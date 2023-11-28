from os import getenv

# DB
SQLALCHEMY_DATABASE_URL = getenv("DATABASE_URL", "postgresql://app:123123123@localhost/app")
# aka Echo in sqlalchemy session
DEBUG_SQL = True if getenv("DEBUG_SQL", "false").lower() == 'true' else False

# Image processing
## Internal
ML_NAME_SERVICE = getenv("ML_NAME_SERVICE","1700559467") 
ML_WORKSPACE_ID = getenv("ML_WORKSPACE_ID","") 
ML_INTERNAL_URL = f'https://mlspace.aicloud.sbercloud.ru/deployments/dgx2-inf-001/kfserving-{ML_NAME_SERVICE}/v1/models/kfserving-{ML_NAME_SERVICE}:predict'

## 24ai token
ML_24AI_TOKEN = getenv("ML_24AI_TOKEN","") 
ML_24AI_URL = getenv("ML_24AI_URL","https://core.24ai.tech/api/v1/") 

## ml calls retry tuning
ML_RETRY_INTERVAL = int(getenv("ML_RETRY_INTERVAL","10"))
ML_RETRY_ATTEMPTS = int(getenv("ML_RETRY_ATTEMPTS","10"))

# S3 Configuration
AWS_ACCESS_KEY_ID = getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = getenv("AWS_SECRET_ACCESS_KEY", 'minioadmin')
AWS_REGION = getenv("AWS_REGION", 'us-east-1')
S3_BUCKET = getenv("S3_BUCKET", 'molbert')
S3_ENDPOINT_URL = getenv("S3_ENDPOINT_URL", "http://127.0.0.1:9000")
IMAGE_DIR = getenv("IMAGE_DIR", 'images')
