"""
There are many situations in which we want to alter the way the text is viewed to the user
from the actual text. Since this is so common, it is rewarding to create a framework in
which this can be done easily. To get to know the problem scope better, we will list a few
possible applications and deduce the requirements for the framework from this.

Some possible applications are listed below.
1. Substitute certain strings with single unicode characters. It may for instance improve
   readability in various programming languages to substitute operators like `!=` with an
   actual `≠`. However, since the text actually has the string `!=`, and it should still be
   editable as such, the substitution should probably only be performed when the string of
   concern is not near the current user selection.
2. Subsitute a tab with a specified amount of spaces.
3. Preview an ongoing operation, like a text insertion, to improve performance and avoid
   recomputation of the entire text while typing.
4. Prepend a selected newline character with some other character, to notify the user that
   a newline has been selected.
5. Insert a certain character into an empty interval in a selection, to be able to show an
   empty interval in environments that cannot display a single cursor stripe, like most
   terminal emulators.
6. Insert a line number before each line.
7. Substitute a folded snippet of text with something else.
8. Substitute non-printable character with a placeholder, to notify the user its there.
9. Substitute certain character with another to mark positions. This is useful for tools
   like easy motion.
10. Any kind of textual markup, like a hex mode or tables, which define all kinds of extra
   textual features which are not part of the text itself and should not be selected.

Some of these applications would also involve displaying the resulting string in a
different color. So this framework is tightly bound with highlighting.

Now, after all these substitutions, we still need to know for a string in the resulting
text the corresponding string in the original text. This is necessary for instance for
determining the highlighting of characters and whether characters are selected or not.
Obviously there is no one-to-one correspondence between characters in either text, so what
is the best way to define such a mapping? Some thoughts.
- Any interval can be mapped to any string, even empty intervals (see application 3 and 5).
- When an empty interval is mapped, and a empty interval selections happens to be at the
  same place, it is not necessarily be in that empty selection. How to distinct between
  this? It means we can't just map positions to positions, since an empty inteval mapping to a
  non empty interval would cause one position to be mapped to two positions.
  Cheap workaround: also keep a dictionary to map the intervals, if someone requests an exact
  interval, use the dict, otherwise construct something from individual positions.
- How do we deal with overlapping substitutions? A seemingly all right way to deal with this
  is to let larger replacements have precedence over shorter ones. This implies that
  replacements of super intervals have precedence over sub intervals.
- The mapping should be able to map interval positions, intervals and selections.
- After a substitution, some interval is mapped to another interval. How are the intermediate
  positions mapped? Only applications 3 and 6 seem to be affected by the choice this behaviour.
  When something inside a folded text snippet is colored, what should be colored in the view text?
  Nothing seems to be the only sane choice.
  When something inside a folded text snippet is selected, what should be selected in the view text?
  Some possibilities are listed below.
  When anything is selected in the fold (even emptily)
  1. the entire fold should look selected.
  2. the entire fold should look unselected.
  3. the first character in the fold should look selected.
  4. there should be an empty selection before the fold.
  Option 2 obviously has its issue of losing track of the selection.
  When something is colored inside an interval that is being edited, what should be colored in
  the view text? Without further information, we don't know what should be colored, since the
  new content of the interval could be entirely unrelated to the old content.
  However, if the interval being edited is part of a larger colored string, the color would
  remain, since the new intervals and old interval are obviously mapped onto each other in the
  mapping. This would have the nasty side effect that when a keyword is being replaced by
  something else, this something else would have the same color as the keyword, which is
  actually incorrect.
  This suggests that the syntax highlighting should be done a text with these operation
  preview substitutions and without the rest. This is true regardless of when the highlighting
  is done. The global asynchronous highlighting should also be done on a text with just the
  preview operations. The latter would asynchronously result in a textview for the entire text.
  From this we must conclude that text views and highlightings should work tightly together.
  Furthermore we can conclude that application 3 is indifferent as to how positions inside
  replaced intervals are being mapped.
  Option 4 seems to be the most straightforward solution here, and should be easy to
  implement.

When mapping an empty interval to a non empty interval, how to know
whether a replacement is in the image of the mapping?

The following are interval positions
0 1   2 3 4
0 1 2 3 4 5
    ^
    Not in the image


Does it help if we go one level of indirection higher w.r.t. the positions?
I.e. the interval positions of interval positions.

Meta interval | 0 1 2 3 4 5 6 7 8 9
interval      |  0   1   2   3   4
Text          |    0   1   2   3

This works in the sense that you can now fully control what to map. Not only text, but
also the interval positions in the text, i.e. the user selections.
It enables you to insert things into the text that do not actually belong to the text, and
thus should not be selectable. You can do this by mapping an empty meta interval.
Generally speaking, you can specify whether or not an interval bound should be mapped.

Intervals must sometimes be mapped to multiple intervals, for instance if there
are line numbers and some selected interval spans over multiple lines.

You can also encode a meta interval position by an interval position and a left/right
flag. When translating intervals to meta intervals it is a good default to make the bounds
exclusive. This way, empty intervals touching a replacement are not considered inside the
replacement.

Are meta intervals relevant when doing a replacement/deletion instead of an insertion?

Insertion
  When something adjacent is selected, should the insertion also look selected? (No,
  but in case of application 3 and 5, Yes)
  On which side do empty intervals appear? (After)
Deletion
  Doesn't matter, something selected inside a deletion will always be an empty interval.
Replacement
  Is an empty interval at the end of the replacement considered to be in the replacement?
  (No)
  When something adjacent is selected, should the replacement also look selected? (No)


It seems that for all of these questions a very sane default answer can be given from
which it is very unlikely that one would want to deviate from.
For the difference between application 3 and 5 and the rest in case of insertions, we should
provide a distinguishing flag or seperate method.

TODO: how do we implement this? Mapping interval positions is not sufficient.

What if we would have different phases/stages of replacements? I.e. insertions would come later
than substitutions. Ideally we wouldn't have to do any work to add a new phase, since we would
just apply the same code with different substitutions.

How would you define and hook into these layers? Currently there are conceal events, and the
remaining applications were done on the fly in the userinterface.
Some possibilities.
1. Define a ordering space of doubles, such that some function can hook into a number.
All functions are then executed in the order of their numbers.
2. Predefine a set of events. For each new application a patch would be needed.
3. Create a list of "events". This list could be modified by plugins.


Abstraction
-----------

We can view all these replacements as text operations/transformations.
The only addition here is that we have to be able to specify more information as to how
intervals are mapped across the transformations.

The other enhancement we need is that we can do proper transformations on just a part of
the text, for performance reasons.
"""
from math import ceil
from bisect import bisect_left
from logging import debug

from .selection import Interval, Selection
from .contract import post
from .navigation import (
    move_n_wrapped_lines_down, count_wrapped_lines, next_beg_of_wrapped_line)


def _compute_selectionview_post(result, self, old=None, new=None):
    for vbeg, vend in result:
        assert 0 <= vbeg <= vend <= len(self.text)

# TODO: make textview thread-safe
# TODO: find a way to statically prevent thread errors


# TODO: rewrite this. Don't need the partial position mappings anymore, since we have the
# intervalmapping, which has an output sensitive running time. We want to store the resulting
# viewable text as a string. How to construct this text? Create a class that views a part of
# a text. I.e. it stores the part as a string and translates the positions automatically. It
# should raise an exception if a part of the text is accessed outside the range of this view.
# This class should behave as a normal text though. That way it can be passed to a
# TextTransformation which constructs a derived text from this.
class TextView:

    """
    Comprise the text features that are shown in the userinterface for a given text
    interval. All the positions in the resulting text are adjusted w.r.t. the text
    concealments that may have been done.

    How does a UI known when a new TextView should be created? A TextView object consists
    of 3 parts w.r.t. to a text interval: - the text (including concealments) - selection
    - highlighting

    So if either the, start, length, text, selection, highlighting or concealment changes,
    the userinterface should create a new TextView object. However, if jus the selection
    of highlighting changes, one only should have to update those. This is currently
    possible by calling compute_highlighting or compute_highlighting.

    Positional computations often have to deal with two kinds of positions: position
    in the original text and in the resulting view text. For clarity we prepend every
    variable containing information relative to the original text with `o` and relative to
    the view text with `v`.

    It should be noted that original positions in origpos_to_viewpos are counted from the
    given offset, i.e. the list is zero-indexed. TODO: make this bijection a separate
    object which hides these ugly and confusing offset differences.
    """

    def __init__(self):
        self.doc = None
        self.width = None
        self.height = None
        self.offset = None

        self.text = None
        self.selection = None
        self.highlighting = None

        self.viewpos_to_origpos = []
        self.origpos_to_viewpos = []

    @staticmethod
    def for_screen(doc, width: int, height: int, offset: int):
        """
        Construct a textview for the given doc starting with (and relative to) position
        start with size of the given length.
        """
        if width <= 0:
            raise ValueError('{} is an invalid width'.format(width))
        if height <= 0:
            raise ValueError('{} is an invalid height'.format(height))
        if offset < 0 or offset > len(doc.text):
            raise ValueError('{} is an invalid offset'.format(offset))

        self = TextView()
        self.doc = doc
        self.width = width
        self.height = height
        self.offset = offset

        self.text, self.origpos_to_viewpos, self.viewpos_to_origpos = (
            self._compute_text_from_view_interval())
        self.selection = self._compute_selection()
        self.highlighting = self._compute_highlighting()

        return self

    @staticmethod
    def for_entire_text(doc, width):
        if width <= 0:
            raise ValueError('{} is an invalid width'.format(width))

        self = TextView()
        self.doc = doc
        self.width = width
        self.offset = 0

        self.text, self.origpos_to_viewpos, self.viewpos_to_origpos = (
            self._compute_text_from_orig_interval(0, len(doc.text)))
        self.selection = self._compute_selection()
        self.highlighting = self._compute_highlighting()

        return self

    def text_as_lines(self):
        """
        Return the text in the textview as a list of lines, where the lines are wrapped
        with self.width.
        """
        result = [line[self.width * i: self.width * (i + 1)]
                  for line in self.text.splitlines()
                  for i in range(ceil(len(line) / self.width))]
        assert len(result) == count_wrapped_lines(self.text, self.width)
        return result

    def _compute_text_from_view_interval(self):
        """
        Compute the concealed text and the corresponding position mapping.
        We don't have any guarantees to the length of the viewtext in terms of the length
        of the original text whatsoever.
        So we can only incrementally try to increase the length of th original text, until
        the viewtext covers the required length.
        Since normally the concealed text is not much (if any) larger, this should not
        lead to accidentally computing a way too large textview.

        Return text and mappings.
        Side effect: none
        """
        width, height = self.width, self.height

        otext = self.doc.text
        obeg = self.offset
        if len(otext) - obeg == 0:
            return '', [0], [0]
        elif len(otext) - obeg < 0:
            raise ValueError('offset is beyond length of text')

        # Length of the sample of the original text that is used to compute the view text
        o_sample_length = 1

        vtext, opos_to_vpos, vpos_to_opos = self._compute_text_from_orig_interval(
            obeg, o_sample_length)
        # The mapping should have synced offsets and be non empty, as o_sample_length > 0 and
        # len(text) > 0
        assert opos_to_vpos[0] >= 0
        while (count_wrapped_lines(vtext, width) < height
               and obeg + o_sample_length < len(otext)):
            o_sample_length *= 2
            vtext, opos_to_vpos, vpos_to_opos = self._compute_text_from_orig_interval(
                obeg, o_sample_length)

        # Everything should be snapped to exactly fit the required length.
        # This is to make textview behave as deterministic as possible, such that potential
        # indexing errors are identified soon.
        beg_last_line = move_n_wrapped_lines_down(vtext, width, 0, height - 1)
        required_length = next_beg_of_wrapped_line(vtext, width, beg_last_line)
        # If the last line is not wrapped and has no eol character, it is the last line in the
        # file, so the next_beg_of_wrapped_line will fail and the required_length should equal
        # the length of vtext
        if required_length == beg_last_line:
            required_length = len(vtext)

        # Assert that we do not have to snap no more then half,
        # otherwise we did too much work
        assert required_length > len(vtext) // 2

        # Extend mappings to allow (exclusive) interval ends to be mapped
        opos_to_vpos.append(len(vtext))
        vpos_to_opos.append(o_sample_length)

        text = vtext[:required_length]
        origpos_to_viewpos = opos_to_vpos[:required_length + 1]
        # FIXME: what should this be?
        # viewpos_to_origpos = vpos_to_opos[:required_length + 1]
        viewpos_to_origpos = vpos_to_opos

        # Some post conditions
        assert len(text) == required_length, '{} != {}'.format(len(text), required_length)
        assert len(origpos_to_viewpos) == required_length + 1
        # assert len(viewpos_to_origpos) == required_length + 1

        return text, origpos_to_viewpos, viewpos_to_origpos

    def _compute_text_from_orig_interval(self, obeg, o_sample_length):
        """
        Compute the concealed text and the corresponding position mapping from an interval
        in terms of the original text.

        Return text and mappings.
        Side effect: none
        """
        conceal = self.doc.conceal
        conceal.generate_local_substitutions(obeg, o_sample_length)

        # Construct a sorted list of relevant substitutions
        first_global_subst = bisect_left(conceal.global_substitutions,
                                         (Interval(obeg, obeg), ''))
        last_global_subst = bisect_left(conceal.global_substitutions,
                                        (Interval(obeg + o_sample_length,
                                                  obeg + o_sample_length), ''))
        substitutions = (conceal.local_substitutions
                         + conceal.global_substitutions[first_global_subst:last_global_subst])
        substitutions.sort()

        vtext_builder = []  # Stringbuilder for text to be displayed
        vpos = 0  # Current position in view text, i.e. olength of text builded so far
        opos = obeg  # Current position in original text
        vpos_to_opos = []  # Mapping from view positions to original positions
        # Mapping from original positions (minus offset) to view positions
        opos_to_vpos = []
        otext = self.doc.text

        subst_index = 0
        while opos < obeg + o_sample_length:
            # Add remaining non-concealed text
            if subst_index >= len(substitutions):
                olength = min(o_sample_length - (opos - obeg), len(otext) - (opos - obeg))
                vpos_to_opos.extend(range(opos, opos + olength))
                opos_to_vpos.extend(range(vpos, vpos + olength))
                vtext_builder.append(otext[opos:opos + olength])
                opos += olength
                vpos += olength
                break

            # sbeg and send are in terms of original positions
            (sbeg, send), replacement = substitutions[subst_index]

            # Add non-concealed text
            if sbeg > opos:
                # Bound viewtext by o_sample_length
                olength = min(sbeg - opos, o_sample_length - vpos)
                vpos_to_opos.extend(range(opos, opos + olength))
                opos_to_vpos.extend(range(vpos, vpos + olength))
                vtext_builder.append(otext[opos:opos + olength])
                vpos += olength
                opos += olength
            # Add concealed text
            else:
                vlength = len(replacement)
                olength = send - sbeg
                vpos_to_opos.extend(vlength * [opos])
                opos_to_vpos.extend(olength * [vpos])
                vtext_builder.append(replacement)
                vpos += vlength
                opos += olength
                subst_index += 1

        vtext = ''.join(vtext_builder)

        # Extend mappings to allow (exclusive) interval ends to be mapped
        opos_to_vpos.append(len(vtext))
        vpos_to_opos.append(o_sample_length)

        # Some post conditions
        # assert len(text) == required_length
        # assert len(origpos_to_viewpos) == required_length + 1
        # assert len(viewpos_to_origpos) == required_length + 1

        return vtext, opos_to_vpos, vpos_to_opos

    def _compute_highlighting(self):
        """
        Construct highlighting view.
        The highlighting view is a mapping from each character in the text to a string.
        Since the text positions are positive integers starting from zero, we implement
        this as a list.
        Return highlighting view
        Side effect: None
        """
        highlightingview = []
        for i in range(len(self.text)):
            opos = self.viewpos_to_origpos[i]
            if opos in self.doc.highlighting:
                highlightingview.append(self.doc.highlighting[opos])
            else:
                highlightingview.append('')

        return highlightingview

    @post(_compute_selectionview_post)
    def _compute_selection(self, old=None, new=None):
        """
        Construct selection view.
        Use the opos_to_vpos mapping to derive the selection intervals in the viewport.
        Return selection view
        Side effect: None
        """
        opos_to_vpos = self.origpos_to_viewpos
        assert len(opos_to_vpos) == len(self.text) + 1
        o_viewbeg = self.viewpos_to_origpos[0]
        o_viewend = self.viewpos_to_origpos[-1] #[len(self.text)]

        selectionview = Selection()
        for beg, end in self.doc.selection:
            # Only add selections when they are in the TextView range
            if (beg < o_viewend and o_viewbeg < end
                    # Make sure empty intervals are taken into account
                    or beg == end == o_viewbeg or beg == end == o_viewend):
                beg = max(beg, o_viewbeg)
                end = min(o_viewend, end)
                assert beg <= end
                offset = self.offset
                vbeg = opos_to_vpos[beg - self.offset]
                # Even though end is exclusive, and may be outside the text, it is being
                # mapped, so we can safely do this
                vend = opos_to_vpos[end - self.offset]
                selectionview.add(Interval(vbeg, vend))

        return selectionview
