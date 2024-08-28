import shutil
import tempfile
import tarfile
import textwrap
from contextlib import contextmanager
import os


def find_key_in_dictionary(input_key, wanted_type, dictionary):
    if hasattr(dictionary, 'items'):
        for k, v in dictionary.items():
            if k == input_key and isinstance(v, wanted_type):
                yield v
            if isinstance(v, dict):
                for result in find_key_in_dictionary(input_key, wanted_type, v):
                    yield result
            elif isinstance(v, list):
                for item in v:
                    for result in find_key_in_dictionary(input_key, wanted_type, item):
                        yield result


@contextmanager
def extract(*args):
    '''Extract Helm chart to temporary directory.
       Used through context manager.'''
    chart = args[0]
    try:
        tmp = tempfile.mkdtemp()
        with tarfile.open(chart) as tar:
            tar.extractall(tmp)
            yield os.path.join(tmp, os.listdir(tmp)[0])
    finally:
        shutil.rmtree(tmp)


def list_item(text, title='-', width=160):
    '''Return bullet list element with indentation'''
    lines = []

    for line in text.splitlines():
        wrapped_line = textwrap.fill(line,
                                     width,
                                     initial_indent='    ',
                                     subsequent_indent='    ',
                                     break_long_words=False,
                                     break_on_hyphens=False)
        lines.append(wrapped_line)
    output = '  {} '.format(title) + '\n'.join(line for line in lines).lstrip()

    return output