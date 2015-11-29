from ..operators import Insert
from .. import commands
from .basetestcase import BaseTestCase

class OperatorTest(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)
        commands.selectnextword(self.document)

    def test_insert(self):
        command = Insert('Foo ')
        command(self.document)
        expected = 'Foo import sys'
        self.assertEqual(expected, self.document.text[:14])

        commands.undo(self.document)
        self.assertEqual('import sys', self.document.text[:10])

