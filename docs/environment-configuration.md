# 环境变量配置指南

本文档详细介绍如何使用 `.env` 文件来配置 AI Studio Proxy API 项目，实现统一的配置管理。

## 概述

项目采用基于 `.env` 文件的现代化配置管理系统，提供以下优势：

### 主要优势

- ✅ **版本更新无忧**: 一个 `git pull` 就完成更新，无需重新配置
- ✅ **配置集中管理**: 所有配置项统一在 `.env` 文件中，清晰明了
- ✅ **启动命令简化**: 无需复杂的命令行参数，一键启动
- ✅ **安全性**: `.env` 文件已被 `.gitignore` 忽略，不会泄露敏感配置
- ✅ **灵活性**: 支持不同环境的配置管理（开发、测试、生产）
- ✅ **Docker 兼容**: Docker 和本地环境使用相同的配置方式
- ✅ **模块化设计**: 配置项按功能分组，便于理解和维护

## 快速开始

### 1. 复制配置模板

```bash
cp .env.example .env
```

### 2. 编辑配置文件

根据您的需要修改 `.env` 文件中的配置项：

```bash
# 编辑配置文件
nano .env
# 或使用其他编辑器
code .env
```

### 3. 启动服务

配置完成后，启动变得非常简单：

```bash
# 图形界面启动（推荐新手）
python gui_launcher.py

# 命令行启动（推荐日常使用）
python launch_camoufox.py --headless

# 调试模式（首次设置或故障排除）
python launch_camoufox.py --debug
```

**就这么简单！** 无需复杂的命令行参数，所有配置都在 `.env` 文件中预设好了。

## 启动命令对比

### 使用 `.env` 配置前（复杂）

```bash
# 之前需要这样的复杂命令
python launch_camoufox.py --headless --server-port 2048 --stream-port 3120 --helper '' --internal-camoufox-proxy 'http://127.0.0.1:7890'
```

### 使用 `.env` 配置后（简单）

```bash
# 现在只需要这样
python launch_camoufox.py --headless
```

**配置一次，终身受益！** 所有复杂的参数都在 `.env` 文件中预设，启动命令变得极其简洁。

## 主要配置项

### 服务端口配置

```env
# FastAPI 服务端口
PORT=8000
DEFAULT_FASTAPI_PORT=2048
DEFAULT_CAMOUFOX_PORT=9222

# 流式代理服务配置
STREAM_PORT=3120
```

### 代理配置

```env
# HTTP/HTTPS 代理设置
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890

# 统一代理配置 (优先级更高)
UNIFIED_PROXY_CONFIG=http://127.0.0.1:7890

# 代理绕过列表
NO_PROXY=localhost;127.0.0.1;*.local
```

### 日志配置

```env
# 服务器日志级别
SERVER_LOG_LEVEL=INFO

# 启用调试日志
DEBUG_LOGS_ENABLED=false
TRACE_LOGS_ENABLED=false

# 是否重定向 print 输出到日志
SERVER_REDIRECT_PRINT=false
```

### 认证配置

```env
# 自动保存认证信息
AUTO_SAVE_AUTH=false

# 认证保存超时时间 (秒)
AUTH_SAVE_TIMEOUT=30

# 自动确认登录
AUTO_CONFIRM_LOGIN=true

# 启用 Qwen 登录支持（默认为访客模式）
ENABLE_QWEN_LOGIN_SUPPORT=false
# 设置为 true 可重新启用认证文件和交互式登录流程
```

### API 默认参数

```env
# 默认温度值 (0.0-2.0)
DEFAULT_TEMPERATURE=1.0

# 默认最大输出令牌数
DEFAULT_MAX_OUTPUT_TOKENS=65536

# 默认 Top-P 值 (0.0-1.0)
DEFAULT_TOP_P=0.95

# 默认停止序列 (JSON 数组格式)
DEFAULT_STOP_SEQUENCES=["用户:"]

# 是否在处理请求时自动打开并使用 "URL Context" 功能
# 参考: https://ai.google.dev/gemini-api/docs/url-context
ENABLE_URL_CONTEXT=true

# 是否默认启用 "指定思考预算" 功能 (true/false),不启用时模型一般将自行决定思考预算
# 当 API 请求中未提供 reasoning_effort 参数时,将使用此值。
ENABLE_THINKING_BUDGET=false

# "指定思考预算量" 的默认值 (token)
# 当 API 请求中未提供 reasoning_effort 参数时,将使用此值。
DEFAULT_THINKING_BUDGET=8192

# 是否默认启用 "Google Search" 功能 (true/false)
# 当 API 请求中未提供 tools 参数时，将使用此设置作为 Google Search 的默认开关状态。
ENABLE_GOOGLE_SEARCH=false
```

### 超时配置

```env
# 响应完成总超时时间 (毫秒)
RESPONSE_COMPLETION_TIMEOUT=300000

# 轮询间隔 (毫秒)
POLLING_INTERVAL=300
POLLING_INTERVAL_STREAM=180

# 静默超时 (毫秒)
SILENCE_TIMEOUT_MS=60000
```

### GUI 启动器配置

```env
# GUI 默认代理地址
GUI_DEFAULT_PROXY_ADDRESS=http://127.0.0.1:7890

# GUI 默认流式代理端口
GUI_DEFAULT_STREAM_PORT=3120

# GUI 默认 Helper 端点
GUI_DEFAULT_HELPER_ENDPOINT=
```

### 脚本注入配置 v3.0 🆕

```env
# 是否启用油猴脚本注入功能
ENABLE_SCRIPT_INJECTION=true

# 油猴脚本文件路径（相对于项目根目录）
# 模型数据直接从此脚本文件中解析，无需额外配置文件
USERSCRIPT_PATH=browser_utils/more_modles.js
```

**脚本注入功能 v3.0 重大升级**：
- **🚀 Playwright 原生拦截**: 使用 Playwright 路由拦截，100% 可靠性
- **🔄 双重保障机制**: 网络拦截 + 脚本注入，确保万无一失
- **📝 直接脚本解析**: 从油猴脚本中自动解析模型列表，无需配置文件
- **🔗 前后端同步**: 前端和后端使用相同的模型数据源
- **⚙️ 零配置维护**: 脚本更新时自动获取新的模型列表
- **🔄 自动适配**: 油猴脚本更新时无需手动更新配置

**与 v1.x 的主要区别**：
- 移除了 `MODEL_CONFIG_PATH` 配置项（已废弃）
- 不再需要手动维护模型配置文件
- 工作机制从"配置文件 + 脚本注入"改为"直接脚本解析 + 网络拦截"

详细使用方法请参见 [脚本注入指南](script_injection_guide.md)。

## 配置优先级

配置项的优先级顺序（从高到低）：

1. **命令行参数** - 直接传递给程序的参数
2. **环境变量** - 系统环境变量或 `.env` 文件中的变量
3. **默认值** - 代码中定义的默认值

## 常见配置场景

### 场景 1：使用代理

```env
# 启用代理
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890

# GUI 中也使用相同代理
GUI_DEFAULT_PROXY_ADDRESS=http://127.0.0.1:7890
```

### 场景 2：调试模式

```env
# 启用详细日志
DEBUG_LOGS_ENABLED=true
TRACE_LOGS_ENABLED=true
SERVER_LOG_LEVEL=DEBUG
SERVER_REDIRECT_PRINT=true
```

### 场景 3：生产环境

```env
# 生产环境配置
SERVER_LOG_LEVEL=WARNING
DEBUG_LOGS_ENABLED=false
TRACE_LOGS_ENABLED=false

# 更长的超时时间
RESPONSE_COMPLETION_TIMEOUT=600000
SILENCE_TIMEOUT_MS=120000
```

### 场景 4：自定义端口

```env
# 避免端口冲突
DEFAULT_FASTAPI_PORT=3048
DEFAULT_CAMOUFOX_PORT=9223
STREAM_PORT=3121
```

### 场景 5：启用脚本注入 v3.0 🆕

```env
# 启用脚本注入功能 v3.0
ENABLE_SCRIPT_INJECTION=true

# 使用自定义脚本（模型数据直接从脚本解析）
USERSCRIPT_PATH=browser_utils/my_custom_script.js

# 调试模式查看注入效果
DEBUG_LOGS_ENABLED=true

# 流式代理配置（与脚本注入配合使用）
STREAM_PORT=3120
```

**v3.0 脚本注入优势**：
- 使用 Playwright 原生网络拦截，无时序问题
- 前后端模型数据100%同步
- 零配置维护，脚本更新自动生效

## 配置优先级

项目采用分层配置系统，按以下优先级顺序确定最终配置：

1. **命令行参数** (最高优先级)
   ```bash
   # 命令行参数会覆盖 .env 文件中的设置
   python launch_camoufox.py --headless --server-port 3048
   ```

2. **`.env` 文件配置** (推荐)
   ```env
   # .env 文件中的配置
   DEFAULT_FASTAPI_PORT=2048
   ```

3. **系统环境变量** (最低优先级)
   ```bash
   # 系统环境变量
   export DEFAULT_FASTAPI_PORT=2048
   ```

### 使用建议

- **日常使用**: 在 `.env` 文件中配置所有常用设置
- **临时调整**: 使用命令行参数进行临时覆盖，无需修改 `.env` 文件
- **CI/CD 环境**: 可以通过系统环境变量进行配置

## 注意事项

### 1. 文件安全

- `.env` 文件已被 `.gitignore` 忽略，不会被提交到版本控制
- 请勿在 `.env.example` 中包含真实的敏感信息
- 如需分享配置，请复制并清理敏感信息后再分享

### 2. 格式要求

- 环境变量名区分大小写
- 布尔值使用 `true`/`false`
- 数组使用 JSON 格式：`["item1", "item2"]`
- 字符串值如包含特殊字符，请使用引号

### 3. 重启生效

修改 `.env` 文件后需要重启服务才能生效。

### 4. 验证配置

启动服务时，日志会显示加载的配置信息，可以通过日志验证配置是否正确。

## 故障排除

### 配置未生效

1. 检查 `.env` 文件是否在项目根目录
2. 检查环境变量名是否正确（区分大小写）
3. 检查值的格式是否正确
4. 重启服务

### 代理配置问题

1. 确认代理服务器地址和端口正确
2. 检查代理服务器是否正常运行
3. 验证网络连接

### 端口冲突

1. 检查端口是否被其他程序占用
2. 使用 GUI 启动器的端口检查功能
3. 修改为其他可用端口

## 更多信息

- [安装指南](installation-guide.md)
- [高级配置](advanced-configuration.md)
- [故障排除](troubleshooting.md)
