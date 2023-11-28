from fastapi import status, APIRouter, Depends, File, UploadFile, Form, HTTPException, BackgroundTasks, Request, Header
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.api.validation.exceptions import ImageValidationException
from ... import schemas
from ... import models
from ...tasks.upload import upload_original, get_image_content
from ...tasks.transform import create_transformed_image
from ...database import SessionLocal
from typing import Optional
from datetime import datetime
from fastapi import UploadFile
from uuid import UUID
from ...models import Image

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_userId(x_user_id: str = Header(None)):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="X-User-Id header missing")
    return x_user_id


@router.post("/image")
async def create_image(
    request: Request,
    background_tasks: BackgroundTasks,
    userId: str = Depends(get_userId),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    operationType: Optional[schemas.OperationType] = Form(None),
    modelType: Optional[schemas.ModelType] = Form(
        default=schemas.ModelType.internal)
) -> schemas.Image:
    extension = 'jpg' if file.content_type == 'image/jpeg' else 'png'
    size = int(request.headers.get('content-length'))
    # 1. Validate that file size is less than 12MB
    if size > 12_000_000:
        raise ImageValidationException(
            name="Image too large",
            info="File size exceeds limit of 12MB",
            type="imageTooLarge"
        )
    
    # TODO: swap logic for peeking at magic bytes
    allowed_mime_types = ['image/jpeg', 'image/png']
    if file.content_type not in allowed_mime_types:
        raise ImageValidationException(
            type="unsupportedFormat",
            info="This image type is currently not supported"
        )

    # 2. Insert new record to the Image db and get UUID imageId in return
    original_image = models.Image(
        type="original",
        userId=userId,
        createdAt=datetime.now(),
        modelType=modelType,
        sizeBytes=size,
        mimeType=file.content_type,
        status="processing"  # assuming initial status is 'processing'
    )

    db.add(original_image)
    db.commit()
    db.refresh(original_image)

    children: List = []

    if operationType is not None:
        transform_image = models.Image(
            type=operationType,
            userId=userId,
            createdAt=datetime.now(),
            modelType=modelType,
            mimeType=file.content_type,
            fromImageId=original_image.imageId,
            status="processing"  # assuming initial status is 'processing'
        )
        db.add(transform_image)
        db.commit()
        db.refresh(transform_image)
        children.append(transform_image)

    # 3. Start image uploading background task without blocking
    background_tasks.add_task(upload_original, file,
                              original_image.imageId, extension, db)

    # 4. Set a task for processing if required
    for child in children:
        background_tasks.add_task(create_transformed_image, original_image.imageId,
                                  extension, child.imageId, operationType, modelType)

    original_image.children = children
    return original_image


@router.post("/image/{imageId}/child")
async def create_image(
    background_tasks: BackgroundTasks,
    imageId: UUID,
    createImage: schemas.CreateChildImage,
    userId: str = Depends(get_userId),
    db: Session = Depends(get_db),
) -> models.Image:
    image = db.query(Image).filter(
        Image.imageId == imageId,
        Image.userId == userId).one_or_none()
    db.commit()

    transform_image = models.Image(
        type=createImage.operationType,
        userId=userId,
        createdAt=datetime.now(),
        modelType=createImage.modelType,
        mimeType=image.mimeType,
        fromImageId=imageId,
        status="processing"  # assuming initial status is 'processing'
    )
    db.add(transform_image)
    db.commit()
    db.refresh(transform_image)
    extension = 'jpg' if image.mimeType == 'image/jpeg' else 'png'

    background_tasks.add_task(create_transformed_image, imageId,
                              extension, transform_image.imageId, createImage.operationType, createImage.modelType)

    return transform_image


@router.get("/image/{imageId}/download")
async def download_image(imageId: UUID, db: Session = Depends(get_db), userId: str = Depends(get_userId)):
    image = db.query(Image).filter(
        Image.imageId == imageId,
        Image.status == 'ready',
        Image.userId == userId).one_or_none()
    db.commit()

    if image is None:
        raise HTTPException(status_code=404, detail="Not found")

    extension = 'jpg' if image.mimeType == 'image/jpeg' else 'png'

    return get_image_content(image.imageId, extension, image.mimeType)

@router.get("/image", response_model=list[schemas.Image])
async def list_images(db: Session = Depends(get_db), userId: str = Depends(get_userId)):
    image = db.query(models.Image).filter(
        models.Image.userId == userId).all()
    db.commit()
    return image

@router.get("/image/{imageId}", response_model=schemas.Image)
async def get_image_object(imageId: UUID, userId: str = Depends(get_userId), db: Session = Depends(get_db)) -> schemas.Image:
    models.Image.children.property.strategy.join_depth = 5
    image = db.query(models.Image). \
      filter(
        models.Image.imageId == imageId,
        models.Image.userId == userId). \
      options(joinedload(Image.children)).  \
      one_or_none()
    db.commit()
    
    if image is None:
        raise HTTPException(status_code=404, detail="Not found")

    return image


@router.get("/image/{imageId}/status")
async def get_image_status(imageId: UUID, db: Session = Depends(get_db), userId: str = Depends(get_userId)) -> schemas.ImageStatusResponse:
    image = db.query(models.Image).filter(
        models.Image.imageId == imageId,
        models.Image.userId == userId). \
        with_entities(models.Image.status). \
          one_or_none()
    db.commit()

    if image is None:
        raise HTTPException(status_code=404, detail="Not found")

    return {"status": image.status}
