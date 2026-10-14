from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.generated_material import GeneratedMaterial


async def get_generated_material_by_id(
    session: AsyncSession,
    generated_material_id: int,
) -> GeneratedMaterial | None:
    return await session.get(GeneratedMaterial, generated_material_id)


async def get_generated_material(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
    material_type: str,
    analysis_hash: str,
) -> GeneratedMaterial | None:
    stmt = select(GeneratedMaterial).where(
        GeneratedMaterial.owner_id == owner_id,
        GeneratedMaterial.source_title == source_title,
        GeneratedMaterial.audience == audience,
        GeneratedMaterial.material_type == material_type,
        GeneratedMaterial.analysis_hash == analysis_hash,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_generated_material(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
    material_type: str,
    analysis_hash: str,
    content: str,
) -> GeneratedMaterial:
    gm = await get_generated_material(session, owner_id, source_title, audience, material_type, analysis_hash)
    if gm is None:
        gm = GeneratedMaterial(
            owner_id=owner_id,
            source_title=source_title,
            audience=audience,
            material_type=material_type,
            analysis_hash=analysis_hash,
        )
        session.add(gm)
    gm.content = content
    await session.commit()
    await session.refresh(gm)
    return gm


async def update_generated_material(
    session: AsyncSession,
    gm: GeneratedMaterial,
    content: str,
) -> GeneratedMaterial:
    gm.content = content
    await session.commit()
    await session.refresh(gm)
    return gm
