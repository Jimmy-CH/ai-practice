"""
核心业务逻辑层 (services/)
职责：承载真正的业务逻辑。例如 ai_service.py 负责组装 Prompt、处理流式 SSE 生成器、实现断线续传逻辑；user_service.py 负责处理注册时的查重和加密。
优势：如果未来你要把 DeepSeek 换成通义千问，或者增加 Token 计费逻辑，只需要修改 ai_service.py，路由层完全不用动。
"""