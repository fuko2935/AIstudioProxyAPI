"""
FastAPI yönlendirici (route) işleyicilerini barındıran modül.
Tüm API uç noktalarına ait işlevleri içerir.
"""

import asyncio
import os
import random
import time
import uuid
from typing import Dict, List, Any, Set
from asyncio import Queue, Future, Lock, Event
import logging

from fastapi import HTTPException, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from playwright.async_api import Page as AsyncPage

# --- Yapılandırma modülünü içe aktar ---
from config import *

# --- models modülünü içe aktar ---
from models import ChatCompletionRequest, WebSocketConnectionManager

# --- browser_utils modülünü içe aktar ---
from browser_utils import _handle_model_list_response, get_default_qwen_models, refresh_model_catalog

# --- Bağımlılıkları içe aktar ---
from .dependencies import *

MODEL_LIST_REFRESH_TTL_SECONDS = int(os.environ.get('MODEL_LIST_REFRESH_TTL_SECONDS', '300'))

# --- Statik dosya uç noktaları ---
async def read_index(logger: logging.Logger = Depends(get_logger)):
    """Ana sayfayı döndürür"""
    index_html_path = os.path.join(os.path.dirname(__file__), "..", "index.html")
    if not os.path.exists(index_html_path):
        logger.error(f"index.html not found at {index_html_path}")
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_html_path)


async def get_css(logger: logging.Logger = Depends(get_logger)):
    """CSS dosyasını döndürür"""
    css_path = os.path.join(os.path.dirname(__file__), "..", "webui.css")
    if not os.path.exists(css_path):
        logger.error(f"webui.css not found at {css_path}")
        raise HTTPException(status_code=404, detail="webui.css not found")
    return FileResponse(css_path, media_type="text/css")


async def get_js(logger: logging.Logger = Depends(get_logger)):
    """JavaScript dosyasını döndürür"""
    js_path = os.path.join(os.path.dirname(__file__), "..", "webui.js")
    if not os.path.exists(js_path):
        logger.error(f"webui.js not found at {js_path}")
        raise HTTPException(status_code=404, detail="webui.js not found")
    return FileResponse(js_path, media_type="application/javascript")


# --- API bilgisi ucu ---
async def get_api_info(request: Request, current_ai_studio_model_id: str = Depends(get_current_ai_studio_model_id)):
    """API bilgilerini döndürür"""
    from api_utils import auth_utils

    server_port = request.url.port or os.environ.get('SERVER_PORT_INFO', '8000')
    host = request.headers.get('host') or f"127.0.0.1:{server_port}"
    scheme = request.headers.get('x-forwarded-proto', 'http')
    base_url = f"{scheme}://{host}"
    api_base = f"{base_url}/v1"
    effective_model_name = current_ai_studio_model_id or MODEL_NAME

    api_key_required = bool(auth_utils.API_KEYS)
    api_key_count = len(auth_utils.API_KEYS)

    if api_key_required:
        message = f"API Key is required. {api_key_count} valid key(s) configured."
    else:
        message = "API Key is not required."

    return JSONResponse(content={
        "model_name": effective_model_name,
        "api_base_url": api_base,
        "server_base_url": base_url,
        "api_key_required": api_key_required,
        "api_key_count": api_key_count,
        "auth_header": "Authorization: Bearer <token> or X-API-Key: <token>" if api_key_required else None,
        "openai_compatible": True,
        "supported_auth_methods": ["Authorization: Bearer", "X-API-Key"] if api_key_required else [],
        "message": message
    })


# --- Sağlık kontrolü ucu ---
async def health_check(
    server_state: Dict[str, Any] = Depends(get_server_state),
    worker_task = Depends(get_worker_task),
    request_queue: Queue = Depends(get_request_queue)
):
    """Sağlık kontrolü"""
    is_worker_running = bool(worker_task and not worker_task.done())
    launch_mode = os.environ.get('LAUNCH_MODE', 'unknown')
    browser_page_critical = launch_mode != "direct_debug_no_browser"
    
    core_ready_conditions = [not server_state["is_initializing"], server_state["is_playwright_ready"]]
    if browser_page_critical:
        core_ready_conditions.extend([server_state["is_browser_connected"], server_state["is_page_ready"]])
    
    is_core_ready = all(core_ready_conditions)
    status_val = "OK" if is_core_ready and is_worker_running else "Error"
    q_size = request_queue.qsize() if request_queue else -1
    
    status_message_parts = []
    if server_state["is_initializing"]: status_message_parts.append("Başlatma devam ediyor")
    if not server_state["is_playwright_ready"]: status_message_parts.append("Playwright hazır değil")
    if browser_page_critical:
        if not server_state["is_browser_connected"]: status_message_parts.append("Tarayıcı bağlı değil")
        if not server_state["is_page_ready"]: status_message_parts.append("Sayfa hazır değil")
    if not is_worker_running: status_message_parts.append("Worker çalışmıyor")
    
    status = {
        "status": status_val,
        "message": "",
        "details": {**server_state, "workerRunning": is_worker_running, "queueLength": q_size, "launchMode": launch_mode, "browserAndPageCritical": browser_page_critical}
    }
    
    if status_val == "OK":
        status["message"] = f"Hizmet çalışıyor; kuyruk uzunluğu: {q_size}."
        return JSONResponse(content=status, status_code=200)
    else:
        status["message"] = f"Hizmet kullanılamıyor; sorun: {(', '.join(status_message_parts) or 'bilinmeyen neden')}. Kuyruk uzunluğu: {q_size}."
        return JSONResponse(content=status, status_code=503)


# --- Model listesi ucu ---
async def list_models(
    logger: logging.Logger = Depends(get_logger),
    model_list_fetch_event: Event = Depends(get_model_list_fetch_event),
    page_instance: AsyncPage = Depends(get_page_instance),
    parsed_model_list: List[Dict[str, Any]] = Depends(get_parsed_model_list),
    excluded_model_ids: Set[str] = Depends(get_excluded_model_ids)
):
    """Model listesini döndürür"""
    logger.info("[API] /v1/models isteği alındı.")

    if not model_list_fetch_event.is_set() and page_instance and not page_instance.is_closed():
        logger.info("/v1/models: Model listesi olayı ayarlanmamış; sayfa yenileniyor...")
        try:
            await page_instance.reload(wait_until="domcontentloaded", timeout=20000)
            await asyncio.wait_for(model_list_fetch_event.wait(), timeout=10.0)
        except Exception as e:
            logger.error(f"/v1/models: Model listesi yenilenirken veya beklenirken hata oluştu: {e}")
        finally:
            if not model_list_fetch_event.is_set():
                model_list_fetch_event.set()
    
    import server

    now = time.time()
    last_refresh = getattr(server, 'model_list_last_refreshed', 0.0)
    refresh_needed = not parsed_model_list or (now - last_refresh > MODEL_LIST_REFRESH_TTL_SECONDS)

    if refresh_needed:
        if page_instance and not page_instance.is_closed():
            logger.info("/v1/models: Önbellek boş ya da süresi dolmuş; model kataloğu yenileniyor.")
            try:
                refreshed_models = await refresh_model_catalog(page_instance, req_id="api-model-refresh")
            except Exception as refresh_err:
                logger.error(f"/v1/models: Model kataloğu yenilenemedi: {refresh_err}")
                refreshed_models = []

            filtered_models = [m for m in refreshed_models if m.get("id") not in excluded_model_ids] if refreshed_models else []

            if filtered_models:
                parsed_model_list = filtered_models
                server.parsed_model_list = filtered_models
                server.global_model_list_raw_json = filtered_models
                server.model_list_last_refreshed = time.time()
                if model_list_fetch_event and not model_list_fetch_event.is_set():
                    model_list_fetch_event.set()
            else:
                logger.warning("/v1/models: Yenileme sonrası kullanılabilir model bulunamadı; DEFAULT_QWEN_MODELS kullanılacak.")
                parsed_model_list = get_default_qwen_models()
                server.parsed_model_list = parsed_model_list
                server.global_model_list_raw_json = parsed_model_list
                server.model_list_last_refreshed = time.time()
                if model_list_fetch_event and not model_list_fetch_event.is_set():
                    model_list_fetch_event.set()
        else:
            logger.warning("/v1/models: Sayfa örneği mevcut değil; DEFAULT_QWEN_MODELS kullanılacak.")
            parsed_model_list = get_default_qwen_models()
            server.parsed_model_list = parsed_model_list
            server.global_model_list_raw_json = parsed_model_list
            server.model_list_last_refreshed = time.time()
            if model_list_fetch_event and not model_list_fetch_event.is_set():
                model_list_fetch_event.set()

    if parsed_model_list:
        final_model_list = [m for m in parsed_model_list if m.get("id") not in excluded_model_ids]
    else:
        final_model_list = get_default_qwen_models()

    if not final_model_list:
        logger.warning("/v1/models: Filtrelenen model listesi boş; DEFAULT_QWEN_MODELS son çare olarak kullanılacak.")
        final_model_list = get_default_qwen_models()

    return {"object": "list", "data": final_model_list}

# --- Sohbet tamamlanma ucu ---
async def chat_completions(
    request: ChatCompletionRequest,
    http_request: Request,
    logger: logging.Logger = Depends(get_logger),
    request_queue: Queue = Depends(get_request_queue),
    server_state: Dict[str, Any] = Depends(get_server_state),
    worker_task = Depends(get_worker_task)
):
    """Sohbet tamamlama isteğini işler"""
    req_id = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=7))
    logger.info(f"[{req_id}] /v1/chat/completions isteği alındı (Stream={request.stream})")
    
    launch_mode = os.environ.get('LAUNCH_MODE', 'unknown')
    browser_page_critical = launch_mode != "direct_debug_no_browser"
    
    service_unavailable = server_state["is_initializing"] or \
                          not server_state["is_playwright_ready"] or \
                          (browser_page_critical and (not server_state["is_page_ready"] or not server_state["is_browser_connected"])) or \
                          not worker_task or worker_task.done()

    if service_unavailable:
        raise HTTPException(status_code=503, detail=f"[{req_id}] Hizmet şu anda kullanılamıyor. Lütfen daha sonra yeniden deneyin.", headers={"Retry-After": "30"})
    
    result_future = Future()
    await request_queue.put({
        "req_id": req_id, "request_data": request, "http_request": http_request,
        "result_future": result_future, "enqueue_time": time.time(), "cancelled": False
    })
    
    try:
        timeout_seconds = RESPONSE_COMPLETION_TIMEOUT / 1000 + 120
        return await asyncio.wait_for(result_future, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"[{req_id}] İstek işlenirken zaman aşımı oluştu.")
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail=f"[{req_id}] İstek istemci tarafından iptal edildi.")
    except HTTPException as http_exc:
        # İstemci bağlantısı koptuğunda daha nazik bir log seviyesi kullan
        if http_exc.status_code == 499:
            logger.info(f"[{req_id}] İstemci bağlantısı kesildi: {http_exc.detail}")
        else:
            logger.warning(f"[{req_id}] HTTP hatası: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.exception(f"[{req_id}] Worker yanıtını beklerken hata oluştu")
        raise HTTPException(status_code=500, detail=f"[{req_id}] Sunucu iç hatası: {e}")


# --- İstek iptali ile ilgili yardımcılar ---
async def cancel_queued_request(req_id: str, request_queue: Queue, logger: logging.Logger) -> bool:
    """Kuyruktaki bir isteği iptal eder"""
    items_to_requeue = []
    found = False
    try:
        while not request_queue.empty():
            item = request_queue.get_nowait()
            if item.get("req_id") == req_id:
                logger.info(f"[{req_id}] İstek kuyrukta bulunup iptal edildi.")
                item["cancelled"] = True
                if (future := item.get("result_future")) and not future.done():
                    future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] Request cancelled."))
                found = True
            items_to_requeue.append(item)
    finally:
        for item in items_to_requeue:
            await request_queue.put(item)
    return found


async def cancel_request(
    req_id: str,
    logger: logging.Logger = Depends(get_logger),
    request_queue: Queue = Depends(get_request_queue)
):
    """İstek iptal uç noktası"""
    logger.info(f"[{req_id}] İptal isteği alındı.")
    if await cancel_queued_request(req_id, request_queue, logger):
        return JSONResponse(content={"success": True, "message": f"Request {req_id} marked as cancelled."})
    else:
        return JSONResponse(status_code=404, content={"success": False, "message": f"Request {req_id} not found in queue."})


# --- Kuyruk durumu ucu ---
async def get_queue_status(
    request_queue: Queue = Depends(get_request_queue),
    processing_lock: Lock = Depends(get_processing_lock)
):
    """Kuyruğun durumunu döndürür"""
    queue_items = list(request_queue._queue)
    return JSONResponse(content={
        "queue_length": len(queue_items),
        "is_processing_locked": processing_lock.locked(),
        "items": sorted([
            {
                "req_id": item.get("req_id", "unknown"),
                "enqueue_time": item.get("enqueue_time", 0),
                "wait_time_seconds": round(time.time() - item.get("enqueue_time", 0), 2),
                "is_streaming": item.get("request_data").stream,
                "cancelled": item.get("cancelled", False)
            } for item in queue_items
        ], key=lambda x: x.get("enqueue_time", 0))
    })


# --- WebSocket günlük ucu ---
async def websocket_log_endpoint(
    websocket: WebSocket,
    logger: logging.Logger = Depends(get_logger),
    log_ws_manager: WebSocketConnectionManager = Depends(get_log_ws_manager)
):
    """WebSocket üzerinden log akışını yönetir"""
    if not log_ws_manager:
        await websocket.close(code=1011)
        return
    
    client_id = str(uuid.uuid4())
    try:
        await log_ws_manager.connect(client_id, websocket)
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Log WebSocket'i (istemci {client_id}) hata verdi: {e}", exc_info=True)
    finally:
        log_ws_manager.disconnect(client_id)


# --- API anahtarı yönetimi veri modelleri ---
class ApiKeyRequest(BaseModel):
    key: str

class ApiKeyTestRequest(BaseModel):
    key: str


# --- API anahtarı yönetim uçları ---
async def get_api_keys(logger: logging.Logger = Depends(get_logger)):
    """API anahtarı listesini döndürür"""
    from api_utils import auth_utils
    try:
        auth_utils.initialize_keys()
        keys_info = [{"value": key, "status": "geçerli"} for key in auth_utils.API_KEYS]
        return JSONResponse(content={"success": True, "keys": keys_info, "total_count": len(keys_info)})
    except Exception as e:
        logger.error(f"API anahtarı listesi alınamadı: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def add_api_key(request: ApiKeyRequest, logger: logging.Logger = Depends(get_logger)):
    """API anahtarı ekler"""
    from api_utils import auth_utils
    key_value = request.key.strip()
    if not key_value or len(key_value) < 8:
        raise HTTPException(status_code=400, detail="Geçersiz API anahtarı formatı.")
    
    auth_utils.initialize_keys()
    if key_value in auth_utils.API_KEYS:
        raise HTTPException(status_code=400, detail="Bu API anahtarı zaten mevcut.")

    try:
        # --- MODIFIED LINE ---
        # Use the centralized path from auth_utils
        key_file_path = auth_utils.KEY_FILE_PATH
        with open(key_file_path, 'a+', encoding='utf-8') as f:
            f.seek(0)
            if f.read(): f.write("\n")
            f.write(key_value)
        
        auth_utils.initialize_keys()
        logger.info(f"API anahtarı eklendi: {key_value[:4]}...{key_value[-4:]}")
        return JSONResponse(content={"success": True, "message": "API anahtarı başarıyla eklendi", "key_count": len(auth_utils.API_KEYS)})
    except Exception as e:
        logger.error(f"API anahtarı eklenemedi: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def test_api_key(request: ApiKeyTestRequest, logger: logging.Logger = Depends(get_logger)):
    """API anahtarını doğrular"""
    from api_utils import auth_utils
    key_value = request.key.strip()
    if not key_value:
        raise HTTPException(status_code=400, detail="API anahtarı boş olamaz.")
    
    auth_utils.initialize_keys()
    is_valid = auth_utils.verify_api_key(key_value)
    status_text = "geçerli" if is_valid else "geçersiz"
    logger.info(f"API anahtarı testi: {key_value[:4]}...{key_value[-4:]} - {status_text}")
    return JSONResponse(content={"success": True, "valid": is_valid, "message": "Anahtar geçerli" if is_valid else "Anahtar geçersiz veya mevcut değil"})


async def delete_api_key(request: ApiKeyRequest, logger: logging.Logger = Depends(get_logger)):
    """API anahtarını siler"""
    from api_utils import auth_utils
    key_value = request.key.strip()
    if not key_value:
        raise HTTPException(status_code=400, detail="API anahtarı boş olamaz.")

    auth_utils.initialize_keys()
    if key_value not in auth_utils.API_KEYS:
        raise HTTPException(status_code=404, detail="API anahtarı bulunamadı.")

    try:
        # --- MODIFIED LINE ---
        # Use the centralized path from auth_utils
        key_file_path = auth_utils.KEY_FILE_PATH
        with open(key_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        with open(key_file_path, 'w', encoding='utf-8') as f:
            f.writelines(line for line in lines if line.strip() != key_value)
            
        auth_utils.initialize_keys()
        logger.info(f"API anahtarı silindi: {key_value[:4]}...{key_value[-4:]}")
        return JSONResponse(content={"success": True, "message": "API anahtarı başarıyla silindi", "key_count": len(auth_utils.API_KEYS)})
    except Exception as e:
        logger.error(f"API anahtarı silinemedi: {e}")
        raise HTTPException(status_code=500, detail=str(e))

