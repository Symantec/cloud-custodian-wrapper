#!/bin/bash
for policy in `ls policies`; do sed -i.bak -e s,{CC_SQS_URL},$CC_SQS_URL,g policies/$policy; done
docker build -t aws-cloudcustodian:latest .
for policy in `ls policies`; do sed -i.bak -e s,$CC_SQS_URL,'{CC_SQS_URL}',g policies/$policy; done
if [[ $? -ne 0 ]] ; then
  echo "\n\nFailed to build the docker image.\n\n"
  exit 1
fi
docker tag aws-cloudcustodian $DOCKER_REGISTRY_URL/aws_tools/aws-cloudcustodian
if [[ $? -ne 0 ]] ; then
  echo "\n\nFailed to tag the docker image.\n\n"
  exit 1
fi
echo "Tagging docker image  ..."
rm policies/*.bak
