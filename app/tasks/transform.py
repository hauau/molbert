from asyncio import sleep
from datetime import datetime
import json
import requests
import base64
from .upload import upload_stream_to_s3, get_image_buffer_test
from ..models import Image
from ..schemas import ModelType, OperationType
from ..database import SessionLocal
from sqlalchemy import update
from ..config import internal_ml_url, internal_ml_workspace, ml_24ai_token, ml_24ai_url
import time
from tempfile import SpooledTemporaryFile
import httpx

async def ml_call(model: ModelType, image_base64: str, task: str, temp_file: SpooledTemporaryFile[bytes]):
    # TODO:    retry
    #    # 3с повторный запрос - 10с
    #    # 10 попыток

    ml_url = internal_ml_url if model == ModelType.internal else ml_24ai_url

    if model == ModelType.ai24:
        ml_url += 'remove-background'

    req_body = {
        "image": image_base64,
        "task": task
    } if model == ModelType.internal else {
        "image": image_base64
    }

    headers = {
        "content-type": "application/json",
        "x-workspace-id": internal_ml_workspace
    } if model == ModelType.internal else {
        "content-type": "application/json",
        "authorization": f"Token {ml_24ai_token}"
    }

    # For decoding chunks not suitable for decoding yet
    buffer = b""

    image_chunk_start_key = b"predictions\":\""
    image_chunk_start_index = 16

    image_chunk_end_key = b"\"}"
    image_chunk_end_index = -3

    # For model-dependant chunking
    if model == ModelType.ai24:
        #  {"success":true,"code":200,"message":"","error":"","data":{"image":"
        image_chunk_start_key = b"data\":{\"image\":\""
        image_chunk_start_index = 68

        image_chunk_end_key = b"\"}}"
        image_chunk_end_index = -4

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url=ml_url, json=req_body, headers=headers, timeout=60) as response:
            if response.is_error:
                temp_file.close()
                await response.aread()
                return response.content
            async for chunk in response.aiter_bytes():
                chunk = chunk.replace(b"\\", b"")                    
                chunk = buffer + chunk
                
                # Extract  b'{"predictions":"saddsfdfd...
                if image_chunk_start_key in chunk:
                    chunk = chunk[image_chunk_start_index:]
                if image_chunk_end_key in chunk:
                    chunk = chunk[:image_chunk_end_index]

                # Calculate how much can be cleanly decoded
                cut_off = len(chunk) % 4
                buffer = chunk[-cut_off:] if cut_off != 0 else b""
                chunk_to_decode = chunk[:-cut_off] if cut_off != 0 else chunk

                # If enough bytes for decode is collected - do it, otherwise wait for next buffer + chunk
                if chunk_to_decode:
                    temp_file.write(base64.b64decode(
                        chunk_to_decode + b'==', validate=False))

async def create_transformed_image(from_uuid: str, from_extension: str, to_uuid: str, task: OperationType, model: ModelType):
    # TODO: Chain with upload end, can't isolate completely from original
    # for now
    await sleep(1)
    print(f"Transforming from {from_uuid}.{from_extension}: {model}/{task}")

    # Step 1: Download parent from S3
    buffer_generator = get_image_buffer_test(from_uuid, from_extension)

    # Step 2: Encode to base64
    base64_encoded = base64.b64encode(buffer_generator.read()).decode('utf-8')

    # Step 3: POST to external service
    # TODO: Add retry/backoff https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
    # TODO: Extract for switching endpoint/optype

    # Step 5: Upload back to S3
    temp_file = SpooledTemporaryFile(max_size=1024)
    err = ""
    match model:
        case ModelType.internal:
            internal_task = 'background_remove' if task == OperationType.background_remove else 'super_resolution'
            err = await ml_call(model, base64_encoded, internal_task, temp_file)
        case ModelType.ai24:
            err = await ml_call(model, base64_encoded, task, temp_file)
    
    if temp_file.closed:
        print("Image processing error: \n", json.dumps(err.decode('utf-8')))
        with SessionLocal() as db:
            db.execute(
                update(Image)
              .where(Image.image_id == to_uuid)
              .values({"status": "error", "uploaded_at": datetime.now(), "transformed_at": datetime.now()})
            )
            db.commit()
            db.close()
            print("Transformed image marked as error")
        return

    temp_file.seek(0)

    await upload_stream_to_s3(temp_file, to_uuid, from_extension)

    temp_file.close()

    # Step 6: Set child status
    with SessionLocal() as db:
        db.execute(
            update(Image)
          .where(Image.image_id == to_uuid)
          .values({"status": "ready", "uploaded_at": datetime.now(), "transformed_at": datetime.now()})
        )
        db.commit()
        db.close()
        print("Transformed image marked as ready")
