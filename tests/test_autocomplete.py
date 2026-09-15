import json
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ine.autocomplete import complete, context, resolve_kind
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


if __name__ == "__main__":
    unittest.main()