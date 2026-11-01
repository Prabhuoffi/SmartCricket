"""Upload validation and saving (FR-3, FR-6, NFR-4)."""
import uuid
from pathlib import Path

import cv2
from fastapi import HTTPException, UploadFile

from .config import settings

IMAGE_EXT = {".jpg", ".jpeg", ".png"}
VIDEO_EXT = {".mp4", ".mov", ".avi"}
IMAGE_MIME = {"image/jpeg", "image/png"}
VIDEO_MIME = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/avi", "application/octet-stream"}
CHUNK = 1024 * 1024


async def save_upload(file: UploadFile, kind: str) -> Path:
    """Check extension, MIME type and size, write to disk, then check the file can be decoded."""
    ext = Path(file.filename or "").suffix.lower()
    if kind == "image":
        allowed_ext, allowed_mime, limit_mb = IMAGE_EXT, IMAGE_MIME, settings.max_image_mb
        type_msg = "Only JPG or PNG images are allowed"
    else:
        allowed_ext, allowed_mime, limit_mb = VIDEO_EXT, VIDEO_MIME, settings.max_video_mb
        type_msg = "Only MP4, MOV or AVI videos are allowed"
    if ext not in allowed_ext or (file.content_type and file.content_type not in allowed_mime):
        raise HTTPException(400, type_msg)

    path = settings.upload_dir / f"{uuid.uuid4().hex}{ext}"
    size, limit = 0, limit_mb * 1024 * 1024
    with path.open("wb") as out:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > limit:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(413, f"File is larger than {limit_mb} MB")
            out.write(chunk)
    if size == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(422, "The file is empty")

    readable = cv2.imread(str(path)) is not None if kind == "image" else _video_readable(path)
    if not readable:
        path.unlink(missing_ok=True)
        raise HTTPException(422, "Image could not be read" if kind == "image" else "Video could not be read")
    return path


def _video_readable(path: Path) -> bool:
    cap = cv2.VideoCapture(str(path))
    ok, _ = cap.read()
    cap.release()
    return ok
