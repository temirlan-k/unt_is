from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile

from src.core.auth_middleware import get_current_user
from src.models.user import User
from src.schemas.req.profile import  UserProfileUpdateReq
from src.services.profile import ProfileService
from src.utils.file_handlers import save_avatar, delete_avatar

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
    search:str = None,skip: int = 0, limit: int = 10,
    profile_service: ProfileService = Depends(ProfileService),
):
    return await profile_service.get_leaderboard(search,skip,limit)

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


@profile_router.post("/avatar")
async def upload_avatar(token: dict = Depends(get_current_user), file: UploadFile = File(...)):
    """
    Upload user avatar
    """
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Get user
    user = await User.get(token.get('sub'))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete old avatar if exists
    if user.avatar:
        delete_avatar(user.avatar)

    # Save new avatar
    avatar_path = await save_avatar(file, user.id)

    # Update user
    user.avatar = avatar_path
    await user.save()

    return {"message": "Avatar uploaded successfully", "avatar_path": avatar_path}


@profile_router.delete("/avatar")
async def delete_user_avatar(token: dict = Depends(get_current_user)):
    """
    Delete user avatar
    """
    user = await User.get(token.get('sub'))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.avatar:
        delete_avatar(user.avatar)
        user.avatar = None
        await user.save()

    return {"message": "Avatar deleted successfully"}
