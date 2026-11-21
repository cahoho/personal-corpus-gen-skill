"""Synthetic-only tests for the offline DeepSeek JSON helper."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("deepseek_tool.py")
FIRST = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
VERSION = "synthetic-v1"
SECRET = "SYNTHETIC_PRIVATE_SENTINEL"


def sample_session():
    return {
        "id": FIRST,
        "current_message_id": 3,
        "messages": [
            {"id": 1, "parent_id": None, "role": "USER", "inserted_at": "2024-01-01T10:00:00+02:00",
             "fragments": [{"type": "REQUEST", "content": "synthetic request"},
                           {"type": "FILE", "content": SECRET, "export_path": "../outside"}]},
            {"id": 2, "parent_id": 1, "role": "ASSISTANT", "status": "INCOMPLETE",
             "fragments": [{"type": "THINK", "content": SECRET},
                           {"type": "TOOL_CALL", "content": SECRET},
                           {"type": "READ_LINK", "content": SECRET},
                           {"type": "UNKNOWN", "content": SECRET},
                           {"type": "RESPONSE", "content": "synthetic response"}]},
            {"id": 3, "parent_id": 2, "role": "USER", "inserted_at": "bad-time",
             "fragments": [{"type": "REQUEST", "content": "synthetic follow-up"}]},
            {"id": 4, "parent_id": 1, "role": "ASSISTANT",
             "fragments": [{"type": "RESPONSE", "content": SECRET}]},
        ],
    }


class DeepSeekToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "chat_sessions").mkdir()
        self.write("manifest.json", {"export_format_version": VERSION})
        self.write("user.json", {"email": SECRET, "id": SECRET})
        self.write("chat_session_index.json", [{"id": FIRST, "title": SECRET}])
        self.write("chat_sessions/" + FIRST + ".json", sample_session())

    def write(self, relative, value):
        (self.root / relative).write_text(json.dumps(value), encoding="utf-8")

    def run_tool(self, command, *args):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), command, str(self.root), *args],
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.stderr, "", result.stderr)
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail("Tool did not produce JSON: " + result.stdout)
        return result.returncode, output, result.stdout

    def extract(self, session_id=FIRST, version=VERSION, start=0, limit=100):
        return self.run_tool("session", "--confirm-version", version, "--session-id", session_id,
                             "--start", str(start), "--limit", str(limit))

    def test_inventory_does_not_open_session_without_confirmation(self):
        (self.root / "chat_sessions" / (FIRST + ".json")).write_text("not-json " + SECRET, encoding="utf-8")
        code, output, raw = self.run_tool("inventory")
        self.assertEqual(code, 0)
        self.assertFalse(output["session_files_opened"])
        self.assertEqual(output["version_status"], "unverified")
        self.assertEqual(output["session_json_file_count"], 1)
        self.assertNotIn(SECRET, raw)
        self.assertNotIn(FIRST, raw)

    def test_inventory_with_confirmation_checks_but_never_emits_private_fields(self):
        code, output, raw = self.run_tool("inventory", "--confirm-version", VERSION)
        self.assertEqual(code, 1)
        self.assertTrue(output["session_files_opened"])
        self.assertEqual(output["valid_session_file_count"], 1)
        self.assertEqual(output["uncovered_message_count"], 1)
        self.assertEqual(output["issues"]["session_unknown_type_fragments"], 1)
        self.assertEqual(output["issues"]["session_invalid_message_time"], 1)
        self.assertEqual(output["version_status"], "user_confirmed_unverified")
        for forbidden in (SECRET, FIRST, "synthetic request", "synthetic response"):
            self.assertNotIn(forbidden, raw)

    def test_version_mismatch_does_not_open_session_files(self):
        code, output, raw = self.run_tool("inventory", "--confirm-version", "wrong")
        self.assertEqual(code, 1)
        self.assertFalse(output["session_files_opened"])
        self.assertEqual(output["issues"]["confirmed_version_mismatch"], 1)
        self.assertNotIn(SECRET, raw)
        code, output, raw = self.extract(version="wrong")
        self.assertEqual(code, 1)
        self.assertEqual(output["error"], "confirmed_version_mismatch")
        self.assertNotIn(SECRET, raw)

    def test_session_extracts_only_current_branch_allowed_fragments(self):
        code, output, raw = self.extract()
        self.assertEqual(code, 0)
        self.assertEqual(output["uncovered_message_count"], 1)
        self.assertEqual(output["current_branch_message_count"], 3)
        self.assertEqual([m["message_id"] for m in output["messages"]], [1, 2, 3])
        self.assertEqual(output["messages"][0]["inserted_at_utc"], "2024-01-01T08:00:00Z")
        self.assertEqual(output["messages"][0]["inserted_at_raw"], "2024-01-01T10:00:00+02:00")
        self.assertIsNone(output["messages"][2]["inserted_at_utc"])
        self.assertIsNone(output["messages"][2]["inserted_at_raw"])
        self.assertEqual(output["unhandled_fragments_current_branch"],
                         [{"message_id": 2, "fragment_index": 3, "kind": "unknown"}])
        self.assertTrue(output["current_branch_has_unhandled_fragments"])
        self.assertEqual(output["messages"][1]["status"], "INCOMPLETE")
        self.assertEqual(output["messages"][1]["fragments"][0]["fragment_index"], 4)
        self.assertEqual(output["messages"][1]["fragments"][0]["text"], "synthetic response")
        self.assertEqual(output["skipped_fragment_counts_all_branches"]["unknown_type_fragments"], 1)
        self.assertEqual(output["skipped_fragment_counts_all_branches"]["file_fragments"], 1)
        self.assertEqual(output["skipped_fragment_counts_all_branches"]["tool_or_link_fragments"], 2)
        self.assertNotIn(SECRET, raw)

    def test_invalid_graphs_and_messages_fail_without_text(self):
        variants = []
        session = sample_session(); session.pop("current_message_id"); variants.append((session, "missing_cursor"))
        session = sample_session(); session["current_message_id"] = 999; variants.append((session, "cursor_not_found"))
        session = sample_session(); session["messages"][1]["parent_id"] = 999; variants.append((session, "parent_not_found"))
        session = sample_session(); session["messages"][1].pop("parent_id"); variants.append((session, "missing_parent_id"))
        session = sample_session(); session["messages"][3]["id"] = 1; variants.append((session, "duplicate_message_id"))
        session = sample_session(); session["messages"][1]["parent_id"] = 3; variants.append((session, "parent_cycle"))
        session = sample_session(); session["messages"][3]["parent_id"] = None; variants.append((session, "invalid_root_count"))
        session = sample_session(); session["messages"][3]["role"] = "SYSTEM"; variants.append((session, "invalid_message_role"))
        session = sample_session(); session["messages"][3]["fragments"] = []; variants.append((session, "missing_or_empty_fragments"))
        session = sample_session(); session["messages"][0]["fragments"][0]["type"] = "RESPONSE"; variants.append((session, "role_fragment_mismatch"))
        session = sample_session(); session["messages"][1]["status"] = "unknown"; variants.append((session, "unknown_message_status"))
        session = sample_session(); session["messages"][1]["fragments"][4]["content"] = {}; variants.append((session, "invalid_text_fragment"))
        session = sample_session(); session["messages"][1]["fragments"][4]["content"] = ""; variants.append((session, "empty_text_fragment"))
        session = sample_session(); session["messages"][0]["id"] = True; variants.append((session, "invalid_message_id"))
        session = sample_session(); session["id"] = SECOND; variants.append((session, "session_id_filename_mismatch"))
        session = sample_session(); session["messages"][0]["fragments"][0] = {}; variants.append((session, "invalid_fragment"))
        for value, expected in variants:
            with self.subTest(expected=expected):
                self.write("chat_sessions/" + FIRST + ".json", value)
                code, output, raw = self.extract()
                self.assertEqual(code, 1)
                self.assertEqual(output["error"], expected)
                self.assertNotIn("synthetic request", raw)
                self.assertNotIn(SECRET, raw)

    def test_duplicate_json_keys_are_refused(self):
        path = self.root / "chat_sessions" / (FIRST + ".json")
        path.write_text('{"id": "' + FIRST + '", "id": "' + FIRST + '", "content": "' + SECRET + '"}', encoding="utf-8")
        code, output, raw = self.extract()
        self.assertEqual(code, 1)
        self.assertEqual(output["error"], "duplicate_json_key")
        self.assertNotIn(SECRET, raw)

    def test_inventory_reports_file_index_discrepancies_without_identifiers(self):
        self.write("chat_session_index.json", [{"id": FIRST}, {"id": FIRST}, {"id": SECOND}])
        third = "33333333-3333-4333-8333-333333333333"
        self.write("chat_sessions/" + third + ".json", {"id": third})
        self.write("chat_sessions/not-a-uuid.json", {"title": SECRET})
        code, output, raw = self.run_tool("inventory")
        self.assertEqual(code, 1)
        self.assertEqual(output["issues"]["duplicate_index_id"], 1)
        self.assertEqual(output["issues"]["invalid_session_filename"], 1)
        self.assertEqual(output["missing_indexed_file_count"], 1)
        self.assertEqual(output["extra_session_file_count"], 1)
        for value in (FIRST, SECOND, third, SECRET):
            self.assertNotIn(value, raw)
        code, output, _ = self.extract()
        self.assertEqual((code, output["error"]), (1, "invalid_index"))

    def test_index_mapping_and_unrecognized_shapes_are_rejected(self):
        self.write("chat_session_index.json", [{"id": FIRST, "file_path": "../outside/secret.json"}])
        code, output, raw = self.run_tool("inventory")
        self.assertEqual(output["issues"]["index_file_path_mismatch"], 1)
        self.assertNotIn("outside", raw)
        self.assertEqual(self.extract()[1]["error"], "invalid_index")
        self.write("chat_session_index.json", {"sessions": [{"id": FIRST}]})
        code, output, _ = self.run_tool("inventory")
        self.assertEqual(code, 1)
        self.assertEqual(output["issues"]["unsupported_index_shape"], 1)
        self.assertIsNone(output["extra_session_file_count"])
        self.assertIsNone(output["missing_indexed_file_count"])

    def test_unknown_or_missing_manifest_version_refuses_session(self):
        for version in (None, "", 1):
            with self.subTest(version=version):
                self.write("manifest.json", {"export_format_version": version})
                code, output, raw = self.extract()
                self.assertEqual(code, 1)
                self.assertEqual(output["error"], "missing_or_invalid_export_version")
                self.assertNotIn(SECRET, raw)
                self.assertFalse(self.run_tool("inventory", "--confirm-version", VERSION)[1]["session_files_opened"])

    def test_selected_session_must_be_explicit_indexed_uuid(self):
        for session_id in (SECOND, "../" + FIRST, "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"):
            with self.subTest(session_id=session_id):
                code, output, raw = self.extract(session_id=session_id)
                self.assertEqual(code, 1)
                self.assertIn(output["error"], ("selected_session_not_in_index", "invalid_selected_session_id"))
                self.assertNotIn(SECRET, raw)

    def test_only_selected_session_is_opened(self):
        self.write("chat_session_index.json", [{"id": FIRST}, {"id": SECOND}])
        (self.root / "chat_sessions" / (SECOND + ".json")).write_text("invalid " + SECRET, encoding="utf-8")
        self.assertEqual(self.extract()[0], 0)
        code, output, raw = self.run_tool("inventory", "--confirm-version", VERSION)
        self.assertEqual(code, 1)
        self.assertEqual(output["valid_session_file_count"], 1)
        self.assertEqual(output["issues"]["session_unreadable_or_invalid_json"], 1)
        self.assertNotIn(SECRET, raw)

    def test_times_sorted_as_instants_and_not_guessed(self):
        self.write("chat_session_index.json", [{"id": FIRST, "inserted_at": "2024-01-01T00:00:00.5Z",
                                                 "updated_at": "2024-01-01T01:00:00+01:00"}])
        code, output, _ = self.run_tool("inventory")
        self.assertEqual(code, 0)
        self.assertEqual(output["index_time_range_utc"], {
            "earliest": "2024-01-01T00:00:00Z", "earliest_raw": "2024-01-01T01:00:00+01:00",
            "latest": "2024-01-01T00:00:00.500000Z", "latest_raw": "2024-01-01T00:00:00.5Z"})
        self.write("chat_session_index.json", [{"id": FIRST, "inserted_at": "2024-01-01T00:00:00"}])
        code, output, _ = self.run_tool("inventory")
        self.assertEqual(code, 1)
        self.assertIsNone(output["index_time_range_utc"])
        self.assertEqual(output["issues"]["invalid_index_time"], 1)

    def test_inputs_are_not_modified_and_attachments_not_opened(self):
        attachment_dir = self.root / "chat_sessions" / (FIRST + "_files")
        attachment_dir.mkdir()
        (attachment_dir / "image.txt").write_text(SECRET, encoding="utf-8")
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(self.run_tool("inventory", "--confirm-version", VERSION)[0], 1)
        self.assertEqual(self.extract()[0], 0)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_string_and_numeric_message_ids_do_not_collapse(self):
        session = sample_session()
        session["messages"][1]["id"] = "2"
        session["messages"][2]["parent_id"] = "2"
        self.write("chat_sessions/" + FIRST + ".json", session)
        code, output, _ = self.extract()
        self.assertEqual(code, 0)
        self.assertEqual([m["message_id"] for m in output["messages"]], [1, "2", 3])
        session["messages"][2]["parent_id"] = 2
        self.write("chat_sessions/" + FIRST + ".json", session)
        self.assertEqual(self.extract()[1]["error"], "parent_not_found")

    def test_session_requires_explicit_version_argument(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "session", str(self.root),
                                 "--session-id", FIRST], text=True, capture_output=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--confirm-version", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(SECRET, result.stderr)

    def test_required_bounded_window_and_no_text_outside_window(self):
        code, output, raw = self.extract(start=1, limit=1)
        self.assertEqual(code, 0)
        self.assertEqual(output["window"], {"start": 1, "limit": 1, "end_exclusive": 2,
                                             "uncovered_before": 1, "uncovered_after": 1})
        self.assertEqual([m["branch_index"] for m in output["messages"]], [1])
        self.assertIn("synthetic response", raw)
        self.assertNotIn("synthetic request", raw)
        self.assertNotIn("synthetic follow-up", raw)
        self.assertNotIn(SECRET, raw)
        self.assertEqual(self.extract(start=2, limit=100)[1]["window"]["uncovered_after"], 0)
        for start, limit, expected in [(-1, 1, "invalid_window"), (0, 0, "invalid_window"),
                                       (0, -1, "invalid_window"), (0, 101, "invalid_window"),
                                       (3, 1, "window_start_out_of_range")]:
            with self.subTest(start=start, limit=limit):
                code, output, raw = self.extract(start=start, limit=limit)
                self.assertEqual((code, output["error"]), (1, expected))
                self.assertNotIn("synthetic request", raw)
        for omitted in ("--start", "--limit"):
            args = ["--confirm-version", VERSION, "--session-id", FIRST,
                    "--start", "0", "--limit", "1"]
            i = args.index(omitted)
            del args[i:i + 2]
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "session", str(self.root), *args],
                                    text=True, capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(omitted, result.stderr)
            self.assertEqual(result.stdout, "")

    def test_unknown_metadata_is_safe_and_separate_for_entire_current_branch(self):
        session = sample_session()
        session["messages"][1]["fragments"][3]["type"] = SECRET * 100
        session["messages"][2]["fragments"].append({"type": "BAD " + SECRET, "content": SECRET})
        session["messages"][3]["fragments"].append({"type": "BAD_BRANCH_" + SECRET, "content": SECRET})
        self.write("chat_sessions/" + FIRST + ".json", session)
        code, output, raw = self.extract(start=0, limit=1)
        self.assertEqual(code, 0)
        self.assertEqual(output["unhandled_fragments_current_branch"], [
            {"message_id": 2, "fragment_index": 3, "kind": "unknown"},
            {"message_id": 3, "fragment_index": 1, "kind": "unknown"},
        ])
        self.assertEqual(output["skipped_fragment_counts_all_branches"]["unknown_type_fragments"], 3)
        self.assertTrue(output["current_branch_has_unhandled_fragments"])
        self.assertNotIn(SECRET, raw)
        self.assertNotIn("synthetic response", raw)

    def test_unrelated_index_problems_are_reported_but_do_not_block(self):
        self.write("chat_session_index.json", [
            {"id": FIRST}, {"id": SECOND, "inserted_at": "bad " + SECRET, "file_path": "../" + SECRET},
            {"id": SECOND}, {"id": SECRET}])
        code, output, raw = self.extract(start=0, limit=1)
        self.assertEqual(code, 0)
        self.assertEqual(output["other_index_issues"], {"duplicate_index_id": 1, "invalid_index_entry": 1,
                                                        "invalid_index_time": 1, "index_file_path_mismatch": 1})
        self.assertEqual(output["selected_index_issues"], {})
        self.assertNotIn(SECOND, raw)
        self.assertNotIn(SECRET, raw)
        self.write("chat_session_index.json", [{"id": FIRST, "inserted_at": SECRET}])
        code, output, raw = self.extract(start=0, limit=1)
        self.assertEqual(code, 0)
        self.assertEqual(output["selected_index_issues"], {"invalid_index_time": 1})
        self.assertNotIn(SECRET, raw)

    def test_inventory_problem_ids_are_opt_in_and_index_errors_remain_visible(self):
        self.write("chat_session_index.json", [{"id": FIRST, "title": SECRET},
                                                {"id": SECOND, "updated_at": SECRET}, {"id": SECOND}])
        code, output, raw = self.run_tool("inventory")
        self.assertEqual(code, 1)
        self.assertNotIn("problem_sessions", output)
        self.assertNotIn(FIRST, raw)
        self.assertNotIn(SECOND, raw)
        code, output, raw = self.run_tool("inventory", "--show-problem-ids")
        self.assertEqual(code, 1)
        self.assertEqual(output["problem_sessions"], [{"session_id": SECOND, "error_codes": [
            "duplicate_index_id", "invalid_index_time", "missing_indexed_file"]}])
        self.assertNotIn(FIRST, raw)
        self.assertNotIn(SECRET, raw)
        (self.root / "chat_session_index.json").write_text("invalid " + SECRET, encoding="utf-8")
        code, output, raw = self.run_tool("inventory", "--show-problem-ids")
        self.assertEqual(code, 1)
        self.assertEqual(output["index_file_error"], "unreadable_or_invalid_json")
        self.assertEqual(output["problem_sessions"], [])
        self.assertNotIn(SECRET, raw)
        self.assertNotIn(FIRST, raw)

    def test_inventory_diagnostic_identifies_failed_session_without_text(self):
        (self.root / "chat_sessions" / (FIRST + ".json")).write_text("invalid " + SECRET, encoding="utf-8")
        code, output, raw = self.run_tool("inventory", "--confirm-version", VERSION, "--show-problem-ids")
        self.assertEqual(code, 1)
        self.assertEqual(output["problem_sessions"], [{"session_id": FIRST,
                                                       "error_codes": ["session_unreadable_or_invalid_json"]}])
        self.assertNotIn(SECRET, raw)

    def test_strict_timestamps_preserve_raw_nanoseconds_and_never_echo_invalid(self):
        self.write("chat_session_index.json", [{"id": FIRST, "inserted_at": "2024-01-01T00:00:00.123456789Z",
                                                 "updated_at": "2024-01-01T00:00:00.123456788Z"}])
        output = self.run_tool("inventory")[1]
        self.assertEqual(output["index_time_range_utc"]["earliest_raw"], "2024-01-01T00:00:00.123456788Z")
        self.assertEqual(output["index_time_range_utc"]["latest_raw"], "2024-01-01T00:00:00.123456789Z")
        session = sample_session()
        session["messages"][0]["inserted_at"] = "2024-01-01T10:00:00.123456789+02:00"
        self.write("chat_sessions/" + FIRST + ".json", session)
        message = self.extract(start=0, limit=1)[1]["messages"][0]
        self.assertEqual(message["inserted_at_raw"], "2024-01-01T10:00:00.123456789+02:00")
        self.assertEqual(message["inserted_at_utc"], "2024-01-01T08:00:00.123456Z")
        for invalid in (SECRET, "2024-01-01 10:00:00Z", "2024-02-30T10:00:00Z",
                        "2024-01-01T10:00:00+01:60", "2024-01-01T10:00:00.1234567890Z"):
            with self.subTest(invalid=invalid):
                session["messages"][0]["inserted_at"] = invalid
                self.write("chat_sessions/" + FIRST + ".json", session)
                _, output, raw = self.extract(start=0, limit=1)
                self.assertIsNone(output["messages"][0]["inserted_at_raw"])
                self.assertIsNone(output["messages"][0]["inserted_at_utc"])
                self.assertNotIn(invalid, raw)

    def test_symlink_is_refused_before_opening(self):
        spec = importlib.util.spec_from_file_location("deepseek_tool_test_import", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        path = self.root / "chat_sessions" / (FIRST + ".json")
        with mock.patch.object(Path, "is_symlink", return_value=True), mock.patch.object(Path, "open") as opener:
            with self.assertRaises(module.Problem) as error:
                module.read_json(self.root.resolve(), path)
            self.assertEqual(error.exception.code, "unsafe_path")
            opener.assert_not_called()

    def test_symlinked_session_is_rejected_when_supported(self):
        path = self.root / "chat_sessions" / (FIRST + ".json")
        outside = self.root / "outside.json"
        outside.write_text(json.dumps(sample_session()), encoding="utf-8")
        path.unlink()
        try:
            path.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink creation is unavailable")
        self.assertEqual(self.extract()[1]["error"], "unsafe_path")
        code, output, _ = self.run_tool("inventory", "--confirm-version", VERSION)
        self.assertEqual(code, 1)
        self.assertEqual(output["issues"]["session_file_symlink"], 1)


if __name__ == "__main__":
    unittest.main()
