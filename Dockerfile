FROM python:2-alpine
ADD . /custodian
RUN /custodian/install_custodian.sh
CMD ["/custodian/clean_accounts.py"]

