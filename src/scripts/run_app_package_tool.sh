#!/usr/bin/env bash

set -e

mkdir -p $HOME/logs
LOGFILE="$(date +"%Y_%m_%d_%I_%M_%p").txt"

echolog()
{
echo $1
echo $1 >> $HOME/logs/$LOGFILE
}

usage()
{
  echo "  Usage: $0 [-c Chart Path] [-d Directory Path] [-i Image Path] [-n name] [-o Output]"
  echo "  -c The Path to the helm chat been packaged"
  echo "  -d The Path to the predefined directory containing Definitions, OtherDefinitions, TOSCA-Metadata"
  echo "  -i The Path to docker tar containing the images required for the passed chart"
  echo "  -n Name of CSAR that will be produced"
  echo "  -o Output locating for CSAR that will be produced"
  exit 1
}

while getopts ":c:d:i:n:o:" option
do
case "${option}"
in
c) CHART_PATH=${OPTARG};;
d) DIR_PATH=${OPTARG};;
i) IMAGE_PATH=${OPTARG};;
n) NAME=${OPTARG};;
o) OUTPUT=${OPTARG};;
\?)
  echolog "Invalid option: -$OPTARG" >&2
  usage
  exit 1;;
:)
  echolog "Option -$OPTARG requires an argument." >&2
  usage
  exit 1;;
*)
  echolog "Unimplemented option: -$OPTARG"
  usage
  exit 1;;
esac
done

if ((OPTIND == 1))
then
    echolog "No options specified"
    usage
    exit 1
fi

shift $((OPTIND - 1))

if [[ -z ${DIR_PATH+x} || ${DIR_PATH} == -* ]]; then
    echolog "Directory path needs to be provided"
    usage
    exit 1
fi

if [[ -z ${NAME+x} || ${NAME} == -* ]]; then
    echolog "Name of CSAR needs to be provided"
    usage
    exit 1
fi

if [[ -z ${CHART_PATH+x} || ${CHART_PATH} == -* ]]; then
    echolog "Path to helm chart needs to be provided"
    usage
    exit 1
fi

if [[ -z ${IMAGE_PATH+x} || ${IMAGE_PATH} == -* ]]; then
    echolog "Path to docker.tar images needs to be provided"
    usage
    exit 1
fi
if [[ -z ${OUTPUT+x} || ${OUTPUT} == -* ]]; then
    echolog "Output location for generate CSAR needs to be provided"
    usage
    exit 1
fi

#Clean earlier csar
sudo rm -rf ${OUTPUT}*csar
sudo chmod +rwx ${OUTPUT}

docker run --rm \
       -v "$OUTPUT":/target \
       -v "$HOME"/.docker:/root/.docker \
       -v /var/run/docker.sock:/var/run/docker.sock \
       -v "$DIR_PATH":/home \
       -v "${IMAGE_PATH}":/build \
       -w /target \
       armdocker.rnd.ericsson.se/proj-am/snapshots/eric-am-package-manager:2.35.0-SNAPSHOT-6991991 \
       generate --helm /build/"${NAME}" --vnfd /home/AppDescriptor.yaml --images /build/docker.images.tar -d /home/ASD --name "${NAME}" --helm3

echo "Files:"
ls -lah ${OUTPUT}
