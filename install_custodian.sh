#!/bin/sh
apk update
apk add --no-cache openssl git ca-certificates
update-ca-certificates
pip install -r /custodian/requirements.txt
rm -rf /var/cache/apk/*
mkdir -p /custodian/src
cd /custodian/src
git clone https://github.com/capitalone/cloud-custodian.git
cp -r /custodian/src/cloud-custodian/tools/c7n_mailer /custodian/mailer
rm -rf /custodian/src
cd /custodian/mailer
python setup.py develop
rm -rf /custodian/mailer/msg-templates
ln -s /custodian/email/msg-templates /custodian/mailer/msg-templates
apk del git
