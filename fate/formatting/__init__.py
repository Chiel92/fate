from importlib import import_module
import logging
import subprocess

from ..commands import selectall
from ..operation import Operation
from ..document import Document
from .. import commands

# Dependencies
from .. import filetype


class Formatter:

    """Container for formatter configuration."""

    def __init__(self, executable, arguments):
        self.executable = executable
        self.arguments = arguments


def formattext(doc):
    """If doc has a formatter, execute it and replace text with the result."""
    formatter = doc.formatter
    if formatter:
        # Execute formatter
        process = subprocess.Popen([formatter.executable, formatter.arguments],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   universal_newlines=True)
        newtext, errors = process.communicate(doc.text)

        # Replace text with formatted text
        oldselection = doc.selection
        selectall(doc)
        operation = Operation(doc, newcontent=[newtext])
        operation(doc)

        # TODO: select something useful after format
        doc.selection = oldselection

commands.formattext = formattext


def load_filetype_formatter(doc):
    doc.formatter = None
    if doc.filetype:
        try:
            module = import_module(__name__ + '.' + doc.filetype)
        except ImportError:
            logging.info('No formatter script found for filetype ' + doc.filetype)
        else:
            logging.info('Formatter script found for filetype ' + doc.filetype)
            doc.formatter = module.formatter

Document.OnFileTypeLoaded.add(load_filetype_formatter)