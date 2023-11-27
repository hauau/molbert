from fastapi import FastAPI, status

from app.api.validation.exceptions import ImageValidationException
from .api.endpoints import image
from .database import engine
from . import models
from fastapi.responses import JSONResponse

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.exception_handler(ImageValidationException)
async def image_validation_exc_handler(_, exc: ImageValidationException):
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, 
        content={"errorType": exc.type, "error": exc.info})

app.include_router(image.router)