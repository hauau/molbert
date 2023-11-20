import aioboto3
from fastapi import UploadFile, HTTPException, Depends
from botocore.exceptions import NoCredentialsError
from sqlalchemy.orm import Session
from ..database import SessionLocal
from sqlalchemy import update
from ..models import Image

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = 'minioadmin'
AWS_SECRET_ACCESS_KEY = 'minioadmin'
AWS_REGION = 'us-east-1'
S3_BUCKET = 'molbert'
S3_ENDPOINT_URL = "http://127.0.0.1:9000"
IMAGE_DIR = 'images'

async def upload_file_to_s3(
    file: UploadFile,
    filename: str,
    extension: str,
    db: Session = Depends(get_db),
) -> str:
    blob_s3_key = f"/{IMAGE_DIR}/{filename}.{extension}"

    session = aioboto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    async with session.client("s3", endpoint_url=S3_ENDPOINT_URL) as s3:
        try:
            print(f"Uploading {blob_s3_key} to s3")
            await s3.upload_fileobj(file.file, S3_BUCKET, blob_s3_key)
            db.execute(
                update(Image).where(Image.image_id == filename).values(status='ready')
            )
            db.commit()
            print(f"Finished Uploading {blob_s3_key} to s3")
        except Exception as e:
            print(f"Unable to s3 upload to {blob_s3_key}: {e} ({type(e)})")
            return ""

    return f"s3://{blob_s3_key}"
