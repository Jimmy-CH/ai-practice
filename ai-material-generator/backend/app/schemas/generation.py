from pydantic import BaseModel


class SaveFromGenerationRequest(BaseModel):
    title: str
    content: str
    material_type: str
    audience: str
    source_title: str = ""
    analysis: str = "{}"
