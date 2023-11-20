from sqlalchemy import Column, String, Enum, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base
import uuid

class Image(Base):
    __tablename__ = "image"
    image_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(Enum('original', 'bgRemoval', 'doubleResolution', name='image_type'))
    created_at = Column(DateTime(timezone=True))
    size_bytes = Column(Integer)
    mime_type = Column(String)
    user_id = Column(String)
    from_image_id = Column(UUID(as_uuid=True), ForeignKey('image.image_id'))
    status = Column(Enum('processing', 'ready', 'error', name='image_status'))

    parent = relationship("Image", remote_side=[image_id])