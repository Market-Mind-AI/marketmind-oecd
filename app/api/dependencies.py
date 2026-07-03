from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.oecd_service import OECDService


async def get_oecd_service(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[OECDService, None]:
    yield OECDService(session)
