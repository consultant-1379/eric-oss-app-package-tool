#!/usr/bin/python
import docker
import itertools
import json
import logging
import os
import shutil
import sys
import tarfile
import tempfile
import fnmatch
import os.path
import yaml
from contextlib import contextmanager
from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool
from subprocess import Popen, PIPE, check_output

from helm_template import HelmTemplate
from image import Image

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader
from yaml import load, safe_load, dump, YAMLError, YAMLObject, Dumper
from datetime import datetime
import re

_DOCKER_SAVE_FILENAME = 'docker.tar'
REL_PATH_TO_HELM_CHART = 'OtherDefinitions/'
TAGGED_IMAGES = ' '

METADATA_KEYS = ['vnf_product_name',
                 'vnf_provider_id',
                 'vnf_package_version',
                 'vnf_release_date_time']
SOURCE = './'


def __set__command(helm, values, set_parameters, helm3, helm_debug):
    fullCommand = []
    helm_options = "--debug" if helm_debug else ""
    start_cmd = ('{} template {} {}'.format("helm3" if helm3 else "helm",
                                            helm_options,
                                            helm))
    fullCommand.append(start_cmd)
    if values:
        fullCommand.append(' --values ' + ','.join(values))
    if set_parameters:
        fullCommand.append(' --set ' + ','.join(set_parameters))
    if not set_parameters and not values and not helm3:
        logging.warning("""This is adding '--set ingress.hostname=a' to the helm template command, if you have not specified any set/values. 
                           This is now deprecated and will be removed.
                           If you rely on it please update your execution of the tool to add this set/value""")
        fullCommand.append(' --set ingress.hostname=a')
    return ''.join(fullCommand)


def __get_images(args):
    helm_chart_paths = get_charts(args)
    image_list = set()
    for chart in helm_chart_paths:
        command = __set__command(chart, args.values, args.set, args.helm3, args.helm_debug)
        logging.info('Command is: ' + str(command))
        helm_template = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        helm_template_output, err = helm_template.communicate()
        __parse_std_err_for_errors(err)
        image_list.update(__parse_helm_template(helm_template_output))
        if __images_in_scalar_values(helm_template_output):
            images_from_scalar_values = __handle_images_in_scalar_values(chart, args)
            if len(images_from_scalar_values) == 0:
                logging.warning(
                    "Could not parse the image urls from the values.yaml file at root of chart. Please check the logs below to ensure all images have been packaged into the csar")
            image_list.update(images_from_scalar_values)
    return image_list


def __parse_std_err_for_errors(err):
    if str(err):
        logging.warn('Std err was not empty: \n {0}'.format(str(err)))
        lines = err.splitlines()
        for line in lines:
            x = re.search('^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}|coalesce\.go:[0-9]*:) [W|w]arning', line)
            if x is None:
                raise EnvironmentError('Helm command failed with error message: {0}'.format(str(err)))


def __images_in_scalar_values(helm_template_output):
    """
    This method gets the "image:" lines from the helm template output and checks to see if any line contains {{
    :param helm_template_output:
    :return: True if the image tags contain {{
    """
    return [line for line in re.findall(".*image:.*", helm_template_output) if "{{" in line]


def get_charts(args):
    helm_chart_paths = []
    if args.helm_dir is not None:
        for root, directories, files in os.walk(args.helm_dir):
            for filepath in files:
                if '.tgz' in filepath:
                    helm_chart_paths.append(args.helm_dir + '/' + filepath)
    if args.helm is not None:
        for chart in args.helm:
            helm_chart_paths.append(chart)
    return helm_chart_paths

def __handle_images_in_scalar_values(helm_chart, args):
    logging.info(
        "Helm template contains images in a scalar value, will parse the values file for the remaining images")
    command = ("helm3 show values " + helm_chart) if args.helm3 else ("helm inspect values " + helm_chart)
    logging.info("Command is: " + command)
    helm_inspect = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    values, err = helm_inspect.communicate()
    if str(err):
        raise EnvironmentError('Helm command failed with error message: {0}'.format(str(err)))
    return __parse_values_file_for_images(values)


def __parse_values_file_for_images(values_file_contents):
    """
    This method will parse a values file which follows the ADP Helm Chart Design Rules and Guidelines
    https://confluence.lmera.ericsson.se/pages/viewpage.action?spaceKey=AA&title=Helm+Chart+Design+Rules+and+Guidelines
    Specifically rules: DR-HC-050 and DR-HC-101
    The values file is from an integration helm chart to DR-HC-050 should be nested under the name of the child chart
    Here follows an example of a values file which will be parsed correctly:
    ```
        global:
          registry:
            url: armdocker.rnd.ericsson.se
            pullSecret: armdocker
        eric-mesh-sidecar-injector:
          imageCredentials:
            repoPath: proj-adp-gs-service-mesh
            pullPolicy: IfNotPresent
            registry:
              url:
              #pullSecret:

          images:
            sidecar_injector:
              name: eric-mesh-sidecar-injector
              tag: 1.1.0-130
            proxy:
              name: eric-mesh-proxy
              tag: 1.1.0-130
            proxy_init:
              name: eric-mesh-proxy-init
              tag: 1.1.0-130
        eric-mesh-controller:
          imageCredentials:
            repoPath: proj-adp-gs-service-mesh
            pullPolicy: IfNotPresent
            registry:
              url:
              #pullSecret:

          images:
            pilot:
              name: eric-mesh-controller
              tag: 1.1.0-130
            proxy:
              name: eric-mesh-proxy
              tag: 1.1.0-130
            kubectl:
              name: eric-mesh-tools
              tag: 1.1.0-130
    ```

    :param values_file_contents: the contents of the values file from the integration helm chart
    :return: a list of Images
    """
    data = load(values_file_contents, Loader=Loader)
    global_root = data.get('global')
    if global_root is None:
        logging.warning("Could not find global in the values.yaml file")
        return set()
    registry = global_root.get('registry')
    if registry is None:
        logging.warning("Could not find global.registry.url in the values.yaml file")
        return set()
    global_registry_url = registry.get('url')
    if global_registry_url is None:
        logging.warning("Could not find global.registry.url in the values.yaml file")
        return set()
    logging.info("Global registry url is: " + global_registry_url)
    image_list = set()
    for key in data.keys():
        if key != 'global':
            sub_chart = data.get(key)
            if isinstance(sub_chart, dict):
                image_credentials = sub_chart.get('imageCredentials')
                if image_credentials is None:
                    logging.warning("Could not find imageCredentials in " + str(key))
                    continue
                repo_path = image_credentials.get('repoPath')
                if repo_path is None:
                    logging.warning("Could not find repoPath in " + str(key))
                    continue
                logging.info("Repo path is: " + repo_path)
                for sub_key in sub_chart.keys():
                    __look_for_images(global_registry_url, image_list, repo_path, sub_chart, sub_key)
            else:
                logging.warning("Could not find imageCredentials in " + str(key))
    return image_list


def __look_for_images(global_registry_url, image_list, repo_path, sub_chart, sub_key):
    """
    This method will parse the images section of a values file which follows the ADP Helm Chart Design Rules and Guidelines
    https://confluence.lmera.ericsson.se/pages/viewpage.action?spaceKey=AA&title=Helm+Chart+Design+Rules+and+Guidelines
    Specifically rules: DR-HC-050
    Here follows an example of a values file images section which will be parsed correctly:
    ```
    images:
      sidecar_injector:
        name: eric-mesh-sidecar-injector
        tag: 1.1.0-130
      proxy:
        name: eric-mesh-proxy
        tag: 1.1.0-130
      proxy_init:
        name: eric-mesh-proxy-init
        tag: 1.1.0-130
    ```

    :param global_registry_url: the parsed global registry url to be used
    :param image_list: the list of images to populate
    :param repo_path: the parsed repo path to be used
    :param sub_chart: the parent section of the values file
    :param sub_key: the key of the parent section of the values file
    :return: a list of images
    """
    if sub_key == 'images':
        images = sub_chart.get(sub_key)
        for images_key in images.keys():
            name = images.get(images_key).get('name')
            if name is None:
                logging.warning("Could not find name in " + images_key)
                continue
            repo = global_registry_url + '/' + repo_path + '/' + name
            tag = images.get(images_key).get('tag')
            if tag is None:
                logging.warning("Could not find tag in " + images_key)
                continue
            image = Image(repo=repo, tag=tag)
            logging.info('Repo is: ' + str(image))
            image_list.add(image)


def __parse_helm_template(helm_template):
    helm_template_obj = HelmTemplate(helm_template)
    return __extract_image_information(helm_template_obj.get_all_images())


def __extract_image_information(images):
    image_list = []
    for image in images:
        stripped = image.strip()
        if not stripped:
            continue
        split = stripped.split(':', 1)
        if len(split) > 1:
            __image = Image(repo=split[0], tag=split[1])
        else:
            __image = Image(repo=split[0])
        logging.info('Repo is: ' + __image.__str__())
        image_list.append(__image)
    return image_list


def __pull_images(images):
    logging.info('Pulling the images')
    pool = ThreadPool(cpu_count())
    pool.map(__pull, images)
    pool.close()
    pool.join()
    logging.info('Images pulled')


def __pull(image):
    client = docker.from_env(timeout=int(600))
    logging.info("Pulling {0}".format(image.__str__()))
    client.images.pull(repository=image.repo, tag=image.tag)
    client.close()

def __tag_images(images, tagged_images):
    client = docker.from_env(timeout=int(600))
    for image in images:
        if "/" in image.repo:
            images_less_repo = re.sub('^(.*?/)',"", image.repo,1)
            client.images.get(image.repo +':' + image.tag).tag(images_less_repo +':' + image.tag)
            tagged_images += ' ' + images_less_repo +':'+ image.tag
        else:
            tagged_images += ' ' + image.repo +':'+ image.tag
    logging.info("List of Re-tagged images : "  + str(tagged_images))
    client.close()
    return tagged_images


def __save_images_to_tar(images, docker_save_filename):
    logging.info('Saving images to tar')
    save = Popen('docker save -o ' + docker_save_filename + ' ' + images, shell=True, stdin=PIPE, stdout=PIPE,
                 stderr=PIPE)
    output, err = save.communicate()
    if str(err):
        logging.error('docker save command failed')
        logging.error('message is: ' + str(err))
        sys.exit(str(err))
    logging.debug('Std Out: ' + str(output))
    size = Popen('ls -lh ' + docker_save_filename, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, err = size.communicate()
    logging.info('Status of docker tar file: ' + str(output))
    if str(err):
        logging.error('Std Err: ' + str(err))


def create_docker_tar(args):
    logging.debug('Helm chart: ' + str(args.helm))
    images = __get_images(args)
    __pull_images(images)
    tagged_images = __tag_images(images, TAGGED_IMAGES)
    __save_images_to_tar(tagged_images, _DOCKER_SAVE_FILENAME)
    return _DOCKER_SAVE_FILENAME


def create_source(args):
    # TODO if this is executed concurrently the source folder will get corrupted. Make the source folder unique.
    # but that brings it's own challenges. cleaning up!
    logging.info("Checking source folder for CSAR and files")
    path_to_chart_in_source = SOURCE + REL_PATH_TO_HELM_CHART + 'ASD'
    try:
        os.makedirs(SOURCE)
        os.makedirs(SOURCE + 'Definitions')
    except OSError:
        logging.info('Validating Definitions folder')
    try:
        os.makedirs(path_to_chart_in_source)
    except OSError:
        logging.info('Validating ASD folder')
    if args.definitions:
        if os.path.isdir(args.definitions):
            files = [f for f in os.listdir(args.definitions) if os.path.isfile(os.path.join(args.definitions, f))]
            for filename in files:
                shutil.copy(os.path.join(args.definitions, filename), SOURCE + 'OtherDefinitions/ASD')
        else:
            shutil.copy(args.definitions, SOURCE + 'Definitions')
    if args.scripts:
        shutil.copytree(args.scripts, SOURCE + 'Scripts')
    if args.helm is not None:
        for helm in args.helm:
            shutil.copy(helm, path_to_chart_in_source)
    if args.helm_dir is not None:
        for root, directories, files in os.walk(args.helm_dir):
            for filepath in files:
                if '.tgz' in filepath:
                    if os.path.exists(path_to_chart_in_source + '/' + filepath):
                        os.path.isfile(path_to_chart_in_source + '/' + filepath)
                    else:
                        shutil.copy(args.helm_dir + '/' + filepath, path_to_chart_in_source)
    if args.scale_mapping is not None:
        shutil.copy(args.scale_mapping, path_to_chart_in_source)


def __create_images_section(docker_file):
    try:
        os.makedirs(SOURCE + 'OtherDefinitions/ASD')
        os.makedirs(SOURCE + 'OtherDefinitions/ASD/images')
    except OSError:
        logging.info('Validating images folder')
    try:
        os.makedirs(SOURCE + 'OtherDefinitions/ASD/Images')
    except OSError:
        logging.info('Validating ASD Images folder')
    shutil.move(docker_file, os.path.join(SOURCE + REL_PATH_TO_HELM_CHART + 'ASD/Images/', _DOCKER_SAVE_FILENAME))

def __empty_images_section():
    logging.info('Checking image selection')
    try:
        os.makedirs(SOURCE + 'OtherDefinitions/ASD')
        os.makedirs(SOURCE + 'OtherDefinitions/ASD/Images')
    except OSError:
        logging.info('Validating Images folder')
    open(SOURCE + 'OtherDefinitions/ASD/Images/images.txt', 'w').close()


def delete_source():
    logging.info("Deleting source folder")
    shutil.rmtree(SOURCE, ignore_errors=True, onerror=None)


def create_path(arg_to_check, path_in_source):
    if arg_to_check:
        shutil.copy(arg_to_check, SOURCE + path_in_source)
        return path_in_source + os.path.basename(arg_to_check)
    else:
        return ''


def __create_images_txt_file(docker_file):
    with tarfile.open(docker_file) as tf:
        manifest = tf.extractfile('manifest.json')
        if manifest is None:
            raise FileNotFoundError('manifest.json')
        data = json.loads(manifest.read())
        images = itertools.chain.from_iterable([image['RepoTags'] for image in data])
    entry1 = open(SOURCE + 'Metadata/images.txt', 'w')
    entry1.write('\n'.join(images))
    entry1.close()


def get_vnfd(args):
    tosca_file = 'Metadata/Tosca.meta'
    metadata_folder = SOURCE + 'Metadata'
    definitions_folder = SOURCE + 'Definitions'
    if os.path.exists(definitions_folder):
        logging.info("Checking Definitions folder")
    else:
        os.makedirs(SOURCE + 'Definitions')
        logging.info("Definitions folder created")
    if os.path.exists(metadata_folder):
        logging.info("Checking Metadata folder")
    else:
        os.makedirs(SOURCE + 'Metadata')
        logging.info("Metadata folder created")
    if args.vnfd:
        if os.path.exists(SOURCE + tosca_file):
            logging.info("Checking Tosca " + args.vnfd + " to " + SOURCE + tosca_file )
        else:
            logging.info("Copying Tosca file from input path.")
            shutil.copy(args.vnfd, SOURCE + tosca_file)
        vnfd_file_name = ('Metadata/' + os.path.basename(args.vnfd))
    else:
        tosca_file = 'Definitions/AppDescriptor.yaml'
        logging.info("Checking placeholder Tosca yaml")
        entry = open(SOURCE + tosca_file, 'w')
        entry.write('template base file')
        entry.close()
        vnfd_file_name = tosca_file 
    if args.vnfd:
        tosca_path = validate_tosca(args)
        yaml_path = validate_yaml(args)
    return vnfd_file_name

def validate_tosca(args):
    tosca_meta_file_name = SOURCE + 'Metadata/Tosca.meta'
    logging.debug("Check if Tosca.meta required " + tosca_meta_file_name )
    if args.vnfd is not None:
        file_name = tosca_meta_file_name
        if os.path.exists(file_name):
            with open(file_name, 'r') as parse_file:
                check_elements = yaml.safe_load(parse_file)
                check_elements['CSAR-Version']
                check_elements['Created-By']
                entry_definitions = check_elements['Entry-Definitions']  # AppDescriptor.yaml
                check_elements['Entry-Definitions']
                check_elements['Entry-OtherDefinitions']
                check_elements['TOSCA-Meta-File-Version']
                logging.debug("Tosca.meta validated.")
        else:
            logging.debug("Tosca.meta not validated. " + file_name)

def validate_yaml(args):
    legacyAppComponentName = 'APPComponent'
    appComponentName = 'AppComponentList'
    file_name = SOURCE + 'Metadata/Tosca.meta'
    with open(file_name, 'r') as parse_file:
        check_elements = yaml.safe_load(parse_file)
        entry_definitions = check_elements['Entry-Definitions']  # AppDescriptor.yaml
    app_descriptor_file_name = SOURCE + entry_definitions
    app_service_file_name = SOURCE + 'OtherDefinitions/ASD/ASD.yaml'
    validation = 'test'
    if args.vnfd is not None:
        file_name = app_descriptor_file_name
        if os.path.exists(app_descriptor_file_name):
            try:
                config = yaml.safe_load(file(app_descriptor_file_name, 'r'))
                logging.info(file_name + " syntax passed, checking structure.")
            except yaml.YAMLError, exc:
                print "Error in configuration file:", exc
                raise ValueError("Validation failure: " + app_descriptor_file_name)
            try:
                with open(app_descriptor_file_name, 'r') as yaml_file:
                    check_elements = yaml.safe_load(yaml_file)
                    check_elements['Description of an APP']['APPName']
                    check_elements['Description of an APP']['APPVersion']
                    check_elements['Description of an APP']['APPType']
                    if appComponentName in check_elements:
                        if isinstance(check_elements[appComponentName], list):
                            for appComponent in check_elements[appComponentName]:
                                appComponent['NameofComponent']
                                appComponent['Version']
                                app_service_file_name = SOURCE + appComponent['Path']
                                appComponent['ArtefactType']
                                if app_service_file_name[-5:] == ".yaml":
                                    validation = validate_asd_file(app_service_file_name)
                                else:
                                    dir_name = app_service_file_name
                                    if os.path.isdir(dir_name):
                                        if not os.listdir(dir_name):
                                            logging.info(dir_name + " is empty.")
                                            raise ValueError("Directory " + dir_name + " is empty.")
                                        else:
                                            logging.info(dir_name + " is not empty.")
                                    else:
                                        logging.info(dir_name + " not found.")
                                        raise ValueError("Please check location " + dir_name)
                        else:
                            check_elements[appComponentName]['NameofComponent']
                            check_elements[appComponentName]['Version']
                            app_service_file_name = SOURCE + check_elements[appComponentName]['Path']
                            check_elements[appComponentName]['ArtefactType']
                            validation = validate_asd_file(app_service_file_name)
                    elif legacyAppComponentName in check_elements:
                        check_elements[legacyAppComponentName]['NameofComponent']
                        check_elements[legacyAppComponentName]['Version']
                        app_service_file_name = SOURCE + check_elements[legacyAppComponentName]['Path']
                        check_elements[legacyAppComponentName]['ArtefactType']
                        validation = validate_asd_file(app_service_file_name)
                    else:
                        logging.info("AppDescriptor file does not have field value 'APPComponent' or 'AppComponentList'.")
                        raise ValueError("Validation failure: AppDescriptor file does not have field value 'APPComponent' or 'AppComponentList'. ")
            except ImportError:
                    logging.info(file_name + " validation failed.")
        else:
            logging.info(app_descriptor_file_name + " not found.")
            raise ValueError("Validation failure " + app_descriptor_file_name)
    else:
        logging.info(file_name + " not found.")
        raise ValueError("Check file " + file_name)
    return validation

def validate_asd_file(app_service_file_name):
    file_name = app_service_file_name
    if os.path.exists(file_name):
        try:
            config = yaml.safe_load(file(file_name, 'r'))
            logging.info(file_name + " syntax passed, checking structure.")
        except yaml.YAMLError, exc:
            print "Error in configuration file:", exc
            raise ValueError("Validation failure " + file_name)
        try:
            with open(file_name, 'r') as yaml_file:
                check_elements = yaml.safe_load(yaml_file)
                check_elements['asdId']
                check_elements['asdSchemaVersion']
                check_elements['asdProvider']
                check_elements['asdApplicationName']
                check_elements['asdApplicationVersion']
                check_elements['deploymentItems']['deploymentItemId']
                check_elements['deploymentItems']['artifactId']
                validation = 'test'
        except ImportError:
            logging.info(file_name + " validation failed.")
    else:
        logging.info(file_name + " not found.")
        raise ValueError("Please check location " + file_name)
    return validation

def check_digest(args):
    if args.sha512 and (args.manifest or args.values_csar):
        return "SHA-512"
    else:
        return ""


def create_manifest_file(args):
    '''Create manifest file from given arguments
    '''
    values_csar_dict = {}
    with open(args.values_csar) as source:
        values_csar_dict = safe_load(source)
    ret = "metadata:\n"
    for key in METADATA_KEYS:
        if key == "vnf_release_date_time":
            ret += "%s: %s\n" % (key, datetime.now().isoformat())
        else:
            ret += "%s: %s\n" % (key, values_csar_dict[key])
    mf = "TOSCA.mf"
    if args.vnfd:
        vnfd_name = str(args.vnfd).rsplit('.', 1)[0]
        mf = vnfd_name + ".mf"
        logging.debug("vnfd if. Debug mf=" + mf + " vnfd_name=" + vnfd_name )
    if args.tosca:
        vnfd_name = str(args.vnfd).rsplit('.', 1)[0]
        mf = vnfd_name + ".mf"
        logging.debug("tosca if. Debug mf=" + mf + " vnfd_name=" + vnfd_name )
    with open(SOURCE + mf, 'w') as fp:
        fp.write(ret)
    return mf
