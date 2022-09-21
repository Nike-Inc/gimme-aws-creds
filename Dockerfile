FROM python:3.10-alpine

WORKDIR /opt/gimme-aws-creds

COPY . .

RUN apk --update add libgcc

ENV PACKAGES="gcc musl-dev python3-dev libffi-dev openssl-dev cargo"

RUN apk --update add $PACKAGES
RUN pip install --upgrade pip setuptools-rust
RUN pip install .
RUN apk del --purge $PACKAGES

ENTRYPOINT ["/usr/local/bin/gimme-aws-creds"]
