FROM fluentd

USER root

RUN gem install fluent-plugin-docker_metadata_filter fluent-plugin-elasticsearch --no-document

COPY conf /fluentd/etc

USER fluent