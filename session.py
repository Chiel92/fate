"""A session represents the state of an editing session"""
from .event import Event
from . import current
import logging


class Session():
    """Class containing all objects of one file editing session"""
    # E.g. text, selection, undo tree, jump history
    OnSessionInit = Event()
    OnApplyOperation = Event()
    OnRead = Event()
    OnWrite = Event()

    def __init__(self, filename=""):
        self.text = ""
        self.filename = filename
        if filename:
            self.read()
        current.sessions.append(self)
        self.OnSessionInit.fire(self)

    def read(self):
        """Read text from file"""
        if self.filename:
            with open(self.filename, 'r') as fd:
                self.text = fd.read()
        self.OnRead.fire()

    def write(self):
        """Write current text to file"""
        if self.filename:
            with open(self.filename, 'w') as fd:
                fd.write(self.text)
        self.OnWrite.fire()

    def apply(self, operation):
        """Apply the operation to the text"""
        partitioned = operation.old_selection.partition(self.text)
        content = self.content(partitioned)
        count = 0
        for i, interval in enumerate(partitioned):
            if interval in operation.old_selection:
                content[i] = operation.new_content[count]
                count += 1

        self.text = ''.join(content)
        self.OnApplyOperation.fire(operation)

    def undo(self, operation):
        """Apply the operation reversely"""
        self.apply(operation.inverse())

    def content(self, selection):
        """Return the content of the selection"""
        return [self.text[beg:end] for beg, end in selection]


from . import user
# Load the plugins, after defining Session
#from . import load_plugins
