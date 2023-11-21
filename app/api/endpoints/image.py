import uuid
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, BackgroundTasks, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from ... import schemas
from ... import models
from ...tasks.upload import upload_original, get_image_content
from ...database import SessionLocal
from typing import Optional
from datetime import datetime
from fastapi import UploadFile
from uuid import UUID
import boto3
from ...models import Image
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
    size = int(request.headers.get('content-length'))
    # 1. Validate that file size is less than 12MB
    if size > 12_000_000:
      raise HTTPException(status_code=400, detail="File size exceeds limit of 12MB")

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
    background_tasks.add_task(upload_original, file, new_image.image_id, extension, db)

    # 4. Respond with imageId: uuid
    return {
        "type": "original",
        "status": "processing",
        "imageId": new_image.image_id,
        "createdAt": new_image.created_at
    }

@router.get("/image/{imageId}/download")
async def get_image_contents(imageId: UUID, response: Response, db: Session = Depends(get_db)):
    # TODO: User filtering
    image = db.query(Image).filter(Image.image_id == imageId, Image.status == 'ready').first()
    db.commit()
    if image is None:
      raise HTTPException(status_code=404, detail="Not found")
    
    extension = 'jpg' if image.mime_type == 'image/jpeg' else 'png'
    
    return get_image_content(image.image_id, extension, image.mime_type)

@router.get("/image/{imageId}", response_model=schemas.Image)
async def get_image_object(imageId: UUID, db: Session = Depends(get_db)):
    # TODO: User filtering
    q_res = db.query(models.Image).filter(models.Image.image_id == imageId).first()
    return q_res

@router.get("/image/{imageId}/status")
async def get_image_status(imageId: UUID, db: Session = Depends(get_db)):
    q_res = db.query(models.Image).filter(models.Image.image_id == imageId).first()
    return {"status":q_res.status}

@router.get("/image", response_model=schemas.Image)
async def list_images(imageId: UUID, db: Session = Depends(get_db)):
    # TODO: User filtering
    q_res = db.query(models.Image).filter(models.Image.image_id == imageId).first()
    return q_res