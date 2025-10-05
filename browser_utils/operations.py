# --- browser_utils/operations.py ---
# 浏览器页面操作相关功能模块

import asyncio
import time
import json
import os
import re
import logging
from typing import Optional, Any, List, Dict, Callable, Set

from playwright.async_api import Page as AsyncPage, Locator, Error as PlaywrightAsyncError

# 导入配置和模型
from config import *
from models import ClientDisconnectedError
from .model_management import refresh_model_catalog

logger = logging.getLogger("AIStudioProxyServer")

async def get_raw_text_content(response_element: Locator, previous_text: str, req_id: str) -> str:
    """从响应元素获取原始文本内容"""
    raw_text = previous_text
    try:
        await response_element.wait_for(state='attached', timeout=1000)
        pre_element = response_element.locator('pre').last
        pre_found_and_visible = False
        try:
            await pre_element.wait_for(state='visible', timeout=250)
            pre_found_and_visible = True
        except PlaywrightAsyncError: 
            pass
        
        if pre_found_and_visible:
            try:
                raw_text = await pre_element.inner_text(timeout=500)
            except PlaywrightAsyncError as pre_err:
                if DEBUG_LOGS_ENABLED:
                    logger.debug(f"[{req_id}] (获取原始文本) 获取 pre 元素内部文本失败: {pre_err}")
        else:
            try:
                raw_text = await response_element.inner_text(timeout=500)
            except PlaywrightAsyncError as e_parent:
                if DEBUG_LOGS_ENABLED:
                    logger.debug(f"[{req_id}] (获取原始文本) 获取响应元素内部文本失败: {e_parent}")
    except PlaywrightAsyncError as e_parent:
        if DEBUG_LOGS_ENABLED:
            logger.debug(f"[{req_id}] (获取原始文本) 响应元素未准备好: {e_parent}")
    except Exception as e_unexpected:
        logger.warning(f"[{req_id}] (获取原始文本) 意外错误: {e_unexpected}")
    
    if raw_text != previous_text:
        if DEBUG_LOGS_ENABLED:
            preview = raw_text[:100].replace('\n', '\\n')
            logger.debug(f"[{req_id}] (获取原始文本) 文本已更新，长度: {len(raw_text)}，预览: '{preview}...'")
    return raw_text

def _parse_userscript_models(script_content: str):
    """从油猴脚本中解析模型列表 - 使用JSON解析方式"""
    try:
        # 查找脚本版本号
        version_pattern = r'const\s+SCRIPT_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]'
        version_match = re.search(version_pattern, script_content)
        script_version = version_match.group(1) if version_match else "v1.6"

        # 查找 MODELS_TO_INJECT 数组的内容
        models_array_pattern = r'const\s+MODELS_TO_INJECT\s*=\s*(\[.*?\]);'
        models_match = re.search(models_array_pattern, script_content, re.DOTALL)

        if not models_match:
            logger.warning("未找到 MODELS_TO_INJECT 数组")
            return []

        models_js_code = models_match.group(1)

        # 将JavaScript数组转换为JSON格式
        # 1. 替换模板字符串中的变量
        models_js_code = models_js_code.replace('${SCRIPT_VERSION}', script_version)

        # 2. 移除JavaScript注释
        models_js_code = re.sub(r'//.*?$', '', models_js_code, flags=re.MULTILINE)

        # 3. 将JavaScript对象转换为JSON格式
        # 移除尾随逗号
        models_js_code = re.sub(r',\s*([}\]])', r'\1', models_js_code)

        # 替换单引号为双引号
        models_js_code = re.sub(r"(\w+):\s*'([^']*)'", r'"\1": "\2"', models_js_code)
        # 替换反引号为双引号
        models_js_code = re.sub(r'(\w+):\s*`([^`]*)`', r'"\1": "\2"', models_js_code)
        # 确保属性名用双引号
        models_js_code = re.sub(r'(\w+):', r'"\1":', models_js_code)

        # 4. 解析JSON
        import json
        models_data = json.loads(models_js_code)

        models = []
        for model_obj in models_data:
            if isinstance(model_obj, dict) and 'name' in model_obj:
                models.append({
                    'name': model_obj.get('name', ''),
                    'displayName': model_obj.get('displayName', ''),
                    'description': model_obj.get('description', '')
                })

        logger.info(f"成功解析 {len(models)} 个模型从油猴脚本")
        return models

    except Exception as e:
        logger.error(f"解析油猴脚本模型列表失败: {e}")
        return []


def _get_injected_models():
    """从油猴脚本中获取注入的模型列表，转换为API格式"""
    try:
        # 直接读取环境变量，避免复杂的导入
        enable_injection = os.environ.get('ENABLE_SCRIPT_INJECTION', 'true').lower() in ('true', '1', 'yes')

        if not enable_injection:
            return []

        # 获取脚本文件路径
        script_path = os.environ.get('USERSCRIPT_PATH', 'browser_utils/more_modles.js')

        # 检查脚本文件是否存在
        if not os.path.exists(script_path):
            # 脚本文件不存在，静默返回空列表
            return []

        # 读取油猴脚本内容
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()

        # 从脚本中解析模型列表
        models = _parse_userscript_models(script_content)

        if not models:
            return []

        # 转换为API格式
        injected_models = []
        for model in models:
            model_name = model.get('name', '')
            if not model_name:
                continue  # 跳过没有名称的模型

            if model_name.startswith('models/'):
                simple_id = model_name[7:]  # 移除 'models/' 前缀
            else:
                simple_id = model_name

            display_name = model.get('displayName', model.get('display_name', simple_id))
            description = model.get('description', f'Injected model: {simple_id}')

            # 注意：不再清理显示名称，保留原始的emoji和版本信息

            model_entry = {
                "id": simple_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ai_studio_injected",
                "display_name": display_name,
                "description": description,
                "raw_model_path": model_name,
                "default_temperature": 1.0,
                "default_max_output_tokens": 65536,
                "supported_max_output_tokens": 65536,
                "default_top_p": 0.95,
                "injected": True  # 标记为注入的模型
            }
            injected_models.append(model_entry)

        return injected_models

    except Exception as e:
        # 静默处理错误，不输出日志，返回空列表
        return []


async def _handle_model_list_response(response: Any):
    """处理模型列表响应"""
    import server

    model_list_fetch_event = getattr(server, 'model_list_fetch_event', None)
    excluded_model_ids = getattr(server, 'excluded_model_ids', set())

    if MODELS_ENDPOINT_URL_CONTAINS not in response.url or not response.ok:
        return

    logger.info(f"捕获到模型列表响应: {response.url} (状态: {response.status})")

    page_instance = getattr(server, 'page_instance', None)
    if not page_instance or page_instance.is_closed():
        logger.error("无法刷新模型列表：页面实例不可用。使用默认回退列表。")
        final_models = [dict(model) for model in DEFAULT_QWEN_MODELS]
    else:
        try:
            refreshed_models = await refresh_model_catalog(page_instance, req_id="network-model-refresh")
        except Exception as refresh_err:
            logger.error(f"刷新模型目录时出现错误: {refresh_err}")
            refreshed_models = []

        if refreshed_models:
            filtered_models = [m for m in refreshed_models if m.get("id") not in excluded_model_ids]
        else:
            filtered_models = []

        if filtered_models:
            final_models = filtered_models
        else:
            logger.warning("模型目录刷新返回空结果或全部被排除，使用 DEFAULT_QWEN_MODELS 作为回退。")
            final_models = [dict(model) for model in DEFAULT_QWEN_MODELS]

    server.parsed_model_list = final_models
    server.global_model_list_raw_json = json.dumps({"data": final_models, "object": "list"})
    server.model_list_last_refreshed = time.time()

    if model_list_fetch_event and not model_list_fetch_event.is_set():
        model_list_fetch_event.set()

async def detect_and_extract_page_error(page: AsyncPage, req_id: str) -> Optional[str]:
    """检测并提取页面错误"""
    error_toast_locator = page.locator(ERROR_TOAST_SELECTOR).last
    try:
        await error_toast_locator.wait_for(state='visible', timeout=500)
        message_locator = error_toast_locator.locator('span.content-text')
        error_message = await message_locator.text_content(timeout=500)
        if error_message:
             logger.error(f"[{req_id}]    检测到并提取错误消息: {error_message}")
             return error_message.strip()
        else:
             logger.warning(f"[{req_id}]    检测到错误提示框，但无法提取消息。")
             return "检测到错误提示框，但无法提取特定消息。"
    except PlaywrightAsyncError: 
        return None
    except Exception as e:
        logger.warning(f"[{req_id}]    检查页面错误时出错: {e}")
        return None

async def save_error_snapshot(error_name: str = 'error'):
    """保存错误快照"""
    import server
    name_parts = error_name.split('_')
    req_id = name_parts[-1] if len(name_parts) > 1 and len(name_parts[-1]) == 7 else None
    base_error_name = error_name if not req_id else '_'.join(name_parts[:-1])
    log_prefix = f"[{req_id}]" if req_id else "[无请求ID]"
    page_to_snapshot = server.page_instance
    
    if not server.browser_instance or not server.browser_instance.is_connected() or not page_to_snapshot or page_to_snapshot.is_closed():
        logger.warning(f"{log_prefix} 无法保存快照 ({base_error_name})，浏览器/页面不可用。")
        return
    
    logger.info(f"{log_prefix} 尝试保存错误快照 ({base_error_name})...")
    timestamp = int(time.time() * 1000)
    error_dir = os.path.join(os.path.dirname(__file__), '..', 'errors_py')
    
    try:
        os.makedirs(error_dir, exist_ok=True)
        filename_suffix = f"{req_id}_{timestamp}" if req_id else f"{timestamp}"
        filename_base = f"{base_error_name}_{filename_suffix}"
        screenshot_path = os.path.join(error_dir, f"{filename_base}.png")
        html_path = os.path.join(error_dir, f"{filename_base}.html")
        
        try:
            await page_to_snapshot.screenshot(path=screenshot_path, full_page=True, timeout=15000)
            logger.info(f"{log_prefix}   快照已保存到: {screenshot_path}")
        except Exception as ss_err:
            logger.error(f"{log_prefix}   保存屏幕截图失败 ({base_error_name}): {ss_err}")
        
        try:
            content = await page_to_snapshot.content()
            f = None
            try:
                f = open(html_path, 'w', encoding='utf-8')
                f.write(content)
                logger.info(f"{log_prefix}   HTML 已保存到: {html_path}")
            except Exception as write_err:
                logger.error(f"{log_prefix}   保存 HTML 失败 ({base_error_name}): {write_err}")
            finally:
                if f:
                    try:
                        f.close()
                        logger.debug(f"{log_prefix}   HTML 文件已正确关闭")
                    except Exception as close_err:
                        logger.error(f"{log_prefix}   关闭 HTML 文件时出错: {close_err}")
        except Exception as html_err:
            logger.error(f"{log_prefix}   获取页面内容失败 ({base_error_name}): {html_err}")
    except Exception as dir_err:
        logger.error(f"{log_prefix}   创建错误目录或保存快照时发生其他错误 ({base_error_name}): {dir_err}")

async def get_response_via_edit_button(
    page: AsyncPage,
    req_id: str,
    check_client_disconnected: Callable
) -> Optional[str]:
    """通过编辑按钮获取响应"""
    logger.info(f"[{req_id}] (Helper) 尝试通过编辑按钮获取响应...")
    last_message_container = page.locator('ms-chat-turn').last
    edit_button = last_message_container.get_by_label("Edit")
    finish_edit_button = last_message_container.get_by_label("Stop editing")
    autosize_textarea_locator = last_message_container.locator('ms-autosize-textarea')
    actual_textarea_locator = autosize_textarea_locator.locator('textarea')
    
    try:
        logger.info(f"[{req_id}]   - 尝试悬停最后一条消息以显示 'Edit' 按钮...")
        try:
            # 对消息容器执行悬停操作
            await last_message_container.hover(timeout=CLICK_TIMEOUT_MS / 2) # 使用一半的点击超时作为悬停超时
            await asyncio.sleep(0.3) # 等待悬停效果生效
            check_client_disconnected("编辑响应 - 悬停后: ")
        except Exception as hover_err:
            logger.warning(f"[{req_id}]   - (get_response_via_edit_button) 悬停最后一条消息失败 (忽略): {type(hover_err).__name__}")
            # 即使悬停失败，也继续尝试后续操作，Playwright的expect_async可能会处理
        
        logger.info(f"[{req_id}]   - 定位并点击 'Edit' 按钮...")
        try:
            from playwright.async_api import expect as expect_async
            await expect_async(edit_button).to_be_visible(timeout=CLICK_TIMEOUT_MS)
            check_client_disconnected("编辑响应 - 'Edit' 按钮可见后: ")
            await edit_button.click(timeout=CLICK_TIMEOUT_MS)
            logger.info(f"[{req_id}]   - 'Edit' 按钮已点击。")
        except Exception as edit_btn_err:
            logger.error(f"[{req_id}]   - 'Edit' 按钮不可见或点击失败: {edit_btn_err}")
            await save_error_snapshot(f"edit_response_edit_button_failed_{req_id}")
            return None
        
        check_client_disconnected("编辑响应 - 点击 'Edit' 按钮后: ")
        await asyncio.sleep(0.3)
        check_client_disconnected("编辑响应 - 点击 'Edit' 按钮后延时后: ")
        
        logger.info(f"[{req_id}]   - 从文本区域获取内容...")
        response_content = None
        textarea_failed = False
        
        try:
            await expect_async(autosize_textarea_locator).to_be_visible(timeout=CLICK_TIMEOUT_MS)
            check_client_disconnected("编辑响应 - autosize-textarea 可见后: ")
            
            try:
                data_value_content = await autosize_textarea_locator.get_attribute("data-value")
                check_client_disconnected("编辑响应 - get_attribute data-value 后: ")
                if data_value_content is not None:
                    response_content = str(data_value_content)
                    logger.info(f"[{req_id}]   - 从 data-value 获取内容成功。")
            except Exception as data_val_err:
                logger.warning(f"[{req_id}]   - 获取 data-value 失败: {data_val_err}")
                check_client_disconnected("编辑响应 - get_attribute data-value 错误后: ")
            
            if response_content is None:
                logger.info(f"[{req_id}]   - data-value 获取失败或为None，尝试从内部 textarea 获取 input_value...")
                try:
                    await expect_async(actual_textarea_locator).to_be_visible(timeout=CLICK_TIMEOUT_MS/2)
                    input_val_content = await actual_textarea_locator.input_value(timeout=CLICK_TIMEOUT_MS/2)
                    check_client_disconnected("编辑响应 - input_value 后: ")
                    if input_val_content is not None:
                        response_content = str(input_val_content)
                        logger.info(f"[{req_id}]   - 从 input_value 获取内容成功。")
                except Exception as input_val_err:
                     logger.warning(f"[{req_id}]   - 获取 input_value 也失败: {input_val_err}")
                     check_client_disconnected("编辑响应 - input_value 错误后: ")
            
            if response_content is not None:
                response_content = response_content.strip()
                content_preview = response_content[:100].replace('\\n', '\\\\n')
                logger.info(f"[{req_id}]   - ✅ 最终获取内容 (长度={len(response_content)}): '{content_preview}...'")
            else:
                logger.warning(f"[{req_id}]   - 所有方法 (data-value, input_value) 内容获取均失败或返回 None。")
                textarea_failed = True
                
        except Exception as textarea_err:
            logger.error(f"[{req_id}]   - 定位或处理文本区域时失败: {textarea_err}")
            textarea_failed = True
            response_content = None
            check_client_disconnected("编辑响应 - 获取文本区域错误后: ")
        
        if not textarea_failed:
            logger.info(f"[{req_id}]   - 定位并点击 'Stop editing' 按钮...")
            try:
                await expect_async(finish_edit_button).to_be_visible(timeout=CLICK_TIMEOUT_MS)
                check_client_disconnected("编辑响应 - 'Stop editing' 按钮可见后: ")
                await finish_edit_button.click(timeout=CLICK_TIMEOUT_MS)
                logger.info(f"[{req_id}]   - 'Stop editing' 按钮已点击。")
            except Exception as finish_btn_err:
                logger.warning(f"[{req_id}]   - 'Stop editing' 按钮不可见或点击失败: {finish_btn_err}")
                await save_error_snapshot(f"edit_response_finish_button_failed_{req_id}")
            check_client_disconnected("编辑响应 - 点击 'Stop editing' 后: ")
            await asyncio.sleep(0.2)
            check_client_disconnected("编辑响应 - 点击 'Stop editing' 后延时后: ")
        else:
             logger.info(f"[{req_id}]   - 跳过点击 'Stop editing' 按钮，因为文本区域读取失败。")
        
        return response_content
        
    except ClientDisconnectedError:
        logger.info(f"[{req_id}] (Helper Edit) 客户端断开连接。")
        raise
    except Exception as e:
        logger.exception(f"[{req_id}] 通过编辑按钮获取响应过程中发生意外错误")
        await save_error_snapshot(f"edit_response_unexpected_error_{req_id}")
        return None

async def get_response_via_copy_button(
    page: AsyncPage,
    req_id: str,
    check_client_disconnected: Callable
) -> Optional[str]:
    """通过复制按钮获取响应"""
    logger.info(f"[{req_id}] (Helper) 尝试通过复制按钮获取响应...")
    last_message_container = page.locator('ms-chat-turn').last
    more_options_button = last_message_container.get_by_label("Open options")
    copy_markdown_button = page.get_by_role("menuitem", name="Copy markdown")
    
    try:
        logger.info(f"[{req_id}]   - 尝试悬停最后一条消息以显示选项...")
        await last_message_container.hover(timeout=CLICK_TIMEOUT_MS)
        check_client_disconnected("复制响应 - 悬停后: ")
        await asyncio.sleep(0.5)
        check_client_disconnected("复制响应 - 悬停后延时后: ")
        logger.info(f"[{req_id}]   - 已悬停。")
        
        logger.info(f"[{req_id}]   - 定位并点击 '更多选项' 按钮...")
        try:
            from playwright.async_api import expect as expect_async
            await expect_async(more_options_button).to_be_visible(timeout=CLICK_TIMEOUT_MS)
            check_client_disconnected("复制响应 - 更多选项按钮可见后: ")
            await more_options_button.click(timeout=CLICK_TIMEOUT_MS)
            logger.info(f"[{req_id}]   - '更多选项' 已点击 (通过 get_by_label)。")
        except Exception as more_opts_err:
            logger.error(f"[{req_id}]   - '更多选项' 按钮 (通过 get_by_label) 不可见或点击失败: {more_opts_err}")
            await save_error_snapshot(f"copy_response_more_options_failed_{req_id}")
            return None
        
        check_client_disconnected("复制响应 - 点击更多选项后: ")
        await asyncio.sleep(0.5)
        check_client_disconnected("复制响应 - 点击更多选项后延时后: ")
        
        logger.info(f"[{req_id}]   - 定位并点击 '复制 Markdown' 按钮...")
        copy_success = False
        try:
            await expect_async(copy_markdown_button).to_be_visible(timeout=CLICK_TIMEOUT_MS)
            check_client_disconnected("复制响应 - 复制按钮可见后: ")
            await copy_markdown_button.click(timeout=CLICK_TIMEOUT_MS, force=True)
            copy_success = True
            logger.info(f"[{req_id}]   - 已点击 '复制 Markdown' (通过 get_by_role)。")
        except Exception as copy_err:
            logger.error(f"[{req_id}]   - '复制 Markdown' 按钮 (通过 get_by_role) 点击失败: {copy_err}")
            await save_error_snapshot(f"copy_response_copy_button_failed_{req_id}")
            return None
        
        if not copy_success:
             logger.error(f"[{req_id}]   - 未能点击 '复制 Markdown' 按钮。")
             return None
             
        check_client_disconnected("复制响应 - 点击复制按钮后: ")
        await asyncio.sleep(0.5)
        check_client_disconnected("复制响应 - 点击复制按钮后延时后: ")
        
        logger.info(f"[{req_id}]   - 正在读取剪贴板内容...")
        try:
            clipboard_content = await page.evaluate('navigator.clipboard.readText()')
            check_client_disconnected("复制响应 - 读取剪贴板后: ")
            if clipboard_content:
                content_preview = clipboard_content[:100].replace('\n', '\\\\n')
                logger.info(f"[{req_id}]   - ✅ 成功获取剪贴板内容 (长度={len(clipboard_content)}): '{content_preview}...'")
                return clipboard_content
            else:
                logger.error(f"[{req_id}]   - 剪贴板内容为空。")
                return None
        except Exception as clipboard_err:
            if "clipboard-read" in str(clipboard_err):
                 logger.error(f"[{req_id}]   - 读取剪贴板失败: 可能是权限问题。错误: {clipboard_err}")
            else:
                 logger.error(f"[{req_id}]   - 读取剪贴板失败: {clipboard_err}")
            await save_error_snapshot(f"copy_response_clipboard_read_failed_{req_id}")
            return None
            
    except ClientDisconnectedError:
        logger.info(f"[{req_id}] (Helper Copy) 客户端断开连接。")
        raise
    except Exception as e:
        logger.exception(f"[{req_id}] 复制响应过程中发生意外错误")
        await save_error_snapshot(f"copy_response_unexpected_error_{req_id}")
        return None

async def _wait_for_response_completion(
    page: AsyncPage,
    prompt_textarea_locator: Locator,
    submit_button_locator: Locator,
    edit_button_locator: Locator,
    req_id: str,
    check_client_disconnected_func: Callable,
    current_chat_id: Optional[str],
    timeout_ms=RESPONSE_COMPLETION_TIMEOUT,
    initial_wait_ms=INITIAL_WAIT_MS_BEFORE_POLLING
) -> bool:
    """等待响应完成"""
    from playwright.async_api import TimeoutError
    
    logger.info(f"[{req_id}] (WaitV3) 开始等待响应完成... (超时: {timeout_ms}ms)")
    await asyncio.sleep(initial_wait_ms / 1000) # Initial brief wait
    
    start_time = time.time()
    wait_timeout_ms_short = 3000 # 3 seconds for individual element checks
    
    consecutive_empty_input_submit_disabled_count = 0
    
    while True:
        try:
            check_client_disconnected_func("等待响应完成 - 循环开始")
        except ClientDisconnectedError:
            logger.info(f"[{req_id}] (WaitV3) 客户端断开连接，中止等待。")
            return False

        current_time_elapsed_ms = (time.time() - start_time) * 1000
        if current_time_elapsed_ms > timeout_ms:
            logger.error(f"[{req_id}] (WaitV3) 等待响应完成超时 ({timeout_ms}ms)。")
            await save_error_snapshot(f"wait_completion_v3_overall_timeout_{req_id}")
            return False

        try:
            check_client_disconnected_func("等待响应完成 - 超时检查后")
        except ClientDisconnectedError:
            return False

        # --- 主要条件: 输入框空 & 提交按钮禁用 ---
        is_input_empty = await prompt_textarea_locator.input_value() == ""
        is_submit_disabled = False
        try:
            is_submit_disabled = await submit_button_locator.is_disabled(timeout=wait_timeout_ms_short)
        except TimeoutError:
            logger.warning(f"[{req_id}] (WaitV3) 检查提交按钮是否禁用超时。为本次检查假定其未禁用。")
        
        try:
            check_client_disconnected_func("等待响应完成 - 按钮状态检查后")
        except ClientDisconnectedError:
            return False

        if is_input_empty and is_submit_disabled:
            consecutive_empty_input_submit_disabled_count += 1
            if DEBUG_LOGS_ENABLED:
                logger.debug(f"[{req_id}] (WaitV3) 主要条件满足: 输入框空，提交按钮禁用 (计数: {consecutive_empty_input_submit_disabled_count})。")

            # --- 最终确认: 编辑按钮可见 ---
            try:
                if await edit_button_locator.is_visible(timeout=wait_timeout_ms_short):
                    logger.info(f"[{req_id}] (WaitV3) ✅ 响应完成: 输入框空，提交按钮禁用，编辑按钮可见。")
                    return True # 明确完成
            except TimeoutError:
                if DEBUG_LOGS_ENABLED:
                    logger.debug(f"[{req_id}] (WaitV3) 主要条件满足后，检查编辑按钮可见性超时。")
            
            try:
                check_client_disconnected_func("等待响应完成 - 编辑按钮检查后")
            except ClientDisconnectedError:
                return False

            # 启发式完成: 如果主要条件持续满足，但编辑按钮仍未出现
            if consecutive_empty_input_submit_disabled_count >= 3: # 例如，大约 1.5秒 (3 * 0.5秒轮询)
                logger.warning(f"[{req_id}] (WaitV3) 响应可能已完成 (启发式): 输入框空，提交按钮禁用，但在 {consecutive_empty_input_submit_disabled_count} 次检查后编辑按钮仍未出现。假定完成。后续若内容获取失败，可能与此有关。")
                return True # 启发式完成
        else: # 主要条件 (输入框空 & 提交按钮禁用) 未满足
            consecutive_empty_input_submit_disabled_count = 0 # 重置计数器
            if DEBUG_LOGS_ENABLED:
                reasons = []
                if not is_input_empty: 
                    reasons.append("输入框非空")
                if not is_submit_disabled: 
                    reasons.append("提交按钮非禁用")
                logger.debug(f"[{req_id}] (WaitV3) 主要条件未满足 ({', '.join(reasons)}). 继续轮询...")

        await asyncio.sleep(0.5) # 轮询间隔

async def _get_final_response_content(
    page: AsyncPage,
    req_id: str,
    check_client_disconnected: Callable
) -> Optional[str]:
    """获取最终响应内容"""
    logger.info(f"[{req_id}] (Helper GetContent) 开始获取最终响应内容...")
    response_content = await get_response_via_edit_button(
        page, req_id, check_client_disconnected
    )
    if response_content is not None:
        logger.info(f"[{req_id}] (Helper GetContent) ✅ 成功通过编辑按钮获取内容。")
        return response_content
    
    logger.warning(f"[{req_id}] (Helper GetContent) 编辑按钮方法失败或返回空，回退到复制按钮方法...")
    response_content = await get_response_via_copy_button(
        page, req_id, check_client_disconnected
    )
    if response_content is not None:
        logger.info(f"[{req_id}] (Helper GetContent) ✅ 成功通过复制按钮获取内容。")
        return response_content
    
    logger.error(f"[{req_id}] (Helper GetContent) 所有获取响应内容的方法均失败。")
    await save_error_snapshot(f"get_content_all_methods_failed_{req_id}")
    return None 