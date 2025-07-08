from metaflow import FlowSpec, step, Parameter
import os, time, socket
import chardet
import pandas as pd
import boto3
from sqlalchemy import create_engine, text
from trino.dbapi import connect
from config_sales import *

class SalesETLFlow(FlowSpec):

    @step
    def start(self):
        print("Starting ETL Flow")
        self.next(self.wait_for_services)

    @step
    def wait_for_services(self):
        def wait_for_service(host, port, service_name, timeout=30):
            print(f" Waiting for {service_name} at {host}:{port} ...")
            for _ in range(timeout):
                try:
                    with socket.create_connection((host, int(port)), timeout=2):
                        print(f" {service_name} is up.")
                        return
                except Exception:
                    time.sleep(1)
            raise Exception(f" {service_name} at {host}:{port} didn't respond after {timeout} seconds.")

        def wait_for_trino_ready(host, port, user, catalog, schema, timeout=60):
            print(f" Waiting for Trino to be ready (catalog: {catalog}, schema: {schema})...")
            start = time.time()
            while time.time() - start < timeout:
                try:
                    conn = connect(
                        host=host,
                        port=port,
                        user=user,
                        catalog=catalog,
                        schema=schema,
                        http_scheme="http"
                    )
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    cur.fetchall()
                    print(" Trino is ready.")
                    return
                except Exception as e:
                    print(f"  Trino not ready yet: {e}")
                    time.sleep(3)
            raise Exception("Trino not ready after waiting.")

        wait_for_service(PG_HOST, PG_PORT, "PostgreSQL")
        wait_for_trino_ready(TRINO_HOST, TRINO_PORT, TRINO_USER, TRINO_CATALOG, TRINO_SCHEMA)
        wait_for_service("minio", 9000, "MinIO")

        self.next(self.read_csv)

    @step
    def read_csv(self):
        print(" Detecting file encoding...")
        with open(CSV_FILE, 'rb') as f:
            raw = f.read(10000)
            self.detected_encoding = chardet.detect(raw)['encoding']

        print(f" Detected encoding: {self.detected_encoding}")
        print(" Reading CSV file...")
        self.df = pd.read_csv(CSV_FILE, encoding=self.detected_encoding)
        print(f" Read {len(self.df)} rows from CSV.")
        self.next(self.load_to_postgres)

    @step
    def load_to_postgres(self):
        print(" Loading into PostgreSQL...")
        conn_str = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
        engine = create_engine(conn_str)

        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}"))
            self.df.to_sql(TABLE_NAME, conn, schema=PG_SCHEMA, if_exists='replace', index=False)

        print(" Data inserted into PostgreSQL.")
        self.next(self.convert_to_parquet)

    @step
    def convert_to_parquet(self):
        print(" Converting to Parquet...")
        self.df.to_parquet(PARQUET_FILE, engine="pyarrow", index=False)
        print(" Parquet file created.")
        self.next(self.upload_to_minio)

    @step
    def upload_to_minio(self):
        print(" Uploading to MinIO...")
        s3 = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
        )

        buckets = s3.list_buckets().get("Buckets", [])
        bucket_names = [b["Name"] for b in buckets]
        if MINIO_BUCKET not in bucket_names:
            print(f" Creating bucket: {MINIO_BUCKET}")
            s3.create_bucket(Bucket=MINIO_BUCKET)

        s3.upload_file(PARQUET_FILE, MINIO_BUCKET, S3_KEY)
        print(f" Uploaded to s3://{MINIO_BUCKET}/{S3_KEY}")
        self.next(self.register_in_trino)

    @step
    def register_in_trino(self):
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
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {TRINO_SCHEMA}")
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}_parquet")

        create_table_sql = f"""
        CREATE TABLE {TABLE_NAME}_parquet (
            {HIVE_COLUMNS}
        )
        WITH (
            external_location = '{S3_LOCATION}',
            format = 'PARQUET'
        )
        """
        cursor.execute(create_table_sql)
        print(f" Trino table created: {TABLE_NAME}_parquet")
        self.trino_conn = trino_conn
        self.next(self.preview_data)

    @step
    def preview_data(self):
        cursor = self.trino_conn.cursor()
        cursor.execute(f"SELECT * FROM {TABLE_NAME}_parquet LIMIT 5")
        rows = cursor.fetchall()
        print(" Sample rows from Trino:")
        for row in rows:
            print(row)
        self.next(self.end)

    @step
    def end(self):
        print("ETL flow completed successfully.")

if __name__ == "__main__":
    SalesETLFlow()