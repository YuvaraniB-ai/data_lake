
# PostgreSQL Config
PG_USER = "admin"
PG_PASSWORD = "admin123"
PG_HOST = "localhost"
PG_PORT = 5433
PG_DB = "data_db"
PG_SCHEMA = "hr"
PG_TABLE = "employees"

# MinIO Config
MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minio"
MINIO_SECRET_KEY = "minio123"
MINIO_BUCKET = "datalake"
S3_OBJECT_KEY = f"{PG_SCHEMA}/{PG_TABLE}/{PG_TABLE}.parquet"
S3_EXTERNAL_LOCATION = f"s3a://{MINIO_BUCKET}/{PG_SCHEMA}/{PG_TABLE}/"

# Trino Config
TRINO_HOST = "localhost"
TRINO_PORT = 8081
TRINO_USER = "admin"
TRINO_CATALOG = "hive"
TRINO_SCHEMA = PG_SCHEMA
