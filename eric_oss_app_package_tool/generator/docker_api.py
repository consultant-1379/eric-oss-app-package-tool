'''Docker API'''

from base64 import b64decode
import json
import os
import logging
import requests


API_MANIFEST = "https://{server}/v2/{path}/manifests/{version}"
API_BLOB = "https://{server}/v2/{path}/blobs/{digest}"


class DockerError(Exception):
    '''Docker Exception'''
    pass


# pylint: disable=too-few-public-methods
class DockerConfig(object):
    '''Docker configuration'''
    def __init__(self, config_path):
        self.config = self.parse_config(config_path)

    @staticmethod
    def parse_config(config_path):
        '''Parse Docker configuration file'''
        with open(os.path.join(config_path, "config.json"), "r") as conf_file:
            return json.loads(conf_file.read())

    def get_credentials(self, server_url):
        '''Get credentials tuple for a given server'''
        credentials = self.config["auths"].get(server_url)
        if not credentials:
            raise KeyError("Credentials for server '{}'"
                           "not found".format(server_url))

        return tuple(b64decode(credentials["auth"]).split(":"))


# pylint: disable=too-few-public-methods
class DockerApi(object):
    '''Docker API v2 client'''
    def __init__(self, docker_config_path, timeout=15):
        self.docker_config = DockerConfig(docker_config_path)
        self.timeout = timeout

    def get_labels(self, image_path):
        '''Return labels dictionary for an image'''
        path_components = image_path.split("/")

        # Split image URL to separate variables e.g. <server>/<path>/<image>:<version>
        server = path_components[0]
        path, version = "/".join(path_components[1:]).split(":")

        credentials = self.docker_config.get_credentials(server)
        try:
            manifest = requests.get(
                API_MANIFEST.format(server=server,
                                    path=path,
                                    version=version),
                auth=credentials,
                headers={
                    "Accept":
                    "application/vnd.docker.distribution.manifest.v2+json"
                },
                timeout=self.timeout
            )
            manifest.raise_for_status()
            digest = manifest.json()["config"]["digest"]
            media_type = manifest.json()["config"]["mediaType"]

            blob = requests.get(API_BLOB.format(server=server,
                                                path=path,
                                                digest=digest),
                                auth=credentials,
                                headers={"Accept": media_type},
                                timeout=self.timeout)
            return blob.json()["config"]["Labels"] or {}
        except (requests.exceptions.RequestException, KeyError) as exc:
            logging.error("Could not get labels for %s (%s)", image_path, exc)
            raise DockerError("Failed to get image labels for {}".format(image_path))
