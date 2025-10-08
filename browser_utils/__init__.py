# --- browser_utils/__init__.py ---
# Tarayıcı işlem araçları modülü
from .initialization import _initialize_page_logic, _close_page_logic, signal_camoufox_shutdown, enable_temporary_chat_mode
from .operations import (
    _handle_model_list_response,
    detect_and_extract_page_error,
    save_error_snapshot,
    get_response_via_edit_button,
    get_response_via_copy_button,
    _wait_for_response_completion,
    _get_final_response_content,
    get_raw_text_content,
    get_default_qwen_models,
)
from .model_management import (
    refresh_model_catalog,
    switch_ai_studio_model,
    load_excluded_models,
    _handle_initial_model_state_and_storage,
    _set_model_from_page_display,
    _verify_ui_state_settings,
    _force_ui_state_settings,
    _force_ui_state_with_retry,
    _verify_and_apply_ui_state
)
from .script_manager import ScriptManager, script_manager

__all__ = [
    # Başlatma ile ilgili
    '_initialize_page_logic',
    '_close_page_logic',
    'signal_camoufox_shutdown',
    'enable_temporary_chat_mode',

    # Sayfa işlemi ile ilgili
    '_handle_model_list_response',
    'detect_and_extract_page_error',
    'save_error_snapshot',
    'get_response_via_edit_button',
    'get_response_via_copy_button',
    '_wait_for_response_completion',
    '_get_final_response_content',
    'get_raw_text_content',
    'get_default_qwen_models',

    # Model yönetimi ile ilgili
    'refresh_model_catalog',
    'switch_ai_studio_model',
    'load_excluded_models',
    '_handle_initial_model_state_and_storage',
    '_set_model_from_page_display',
    '_verify_ui_state_settings',
    '_force_ui_state_settings',
    '_force_ui_state_with_retry',
    '_verify_and_apply_ui_state',

    # Script yönetimi ile ilgili
    'ScriptManager',
    'script_manager'
]
