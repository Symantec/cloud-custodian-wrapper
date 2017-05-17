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
/custodian/deploy/build_docker.sh
if [[ $? -ne 0 ]] ; then
  echo "Failed to tag the docker image."
  exit 1
fi
docker push $DOCKER_REGISTRY_URL/aws_tools/aws-cloudcustodian
if [[ $? -ne 0 ]] ; then
  echo "Failed to push the docker image to the registry."
  exit 1
fi
echo "Pushing docker image  ..."
sed -i.bak -e s/{DOCKER_REGISTRY_URL}/$DOCKER_REGISTRY_URL/g /custodian/deploy/openshift_template.yml
echo "Deploying to openshift..."
oc process -f /custodian/deploy/openshift_template.yml | oc apply -f -
if [[ $? -ne 0 ]] ; then
  echo "oc process -f /custodian/deploy/openshift_template.yml | oc apply -f - HAS FAILED"
  exit 1
fi
oc deploy aws-cloudcustodian --latest=true
if [[ $? -ne 0 ]] ; then
  echo "oc deploy aws-cloudcustodian --latest=true HAS FAILED"
  exit 1
fi
sed -i.bak -e s/$DOCKER_REGISTRY_URL/'{DOCKER_REGISTRY_URL}'/g /custodian/deploy/openshift_template.yml
rm /custodian/deploy/openshift_template.yml.bak
echo ""
echo "Successfully deployed your docker image to openshift, `echo $OPENSHIFT_URL`/console/project/aws-cloudcustodian/overview?main-tab=openshiftConsole%2Foverview"
