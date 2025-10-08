# 依赖版本说明

本文档详细说明了项目的 Python 版本要求、Poetry 依赖管理和版本控制策略。

## 📦 依赖管理工具

项目使用 **Poetry** 进行现代化的依赖管理，相比传统的 `requirements.txt` 提供：

- ✅ **依赖解析**: 自动解决版本冲突
- ✅ **锁定文件**: `poetry.lock` 确保环境一致性
- ✅ **虚拟环境**: 自动创建和管理虚拟环境
- ✅ **依赖分组**: 区分生产依赖和开发依赖
- ✅ **语义化版本**: 更精确的版本控制
- ✅ **构建系统**: 内置打包和发布功能

## 🐍 Python 版本要求

### Poetry 配置

```toml
[tool.poetry.dependencies]
python = ">=3.9,<4.0"
```

### 推荐配置
- **生产环境**: Python 3.10+ 或 3.11+ (最佳性能和稳定性)
- **开发环境**: Python 3.11+ 或 3.12+ (获得最佳开发体验)
- **最低要求**: Python 3.9 (基础功能支持)

### 版本兼容性矩阵

| Python版本 | 支持状态 | 推荐程度 | 主要特性 | 说明 |
|-----------|---------|---------|---------|------|
| 3.8 | ❌ 不支持 | 不推荐 | - | 缺少必要的类型注解特性 |
| 3.9 | ✅ 完全支持 | 可用 | 基础功能 | 最低支持版本，所有功能正常 |
| 3.10 | ✅ 完全支持 | 推荐 | 结构化模式匹配 | Docker 默认版本，稳定可靠 |
| 3.11 | ✅ 完全支持 | 强烈推荐 | 性能优化 | 显著性能提升，类型提示增强 |
| 3.12 | ✅ 完全支持 | 推荐 | 更快启动 | 更快启动时间，最新稳定特性 |
| 3.13 | ✅ 完全支持 | 可用 | 最新特性 | 最新版本，开发环境推荐 |

## 📋 Poetry 依赖配置

### pyproject.toml 结构

```toml
[tool.poetry]
name = "aistudioproxyapi"
version = "0.1.0"
package-mode = false

[tool.poetry.dependencies]
# 生产依赖
python = ">=3.9,<4.0"
fastapi = "==0.115.12"
# ... 其他依赖

[tool.poetry.group.dev.dependencies]
# 开发依赖 (可选安装)
pytest = "^7.0.0"
black = "^23.0.0"
# ... 其他开发工具
```

### 版本约束语法

Poetry 使用语义化版本约束：

- `==1.2.3` - 精确版本
- `^1.2.3` - 兼容版本 (>=1.2.3, <2.0.0)
- `~1.2.3` - 补丁版本 (>=1.2.3, <1.3.0)
- `>=1.2.3,<2.0.0` - 版本范围
- `*` - 最新版本

## 🔧 核心依赖版本

### Web 框架相关
```toml
fastapi = "==0.115.12"
pydantic = ">=2.7.1,<3.0.0"
uvicorn = "==0.29.0"
```

**版本说明**:
- **FastAPI 0.115.12**: 最新稳定版本，包含性能优化和新功能
  - 新增 Query/Header/Cookie 参数模型支持
  - 改进的类型提示和验证
  - 更好的 OpenAPI 文档生成
- **Pydantic 2.7.1+**: 现代数据验证库，使用版本范围确保兼容性
- **Uvicorn 0.29.0**: 高性能 ASGI 服务器

### 浏览器自动化
```toml
playwright = "*"
camoufox = {version = "0.4.11", extras = ["geoip"]}
```

**版本说明**:
- **Playwright**: 使用最新版本 (`*`)，确保浏览器兼容性
- **Camoufox 0.4.11**: 反指纹检测浏览器，包含地理位置数据扩展

### 网络和安全
```toml
aiohttp = "~=3.9.5"
requests = "==2.31.0"
cryptography = "==42.0.5"
pyjwt = "==2.8.0"
websockets = "==12.0"
aiosocks = "~=0.2.6"
python-socks = "~=2.7.1"
```

**版本说明**:
- **aiohttp ~3.9.5**: 异步HTTP客户端，允许补丁版本更新
- **cryptography 42.0.5**: 加密库，固定版本确保安全性
- **websockets 12.0**: WebSocket 支持
- **requests 2.31.0**: HTTP 客户端库

### 系统工具
```toml
python-dotenv = "==1.0.1"
httptools = "==0.6.1"
uvloop = {version = "*", markers = "sys_platform != 'win32'"}
Flask = "==3.0.3"
```

**版本说明**:
- **uvloop**: 仅在非 Windows 系统安装，显著提升性能
- **httptools**: HTTP 解析优化
- **python-dotenv**: 环境变量管理
- **Flask**: 用于特定功能的轻量级 Web 框架

## 🔄 Poetry 依赖管理命令

### 基础命令

```bash
# 安装所有依赖
poetry install

# 安装包括开发依赖
poetry install --with dev

# 添加新依赖
poetry add package_name

# 添加开发依赖
poetry add --group dev package_name

# 移除依赖
poetry remove package_name

# 更新依赖
poetry update

# 更新特定依赖
poetry update package_name

# 查看依赖树
poetry show --tree

# 导出 requirements.txt (兼容性)
poetry export -f requirements.txt --output requirements.txt
```

### 锁定文件管理

```bash
# 更新锁定文件
poetry lock

# 不更新锁定文件的情况下安装
poetry install --no-update

# 检查锁定文件是否最新
poetry check
```

## 📊 依赖更新策略

### 自动更新 (使用 ~ 版本范围)
- `aiohttp~=3.9.5` - 允许补丁版本更新 (3.9.5 → 3.9.x)
- `aiosocks~=0.2.6` - 允许补丁版本更新 (0.2.6 → 0.2.x)
- `python-socks~=2.7.1` - 允许补丁版本更新 (2.7.1 → 2.7.x)

### 固定版本 (使用 == 精确版本)
- 核心框架组件 (FastAPI, Uvicorn, python-dotenv)
- 安全相关库 (cryptography, pyjwt, requests)
- 稳定性要求高的组件 (websockets, httptools)

### 兼容版本 (使用版本范围)
- `pydantic>=2.7.1,<3.0.0` - 主版本内兼容更新

### 最新版本 (使用 * 或无限制)
- `playwright = "*"` - 浏览器自动化，需要最新功能
- `uvloop = "*"` - 性能优化库，持续更新

## 版本升级建议

### 已完成的依赖升级
1. **FastAPI**: 0.111.0 → 0.115.12 ✅
   - 新增 Query/Header/Cookie 参数模型功能
   - 改进的类型提示和验证机制
   - 更好的 OpenAPI 文档生成和异步性能
   - 向后兼容，无破坏性变更
   - 增强的中间件支持和错误处理

2. **Pydantic**: 固定版本 → 版本范围 ✅
   - 从 `pydantic==2.7.1` 更新为 `pydantic>=2.7.1,<3.0.0`
   - 确保与 FastAPI 0.115.12 的完美兼容性
   - 允许自动获取补丁版本更新和安全修复
   - 支持最新的数据验证特性

3. **开发工具链现代化**: ✅
   - Poetry 依赖管理替代传统 requirements.txt
   - Pyright 类型检查支持，提升开发体验
   - 模块化配置管理，支持 .env 文件

### 可选的次要依赖更新
- `charset-normalizer`: 3.4.1 → 3.4.2
- `click`: 8.1.8 → 8.2.1
- `frozenlist`: 1.6.0 → 1.6.2

### 升级注意事项
- 在测试环境中先验证兼容性
- 关注 FastAPI 版本更新的 breaking changes
- 定期检查安全漏洞更新

## 环境特定配置

### Docker 环境
- **基础镜像**: `python:3.10-slim-bookworm`
- **系统依赖**: 自动安装浏览器运行时依赖
- **Python版本**: 固定为 3.10 (容器内)

### 开发环境
- **推荐**: Python 3.11+ 
- **虚拟环境**: 强烈推荐使用 venv 或 conda
- **IDE支持**: 配置了 pyrightconfig.json (Python 3.13)

### 生产环境
- **推荐**: Python 3.10 或 3.11
- **稳定性**: 使用固定版本依赖
- **监控**: 定期检查依赖安全更新

## 故障排除

### 常见版本冲突
1. **Python 3.8 兼容性问题**
   - 升级到 Python 3.9+
   - 检查类型提示语法兼容性

2. **依赖版本冲突**
   - 使用虚拟环境隔离
   - 清理 pip 缓存: `pip cache purge`

3. **系统依赖缺失**
   - Linux: 安装 `xvfb` 用于虚拟显示
   - 运行 `playwright install-deps`

### 版本检查命令
```bash
# 检查 Python 版本
python --version

# 检查已安装包版本
pip list

# 检查过时的包
pip list --outdated

# 检查特定包信息
pip show fastapi
```

## 更新日志

### 2025-01-25
- **重要更新**: FastAPI 从 0.111.0 升级到 0.115.12
- **重要更新**: Pydantic 版本策略从固定版本改为版本范围 (>=2.7.1,<3.0.0)
- 更新 Python 版本要求说明 (推荐 3.9+，强烈建议 3.10+)
- 添加详细的依赖版本兼容性矩阵
- 完善 Docker 环境版本说明 (Python 3.10)
- 增加版本升级建议和故障排除指南
- 更新所有相关文档以反映新的依赖版本要求
