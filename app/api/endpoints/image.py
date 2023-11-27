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


@router.post("/image", response_model=dict)
async def create_image(
    request: Request,
    background_tasks: BackgroundTasks,
    userId: str = Depends(get_userId),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    operationType: Optional[schemas.OperationType] = Form(None),
    modelType: Optional[schemas.ModelType] = Form(
        default=schemas.ModelType.internal)
):
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
    new_image = models.Image(
        type=operationType if operationType else "original",
        userId=userId,
        createdAt=datetime.now(),
        modelType=modelType,
        sizeBytes=size,
        mimeType=file.content_type,
        status="processing"  # assuming initial status is 'processing'
    )

    db.add(new_image)
    db.commit()
    db.refresh(new_image)

    children: List = []

    if operationType is not None:
        transform_image = models.Image(
            type=operationType,
            userId=userId,
            createdAt=datetime.now(),
            modelType=modelType,
            mimeType=file.content_type,
            fromImageId=new_image.imageId,
            status="processing"  # assuming initial status is 'processing'
        )
        db.add(transform_image)
        db.commit()
        db.refresh(transform_image)
        children.append({
            "type": operationType,
            "status": "processing",
            "modelType": modelType,
            "imageId": transform_image.imageId,
            "createdAt": transform_image.createdAt
        })

    # 3. Start image uploading background task without blocking
    background_tasks.add_task(upload_original, file,
                              new_image.imageId, extension, db)

    # 4. Set a task for processing if required
    for child in children:
        background_tasks.add_task(create_transformed_image, new_image.imageId,
                                  extension, child["imageId"], operationType, modelType)

    return {
        "type": "original",
        "status": "processing",
        "children": children,
        "imageId": new_image.imageId,
        "createdAt": new_image.createdAt
    }


@router.post("/image/{imageId}/child", response_model=dict)
async def create_image(
    request: Request,
    background_tasks: BackgroundTasks,
    imageId: UUID,
    createImage: schemas.CreateChildImage,
    userId: str = Depends(get_userId),
    db: Session = Depends(get_db),
):
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

    return {
        "type": createImage.operationType,
        "status": "processing",
        "modelType": createImage.modelType,
        "imageId": transform_image.imageId,
        "fromImageId": imageId,
        "createdAt": transform_image.createdAt
    }


@router.get("/image/{imageId}/download")
async def download_image(imageId: UUID, db: Session = Depends(get_db), userId: str = Depends(get_userId)):
    image = db.query(Image).filter(
        Image.imageId == imageId,
        Image.status == 'ready',
        Image.userId == userId).first()
    db.commit()

    if image is None:
        raise HTTPException(status_code=404, detail="Not found")

    extension = 'jpg' if image.mimeType == 'image/jpeg' else 'png'

    return get_image_content(image.imageId, extension, image.mimeType)

@router.get("/image")
async def list_images(db: Session = Depends(get_db), userId: str = Depends(get_userId)):
    image = db.query(models.Image).filter(
        models.Image.userId == userId).all()
    return image

@router.get("/image/{imageId}")
async def get_image_object(imageId: UUID, userId: str = Depends(get_userId), db: Session = Depends(get_db)):
    models.Image.children.property.strategy.join_depth = 5
    image = db.query(models.Image). \
      filter(
        models.Image.imageId == imageId,
        models.Image.userId == userId). \
      options(joinedload(Image.children)).  \
      one_or_none()
    
    if image is None:
        raise HTTPException(status_code=404, detail="Not found")

    return image


@router.get("/image/{imageId}/status")
async def get_image_status(imageId: UUID, db: Session = Depends(get_db), userId: str = Depends(get_userId)):
    image = db.query(models.Image).filter(
        models.Image.imageId == imageId,
        models.Image.userId == userId).one_or_none()

    if image is None:
        raise HTTPException(status_code=404, detail="Not found")

    return {"status": image.status}
