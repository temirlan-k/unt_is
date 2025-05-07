import os
import uuid
from fastapi import UploadFile
from pathlib import Path

UPLOAD_DIR = Path("uploads/avatars")


async def save_avatar(file: UploadFile, user_id: str) -> str:
    """
    Save user avatar to the uploads directory
    Returns the URL path to the saved file
    """
    # Create upload directory if it doesn't exist
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{user_id}_{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    # Save the file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Return URL path instead of file system path
    return f"/uploads/avatars/{unique_filename}"


def delete_avatar(avatar_path: str) -> None:
    """Delete user avatar file"""
    if avatar_path:
        # Convert URL path to file system path
        file_path = Path(".") / avatar_path.lstrip("/")
        if file_path.exists():
            os.remove(file_path)
