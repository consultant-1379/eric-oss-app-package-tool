import sys
import argparse
from argparse import Namespace
import logging
import zipfile
import shutil
from eric_oss_app_package_tool.generator import generate, product_report, hash_utils
from vnfsdk_pkgtools.packager import csar
from vnfsdk_pkgtools.packager import utils
import os
from yaml import safe_load, dump

SIGNATURE_FILE_NAME = 'signature.csm'
Files_Folder = 'Metadata/'


def __check_arguments(args):
    check_helm_arguments(args)
    if args.scripts and not os.path.exists(args.scripts):
        raise ValueError("The scripts folder, " + args.scripts + ", doesn't exist")
    if args.manifest and args.vnfd:
        manifest_name = os.path.basename(str(args.manifest)).rsplit('.', 1)[0]
        vnfd_name = os.path.basename(str(args.vnfd)).rsplit('.', 1)[0]
        if manifest_name != vnfd_name:
            raise ValueError("The name of both yaml file and manifest file must match.")
    if (args.pkgOption is '1') and args.certificate and not args.manifest and not args.values_csar:
        raise ValueError("A valid manifest file must be provided if certificate is provided.")
    if (args.pkgOption is '2') and (not args.certificate or not args.key):
        raise ValueError("A valid certificate and key is not provided for Option 2")
    if args.key and not os.path.exists(args.key):
        raise ValueError("The specified private key, " + args.key + ", doesn't exist")
    if args.images is not None and not os.path.exists(args.images):
        raise ValueError("The specified images file, " + args.images + ", doesn't exist")
    if args.manifest and args.values_csar:
        raise ValueError("You cannot use both --manifest and --values-csar arguments at the same time")
    if args.definitions and not os.path.exists(args.definitions):
        raise ValueError("The definitions file or folder, " + args.definitions + ", doesn't exist")
    if args.scale_mapping and not os.path.exists(args.scale_mapping):
        raise ValueError("The scale-mapping file, " + args.scale_mapping + ", doesn't exist")


def check_helm_arguments(args):
    logging.info('Checking charts')
    if not args.helm and not args.helm_dir:
        args.helm_dir = 'OtherDefinitions/ASD/'
        logging.info('Using default folder ASD for charts')
    if args.helm is not None:
        for helm in args.helm:
            if not os.path.exists(helm):
                raise ValueError("The specified helm chart, " + helm + ", doesn't exist")
    if args.helm_dir is not None:
        if not os.path.isdir(args.helm_dir):
            raise ValueError("The specified helm directory is not a directory")
        helm_charts_exist = False
        for root, directories, files in os.walk(args.helm_dir):
            for filename in files:
                if '.tgz' in filename:
                    helm_charts_exist = True
        if not helm_charts_exist:
            raise ValueError("The specified directory does not contain any helm charts")


def __check_values_csar_validity(values_file):
    with open(values_file) as source:
        values_csar_dict = safe_load(source)
        for key in generate.METADATA_KEYS:
            if key != "vnf_release_date_time" and key not in values_csar_dict:
                raise ValueError("The specified values-csar yaml file does not contain all the required keys")


def generate_option1(args, vnfd):
    if args.values_csar:
        __check_values_csar_validity(args.values_csar)
        path_to_manifest_in_source = generate.create_manifest_file(args)
    else:
        path_to_manifest_in_source = generate.create_path(args.manifest, '')
    filename = str(args.name) + '.csar'
    try:
        logging.info('Deleting pre-existing csar file with the name: {0}'.format(filename))
        os.remove(filename)
    except OSError:
        logging.debug('No pre-existing csar file to delete')

    path_to_helm_in_source = generate.REL_PATH_TO_HELM_CHART
    path_to_history_in_source = generate.create_path(args.history, Files_Folder)
    digest_value = generate.check_digest(args)
    path_to_cert_in_source = generate.create_path(args.certificate, Files_Folder)
    csar_args = Namespace(helm=path_to_helm_in_source, csar_name=filename, manifest=path_to_manifest_in_source,
                          history=path_to_history_in_source,
                          tests='', licenses='', debug='', created_by='Ericsson', certificate=path_to_cert_in_source,
                          digest=digest_value,
                          privkey=args.key
                          )
    logging.info("Csar args Option 1 " + str(csar_args))
    csar.write(generate.SOURCE, vnfd, filename, csar_args)


def generate_option2(args, vnfd):
    filename = 'pkg_' + str(args.name) + '.csar'
    try:
        logging.info('Deleting pre-existing csar file with the name: {0}'.format(filename))
        os.remove(filename)
    except OSError:
        logging.debug('No pre-existing csar file to delete')

    path_to_helm_in_source = generate.REL_PATH_TO_HELM_CHART
    path_to_history_in_source = generate.create_path(args.history, Files_Folder)
    csar_args = Namespace(helm=path_to_helm_in_source, csar_name=filename, manifest='',
                          history=path_to_history_in_source,
                          tests='', licenses='', debug='', created_by='Ericsson', certificate='',
                          digest='',
                          privkey=''
                          )
    logging.info("Csar args Option 2 " + str(csar_args))
    sourceDir = os.getcwd()
    csar.write(sourceDir, vnfd, filename, csar_args)
    csaroutDir = os.getcwd() + "/../"
    filename_full_path = os.path.join(csaroutDir, filename)
    print("PATH CHECK:  \nSource folder: " + sourceDir +"\nUnsigned folder: "+csaroutDir+"\nUnsigned csar: "+filename+"\n")
    if args.certificate:
        csar.check_file_dir(root=sourceDir,
                            entry=args.certificate,
                            msg='Please specify a valid certificate file.',
                            check_dir=False)
        if not args.key:
            raise ValueError('Need private key file for signing')
        csar.check_file_dir(root='',
                            entry=args.key,
                            msg='Please specify a valid private key file.',
                            check_dir=False)

    if args.certificate and args.key:
        logging.debug('calculate signature: {0}', str(args.certificate))
        signature = utils.sign(msg_file=filename_full_path,
                               cert_file=os.path.join(sourceDir, args.certificate),
                               key_file=args.key)

    with open(SIGNATURE_FILE_NAME, "w") as file:
        file.write(signature)

    destination = "../" + str(args.name) + '.csar'
    try:
        logging.info('Deleting pre-existing csar file with the name: {0}'.format(destination))
        os.remove(destination)
    except OSError:
        logging.debug('No pre-existing csar file to delete')

    logging.debug("Compressing to make Option 2 csar")
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as f:
        cert_file_full_path = os.path.join(sourceDir, args.certificate)
        logging.debug('Writing to archive: {0}'.format(cert_file_full_path))
        f.write(cert_file_full_path, os.path.basename(args.certificate))
        if os.path.isfile(SIGNATURE_FILE_NAME):
            signature_file_full_path = os.path.join(sourceDir, SIGNATURE_FILE_NAME)
            logging.debug('Writing to sig: {0}'.format(signature_file_full_path))
            f.write(signature_file_full_path, SIGNATURE_FILE_NAME)
        else:
            raise ValueError("The signature file does not exist")
        f.write(filename_full_path, filename)

    try:
        logging.info('Deleting existing csar file with the name: {0}'.format(filename))
        os.remove("../" + filename)
    except OSError:
        logging.debug('No existing csar file to delete')


def generate_func(args):
    logging.debug('Args: ' + str(args))
    __check_arguments(args)
    __docker_tar_generated = False
    if args.no_images:
        logging.info("Lightweight CSAR requested, skipping docker.tar file generation")
    elif args.images:
        logging.info("docker.tar file has been passed in, skipping docker.tar file generation")
        docker_file = args.images
    else:
        logging.info("Generating the docker.tar file")
        docker_file = generate.create_docker_tar(args)
        __docker_tar_generated = True

    generate.create_source(args)
    if args.no_images:
        generate.__empty_images_section()
    else:
        generate.__create_images_section(docker_file)

    if args.product_report:
        product_report_ok = product_report.create_product_report(args)

    vnfd_path = generate.get_vnfd(args)

    if __docker_tar_generated:
        generate_hash_for_docker_tar(vnfd_path, docker_file)

    if args.pkgOption is '2':
        generate_option2(args, vnfd_path)
    else:
        generate_option1(args, vnfd_path)

    #generate.delete_source()
    shutil.move( "../" + str(args.name) + '.csar' , str(args.name) + '.csar')
    
    if args.output:
        filename = str(args.name) + '.csar'
        if os.path.exists( args.output ):
            logging.info("Validating output folder")
        else:
            os.makedirs( args.output )
        logging.info("Folder output specified as: " + args.output)
        shutil.move( filename , filename + ".moving" )
        if os.path.exists( args.output + "/" + filename + ".bak" ):
            os.remove( args.output + "/" + filename + ".bak" )
        if os.path.exists( args.output + "/" + filename ):
            shutil.move( args.output + "/" + filename , args.output + "/" + filename +".bak" )
        shutil.move( filename + ".moving" , args.output + "/" + str(args.name) + '.csar')

    if args.product_report and not product_report_ok:
        sys.exit(1)


def generate_hash_for_docker_tar(vnfd_path, docker_file):
    full_vnfd_path = os.path.join(generate.SOURCE, vnfd_path)
    with open(full_vnfd_path, 'r+') as values_file:
        vnfd_dict = safe_load(values_file)
        try:
            if type(vnfd_dict) is dict and 'tosca_definitions_version' in vnfd_dict and vnfd_dict[
                'tosca_definitions_version'] == 'tosca_simple_yaml_1_3':
                logging.info('Csar vnfd version is 1.3 - starting to generate hashes for software_images artifacts')
                calculate_and_write_hash_for_docker_tar(vnfd_dict, docker_file)
                updated_vnfd = dump(vnfd_dict, sort_keys=False)
                values_file.seek(0)
                values_file.write(updated_vnfd)
                values_file.truncate()
        except Exception:
            logging.error('Failed to fill hash values for docker.tar artifact', exc_info=True)


def calculate_and_write_hash_for_docker_tar(vnfd_dict, docker_file):
    if type(vnfd_dict['node_types']) is dict and 'node_types' in vnfd_dict:
        for node_type_name, node_type in vnfd_dict['node_types'].items():
            try:
                logging.info('Filling hash value for docker.tar artifact in {} node type'.format(node_type_name))
                hash_algorithm = node_type['artifacts']['software_images']['properties']['checksum']['algorithm']
                if hash_algorithm is not None and hash_algorithm in hash_utils.HASH.keys():
                    logging.info('Calculating hash for docker.tar artifact in {} node type using {} algorithm'.format(node_type_name, hash_algorithm))
                    checksum_hash = hash_utils.HASH[hash_algorithm](docker_file)
                    node_type['artifacts']['software_images']['properties']['checksum']['hash'] = checksum_hash
                else:
                    logging.error(
                        'Failed to generate hash for docker.tar artifact in {} node type because algorithm is not specified or is not recognized'.format(
                            node_type_name))
            except KeyError as e:
                logging.error('Failed to fill hash values for docker.tar artifact because key {} not found '.format(e))
    else:
        logging.error('Wrong structure, node_types is not a dictionary or node_types is not present')


def parse_args(args_list):
    """
    CLI entry point
    """

    parser = argparse.ArgumentParser(description='CSAR File Utilities')

    subparsers = parser.add_subparsers(help='generate')
    generate = subparsers.add_parser('generate')
    generate.set_defaults(func=generate_func)
    generate.add_argument(
        '--docker-config',
        help='''Path to Docker configuration''',
        default='/root/.docker'
    )
    generate.add_argument(
        '-hm',
        '--helm',
        help='''One or more Helm charts to use to generate the csar file.
        This can be absolute paths or relative to the the current folder''',
        nargs='*',
        type=str
    )
    generate.add_argument(
        '-hd',
        '--helm-dir',
        help='''A directory containing the helm charts'''
    )
    generate.add_argument(
        '-n',
        '--name',
        help='The name to give the generated csar file',
        required=True
    )
    generate.add_argument(
        '-sc',
        '--scripts',
        help='the path to a folder which contains scripts to be included in the csar file'
    )
    generate.add_argument(
        '-l',
        '--log',
        help='Change the logging level for this execution, default is INFO',
        default="INFO"
    )
    generate.add_argument(
        '--set',
        help='Values to be passed to the helm template during csar package generation',
        nargs='*'
    )
    generate.add_argument(
        '-f',
        '--values',
        help='Yaml file containing values to be passed to the helm template during csar package generation',
        nargs='*'
    )
    generate.add_argument(
        '-hs',
        '--history',
        help='The path to the change log for the csar file',
        default=''
    )
    generate.add_argument(
        '-mf',
        '--manifest',
        help='The path to the manifest file for the csar file.',
        default=''
    )
    generate.add_argument(
        '-vn',
        '--vnfd',
        '--tosca',
        help='The path to the VNF Descriptor yaml file for the csar file',
        default=''
    )
    generate.add_argument(
        '-d',
        '--definitions',
        help='The path to an additional definitions file or a directory containing definition files',
        default=''
    )
    generate.add_argument(
        '-sm',
        '--scale-mapping',
        help='The path to a scale-mapping file.',
    )
    generate.add_argument(
        '--sha512',
        type=convert_str_to_bool,
        help='Boolean to generate SHA512 hash for each file in the csar file and write to manifest file if provided.',
        default=True
    )
    generate.add_argument(
        '-cert',
        '--certificate',
        help='The certificate file for signing of the CSAR',
        default=''
    )
    generate.add_argument(
        '--key',
        help='Private key file for signing of the CSAR',
        default=''
    )
    generate.add_argument(
        '--images',
        help='The path to a pre-packaged file containing the container images exported from the Helm chart',
        default=None
    )

    generate.add_argument(
        '--no-images',
        help='Flag to skip generation of the docker.tar file',
        action='store_true'
    )
    generate.add_argument(
        '-vc',
        '--values-csar',
        help='The path to the yaml file containing values for generating manifest for csar package',
        default=''
    )
    generate.add_argument(
        '--pkgOption',
        help='To generate signed VNF package, 1 for Option1 and 2 for Option2. Set to 1 by default',
        default=1
    )
    generate.add_argument(
        '--helm3',
        action='store_true',
        help='To generate CSAR with Helm 3'
    )
    generate.add_argument(
        '--helm-debug',
        action='store_true',
        help='Run helm commands with debug option'
    )
    generate.add_argument(
        '--product-report',
        help='To generate product report YAML file'
    )
    generate.add_argument(
        '--output',
        help='Move final csar to specific folder'
    )

    return parser.parse_args(args_list)


def convert_str_to_bool(arg):
    if arg.lower() in ('true', 't'):
        return True
    elif arg.lower() in ('false', 'f'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def __configure_logging(logging, level):
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=level.upper())


def main():
    args = parse_args(sys.argv[1:])
    __configure_logging(logging, args.log)
    args.func(args)


if __name__ == '__main__':
    main()
