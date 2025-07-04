import os
import pandas as pd
import boto3
from sqlalchemy import create_engine
from trino.dbapi import connect
import config  # ← import config module

# Step 1: Read from PostgreSQL
print(" Reading data from PostgreSQL...")
conn_str = f"postgresql+psycopg2://{config.PG_USER}:{config.PG_PASSWORD}@{config.PG_HOST}:{config.PG_PORT}/{config.PG_DB}"
engine = create_engine(conn_str)
df = pd.read_sql_table(config.PG_TABLE, con=engine, schema=config.PG_SCHEMA)

# Step 2: Convert to Parquet
local_parquet = f"{config.PG_TABLE}.parquet"
df.to_parquet(local_parquet, engine="pyarrow", index=False)
print(f" Converted to Parquet: {local_parquet}")

# Step 3: Upload to MinIO
print(" Uploading to MinIO...")
s3 = boto3.client(
    "s3",
    endpoint_url=config.MINIO_ENDPOINT,
    aws_access_key_id=config.MINIO_ACCESS_KEY,
    aws_secret_access_key=config.MINIO_SECRET_KEY,
)

buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]
if config.MINIO_BUCKET not in buckets:
    s3.create_bucket(Bucket=config.MINIO_BUCKET)

s3.upload_file(local_parquet, config.MINIO_BUCKET, config.S3_OBJECT_KEY)
print(f" Uploaded to s3://{config.MINIO_BUCKET}/{config.S3_OBJECT_KEY}")

# Step 4: Register external table in Trino
print(" Registering external table in Trino (Hive)...")
conn = connect(
    host=config.TRINO_HOST,
    port=config.TRINO_PORT,
    user=config.TRINO_USER,
    catalog=config.TRINO_CATALOG,
    schema=config.TRINO_SCHEMA,
    http_scheme="http",
)
cursor = conn.cursor()

cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {config.TRINO_CATALOG}.{config.TRINO_SCHEMA}")
cursor.execute(f"DROP TABLE IF EXISTS {config.TRINO_CATALOG}.{config.TRINO_SCHEMA}.{config.PG_TABLE}_parquet")

columns = ",\n".join([
    "id INT",
    "name VARCHAR",
    "department VARCHAR",
    "job_title VARCHAR",
    "salary DOUBLE"
])

create_table_sql = f"""
CREATE TABLE {config.TRINO_CATALOG}.{config.TRINO_SCHEMA}.{config.PG_TABLE}_parquet (
{columns}
)
WITH (
    external_location = '{config.S3_EXTERNAL_LOCATION}',
    format = 'PARQUET'
)
"""
cursor.execute(create_table_sql)
print(f" Table registered in Trino as {config.TRINO_CATALOG}.{config.TRINO_SCHEMA}.{config.PG_TABLE}_parquet")

cursor.execute(f"SELECT * FROM {config.TRINO_CATALOG}.{config.TRINO_SCHEMA}.{config.PG_TABLE}_parquet")
rows = cursor.fetchall()
print(" Sample Data from Trino:")
for row in rows:
    print(row)