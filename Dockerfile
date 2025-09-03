FROM openjdk:8-jre-slim

WORKDIR /opt

ENV HADOOP_VERSION=3.2.0
ENV METASTORE_VERSION=3.0.0
ENV ICEBERG_VERSION=1.5.0
ENV AWS_SDK_VERSION=1.11.563

# Install required tools (added bash here ✅)
RUN apt-get update && apt-get install -y netcat curl bash && rm -rf /var/lib/apt/lists/*

ENV HADOOP_HOME=/opt/hadoop-${HADOOP_VERSION}
ENV HIVE_HOME=/opt/apache-hive-metastore-${METASTORE_VERSION}-bin
ENV PATH="${HADOOP_HOME}/bin:${HIVE_HOME}/bin:${PATH}"

# Download and extract Hive + Hadoop + MySQL connector + PostgreSQL driver
RUN curl -L https://downloads.apache.org/hive/hive-standalone-metastore-${METASTORE_VERSION}/hive-standalone-metastore-${METASTORE_VERSION}-bin.tar.gz \
        | tar zxf - && \
    curl -L https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz \
        | tar zxf - && \
    curl -L https://dev.mysql.com/get/Downloads/Connector-J/mysql-connector-java-8.0.19.tar.gz \
        | tar zxf - && \
    curl -L --output postgresql-42.4.0.jar https://jdbc.postgresql.org/download/postgresql-42.4.0.jar && \
    cp mysql-connector-java-8.0.19/mysql-connector-java-8.0.19.jar ${HIVE_HOME}/lib/ && \
    cp postgresql-42.4.0.jar ${HIVE_HOME}/lib/ && \
    rm -rf mysql-connector-java-8.0.19 postgresql-42.4.0.jar

# Add Iceberg Hive runtime JAR
RUN curl -L -o ${HIVE_HOME}/lib/iceberg-hive-runtime-${ICEBERG_VERSION}.jar \
        https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-hive-runtime/${ICEBERG_VERSION}/iceberg-hive-runtime-${ICEBERG_VERSION}.jar

# Add Hadoop AWS + AWS SDK bundle for S3/MinIO support
RUN curl -L -o ${HADOOP_HOME}/share/hadoop/common/lib/hadoop-aws-${HADOOP_VERSION}.jar \
        https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_VERSION}/hadoop-aws-${HADOOP_VERSION}.jar && \
    curl -L -o ${HADOOP_HOME}/share/hadoop/common/lib/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar \
        https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_VERSION}/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar

# 🔁 COPY custom local JAR + log4j2 config
COPY scripts/hive-exec-3.0.0.jar ${HIVE_HOME}/lib/
COPY scripts/metastore-log4j2.properties ${HIVE_HOME}/conf/

# ✅ Copy Hive configuration so it doesn't fallback to Derby
COPY conf/metastore-site.xml ${HIVE_HOME}/conf/hive-site.xml

# Add entrypoint script
COPY scripts/entrypoint.sh /entrypoint.sh

# Create hive user and set permissions
RUN groupadd -r hive --gid=1000 && \
    useradd -r -g hive --uid=1000 -d ${HIVE_HOME} hive && \
    chown hive:hive -R ${HIVE_HOME} && \
    chown hive:hive /entrypoint.sh && chmod +x /entrypoint.sh && \
    chown hive:hive /opt

USER hive
EXPOSE 9083

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
