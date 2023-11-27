# Dependencies
- python 3.11
- pg 14
- S3 compatible server
- install requirements.txt

# Configuration
Environmental variables are used.

```Bash
# DB
DATABASE_URL=postgresql://app:123123123@localhost/app
# aka Echo in sqlalchemy session
DEBUG_SQL=true

# Image processing
## Internal name service, used in internal ml url template
ML_NAME_SERVICE=1700559467
## Internal workspace id for internal ml x-workspace-id header value
ML_WORKSPACE_ID=aaaaa-aaaaa-aaaaaa-aaaaaaaa

# 24ai token
ML_24AI_TOKEN=
ML_24AI_URL=https://core.24ai.tech/api/v1/

# ml calls retry tuning
ML_RETRY_INTERNVAL=10
ML_RETRY_ATTEMPTS=10

# S3 Configuration
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
# Default `us-east-1` for minio
AWS_REGION=us-east-1
S3_BUCKET=molbert
S3_ENDPOINT_URL=http://127.0.0.1:9000
## Subdir in bucket to use, i.e. bucket/image_dir/object_key
IMAGE_DIR=images

```

# Developing

- define environmental variables
- run PG/S3
- ...or use docker-compose
- ...or specify external in env vars
- run locally 
- ...or use docker
- e.g. `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`


