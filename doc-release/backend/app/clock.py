"""时间基准：数据库统一存 naive UTC，API 输出带 Z 的绝对时间，日志行用本地时间。

混用 datetime.now() 与 datetime.utcnow() 会让「运行列表时间」与「日志行时间」
相差一个时区偏移，因此把两套语义收敛到本模块，避免各处再各写一遍。
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """naive UTC：SQLite 的 DateTime 列不保存时区，这里统一成 UTC 后再入库。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value: datetime | None) -> str | None:
    """输出显式 UTC 时间（带 Z），前端据此转换为本地时间展示。"""
    if value is None:
        return None
    naive = value.replace(tzinfo=None) if value.tzinfo is not None else value
    return naive.isoformat(timespec="seconds") + "Z"


def local_now_iso() -> str:
    """本地时间字符串：用于日志行与步骤耗时，读者直接看到与自己一致的时钟。"""
    return datetime.now().isoformat(timespec="seconds")
