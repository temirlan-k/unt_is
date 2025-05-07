from fastapi import APIRouter, UploadFile, File, HTTPException
from ..models.user import User
from ..utils.file_handlers import save_avatar, delete_avatar

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/{user_id}/avatar")
async def upload_avatar(user_id: str, file: UploadFile = File(...)):
    """
    Upload user avatar
    """
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Get user
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete old avatar if exists
    if user.avatar:
        delete_avatar(user.avatar)

    # Save new avatar
    avatar_path = await save_avatar(file, user_id)

    # Update user
    user.avatar = avatar_path
    await user.save()

    return {"message": "Avatar uploaded successfully", "avatar_path": avatar_path}


@router.delete("/{user_id}/avatar")
async def delete_user_avatar(user_id: str):
    """
    Delete user avatar
    """
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.avatar:
        delete_avatar(user.avatar)
        user.avatar = None
        await user.save()

    return {"message": "Avatar deleted successfully"}
