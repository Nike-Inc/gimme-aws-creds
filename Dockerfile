FROM python:3.8-alpine

WORKDIR /opt/gimme-aws-creds

COPY . .

RUN apk --update add gcc musl-dev libffi-dev openssl-dev \
    && python setup.py install \
    && apk del --purge gcc musl-dev libffi-dev openssl-dev

ENTRYPOINT ["/usr/local/bin/gimme-aws-creds"]
