"""
CSS选择器配置模块
包含所有用于页面元素定位的CSS选择器
"""

# --- 输入相关选择器 ---
PROMPT_TEXTAREA_SELECTOR = '#chat-input'
INPUT_SELECTOR = PROMPT_TEXTAREA_SELECTOR
INPUT_SELECTOR2 = PROMPT_TEXTAREA_SELECTOR

# --- 按钮选择器 ---
SUBMIT_BUTTON_SELECTOR = '#send-message-button'
CLEAR_CHAT_BUTTON_SELECTOR = '#new-chat-button'
CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR = '[data-qwen-not-supported]'
UPLOAD_BUTTON_SELECTOR = 'button.chat-prompt-upload-group-btn'

# --- 响应相关选择器 ---
RESPONSE_CONTAINER_SELECTOR = '.response-message-body--normal, .response-message-body--media'
RESPONSE_TEXT_SELECTOR = '.response-message-body--normal, .response-message-body--media'

# --- 加载和状态选择器 ---
LOADING_SPINNER_SELECTOR = '.running-panel-text-loading, .qwen-chat-loading-icon'
OVERLAY_SELECTOR = 'div[role="dialog"]'

# --- 错误提示选择器 ---
ERROR_TOAST_SELECTOR = '.toast-warning, .toast-error, .chat-toast'

# --- 编辑相关选择器 ---
EDIT_MESSAGE_BUTTON_SELECTOR = '[data-qwen-not-supported]'
MESSAGE_TEXTAREA_SELECTOR = '[data-qwen-not-supported]'
FINISH_EDIT_BUTTON_SELECTOR = '[data-qwen-not-supported]'

# --- 菜单和复制相关选择器 ---
MORE_OPTIONS_BUTTON_SELECTOR = 'button[data-testid="message-actions"]'
COPY_MARKDOWN_BUTTON_SELECTOR = 'button[data-testid="copy-markdown"]'
COPY_MARKDOWN_BUTTON_SELECTOR_ALT = 'button[data-testid="copy"]'

# --- 设置相关选择器 ---
MAX_OUTPUT_TOKENS_SELECTOR = '[data-qwen-not-supported]'
STOP_SEQUENCE_INPUT_SELECTOR = '[data-qwen-not-supported]'
MAT_CHIP_REMOVE_BUTTON_SELECTOR = '[data-qwen-not-supported]'
TOP_P_INPUT_SELECTOR = '[data-qwen-not-supported]'
TEMPERATURE_INPUT_SELECTOR = '[data-qwen-not-supported]'
USE_URL_CONTEXT_SELECTOR = '[data-qwen-not-supported]'
SET_THINKING_BUDGET_TOGGLE_SELECTOR = '[data-qwen-not-supported]'
# Thinking budget slider input
THINKING_BUDGET_INPUT_SELECTOR = '[data-qwen-not-supported]'
# --- Google Search Grounding ---
GROUNDING_WITH_GOOGLE_SEARCH_TOGGLE_SELECTOR = '[data-qwen-not-supported]'
