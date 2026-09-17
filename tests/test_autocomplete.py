import json
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ine.autocomplete import _respond, complete, context, resolve_kind
from ine.dictionary import ValueShape, makeable, parents, suggest, value_hint


class ContextTests(unittest.TestCase):
    def test_kind_context_after_make(self):
        self.assertEqual(context("make ", 5), {"type": "kind"})

    def test_kind_context_with_partial_word(self):
        self.assertEqual(context("make he", 7), {"type": "kind"})

    def test_kind_context_while_typing_keyword(self):
        self.assertEqual(context("make", 4), {"type": "kind"})

    def test_inside_context(self):
        self.assertEqual(context("header inside ", 14), {
            "type": "inside", "child": "header", "partial": "",
        })

    def test_inside_context_with_partial_parent(self):
        self.assertEqual(context("header inside p", 15), {
            "type": "inside", "child": "header", "partial": "p",
        })

    def test_property_context_after_kind(self):
        self.assertEqual(context("header ", 7), {
            "type": "properties", "kind_word": "header", "partial": "",
        })

    def test_value_context_after_typed_property(self):
        self.assertEqual(context("page title ", 11), {
            "type": "value", "kind_word": "page", "prop": "title",
        })

    def test_value_context_while_typing_property_is_still_properties(self):
        self.assertEqual(context("page titl", 9), {
            "type": "properties", "kind_word": "page", "partial": "titl",
        })

    def test_property_context_while_typing_property(self):
        self.assertEqual(context("card-1 tit", 10), {
            "type": "properties", "kind_word": "card-1", "partial": "tit",
        })

    def test_no_context_on_empty_line(self):
        self.assertIsNone(context("", 0))
        self.assertIsNone(context("   ", 3))

    def test_no_context_after_property_value(self):
        self.assertIsNone(context("page title \"Home\" ", 17))

    def test_comment_line_is_ignored(self):
        self.assertIsNone(context("# header ", 9))

    def test_make_pair_is_not_a_kind_context(self):
        self.assertIsNone(context("make hero banner", 16))

    def test_group_keyword_statement_start_is_no_context(self):
        self.assertIsNone(context("group ", 6))
        self.assertIsNone(context("group cards = ", 14))
        self.assertIsNone(context("group cards = card-1", 19))

    def test_say_keyword_statement_start_is_no_context(self):
        self.assertIsNone(context("say ", 4))
        self.assertIsNone(context("say person", 10))
        self.assertIsNone(context("say person age", 14))


class CursorEdgeCaseTests(unittest.TestCase):
    """Unusual cursor positions: document what is correct, what degrades
    gracefully, and that nothing crashes (test-and-document mission 14)."""

    @staticmethod
    def items(buffer, column, line=0):
        return complete({"buffer": buffer, "line": line, "column": column})["items"]

    def test_cursor_at_line_start_is_no_context(self):
        self.assertIsNone(context("make page", 0))
        self.assertEqual(self.items("make page", 0), [])

    def test_cursor_after_blank_line_is_no_context(self):
        buffer = "make page\ncontent\n\n"
        self.assertIsNone(context("", 0))
        self.assertEqual(complete({"buffer": buffer, "line": 2, "column": 0})["items"], [])

    def test_cursor_after_multiple_spaces_keeps_context(self):
        self.assertEqual(context("header     ", 10), {
            "type": "properties", "kind_word": "header", "partial": "",
        })

    def test_cursor_midline_while_typing_keyword_is_kind_context(self):
        self.assertEqual(context("make p", 6), {"type": "kind"})
        self.assertEqual({i["label"] for i in self.items("make p", 6)},
                         set(makeable()))

    def test_cursor_inside_a_quoted_value_is_no_context(self):
        self.assertIsNone(context('page title "Ho', 15))
        self.assertEqual(self.items('page title "Ho', 15), [])

    def test_cursor_at_the_end_of_a_complete_value_is_no_context(self):
        self.assertIsNone(context('page title "Home" ', 17))

    def test_cursor_after_comment_on_own_line_is_no_context(self):
        self.assertIsNone(context("# header ", 9))
        self.assertEqual(self.items("# header ", 9), [])

    def test_cursor_after_inline_comment_is_no_context(self):
        # A finished `make` declaration has nothing more to complete, even
        # when an inline comment follows it (mission 43 fix for the mission
        # 14 misclassification).
        result = complete({"buffer": "make page # note ", "line": 0, "column": 18})
        self.assertNotIn("error", result)
        self.assertEqual(result["context"], None)
        self.assertEqual(result["items"], [])

    def test_complete_make_statement_starts_no_context(self):
        # A finished declaration has nothing left to complete; only a
        # half-typed kind while the cursor is still on it stays in the
        # `kind` context.
        for line in ("make page ", "make hero banner ", "make page # note ",
                     "make 3 card "):
            with self.subTest(line=line):
                self.assertIsNone(context(line, len(line)))
        for line in ("make p", "make he"):
            with self.subTest(line=line):
                self.assertEqual(context(line, len(line)), {"type": "kind"})

    def test_cursor_mid_identifier_keeps_property_context(self):
        self.assertEqual(context("card-1 tit", 10), {
            "type": "properties", "kind_word": "card-1", "partial": "tit",
        })


class ContainmentCompletionTests(unittest.TestCase):
    """`<child> inside ` must answer from `parents()` (mission 15)."""

    @staticmethod
    def items(buffer, column, line=0):
        return complete({"buffer": buffer, "line": line, "column": column})["items"]

    def test_header_inside_returns_page(self):
        self.assertEqual(
            [i["label"] for i in self.items("header inside ", 14)],
            parents("header"),
        )
        self.assertEqual(parents("header"), ["page"])

    def test_card_inside_returns_card_group(self):
        self.assertEqual(parents("card"), ["card-group"])
        self.assertEqual(
            [i["label"] for i in self.items("card inside ", 13)],
            ["card-group"],
        )

    def test_banner_inside_returns_container(self):
        self.assertEqual(parents("banner"), ["container"])
        self.assertEqual(
            [i["label"] for i in self.items("banner inside ", 15)],
            ["container"],
        )

    def test_page_inside_returns_nothing_top_level(self):
        self.assertEqual(parents("page"), [])
        self.assertEqual(self.items("page inside ", 13), [])

    def test_copy_inside_returns_nothing_undeclared(self):
        self.assertEqual(parents("copy"), [])
        self.assertEqual(self.items("copy inside ", 13), [])

    def test_case_sensitivity_no_completion_for_caps(self):
        self.assertEqual(parents("Page"), [])
        self.assertEqual(self.items("Page inside ", 13), [])


class ResolveKindTests(unittest.TestCase):
    def test_name_is_a_dictionary_kind(self):
        self.assertEqual(resolve_kind("make page\n", "header"), "header")

    def test_entity_from_make_with_kind(self):
        self.assertEqual(resolve_kind("make hero banner\n", "hero"), "banner")

    def test_entity_from_make_default(self):
        self.assertEqual(resolve_kind("make hero\n", "hero"), "hero")

    def test_entity_from_multiplicity(self):
        self.assertEqual(resolve_kind("make 2 card\n", "card-1"), "card")

    def test_group_name_resolves_to_member_kind(self):
        self.assertEqual(
            resolve_kind("make 2 card\ngroup cards = card-1 card-2\n", "cards"),
            "card",
        )

    def test_unknown_name_is_none(self):
        self.assertIsNone(resolve_kind("", "zzz"))

    def test_numbers_are_not_entity_names(self):
        self.assertIsNone(resolve_kind("make 2 card\n", "2"))


class BufferContextTests(unittest.TestCase):
    """Multi-line buffers: entities declared ABOVE the cursor must resolve
    property / value / inside contexts on later lines; a `say` line yields
    no context while the surrounding lines still do. Locks the
    buffer-scanning contract of resolve_kind (mission 46)."""

    @staticmethod
    def items(buffer, column, line=0):
        return complete({"buffer": buffer, "line": line, "column": column})["items"]

    def test_kind_above_cursor_resolves_property_context(self):
        buffer = "make hero banner\nhero titl"
        self.assertEqual(context(buffer.splitlines()[1], 9), {
            "type": "properties", "kind_word": "hero", "partial": "titl",
        })
        self.assertEqual([i["label"] for i in self.items(buffer, 9, line=1)],
                         [i.text for i in suggest("banner")])

    def test_multiplicity_above_cursor_resolves_property_context(self):
        buffer = "make 2 card\ncard-1 tit"
        self.assertEqual(context(buffer.splitlines()[1], 10), {
            "type": "properties", "kind_word": "card-1", "partial": "tit",
        })
        self.assertEqual([i["label"] for i in self.items(buffer, 10, line=1)],
                         [i.text for i in suggest("card")])

    def test_kind_above_cursor_resolves_value_context(self):
        buffer = "make hero banner\nhero title "
        self.assertEqual(context(buffer.splitlines()[1], 11), {
            "type": "value", "kind_word": "hero", "prop": "title",
        })
        self.assertEqual([i["label"] for i in self.items(buffer, 11, line=1)],
                         ['""'])

    def test_group_above_cursor_resolves_inside_context(self):
        buffer = "make 2 card\ngroup cards = card-1 card-2\ncards inside "
        self.assertEqual(context(buffer.splitlines()[2], 13), {
            "type": "inside", "child": "cards", "partial": "",
        })
        self.assertEqual([i["label"] for i in self.items(buffer, 13, line=2)],
                         parents("card"))

    def test_say_line_has_no_context_but_neighbors_do(self):
        buffer = "make p\nsay hello\npage t"
        self.assertIsNone(context(buffer.splitlines()[1], 9))
        self.assertEqual(self.items(buffer, 9, line=1), [])
        self.assertEqual(context(buffer.splitlines()[0], 6), {"type": "kind"})
        self.assertEqual(context(buffer.splitlines()[2], 6), {
            "type": "properties", "kind_word": "page", "partial": "t",
        })


class CompletionTests(unittest.TestCase):
    @staticmethod
    def items(buffer, column, line=0):
        return complete({"buffer": buffer, "line": line, "column": column})["items"]

    def test_kind_completion_lists_makeable_kinds(self):
        items = self.items("make ", 5)
        self.assertEqual({i["label"] for i in items}, set(makeable()))
        self.assertTrue(all(i["type"] == "kind" for i in items))
        self.assertTrue(all(i["insert"] == i["label"] for i in items))
        self.assertTrue(any(i["label"] == "header" for i in items))

    def test_kind_completion_excludes_ambient_and_universal(self):
        items = self.items("make he", 7)
        self.assertNotIn("viewport", [i["label"] for i in items])
        self.assertNotIn("universal", [i["label"] for i in items])

    def test_property_completion_after_kind_word(self):
        items = self.items("header ", 7)
        labels = [i["label"] for i in items]
        self.assertEqual(labels, [i.text for i in suggest("header")])
        self.assertIn("title", labels)
        self.assertIn("text", labels)
        self.assertIn("height", labels)
        self.assertIn("logo", labels)
        self.assertIn("navigation", labels)

    def test_property_completion_via_make_with_kind(self):
        buffer = "make hero banner\nhero "
        items = self.items(buffer, 5, line=1)
        self.assertEqual([i["label"] for i in items], [i.text for i in suggest("banner")])
        self.assertIn("title", [i["label"] for i in items])

    def test_property_completion_via_multiplicity(self):
        buffer = "make 2 card\ncard-1 "
        items = self.items(buffer, 7, line=1)
        labels = [i["label"] for i in items]
        self.assertEqual(labels, [i.text for i in suggest("card")])
        self.assertIn("border", labels)


class ValueShapeTests(unittest.TestCase):
    @staticmethod
    def items(buffer, column, line=0):
        return complete({"buffer": buffer, "line": line, "column": column})["items"]

    def test_universal_title_and_text_are_text_shaped(self):
        items = self.items("page ", 5)
        by_label = {i["label"]: i for i in items}
        self.assertEqual(by_label["title"].get("value_shape"), "text")
        self.assertEqual(by_label["text"].get("value_shape"), "text")

    def test_universal_shape_applies_on_any_kind(self):
        items = self.items("header ", 7)
        by_label = {i["label"]: i for i in items}
        self.assertEqual(by_label["title"].get("value_shape"), "text")

    def test_regular_property_has_no_value_shape(self):
        items = self.items("header ", 7)
        by_label = {i["label"]: i for i in items}
        self.assertIsNone(by_label["height"].get("value_shape"))

    def test_concept_items_have_no_value_shape(self):
        items = self.items("header ", 7)
        by_label = {i["label"]: i for i in items}
        self.assertIsNone(by_label["logo"].get("value_shape"))

    def test_kind_items_have_no_value_shape(self):
        items = self.items("make ", 5)
        self.assertTrue(all("value_shape" not in i for i in items))

    def test_property_labels_are_unchanged_by_shape(self):
        items = self.items("page ", 5)
        by_label = {i["label"]: i for i in items}
        self.assertEqual("title", by_label["title"]["insert"])

    def test_inside_completion_returns_parents(self):
        items = self.items("header inside ", 14)
        self.assertEqual([i["label"] for i in items], parents("header"))
        self.assertTrue(all(i["type"] == "parent" for i in items))

    def test_inside_completion_details_use_program_direction(self):
        items = self.items("header inside p", 15)
        self.assertIn("header inside page", [i["detail"] for i in items])
        self.assertTrue(all(i["insert"] == i["label"] for i in items))

    def test_inside_completion_via_group(self):
        buffer = "make 2 card\ngroup cards = card-1 card-2\ncards inside "
        items = self.items(buffer, 13, line=2)
        self.assertEqual([i["label"] for i in items], parents("card"))

    def test_unknown_name_gets_nothing(self):
        self.assertEqual(self.items("zzz ", 4), [])

    def test_unknown_child_inside_gets_nothing(self):
        self.assertEqual(self.items("zzz inside ", 11), [])


class ValueCompletionTests(unittest.TestCase):
    @staticmethod
    def items(buffer, column, line=0):
        return complete({"buffer": buffer, "line": line, "column": column})["items"]

    def test_text_property_value_completion(self):
        items = self.items("card title ", 11)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["label"], '""')
        self.assertEqual(item["insert"], '""')
        self.assertEqual(item["type"], "value")
        self.assertEqual(item["detail"], value_hint("card", "title"))

    def test_text_value_completion_via_multiplicity(self):
        buffer = "make 2 card\ncard-1 text "
        items = self.items(buffer, 12, line=1)
        self.assertEqual([i["label"] for i in items], ['""'])
        self.assertEqual(items[0]["detail"], value_hint("card", "text"))

    def test_unknown_property_value_completion_is_empty(self):
        self.assertEqual(self.items("card color ", 11), [])

    def test_non_kind_first_word_value_completion_is_empty(self):
        self.assertEqual(self.items("zzz banner ", 11), [])

    def test_choice_shape_lists_allowed_options(self):
        with mock.patch(
            "ine.autocomplete.dictionary.value_shape",
            return_value=ValueShape("choice", ("row", "column")),
        ):
            items = self.items("card layout ", 13)
        self.assertEqual([i["label"] for i in items], ["row", "column"])
        self.assertTrue(all(i["insert"] == i["label"] for i in items))
        self.assertTrue(all(i["type"] == "value" for i in items))

    def test_number_shape_offers_numeric_placeholder(self):
        with mock.patch(
            "ine.autocomplete.dictionary.value_shape",
            return_value=ValueShape("number"),
        ):
            items = self.items("card ratio ", 11)
        self.assertEqual([i["label"] for i in items], ["123"])
        self.assertEqual(items[0]["insert"], "123")
        self.assertEqual(items[0]["type"], "value")

    def test_value_response_carries_a_value_context(self):
        result = complete({"buffer": "page title ", "line": 0, "column": 11})
        self.assertEqual(result["context"], {
            "type": "value", "kind_word": "page", "prop": "title",
        })

    def test_response_echoes_position(self):
        result = complete({"buffer": "make ", "line": 0, "column": 5})
        self.assertEqual((result["line"], result["column"]), (0, 5))
        self.assertEqual(result["context"], {"type": "kind"})


class ProtocolTests(unittest.TestCase):
    def test_stdin_stdout_roundtrip(self):
        script = os.path.join(
            os.path.dirname(__file__), "..", "src", "ine", "autocomplete.py"
        )
        payload = {"buffer": "make ", "line": 0, "column": 5}
        proc = subprocess.run(
            [sys.executable, os.path.abspath(script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        result = json.loads(proc.stdout)
        self.assertNotIn("error", result)
        self.assertEqual([i["label"] for i in result["items"]], makeable())

    def test_garbage_input_keeps_protocol_alive(self):
        script = os.path.join(
            os.path.dirname(__file__), "..", "src", "ine", "autocomplete.py"
        )
        proc = subprocess.run(
            [sys.executable, os.path.abspath(script)],
            input="not json",
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        result = json.loads(proc.stdout)
        self.assertEqual(result["items"], [])
        self.assertIn("error", result)

    @staticmethod
    def _script():
        return os.path.join(
            os.path.dirname(__file__), "..", "src", "ine", "autocomplete.py"
        )

    def test_persistent_process_answers_each_line(self):
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(self._script())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        proc.stdin.write(json.dumps({"buffer": "header inside p", "line": 0, "column": 15}) + "\n")
        proc.stdin.flush()
        first = json.loads(proc.stdout.readline())
        self.assertEqual([i["label"] for i in first["items"]], parents("header"))
        proc.stdin.write(json.dumps({"buffer": "make ", "line": 0, "column": 5}) + "\n")
        proc.stdin.flush()
        second = json.loads(proc.stdout.readline())
        self.assertEqual([i["label"] for i in second["items"]], makeable())
        proc.stdin.close()
        self.assertEqual(proc.wait(timeout=10), 0)

    def test_request_id_is_echoed(self):
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(self._script())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        proc.stdin.write(json.dumps({"buffer": "header ", "line": 0, "column": 7, "id": 42}) + "\n")
        proc.stdin.flush()
        result = json.loads(proc.stdout.readline())
        self.assertEqual(result["id"], 42)
        proc.stdin.close()
        proc.wait(timeout=10)

    def test_missing_buffer_is_an_empty_response(self):
        result = complete({"line": 0, "column": 5})
        self.assertIn("items", result)
        self.assertEqual(result["items"], [])

    def test_missing_line_defaults_to_the_first_line(self):
        result = complete({"buffer": "make ", "column": 5})
        self.assertEqual([i["label"] for i in result["items"]], makeable())

    def test_missing_column_defaults_to_zero(self):
        result = complete({"buffer": "make ", "line": 0})
        self.assertEqual(result["items"], [])

    def test_null_column_uses_the_whole_line(self):
        result = complete({"buffer": "make ", "line": 0, "column": None})
        self.assertNotIn("error", result)
        self.assertIn("items", result)
        self.assertEqual([i["label"] for i in result["items"]], makeable())

    def test_wrong_type_line_is_an_error_response(self):
        result = _respond({"buffer": "make ", "line": "x", "column": 5})
        self.assertIn("error", result)
        self.assertEqual(result["items"], [])

    def test_id_is_echoed_even_on_an_error_response(self):
        result = _respond({"buffer": "make ", "line": "x", "column": 5, "id": 7})
        self.assertIn("error", result)
        self.assertEqual(result["id"], 7)

    def test_malformed_keys_then_valid_completion_in_one_session(self):
        # Well-formed-but-wrong payloads must each yield a valid JSON
        # response and leave the persistent worker alive; the same session
        # still answers a normal completion afterwards (mission 47).
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(self._script())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        def ask(payload):
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        result = ask({"line": 0, "column": 5})
        self.assertEqual(result["items"], [])
        result = ask({"buffer": "make ", "line": "x", "column": 5, "id": 7})
        self.assertIn("error", result)
        self.assertEqual(result["id"], 7)
        result = ask({"validate": True, "buffer": "make @\n"})
        self.assertEqual(len(result["diagnostics"]), 1)
        result = ask({"buffer": "page title ", "line": 0, "column": 11, "id": 11})
        self.assertNotIn("error", result)
        self.assertEqual(result["id"], 11)
        self.assertEqual([i["label"] for i in result["items"]], ['""'])
        proc.stdin.close()
        self.assertEqual(proc.wait(timeout=10), 0)

    def test_error_line_does_not_kill_the_loop(self):
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(self._script())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        cases = [
            (json.dumps({"buffer": "header ", "line": 0, "column": 7}) + "\n",
             lambda r: self.assertEqual(
                 [i["label"] for i in r["items"]], [i.text for i in suggest("header")])),
            ("not json\n",
             lambda r: (self.assertEqual(r["items"], []),
                        self.assertIn("error", r))),
            (json.dumps({"buffer": "make 2 card\ngroup cards = card-1 card-2\ncards inside ",
                         "line": 2, "column": 13}) + "\n",
             lambda r: self.assertEqual(
                 [i["label"] for i in r["items"]], parents("card"))),
        ]
        for line, check in cases:
            proc.stdin.write(line)
            proc.stdin.flush()
            check(json.loads(proc.stdout.readline()))
        proc.stdin.close()
        self.assertEqual(proc.wait(timeout=10), 0)

    def test_editor_flow_end_to_end(self):
        """One live session answering the four contexts an editor asks."""
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(self._script())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        buffer = "make page\npage title \"Home\"\nmake header\nheader inside page\n"
        requests = [
            ({"buffer": buffer + "make ", "line": 4, "column": 5, "id": 1},
             "kind",
             lambda r: (self.assertEqual(r["id"], 1),
                        self.assertEqual({i["label"] for i in r["items"]},
                                         set(makeable())))),
            ({"buffer": buffer + "page ", "line": 4, "column": 5, "id": 2},
             "properties",
             lambda r: (self.assertEqual(r["id"], 2),
                        self.assertEqual([i["label"] for i in r["items"]],
                                         [i.text for i in suggest("page")]))),
            ({"buffer": buffer + "page title ", "line": 4, "column": 11, "id": 3},
             "value",
             lambda r: (self.assertEqual(r["id"], 3),
                        self.assertEqual([i["label"] for i in r["items"]], ['""']))),
            ({"buffer": buffer + "header inside ", "line": 4, "column": 15, "id": 4},
             "inside",
             lambda r: (self.assertEqual(r["id"], 4),
                        self.assertEqual([i["label"] for i in r["items"]],
                                         parents("header")))),
        ]
        for payload, expected, check in requests:
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()
            result = json.loads(proc.stdout.readline())
            self.assertNotIn("error", result)
            self.assertEqual(result["context"]["type"], expected)
            check(result)
        proc.stdin.close()
        self.assertEqual(proc.wait(timeout=10), 0)


class ValidateTests(unittest.TestCase):
    """The validation query ({"validate": true, "buffer": ...}) returns
    parse-level diagnostics: a clean buffer -> [], lex errors carry
    line + column, syntax errors carry line (the parser has no column),
    and errors never break the protocol loop."""

    @staticmethod
    def validate(buffer):
        return complete({"validate": True, "buffer": buffer})

    def test_validate_clean_buffer_returns_empty(self):
        result = self.validate('make page\npage title "Home"\n')
        self.assertTrue(result["validate"])
        self.assertEqual(result["diagnostics"], [])

    def test_validate_empty_buffer_returns_empty(self):
        self.assertEqual(self.validate("")["diagnostics"], [])

    def test_validate_lex_error_reports_line_and_column(self):
        result = self.validate('make page\npage title "oops\n')
        self.assertEqual(len(result["diagnostics"]), 1)
        diag = result["diagnostics"][0]
        self.assertEqual(diag["line"], 1)
        self.assertIn("column", diag)
        self.assertIn("unterminated string", diag["message"])

    def test_validate_unexpected_character_reports_exact_column(self):
        diag = self.validate("make page @\n")["diagnostics"][0]
        self.assertEqual(diag["line"], 0)
        self.assertEqual(diag["column"], 10)
        self.assertEqual(diag["message"], "unexpected character '@'")

    def test_validate_syntax_error_reports_line_without_column(self):
        # `say page` parses as a name expecting '.property'; the NEWLINE
        # token after the name is not a property, so this is a syntax error
        # with a line and no column.
        diag = self.validate("say page\n")["diagnostics"][0]
        self.assertEqual(diag["line"], 0)
        self.assertNotIn("column", diag)
        self.assertIn("property", diag["message"])

    def test_validate_response_is_distinct_from_completion(self):
        result = self.validate("make page\n")
        self.assertEqual(result, {"validate": True, "diagnostics": []})
        self.assertNotIn("context", result)
        self.assertNotIn("items", result)

    def test_validate_response_echoes_id(self):
        result = complete({"validate": True, "buffer": "make page\n", "id": 7})
        self.assertEqual(result["id"], 7)

    @staticmethod
    def _script():
        return os.path.join(
            os.path.dirname(__file__), "..", "src", "ine", "autocomplete.py"
        )

    def test_validate_then_completion_in_one_live_session(self):
        # Protocol liveness: a validate query over a broken buffer must not
        # kill the worker; the next completion still answers.
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(self._script())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        proc.stdin.write(json.dumps({"validate": True, "buffer": "make page @\n"}) + "\n")
        proc.stdin.flush()
        first = json.loads(proc.stdout.readline())
        self.assertNotIn("error", first)
        self.assertTrue(first["validate"])
        self.assertEqual(len(first["diagnostics"]), 1)
        proc.stdin.write(json.dumps({"buffer": "page title ", "line": 0, "column": 11}) + "\n")
        proc.stdin.flush()
        second = json.loads(proc.stdout.readline())
        self.assertNotIn("error", second)
        self.assertEqual([i["label"] for i in second["items"]], ['""'])
        proc.stdin.close()
        self.assertEqual(proc.wait(timeout=10), 0)


if __name__ == "__main__":
    unittest.main()