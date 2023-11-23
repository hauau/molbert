from asyncio import sleep
from datetime import datetime
import requests
import base64
from .upload import upload_stream_to_s3, get_image_buffer_test
from ..models import Image
from ..schemas import ModelType, OperationType
from ..database import SessionLocal
from sqlalchemy import update
from ..config import internal_ml_url, internal_ml_workspace
import time
from tempfile import SpooledTemporaryFile
import httpx


def apply_transform(image: Image):
    if image.status == 'ready':
        raise BaseException("Trying to transform image in status 'ready'")

    match image.type:
        case OperationType.bgRemoval:
            print('bgRemoval ', image.image_id)
            remove_background_native()
        case OperationType.doubleResolution:
            print('doubleResolution ', image.image_id)


async def stream_response(url, req_body, headers):
    with requests.post(url=url, json=req_body, headers=headers, stream=True, timeout=60) as response:
        if response.status_code > 300:
            print(response.content)
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=32000):
            yield chunk  # This will yield raw byte-like chunks of the HTTP response


async def internal_ml_call(image_base64: str, task: str, temp_file: SpooledTemporaryFile[bytes]):
    # TODO:    retry
    #    # 3с повторный запрос - 10с
    #    # 10 попыток

    req_body = {
        "image": image_base64,
        "task": task
    }

    headers = {
        "content-type": "application/json",
        "x-workspace-id": internal_ml_workspace
    }

    # For decoding chunks not suitable for decoding yet
    buffer = b""
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url=internal_ml_url, json=req_body, headers=headers, timeout=60) as response:
            async for chunk in response.aiter_bytes():
                chunk = buffer + chunk
                # Extract  b'{"predictions":"saddsfdfd...
                if b"predictions" in chunk:
                    chunk = chunk[16:]
                if b"\"}" in chunk:
                    chunk = chunk[:-3]

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

    # Step 1: Download parent from S3
    buffer_generator = get_image_buffer_test(from_uuid, from_extension)

    # Step 2: Encode to base64
    t_encode_b64 = time.time()
    base64_encoded = base64.b64encode(buffer_generator.read()).decode('utf-8')
    print("Image -> base64 ", time.time() - t_encode_b64)

    # Step 3: POST to external service
    # TODO: Add retry/backoff https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
    # TODO: Extract for switching endpoint/optype

    # Step 5: Upload back to S3
    temp_file = SpooledTemporaryFile(max_size=1024)
    
    match model:
        case ModelType.internal:
            internal_task = 'background_remove' if task == OperationType.bgRemoval else 'super_resolution'
            await internal_ml_call(base64_encoded, internal_task, temp_file)
        case ModelType.ai24:
            raise BaseException("Not implemented")  
    
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
