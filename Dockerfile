FROM python:3.7-alpine

WORKDIR /opt/gimme-aws-creds

COPY . .

RUN apk --update add gcc musl-dev libffi-dev openssl-dev \
    && python setup.py install \
    && apk del --purge gcc musl-dev libffi-dev openssl-dev
