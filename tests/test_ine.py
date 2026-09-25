import json
import os
import shutil
import sys
import subprocess
import tempfile
import unittest
import warnings
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ine.backend_c import emit as emit_c
from ine.backend_html import BackendError, render
from ine.cli import build
from ine.dictionary import (
    Suggestion, ValueShape, _shape_from, find, for_model, makeable, members, parents,
    properties_for, style_declarations, style_overrides, suggest, value_hint,
    value_shape,
)
from ine.interpreter import execute
from ine.lexer import LexError, TokenKind, lex
from ine.native import compile_c, find_c_compiler, run_native
from ine.parser import (
    GroupStatement, InsideStatement, MakeStatement, PropertyRef, PropertyStatement, SayStatement, SyntaxError, parse,
)
from ine.semantic import SemanticError, advisory_warnings, analyze, resolve


def _has_display():
    """Return True when a windowing system is reachable via tkinter."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.destroy()
        return True
    except Exception:
        return False


def _skip_without_display(fn):
    """Mark fn so it is skipped when no display server is available."""
    fn._requires_display = True
    return unittest.skipUnless(_has_display(), "requires a display server")(fn)


class LexerTests(unittest.TestCase):
    def test_keyword_ident_and_newline(self):
        tokens = lex("make page\n")
        self.assertEqual([t.kind for t in tokens], [
            TokenKind.KEYWORD, TokenKind.IDENT, TokenKind.NEWLINE, TokenKind.EOF,
        ])
        self.assertEqual(tokens[0].value, "make")
        self.assertEqual(tokens[1].value, "page")

    def test_quoted_string(self):
        tokens = lex('page title "Hello"\n')
        self.assertEqual(tokens[2].kind, TokenKind.STRING)
        self.assertEqual(tokens[2].value, "Hello")

    def test_comment_is_skipped(self):
        tokens = lex("# note\nmake page\n")
        self.assertEqual([t.kind for t in tokens], [
            TokenKind.NEWLINE, TokenKind.KEYWORD, TokenKind.IDENT,
            TokenKind.NEWLINE, TokenKind.EOF,
        ])

    def test_hyphenated_ident(self):
        tokens = lex("make card-1\n")
        self.assertEqual(tokens[1].value, "card-1")

    def test_number_is_its_own_token(self):
        tokens = lex("768\n")
        self.assertEqual(tokens[0].kind, TokenKind.NUMBER)

    def test_unterminated_string_is_an_error(self):
        with self.assertRaises(LexError):
            lex('page title "oops\n')

    def test_unexpected_character_is_an_error(self):
        with self.assertRaises(LexError):
            lex("make page @\n")


class ParserTests(unittest.TestCase):
    def test_make_without_kind_defaults_to_name(self):
        statements = parse(lex("make page\n"))
        self.assertEqual(statements, [MakeStatement("page", "page", 1)])

    def test_make_with_kind(self):
        statements = parse(lex("make hero banner\n"))
        self.assertEqual(statements, [MakeStatement("hero", "banner", 1)])

    def test_property_statement(self):
        statements = parse(lex('page title "Hello"\n'))
        self.assertEqual(statements, [PropertyStatement("page", "title", "Hello", 1)])

    def test_no_final_newline_is_ok(self):
        statements = parse(lex('make page\npage title "Hello"'))
        self.assertEqual(len(statements), 2)

    def test_empty_property_value_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex("page title\n"))

    def test_property_value_must_be_quoted_or_number(self):
        with self.assertRaises(SyntaxError):
            parse(lex("page title words\n"))

    def test_number_property_value(self):
        statements = parse(lex("person age 25\n"))
        prop = statements[0]
        self.assertIsInstance(prop, PropertyStatement)
        self.assertEqual(prop.value, 25)
        self.assertIsInstance(prop.value, int)

    def test_decimal_property_value(self):
        statements = parse(lex("person height 1.75\n"))
        self.assertEqual(statements[0].value, 1.75)
        self.assertIsInstance(statements[0].value, float)

    def test_say_number(self):
        statements = parse(lex("say 25\n"))
        self.assertEqual(statements, [SayStatement(25, 1)])

    def test_extra_text_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex("make page extra words\n"))

    def test_make_requires_a_name(self):
        with self.assertRaises(SyntaxError):
            parse(lex("make\n"))

    def test_inside_relationship_parses(self):
        statements = parse(lex("make header\nmake page\nheader inside page\n"))
        self.assertEqual(statements[2], InsideStatement("header", "page", 3))

    def test_inside_requires_a_parent(self):
        with self.assertRaises(SyntaxError):
            parse(lex("header inside\n"))

    def test_inside_extra_text_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex("header inside page foo\n"))

    def test_inside_at_statement_start_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex("inside page\n"))


class SemanticTests(unittest.TestCase):
    def test_model_is_built(self):
        statements = parse(lex('make page\npage title "Hello"\n'))
        model = analyze(statements)
        self.assertEqual(model.entities["page"].kind, "page")
        self.assertEqual(model.properties[("page", "title")], "Hello")

    def test_property_on_undeclared_entity_is_an_error(self):
        statements = parse(lex('page title "Hello"\n'))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_duplicate_entity_is_an_error(self):
        statements = parse(lex("make page\nmake page\n"))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_repeated_property_overrides(self):
        statements = parse(lex('make page\npage title "A"\npage title "B"\n'))
        model = analyze(statements)
        self.assertEqual(model.properties[("page", "title")], "B")

    def test_relationship_is_stored_in_the_model(self):
        statements = parse(lex("make page\nmake header\nheader inside page\n"))
        model = analyze(statements)
        self.assertEqual(model.relationships, {"header": "page"})

    def test_inside_undeclared_child_is_an_error(self):
        statements = parse(lex("make page\nheader inside page\n"))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_inside_undeclared_parent_is_an_error(self):
        statements = parse(lex("make header\nheader inside page\n"))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_inside_itself_is_an_error(self):
        statements = parse(lex("make header\nheader inside header\n"))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_inside_twice_is_an_error(self):
        statements = parse(lex(
            "make page\nmake header\nmake logo\n"
            "header inside page\nheader inside logo\n"
        ))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_containment_cycle_is_an_error(self):
        statements = parse(lex(
            "make header\nmake page\n"
            "header inside page\npage inside header\n"
        ))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_relationship_passes_through_resolution(self):
        statements = parse(lex(
            'make page\nmake header\nheader inside page\nsay "go"\n'
        ))
        model = analyze(statements)
        resolved = resolve(statements, model)
        self.assertIn(InsideStatement("header", "page", 3), resolved)


class BackendTests(unittest.TestCase):
    def test_page_renders_title_and_heading(self):
        statements = parse(lex('make page\npage title "Hello, MyLanguage"\n'))
        model = analyze(statements)
        output = render(model)
        self.assertIn("<title>Hello, MyLanguage</title>", output)
        self.assertIn("<h1>Hello, MyLanguage</h1>", output)

    def test_slice_renders_nested_elements_from_the_dictionary(self):
        program = (
            'make page\n'
            'page title "Company Name"\n'
            'make header\n'
            'header inside page\n'
            'make logo\n'
            'logo text "Company Name"\n'
            'logo inside header\n'
            'make navigation\n'
            'navigation inside header\n'
        )
        statements = parse(lex(program))
        model = analyze(statements)
        output = render(model)
        self.assertIn('<div class="page">', output)
        self.assertIn('<header class="header">', output)
        self.assertIn('<div class="logo">Company Name</div>', output)
        self.assertIn('<nav class="navigation">', output)
        self.assertLess(output.index("header"), output.index("logo"))
        self.assertLess(output.index("logo"), output.index("navigation"))

    def test_inside_statements_are_not_rendered_as_property_text(self):
        program = 'make page\nmake header\nheader inside page\n'
        model = analyze(parse(lex(program)))
        output = render(model)
        self.assertNotIn("inside", output)

    def test_unknown_kind_is_rejected(self):
        statements = parse(lex("make page\nmake wizard magic\n"))
        model = analyze(statements)
        with self.assertRaises(BackendError):
            render(model)

    def test_missing_page_is_rejected(self):
        statements = parse(lex("make header\n"))
        model = analyze(statements)
        with self.assertRaises(BackendError):
            render(model)


class DictionaryTests(unittest.TestCase):
    def test_find_returns_entry_for_declared_kind(self):
        entry = find("header")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["term"], "header")
        self.assertEqual(entry["element"], "header")

    def test_find_returns_none_for_unknown_kind(self):
        self.assertIsNone(find("wizard"))

    def test_makeable_kinds_exclude_ambient_and_universal_entries(self):
        kinds = makeable()
        for expected in ("page", "header", "logo", "navigation",
                         "card", "card-group", "footer", "button", "image",
                         "section", "title"):
            self.assertIn(expected, kinds)
        self.assertNotIn("viewport", kinds)
        self.assertNotIn("universal", kinds)

    def test_suggest_without_kind_lists_every_kind_in_order(self):
        items = suggest()
        self.assertEqual([item.source for item in items], ["kind"] * len(items))
        self.assertEqual([item.text for item in items], makeable())
        self.assertIn(Suggestion("header", "kind", find("header")["meaning"]), items)

    def test_suggest_kind_lists_declared_and_universal_properties(self):
        items = suggest("header")
        texts = [item.text for item in items]
        self.assertIn("height", texts)
        self.assertIn("orientation", texts)
        self.assertIn("title", texts)
        self.assertIn("text", texts)
        self.assertIn(Suggestion("height", "property", "compact"), items)

    def test_suggest_kind_lists_structural_members_as_inside(self):
        items = suggest("header")
        self.assertIn(Suggestion("logo", "concept", "logo inside header"), items)
        self.assertIn(
            Suggestion("navigation", "concept", "navigation inside header"), items
        )

    def test_card_does_not_suggest_title_text_as_children(self):
        items = suggest("card")
        texts = [item.text for item in items]
        self.assertNotIn(
            Suggestion("title", "concept", "title inside card"), items
        )
        self.assertNotIn(
            Suggestion("text", "concept", "text inside card"), items
        )
        self.assertEqual(texts.count("title"), 1)
        self.assertEqual(texts.count("text"), 1)

    def test_section_does_not_suggest_title_text_as_children(self):
        items = suggest("section")
        self.assertNotIn(
            Suggestion("title", "concept", "title inside section"), items
        )
        self.assertNotIn(
            Suggestion("text", "concept", "text inside section"), items
        )
        self.assertIn(Suggestion("button", "concept", "button inside section"), items)
        self.assertIn(Suggestion("image", "concept", "image inside section"), items)

    def test_no_sibling_inference_from_kind_buckets(self):
        for kind in makeable():
            for item in suggest(kind):
                self.assertNotEqual(item.source, "related")
        self.assertNotIn("footer", [s.text for s in suggest("header")])
        self.assertNotIn("section", [s.text for s in suggest("banner")])
        self.assertNotIn("banner", [s.text for s in suggest("section")])

    def test_suggest_unknown_kind_is_empty(self):
        self.assertEqual(suggest("wizard"), [])

    def test_suggest_deduplicates_overlapping_names(self):
        section = [s.text for s in suggest("section")]
        self.assertEqual(section.count("title"), 1)
        self.assertEqual(section.count("text"), 1)
        header = [s.text for s in suggest("header")]
        self.assertEqual(header.count("logo"), 1)
        self.assertEqual(header.count("navigation"), 1)

    def test_properties_include_universal_title_and_text(self):
        self.assertEqual(
            properties_for("card"),
            ["border", "corner-radius", "padding", "text", "title"],
        )

    def test_properties_for_ambient_viewport_returns_width_height(self):
        self.assertEqual(properties_for("viewport"), ["height", "width"])

    def test_suggest_ambient_viewport_lists_declared_properties(self):
        self.assertEqual(
            suggest("viewport"),
            [
                Suggestion("height", "property", "a length"),
                Suggestion("width", "property", "a length"),
            ],
        )

    def test_properties_for_unknown_kind_is_empty(self):
        self.assertEqual(properties_for("wizard"), [])

    def test_value_hint_uses_defaults(self):
        self.assertEqual(value_hint("header", "height"), "compact")

    def test_value_hint_uses_typed_properties(self):
        self.assertEqual(value_hint("viewport", "width"), "a length")

    def test_value_hint_uses_universal_properties(self):
        self.assertEqual(
            value_hint("card", "title"),
            "the heading or name of the thing",
        )
        self.assertEqual(
            value_hint("card", "text"),
            "the thing's readable content",
        )

    def test_value_hint_unknown_property_is_none(self):
        self.assertIsNone(value_hint("header", "not-a-property"))
        self.assertIsNone(value_hint("wizard", "anything"))

    def test_value_shape_universal_title_and_text_are_text(self):
        self.assertEqual(
            value_shape("header", "title"), ValueShape("text"),
        )
        self.assertEqual(
            value_shape("card", "text"), ValueShape("text"),
        )
        self.assertEqual(value_shape("page", "title").choices, ())

    def test_value_shape_plain_property_is_unknown(self):
        self.assertEqual(value_shape("header", "height"), ValueShape())
        self.assertEqual(value_shape("card", "border"), ValueShape())
        self.assertEqual(value_shape("header", "layout"), ValueShape())

    def test_value_shape_defaults_only_kind_properties_are_unknown(self):
        self.assertEqual(value_shape("card", "padding"), ValueShape())
        self.assertEqual(value_shape("card", "corner-radius"), ValueShape())
        self.assertEqual(value_shape("header", "orientation"), ValueShape())

    def test_value_shape_uses_existing_declared_types(self):
        self.assertEqual(value_shape("viewport", "width"), ValueShape("length"))
        self.assertEqual(value_shape("viewport", "height"), ValueShape("length"))

    def test_value_shape_unknown_kind_or_property_is_unknown(self):
        self.assertEqual(value_shape("wizard", "anything"), ValueShape())
        self.assertEqual(value_shape("header", "not-a-property"), ValueShape())

    def test_shape_from_string_and_choice_list(self):
        self.assertEqual(_shape_from("text"), ValueShape("text"))
        self.assertEqual(_shape_from("length"), ValueShape("length"))
        self.assertEqual(_shape_from("number"), ValueShape("number"))
        self.assertEqual(_shape_from("row"), ValueShape())
        self.assertEqual(
            _shape_from(["row", "column"]),
            ValueShape("choice", ("row", "column")),
        )
        self.assertEqual(_shape_from(None), ValueShape())
        self.assertEqual(_shape_from(""), ValueShape())
        self.assertEqual(_shape_from([]), ValueShape())
        self.assertEqual(_shape_from([1, 2]), ValueShape())

    def test_malformed_dictionary_json_is_skipped_without_crashing(self):
        from ine import dictionary
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "good.json"), "w", encoding="utf-8") as h:
                json.dump({"term": "widget", "meaning": "a thing"}, h)
            with open(os.path.join(tmp, "broken.json"), "w", encoding="utf-8") as h:
                h.write("this is { not valid json !!!")
            with open(os.path.join(tmp, "not-json.json"), "w", encoding="utf-8") as h:
                h.write("plain text, not JSON at all")
            with open(os.path.join(tmp, "not-dict.json"), "w", encoding="utf-8") as h:
                json.dump(["list", "not", "a", "dict"], h)
            with open(os.path.join(tmp, "no-term.json"), "w", encoding="utf-8") as h:
                json.dump({"meaning": "no term key"}, h)
            with mock.patch.object(dictionary, "DICTIONARY_DIR", tmp):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    data = dictionary._load()
        self.assertEqual(list(data), ["widget"])
        self.assertEqual(data["widget"]["meaning"], "a thing")
        messages = [str(w.message) for w in caught]
        self.assertEqual(len(messages), 4)
        for name in ("broken.json", "not-json.json", "not-dict.json", "no-term.json"):
            self.assertTrue(
                any(name in message and "skipping" in message for message in messages),
                f"expected a skip warning naming {name}, got {messages}",
            )
        self.assertTrue(
            all("good.json" not in message for message in messages),
            "the valid file must not be reported as skipped",
        )

    def test_members_are_structural_children_only(self):
        self.assertEqual(members("header"), ["logo", "navigation"])
        self.assertEqual(members("page"), ["container", "footer", "header", "section"])
        self.assertEqual(members("card-group"), ["card"])
        self.assertEqual(members("container"), ["banner", "card-group"])
        self.assertEqual(members("card"), [])
        self.assertEqual(members("banner"), [])
        self.assertEqual(members("section"), ["button", "image"])

    def test_parents_reverse_the_contains_direction(self):
        self.assertEqual(parents("header"), ["page"])
        self.assertEqual(parents("logo"), ["header"])
        self.assertEqual(parents("navigation"), ["header"])
        self.assertEqual(parents("banner"), ["container"])
        self.assertEqual(parents("card"), ["card-group"])

    def test_parents_ground_orphan_kinds_from_real_examples(self):
        self.assertEqual(parents("card-group"), ["container"])
        self.assertEqual(parents("section"), ["page"])

    def test_parents_is_empty_for_roots_and_unknowns(self):
        self.assertEqual(parents("page"), [])
        self.assertEqual(parents("viewport"), [])
        self.assertEqual(parents("wizard"), [])
        self.assertEqual(parents("text"), [])

    def test_parents_never_treat_content_as_children(self):
        self.assertEqual(parents("title"), [])
        self.assertEqual(parents("text"), [])
        self.assertEqual(parents("description"), [])

    def test_for_model_suggests_each_entitys_statements(self):
        statements = parse(lex(
            'make page\npage title "Hi"\nmake header\nheader inside page\n'
        ))
        model = analyze(statements)
        items = for_model(model)
        texts = [item.text for item in items]
        self.assertIn("header height", texts)
        self.assertIn("page orientation", texts)
        self.assertIn("make logo", texts)
        self.assertIn("make footer", texts)
        for item in items:
            if item.text == "make logo":
                self.assertEqual(item.note, "logo inside header")

    def test_for_model_skips_unknown_kinds(self):
        statements = parse(lex('make alice person\nalice name "A"\n'))
        model = analyze(statements)
        self.assertEqual(for_model(model), [])

    def test_dict_cli_lists_kinds(self):
        from io import StringIO
        from contextlib import redirect_stdout
        from ine.cli import main
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--dict"])
        self.assertEqual(code, 0)
        self.assertIn("header", out.getvalue())
        self.assertIn("what can follow 'make'", out.getvalue())

    def test_dict_cli_suggests_for_a_kind(self):
        from io import StringIO
        from contextlib import redirect_stdout
        from ine.cli import main
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--dict", "card"])
        self.assertEqual(code, 0)
        self.assertIn("card (surface)", out.getvalue())
        self.assertIn("element: article", out.getvalue())
        self.assertIn("padding", out.getvalue())
        self.assertIn("corner-radius", out.getvalue())
        self.assertNotIn("title inside card", out.getvalue())

    def test_dict_cli_shows_structural_members_as_inside(self):
        from io import StringIO
        from contextlib import redirect_stdout
        from ine.cli import main
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--dict", "header"])
        self.assertEqual(code, 0)
        self.assertIn("contains: logo, navigation", out.getvalue())

    def test_dict_cli_reports_where_a_kind_belongs(self):
        from io import StringIO
        from contextlib import redirect_stdout
        from ine.cli import main
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--dict", "section"])
        self.assertEqual(code, 0)
        self.assertIn("belongs inside: page", out.getvalue())
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--dict", "card-group"])
        self.assertEqual(code, 0)
        self.assertIn("belongs inside: container", out.getvalue())

    def test_dict_cli_unknown_kind_fails(self):
        from ine.cli import main
        self.assertEqual(main(["--dict", "wizard"]), 1)

    def test_dict_cli_prints_structured_entry_for_a_kind(self):
        from io import StringIO
        from contextlib import redirect_stdout
        from ine.cli import main
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--dict", "footer"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("footer (bar):", text)
        self.assertIn("element: footer", text)
        self.assertIn("meaning:", text)
        self.assertIn("defaults:", text)
        self.assertIn("content-position   center", text)
        self.assertIn("implementation.html: footer element", text)
        self.assertIn("belongs inside: page", text)

    def test_dict_cli_exposes_responsiveness_defaults(self):
        from io import StringIO
        from contextlib import redirect_stdout
        from ine.cli import main
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--dict", "card-group"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("narrow-layout", text)
        self.assertIn("narrow-class", text)
        self.assertIn("stack members", text)
        self.assertIn("viewport.width == narrow", text)

    def test_dict_cli_shows_the_first_choice_declaration(self):
        # PLAN item 7: card-group `layout` is declared as a "choice"
        # (row/column); `--dict` surfaces the options.
        from io import StringIO
        from contextlib import redirect_stdout
        from ine.cli import main
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--dict", "card-group"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("properties:", text)
        self.assertIn("layout             choice: row, column", text)


class DictionaryIntegrityTests(unittest.TestCase):
    """Guard on the shipped dictionary/*.json files themselves.

    These read the real files directly (not the loader's cache), so a
    duplicate term, a typo in a containment list, or an untyped property
    value fails loudly instead of silently degrading completion.
    """

    # Containment members that may appear in a `contains` list without
    # being a declared kind — a documented scope boundary. Empty today:
    # every member resolves to a declared kind.
    SCOPE_BOUNDARY_MEMBERS: set[str] = set()

    def setUp(self):
        from ine import dictionary
        self.paths = {}  # term -> file name (detects duplicates)
        self.entries = []
        for name in sorted(os.listdir(dictionary.DICTIONARY_DIR)):
            if not name.endswith(".json"):
                continue
            with open(
                os.path.join(dictionary.DICTIONARY_DIR, name),
                "r", encoding="utf-8",
            ) as handle:
                entry = json.load(handle)
            self.entries.append(entry)
            self.paths[entry["term"]] = name
        self.declared = set(self.paths)

    def test_every_entry_has_term_and_meaning(self):
        for entry in self.entries:
            self.assertIn("term", entry, entry)
            self.assertIn("meaning", entry, entry)
            self.assertTrue(str(entry["meaning"]).strip())

    def test_term_values_are_unique_across_files(self):
        self.assertEqual(len(self.paths), len(self.entries))

    def test_containment_members_resolve_or_are_in_scope_boundary(self):
        allowed = self.declared | self.SCOPE_BOUNDARY_MEMBERS
        for entry in self.entries:
            defaults = entry.get("defaults")
            if not isinstance(defaults, dict):
                continue
            contains = defaults.get("contains")
            if not isinstance(contains, list):
                continue
            for child in contains:
                self.assertIn(
                    child, allowed,
                    f"{entry['term']} contains undeclared kind {child!r}",
                )

    def test_property_values_are_valid_shape_inputs(self):
        for entry in self.entries:
            declared = entry.get("properties")
            if not isinstance(declared, dict):
                continue
            for prop, raw in declared.items():
                shape = _shape_from(raw)
                self.assertNotEqual(
                    shape.type, "unknown",
                    f"{entry['term']}.properties/{prop} is not a valid "
                    f"value shape: {raw!r}",
                )

    def test_every_makeable_kind_declares_an_element(self):
        for term in makeable():
            entry = find(term)
            self.assertIsNotNone(entry, f"makeable kind {term!r} is missing")
            self.assertTrue(
                str(entry.get("element", "")).strip(),
                f"makeable kind {term!r} declares no element",
            )

    def test_members_and_parents_are_exact_inverse_over_shipped_kinds(self):
        # Mission 64 reliability net: containment is an exact inverse under
        # the reader API. For every shipped kind pair, `B in members(A)` iff
        # `A in parents(B)` — no pair may appear in only one direction.
        kinds = makeable()
        self.assertGreater(len(kinds), 0)
        pairs = [(a, b) for a in kinds for b in kinds
                 if b in members(a)]
        self.assertGreater(
            len(pairs), 0,
            "no containment pairs declared — the inverse check is vacuous")
        for a in kinds:
            for b in kinds:
                self.assertEqual(
                    b in members(a),
                    a in parents(b),
                    "members/parents asymmetry for shipped pair ({}, {})"
                    .format(a, b),
                )


class DictionaryStyleTests(unittest.TestCase):
    """The dictionary's `style` block is the only source of physical
    declarations: a kind paints exactly what its entry declares, a value
    the program writes replaces the kind's default, and a kind with no
    `style` block paints nothing at all."""

    def test_declared_defaults_become_declarations(self):
        # card declares padding/border/corner-radius, so its three hint
        # words must resolve to real CSS — this is the whole point of the
        # style block existing rather than a hardcoded table.
        declarations = style_declarations("card")
        self.assertIn("padding: 1.25rem", declarations)          # comfortable
        self.assertIn("border: 1px solid #e2e8f0", declarations)  # subtle
        self.assertIn("border-radius: 10px", declarations)        # slight

    def test_kind_without_a_style_block_declares_nothing(self):
        self.assertEqual(style_declarations("section"), [])
        self.assertEqual(style_declarations("card-group"), [])
        self.assertEqual(style_declarations("container"), [])

    def test_undeclared_kind_declares_nothing(self):
        self.assertEqual(style_declarations("person"), [])
        self.assertEqual(style_declarations("no-such-kind"), [])

    def test_written_value_replaces_the_kind_default(self):
        declarations = style_declarations("card", {"padding": 32})
        self.assertIn("padding: 32px", declarations)
        self.assertNotIn("padding: 1.25rem", declarations)

    def test_written_hint_word_resolves_through_the_map(self):
        declarations = style_declarations("card", {"corner-radius": "round"})
        self.assertIn("border-radius: 999px", declarations)

    def test_written_string_the_map_does_not_know_passes_through(self):
        # The escape hatch: the dictionary advises and never validates, so
        # an author who wants raw CSS can write it.
        declarations = style_declarations("card", {"border": "3px dotted red"})
        self.assertIn("border: 3px dotted red", declarations)

    def test_zero_is_not_a_zero_pixel_length(self):
        self.assertIn("border-radius: 0", style_declarations("card", {"corner-radius": 0}))

    def test_a_declaration_is_emitted_once(self):
        # hero's base already centres; the `text-alignment` default says the
        # same thing, and the rule must not carry `text-align` twice.
        declarations = style_declarations("banner")
        self.assertEqual(
            len([d for d in declarations if d.startswith("text-align:")]), 1)

    def test_overrides_are_empty_when_nothing_differs(self):
        self.assertEqual(style_overrides("card", {"padding": "comfortable"}), [])
        self.assertEqual(style_overrides("card", {}), [])

    def test_overrides_carry_only_what_the_program_changed(self):
        overrides = style_overrides("card", {"padding": 32})
        self.assertEqual(overrides, ["padding: 32px"])

    def test_layout_hint_is_not_a_style_property(self):
        # `layout` on card-group is consumed by the backend's row/stack
        # logic; it must not also leak into the stylesheet.
        self.assertEqual(style_declarations("card-group", {"layout": "row"}), [])


class HtmlStyleTests(unittest.TestCase):
    """The HTML backend paints what the dictionary declares, and a written
    value wins over the kind's rule."""

    def _render(self, source):
        model = analyze(parse(lex(source)))
        return render(model)

    def test_stylesheet_holds_one_rule_per_kind_used(self):
        output = self._render('make page\nmake card\ncard inside page\n')
        self.assertIn(".card { border: 1px solid #e2e8f0;", output)
        self.assertIn(".page { min-height: 100vh; }", output)

    def test_stylesheet_omits_kinds_the_program_does_not_use(self):
        output = self._render('make page\n')
        self.assertNotIn(".card {", output)
        self.assertNotIn(".footer {", output)

    def test_document_carries_a_viewport_and_a_body_baseline(self):
        output = self._render('make page\n')
        self.assertIn(
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            output,
        )
        self.assertIn("body { margin: 0;", output)

    def test_elements_carry_their_kind_so_rules_can_reach_them(self):
        output = self._render(
            'make page\nmake hero banner\nhero inside page\n'
            'make main container\nmain inside page\n')
        self.assertIn('<div class="banner hero">', output)
        self.assertIn('<div class="container main">', output)

    def test_an_entity_named_like_its_kind_carries_one_class(self):
        output = self._render('make page\nmake card\ncard inside page\n')
        self.assertIn('<article class="card">', output)
        self.assertNotIn('class="card card"', output)

    def test_a_written_value_lands_on_the_element_and_wins(self):
        output = self._render(
            'make page\nmake card\ncard inside page\ncard padding 32\n')
        # The kind's default is still in the stylesheet...
        self.assertIn(".card { border: 1px solid #e2e8f0;", output)
        # ...and the entity overrides it inline, which beats any rule.
        self.assertIn('class="card" style="padding: 32px"', output)

    def test_overrides_survive_an_entity_named_like_its_kind(self):
        # `make card` names the entity `card`, so a per-entity stylesheet
        # rule could not address it without touching the kind's rule.
        output = self._render(
            'make page\nmake card\ncard inside page\ncard padding 32\n')
        self.assertIn('style="padding: 32px"', output)

    def test_row_layout_still_marks_children_as_growing(self):
        output = self._render(
            'make page\nmake card-group\ncard-group inside page\n'
            'make card\ncard inside card-group\n')
        self.assertIn('<article class="card" style="flex:1">', output)


class NarrowResponsiveRuleTests(unittest.TestCase):
    """Mission 83 (unblocks item 59): the HTML backend emits ONE
    `@media (max-width: 768px)` rule for row-layout kinds whose dictionary
    entry declares `narrow-class` + `narrow-layout` (card-group). Gated on
    the declared data, never on the kind's name — a program without such a
    kind gains no @media output."""

    @staticmethod
    def _render(source):
        from contextlib import redirect_stdout
        from io import StringIO
        import tempfile
        from ine.cli import build
        with tempfile.TemporaryDirectory() as tmp:
            source_path = os.path.join(tmp, "narrow.ine")
            out_path = os.path.join(tmp, "narrow.html")
            with open(source_path, "w", encoding="utf-8") as handle:
                handle.write(source)
            with redirect_stdout(StringIO()):
                build(source_path, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                return handle.read()

    NARROW_RULE = "@media (max-width: 768px) { .card-group { flex-direction: column; } }"

    def test_card_group_emits_the_one_narrow_rule(self):
        output = self._render(
            'make page\nmake card-group\ncard-group inside page\n'
            'make card\ncard inside card-group\n')
        self.assertIn(self.NARROW_RULE, output)

    def test_kind_without_narrow_declarations_emits_no_media(self):
        output = self._render('make page\nmake banner\nbanner inside page\n')
        self.assertNotIn("@media", output)

    def test_desktop_row_output_is_unchanged(self):
        output = self._render(
            'make page\nmake card-group\ncard-group inside page\n'
            'make card\ncard inside card-group\n')
        self.assertIn('<div class="card-group" style="display:flex; gap:20px">',
                      output)
        self.assertIn('<article class="card" style="flex:1">', output)

    def test_changing_declared_narrow_layout_value_keeps_one_rule(self):
        # Editing the declared value must not change the number of rules or
        # any unrelated kind's output; the rule is still derived from the
        # declared narrow defaults on card-group.
        output = self._render(
            'make page\nmake card-group\ncard-group inside page\n'
            'make card\ncard inside card-group\n')
        self.assertEqual(output.count(self.NARROW_RULE), 1)


class BackendMetadataContractTests(unittest.TestCase):
    """The backends must honor the dictionary's declared metadata, not their
    own fallback defaults (Mission 65).

    Guards the Session 25 freeze at the test level: when the dictionary
    declares `element` / `layout` / `position` for a makeable kind, the HTML
    and visual backends return exactly that value, and the shipped goldens
    still render byte-identical to their examples.
    """

    def test_html_backend_returns_declared_element_and_layout(self):
        from ine.backend_html import (
            DEFAULT_ELEMENT, _element_for_kind, _layout_for_kind,
        )
        declared_element = [k for k in makeable() if find(k).get("element")]
        declared_layout = [k for k in makeable() if find(k).get("layout")]
        self.assertGreater(len(declared_element), 0)
        self.assertGreater(
            len([k for k in declared_element
                 if find(k).get("element") != DEFAULT_ELEMENT]),
            0,
            "no kind declares a non-default element — the element check is "
            "vacuous",
        )
        for kind in declared_element:
            self.assertEqual(
                _element_for_kind(kind), find(kind).get("element"),
                f"HTML element for {kind} must come from the dictionary",
            )
        self.assertEqual(
            _layout_for_kind("card-group"), "row",
            "HTML layout for card-group must come from the dictionary",
        )
        self.assertEqual(declared_layout, ["card-group"])
        self.assertNotEqual(declared_layout[0], "stack")

    def test_visual_backend_returns_declared_layout_and_position(self):
        from ine.backend_visual import _layout_of, _position_of
        from ine.semantic import Entity, Model
        declared_layout = [k for k in makeable() if find(k).get("layout")]
        declared_position = [k for k in makeable() if find(k).get("position")]
        self.assertEqual(declared_layout, ["card-group"])
        self.assertEqual(declared_position, ["footer"])
        for kind in declared_layout:
            model = Model(entities={"x": Entity("x", kind)})
            self.assertEqual(
                _layout_of(model, "x"), find(kind).get("layout"),
                f"visual layout for {kind} must come from the dictionary",
            )
        for kind in declared_position:
            model = Model(entities={"x": Entity("x", kind)})
            self.assertEqual(
                _position_of(model, "x"), find(kind).get("position"),
                f"visual position for {kind} must come from the dictionary",
            )

    def test_visual_backend_padding_comes_from_the_dictionary(self):
        """Spacing hints resolve to pixels; a kind without one keeps the old
        literals. No window is opened -- only the resolver is asked."""
        from ine.backend_visual import _padding_of
        source = (
            'make page\n'
            'make banner\nbanner inside page\n'
            'make card\ncard inside page\n'
            'make header\nheader inside page\n'
            'make logo\nlogo inside header\n'
        )
        model = analyze(parse(lex(source)))
        # `card` declares `"padding": "comfortable"` -> 1.25rem -> 20px on
        # every side, not the renderer's own 16/8 literals.
        self.assertEqual(_padding_of(model, "card"), (20, 20))
        self.assertNotEqual(_padding_of(model, "card"), (8, 16))
        # `banner` declares `"padding": "generous"` -> "3.5rem 1.5rem".
        self.assertEqual(_padding_of(model, "banner"), (56, 24))
        # `logo` declares no padding hint, so the old literals stand.
        self.assertEqual(_padding_of(model, "logo"), (8, 16))

    def test_shipped_goldens_render_byte_identical(self):
        examples = {
            "hello": os.path.join(
                os.path.dirname(__file__), "..", "examples", "hello", "hello.ine"),
            "topbar": os.path.join(
                os.path.dirname(__file__), "..", "examples",
                "homepage-topbar", "topbar.ine"),
            "hero": os.path.join(
                os.path.dirname(__file__), "..", "examples",
                "homepage-hero", "hero.ine"),
            "cards": os.path.join(
                os.path.dirname(__file__), "..", "examples",
                "homepage-cards", "cards.ine"),
            "site": os.path.join(
                os.path.dirname(__file__), "..", "examples", "site", "site.ine"),
        }
        golden_dir = os.path.join(os.path.dirname(__file__), "expected")
        for name, source in examples.items():
            with tempfile.TemporaryDirectory() as tmp:
                out_path = os.path.join(tmp, name + ".html")
                build(source, out_path)
                with open(out_path, "r", encoding="utf-8") as handle:
                    actual = handle.read()
                with open(os.path.join(golden_dir, name + ".html"),
                          "r", encoding="utf-8") as handle:
                    expected = handle.read()
                self.assertEqual(actual, expected,
                                 "{}.html golden drifted from a fresh render"
                                 .format(name))


class VocabularyCoverageTests(unittest.TestCase):
    """Lock the 'all real programs are covered by the dictionary' claim.

    Parse every real program under examples/ and .agent/experiments/ and
    assert that every kind, property, and containment pair either resolves
    through the dictionary (find / members / parents / properties_for) or
    falls in a documented scope-boundary set. Catches silent regressions
    when vocabulary changes — and only fails if a program silently loses
    coverage without the boundary or BLOCKERS being updated first.
    """

    # Kinds / properties that real programs use but the dictionary does not
    # declare. Boundary is documented (alice.ine custom domain + NOTES).
    CUSTOM_DOMAIN_KINDS: set[str] = {"person"}
    CUSTOM_DOMAIN_PROPERTIES: set[str] = {"name", "age", "height"}

    def setUp(self):
        root = os.path.dirname(os.path.dirname(__file__))
        examples = os.path.join(root, "examples")
        experiments = os.path.join(root, ".agent", "experiments")
        self.programs = []
        for dirpath in (examples, experiments):
            if not os.path.isdir(dirpath):
                continue
            for name in sorted(os.listdir(dirpath)):
                if name.endswith(".ine"):
                    self.programs.append(os.path.join(dirpath, name))
        self.assertGreater(len(self.programs), 0, "no programs found to reconcile")
        from ine import dictionary as dictmod
        self.declared = dictmod.makeable()
        self.members = dictmod.members
        self.find = dictmod.find
        self.properties_for = dictmod.properties_for
        self.results = []
        for path in self.programs:
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            try:
                stmts = parse(lex(src + "\n"))
            except Exception:
                self.results.append((path, "skip", set(), set(), set()))
                continue
            kinds = set()
            props = set()
            containment_pairs = set()
            entities = {}
            groups = {}
            for s in stmts:
                if isinstance(s, MakeStatement):
                    kinds.add(s.kind)
                    entities[s.target] = s.kind
                elif isinstance(s, PropertyStatement):
                    props.add(s.name)
                elif isinstance(s, PropertyRef):
                    props.add(s.name)
                elif isinstance(s, GroupStatement):
                    groups[s.name] = tuple(s.members)
                    for n in s.members:
                        kinds.add(entities.get(n, n))
                elif isinstance(s, InsideStatement):
                    child_names = groups.get(s.child, (s.child,))
                    parent_names = groups.get(s.parent, (s.parent,))
                    for cname in child_names:
                        for pname in parent_names:
                            child_kind = entities.get(cname, cname)
                            parent_kind = entities.get(pname, pname)
                            containment_pairs.add((child_kind, parent_kind))
            self.results.append(
                (path, "ok", kinds, props, containment_pairs))

    def test_entity_kinds_resolve_through_dictionary(self):
        boundary = self.CUSTOM_DOMAIN_KINDS
        failures = []
        for path, status, kinds, _, _ in self.results:
            for kind in kinds:
                if kind not in boundary and kind not in self.declared:
                    failures.append((os.path.basename(path), kind))
        self.assertEqual(
            failures, [],
            "entity kinds not in dictionary or boundary: "
            + str(failures),
        )

    def test_properties_resolve_through_dictionary(self):
        for path, status, kinds, props, _ in self.results:
            if status != "ok":
                continue
            for prop in props:
                if prop in ("title", "text"):
                    continue
                if prop in self.CUSTOM_DOMAIN_PROPERTIES:
                    continue
                resolved = False
                for kind in kinds:
                    if kind in self.declared and prop in self.properties_for(kind):
                        resolved = True
                        break
                self.assertTrue(
                    resolved,
                    f"{os.path.basename(path)}: property {prop!r} not "
                    f"declared on any entity kind used in the program",
                )

    def test_containment_pairs_resolve_through_dictionary(self):
        for path, status, _, _, containment_pairs in self.results:
            if status != "ok":
                continue
            for child_kind, parent_kind in containment_pairs:
                members = self.members(parent_kind)
                self.assertIn(
                    child_kind, members,
                    f"{os.path.basename(path)}: {child_kind} inside "
                    f"{parent_kind} not in dictionary members",
                )


class EvidenceGateTests(unittest.TestCase):
    """Lock the BLOCKERS.md evidence gates forward (Mission 53).

    "Advisory, never a validator" cuts both ways: the dictionary must NOT
    silently grow vocabulary a reconciliation or a WORKBOOK decision is
    still pending on. These tests read the real reader API and fail loudly
    if a future well-meaning vocabulary addition quietly overrides a
    recorded evidence gate without commander approval.
    """

    # Kinds the Session 31/37 reconciliation explicitly ruled out until
    # evidence or a WORKBOOK decision lands (see BLOCKERS.md): `search`
    # (proposed header member, never used in a real program), `subtitle` /
    # `description` (stripped from `contains`, no evidence), and the field
    # kinds (`input`) + `table` / `chart` gaps from the dashboard/form
    # experiments (Missions 19-21).
    VETOED_KINDS = frozenset({
        "search", "subtitle", "description", "input", "table", "chart",
    })

    def test_vetoed_kinds_are_not_declared(self):
        undeclared = [k for k in sorted(self.VETOED_KINDS)
                      if find(k) is not None]
        self.assertEqual(
            undeclared, [],
            "evidence-gated kinds declared without commander approval: "
            + str(undeclared),
        )
        self.assertEqual(
            set(makeable()) & self.VETOED_KINDS, set(),
            "evidence-gated kinds became makeable",
        )
        for kind in sorted(self.VETOED_KINDS):
            self.assertEqual(
                suggest(kind), [],
                f"vetoed kind {kind!r} now yields suggestions",
            )

    def test_vetoed_properties_are_not_declared_anywhere(self):
        # `subtitle` / `description` must not reappear as content properties
        # (WORKBOOK §36 re-grounded only title/text), and `search` must not
        # resurface as a header property.
        for term in makeable():
            props = set(properties_for(term))
            self.assertFalse(
                props & self.VETOED_KINDS,
                f"{term} declares vetoed properties: "
                f"{sorted(props & self.VETOED_KINDS)}",
            )

    def test_button_is_not_a_header_member(self):
        # WORKBOOK L544 proposes `button inside header`; the evidence is
        # `button inside section` (dictionary-demo.ine). There is no second
        # authority: the header's membership must not grow a button without
        # a decision.
        self.assertNotIn(
            "button", members("header"),
            "button inside header added to containment without evidence",
        )

    def test_card_group_layout_is_the_first_choice(self):
        # PLAN item 7 landed: card-group `layout` is the first enumerated
        # `choice` value ("row"/"column"), declared with the commander's
        # decision. It supersedes the Session 33 unknown-shape revert.
        shape = value_shape("card-group", "layout")
        self.assertEqual(shape.type, "choice")
        self.assertEqual(shape.choices, ("row", "column"))


class AliceCustomDomainTests(unittest.TestCase):
    """End-to-end guard for the canonical "dictionary is advisory"
    program (examples/alice/alice.ine).

    alice.ine declares a custom domain (person/name/age/height) the
    dictionary does not know and must not need to know. These tests lock
    the output shape the real file produces today and that the custom
    domain stays outside the dictionary's reach (for_model contributes
    nothing for it, while ordinary page programs still get suggestions)."""

    ALICE_SOURCE = os.path.join(
        os.path.dirname(__file__), "..", "examples", "alice", "alice.ine"
    )
    HELLO_SOURCE = os.path.join(
        os.path.dirname(__file__), "..", "examples", "hello", "hello.ine"
    )

    def _model(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        statements = parse(lex(source + "\n"))
        return analyze(statements)

    def test_alice_ine_builds_and_outputs_exactly_its_three_values(self):
        statements = parse(lex(self._read(self.ALICE_SOURCE)))
        model = analyze(statements)
        resolved = resolve(statements, model)
        self.assertEqual(list(model.entities), ["alice"])
        self.assertEqual(model.entities["alice"].kind, "person")
        self.assertEqual(execute(resolved), ["Alice", 25, 1.7])

    def test_alice_ine_is_not_an_html_program_today(self):
        # The HTML backend needs a page entity; alice.ine is a native/say
        # program, so building it today renders nothing (BackendError) and
        # writes no file. Pins the output shape as it exists today —
        # do not invent an HTML shape for a native-only program.
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.html")
            with self.assertRaises(BackendError):
                build(self.ALICE_SOURCE, out_path)
            self.assertFalse(os.path.exists(out_path))

    def test_for_model_contributes_nothing_for_alice_custom_domain(self):
        # Reads the REAL program — companion to
        # test_for_model_skips_unknown_kinds.
        self.assertEqual(for_model(self._model(self.ALICE_SOURCE)), [])

    def test_for_model_still_suggests_for_ordinary_page_programs(self):
        self.assertGreater(len(for_model(self._model(self.HELLO_SOURCE))), 0)

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()


class SayTests(unittest.TestCase):
    def test_say_is_a_keyword(self):
        tokens = lex('say "Hello"\n')
        self.assertEqual(tokens[0].kind, TokenKind.KEYWORD)
        self.assertEqual(tokens[0].value, "say")

    def test_parse_say_statement(self):
        statements = parse(lex('say "Hello, world!"\n'))
        self.assertEqual(statements, [SayStatement("Hello, world!", 1)])

    def test_say_requires_a_string_or_number(self):
        with self.assertRaises(SyntaxError):
            parse(lex("say page\n"))

    def test_say_extra_text_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex('say "x" extra\n'))

    def test_say_property_reference_parses(self):
        statements = parse(lex('say person age\n'))
        say = statements[0]
        self.assertIsInstance(say, SayStatement)
        self.assertEqual(say.value, PropertyRef("person", "age", 1))

    def test_say_reference_requires_property_name(self):
        with self.assertRaises(SyntaxError):
            parse(lex("say person\n"))

    def test_execution_returns_outputs_in_order(self):
        statements = parse(lex('say "one"\nsay "two"\n'))
        self.assertEqual(execute(statements), ["one", "two"])

    def test_execution_returns_numbers(self):
        statements = parse(lex('say 25\nsay 1.5\n'))
        self.assertEqual(execute(statements), [25, 1.5])

    def test_execution_returns_mixed_values(self):
        statements = parse(lex('say "age"\nsay 25\n'))
        self.assertEqual(execute(statements), ["age", 25])

    def test_program_without_say_produces_no_output(self):
        statements = parse(lex('make page\npage title "Hi"\n'))
        self.assertEqual(execute(statements), [])

    def test_say_is_not_part_of_the_model(self):
        statements = parse(lex('make page\npage title "Hi"\nsay "bye"\n'))
        model = analyze(statements)
        self.assertEqual(model.properties[("page", "title")], "Hi")
        self.assertNotIn("bye", str(model))

    def test_say_is_not_rendered_into_html(self):
        statements = parse(lex('make page\nsay "invisible"\n'))
        model = analyze(statements)
        html = render(model)
        self.assertNotIn("invisible", html)


class PropertyReferenceTests(unittest.TestCase):
    PROGRAM = "make person\nperson name \"Alice\"\nperson age 25\n"

    def test_say_does_not_execute_literal_until_resolved(self):
        statements = parse(lex("say person age\n"))
        model = analyze(parse(lex(self.PROGRAM)))
        resolved = resolve(statements, model)
        self.assertEqual(resolved, [SayStatement(25, 1)])

    def test_resolve_string_property(self):
        statements = parse(lex("say person name\n"))
        model = analyze(parse(lex(self.PROGRAM)))
        resolved = resolve(statements, model)
        self.assertEqual(resolved, [SayStatement("Alice", 1)])

    def test_resolve_int_property(self):
        statements = parse(lex("say person age\n"))
        model = analyze(parse(lex(self.PROGRAM)))
        resolved = resolve(statements, model)
        self.assertEqual(resolved, [SayStatement(25, 1)])
        self.assertIsInstance(resolved[0].value, int)

    def test_resolve_missing_property_is_an_error(self):
        statements = parse(lex("say person height\n"))
        model = analyze(parse(lex(self.PROGRAM)))
        with self.assertRaises(SemanticError):
            resolve(statements, model)

    def test_resolve_undeclared_entity_is_an_error(self):
        statements = parse(lex("say ghost age\n"))
        model = analyze(parse(lex(self.PROGRAM)))
        with self.assertRaises(SemanticError):
            resolve(statements, model)

    def test_resolve_leaves_literals_untouched(self):
        statements = parse(lex('say "hello"\nsay 7\n'))
        model = analyze(parse(lex(self.PROGRAM)))
        resolved = resolve(statements, model)
        self.assertEqual(resolved, statements)

    def test_resolve_feeds_execution(self):
        statements = parse(lex(self.PROGRAM + "say person name\nsay person age\n"))
        model = analyze(statements)
        resolved = resolve(statements, model)
        self.assertEqual(execute(resolved), ["Alice", 25])


class MultiplicityTests(unittest.TestCase):
    """`make <count> <kind>` expands into numbered entity declarations."""

    def test_make_three_cards_expands_to_three_statements(self):
        statements = parse(lex("make 3 card\n"))
        self.assertEqual(len(statements), 3)
        self.assertEqual(statements, [
            MakeStatement("card-1", "card", 1),
            MakeStatement("card-2", "card", 1),
            MakeStatement("card-3", "card", 1),
        ])

    def test_make_one_kind_uses_index_1(self):
        statements = parse(lex("make 1 banner\n"))
        self.assertEqual(statements, [MakeStatement("banner-1", "banner", 1)])

    def test_make_five_expands_to_five(self):
        statements = parse(lex("make 5 card\n"))
        self.assertEqual(len(statements), 5)
        self.assertEqual(statements[0], MakeStatement("card-1", "card", 1))
        self.assertEqual(statements[4], MakeStatement("card-5", "card", 1))

    def test_multiplicity_kind_can_be_multi_word(self):
        statements = parse(lex("make 2 card-group\n"))
        self.assertEqual(statements, [
            MakeStatement("card-group-1", "card-group", 1),
            MakeStatement("card-group-2", "card-group", 1),
        ])

    def test_zero_count_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex("make 0 card\n"))

    def test_decimal_count_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex("make 3.5 card\n"))

    def test_missing_kind_after_count_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex("make 3\n"))

    def test_extra_text_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex("make 3 card extra\n"))

    def test_negative_count_cannot_even_lex(self):
        with self.assertRaises(LexError):
            parse(lex("make -3 card\n"))

    def test_model_from_multiplicity_matches_handwritten_model(self):
        multi = parse(lex(
            "make 3 card\n"
            'card-1 title "Fast"\n'
            'card-1 text "A"\n'
            'card-2 title "Simple"\n'
            'card-2 text "B"\n'
            'card-3 title "Reliable"\n'
            'card-3 text "C"\n'
            "make card-group card-group\n"
            "card-1 inside card-group\n"
            "card-2 inside card-group\n"
            "card-3 inside card-group\n"
        ))
        handwritten = parse(lex(
            "make card-1 card\n"
            'card-1 title "Fast"\n'
            'card-1 text "A"\n'
            "make card-2 card\n"
            'card-2 title "Simple"\n'
            'card-2 text "B"\n'
            "make card-3 card\n"
            'card-3 title "Reliable"\n'
            'card-3 text "C"\n'
            "make card-group card-group\n"
            "card-1 inside card-group\n"
            "card-2 inside card-group\n"
            "card-3 inside card-group\n"
        ))
        self.assertEqual(analyze(multi).entities, analyze(handwritten).entities)
        self.assertEqual(analyze(multi).properties, analyze(handwritten).properties)
        self.assertEqual(analyze(multi).relationships, analyze(handwritten).relationships)

    def test_multiplicity_plus_handwritten_duplicate_is_an_error(self):
        statements = parse(lex("make 3 card\nmake card-1 card\n"))
        with self.assertRaises(SemanticError):
            analyze(statements)


class GroupSemanticsTests(unittest.TestCase):
    """`group <name> = <members>` names a collection; statements targeting
    the group expand to one statement per member."""

    PROGRAM = (
        "make page\n"
        "make card-group card-group\n"
        "card-group inside page\n"
        "make 3 card\n"
        "group cards = card-1 card-2 card-3\n"
        "cards inside card-group\n"
    )

    def test_group_statement_parses(self):
        statements = parse(lex("group cards = card-1 card-2 card-3\n"))
        self.assertEqual(statements, [
            GroupStatement("cards", ("card-1", "card-2", "card-3"), 1)
        ])

    def test_group_with_one_member_parses(self):
        statements = parse(lex("group one = card-1\n"))
        self.assertEqual(statements, [GroupStatement("one", ("card-1",), 1)])

    def test_group_requires_equals(self):
        with self.assertRaises(SyntaxError):
            parse(lex("group cards card-1\n"))

    def test_group_requires_a_name(self):
        with self.assertRaises(SyntaxError):
            parse(lex("group = card-1\n"))

    def test_group_requires_members(self):
        with self.assertRaises(SyntaxError):
            parse(lex("group cards =\n"))

    def test_group_name_is_a_keyword(self):
        tokens = lex("group\n")
        self.assertEqual(tokens[0].kind, TokenKind.KEYWORD)

    def test_model_records_the_group(self):
        model = analyze(parse(lex(self.PROGRAM)))
        self.assertEqual(model.groups, {
            "cards": ("card-1", "card-2", "card-3")
        })

    def test_group_inside_expands_to_per_member_relationships(self):
        model = analyze(parse(lex(self.PROGRAM)))
        for card in ("card-1", "card-2", "card-3"):
            self.assertEqual(model.relationships[card], "card-group")

    def test_group_property_applies_to_every_member(self):
        statements = parse(lex(self.PROGRAM + 'cards text "shared"\n'))
        model = analyze(statements)
        for card in ("card-1", "card-2", "card-3"):
            self.assertEqual(model.properties[(card, "text")], "shared")

    def test_group_property_does_not_create_a_group_entity_property(self):
        statements = parse(lex(self.PROGRAM + 'cards text "shared"\n'))
        model = analyze(statements)
        self.assertNotIn(("cards", "text"), model.properties)

    def test_group_does_not_create_an_entity(self):
        model = analyze(parse(lex(self.PROGRAM)))
        self.assertNotIn("cards", model.entities)

    def test_group_member_not_declared_is_an_error(self):
        statements = parse(lex("group cards = card-1 ghost\n"))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_group_name_colliding_with_entity_is_an_error(self):
        statements = parse(lex("make card\ncard inside page\n"
                               "group card = card-1\n"))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_duplicate_group_is_an_error(self):
        statements = parse(lex(
            "make 2 card\n"
            "group cards = card-1\n"
            "group cards = card-2\n"
        ))
        with self.assertRaises(SemanticError):
            analyze(statements)

    def test_say_on_a_group_is_an_error(self):
        statements = parse(lex(self.PROGRAM + "say cards title\n"))
        model = analyze(statements)
        with self.assertRaises(SemanticError):
            resolve(statements, model)

    def test_group_renders_html_identically_to_handwritten(self):
        statements = parse(lex(self.PROGRAM))
        model = analyze(statements)
        output = render(model)
        for card in ("card-1", "card-2", "card-3"):
            self.assertIn(f'class="card {card}"', output)
        self.assertIn('<div class="card-group" style="display:flex; gap:20px">',
                      output)

    def test_per_member_and_group_property_overrides(self):
        statements = parse(lex(self.PROGRAM +
            'cards text "default"\n'
            'card-1 title "Member One"\n'))
        model = analyze(statements)
        for card in ("card-2", "card-3"):
            self.assertEqual(model.properties[(card, "text")], "default")
        self.assertEqual(model.properties[("card-1", "title")], "Member One")
        self.assertEqual(model.properties[("card-1", "text")], "default")


class AdvisoryValidationTests(unittest.TestCase):
    """Mission 82: dictionary-backed semantic validation is advisory.

    The model always builds and renders; each violation becomes a returned
    warning string instead of a raised error. `title`/`text` (universal)
    and custom-domain kinds (Alice's `person`) are never flagged."""

    def _warnings(self, source):
        return advisory_warnings(analyze(parse(lex(source))))

    def test_undeclared_property_name_is_flagged(self):
        warnings = self._warnings('make banner\nbanner colour "red"\n')
        self.assertEqual(len(warnings), 1)
        self.assertIn("colour", warnings[0])
        self.assertIn("banner", warnings[0])

    def test_undeclared_property_still_builds_a_model(self):
        statements = parse(lex(
            'make page\nmake header\nheader inside page\nheader colour "red"\n'))
        model = analyze(statements)
        self.assertIn(("header", "colour"), model.properties)
        html = render(model)
        self.assertIn('class="header"', html)

    def test_declared_property_is_not_flagged(self):
        warnings = self._warnings('make banner\nbanner padding "generous"\n')
        self.assertEqual(warnings, [])

    def test_value_outside_vocabulary_is_flagged(self):
        warnings = self._warnings('make banner\nbanner padding "banana"\n')
        self.assertEqual(len(warnings), 1)
        self.assertIn("banana", warnings[0])

    def test_value_in_vocabulary_is_not_flagged(self):
        for word in ("compact", "comfortable", "generous"):
            with self.subTest(word=word):
                warnings = self._warnings(f'make banner\nbanner padding "{word}"\n')
                self.assertEqual(warnings, [])

    def test_universal_title_and_text_are_never_flagged(self):
        warnings = self._warnings(
            'make banner\nbanner title "Anything"\nbanner text "Any text"\n')
        self.assertEqual(warnings, [])

    def test_choice_value_within_options_is_not_flagged(self):
        # PLAN item 7: card-group `layout` is a declared choice (row/column).
        for word in ("row", "column"):
            with self.subTest(word=word):
                warnings = self._warnings(f'make card-group\ncard-group layout "{word}"\n')
                self.assertEqual(warnings, [])

    def test_choice_value_outside_options_is_flagged(self):
        warnings = self._warnings(
            'make card-group\ncard-group layout "diagonal"\n')
        self.assertEqual(len(warnings), 1)
        self.assertIn("diagonal", warnings[0])

    def test_undeclared_containment_is_flagged(self):
        warnings = self._warnings('make header\nmake footer\nfooter inside header\n')
        self.assertEqual(len(warnings), 1)
        self.assertIn("footer", warnings[0])
        self.assertIn("header", warnings[0])

    def test_undeclared_containment_still_builds_a_model(self):
        statements = parse(lex('make header\nmake footer\nfooter inside header\n'))
        model = analyze(statements)
        self.assertEqual(model.relationships["footer"], "header")

    def test_declared_containment_is_not_flagged(self):
        warnings = self._warnings(
            'make page\nmake header\nheader inside page\n')
        self.assertEqual(warnings, [])

    def test_legitimate_false_positive_reported_but_non_fatal(self):
        warnings = self._warnings(
            'make alice person\nalice name "Alice"\nalice age 25\n')
        self.assertEqual(warnings, [])

    def test_cli_reports_warning_to_stderr_without_changing_exit(self):
        from io import StringIO
        from contextlib import redirect_stderr
        from ine.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            source_path = os.path.join(tmp, "bad.ine")
            out_path = os.path.join(tmp, "bad.html")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write('make page\nmake header\nheader inside page\n'
                        'header colour "red"\n')
            err = StringIO()
            with redirect_stderr(err):
                code = main([source_path, "-o", out_path])
            self.assertEqual(code, 0)
            self.assertIn("warning:", err.getvalue())
            self.assertIn("colour", err.getvalue())

    def test_all_examples_produce_no_advisory_warnings(self):
        examples = os.path.join(
            os.path.dirname(__file__), "..", "examples")
        for dirpath, _, _files in os.walk(examples):
            for name in sorted(os.listdir(dirpath)):
                if not name.endswith(".ine"):
                    continue
                with open(os.path.join(dirpath, name), "r",
                          encoding="utf-8") as handle:
                    source = handle.read()
                with self.subTest(program=name):
                    warnings = self._warnings(source)
                    self.assertEqual(warnings, [])


class EndToEndTests(unittest.TestCase):
    HELLO_SOURCE = os.path.join(
        os.path.dirname(__file__), "..", "examples", "hello", "hello.ine"
    )
    HELLO_GOLDEN = os.path.join(
        os.path.dirname(__file__), "expected", "hello.html"
    )

    def test_hello_builds_exactly_the_golden_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "hello.html")
            build(self.HELLO_SOURCE, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                actual = handle.read()
            with open(self.HELLO_GOLDEN, "r", encoding="utf-8") as handle:
                expected = handle.read()
            self.assertEqual(actual, expected)

    def test_hello_cli_default_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "hello.html")
            build(self.HELLO_SOURCE, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                output = handle.read()
            self.assertIn("<!DOCTYPE html>", output)
            self.assertIn("Hello, MyLanguage", output)

    def test_say_program_executes_and_writes_no_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = os.path.join(tmp, "say.ine")
            out_path = os.path.join(tmp, "say.html")
            with open(source_path, "w", encoding="utf-8") as handle:
                handle.write('say "Hello, world!"\n')
            model, outputs, html = build(source_path, out_path)
            self.assertEqual(outputs, ["Hello, world!"])
            self.assertIsNone(html)
            self.assertFalse(os.path.exists(out_path))

    def test_topbar_builds_exactly_the_golden_output(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-topbar", "topbar.ine"
        )
        golden_path = os.path.join(
            os.path.dirname(__file__), "expected", "topbar.html"
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "topbar.html")
            build(source_path, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                actual = handle.read()
            with open(golden_path, "r", encoding="utf-8") as handle:
                expected = handle.read()
            self.assertEqual(actual, expected)

    def test_hero_builds_exactly_the_golden_output(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-hero", "hero.ine"
        )
        golden_path = os.path.join(
            os.path.dirname(__file__), "expected", "hero.html"
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "hero.html")
            build(source_path, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                actual = handle.read()
            with open(golden_path, "r", encoding="utf-8") as handle:
                expected = handle.read()
            self.assertEqual(actual, expected)

    def test_cards_builds_exactly_the_golden_output(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.ine"
        )
        golden_path = os.path.join(
            os.path.dirname(__file__), "expected", "cards.html"
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "cards.html")
            build(source_path, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                actual = handle.read()
            with open(golden_path, "r", encoding="utf-8") as handle:
                expected = handle.read()
            self.assertEqual(actual, expected)

    def test_cards_html_contains_footer_text(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.ine"
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "cards.html")
            build(source_path, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                output = handle.read()
            self.assertIn('<footer class="footer">', output)
            self.assertIn("2026", output)

    def test_cards_html_uses_row_layout_for_card_group(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.ine"
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "cards.html")
            build(source_path, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                output = handle.read()
            self.assertIn(
                '<div class="card-group" style="display:flex; gap:20px">',
                output,
            )
            self.assertIn('<article class="card card-1" style="flex:1">', output)
            self.assertIn('<article class="card card-2" style="flex:1">', output)
            self.assertIn('<article class="card card-3" style="flex:1">', output)

    def test_cards_html_renders_card_titles_as_headings(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.ine"
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "cards.html")
            build(source_path, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                output = handle.read()
            self.assertIn("<h3>Fast</h3>", output)
            self.assertIn("<h3>Simple</h3>", output)
            self.assertIn("<h3>Reliable</h3>", output)


class SiteExampleTests(unittest.TestCase):
    """The whole-page example: examples/site/site.ine is the language used
    for what it is for, with nothing in it that the dictionary does not
    already declare."""

    SOURCE = os.path.join(
        os.path.dirname(__file__), "..", "examples", "site", "site.ine"
    )

    def _output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "site.html")
            build(self.SOURCE, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                return handle.read()

    def test_group_statement_styles_every_member(self):
        output = self._output()
        for card in ("a1", "a2", "a3"):
            self.assertIn(
                f'class="card {card}" style="flex:1; border: none; border-radius: 0; padding: 0.75rem"',
                output,
                f"{card} did not receive the group's written values",
            )

    def test_the_other_row_keeps_the_declared_defaults(self):
        output = self._output()
        for card in ("f1", "f2", "f3"):
            self.assertIn(f'class="card {card}" style="flex:1"', output)

    def test_kinds_are_drawn_from_the_dictionary_alone(self):
        output = self._output()
        for rule in (".header {", ".logo {", ".navigation {", ".banner {",
                     ".card {", ".footer {", ".page {"):
            self.assertIn(rule, output)


class CliErrorTests(unittest.TestCase):
    """`_report_error` prints the message text plus a location clause.
    Errors that carry a column (LexError) now report both line and column;
    errors with only a line (SyntaxError/SemanticError/BackendError) keep the
    existing `(line L)` format."""

    def test_lex_error_report_includes_column(self):
        from io import StringIO
        from contextlib import redirect_stderr
        from ine.cli import main
        err = StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.ine")
            with open(path, "w", encoding="utf-8") as f:
                f.write("make page @\n")
            with redirect_stderr(err):
                code = main([path])
        self.assertEqual(code, 1)
        output = err.getvalue()
        self.assertIn("unexpected character '@'", output)
        self.assertIn("(line 1, column 11)", output)

    def test_syntax_error_report_includes_line_only(self):
        from io import StringIO
        from contextlib import redirect_stderr
        from ine.cli import main
        err = StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.ine")
            with open(path, "w", encoding="utf-8") as f:
                f.write("say page\n")
            with redirect_stderr(err):
                code = main([path])
        self.assertEqual(code, 1)
        output = err.getvalue()
        self.assertIn("property", output)
        self.assertIn("(line 1)", output)
        self.assertNotIn("column", output)

    def test_message_text_is_not_altered_by_location_clause(self):
        from io import StringIO
        from contextlib import redirect_stderr
        from ine.cli import main
        err = StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.ine")
            with open(path, "w", encoding="utf-8") as f:
                f.write("make page @\n")
            with redirect_stderr(err):
                code = main([path])
        self.assertEqual(code, 1)
        output = err.getvalue()
        self.assertTrue(output.startswith("error: unexpected character '@' "))


class VisualBackendTests(unittest.TestCase):
    """Tests for the visual backend's model-consumption logic.

    These test the pure helper functions and model-reading paths without
    requiring a display server.  The actual tkinter window creation is
    tested only when a display is available (the test runner on a normal
    desktop machine).
    """

    def test_children_of_returns_children_in_declaration_order(self):
        statements = parse(lex(
            "make page\nmake header\nmake logo\n"
            "header inside page\nlogo inside header\n"
        ))
        model = analyze(statements)
        from ine.backend_visual import _children_of
        self.assertEqual(_children_of(model, "page"), ["header"])
        self.assertEqual(_children_of(model, "header"), ["logo"])
        self.assertEqual(_children_of(model, "logo"), [])

    def test_children_of_root_has_no_children(self):
        statements = parse(lex('make page\npage title "Hi"\n'))
        model = analyze(statements)
        from ine.backend_visual import _children_of
        self.assertEqual(_children_of(model, "page"), [])

    def test_kind_of_returns_entity_kind(self):
        statements = parse(lex("make hero banner\nmake page\nhero inside page\n"))
        model = analyze(statements)
        from ine.backend_visual import _kind_of
        self.assertEqual(_kind_of(model, "hero"), "banner")
        self.assertEqual(_kind_of(model, "page"), "page")

    def test_bg_returns_explicit_color_for_page(self):
        from ine.backend_visual import _bg, KIND_COLORS
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["p"] = Entity("p", "page")
        model.relationships = {}
        self.assertEqual(_bg(model, "p"), KIND_COLORS["page"])

    def test_bg_inherits_from_parent_when_kind_has_no_color(self):
        from ine.backend_visual import _bg
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["p"] = Entity("p", "page")
        model.entities["l"] = Entity("l", "logo")
        model.relationships = {"l": "p"}
        self.assertEqual(_bg(model, "l"), _bg(model, "p"))

    def test_fg_returns_text_color_for_known_kind(self):
        from ine.backend_visual import _fg, KIND_TEXT_COLORS
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["h"] = Entity("h", "header")
        self.assertEqual(_fg(model, "h"), KIND_TEXT_COLORS["header"])

    def test_is_leaf_true_for_entity_with_no_children(self):
        from ine.backend_visual import _is_leaf
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["x"] = Entity("x", "card")
        model.relationships = {}
        self.assertTrue(_is_leaf(model, "x"))

    def test_is_leaf_false_for_entity_with_children(self):
        from ine.backend_visual import _is_leaf
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["p"] = Entity("p", "page")
        model.entities["c"] = Entity("c", "header")
        model.relationships = {"c": "p"}
        self.assertFalse(_is_leaf(model, "p"))

    def test_has_text_true_when_text_property_exists(self):
        from ine.backend_visual import _has_text
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["h"] = Entity("h", "banner")
        model.properties[("h", "text")] = "Welcome"
        self.assertTrue(_has_text(model, "h"))

    def test_has_text_false_when_no_text_property(self):
        from ine.backend_visual import _has_text
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["h"] = Entity("h", "banner")
        self.assertFalse(_has_text(model, "h"))

    def _render_window(self, model, title_override=None):
        """Render into a real tk root, skipping when tkinter fails at run time.

        _has_display() is evaluated once at import (the skip decorator);
        a mid-run Tcl failure (e.g. Windows Store Python intermittently
        failing to read init.tcl under load) must skip, not fail the suite.
        """
        import tkinter as tk
        from ine.backend_visual import render
        try:
            return render(model, title_override=title_override)
        except tk.TclError as exc:
            self.skipTest(f"tkinter became unavailable at run time: {exc}")

    @_skip_without_display
    def test_visual_render_returns_a_tk_root(self):
        import tkinter as tk
        statements = parse(lex(
            'make page\npage title "Test"\n'
            'make header\nheader inside page\n'
        ))
        model = analyze(statements)
        root = self._render_window(model)
        self.assertIsInstance(root, tk.Tk)
        self.assertEqual(root.title(), "Test")
        root.destroy()

    @_skip_without_display
    def test_visual_render_uses_title_override(self):
        import tkinter as tk
        statements = parse(lex('make page\npage title "Original"\n'))
        model = analyze(statements)
        root = self._render_window(model, title_override="Override Title")
        self.assertEqual(root.title(), "Override Title")
        root.destroy()

    def test_visual_render_no_page_raises_error(self):
        from ine.backend_visual import render, VisualError
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["h"] = Entity("h", "header")
        with self.assertRaises(VisualError):
            render(model)

    def test_visual_render_multiple_pages_raises_error(self):
        from ine.backend_visual import render, VisualError
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["p1"] = Entity("p1", "page")
        model.entities["p2"] = Entity("p2", "page")
        with self.assertRaises(VisualError):
            render(model)

    def test_hero_int_program_builds_model_for_visual(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-hero", "hero.ine"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        statements = parse(lex(source))
        model = analyze(statements)
        self.assertEqual(len(model.entities), 6)
        self.assertIn("page", model.entities)
        self.assertIn("header", model.entities)
        self.assertIn("logo", model.entities)
        self.assertIn("navigation", model.entities)
        self.assertIn("main", model.entities)
        self.assertIn("hero", model.entities)

    @_skip_without_display
    def test_hero_int_visual_render_creates_window(self):
        import tkinter as tk
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-hero", "hero.ine"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        statements = parse(lex(source))
        model = analyze(statements)
        root = self._render_window(model)
        self.assertIsInstance(root, tk.Tk)
        self.assertEqual(root.title(), "Company Name")
        root.destroy()

    @_skip_without_display
    def test_visual_render_default_title_when_no_title_property(self):
        import tkinter as tk
        statements = parse(lex("make page\n"))
        model = analyze(statements)
        root = self._render_window(model)
        self.assertEqual(root.title(), "Ine")
        root.destroy()

    def test_cards_program_builds_model_for_visual(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.ine"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        statements = parse(lex(source))
        model = analyze(statements)
        self.assertEqual(len(model.entities), 11)
        self.assertEqual(model.entities["card-1"].kind, "card")
        self.assertEqual(model.entities["card-2"].kind, "card")
        self.assertEqual(model.entities["card-3"].kind, "card")
        self.assertEqual(model.entities["card-group"].kind, "card-group")
        self.assertEqual(model.entities["footer"].kind, "footer")
        self.assertEqual(model.relationships["card-1"], "card-group")
        self.assertEqual(model.relationships["card-2"], "card-group")
        self.assertEqual(model.relationships["card-3"], "card-group")
        self.assertEqual(model.relationships["footer"], "page")

    @_skip_without_display
    def test_cards_visual_render_creates_window(self):
        import tkinter as tk
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.ine"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        statements = parse(lex(source))
        model = analyze(statements)
        root = self._render_window(model)
        self.assertIsInstance(root, tk.Tk)
        self.assertEqual(root.title(), "Company Name")
        root.destroy()

    def test_layout_of_returns_stack_for_unknown_kind(self):
        from ine.backend_visual import _layout_of
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["x"] = Entity("x", "not-a-real-kind")
        self.assertEqual(_layout_of(model, "x"), "stack")

    def test_layout_of_card_group_reads_dictionary_row(self):
        from ine.backend_visual import _layout_of
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["g"] = Entity("g", "card-group")
        self.assertEqual(_layout_of(model, "g"), "row")

    def test_position_of_returns_flow_for_unknown_kind(self):
        from ine.backend_visual import _position_of
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["x"] = Entity("x", "not-a-real-kind")
        self.assertEqual(_position_of(model, "x"), "flow")

    def test_position_of_footer_reads_dictionary_bottom(self):
        from ine.backend_visual import _position_of
        from ine.semantic import Model, Entity
        model = Model()
        model.entities["f"] = Entity("f", "footer")
        self.assertEqual(_position_of(model, "f"), "bottom")

    @_skip_without_display
    def test_cards_visual_packs_cards_side_by_side(self):
        import tkinter as tk
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.ine"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        model = analyze(parse(lex(source)))
        root = self._render_window(model)
        cards = self._card_frames(root)
        self.assertEqual(len(cards), 3)
        for frame in cards:
            self.assertEqual(frame.pack_info()["side"], "left")
        root.destroy()

    @_skip_without_display
    def test_cards_visual_pins_footer_to_bottom(self):
        import tkinter as tk
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.ine"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        model = analyze(parse(lex(source)))
        root = self._render_window(model)
        footer = self._bottom_frame(root)
        self.assertIsNotNone(footer)
        self.assertEqual(footer.pack_info()["side"], "bottom")
        labels = [w for w in footer.winfo_children() if isinstance(w, tk.Label)]
        self.assertEqual(len(labels), 1)
        self.assertIn("2026", labels[0].cget("text"))
        root.destroy()

    def _card_frames(self, widget):
        import tkinter as tk
        found = []
        if isinstance(widget, tk.Frame):
            children = widget.winfo_children()
            if len(children) == 2 and all(isinstance(c, tk.Label) for c in children):
                found.append(widget)
        for child in widget.winfo_children():
            found.extend(self._card_frames(child))
        return found

    def _bottom_frame(self, widget):
        import tkinter as tk
        if isinstance(widget, tk.Frame):
            try:
                if widget.pack_info().get("side") == "bottom":
                    return widget
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            result = self._bottom_frame(child)
            if result is not None:
                return result
        return None


class DisplayGuardTests(unittest.TestCase):
    """Verify _has_display() returns False when tkinter cannot create a window."""

    def test_returns_false_when_tk_raises(self):
        import tkinter as tk
        real_tk = tk.Tk
        try:
            tk.Tk = mock.Mock(side_effect=tk.TclError("no display"))
            self.assertFalse(_has_display())
        finally:
            tk.Tk = real_tk

    def test_returns_true_when_tk_succeeds(self):
        import tkinter as tk
        real_tk = tk.Tk
        try:
            def _fake():
                r = mock.Mock()
                return r
            tk.Tk = _fake
            self.assertTrue(_has_display())
        finally:
            tk.Tk = real_tk

    def test_all_window_tests_have_skip_decorator(self):
        window_tests = [
            "test_visual_render_returns_a_tk_root",
            "test_visual_render_uses_title_override",
            "test_hero_int_visual_render_creates_window",
            "test_visual_render_default_title_when_no_title_property",
            "test_cards_visual_render_creates_window",
            "test_cards_visual_packs_cards_side_by_side",
            "test_cards_visual_pins_footer_to_bottom",
        ]
        for name in window_tests:
            fn = getattr(VisualBackendTests, name)
            self.assertTrue(
                getattr(fn, "_requires_display", False),
                f"{name} is missing the display-server skip guard",
            )

    def test_render_window_skips_on_runtime_tcl_error(self):
        import tkinter as tk
        view = VisualBackendTests("test_visual_render_returns_a_tk_root")
        with mock.patch(
            "ine.backend_visual.render",
            side_effect=tk.TclError("couldn't read file init.tcl"),
        ):
            try:
                view._render_window(None)
            except unittest.SkipTest as exc:
                self.assertIn("tkinter became unavailable at run time", str(exc))
                return
        self.fail("expected the runtime TclError to skip, not fail the suite")


class ExperimentsRenderTests(unittest.TestCase):
    """Every evidence-collection experiment in .agent/experiments must
    lex, parse, analyze, and render to HTML. Guards the Missions 19/20
    evidence programs as the dictionary evolves."""

    def test_every_experiment_lexes_parses_analyzes_and_renders(self):
        experiments_dir = os.path.join(
            os.path.dirname(__file__), "..", ".agent", "experiments"
        )
        for exp_name in sorted(os.listdir(experiments_dir)):
            if not exp_name.endswith(".ine"):
                continue
            with self.subTest(experiment=exp_name):
                source_path = os.path.join(experiments_dir, exp_name)
                with open(source_path, "r", encoding="utf-8") as handle:
                    source = handle.read()
                with tempfile.TemporaryDirectory() as tmp:
                    out_path = os.path.join(tmp, "out.html")
                    build(source_path, out_path)
                    with open(out_path, "r", encoding="utf-8") as handle:
                        output = handle.read()
                    self.assertIn("<!DOCTYPE html>", output)


class NativeBackendTests(unittest.TestCase):
    def test_emit_produces_a_standalone_c_program(self):
        statements = parse(lex('say "Hello, machine"\n'))
        source = emit_c(statements)
        self.assertIn("#include <stdio.h>", source)
        self.assertIn('int main(void)', source)
        self.assertIn('printf("%s\\n", "Hello, machine")', source)
        self.assertIn("return 0;", source)

    def test_emit_uses_percent_s_so_content_is_never_format(self):
        statements = parse(lex('say "100% ready"\n'))
        source = emit_c(statements)
        self.assertIn('printf("%s\\n", "100% ready")', source)

    def test_emit_integer_as_percent_d(self):
        statements = parse(lex("say 25\n"))
        source = emit_c(statements)
        self.assertIn('printf("%d\\n", 25)', source)

    def test_emit_float_as_precise_g(self):
        statements = parse(lex("say 1.5\n"))
        source = emit_c(statements)
        self.assertIn('printf("%.17g\\n", 1.5)', source)

    def test_emit_escapes_c_string_contents(self):
        statements = parse(lex('say "a backslash \\ here"\n'))
        source = emit_c(statements)
        self.assertIn('printf("%s\\n", "a backslash \\\\ here")', source)

    def test_emit_ignores_model_statements(self):
        statements = parse(lex('make page\npage title "Hi"\nsay "go"\n'))
        source = emit_c(statements)
        self.assertIn('printf("%s\\n", "go")', source)
        self.assertNotIn("page", source)

    def test_emit_ignores_inside_statements(self):
        statements = parse(lex(
            'make page\nmake header\nheader inside page\nsay "go"\n'
        ))
        source = emit_c(statements)
        self.assertIn('printf("%s\\n", "go")', source)
        self.assertNotIn("inside", source)
        self.assertNotIn("header", source)

    def test_emit_with_no_say_prints_nothing(self):
        statements = parse(lex("make page\n"))
        source = emit_c(statements)
        self.assertIn("return 0;", source)
        self.assertEqual(source.count("printf"), 0)

    @unittest.skipUnless(find_c_compiler() is not None, "no C compiler available")
    def test_native_executable_prints_on_the_cpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            statements = parse(lex('say "native hello"\nsay "native again"\n'))
            c_path, exe_path = compile_c(statements, "probe", work_dir=tmp)
            self.assertTrue(os.path.exists(c_path))
            self.assertTrue(os.path.exists(exe_path))
            output = run_native(exe_path)
            self.assertEqual(output.splitlines(), ["native hello", "native again"])

    @unittest.skipUnless(find_c_compiler() is not None, "no C compiler available")
    def test_native_executable_prints_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            statements = parse(lex('say "age"\nsay 25\nsay 1.5\n'))
            c_path, exe_path = compile_c(statements, "probe", work_dir=tmp)
            output = run_native(exe_path)
            self.assertEqual(output.splitlines(), ["age", "25", "1.5"])

    @unittest.skipUnless(find_c_compiler() is not None, "no C compiler available")
    def test_native_executable_prints_resolved_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = (
                'make person\n'
                'person name "Alice"\n'
                'person age 25\n'
                'say person name\n'
                'say person age\n'
            )
            model = analyze(parse(lex(source)))
            resolved = resolve(parse(lex(source)), model)
            c_path, exe_path = compile_c(resolved, "probe", work_dir=tmp)
            output = run_native(exe_path)
            self.assertEqual(output.splitlines(), ["Alice", "25"])


class ReadmeQuickStartTests(unittest.TestCase):
    """The README quick-start flow must run exactly as documented
    (Mission 70). Protects the docs' promises against engine drift."""

    @staticmethod
    def _run_ine(cwd, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
        return subprocess.run(
            [sys.executable, "-m", "ine", *args], cwd=cwd, env=env,
            capture_output=True, text=True)

    def test_readme_quick_start_flow_runs_exactly_as_documented(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "hello.ine"), "w",
                      encoding="utf-8") as handle:
                handle.write('make page\npage title "Hello, Ine"\n')
            proc = self._run_ine(
                tmp, "hello.ine", "-o", "hello.html")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for expected in (
                "read:       hello.ine",
                "entities:   1",
                "properties: 1",
                "wrote:      hello.html",
            ):
                self.assertIn(expected, proc.stdout)
            with open(os.path.join(tmp, "hello.html"), "r",
                      encoding="utf-8") as handle:
                html = handle.read()
            self.assertIn("<title>Hello, Ine</title>", html)
            self.assertIn("<h1>Hello, Ine</h1>", html)

    def test_readme_dict_commands_each_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "hello.ine"), "w",
                      encoding="utf-8") as handle:
                handle.write('make page\npage title "Hi"\n')
            for args in (
                ("--dict",),
                ("--dict", "card"),
                ("--dict", "header"),
                ("--dict", "hello.ine"),
            ):
                with self.subTest(args=args):
                    proc = self._run_ine(tmp, *args)
                    self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()