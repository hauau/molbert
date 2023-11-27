from sqlalchemy import Column, String, Enum, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship, mapped_column, deferred
from sqlalchemy.dialects.postgresql import UUID
from .database import Base
import uuid

class Image(Base):
    __tablename__ = "image"
    imageId = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, name='image_id')
    type = Column(Enum('original', 'background_remove', 'super_resolution', name='image_type'))
    modelType = Column(Enum('internal', '24ai', name='model_type'), name='model_type')
    createdAt = Column(DateTime(timezone=True), name='created_at')
    uploadedAt = deferred(Column(DateTime(timezone=True), name='uploaded_at'))
    transformedAt = deferred(Column(DateTime(timezone=True), name='transformed_at'))
    sizeBytes = deferred(Column(Integer, name='size_bytes'))
    mimeType = Column(String, name='mime_type')
    userId = deferred(Column(String, name='user_id'))
    fromImageId = mapped_column(UUID(as_uuid=True), ForeignKey('image.image_id'), name='from_image_id')
    status = Column(Enum('processing', 'ready', 'error', name='image_status'))

    children = relationship("Image", back_populates="parent", remote_side=[fromImageId])
    parent = relationship("Image", back_populates="children", remote_side=[imageId])
