import aioboto3
from fastapi import UploadFile, Depends
from sqlalchemy.orm import Session
from sqlalchemy import update
from ..models import Image
from datetime import datetime
from fastapi.responses import StreamingResponse
import boto3
from ..config import AWS_ACCESS_KEY_ID, AWS_REGION, AWS_SECRET_ACCESS_KEY, S3_BUCKET, S3_ENDPOINT_URL, IMAGE_DIR
from smart_open import open

session = aioboto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

async def upload_stream_to_s3(stream_generator, filename: str, extension: str):
    blob_s3_key = f"/{IMAGE_DIR}/{filename}.{extension}"
    s3_client = boto3.client('s3',
                            endpoint_url=S3_ENDPOINT_URL,
                            aws_access_key_id=AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                            region_name=AWS_REGION)
    
    with open(f's3://{S3_BUCKET}/{blob_s3_key}', 'wb', transport_params={'client': s3_client}) as fout:
        for chunk in stream_generator:
            fout.write(chunk)
        print(f"Finished Uploading {blob_s3_key} to s3")

async def upload_file_to_s3(
    file,
    filename: str,
    extension: str
) -> str:
    blob_s3_key = f"/{IMAGE_DIR}/{filename}.{extension}"

    async with session.client("s3", endpoint_url=S3_ENDPOINT_URL) as s3:
        try:
            print(f"Uploading {blob_s3_key} to s3")
            await s3.upload_fileobj(file, S3_BUCKET, blob_s3_key)
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
    await upload_file_to_s3(file.file, filename, extension)
    db.execute(
      update(Image)
        .where(Image.imageId == filename)
        .values({"status": "ready", "uploadedAt": datetime.now()})
    )
    db.commit()

def get_image_buffer_generator_s3(uuid: str, extension: str):
    # Initialize the S3 client
    object_key = f"/{IMAGE_DIR}/{uuid}.{extension}"

    s3_client = boto3.client('s3',
                            endpoint_url=S3_ENDPOINT_URL,
                            aws_access_key_id=AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                            region_name=AWS_REGION)

    # Get the object from S3
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=object_key)
    
    for chunk in response['Body'].iter_chunks(chunk_size=1024):
      yield chunk

def get_image_buffer_test(uuid: str, extension: str):
    # Initialize the S3 client
    object_key = f"/{IMAGE_DIR}/{uuid}.{extension}"

    s3_client = boto3.client('s3',
                            endpoint_url=S3_ENDPOINT_URL,
                            aws_access_key_id=AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                            region_name=AWS_REGION)

    # Get the object from S3
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=object_key)
    
    return response['Body']

s3_client = boto3.client('s3',
                        endpoint_url=S3_ENDPOINT_URL,
                        aws_access_key_id=AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                        region_name=AWS_REGION)

def get_image_content(uuid: str, extension: str, media_type: str):
    # Initialize the S3 client
    object_key = f"/{IMAGE_DIR}/{uuid}.{extension}"

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
