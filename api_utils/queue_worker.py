"""
Kuyruk işçisi modülü
İstek kuyruğundaki görevleri işler
"""

import asyncio
import time
from fastapi import HTTPException



async def queue_worker():
    """Kuyruk işçisi, istek kuyruğundaki görevleri işler"""
    # Global değişkenleri içe aktar
    from server import (
        logger, request_queue, processing_lock, model_switching_lock, 
        params_cache_lock
    )
    
    logger.info("--- Kuyruk Worker başlatıldı ---")
    
    # Global değişkenleri kontrol et ve başlat
    if request_queue is None:
        logger.info("request_queue başlatılıyor...")
        from asyncio import Queue
        request_queue = Queue()
    
    if processing_lock is None:
        logger.info("processing_lock başlatılıyor...")
        from asyncio import Lock
        processing_lock = Lock()
    
    if model_switching_lock is None:
        logger.info("model_switching_lock başlatılıyor...")
        from asyncio import Lock
        model_switching_lock = Lock()
    
    if params_cache_lock is None:
        logger.info("params_cache_lock başlatılıyor...")
        from asyncio import Lock
        params_cache_lock = Lock()
    
    was_last_request_streaming = False
    last_request_completion_time = 0
    
    while True:
        request_item = None
        result_future = None
        req_id = "UNKNOWN"
        completion_event = None
        
        try:
            # 检查队列中的项目，清理已断开连接的请求
            queue_size = request_queue.qsize()
            if queue_size > 0:
                checked_count = 0
                items_to_requeue = []
                processed_ids = set()
                
                while checked_count < queue_size and checked_count < 10:
                    try:
                        item = request_queue.get_nowait()
                        item_req_id = item.get("req_id", "unknown")
                        
                        if item_req_id in processed_ids:
                            items_to_requeue.append(item)
                            continue
                            
                        processed_ids.add(item_req_id)
                        
                        if not item.get("cancelled", False):
                            item_http_request = item.get("http_request")
                            if item_http_request:
                                try:
                                    if await item_http_request.is_disconnected():
                                        logger.info(f"[{item_req_id}] (Worker Queue Check) İstemci bağlantısı kesildi, istek iptal ediliyor.")
                                        item["cancelled"] = True
                                        item_future = item.get("result_future")
                                        if item_future and not item_future.done():
                                            item_future.set_exception(HTTPException(status_code=499, detail=f"[{item_req_id}] Client disconnected while queued."))
                                except Exception as check_err:
                                    logger.error(f"[{item_req_id}] (Worker Queue Check) Error checking disconnect: {check_err}")
                        
                        items_to_requeue.append(item)
                        checked_count += 1
                    except asyncio.QueueEmpty:
                        break
                
                for item in items_to_requeue:
                    await request_queue.put(item)
            
            # 获取下一个请求
            try:
                request_item = await asyncio.wait_for(request_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                # 如果5秒内没有新请求，继续循环检查
                continue
            
            req_id = request_item["req_id"]
            request_data = request_item["request_data"]
            http_request = request_item["http_request"]
            result_future = request_item["result_future"]

            if request_item.get("cancelled", False):
                logger.info(f"[{req_id}] (Worker) İstek iptal edilmiş, atlanıyor.")
                if not result_future.done():
                    result_future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] İstek kullanıcı tarafından iptal edildi"))
                request_queue.task_done()
                continue

            is_streaming_request = request_data.stream
            logger.info(f"[{req_id}] (Worker) İstek kuyruğundan alındı. Mod: {'akış' if is_streaming_request else 'akış dışı'}")

            # 优化：在开始处理前主动检测客户端连接状态，避免不必要的处理
            from api_utils.request_processor import _test_client_connection
            is_connected = await _test_client_connection(req_id, http_request)
            if not is_connected:
                logger.info(f"[{req_id}] (Worker) ✅ İstemci bağlantısı kesildi; işlem atlanıyor")
                if not result_future.done():
                    result_future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] İstemci işlem başlamadan bağlantıyı kesti"))
                request_queue.task_done()
                continue
            
            # 流式请求间隔控制
            current_time = time.time()
            if was_last_request_streaming and is_streaming_request and (current_time - last_request_completion_time < 1.0):
                delay_time = max(0.5, 1.0 - (current_time - last_request_completion_time))
                logger.info(f"[{req_id}] (Worker) Ardışık akış isteği, {delay_time:.2f}s gecikme ekleniyor...")
                await asyncio.sleep(delay_time)
            
            # 等待锁前再次主动检测客户端连接
            is_connected = await _test_client_connection(req_id, http_request)
            if not is_connected:
                logger.info(f"[{req_id}] (Worker) ✅ Kilit beklenirken istemci bağlantısı kesildi, işlem iptal ediliyor")
                if not result_future.done():
                    result_future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] İstemci isteği kapattı"))
                request_queue.task_done()
                continue
            
            logger.info(f"[{req_id}] (Worker) İşleme kilidi bekleniyor...")
            async with processing_lock:
                logger.info(f"[{req_id}] (Worker) İşleme kilidi alındı, çekirdek işlem başlatılıyor...")
                completion_event = None
                submit_btn_loc = None
                client_disco_checker = None
                disconnect_monitor_task = None
                client_disconnected_early = False
                current_request_was_streaming = False
                
                # 获取锁后最终主动检测客户端连接
                is_connected = await _test_client_connection(req_id, http_request)
                if not is_connected:
                    logger.info(f"[{req_id}] (Worker) ✅ Kilit alındıktan sonra istemci bağlantısı kesildi, işlem iptal ediliyor")
                    if not result_future.done():
                        result_future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] İstemci isteği kapattı"))
                elif result_future.done():
                    logger.info(f"[{req_id}] (Worker) Future işlem öncesinde tamamlanmış veya iptal edilmiş; atlanıyor.")
                else:
                    # Her yeni istekte sohbeti sıfırla
                    try:
                        from server import page_instance, is_page_ready
                        if page_instance and is_page_ready:
                            from browser_utils.page_controller import PageController

                            def noop_disconnect_checker(stage: str = "") -> bool:
                                return False

                            page_controller = PageController(page_instance, logger, req_id)
                            await page_controller.clear_chat_history(noop_disconnect_checker)
                            logger.info(f"[{req_id}] (Worker) ✅ İstek öncesi sohbet geçmişi sıfırlandı.")
                        else:
                            logger.warning(f"[{req_id}] (Worker) Sohbet sıfırlanamadı; sayfa hazır değil (page_ready={is_page_ready}).")
                    except Exception as pre_clear_err:
                        logger.error(f"[{req_id}] (Worker) İstek öncesi sohbet temizlenirken hata: {pre_clear_err}", exc_info=True)

                    # 调用实际的请求处理函数
                    try:
                        from api_utils import _process_request_refactored
                        returned_value = await _process_request_refactored(
                            req_id, request_data, http_request, result_future
                        )
                        
                        if isinstance(returned_value, tuple) and len(returned_value) == 3:
                            completion_event, submit_btn_loc, client_disco_checker = returned_value
                            if completion_event is not None:
                                current_request_was_streaming = True
                                logger.info(f"[{req_id}] (Worker) _process_request_refactored returned stream info (event, locator, checker).")
                            else:
                                current_request_was_streaming = False
                                logger.info(f"[{req_id}] (Worker) _process_request_refactored returned a tuple, but completion_event is None (likely non-stream or early exit).")
                        elif returned_value is None:
                            current_request_was_streaming = False
                            logger.info(f"[{req_id}] (Worker) _process_request_refactored returned non-stream completion (None).")
                        else:
                            current_request_was_streaming = False
                            logger.warning(f"[{req_id}] (Worker) _process_request_refactored returned unexpected type: {type(returned_value)}")

                        # 统一的客户端断开检测和响应处理
                        if completion_event:
                            # 流式模式：等待流式生成器完成信号
                            logger.info(f"[{req_id}] (Worker) Akış üreticisinden tamamlanma sinyali bekleniyor...")

                            # 创建一个增强的客户端断开检测器，支持提前done信号触发
                            client_disconnected_early = False

                            async def enhanced_disconnect_monitor():
                                nonlocal client_disconnected_early
                                while not completion_event.is_set():
                                    try:
                                        # İstemci bağlantısını proaktif olarak kontrol et
                                        is_connected = await _test_client_connection(req_id, http_request)
                                        if not is_connected:
                                            logger.info(f"[{req_id}] (Worker) ✅ Akış sırasında istemci bağlantısı kesildi, done sinyali erken tetiklendi")
                                            client_disconnected_early = True
                                            # Beklemeyi sonlandırmak için completion_event'i hemen ayarla
                                            if not completion_event.is_set():
                                                completion_event.set()
                                            break
                                        await asyncio.sleep(0.3)  # Daha sık kontrol aralığı
                                    except Exception as e:
                                        logger.error(f"[{req_id}] (Worker) Gelişmiş bağlantı kesilme denetleyicisinde hata: {e}")
                                        break

                            # 启动增强的断开连接监控
                            disconnect_monitor_task = asyncio.create_task(enhanced_disconnect_monitor())
                        else:
                            # 非流式模式：等待处理完成并检测客户端断开
                            logger.info(f"[{req_id}] (Worker) Akış dışı modda işlem tamamlanması bekleniyor...")

                            client_disconnected_early = False

                            async def non_streaming_disconnect_monitor():
                                nonlocal client_disconnected_early
                                while not result_future.done():
                                    try:
                                        # İstemci bağlantısını proaktif olarak kontrol et
                                        is_connected = await _test_client_connection(req_id, http_request)
                                        if not is_connected:
                                            logger.info(f"[{req_id}] (Worker) ✅ Akış dışı işlem sırasında istemci bağlantısı kesildi, işlem iptal ediliyor")
                                            client_disconnected_early = True
                                            # result_future'ı iptal et
                                            if not result_future.done():
                                                result_future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] İstemci akış dışı işlem sırasında bağlantıyı kesti"))
                                            break
                                        await asyncio.sleep(0.3)  # Daha sık kontrol aralığı
                                    except Exception as e:
                                        logger.error(f"[{req_id}] (Worker) Akış dışı bağlantı denetleyicisinde hata: {e}")
                                        break

                            # 启动非流式断开连接监控
                            disconnect_monitor_task = asyncio.create_task(non_streaming_disconnect_monitor())

                        # 等待处理完成（流式或非流式）
                        try:
                            if completion_event:
                                # 流式模式：等待completion_event
                                from server import RESPONSE_COMPLETION_TIMEOUT
                                await asyncio.wait_for(completion_event.wait(), timeout=RESPONSE_COMPLETION_TIMEOUT/1000 + 60)
                                logger.info(f"[{req_id}] (Worker) ✅ Akış üreticisinden tamamlanma sinyali alındı. İstemci erken koptu mu: {client_disconnected_early}")
                            else:
                                # 非流式模式：等待result_future完成
                                from server import RESPONSE_COMPLETION_TIMEOUT
                                await asyncio.wait_for(asyncio.shield(result_future), timeout=RESPONSE_COMPLETION_TIMEOUT/1000 + 60)
                                logger.info(f"[{req_id}] (Worker) ✅ Akış dışı işlem tamamlandı. İstemci erken koptu mu: {client_disconnected_early}")

                            # 如果客户端提前断开，跳过按钮状态处理
                            if client_disconnected_early:
                                logger.info(f"[{req_id}] (Worker) İstemci erken koptu, buton durumu işlemesi atlandı")
                            elif submit_btn_loc is not None and client_disco_checker and completion_event:
                                    # 等待发送按钮禁用确认流式响应完全结束
                                    logger.info(f"[{req_id}] (Worker) Akış yanıtı tamamlandı, gönder butonu durumu kontrol ediliyor...")
                                    wait_timeout_ms = 30000  # 30 seconds
                                    try:
                                        from playwright.async_api import expect as expect_async
                                        from api_utils.request_processor import ClientDisconnectedError

                                        # 检查客户端连接状态
                                        client_disco_checker("Akış yanıtı sonrası buton durumu kontrolü - ön kontrol")
                                        await asyncio.sleep(0.5)  # 给UI一点时间更新

                                        # 检查按钮是否仍然启用，如果启用则直接点击停止
                                        logger.info(f"[{req_id}] (Worker) Gönder butonu durumu kontrol ediliyor...")
                                        try:
                                            is_button_enabled = await submit_btn_loc.is_enabled(timeout=2000) if submit_btn_loc else False
                                            logger.info(f"[{req_id}] (Worker) Gönder butonu etkin mi: {is_button_enabled}")

                                            if is_button_enabled:
                                                # 流式响应完成后按钮仍启用，直接点击停止
                                                logger.info(f"[{req_id}] (Worker) Akış tamamlandı fakat buton etkin; üretimi durdurmak için butona tıklanıyor...")
                                                await submit_btn_loc.click(timeout=5000, force=True)
                                                logger.info(f"[{req_id}] (Worker) ✅ Gönder butonuna tıklama tamamlandı.")
                                            else:
                                                logger.info(f"[{req_id}] (Worker) Gönder butonu zaten devre dışı, işlem gerekmiyor.")
                                        except Exception as button_check_err:
                                            logger.warning(f"[{req_id}] (Worker) Gönder butonu durumu kontrol edilemedi: {button_check_err}")

                                        # 等待按钮最终禁用
                                        logger.info(f"[{req_id}] (Worker) Gönder butonunun tamamen devre dışı kalması bekleniyor...")
                                        await expect_async(submit_btn_loc).to_be_disabled(timeout=wait_timeout_ms)
                                        logger.info(f"[{req_id}] ✅ Gönder butonu devre dışı bırakıldı.")

                                    except Exception as e_pw_disabled:
                                        logger.warning(f"[{req_id}] ⚠️ Akış sonrası buton durumu işlemesinde zaman aşımı veya hata: {e_pw_disabled}")
                                        from api_utils.request_processor import save_error_snapshot
                                        await save_error_snapshot(f"stream_post_submit_button_handling_timeout_{req_id}")
                                    except ClientDisconnectedError:
                                        logger.info(f"[{req_id}] Akış sonrası buton durumu işlenirken istemci bağlantısı kesildi.")
                            elif completion_event and current_request_was_streaming:
                                logger.warning(f"[{req_id}] (Worker) Akış isteği ancak submit_btn_loc veya client_disco_checker sağlanmadı; buton beklemesi atlandı.")

                        except asyncio.TimeoutError:
                            logger.warning(f"[{req_id}] (Worker) ⚠️ İşlemin tamamlanması beklenirken zaman aşımı oluştu.")
                            if not result_future.done():
                                result_future.set_exception(HTTPException(status_code=504, detail=f"[{req_id}] Processing timed out waiting for completion."))
                        except Exception as ev_wait_err:
                            logger.error(f"[{req_id}] (Worker) ❌ İşlemin tamamlanması beklenirken hata oluştu: {ev_wait_err}")
                            if not result_future.done():
                                result_future.set_exception(HTTPException(status_code=500, detail=f"[{req_id}] Error waiting for completion: {ev_wait_err}"))
                        finally:
                            # 清理断开连接监控任务
                            if disconnect_monitor_task and not disconnect_monitor_task.done():
                                disconnect_monitor_task.cancel()
                                try:
                                    await disconnect_monitor_task
                                except asyncio.CancelledError:
                                    pass

                    except Exception as process_err:
                        logger.error(f"[{req_id}] (Worker) _process_request_refactored execution error: {process_err}")
                        if not result_future.done():
                            result_future.set_exception(HTTPException(status_code=500, detail=f"[{req_id}] Request processing error: {process_err}"))
            
            logger.info(f"[{req_id}] (Worker) İşleme kilidi serbest bırakılıyor.")

            # Kilidi bıraktıktan sonra temizleme işlemlerini hemen gerçekleştir
            try:
                # Akış kuyruğu önbelleğini temizle
                from api_utils import clear_stream_queue
                await clear_stream_queue()

                # Akış ve akış dışı tüm modlar için sohbet geçmişini temizle
                if submit_btn_loc and client_disco_checker:
                    from server import page_instance, is_page_ready
                    if page_instance and is_page_ready:
                        from browser_utils.page_controller import PageController
                        page_controller = PageController(page_instance, logger, req_id)
                        logger.info(f"[{req_id}] (Worker) Sohbet geçmişi temizleniyor ({'akış' if completion_event else 'akış dışı'} mod)...")
                        await page_controller.clear_chat_history(client_disco_checker)
                        logger.info(f"[{req_id}] (Worker) ✅ Sohbet geçmişi temizlendi.")
                else:
                    logger.info(f"[{req_id}] (Worker) Sohbet geçmişi temizliği atlandı; gerekli parametreler eksik (submit_btn_loc: {bool(submit_btn_loc)}, client_disco_checker: {bool(client_disco_checker)})")
            except Exception as clear_err:
                logger.error(f"[{req_id}] (Worker) Temizleme işlemi sırasında hata oluştu: {clear_err}", exc_info=True)

            was_last_request_streaming = is_streaming_request
            last_request_completion_time = time.time()
            
        except asyncio.CancelledError:
            logger.info("--- Kuyruk işçisi iptal edildi ---")
            if result_future and not result_future.done():
                result_future.cancel("Worker cancelled")
            break
        except Exception as e:
            logger.error(f"[{req_id}] (Worker) ❌ İstek işlenirken beklenmeyen hata: {e}", exc_info=True)
            if result_future and not result_future.done():
                result_future.set_exception(HTTPException(status_code=500, detail=f"[{req_id}] Sunucu iç hatası: {e}"))
        finally:
            if request_item:
                request_queue.task_done()
    
    logger.info("--- Kuyruk işçisi durduruldu ---") 
