FROM fluent/fluentd:v1.16-1

USER root

RUN gem install fluent-plugin-elasticsearch fluent-plugin-docker_metadata_filter --no-document

COPY conf /fluentd/etc

USER fluent
