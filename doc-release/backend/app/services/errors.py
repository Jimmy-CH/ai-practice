class ServiceError(Exception):
    """业务服务异常基类，API 层据此映射 HTTP 状态码。"""


class GitError(ServiceError):
    """git 相关错误（仓库不可读、引用无效、范围为空等）。"""


class RunCancelled(ServiceError):
    """运行被用户取消。"""
