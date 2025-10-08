import asyncio
import multiprocessing
import random
import time
import json
from typing import List, Optional, Dict, Any, Union, AsyncGenerator, Tuple, Callable, Set
import os
import traceback
from contextlib import asynccontextmanager
import sys
import platform
import logging
import logging.handlers
import socket # __main__ içinde basit doğrudan çalıştırma ipucu için socket'i sakla
from asyncio import Queue, Lock, Future, Task, Event

# Yeni: load_dotenv'i içe aktar
from dotenv import load_dotenv

# Yeni: Tüm diğer içe aktarmalardan önce .env dosyasını yükle
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from playwright.async_api import Page as AsyncPage, Browser as AsyncBrowser, Playwright as AsyncPlaywright, Error as PlaywrightAsyncError, expect as expect_async, BrowserContext as AsyncBrowserContext, Locator, TimeoutError
from playwright.async_api import async_playwright
from urllib.parse import urljoin, urlparse
import uuid
import datetime
import aiohttp
import stream
import queue

# --- Yapılandırma modülü içe aktarmaları ---
from config import *

# --- models modülü içe aktarmaları ---
from models import (
    FunctionCall,
    ToolCall,
    MessageContentItem, 
    Message,
    ChatCompletionRequest,
    ClientDisconnectedError,
    StreamToLogger,
    WebSocketConnectionManager,
    WebSocketLogHandler
)

# --- logging_utils modülü içe aktarmaları ---
from logging_utils import setup_server_logging, restore_original_streams

# --- browser_utils modülü içe aktarmaları ---
from browser_utils import (
    _initialize_page_logic,
    _close_page_logic,
    signal_camoufox_shutdown,
    _handle_model_list_response,
    detect_and_extract_page_error,
    save_error_snapshot,
    get_response_via_edit_button,
    get_response_via_copy_button,
    _wait_for_response_completion,
    _get_final_response_content,
    get_raw_text_content,
    switch_ai_studio_model,
    load_excluded_models,
    _handle_initial_model_state_and_storage,
    _set_model_from_page_display
)

# --- api_utils modülü içe aktarmaları ---
from api_utils import (
    generate_sse_chunk,
    generate_sse_stop_chunk, 
    generate_sse_error_chunk,
    use_helper_get_response,
    use_stream_response,
    clear_stream_queue,
    prepare_combined_prompt,
    validate_chat_request,
    _process_request_refactored,
    create_app,
    queue_worker
)

# --- stream queue ---
STREAM_QUEUE:Optional[multiprocessing.Queue] = None
STREAM_PROCESS = None

# --- Global State ---
playwright_manager: Optional[AsyncPlaywright] = None
browser_instance: Optional[AsyncBrowser] = None
page_instance: Optional[AsyncPage] = None
is_playwright_ready = False
is_browser_connected = False
is_page_ready = False
is_initializing = False

# --- Global proxy yapılandırması ---
PLAYWRIGHT_PROXY_SETTINGS: Optional[Dict[str, str]] = None

global_model_list_raw_json: Optional[List[Any]] = None
parsed_model_list: List[Dict[str, Any]] = []
model_list_fetch_event = asyncio.Event()
model_list_last_refreshed: float = 0.0

current_ai_studio_model_id: Optional[str] = None
model_switching_lock: Optional[Lock] = None

excluded_model_ids: Set[str] = set()

request_queue: Optional[Queue] = None
processing_lock: Optional[Lock] = None
worker_task: Optional[Task] = None

page_params_cache: Dict[str, Any] = {}
params_cache_lock: Optional[Lock] = None

logger = logging.getLogger("AIStudioProxyServer")
log_ws_manager = None


# --- FastAPI App tanımı ---
app = create_app()

# --- Main Guard ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 2048))
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=False
    )