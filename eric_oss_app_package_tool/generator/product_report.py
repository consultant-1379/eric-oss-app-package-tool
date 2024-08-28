#!/usr/bin/python
'''Product report'''

import sys
import os
import logging
from subprocess import check_output, CalledProcessError
from collections import OrderedDict
import re
import yaml

from eric_oss_app_package_tool.generator.helm_template import HelmTemplate
from eric_oss_app_package_tool.generator.generate import get_charts
from eric_oss_app_package_tool.generator.docker_api import DockerApi, DockerError
from eric_oss_app_package_tool.generator.utils import extract, list_item

logging.getLogger("urllib3").setLevel(logging.WARNING)

_IMAGES_TEXT_FILE = "source/Files/images.txt"


# pylint: disable=too-many-ancestors
def ordered_dump(data, stream=None, **kwds):
    '''Dump OrderedDict as YAML.
       By default pyyaml does is not aware of that type.'''

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())

    yaml.SafeDumper.add_representer(ImageData, _dict_representer)
    yaml.SafeDumper.add_representer(HelmData, _dict_representer)
    return yaml.dump(data, stream, yaml.SafeDumper, **kwds)


def load_yaml_file(filename):
    '''Load YAML file as dictionaries'''
    try:
        yaml_file = open(filename, "r")
    except IOError:
        logging.debug("File %s not available", filename)
    else:
        with yaml_file:
            try:
                return yaml.safe_load(yaml_file)
            except yaml.YAMLError:
                logging.debug("File %s could not be loaded", filename)
    return {}


class ProductInfo(OrderedDict):
    '''Common class for Product Report elements'''
    def get_symmetric_diff(self, second):
        '''Get differences on two objects'''
        diff = list(self.viewitems() ^ second.viewitems())
        half = len(diff) // 2
        return dict(diff[:half]), dict(diff[half:])

    def __repr__(self):
        return "\n".join(["{}: {}".format(k, repr(v)) for k, v in self.items()])

    def is_valid(self):
        '''Check all values set'''
        if not all(self.values()):
            logging.debug("Validation failed for %s", self)
            return False

        return True


class HelmData(ProductInfo):
    '''Class representing Helm YAML output'''
    def __init__(self, **kwargs):
        super(HelmData, self).__init__()
        self.path = kwargs.get("path", "")
        self["product_number"] = kwargs.get("product_number", "")
        self["product_version"] = kwargs.get("product_version", "")
        self["package"] = kwargs.get("package", "")
        self["chart_name"] = kwargs.get("chart_name", "")
        self["chart_version"] = kwargs.get("chart_version", "")

    def __str__(self):
        return "Helm Chart '{}' version '{}'".format(self["chart_name"], self["chart_version"])


class ImageData(ProductInfo):
    '''Class representing Docker image YAML output'''
    def __init__(self, **kwargs):
        super(ImageData, self).__init__()
        self.path = kwargs.get("path", "")
        self["product_number"] = kwargs.get("product_number", "")
        self["product_version"] = kwargs.get("product_version", "")
        self["image"] = kwargs.get("image", "")
        self["image_name"] = kwargs.get("image_name", "")
        self["image_tag"] = kwargs.get("image_tag", "")

    def __str__(self):
        return "Image '{}' version '{}'".format(self["image_name"], self["image_tag"])


# pylint: disable=too-many-instance-attributes, too-many-arguments
class HelmChart(object):
    '''Helm Chart'''
    def __init__(self, helmdir, parent, package, args, include_report=False):
        self.path = os.path.join(parent, package)
        self.data = HelmData(package=package, path=self.path)
        self.helmdir = helmdir
        self.include_report = include_report
        self.args = args
        self.docker_api = DockerApi(args.docker_config)

        self.images = []
        self.packages = []

        self.eric_product_info = None
        self.chart = None

        self.errors = []
        self.warnings = []

        self._get_helm_template()
        self._extract_chart_data()
        self._process_chart_metadata()
        self._add_chart_images()
        self._add_crds()
        self._add_dependencies()

    def __str__(self):
        return str(self.data)

    def get_components(self):
        '''Return all Helm charts and Docker images'''
        packages = []

        if self.include_report:
            packages.append(self.data)

        images = self.images

        for package in self.packages:
            subpackages, subimages = package.get_components()
            packages.extend(subpackages)
            images.extend(subimages)

        return packages, images

    def get_errors(self):
        '''Get error messages'''
        errors = {self.path: self.errors} if self.errors else {}

        for package in self.packages:
            errors.update(package.get_errors())

        return errors

    def get_warnings(self):
        '''Get warning messages'''
        warnings = {self.path: self.warnings} if self.warnings else {}

        for package in self.packages:
            warnings.update(package.get_warnings())

        return warnings

    def _extract_image_metadata_from_image(self, image_name):
        '''Extract Product information from a Docker image'''
        labels = {}

        try:
            labels = self.docker_api.get_labels(image_name)
        except DockerError as exc:
            self.errors.append(exc.message)

        product_number = str(labels.get("com.ericsson.product-number", "")).replace(" ", "")
        product_revision = str(labels.get("org.opencontainers.image.version", ""))

        image_path, image_tag = image_name.split(':')
        image_basename = os.path.basename(image_path)

        return ImageData(
            product_number=product_number,
            product_version=re.sub('[-+][0-9]+',
                                   '',
                                   product_revision or image_tag),
            image=image_name,
            image_name=image_basename,
            image_tag=image_tag
        )

    def _extract_image_metadata_from_product_info(self, image_metadata):
        '''Extract Product from Docker container image'''
        image_name = "{}/{}/{}:{}".format(image_metadata.get("registry", ""),
                                          image_metadata.get("repoPath", ""),
                                          image_metadata.get("name", ""),
                                          image_metadata.get("tag", ""))

        product_number = image_metadata.get("productNumber", "").split('/')[0]
        product_number = product_number.replace(" ", "")

        labels_data = self._extract_image_metadata_from_image(image_name)

        eric_info_data = ImageData(
            product_number=product_number,
            product_version=re.sub('[-+][0-9]+', '', image_metadata.get("tag", "")),
            image=image_name,
            image_name=image_metadata.get("name", ""),
            image_tag=image_metadata.get("tag", "")
        )

        if labels_data != eric_info_data:
            labels_diff, eric_diff = eric_info_data.get_symmetric_diff(labels_data)
            self.errors.append("Image labels not matching to product info in '{}':\n"
                               "{:7} {}\n"
                               "{:7} {}".format(image_name,
                                                "Labels:",
                                                repr(labels_diff),
                                                "Chart:",
                                                repr(eric_diff)))

        if not eric_info_data.is_valid() and labels_data.is_valid():
            self.warnings.append("eric_product_info.yaml not valid on {}. "
                                 "Using image labels as source".format(labels_data))
            return labels_data

        return eric_info_data

    def _get_annotations(self):
        '''Get annotations'''
        if self.template:
            return self.template.get_annotations()
        return {}

    def _get_images_from_helm_template(self):
        '''Return list of images from Helm template'''
        if self.template:
            return self.template.get_all_images()
        return []

    def _get_helm_template(self):
        '''Parse Helm template YAML'''
        helm_command = "helm3" if self.args.helm3 else "helm"
        helm_options = "--debug" if self.args.helm_debug else ""

        try:
            helm_output = check_output("{} template {} {}".format(helm_command,
                                                                  helm_options,
                                                                  self.helmdir).split())
            self.template = HelmTemplate(helm_output)
        except CalledProcessError:
            self.errors.append("Cannot get Helm template for: {}".format(self.path))
            self.template = None

    def _extract_chart_data(self):
        '''Return Helm chart metadata as dictionaries'''
        self.eric_product_info = load_yaml_file("{}/eric-product-info.yaml".format(self.helmdir))
        self.chart = load_yaml_file("{}/Chart.yaml".format(self.helmdir))

    def _process_chart_metadata(self):
        '''Extract Product information from Helm chart'''
        self.data["chart_name"] = self.chart.get("name", "")
        self.data["chart_version"] = self.chart.get("version", "")

        if not self.eric_product_info:
            self.warnings.append("Helm Chart not conforming to "
                                 "DR-D1121-067, eric-product-info.yaml missing")

        product_number = self.eric_product_info.get("productNumber", "")
        product_version = self.chart.get("appVersion", "")

        if not product_version:
            annotations = self._get_annotations()
            product_version = annotations.get("ericsson.com/product-revision", "")

        self.data["product_number"] = product_number.replace(" ", "")
        self.data["product_version"] = product_version

        if not self.data.is_valid() and self.include_report:
            self.errors.append("Chart metadata not valid on:\n{}".format(list_item(repr(self.data))))

        logging.debug("%s added", self.data)

    def _add_crds(self):
        '''Add dependent CRD packages'''
        crd_dir = os.path.join(self.helmdir, "eric-crd")

        if not os.path.isdir(crd_dir):
            logging.debug("No CRD packages in %s", self)
            return

        for crd_package in os.listdir(crd_dir):
            with extract(os.path.join(crd_dir, crd_package)) as helm:
                crd = HelmChart(helm,
                                "{}/eric-crd".format(self.path),
                                crd_package,
                                args=self.args,
                                include_report=True)
                self.packages.append(crd)
                logging.info("Found CRD %s from %s", crd, self)

    def _add_dependencies(self):
        '''Add dependent Helm charts'''
        charts_dir = os.path.join(self.helmdir, "charts")

        if not os.path.isdir(charts_dir):
            logging.debug("No charts dir in %s", self)
            return

        for dependency in os.listdir(charts_dir):
            chart_path = os.path.join(charts_dir, dependency)
            helm = HelmChart(chart_path,
                             "{}/charts".format(self.path),
                             dependency,
                             args=self.args,
                             include_report=False)
            self.packages.append(helm)
            logging.debug("Found dependency %s from %s", helm, self)

    def _add_image(self, image_metadata):
        '''Add an image to images list'''
        image_metadata.path = self.path

        if not image_metadata.is_valid():
            self.errors.append("Image metadata not valid on:\n{}".format(list_item(repr(image_metadata))))

        self.images.append(image_metadata)
        logging.debug("%s added from %s", image_metadata, self.data)

    def _add_chart_images(self):
        '''Add dependent Docker images'''
        if self.eric_product_info:  # get images through eric_product_info.yaml
            for _, image in self.eric_product_info.get("images", {}).items():
                image_metadata = self._extract_image_metadata_from_product_info(image)
                self._add_image(image_metadata)

        else:  # Get images through Helm template
            images = self._get_images_from_helm_template()

            for image_name in images:
                image_metadata = self._extract_image_metadata_from_image(image_name)
                self._add_image(image_metadata)


def remove_duplicates(components):
    '''Remove duplicate components from final output'''
    packages = {}
    images = {}

    for image in components["images"]:
        existing = images.get(image["image"], {})
        if existing:
            logging.debug("Removing duplicate %s", image)
            continue

        images[image["image"]] = image

    for package in components["packages"]:
        existing = packages.get(package["chart_name"], {})
        if existing:
            # Print info if duplicate packages, prefer newer version
            if existing["chart_version"] > package["chart_version"]:
                logging.info("Removing duplicate %s, already added %s", package, existing)
                continue

            logging.info("Removing duplicate %s, already added %s", existing, package)

        packages[package["chart_name"]] = package

    components["images"] = images.values()
    components["packages"] = packages.values()


def verify_all_components_valid(components):
    '''Verify all components have valid data'''
    invalid = [c for c in components["images"] + components["packages"] if not c.is_valid()]

    if invalid:
        logging.error("Incomplete entries in the output file:\n%s\n",
                      "\n".join(list(map(list_item, ["{}:\n{}".format(c.path, list_item(repr(c))) for c in invalid]))))
        return False

    return True


def verify_unique_product_numbers(components):
    '''Check that product numbers in product report are unique'''
    valid = True
    product_numbers = {}

    for component in components["images"] + components["packages"]:
        product_numbers.setdefault(component["product_number"], []).append(component)

    duplicates = {num: items for (num, items) in product_numbers.items()
                  if (len(items) > 1 and num)}

    for product_number, products in duplicates.items():
        product_names = [p.get("image_name") or p.get("chart_name") for p in products]
        if len(products) != product_names.count(product_names[0]):
            logging.error("Same product number '%s' used in multipe components:\n%s\n",
                          product_number,
                          "\n".join(map(list_item, ["{}:\n{}".format(c.path, list_item(repr(c))) for c in products])))
            valid = False

    return valid


def verify_all_images_in_report(args, images):
    '''Verify contents of product report matches with the downloaded images'''
    if args.no_images:
        return True

    try:
        with open(_IMAGES_TEXT_FILE, "r") as image_file:
            downloaded = set(image_file.read().splitlines())
            report = set([i["image"] for i in images])

            report_missing = downloaded - report
            download_missing = report - downloaded

            if report_missing or download_missing:
                if report_missing:
                    logging.error("Images not in Product Report:\n%s\n",
                                  "\n".join(map(list_item, report_missing)))
                if download_missing:
                    logging.error("Images not in CSAR package:\n%s\n",
                                  "\n".join(map(list_item, download_missing)))
                return False

    except IOError:
        logging.error("Could not open file '%s'", _IMAGES_TEXT_FILE)
        return False

    return True

def check_for_errors(errors):
    '''Check error messages from product report creation'''
    if errors:
        message = ""
        for path, error in errors.items():
            message += list_item("{}:\n{}\n".format(path, "\n".join(map(list_item, error)))) + os.linesep
        logging.error("Errors while processing product report:\n%s", message)
        return False
    return True


def check_for_warnings(warnings):
    '''Check warning messages from product report creation'''
    if warnings:
        message = ""
        for path, warn in warnings.items():
            message += list_item("{}:\n{}\n".format(path, "\n".join(map(list_item, warn)))) + os.linesep
        logging.warning("Warnings while processing product report:\n%s", message)


def create_product_report(args):
    '''Create product report YAML file'''
    output = {"includes": {"images": [], "packages": []}}
    errors = {}
    warnings = {}

    charts = get_charts(args)
    for chart in charts:
        with extract(chart) as helmdir:
            helm = HelmChart(helmdir,
                             "",
                             os.path.basename(chart),
                             args=args,
                             include_report=True)
            packages, images = helm.get_components()
            output["includes"]["packages"] = packages
            output["includes"]["images"] = images

            errors.update(helm.get_errors())
            warnings.update(helm.get_warnings())

    remove_duplicates(output["includes"])

    try:
        with open(args.product_report, "w") as outfile:
            outfile.write(ordered_dump(output, default_flow_style=False))
        logging.info("Wrote product report YAML file to %s", args.product_report)
    except IOError:
        logging.exception("Failed to write product report file to %s", args.product_report)
        sys.exit(1)

    check_for_warnings(warnings)

    if any((not check_for_errors(errors),
            not verify_unique_product_numbers(output["includes"]),
            not verify_all_components_valid(output["includes"]),
            not verify_all_images_in_report(args, output["includes"]["images"]))):
        logging.error("Product Report failed validation")
        sys.exit(1)
