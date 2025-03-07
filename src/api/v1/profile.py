from beanie import PydanticObjectId
from fastapi import APIRouter, Depends

from src.core.auth_middleware import get_current_user
from src.schemas.req.profile import  UserProfileUpdateReq
from src.services.profile import ProfileService

profile_router = APIRouter()


@profile_router.patch("/update")
async def update_profile(
    req: UserProfileUpdateReq,
    token: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(ProfileService),
):
    return await profile_service.update_profile(token.get("sub"), req)


@profile_router.get("/me")
async def me(
    token: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(ProfileService),
):
    return await profile_service.get_user_by_id(token.get("sub"))


@profile_router.get('/leaderboard')
async def get_leaderboard(
    skip: int = 0, limit: int = 10,
    profile_service: ProfileService = Depends(ProfileService),
):
    return await profile_service.get_leaderboard(skip,limit)

@profile_router.get("/leaderboard/me", )
async def get_user_rank(    
    token: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(ProfileService),
):
    """Возвращает место текущего пользователя в лидерборде и его total_score"""
    return await profile_service.get_user_rank((token.get('sub')))


@profile_router.get('/stats')
async def get_quiz_stats(
    token: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(ProfileService),
):
    return await profile_service.get_quiz_stats(PydanticObjectId(token.get('sub')))