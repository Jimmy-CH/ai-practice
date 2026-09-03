"""
数据校验层 (schemas/)
职责：定义 Pydantic 模型，用于请求体的类型校验和响应体的格式化。
优势：将“数据库实体（ORM）”与“对外暴露的数据结构（Schema）”解耦。比如 User 表里有 hashed_password，但返回给前端的 Schema 里绝对不能包含这个字段。
"""