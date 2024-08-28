import argparse
import os
import shutil
import pytest
from mock import patch
import logging

from eric_oss_app_package_tool.generator import generate, product_report
from eric_oss_app_package_tool.generator.image import Image

ROOT_DIR = os.path.abspath(os.path.join((os.path.abspath(__file__)), os.pardir))
RESOURCES = os.path.abspath(os.path.join(ROOT_DIR, os.pardir, 'resources'))
images = ["armdocker.rnd.ericsson.se/proj-orchestration-so/api-gateway:1.0.0-31",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/dashboard:1.0.2-3",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/eai-adapter:1.0.0-82",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/ecm-adapter:1.0.0-40",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/ecm-stub:1.0.0-26",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/engine:1.0.6-29",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/enm-adapter:1.0.0-61",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/enm-stub:1.0.0-42",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/eso-security:1.0.0-15",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/eso-workflow:1.0.0-36",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/onboarding:1.0.0-14",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/orchestration-gui:18.0.0-53",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/orchestrationcockpit:1.0.1-65",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/subsystems-manager:1.0.1-51",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/topology:1.0.1-33",
          "armdocker.rnd.ericsson.se/proj-orchestration-so/tosca:1.1.0",
          "dl360x3425.ete.ka.sw.ericsson.se:5000/sdpimages/eric-ec-sdp:1.0.0-090121"]


mock_args = argparse.Namespace(docker_config="", helm3=True, helm_debug=False)


def test_split_images_no_empty_lines():
    image_list = generate.__extract_image_information(images)
    assert len(image_list) == 17


def test_split_images_no_empty_information():
    image_list = generate.__extract_image_information(images)
    for image in image_list:
        assert len(image.repo) != 0
        assert len(image.tag) != 0


def test_images_with_no_tags():
    images = ["armdocker.rnd.ericsson.se/proj-orchestration-so/eso-security:1.0.0-15",
              "armdocker.rnd.ericsson.se/proj-orchestration-so/eso-workflow",
              "armdocker.rnd.ericsson.se/proj-orchestration-so/onboarding:1.0.0-14"]
    image_list = generate.__extract_image_information(images)
    tags = []
    for image in image_list:
        tags.append(image.tag)
    tags.remove("latest")
    assert len(tags) == 2


def test_create_path():
    test_string = generate.create_path('', 'a_destination')
    assert test_string == ''


def test_check_digest_with_manifest():
    true_sha_and_manifest = argparse.Namespace(sha512=True, manifest='aManifest', values_csar='')
    assert generate.check_digest(true_sha_and_manifest) == 'SHA-512'


def test_check_digest_with_values_csar():
    true_sha_and_values_csar = argparse.Namespace(sha512=True, manifest='', values_csar='aValuesCsar')
    assert generate.check_digest(true_sha_and_values_csar) == 'SHA-512'


def test_check_digest_without_manifest_and_values_csar():
    true_sha_only = argparse.Namespace(sha512=True, manifest='', values_csar='')
    assert generate.check_digest(true_sha_only) == ''


def test_check_digest_false_sha():
    true_sha_and_manifest = argparse.Namespace(sha512=False, manifest='')
    assert generate.check_digest(true_sha_and_manifest) == ''


expected_images = [
    Image(repo='armdocker.rnd.ericsson.se/proj-adp-gs-service-mesh/eric-mesh-controller', tag='1.1.0-130'),
    Image(repo='armdocker.rnd.ericsson.se/proj-adp-gs-service-mesh/eric-mesh-certificate-mgr-agent', tag='1.1.0-130'),
    Image(repo='armdocker.rnd.ericsson.se/proj-adp-gs-service-mesh/eric-mesh-certificate-mgr', tag='1.1.0-130'),
    Image(repo='armdocker.rnd.ericsson.se/proj-adp-gs-service-mesh/eric-mesh-sidecar-injector', tag='1.1.0-130'),
    Image(repo='armdocker.rnd.ericsson.se/proj-adp-gs-service-mesh/eric-mesh-proxy', tag='1.1.0-130'),
    Image(repo='armdocker.rnd.ericsson.se/proj-adp-gs-service-mesh/eric-mesh-tools', tag='1.1.0-130'),
    Image(repo='armdocker.rnd.ericsson.se/proj-adp-gs-service-mesh/eric-mesh-proxy-init', tag='1.1.0-130')]


def test_images_from_values_file():
    with open(os.path.join(RESOURCES, "values.yaml"), "r") as values:
        image_list = generate.__parse_values_file_for_images(values.read())
    assert len(image_list) == len(expected_images)
    assert all(elem in expected_images for elem in image_list)


def test_images_from_values_file_no_global():
    with open(os.path.join(RESOURCES, "values_no_global.yaml"), "r") as values:
        image_list = generate.__parse_values_file_for_images(values.read())
    assert len(image_list) == 0


def test_images_from_values_file_no_global_registry():
    with open(os.path.join(RESOURCES, "values_no_global_registry.yaml"), "r") as values:
        image_list = generate.__parse_values_file_for_images(values.read())
    assert len(image_list) == 0


def test_images_from_values_file_no_global_registry_url():
    with open(os.path.join(RESOURCES, "values_no_global_registry_url.yaml"), "r") as values:
        image_list = generate.__parse_values_file_for_images(values.read())
    assert len(image_list) == 0


def test_images_from_values_file_no_image_credentials():
    with open(os.path.join(RESOURCES, "values_no_image_credentials.yaml"), "r") as values:
        image_list = generate.__parse_values_file_for_images(values.read())
    assert len(image_list) == 0


def test_images_from_values_file_no_repo_path():
    with open(os.path.join(RESOURCES, "values_no_repo_path.yaml"), "r") as values:
        image_list = generate.__parse_values_file_for_images(values.read())
    assert len(image_list) == 0


def test_images_from_values_file_no_image_name():
    with open(os.path.join(RESOURCES, "values_no_name.yaml"), "r") as values:
        image_list = generate.__parse_values_file_for_images(values.read())
    assert len(image_list) == 0


def test_images_from_values_file_no_image_tag():
    with open(os.path.join(RESOURCES, "values_no_tag.yaml"), "r") as values:
        image_list = generate.__parse_values_file_for_images(values.read())
    assert len(image_list) == 0


yaml_parsing_expected_images = [
    Image(repo='armdocker.rnd.ericsson.se/proj-am/releases/eric-am-onboarding-service', tag='stable'),
    Image(repo='armdocker.rnd.ericsson.se/proj-am/releases/eric-am-common-wfs', tag='1.0.174-1'),
    Image(repo='armdocker.rnd.ericsson.se/proj-orchestration-so/bro-agent-fm', tag='bfh54fg4'),
    Image(repo='armdocker.rnd.ericsson.se/proj-am/sles/sles-pg10', tag='latest'),
    Image(repo='armdocker.rnd.ericsson.se/proj-orchestration-so/keycloak-client', tag='latest')]


def test_images_from_helm_template_valid_template():
    with open(os.path.join(RESOURCES, "helm_templates/valid_template.yaml"), "r") as helm_template:
        image_list = generate.__parse_helm_template(helm_template.read())
    assert len(image_list) == 5
    assert all(elem in yaml_parsing_expected_images for elem in image_list)


def test_images_from_helm_template_with_duplicates():
    with open(os.path.join(RESOURCES, "helm_templates/valid_template_with_duplicate_images.yaml"),
              "r") as helm_template:
        image_list = generate.__parse_helm_template(helm_template.read())
    assert len(image_list) == 5
    assert all(elem in yaml_parsing_expected_images for elem in image_list)


def test_images_in_scalar_values_check():
    with open(os.path.join(RESOURCES, "helm_templates/valid_template_with_images_in_scalars.yaml"),
              "r") as helm_template:
        assert generate.__images_in_scalar_values((helm_template.read())) is not None


def test_empty_images_section_generation():
    generate.__empty_images_section()
    count = 0
    for root, subdirs, files in os.walk('OtherDefinitions'):
        for filename in files:
            count += 1
            assert filename == 'images.txt'
    assert count != 0
    shutil.rmtree('OtherDefinitions')


std_err_warn_helm2 = "2020/08/17 11:47:17 Warning: Merging destination map for chart 'eric-sec-admin-user-management'. " \
               "The destination item 'tls' is a table and ignoring the source 'tls' as it has a non-table value of: <nil>\n" \
               "2020/08/17 11:47:17 Warning: Merging destination map for chart 'eric-sec-admin-user-management'. " \
               "The destination item 'tls' is a table and ignoring the source 'tls' as it has a non-table value of: <nil>\n" \
               "2020/08/17 11:47:17 warning: Merging destination map for chart 'eric-sec-admin-user-management'. " \
               "The destination item 'tls' is a table and ignoring the source 'tls' as it has a non-table value of: <nil>\n"

std_err_err_helm2 = "2020/08/17 11:47:17 Error: Merging destination map for chart 'eric-sec-admin-user-management'. " \
              "The destination item 'tls' is a table and ignoring the source 'tls' as it has a non-table value of: <nil>\n"

st_err_warn_helm3 = "coalesce.go:160: warning: skipped value for fh: Not a table."

std_err_err_helm3 = "Error: template: eric-eea-int-helm-chart/charts/eric-log-shipper/templates/filebeat-serviceaccount.yaml:1:14: executing \"eric-eea-int-helm-chart/charts/eric-log-shipper/templates/filebeat-serviceaccount.yaml\" at <.Values.rbac.createServiceAccount>: can't evaluate field createServiceAccount in type interface {}"


def test__parse_std_err_for_errors_should_pass_helm2():
    generate.__parse_std_err_for_errors(std_err_warn_helm2)


def test__parse_std_err_for_errors_should_raise_exception_helm2():
    with pytest.raises(EnvironmentError):
        generate.__parse_std_err_for_errors(std_err_err_helm2)


def test__parse_std_err_for_errors_should_pass_helm3():
    generate.__parse_std_err_for_errors(st_err_warn_helm3)


def test__parse_std_err_for_errors_should_raise_exception_helm3():
    with pytest.raises(EnvironmentError):
        generate.__parse_std_err_for_errors(std_err_err_helm3)

'''
@patch('eric_oss_app_package_tool.generator.docker_api.DockerConfig.parse_config')
@patch('eric_oss_app_package_tool.generator.product_report.HelmChart._extract_image_metadata_from_image')
def test_get_component_metadata_with_ok_chart_and_ok_epi(docker, parse_config):
    docker.return_value = \
       {'image': 'armdocker.rnd.ericsson.se/proj-common-assets-cd/security/eric-sec-sip-tls-crd-job:2.8.0-35',
         'product_number': 'CXC1742971',
         'product_version': '2.8.0',
         'image_name': 'eric-sec-sip-tls-crd-job',
         'image_tag': '2.8.0-35'}

    path = os.path.join(RESOURCES, "helmdirs/eric-sec-sip-tls-crd")
    helm = product_report.HelmChart(path, "", "eric-sec-sip-tls-crd", mock_args, include_report=True)
    charts, images = helm.get_components()
    assert len(charts) == 1
    assert len(images) == 1
    assert {'chart_name': 'eric-sec-sip-tls-crd',
            'chart_version': '2.8.0+35',
            'product_version': '2.8.0',
            'product_number': 'CXC1742970',
            'package': 'eric-sec-sip-tls-crd'} in charts

    assert {'image': 'armdocker.rnd.ericsson.se/proj-common-assets-cd/security/eric-sec-sip-tls-crd-job:2.8.0-35',
            'product_number': 'CXC1742971',
            'product_version': '2.8.0',
            'image_name': 'eric-sec-sip-tls-crd-job',
            'image_tag': '2.8.0-35'} in images

'''

'''
@patch('eric_oss_app_package_tool.generator.docker_api.DockerConfig.parse_config')
@patch('eric_oss_app_package_tool.generator.product_report.HelmChart._extract_image_metadata_from_image')
def test_get_component_metadata_with_ok_epi_and_ok_integration_helm_chart(docker, parse_config):
    path = os.path.join(RESOURCES, "helmdirs/eric-cloud-native-base")

    expected = [
        {'image': 'armdocker.rnd.ericsson.se/proj-common-assets-cd-released/control/cm/eric-cm-mediator/eric-cm-mediator-init-container:7.6.0-11',
         'image_tag': '7.6.0-11',
         'product_version': '7.6.0',
         'product_number': 'CXU1010357',
         'image_name': 'eric-cm-mediator-init-container'},
        {'image': 'armdocker.rnd.ericsson.se/proj-common-assets-cd-released/control/cm/eric-cm-mediator/eric-cm-mediator:7.6.0-11',
         'image_tag': '7.6.0-11',
         'product_version': '7.6.0',
         'product_number': 'CXC2011452',
         'image_name': 'eric-cm-mediator'},
        {'image': 'armdocker.rnd.ericsson.se/proj-common-assets-cd-released/control/cm/eric-cm-mediator/eric-cm-key-init:7.6.0-11',
         'image_tag': '7.6.0-11',
         'product_version': '7.6.0',
         'product_number': 'CXC1742649',
         'image_name': 'eric-cm-key-init'},
        {'image': 'armdocker.rnd.ericsson.se/proj-adp-eric-ctrl-bro-drop/eric-ctrl-bro:4.7.0-23',
         'image_tag': '4.7.0-23',
         'product_version': '4.7.0',
         'product_number': 'CXC2012182',
         'image_name': 'eric-ctrl-bro'}
    ]
    docker.side_effect = expected

    helm = product_report.HelmChart(path, "", "eric-cloud-native-base", mock_args, include_report=True)
    charts, images = helm.get_components()
    assert len(charts) == 1
    assert len(images) == 4

    assert {'chart_name': 'eric-cloud-native-base',
            'chart_version': '1.50.0',
            'product_version': '1.0.0',
            'product_number': 'CXD101001',
            'package': 'eric-cloud-native-base'} in charts

    for image in expected:
        assert image in images
'''

'''

@patch('eric_oss_app_package_tool.generator.docker_api.DockerConfig.parse_config')
@patch('eric_oss_app_package_tool.generator.product_report.HelmChart._extract_image_metadata_from_image')
def test_get_component_metadata_with_no_helm_charts(DockerApi, parse_config):
    path = os.path.join(RESOURCES, "no_helm_charts")
    helm = product_report.HelmChart(path, "", "", mock_args, include_report=True)
    charts, images = helm.get_components()
    assert len(charts) == 1
    assert len(images) == 0
    assert {'chart_name': '',
            'chart_version': '',
            'product_version': '',
            'product_number': '',
            'package': ''} in charts
'''
