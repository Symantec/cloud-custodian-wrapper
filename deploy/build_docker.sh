#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
for policy in `ls $DIR/../policies`; do sed -i.bak -e s,{CC_SQS_URL},$CC_SQS_URL,g $DIR/../policies/$policy; done
rm -rf policies/*.bak
docker build -t aws-cloudcustodian:latest $DIR/../
for policy in `ls $DIR/../policies`; do sed -i.bak -e s,$CC_SQS_URL,'{CC_SQS_URL}',g $DIR/../policies/$policy; done
rm -rf $DIR/../policies/*.bak
if [[ $? -ne 0 ]] ; then
  echo "\n\nFailed to build the docker image.\n\n"
  exit 1
fi
echo "Successfully built the docker container for cloud custodian"
if [[ -z "$DOCKER_REGISTRY_URL" ]]; then
  echo "DOCKER_REGISTRY_URL ENV variable is not set, so the build script did not tag the docker image. Though the docker image did build. Check docker images."
  exit 1
fi
docker tag aws-cloudcustodian $DOCKER_REGISTRY_URL/aws_tools/aws-cloudcustodian
if [[ $? -ne 0 ]] ; then
  echo "Failed to tag the docker image."
  exit 1
fi
echo "Tagged docker image."
