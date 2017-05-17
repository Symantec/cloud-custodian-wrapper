#!/bin/sh
apk update
apk add --no-cache openssl git ca-certificates
update-ca-certificates
pip install -r /custodian/requirements.txt
rm -rf /var/cache/apk/*
mkdir -p /custodian/src
cd /custodian/src
# git clone https://github.com/capitalone/cloud-custodian.git
git clone https://github.com/JohnTheodore/cloud-custodian.git; cd cloud-custodian; git checkout less_log_spam; cd ..;
cp -r /custodian/src/cloud-custodian/tools/c7n_mailer /custodian/mailer
rm -rf /custodian/src
cd /custodian/mailer
echo "Installing mailer requirements"
pip install -r ./requirements.txt
python setup.py develop
rm /custodian/mailer/msg-templates/default.html.j2
cp /custodian/email/msg-templates/mail-template.html.j2 /custodian/mailer/msg-templates/default.html.j2
apk del git
