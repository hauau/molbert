from asyncio import sleep
from datetime import datetime
import requests
import io
import json
import base64
from .upload import get_image_content, upload_stream_to_s3, get_image_buffer_test, upload_file_to_s3, get_image_buffer_generator_s3
from ..models import Image
from ..schemas import OperationType
from ..database import SessionLocal
from sqlalchemy import update
from ..config import internal_ml_url, internal_ml_workspace
import time
from tempfile import SpooledTemporaryFile
import concurrent.futures
import httpx
from binascii import a2b_base64

async def async_post_request(url, json_data):
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=json_data)
        response.raise_for_status()
        return response.content

# model result to image contents
# TODO: stream result
def base64_2_image(data):
    print(data.content)
    content = json.loads(data.content)
    buff = io.BytesIO(base64.b64decode(content['predictions']))
    return Image.open(buff)

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

async def remove_background_native(from_uuid: str, from_extension: str, to_uuid: str):
    # TODO: Chain with upload end, can't isolate completely from original
    # for now
    print("ML remove_background_native")
    await sleep(1)
    # Step 1: Download parent from S3
    t_get_buff = time.time()
    buffer_generator = get_image_buffer_test(from_uuid, from_extension)
    print("ML got Buffer ", time.time() - t_get_buff)

    # Step 2: Encode to base64
    t_encode_b64 = time.time()
    base64_encoded = base64.b64encode(buffer_generator.read()).decode('utf-8')
    print("ML encoded image ", time.time() - t_encode_b64)

    # Step 3: POST to external service
    # TODO: Stream json body base64 part somehow
    # TODO: Add retry/backoff https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
    # TODO: Extract for switching endpoint/optype
    t_ml_request = time.time()
    internal_task = "background_remove"
    req_body = {"image": base64_encoded,"task":internal_task}

    # with open("Output.txt", "w") as text_file:
    #   text_file.write(json.dumps(req_body))

    # 3с повторный запрос - 10с
    # 10 попыток

    headers={
            "content-type": "application/json",
            "x-workspace-id": internal_ml_workspace
        }
   
    t_upload = time.time()

    # Step 5: Upload back to S3
    temp_file = SpooledTemporaryFile()
    req_body = {"image": base64_encoded,"task":internal_task}

    random_file = open("response.jpg", "wb")

    # For decoding chunks not suitable for decoding yet
    buffer = b""
    async with httpx.AsyncClient() as client:
      async with client.stream("POST", url=internal_ml_url,json=req_body,headers=headers, timeout=60) as response:
          async for chunk in response.aiter_bytes():
            print("Original:\t", len(chunk))
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

            print("For decode:\t", len(chunk_to_decode))

            if chunk_to_decode:
              try:
                  base64.b64decode(chunk_to_decode + b'==', validate=False)
              except:
                  print(chunk_to_decode)
  
              random_file.write(base64.b64decode(chunk_to_decode + b'==', validate=False))
              temp_file.write(base64.b64decode(chunk_to_decode + b'==', validate=False))   
                

  
 
    temp_file.seek(0)

    random_file.close()

    await upload_stream_to_s3(temp_file, to_uuid, from_extension)
    print("ML uploaded result ", time.time() - t_upload)
    
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
        print("ML marked as ready")
