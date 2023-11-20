from fastapi import FastAPI
from .api.endpoints import image
from .database import engine
from . import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(image.router)