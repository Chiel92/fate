from abc import abstractmethod

from .selection import Interval, Selection


class Text:

    # TODO: somehow add sequence and buffer interface to this

    """Interface for text objects."""

    @abstractmethod
    def __getitem__(self, item: (int, Interval, Selection)):
        pass

    @abstractmethod
    def transform(self, transformation):
        pass


class StringText(Text, str):

    """Implementation of a Text using a simple string."""

    def __new__(cls, content):
        return str.__new__(cls, content)

    def __getitem__(self, item: (int, Interval, Selection, slice)):
        if isinstance(item, (int, slice)):
            return str.__getitem__(self, item)
        if isinstance(item, Interval):
            beg, end = item
            return str.__getitem__(self, slice(beg, end))
        if isinstance(item, Selection):
            return [self[interval] for interval in item]
        raise ValueError

    def transform(self, transformation):
        """Apply the transformation to self."""
        oldselection = transformation.selection
        content = transformation.selection.content(self)
        original_content = transformation.original_content
        assert content == original_content, "Transformation applied on wrong text"
        replacements = transformation.replacements

        transformation.validate(self)

        partition = oldselection.partition(self)
        partition_content = [(in_selection, self[interval])
                             for in_selection, interval in partition]

        count = 0
        result = []
        for in_selection, string in partition_content:
            if in_selection:
                result.append(replacements[count])
                count += 1
            else:
                result.append(string)

        return StringText(''.join(result))


class PartialText(StringText):

    """
    Implementation of a text while only a small part of the text is maintained and retrievable.
    This is useful for applying text transformations on the text that is visible on the screen
    in a fast and cheap manner.
    """

    def __init__(self, text: Text, beg: int, end: int):
        StringText.__init__(self, text[Interval(beg, end)])
        self.origin = text
        self.beg = beg
        self.end = end

    def __contains__(self, item: (int, Interval)):
        if isinstance(item, int):
            return self.beg <= item <= self.end
        if isinstance(item, Interval):
            return self.beg <= item[0] <= item[1] <= self.end
        raise ValueError

    def __getitem__(self, item: (int, Interval, Selection), failfast=False):
        if isinstance(item, int):
            if item not in self:
                raise IndexError('item {} is out of range ({},{})'.format(item, self.beg,
                                                                          self.end))
            return StringText.__getitem__(self, item - self.beg)
        if isinstance(item, Interval):
            beg, end = item
            if failfast and item not in self:
                raise IndexError('item ({},{}) is out of range ({},{})'.format(beg, end, self.beg,
                                                                               self.end))
            # We don't have to cap the indices by self.end, slicing does that for us.
            return StringText.__getitem__(self, Interval(max(0, beg - self.beg),
                                                         max(0, end - self.beg)))
        if isinstance(item, Selection):
            return [self[interval] for interval in item]
        raise ValueError

    def transform(self, transformation):
        """
        Apply the transformation to self.
        """
        # Check that substitutions are inside our valid range and call base.
        for interval in transformation.selection:
            if interval not in self:
                beg, end = interval
                raise IndexError('item ({},{}) is out of range ({},{})'.format(beg, end, self.beg,
                                                                               self.end))

        StringText.transform(self, transformation)
