import uuid
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List
from ... import schemas
from ... import models
from ...tasks.upload import upload_file_to_s3
from ...database import SessionLocal
from typing import Optional
from datetime import datetime
import aioboto3
from fastapi import UploadFile
import math


router = APIRouter()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/image", response_model=dict)
async def create_image(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    operationType: Optional[schemas.OperationType] = Form(None),
):
    extension = 'jpg' if file.content_type == 'image/jpeg' else 'png'
    size = math.ceil(int(request.headers.get('content-length'))/1024)
    # 1. Validate that file size is less than 12MB
    # 2. Insert new record to the Image db and get UUID image_id in return
    new_image = models.Image(
        type=operationType if operationType else "original",
        user_id="test",
        created_at=datetime.now(),
        size_bytes=size,
        mime_type=file.content_type,
        status="processing"  # assuming initial status is 'processing'
    )

    db.add(new_image)
    db.commit()
    db.refresh(new_image)

    # 3. Start image uploading background task without blocking
    background_tasks.add_task(upload_file_to_s3, file, new_image.image_id, extension)

    # 4. Respond with imageId: uuid
    return {
        "type": "original",
        "status": "processing",
        "imageId": new_image.image_id,
        "createdAt": new_image.created_at
    }


@router.get("/image", response_model=List[schemas.Image])
async def list_images():
    # Mock response for listing images
    return [{
        "type": "original",
        "status": "processing",
        "imageId": uuid.uuid4(),
        "createdAt": datetime.now()
    }]
