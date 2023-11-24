from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, BackgroundTasks, Request, Header
from sqlalchemy.orm import Session
from typing import List
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

# Dependency


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_id(x_user_id: str = Header(None)):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="X-User-Id header missing")
    return x_user_id


@router.post("/image", response_model=dict)
async def create_image(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    operationType: Optional[schemas.OperationType] = Form(None),
    modelType: Optional[schemas.ModelType] = Form(
        default=schemas.ModelType.internal)
):
    # TODO:
    if modelType == schemas.ModelType.ai24:
        raise HTTPException(
            status_code=400, detail="Specified model is not supported yet")

    extension = 'jpg' if file.content_type == 'image/jpeg' else 'png'
    size = int(request.headers.get('content-length'))
    # 1. Validate that file size is less than 12MB
    if size > 12_000_000:
        raise HTTPException(
            status_code=400, detail="File size exceeds limit of 12MB")

    # 2. Insert new record to the Image db and get UUID image_id in return
    new_image = models.Image(
        type=operationType if operationType else "original",
        user_id=user_id,
        created_at=datetime.now(),
        size_bytes=size,
        mime_type=file.content_type,
        status="processing"  # assuming initial status is 'processing'
    )

    db.add(new_image)
    db.commit()
    db.refresh(new_image)

    children: List = []

    if operationType is not None:
        transform_image = models.Image(
            type=operationType,
            user_id=user_id,
            created_at=datetime.now(),
            mime_type=file.content_type,
            from_image_id=new_image.image_id,
            status="processing"  # assuming initial status is 'processing'
        )
        db.add(transform_image)
        db.commit()
        db.refresh(transform_image)
        children.append({
            "type": operationType,
            "status": "processing",
            "modelType": modelType,
            "imageId": transform_image.image_id,
            "createdAt": transform_image.created_at
        })

    # 3. Start image uploading background task without blocking
    background_tasks.add_task(upload_original, file,
                              new_image.image_id, extension, db)

    # 4. Set a task for processing if required
    for child in children:
        background_tasks.add_task(create_transformed_image, new_image.image_id,
                                  extension, child["imageId"], operationType, modelType)

    return {
        "type": "original",
        "status": "processing",
        "children": children,
        "imageId": new_image.image_id,
        "createdAt": new_image.created_at
    }


@router.post("/image/{imageId}/child", response_model=dict)
async def create_image(
    request: Request,
    background_tasks: BackgroundTasks,
    imageId: UUID,
    createImage: schemas.CreateChildImage,
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    # TODO:
    if createImage.modelType == schemas.ModelType.ai24:
        raise HTTPException(
            status_code=400, detail="Specified model is not supported yet")

    image = db.query(Image).filter(
    Image.image_id == imageId,
    Image.user_id == user_id).one()
    db.commit()

    size = int(request.headers.get('content-length'))
    # 1. Validate that file size is less than 12MB
    if size > 12_000_000:
        raise HTTPException(
            status_code=400, detail="File size exceeds limit of 12MB")

    transform_image = models.Image(
        type=createImage.operationType,
        user_id=user_id,
        created_at=datetime.now(),
        # TODO: add to db model
        model_type=createImage.modelType,
        mime_type=image.mime_type,
        from_image_id=imageId,
        status="processing"  # assuming initial status is 'processing'
    )
    db.add(transform_image)
    db.commit()
    db.refresh(transform_image)
    extension = 'jpg' if image.mime_type == 'image/jpeg' else 'png'

    background_tasks.add_task(create_transformed_image, imageId,
                              extension, transform_image.image_id, createImage.operationType, createImage.modelType)

    return {
        "type": createImage.operationType,
        "status": "processing",
        "modelType": createImage.modelType,
        "imageId": transform_image.image_id,
        "fromImageId": imageId,
        "createdAt": transform_image.created_at
    }


@router.get("/image/{imageId}/download")
async def download_image(imageId: UUID, db: Session = Depends(get_db), user_id: str = Depends(get_user_id)):
    image = db.query(Image).filter(
        Image.image_id == imageId,
        Image.status == 'ready',
        Image.user_id == user_id).first()
    db.commit()

    if image is None:
        raise HTTPException(status_code=404, detail="Not found")

    extension = 'jpg' if image.mime_type == 'image/jpeg' else 'png'

    return get_image_content(image.image_id, extension, image.mime_type)


@router.get("/image")
async def list_images(db: Session = Depends(get_db), user_id: str = Depends(get_user_id)):
    image = db.query(models.Image).filter(
        models.Image.user_id == user_id).all()
    return image


@router.get("/image/{imageId}", response_model=schemas.Image)
async def get_image_object(imageId: UUID, db: Session = Depends(get_db)):
    # TODO: User filtering
    image = db.query(models.Image).filter(
        models.Image.image_id == imageId).first()

    if image is None:
        raise HTTPException(status_code=404, detail="Not found")

    return image


@router.get("/image/{imageId}/status")
async def get_image_status(imageId: UUID, db: Session = Depends(get_db), user_id: str = Depends(get_user_id)):
    image = db.query(models.Image).filter(
        models.Image.image_id == imageId, models.Image.user_id == user_id).first()

    if image is None:
        raise HTTPException(status_code=404, detail="Not found")

    return {"status": image.status}
