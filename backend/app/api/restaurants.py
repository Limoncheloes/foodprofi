from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_session
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.restaurant import RestaurantRead

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("", response_model=list[RestaurantRead])
async def list_restaurants(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[RestaurantRead]:
    result = await session.execute(select(Restaurant))
    return result.scalars().all()
