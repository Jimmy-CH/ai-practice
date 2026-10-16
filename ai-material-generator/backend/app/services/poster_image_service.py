from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.poster_image import PosterImage, PosterPrompt


async def get_poster_prompt(
    session: AsyncSession,
    owner_id: int,
    script_hash: str,
) -> PosterPrompt | None:
    stmt = select(PosterPrompt).where(
        PosterPrompt.owner_id == owner_id,
        PosterPrompt.script_hash == script_hash,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_poster_prompt(
    session: AsyncSession,
    owner_id: int,
    script_hash: str,
    prompt: str,
) -> PosterPrompt:
    record = await get_poster_prompt(session, owner_id, script_hash)
    if record is None:
        record = PosterPrompt(owner_id=owner_id, script_hash=script_hash)
        session.add(record)
    record.prompt = prompt
    await session.commit()
    await session.refresh(record)
    return record


async def create_poster_image(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
    prompt: str,
    file_path: str,
    file_size: int,
) -> PosterImage:
    image = PosterImage(
        owner_id=owner_id,
        source_title=source_title,
        audience=audience,
        prompt=prompt,
        file_path=file_path,
        file_size=file_size,
    )
    session.add(image)
    await session.commit()
    await session.refresh(image)
    return image


async def get_poster_image_by_id(session: AsyncSession, image_id: int) -> PosterImage | None:
    return await session.get(PosterImage, image_id)


async def list_poster_images(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
) -> list[PosterImage]:
    stmt = (
        select(PosterImage)
        .where(
            PosterImage.owner_id == owner_id,
            PosterImage.source_title == source_title,
            PosterImage.audience == audience,
        )
        .order_by(PosterImage.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_poster_image(session: AsyncSession, image: PosterImage) -> None:
    await session.delete(image)
    await session.commit()
