"""Tests for the canonical formatter.

Four properties carry the whole contract, and each has its own group
below: formatting is idempotent, it is byte-exact on canonical input, it
preserves meaning, and it hands back anything it cannot re-emit — a
syntax error, a comment — instead of writing over the user's file.

The meaning check compares the statement trees with their line numbers
dropped. Line numbers are where a statement was typed, and canonical
form moves statements to other lines on purpose, so comparing them would
assert that formatting changes nothing at all rather than that it
changes no meaning.
"""

import os
import sys
import unittest
from dataclasses import fields, is_dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ine.autocomplete import complete
from ine.formatter import format_program
from ine.lexer import lex
from ine.parser import parse


def meaning(source: str):
    """The statement tree of `source` with every line number removed.

    Written out independently of the formatter's own comparison so that
    the test asserts the contract rather than restating the code: two
    programs with the same `meaning` differ only in where their
    statements sit.
    """

    def strip(value):
        if is_dataclass(value) and not isinstance(value, type):
            return tuple(
                (field.name, strip(getattr(value, field.name)))
                for field in fields(value)
                if field.name != "line"
            )
        if isinstance(value, (list, tuple)):
            return tuple(strip(item) for item in value)
        return value

    return [strip(statement) for statement in parse(lex(source))]


# A program in canonical form: one statement per line, the body of each
# `make` indented 4 spaces, a blank line between the groups, one `say`
# line standing on its own, and exactly one newline at the end.
CANONICAL = '''\
make page
    page title "Company Name"

make header
    header inside page

make logo
    logo text "Company Name"
    logo inside header

say page title
'''

# The same program as it might actually be typed: no indentation, no
# blank lines, ragged spacing, and a blank line where none belongs.
MESSY = '''\
make page
page title "Company Name"
make header
   header inside page


make logo
        logo text "Company Name"
logo inside header
say page title
'''

# Programs that lex and parse, used for the idempotence and meaning
# checks. Every construct the grammar has is in here: a bare `make`, a
# named kind, a numbered `make`, a property with a string and with a
# number, an `inside`, a `say` of a value, a `say` of a reference, and a
# group.
SAMPLES = {
    "canonical": CANONICAL,
    "messy": MESSY,
    "bare make": "make card\n",
    "named kind": "make badge card\nbadge title \"New\"\n",
    "numbered make": "make 3 card\n",
    "string property": "card text \"hello world\"\n",
    "number property": "card width 12\n",
    "float property": "card width 1.5\n",
    "inside": "header inside page\n",
    "say value": "say \"hello\"\n",
    "say reference": "say page title\n",
    "say number": "say 42\n",
    "group": "group cards = card-1 card-2 card-3\n",
    "two says": "say \"a\"\nsay \"b\"\n",
    "ordered mix": "make card\ncard text \"a\"\nmake header\nheader inside card\n",
    "many subjects": "make page\nmake header\nheader inside page\nmake card\ncard inside page\n",
}

# Source that does not lex or parse. A formatter is the last thing that
# should touch a file it cannot read.
BROKEN = {
    "keyword alone": "make\n",
    "property without a value": "card padding\n",
    "unterminated string": "card text \"oops\n",
    "stray character": "make card\ncard text @\n",
    "empty line inside a statement": "make\n\ncard\n",
    "extra text": "make card extra words here\n",
    "bad number": "card width 1.2.3\n",
}


class CanonicalFormTests(unittest.TestCase):
    """Canonical source formats to itself, byte for byte."""

    def test_canonical_sample_is_byte_exact(self):
        self.assertEqual(format_program(CANONICAL), CANONICAL)

    def test_messy_sample_becomes_the_canonical_sample(self):
        self.assertEqual(format_program(MESSY), CANONICAL)

    def test_body_is_indented_four_spaces(self):
        text = format_program("make logo\nlogo text \"x\"\nlogo inside header\n")
        self.assertEqual(
            text,
            "make logo\n"
            "    logo text \"x\"\n"
            "    logo inside header\n",
        )

    def test_a_blank_line_separates_groups(self):
        text = format_program("make page\nmake header\n")
        self.assertEqual(text, "make page\n\nmake header\n")

    def test_a_say_line_stands_alone(self):
        text = format_program("say \"a\"\nsay \"b\"\n")
        self.assertEqual(text, "say \"a\"\n\nsay \"b\"\n")

    def test_ends_with_exactly_one_newline(self):
        text = format_program("make card\n\n\n\n")
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_no_line_ends_in_a_space(self):
        for sample in SAMPLES.values():
            for line in format_program(sample).splitlines():
                self.assertEqual(line, line.rstrip())

    def test_a_bare_make_keeps_its_short_form(self):
        # `make card` declares card as its own kind. The kind is written
        # back only when the source named a second word for it.
        self.assertEqual(format_program("make  card\n"), "make card\n")

    def test_a_named_kind_keeps_both_words(self):
        self.assertEqual(format_program("make  badge   card\n"), "make badge card\n")

    def test_a_group_stays_on_one_line(self):
        text = format_program("group cards = card-1   card-2\n")
        self.assertEqual(text, "group cards = card-1 card-2\n")


class IdempotenceTests(unittest.TestCase):
    """Formatting twice is formatting once."""

    def test_every_sample_is_idempotent(self):
        for name, sample in SAMPLES.items():
            once = format_program(sample)
            self.assertEqual(format_program(once), once, name)

    def test_the_canonical_sample_is_a_fixed_point(self):
        self.assertEqual(format_program(format_program(CANONICAL)), CANONICAL)

    def test_layout_does_not_survive_into_the_output(self):
        # Two typings of one program reach the same bytes, which is what
        # makes the formatter deterministic rather than merely stable.
        self.assertEqual(format_program(MESSY), format_program(CANONICAL))


class MeaningTests(unittest.TestCase):
    """Normalization never changes what the program says."""

    def test_every_sample_keeps_its_meaning(self):
        for name, sample in SAMPLES.items():
            self.assertEqual(meaning(format_program(sample)), meaning(sample), name)

    def test_a_numbered_make_expands_to_the_entities_it_declares(self):
        text = format_program("make 3 card\n")
        self.assertEqual(
            text, "make card-1 card\n\nmake card-2 card\n\nmake card-3 card\n"
        )
        self.assertEqual(meaning(text), meaning("make 3 card\n"))

    def test_a_string_keeps_its_hash(self):
        # `#` starts a comment in source, but not inside a string: the
        # formatter must not mistake one for the other.
        text = format_program('card text "a#b"\n')
        self.assertEqual(text, 'card text "a#b"\n')
        self.assertEqual(meaning(text), meaning('card text "a#b"\n'))

    def test_a_string_keeps_its_spacing(self):
        text = format_program('card text "  two  spaces  "\n')
        self.assertEqual(meaning(text), meaning('card text "  two  spaces  "\n'))

    def test_a_float_keeps_its_value(self):
        for source in ('card width 1.5\n', 'card width 0.1\n', 'card width 1e3\n'):
            text = format_program(source)
            self.assertEqual(meaning(text), meaning(source), source)


class UnreadableSourceTests(unittest.TestCase):
    """Source the formatter cannot re-emit comes back untouched."""

    def test_broken_source_is_untouched(self):
        for name, sample in BROKEN.items():
            self.assertEqual(format_program(sample), sample, name)

    def test_an_empty_file_is_untouched(self):
        self.assertEqual(format_program(""), "")

    def test_a_file_of_blank_lines_is_untouched(self):
        self.assertEqual(format_program("\n\n\n"), "\n\n\n")

    def test_a_commented_file_is_untouched(self):
        # The lexer drops comments, so the canonical form cannot hold
        # one. Re-emitting would delete the note; the file is handed
        # back whole instead. The editor formats on save, so this is the
        # difference between a formatter and a silent eraser.
        source = '# Homepage slice.\nmake page\npage title "x"\n'
        self.assertEqual(format_program(source), source)

    def test_an_inline_comment_is_untouched(self):
        source = 'make page # the root\npage title "x"\n'
        self.assertEqual(format_program(source), source)

    def test_a_comment_only_file_is_untouched(self):
        self.assertEqual(format_program("# just a note\n"), "# just a note\n")


class ProtocolTests(unittest.TestCase):
    """The editor's format query, end to end through `complete`."""

    def test_a_format_query_returns_the_canonical_text(self):
        result = complete({"format": True, "buffer": MESSY})
        self.assertTrue(result["format"])
        self.assertEqual(result["text"], CANONICAL)

    def test_a_format_query_echoes_the_id(self):
        result = complete({"format": True, "buffer": "make card\n", "id": 7})
        self.assertEqual(result["id"], 7)
        self.assertEqual(result["text"], "make card\n")

    def test_a_format_query_on_a_broken_buffer_returns_it(self):
        result = complete({"format": True, "buffer": "make\n"})
        self.assertEqual(result["text"], "make\n")

    def test_a_format_query_on_a_missing_buffer_is_empty(self):
        self.assertEqual(complete({"format": True}), {"format": True, "text": ""})

    def test_a_format_query_never_raises_on_a_non_string(self):
        self.assertEqual(
            complete({"format": True, "buffer": None}),
            {"format": True, "text": ""},
        )


if __name__ == "__main__":
    unittest.main()
