from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid
from fastapi.responses import FileResponse
import random

app = FastAPI()

class Image(BaseModel):
    status: str
    imageId: UUID
    createdAt: datetime

class OperationType(str, Enum):
    bgRemoval = "bgRemoval"
    doubleResolution = "doubleResolution"

class CreateChildrenBody(BaseModel):
    operationType: OperationType = Field()

class UploadError(BaseModel):
    error: str
    errorType: str

@app.get("/image", response_model=List[Image])
async def list_images():
    # Mock response for listing images
    return [
        {"status": "processing", "imageId": uuid4(), "createdAt": datetime.now()},
        {"status": "ready", "imageId": uuid4(), "createdAt": datetime.now()},
    ]

@app.post("/image", response_model=dict, status_code=201)
async def upload_image(file: UploadFile = File(...), operationType: Optional[OperationType] = Form(None)):
    # Mock response for uploading image

    image_id = str(uuid4())
    print("filename: ", file.filename)
    current_datetime = datetime.utcnow().isoformat() + 'Z'

    if operationType: 
      return {
        "type": "original",
        "status": "processing",
        "imageId": uuid.uuid4(),
        "children": [
            {
                "imageId": uuid.uuid4(),
                "type": operationType.value,
                "status": "processing"
            }
        ],
        "createdAt": current_datetime
      }

    return {
      "type": "original",
      "status": "processing",
      "imageId": uuid.uuid4(),
      "createdAt": current_datetime
    }

@app.get("/image/{imageId}", response_model=Image)
async def get_image(imageId: UUID):
    # Mock response for getting image status
    current_datetime = datetime.utcnow().isoformat() + 'Z'
    return {
        "type": "original",
        "status": "ready",
        "imageId": imageId,
        "children": [
            {
                "imageId": uuid.uuid4(),
                "status": "ready"
            }
        ],
        "createdAt": current_datetime
      }

@app.get("/image/{imageId}/download")
async def download_image(imageId: UUID):
    # Mock response for downloading processed file
    # Here, we return a placeholder response, replace this with the actual file handling logic
    return FileResponse("stallman.jpg")

@app.get("/image/{imageId}/status", response_model=dict)
async def download_image(imageId: UUID):
    # Mock response for downloading processed file
    # Here, we return a placeholder response, replace this with the actual file handling logic
    return random.choice([{"status": "ready"}, {"status": "processing"}, {"status": "error"}])


@app.post("/image/{imageId}/children", response_model=dict)
async def create_children(imageId: UUID, body: CreateChildrenBody):
    # Mock response for downloading processed file
    # Here, we return a placeholder response, replace this with the actual file handling logic
    return {
      "type": body.operationType.value,
      "status": "processing",
      "imageId": uuid.uuid4(),
      "createdAt": datetime.utcnow().isoformat() + 'Z'
    }

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "errorType": "customError"},
    )
