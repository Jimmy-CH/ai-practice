# app/core/metrics.py
from prometheus_fastapi_instrumentator import Instrumentator


def setup_metrics(app):
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        env_var_name="ENABLE_METRICS",
        excluded_handlers=["/health", "/metrics"],
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

