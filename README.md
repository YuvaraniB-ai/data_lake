# Trino-Hive-Postgres-Minio on Docker

This project sets up Trino + Hive + MinIO with PostgreSQL as the Hive Metastore using Docker Compose. 

Step 1: Go to the docker-compose directory
 cd docker-compose
Step 2: Build the Hive Metastore Docker image (Postgres-compatible)
 docker build -t my-hive-metastore .
Step 3: Start all services using Docker Compose
 docker-compose up -d
Step 4: Create a bucket in MinIO
  Username: minio
  Password: minio123
  Access the MinIO console via http://localhost:9000
Step 5: Connect to the running Trino container
 docker exec -it docker-compose_trino-coordinator_1 trino
Step 6: Create schema and table using Trino
  CREATE SCHEMA minio.test
  WITH (location = 's3a://test/');

 CREATE TABLE minio.test.customer
 WITH (
    format = 'ORC',
    external_location = 's3a://test/customer/'
 ) 
 AS SELECT * FROM tpch.tiny.customer;
 Step 7: Inspect Hive Metastore in Postgres
 docker exec -it docker-compose_postgres_1 psql -U admin -d hive_db
Step 8: Run SQL queries to view metadata
SELECT
  "DB_ID",
  "DB_LOCATION_URI",
  "NAME", 
  "OWNER_NAME",
  "OWNER_TYPE",
  "CTLG_NAME"
FROM "DBS";
Step 9: Shut down all containers
 docker-compose down


