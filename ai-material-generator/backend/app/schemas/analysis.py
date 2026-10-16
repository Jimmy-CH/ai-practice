from pydantic import BaseModel, ConfigDict


class AnalysisUpdate(BaseModel):
    new_features: list[str]
    changes: list[str]
    notices: list[str]
    risks: list[str]


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    source_title: str
    新增功能: list[str]
    变更与优化: list[str]
    注意事项: list[str]
    风险提示: list[str]
    created_at: str | None = None
    updated_at: str | None = None
