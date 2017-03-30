#!/bin/bash
[ -z "$DOCKER_REGISTRY_URL" ] && echo "Need to set env DOCKER_REGISTRY_URL" && exit 1
[ -z "$OPENSHIFT_URL" ] && echo "Need to set env OPENSHIFT_URL" && exit 1
[ -z "$CC_SQS_URL" ] && echo "Need to set env CC_SQS_URL" && exit 1
oc project aws-cloudcustodian
if [[ $? -ne 0 ]] ; then
  echo "You need to login to openshift: "
  oc login `echo $OPENSHIFT_URL`
  oc project aws-cloudcustodian
fi
echo "oc successfully switch to project aws-cloudcustodian"
./build_docker.sh
if [[ $? -ne 0 ]] ; then
  echo "\n\nFailed to tag the docker image.\n\n"
  exit 1
fi
echo "Tagging docker image  ..."
docker push $DOCKER_REGISTRY_URL/aws_tools/aws-cloudcustodian
echo "Pushing docker image  ..."
sed -i.bak -e s/{DOCKER_REGISTRY_URL}/$DOCKER_REGISTRY_URL/g openshift-template.yml
echo "Deploying to openshift..."
oc process -f openshift-template.yml | oc apply -f -
oc deploy aws-cloudcustodian --latest=true
sed -i.bak -e s/$DOCKER_REGISTRY_URL/'{DOCKER_REGISTRY_URL}'/g openshift-template.yml
rm openshift-template.yml.bak
