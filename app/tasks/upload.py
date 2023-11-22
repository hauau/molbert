import aioboto3
from fastapi import UploadFile, Depends
from sqlalchemy.orm import Session
from sqlalchemy import update
from ..models import Image
from datetime import datetime
from fastapi.responses import StreamingResponse
import boto3


# AWS S3 Configuration
AWS_ACCESS_KEY_ID = 'minioadmin'
AWS_SECRET_ACCESS_KEY = 'minioadmin'
AWS_REGION = 'us-east-1'
S3_BUCKET = 'molbert'
S3_ENDPOINT_URL = "http://127.0.0.1:9000"
IMAGE_DIR = 'images'

session = aioboto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

async def upload_file_to_s3(
    file: UploadFile,
    filename: str,
    extension: str
) -> str:
    blob_s3_key = f"/{IMAGE_DIR}/{filename}.{extension}"

    async with session.client("s3", endpoint_url=S3_ENDPOINT_URL) as s3:
        try:
            print(f"Uploading {blob_s3_key} to s3")
            await s3.upload_fileobj(file.file, S3_BUCKET, blob_s3_key)
            print(f"Finished Uploading {blob_s3_key} to s3")
        except Exception as e:
            print(f"Unable to s3 upload to {blob_s3_key}: {e} ({type(e)})")
            return ""

    return f"s3://{blob_s3_key}"

async def upload_original(
    file: UploadFile,
    filename: str,
    extension: str,
    db: Session
) -> str:
    await upload_file_to_s3(file, filename, extension)
    db.execute(
      update(Image)
        .where(Image.image_id == filename)
        .values({"status": "ready", "uploaded_at": datetime.now()})
    )
    db.commit()

def get_image_content(uuid: str, extension: str, media_type: str):
    # Initialize the S3 client
    object_key = f"/images/{uuid}.{extension}"
    print(object_key)

    s3_client = boto3.client('s3',
                            endpoint_url=S3_ENDPOINT_URL,
                            aws_access_key_id=AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                            region_name=AWS_REGION)

    # Get the object from S3
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=object_key)
    
    # Define a generator function to stream the data
    def iterfile():
        for chunk in response['Body'].iter_chunks(chunk_size=1024):
            yield chunk
    # Return a streaming response
    return StreamingResponse(
        content=iterfile(),
        media_type=media_type,
        headers={ "content-length" : str (response[ "ContentLength" ]), "etag" : response[ "ETag" ]}
        )
