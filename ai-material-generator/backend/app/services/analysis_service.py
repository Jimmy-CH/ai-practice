import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.parsed_analysis import ParsedAnalysis
from app.schemas.analysis import AnalysisUpdate


async def get_analysis(session: AsyncSession, analysis_id: int) -> ParsedAnalysis | None:
    return await session.get(ParsedAnalysis, analysis_id)


async def get_analysis_by_title(session: AsyncSession, owner_id: int, source_title: str) -> ParsedAnalysis | None:
    stmt = select(ParsedAnalysis).where(
        ParsedAnalysis.owner_id == owner_id,
        ParsedAnalysis.source_title == source_title,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_analysis(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    data: dict,
) -> ParsedAnalysis:
    analysis = await get_analysis_by_title(session, owner_id, source_title)
    if analysis is None:
        analysis = ParsedAnalysis(owner_id=owner_id, source_title=source_title)
        session.add(analysis)

    analysis.new_features = json.dumps(data.get("新增功能", []), ensure_ascii=False)
    analysis.changes = json.dumps(data.get("变更与优化", []), ensure_ascii=False)
    analysis.notices = json.dumps(data.get("注意事项", []), ensure_ascii=False)
    analysis.risks = json.dumps(data.get("风险提示", []), ensure_ascii=False)

    await session.commit()
    await session.refresh(analysis)
    return analysis


async def update_analysis(
    session: AsyncSession,
    analysis: ParsedAnalysis,
    data: AnalysisUpdate | dict,
) -> ParsedAnalysis:
    if isinstance(data, AnalysisUpdate):
        payload = data.model_dump()
    else:
        payload = data

    analysis.new_features = json.dumps(payload.get("new_features", []), ensure_ascii=False)
    analysis.changes = json.dumps(payload.get("changes", []), ensure_ascii=False)
    analysis.notices = json.dumps(payload.get("notices", []), ensure_ascii=False)
    analysis.risks = json.dumps(payload.get("risks", []), ensure_ascii=False)

    await session.commit()
    await session.refresh(analysis)
    return analysis
