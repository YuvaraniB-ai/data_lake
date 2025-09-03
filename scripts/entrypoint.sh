#!/bin/bash
set -euo pipefail

export HADOOP_HOME=/opt/hadoop-3.2.0
export HIVE_HOME=/opt/apache-hive-metastore-3.0.0-bin
export JAVA_HOME=/usr/local/openjdk-8

# Defaults (can be overridden via env)
export METASTORE_DB_HOSTNAME=${METASTORE_DB_HOSTNAME:-localhost}
export HMS_PORT=${HMS_PORT:-9083}
export METASTORE_TYPE=${METASTORE_TYPE:-postgres}   # default to postgres

MYSQL="mysql"
POSTGRES="postgres"

# Configure Hadoop AWS classpath (match JAR versions from Dockerfile)
export HADOOP_CLASSPATH="${HADOOP_HOME}/share/hadoop/common/lib/aws-java-sdk-bundle-1.11.563.jar:${HADOOP_HOME}/share/hadoop/common/lib/hadoop-aws-3.2.0.jar"

wait_for_db() {
  local host=$1
  local port=$2
  echo "⏳ Waiting for database on ${host}:${port} ..."
  until nc -z "${host}" "${port}"; do
    sleep 1
  done
  echo "✅ Database on ${host}:${port} is available"
}

init_metastore() {
  local db_type=$1
  echo "🔧 Checking Hive Metastore schema for ${db_type}..."
  if ! "${HIVE_HOME}/bin/schematool" -dbType "${db_type}" -info >/dev/null 2>&1; then
    echo "⚡ Initializing schema for ${db_type}..."
    "${HIVE_HOME}/bin/schematool" -initSchema -dbType "${db_type}"
  else
    echo "✅ Schema already initialized for ${db_type}"
  fi
}

start_metastore() {
  echo "🚀 Starting Hive Metastore on port ${HMS_PORT}"
  exec "${HIVE_HOME}/bin/start-metastore" -p "${HMS_PORT}"
}

case "${METASTORE_TYPE}" in
  "${MYSQL}")
    wait_for_db "${METASTORE_DB_HOSTNAME}" 3306
    init_metastore mysql
    start_metastore
    ;;
  "${POSTGRES}")
    wait_for_db "${METASTORE_DB_HOSTNAME}" 5432
    init_metastore postgres
    start_metastore
    ;;
  *)
    echo "❌ Unknown METASTORE_TYPE: ${METASTORE_TYPE}. Must be '${MYSQL}' or '${POSTGRES}'."
    exit 1
    ;;
esac
