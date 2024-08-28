import os

import pytest
import argparse
from eric_oss_app_package_tool.cli import __main__

ROOT_DIR = os.path.abspath(os.path.join((os.path.abspath(__file__)), os.pardir))
HELM = os.path.join(ROOT_DIR, os.pardir, 'resources', 'helm')
EMPTY_HELM_DIR = os.path.join(ROOT_DIR, os.pardir, 'resources', 'no_helm_charts')
SCRIPTS = os.path.join(ROOT_DIR, os.pardir, 'resources', 'script')
VNFD = os.path.join(ROOT_DIR, os.pardir, 'resources', 'acceptance.yaml')
MF = os.path.join(ROOT_DIR, os.pardir, 'resources', 'acceptance.mf')
KEY = os.path.join(ROOT_DIR, os.pardir, 'resources', 'key')
VALUES_CSAR = os.path.join(ROOT_DIR, os.pardir, 'resources', 'values_csar.yaml')
VALUES_CSAR_INVALID = os.path.join(ROOT_DIR, os.pardir, 'resources', 'values_csar_invalid.yaml')
DEF_DIR = os.path.join(ROOT_DIR, os.pardir, 'resources', 'definitions')
DEF_FILE = os.path.join(DEF_DIR, 'types-definitions.yaml')
REPORT_OUT= os.path.join(ROOT_DIR, 'product-report.yaml')

def test_main(capsys):
    with pytest.raises(SystemExit):
        args = __main__.parse_args(['generate', '-h'])
        args.func(args)
    out, err = capsys.readouterr()
    assert out.startswith('usage:')


def test_check_arguments_no_valid_helm():
    with pytest.raises(ValueError) as output:
        invalid_helm_arg = argparse.Namespace(helm=["non_existent"], helm_dir=None)
        __main__.__check_arguments(invalid_helm_arg)
    assert str(output.value) == "The specified helm chart, non_existent, doesn't exist"

def test_check_arguments_no_helm_charts_in_directory():
    with pytest.raises(ValueError) as output:
        invalid_helm_arg = argparse.Namespace(helm_dir=EMPTY_HELM_DIR, helm=None)
        __main__.__check_arguments(invalid_helm_arg)
    assert str(output.value) == "The specified directory does not contain any helm charts"


def test_check_arguments_helm_charts_not_directory():
    with pytest.raises(ValueError) as output:
        invalid_helm_arg = argparse.Namespace(helm_dir=HELM, helm=None)
        __main__.__check_arguments(invalid_helm_arg)
    assert str(output.value) == "The specified helm directory is not a directory"


def test_check_arguments_multiple_helm_charts():
    with pytest.raises(ValueError) as output:
        invalid_helm_arg = argparse.Namespace(helm=[HELM, 'non_existent'], helm_dir=None)
        __main__.__check_arguments(invalid_helm_arg)
    assert str(output.value) == "The specified helm chart, non_existent, doesn't exist"

def test_check_arguments_no_valid_scale_mapping():
    with pytest.raises(ValueError) as output:
        invalid_scale_mapping__arg = argparse.Namespace(helm=[str(HELM)], helm_dir=None, definitions=str(DEF_DIR),
                                                        scripts='', manifest='', certificate='', key='', images=None, scale_mapping='non_existent',
                                                        pkgOption='1')
        __main__.__check_arguments(invalid_scale_mapping__arg)
    assert str(output.value) == "The scale-mapping file, non_existent, doesn't exist"


def test_check_arguments_no_valid_scripts():
    with pytest.raises(ValueError) as output:
        invalid_script__arg = argparse.Namespace(helm=[str(HELM)], helm_dir=None, scripts='non_existent')
        __main__.__check_arguments(invalid_script__arg)
    assert str(output.value) == "The scripts folder, non_existent, doesn't exist"


def test_check_arguments_cert_with_no_manifest_or_values_csar():
    with pytest.raises(ValueError) as output:
        missing_manifest__arg = argparse.Namespace(helm=[str(HELM)], helm_dir=None, scripts='',
                                                   certificate='acert', manifest='', values_csar='', pkgOption='1')
        __main__.__check_arguments(missing_manifest__arg)
    assert str(output.value) == "A valid manifest file must be provided if certificate is provided."


def test_check_arguments_no_valid_key():
    with pytest.raises(ValueError) as output:
        invalid_key = argparse.Namespace(helm=[str(HELM)], helm_dir=None, scripts=str(SCRIPTS),
                                         vnfd='',
                                         manifest=str(MF),
                                         key='non_existent', certificate='acert', pkgOption='1')
        __main__.__check_arguments(invalid_key)
    assert str(output.value) == "The specified private key, non_existent, doesn't exist"


def test_check_arguments_option2_no_valid_cert():
    with pytest.raises(ValueError) as output:
        invalid_cert = argparse.Namespace(helm=[str(HELM)], helm_dir=None, scripts=str(SCRIPTS),
                                         vnfd='',
                                         manifest=str(MF),
                                         key='non_existent', certificate='', pkgOption='2')

        __main__.__check_arguments(invalid_cert)
    assert str(output.value) == "A valid certificate and key is not provided for Option 2"


def test_check_arguments_option2_no_valid_key():
    with pytest.raises(ValueError) as output:
        invalid_key = argparse.Namespace(helm=[str(HELM)], helm_dir=None, scripts=str(SCRIPTS),
                                         vnfd='',
                                         manifest=str(MF),
                                         key='', certificate='acert', pkgOption='2')

        __main__.__check_arguments(invalid_key)
    assert str(output.value) == "A valid certificate and key is not provided for Option 2"


def test_check_arguments_with_valid_args_passes_with_manifest_file():
    valid_key = argparse.Namespace(helm=[str(HELM)], helm_dir=None, scripts=str(SCRIPTS),
                                   vnfd=str(VNFD),
                                   manifest=str(MF),
                                   key=str(KEY), certificate='acert',
                                   values_csar='',
                                   definitions='',
                                   images=None,
                                   scale_mapping=None,
                                   pkgOption='1')
    __main__.__check_arguments(valid_key)


def test_check_arguments_with_valid_args_passes_with_values_csar_file():
    valid_key = argparse.Namespace(helm=[str(HELM)], helm_dir=None, scripts=str(SCRIPTS),
                                   vnfd=str(VNFD),
                                   manifest='',
                                   key=str(KEY), certificate='',
                                   values_csar=str(VALUES_CSAR),
                                   definitions=str(DEF_FILE),
                                   images=None,
                                   scale_mapping=None,
                                   pkgOption='1')
    __main__.__check_arguments(valid_key)


def test_check_arguments_with_valid_args_passes_and_path_to_images(tmp_path):
    images = tmp_path / 'images.tar'
    images.touch()
    valid_key = argparse.Namespace(helm=[str(HELM)], helm_dir=None, scripts=str(SCRIPTS),
                                   vnfd=str(VNFD),
                                   manifest=str(MF),
                                   key=str(KEY), certificate='acert',
                                   values_csar='',
                                   definitions=str(DEF_DIR),
                                   images=str(images),
                                   scale_mapping=None,
                                   pkgOption='1')
    __main__.__check_arguments(valid_key)


def test_check_arguments_with_nonexistent_images():
    valid_key = argparse.Namespace(helm=[str(HELM)], helm_dir=None, scripts=str(SCRIPTS),
                                   vnfd=str(VNFD),
                                   manifest=str(MF),
                                   key=str(KEY), certificate='acert',
                                   values_csar='',
                                   definitions='',
                                   scale_mapping=None,
                                   images='/tmp/does_not_exist.tar',
                                   pkgOption='1')
    with pytest.raises(ValueError):
        __main__.__check_arguments(valid_key)


def test_convert_str_to_bool_true_and_false():
    low_true = 'true'
    cap_true = 'TRUE'
    low_false = 'false'
    cap_false = 'FALSE'
    assert __main__.convert_str_to_bool(low_true)
    assert __main__.convert_str_to_bool(cap_true)
    assert not __main__.convert_str_to_bool(low_false)
    assert not __main__.convert_str_to_bool(cap_false)


def test_convert_str_to_bool_non_bool_number():
    with pytest.raises(argparse.ArgumentTypeError):
        numbers = "3462786"
        __main__.convert_str_to_bool(numbers)


def test_convert_str_to_bool_non_bool_word():
    with pytest.raises(argparse.ArgumentTypeError):
        letters = "somelettersthataren'taboolean"
        __main__.convert_str_to_bool(letters)


def test_values_csar_validity():
    with pytest.raises(ValueError) as output:
        __main__.__check_values_csar_validity(VALUES_CSAR_INVALID)
    assert str(output.value) == "The specified values-csar yaml file does not contain all the required keys"


def test_check_arguments_no_valid_definitions():
    with pytest.raises(ValueError) as output:
        invalid_definition_arg = argparse.Namespace(helm=[str(HELM)], helm_dir=None, definitions='non_existent',
                                                    scripts='', manifest='', certificate='', key='', images=None, scale_mapping=None,
                                                    pkgOption='1')
        __main__.__check_arguments(invalid_definition_arg)
    assert str(output.value) == "The definitions file or folder, non_existent, doesn't exist"


def test_check_arguments_with_valid_definition_directory_passes():
    valid_definitons_directory = argparse.Namespace(helm=[str(HELM)], helm_dir=None, definitions=str(DEF_DIR),
                                                    scripts='', manifest='', certificate='', key='', images=None, scale_mapping=None,
                                                    pkgOption='1')
    __main__.__check_arguments(valid_definitons_directory)


def test_check_arguments_with_valid_definition_file_passes():
    valid_definitons_file = argparse.Namespace(helm=[str(HELM)], helm_dir=None, definitions=str(DEF_FILE),
                                               scripts='', manifest='', certificate='', key='', images=None, scale_mapping=None,
                                               pkgOption='1')
    __main__.__check_arguments(valid_definitons_file)


def test_check_arguments_both_values_csar_and_manifest_files():
    with pytest.raises(ValueError) as output:
        both_values_csar_and_manifest_files = argparse.Namespace(helm=[str(HELM)], helm_dir=None,
                                                       manifest=str(MF),
                                                       values_csar=str(VALUES_CSAR),
                                                       scripts='', vnfd='', certificate='', key='', images=None, definitions='',
                                                       pkgOption='1')
        __main__.__check_arguments(both_values_csar_and_manifest_files)
    assert str(output.value) == "You cannot use both --manifest and --values-csar arguments at the same time"


def test_check_arguments_with_valid_product_report_file():
    valid_definitons_file = argparse.Namespace(helm=[str(HELM)], helm_dir=None, definitions=str(DEF_FILE),
                                               scripts='', manifest='', certificate='', key='', images=None, scale_mapping=None,
                                               pkgOption='1',
                                               product_report=[str(REPORT_OUT)])
    __main__.__check_arguments(valid_definitons_file)
