import os
import time
import socket
import chardet
import pandas as pd
import boto3
from sqlalchemy import create_engine, text
from trino.dbapi import connect
from config_sales import *

def wait_for_service(host, port, service_name, timeout=30):
    print(f" Waiting for {service_name} at {host}:{port} ...")
    for i in range(timeout):
        try:
            with socket.create_connection((host, int(port)), timeout=2):
                print(f" {service_name} is up.")
                return
        except Exception:
            time.sleep(1)
    raise Exception(f" {service_name} at {host}:{port} didn't respond after {timeout} seconds.")

# Wait for dependent services
wait_for_service(PG_HOST, PG_PORT, "PostgreSQL")
wait_for_service(TRINO_HOST, TRINO_PORT, "Trino")
wait_for_service("minio", 9000, "MinIO")

# STEP 1: Detect encoding and read CSV
print(" Detecting file encoding...")
with open(CSV_FILE, 'rb') as f:
    raw = f.read(10000)
    detected_encoding = chardet.detect(raw)['encoding']

print(f" Detected encoding: {detected_encoding}")
print(" Reading CSV file...")
df = pd.read_csv(CSV_FILE, encoding=detected_encoding)

# STEP 2: Load to PostgreSQL
print(" Loading into PostgreSQL...")
conn_str = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
engine = create_engine(conn_str)

with engine.connect() as conn:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}"))
    df.to_sql(TABLE_NAME, conn, schema=PG_SCHEMA, if_exists='replace', index=False)

# STEP 3: Convert to Parquet
print(" Converting to Parquet...")
df.to_parquet(PARQUET_FILE, engine="pyarrow", index=False)

# STEP 4: Upload to MinIO
print(" Uploading to MinIO...")
s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
)

# Create bucket if it doesn't exist
buckets = s3.list_buckets().get("Buckets", [])
bucket_names = [b["Name"] for b in buckets]
if MINIO_BUCKET not in bucket_names:
    print(f" Creating bucket: {MINIO_BUCKET}")
    s3.create_bucket(Bucket=MINIO_BUCKET)

s3.upload_file(PARQUET_FILE, MINIO_BUCKET, S3_KEY)
print(f" Uploaded to s3://{MINIO_BUCKET}/{S3_KEY}")

# STEP 5: Register in Trino
print(" Registering external table in Trino...")
trino_conn = connect(
    host=TRINO_HOST,
    port=TRINO_PORT,
    user=TRINO_USER,
    catalog=TRINO_CATALOG,
    schema=TRINO_SCHEMA,
    http_scheme="http"
)

cursor = trino_conn.cursor()
cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {TRINO_CATALOG}.{TRINO_SCHEMA}")
cursor.execute(f"DROP TABLE IF EXISTS {TRINO_CATALOG}.{TRINO_SCHEMA}.{TABLE_NAME}_parquet")

create_table_sql = f"""
CREATE TABLE {TRINO_CATALOG}.{TRINO_SCHEMA}.{TABLE_NAME}_parquet (
{HIVE_COLUMNS}
)
WITH (
    external_location = '{S3_LOCATION}',
    format = 'PARQUET'
)
"""
cursor.execute(create_table_sql)
print(f" Trino table created: {TRINO_CATALOG}.{TRINO_SCHEMA}.{TABLE_NAME}_parquet")

# STEP 6: Sample preview
cursor.execute(f"SELECT * FROM {TRINO_CATALOG}.{TRINO_SCHEMA}.{TABLE_NAME}_parquet LIMIT 5")
rows = cursor.fetchall()
print(" Sample rows from Trino:")
for row in rows:
    print(row)
