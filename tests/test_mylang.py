import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mylang.backend_html import BackendError, render
from mylang.cli import build
from mylang.interpreter import execute
from mylang.lexer import LexError, TokenKind, lex
from mylang.parser import MakeStatement, PropertyStatement, SayStatement, SyntaxError, parse
from mylang.semantic import SemanticError, analyze


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

    def test_property_value_must_be_quoted(self):
        with self.assertRaises(SyntaxError):
            parse(lex("page title 42\n"))

    def test_extra_text_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex("make page extra words\n"))

    def test_make_requires_a_name(self):
        with self.assertRaises(SyntaxError):
            parse(lex("make\n"))


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


class BackendTests(unittest.TestCase):
    def test_page_renders_title_and_heading(self):
        statements = parse(lex('make page\npage title "Hello, MyLanguage"\n'))
        model = analyze(statements)
        output = render(model)
        self.assertIn("<title>Hello, MyLanguage</title>", output)
        self.assertIn("<h1>Hello, MyLanguage</h1>", output)

    def test_unknown_kind_is_rejected(self):
        statements = parse(lex("make page\nmake header\n"))
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

    def test_say_requires_a_string(self):
        with self.assertRaises(SyntaxError):
            parse(lex("say page\n"))

    def test_say_extra_text_is_an_error(self):
        with self.assertRaises(SyntaxError):
            parse(lex('say "x" extra\n'))

    def test_execution_returns_outputs_in_order(self):
        statements = parse(lex('say "one"\nsay "two"\n'))
        self.assertEqual(execute(statements), ["one", "two"])

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


if __name__ == "__main__":
    unittest.main()