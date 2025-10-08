"""
API araçları modülü
FastAPI uygulaması başlatma, rota işleme ve araç fonksiyonları sağlar
"""

# Uygulama başlatma
from .app import (
    create_app
)

# Rota işleyicileri
from .routes import (
    read_index,
    get_css,
    get_js,
    get_api_info,
    health_check,
    list_models,
    chat_completions,
    cancel_request,
    get_queue_status,
    websocket_log_endpoint
)

# Yardımcı fonksiyonlar
from .utils import (
    generate_sse_chunk,
    generate_sse_stop_chunk,
    generate_sse_error_chunk,
    use_stream_response,
    clear_stream_queue,
    use_helper_get_response,
    validate_chat_request,
    prepare_combined_prompt,
    estimate_tokens,
    calculate_usage_stats
)

# İstek işlemcisi
from .request_processor import (
    _process_request_refactored
)

# Kuyruk işçisi
from .queue_worker import (
    queue_worker
)

__all__ = [
    # Uygulama başlatma
    'create_app',
    # Rota işleyicileri
    'read_index',
    'get_css',
    'get_js',
    'get_api_info',
    'health_check',
    'list_models',
    'chat_completions',
    'cancel_request',
    'get_queue_status',
    'websocket_log_endpoint',
    # Yardımcı fonksiyonlar
    'generate_sse_chunk',
    'generate_sse_stop_chunk',
    'generate_sse_error_chunk',
    'use_stream_response',
    'clear_stream_queue',
    'use_helper_get_response',
    'validate_chat_request',
    'prepare_combined_prompt',
    'estimate_tokens',
    'calculate_usage_stats',
    # İstek işlemcisi
    '_process_request_refactored',
    # Kuyruk işçisi
    'queue_worker'
] 
