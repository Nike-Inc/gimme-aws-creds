FROM python:3.8-alpine

WORKDIR /opt/gimme-aws-creds

COPY . .

ENV PACKAGES="gcc musl-dev python3-dev libffi-dev openssl-dev cargo"

RUN apk --update add $PACKAGES \
    && pip install --upgrade pip setuptools-rust \
    && pip install futures \
    && python setup.py install \
    && apk del --purge $PACKAGES

ENTRYPOINT ["/usr/local/bin/gimme-aws-creds"]
