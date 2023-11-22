from asyncio import sleep
from datetime import datetime
import requests
import io
import json
import base64
from os import getenv
from .upload import get_image_content, get_image_buffer_test, upload_file_to_s3, get_image_buffer_generator_s3
from ..models import Image
from ..schemas import OperationType
from ..database import SessionLocal
from sqlalchemy import update

name_service = getenv("ML_NAME_SERVICE","1700559467") 
internal_ml_url = f'https://mlspace.aicloud.sbercloud.ru/deployments/dgx2-inf-001/kfserving-{name_service}/v1/models/kfserving-{name_service}:predict'
internal_ml_workspace = getenv("ML_WORKSPACE_ID","111111-11111-11111-11111-1111111") 

def buffer_gen_2_base64(buffer_generator):
    result = ""
    for chunk in buffer_generator:
        result += base64.b64encode(chunk).decode()
    return result

# model result to image contents
# TODO: stream result
def base64_2_image(data):
    print(data.content)
    content = json.loads(data.content)
    buff = io.BytesIO(base64.b64decode(content['predictions']))
    return Image.open(buff)

# Modified function to encode streamed content
def encode_image_base64_streaming_from_buffer(buffer_generator):
    result = ""
    for chunk in buffer_generator:
        result += base64.b64encode(chunk).decode()
    return result

def apply_transform(image: Image):
    if image.status == 'ready':
        raise BaseException("Trying to transform image in status 'ready'")
    
    match image.type:
        case OperationType.bgRemoval:
            print('bgRemoval ', image.image_id)
            remove_background_native()
        case OperationType.doubleResolution:
            print('doubleResolution ', image.image_id)

async def remove_background_native(from_uuid: str, from_extension: str, to_uuid: str):
    # TODO: Chain with upload end, can't isolate completely from original
    # for now
    print("ML remove_background_native")
    await sleep(1)
    # Step 1: Download parent from S3
    buffer_generator = get_image_buffer_test(from_uuid, from_extension)
    print("ML got Buffer")

    # Step 2: Encode to base64
    base64_encoded = encode_image_base64_streaming_from_buffer(buffer_generator)
    print("ML encoded image")

    # Step 3: POST to external service
    # TODO: Stream json body base64 part somehow
    # TODO: Add retry/backoff https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
    # TODO: Extract for switching endpoint/optype
    internal_task = "background_remove"
    req_body = {"image": base64_encoded,"task":internal_task}

    # with open("Output.txt", "w") as text_file:
    #   text_file.write(json.dumps(req_body))
    
    response = requests.post(
        url=internal_ml_url,
        json=req_body,
        headers={
            "content-type": "application/json",
            "x-workspace-id": internal_ml_workspace
        },
        timeout=60)
    print(response.content)
    response.raise_for_status()
    predictions = response.json().get("predictions", "")
    print("ML POSTed")

    # Step 4: Decode from base64
    decoded_data = base64.b64decode(predictions)
    # the decoded data in a BytesIO object
    decoded_data_io = io.BytesIO(decoded_data)
    print("ML response decoded")

    # Step 5: Upload back to S3
    await upload_file_to_s3(decoded_data_io, to_uuid, from_extension)
    print("ML uploaded result")

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
