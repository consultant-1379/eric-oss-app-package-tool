class Image(object):
    """Holds information about a docker image.
        repo is mandatory, tag is optional"""
    def __init__(self, repo, tag="latest"):
        self.repo = repo
        self.tag = tag

    def __str__(self):
        return self.repo + ":" + self.tag

    def __hash__(self):
        return hash(self.__str__())

    def __eq__(self, other):
        if isinstance(other, Image):
            return self.__str__() == other.__str__()
        else:
            return False
