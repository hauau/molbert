from os import getenv

# DB
SQLALCHEMY_DATABASE_URL = getenv("DATABASE_URL", "postgresql://app:123123123@localhost/app")
# aka Echo in sqlalchemy session
DEBUG_SQL = True if getenv("DEBUG_SQL", "false").lower() == 'true' else False

# Image processing
name_service = getenv("ML_NAME_SERVICE","1700559467") 
internal_ml_workspace = getenv("ML_WORKSPACE_ID","111111-11111-11111-11111-1111111") 
internal_ml_url = f'https://mlspace.aicloud.sbercloud.ru/deployments/dgx2-inf-001/kfserving-{name_service}/v1/models/kfserving-{name_service}:predict'

# S3 Configuration
AWS_ACCESS_KEY_ID = getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = getenv("AWS_SECRET_ACCESS_KEY", 'minioadmin')
AWS_REGION = getenv("AWS_REGION", 'us-east-1')
S3_BUCKET = getenv("S3_BUCKET", 'molbert')
S3_ENDPOINT_URL = getenv("S3_ENDPOINT_URL", "http://127.0.0.1:9000")
IMAGE_DIR = getenv("IMAGE_DIR", 'images')
