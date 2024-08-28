import yaml
import logging
from utils import find_key_in_dictionary


class HelmTemplate(object):
    """This class contains methods for retrieving information from the rendered chart."""

    def __init__(self, helm_template):
        self.helm_template = helm_template
        self.templates = self.__load_into_yaml()

    def __load_into_yaml(self):
        return yaml.load_all(self.helm_template.decode('utf-8').replace('\t', ' ').rstrip(),
                             Loader=yaml.SafeLoader)

    def get_all_images(self):
        images = set()
        for template in self.templates:
            value = list(find_key_in_dictionary(input_key="image", wanted_type=str, dictionary=template))
            if value:
                logging.debug("value found is: " + str(value))
                images.update(value)
        logging.debug("Images are: " + str(images))
        return images

    def get_annotations(self, kind="ConfigMap"):
        annotations = {}

        try:
            # Get the first template of the specified "kind"
            template = next(t for t in self.templates if t.get("kind") == kind)
            annotations = template.get("metadata", {}).get("annotations", {})
        except StopIteration:
            logging.warning("Annotations could not be found")

        return annotations