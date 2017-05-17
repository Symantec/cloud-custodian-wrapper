FROM python:2-alpine
ADD . /custodian
RUN /custodian/deploy/install_custodian.sh
CMD ["/custodian/custodian_wrapper/clean_accounts.py"]
