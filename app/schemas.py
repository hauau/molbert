from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from enum import Enum

class ImageStatus(str, Enum):
    processing = "processing"
    ready = "ready"
    error = "error"

class OperationType(str, Enum):
    background_remove = "background_remove"
    super_resolution = "super_resolution"

class ModelType(str, Enum):
    internal = "internal"
    ai24 = "24ai"

class ImageBase(BaseModel):
    imageId: UUID4
    type: str
    status: ImageStatus
    fromImageId: Optional[UUID4]
    
class ImageCreate(ImageBase):
    pass

class ImageStatusResponse:
    status: ImageStatus

class Image(ImageBase):
    createdAt: datetime
    modelType: Optional[ModelType]
    children: Optional[list["Image"]]

    class Config:
        orm_mode = True

class CreateChildImage(BaseModel):
    operationType: OperationType
    modelType: Optional[ModelType] = ModelType.internal


class CreateImage(BaseModel):
    operationType: OperationType
    modelType: Optional[ModelType] = ModelType.internal
    image: str
