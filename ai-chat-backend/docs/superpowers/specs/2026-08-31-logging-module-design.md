# 日志模块设计文档

## 概述

为 AI Chat Backend 项目新增生产级日志模块，基于 Python 标准 `logging`，支持 JSON 结构化输出（生产）和彩色可读输出（开发），通过环境变量控制，Handler 架构支持后续扩展接入 ELK/Loki 等外部日志系统。

## 模块结构

```
app/
├── core/
│   ├── __init__.py
│   ├── logger.py       # 日志配置 + 统一入口
│   └── middleware.py    # 请求日志中间件
├── api/
```

## 核心组件

### `app/core/logger.py`

| 组件 | 说明 |
|------|------|
| `JsonFormatter` | 自定义 Formatter，输出 JSON 格式（timestamp, level, logger_name, message, extra） |
| `ConsoleFormatter` | 彩色人类可读格式，用于开发环境 |
| `setup_logger()` | 初始化函数，配置 handler、设置级别，接受额外 handler 列表用于扩展 |
| `logger` | 模块级全局 logger 实例 |
| `get_logger(name)` | 工厂函数，创建子 logger |

### 日志格式

**JSON 格式（生产）**：
```json
{"timestamp": "2026-08-31T08:00:00.000Z", "level": "INFO", "logger": "app.api.chat", "message": "AI 服务调用成功", "user_id": "123"}
```

**Console 格式（开发）**：
```
2026-08-31 08:00:00 | INFO     | app.api.chat | AI 服务调用成功 | user_id=123
```

## 配置项

`.env` 新增：
```
LOG_LEVEL=INFO          # DEBUG / INFO / WARNING / ERROR / CRITICAL
LOG_FORMAT=json         # json（生产）或 console（开发）
```

`app/config.py` 新增对应字段：
```python
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")
```

## FastAPI 集成

### `app/main.py` 改动

- 在 `lifespan` 中调用 `setup_logger()` 完成初始化
- 拦截 uvicorn 日志走统一配置（通过 `log_config` 参数或 `logging.config.dictConfig`）

### 请求日志中间件

新增轻量级中间件，自动记录：
- 请求方法、路径、客户端 IP
- 响应状态码、耗时（ms）
- INFO 级别记录正常请求，ERROR 级别记录 5xx 异常

## 扩展机制

`setup_logger()` 函数签名：
```python
def setup_logger(extra_handlers: list[logging.Handler] | None = None) -> None
```

后续接入 ELK/Loki 示例：
```python
from elasticsearch import Elasticsearch
from elasticsearch.handlers import ElasticsearchHandler

handler = ElasticsearchHandler(...)
setup_logger(extra_handlers=[handler])
```

## 业务代码使用

```python
from app.core.logger import logger

logger.info("用户登录成功", extra={"user_id": user_id})
logger.error("AI 服务调用失败", extra={"error": str(e)})
```

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `app/core/__init__.py` | 新建 |
| `app/core/logger.py` | 新建 |
| `app/core/middleware.py` | 新建（请求日志中间件） |
| `app/config.py` | 修改（新增 LOG_LEVEL, LOG_FORMAT） |
| `app/main.py` | 修改（集成日志初始化 + 中间件） |
| `.env` | 修改（新增环境变量） |
