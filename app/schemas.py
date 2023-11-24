from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from enum import Enum

class ImageBase(BaseModel):
    type: str
    status: str

class ImageCreate(ImageBase):
    pass

class OperationType(str, Enum):
    background_remove = "background_remove"
    super_resolution = "super_resolution"

class ModelType(str, Enum):
    internal = "internal"
    ai24 = "24ai"

class Image(ImageBase):
    image_id: UUID4
    created_at: datetime
    model_type: Optional[ModelType]
    size_bytes: Optional[int]
    mime_type: Optional[str]
    from_image_id: Optional[UUID4]

    class Config:
        orm_mode = True

class CreateChildImage(BaseModel):
    operationType: OperationType
    modelType: Optional[ModelType] = ModelType.internal
