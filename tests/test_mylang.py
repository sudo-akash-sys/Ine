import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mylang.backend_c import emit as emit_c
from mylang.backend_html import BackendError, render
from mylang.cli import build
from mylang.interpreter import execute
from mylang.lexer import LexError, TokenKind, lex
from mylang.native import compile_c, find_c_compiler, run_native
from mylang.parser import (
    InsideStatement, MakeStatement, PropertyRef, PropertyStatement, SayStatement, SyntaxError, parse,
)
from mylang.semantic import SemanticError, analyze, resolve


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


class EndToEndTests(unittest.TestCase):
    HELLO_SOURCE = os.path.join(
        os.path.dirname(__file__), "..", "examples", "hello", "hello.int"
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
            source_path = os.path.join(tmp, "say.int")
            out_path = os.path.join(tmp, "say.html")
            with open(source_path, "w", encoding="utf-8") as handle:
                handle.write('say "Hello, world!"\n')
            model, outputs, html = build(source_path, out_path)
            self.assertEqual(outputs, ["Hello, world!"])
            self.assertIsNone(html)
            self.assertFalse(os.path.exists(out_path))

    def test_topbar_builds_exactly_the_golden_output(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-topbar", "topbar.int"
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
            os.path.dirname(__file__), "..", "examples", "homepage-hero", "hero.int"
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
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.int"
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
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.int"
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
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.int"
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "cards.html")
            build(source_path, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                output = handle.read()
            self.assertIn(
                '<div class="card-group" style="display:flex;gap:20px">',
                output,
            )
            self.assertIn('<article class="card-1" style="flex:1">', output)
            self.assertIn('<article class="card-2" style="flex:1">', output)
            self.assertIn('<article class="card-3" style="flex:1">', output)

    def test_cards_html_renders_card_titles_as_headings(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.int"
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "cards.html")
            build(source_path, out_path)
            with open(out_path, "r", encoding="utf-8") as handle:
                output = handle.read()
            self.assertIn("<h3>Fast</h3>", output)
            self.assertIn("<h3>Simple</h3>", output)
            self.assertIn("<h3>Reliable</h3>", output)


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
        from mylang.backend_visual import _children_of
        self.assertEqual(_children_of(model, "page"), ["header"])
        self.assertEqual(_children_of(model, "header"), ["logo"])
        self.assertEqual(_children_of(model, "logo"), [])

    def test_children_of_root_has_no_children(self):
        statements = parse(lex('make page\npage title "Hi"\n'))
        model = analyze(statements)
        from mylang.backend_visual import _children_of
        self.assertEqual(_children_of(model, "page"), [])

    def test_kind_of_returns_entity_kind(self):
        statements = parse(lex("make hero banner\nmake page\nhero inside page\n"))
        model = analyze(statements)
        from mylang.backend_visual import _kind_of
        self.assertEqual(_kind_of(model, "hero"), "banner")
        self.assertEqual(_kind_of(model, "page"), "page")

    def test_bg_returns_explicit_color_for_page(self):
        from mylang.backend_visual import _bg, KIND_COLORS
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["p"] = Entity("p", "page")
        model.relationships = {}
        self.assertEqual(_bg(model, "p"), KIND_COLORS["page"])

    def test_bg_inherits_from_parent_when_kind_has_no_color(self):
        from mylang.backend_visual import _bg
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["p"] = Entity("p", "page")
        model.entities["l"] = Entity("l", "logo")
        model.relationships = {"l": "p"}
        self.assertEqual(_bg(model, "l"), _bg(model, "p"))

    def test_fg_returns_text_color_for_known_kind(self):
        from mylang.backend_visual import _fg, KIND_TEXT_COLORS
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["h"] = Entity("h", "header")
        self.assertEqual(_fg(model, "h"), KIND_TEXT_COLORS["header"])

    def test_is_leaf_true_for_entity_with_no_children(self):
        from mylang.backend_visual import _is_leaf
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["x"] = Entity("x", "card")
        model.relationships = {}
        self.assertTrue(_is_leaf(model, "x"))

    def test_is_leaf_false_for_entity_with_children(self):
        from mylang.backend_visual import _is_leaf
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["p"] = Entity("p", "page")
        model.entities["c"] = Entity("c", "header")
        model.relationships = {"c": "p"}
        self.assertFalse(_is_leaf(model, "p"))

    def test_has_text_true_when_text_property_exists(self):
        from mylang.backend_visual import _has_text
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["h"] = Entity("h", "banner")
        model.properties[("h", "text")] = "Welcome"
        self.assertTrue(_has_text(model, "h"))

    def test_has_text_false_when_no_text_property(self):
        from mylang.backend_visual import _has_text
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["h"] = Entity("h", "banner")
        self.assertFalse(_has_text(model, "h"))

    def test_visual_render_returns_a_tk_root(self):
        import tkinter as tk
        from mylang.backend_visual import render
        statements = parse(lex(
            'make page\npage title "Test"\n'
            'make header\nheader inside page\n'
        ))
        model = analyze(statements)
        root = render(model)
        self.assertIsInstance(root, tk.Tk)
        self.assertEqual(root.title(), "Test")
        root.destroy()

    def test_visual_render_uses_title_override(self):
        import tkinter as tk
        from mylang.backend_visual import render
        statements = parse(lex('make page\npage title "Original"\n'))
        model = analyze(statements)
        root = render(model, title_override="Override Title")
        self.assertEqual(root.title(), "Override Title")
        root.destroy()

    def test_visual_render_no_page_raises_error(self):
        from mylang.backend_visual import render, VisualError
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["h"] = Entity("h", "header")
        with self.assertRaises(VisualError):
            render(model)

    def test_visual_render_multiple_pages_raises_error(self):
        from mylang.backend_visual import render, VisualError
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["p1"] = Entity("p1", "page")
        model.entities["p2"] = Entity("p2", "page")
        with self.assertRaises(VisualError):
            render(model)

    def test_hero_int_program_builds_model_for_visual(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-hero", "hero.int"
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

    def test_hero_int_visual_render_creates_window(self):
        import tkinter as tk
        from mylang.backend_visual import render
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-hero", "hero.int"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        statements = parse(lex(source))
        model = analyze(statements)
        root = render(model)
        self.assertIsInstance(root, tk.Tk)
        self.assertEqual(root.title(), "Company Name")
        root.destroy()

    def test_visual_render_default_title_when_no_title_property(self):
        import tkinter as tk
        from mylang.backend_visual import render
        statements = parse(lex("make page\n"))
        model = analyze(statements)
        root = render(model)
        self.assertEqual(root.title(), "MyLanguage")
        root.destroy()

    def test_cards_program_builds_model_for_visual(self):
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.int"
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

    def test_cards_visual_render_creates_window(self):
        import tkinter as tk
        from mylang.backend_visual import render
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.int"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        statements = parse(lex(source))
        model = analyze(statements)
        root = render(model)
        self.assertIsInstance(root, tk.Tk)
        self.assertEqual(root.title(), "Company Name")
        root.destroy()

    def test_layout_of_returns_stack_for_unknown_kind(self):
        from mylang.backend_visual import _layout_of
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["x"] = Entity("x", "not-a-real-kind")
        self.assertEqual(_layout_of(model, "x"), "stack")

    def test_layout_of_card_group_reads_dictionary_row(self):
        from mylang.backend_visual import _layout_of
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["g"] = Entity("g", "card-group")
        self.assertEqual(_layout_of(model, "g"), "row")

    def test_position_of_returns_flow_for_unknown_kind(self):
        from mylang.backend_visual import _position_of
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["x"] = Entity("x", "not-a-real-kind")
        self.assertEqual(_position_of(model, "x"), "flow")

    def test_position_of_footer_reads_dictionary_bottom(self):
        from mylang.backend_visual import _position_of
        from mylang.semantic import Model, Entity
        model = Model()
        model.entities["f"] = Entity("f", "footer")
        self.assertEqual(_position_of(model, "f"), "bottom")

    def test_cards_visual_packs_cards_side_by_side(self):
        import tkinter as tk
        from mylang.backend_visual import render
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.int"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        model = analyze(parse(lex(source)))
        root = render(model)
        cards = self._card_frames(root)
        self.assertEqual(len(cards), 3)
        for frame in cards:
            self.assertEqual(frame.pack_info()["side"], "left")
        root.destroy()

    def test_cards_visual_pins_footer_to_bottom(self):
        import tkinter as tk
        from mylang.backend_visual import render
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "homepage-cards", "cards.int"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        model = analyze(parse(lex(source)))
        root = render(model)
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


if __name__ == "__main__":
    unittest.main()