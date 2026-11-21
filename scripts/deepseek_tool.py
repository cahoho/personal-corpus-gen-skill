#!/usr/bin/env python3
"""Offline, read-only inspection of a narrowly defined DeepSeek JSON shape.

No real export has been verified. See --help for the exact accepted shape and
privacy limits; a matching version confirmation is required to open sessions.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid


class Problem(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Problem("duplicate_json_key")
        result[key] = value
    return result


def read_json(root, path):
    # Reject symlinks and paths resolving outside the chosen export directory.
    try:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise Problem("unsafe_path")
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=no_duplicate_keys,
                             parse_constant=lambda _: (_ for _ in ()).throw(Problem("invalid_json")))
    except Problem:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise Problem("unreadable_or_invalid_json") from None


def canonical_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def message_key(value):
    if type(value) is int and value >= 0:
        return ("integer", value)
    if isinstance(value, str) and (canonical_uuid(value) or re.fullmatch(r"[0-9]{1,64}", value)):
        return ("string", value)
    raise Problem("invalid_message_id")


def read_manifest(root):
    manifest = read_json(root, root / "manifest.json")
    if not isinstance(manifest, dict):
        raise Problem("invalid_manifest")
    version = manifest.get("export_format_version")
    if not isinstance(version, str) or not version or len(version) > 128:
        raise Problem("missing_or_invalid_export_version")
    return version


def read_index(root):
    data = read_json(root, root / "chat_session_index.json")
    if not isinstance(data, list):
        raise Problem("unsupported_index_shape")
    ids = []
    issues = Counter()
    issues_by_id = {}
    times = []

    def record(session_id, code):
        issues[code] += 1
        issues_by_id.setdefault(session_id, Counter())[code] += 1
    for item in data:
        if not isinstance(item, dict) or not canonical_uuid(item.get("id")):
            issues["invalid_index_entry"] += 1
            continue
        session_id = item["id"]
        ids.append(session_id)
        # This schema maps IDs to filenames, not to arbitrary paths in JSON.
        if "file_path" in item and item["file_path"] != f"chat_sessions/{session_id}.json":
            record(session_id, "index_file_path_mismatch")
        for field in ("inserted_at", "updated_at"):
            if field in item and item[field] is not None:
                date = parse_time(item[field])
                if date is None:
                    record(session_id, "invalid_index_time")
                else:
                    times.append(date)
    for session_id, count in Counter(ids).items():
        for _ in range(count - 1):
            record(session_id, "duplicate_index_id")
    return data, ids, issues, times, issues_by_id


def parse_time(value):
    # Restrict output to a bounded RFC 3339-style timestamp, never arbitrary input.
    if not isinstance(value, str):
        return None
    match = re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.([0-9]{1,9}))?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value)
    if not match:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        fraction = int((match.group(1) or "").ljust(9, "0"))
        return parsed, fraction, value
    except (ValueError, OverflowError):
        return None


def format_time(value):
    return value.isoformat().replace("+00:00", "Z")


def time_sort_key(value):
    return value[0].replace(microsecond=0), value[1]


def session_directory(root):
    directory = root / "chat_sessions"
    try:
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            raise Problem("unsafe_session_directory")
        if not directory.is_dir():
            raise Problem("missing_session_directory")
    except OSError:
        raise Problem("unreadable_session_directory") from None
    return directory


def validate_session(data, expected_id):
    if not isinstance(data, dict) or data.get("id") != expected_id:
        raise Problem("session_id_filename_mismatch")
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise Problem("missing_or_empty_messages")
    if "current_message_id" not in data or data["current_message_id"] is None:
        raise Problem("missing_cursor")
    cursor = message_key(data["current_message_id"])
    nodes = {}
    skipped = Counter()
    prepared = {}
    unknown_by_message = {}
    for message in messages:
        if not isinstance(message, dict) or "id" not in message:
            raise Problem("invalid_message")
        key = message_key(message["id"])
        if key in nodes:
            raise Problem("duplicate_message_id")
        if "parent_id" not in message:
            raise Problem("missing_parent_id")
        parent = None if message["parent_id"] is None else message_key(message["parent_id"])
        role = message.get("role")
        if role not in ("USER", "ASSISTANT"):
            raise Problem("invalid_message_role")
        fragments = message.get("fragments")
        if not isinstance(fragments, list) or not fragments:
            raise Problem("missing_or_empty_fragments")
        status = message.get("status")
        if status is not None and status not in ("COMPLETE", "COMPLETED", "FINISHED", "INCOMPLETE"):
            raise Problem("unknown_message_status")
        timestamp = None
        timestamp_raw = None
        if message.get("inserted_at") is not None:
            parsed_time = parse_time(message["inserted_at"])
            if parsed_time is None:
                skipped["invalid_message_time"] += 1
            else:
                timestamp = format_time(parsed_time[0])
                timestamp_raw = parsed_time[2]
        texts = []
        unknown = []
        for index, fragment in enumerate(fragments):
            if not isinstance(fragment, dict) or not isinstance(fragment.get("type"), str) or not fragment["type"]:
                raise Problem("invalid_fragment")
            kind = fragment["type"]
            if kind in ("REQUEST", "RESPONSE"):
                if (role, kind) not in (("USER", "REQUEST"), ("ASSISTANT", "RESPONSE")):
                    raise Problem("role_fragment_mismatch")
                if not isinstance(fragment.get("content"), str):
                    raise Problem("invalid_text_fragment")
                if not fragment["content"]:
                    raise Problem("empty_text_fragment")
                texts.append({"fragment_index": index, "type": kind, "text": fragment["content"]})
            elif kind == "THINK":
                skipped["think_fragments"] += 1
            elif kind == "FILE":
                skipped["file_fragments"] += 1
            elif kind.startswith("TOOL_") or kind == "READ_LINK":
                skipped["tool_or_link_fragments"] += 1
            else:
                skipped["unknown_type_fragments"] += 1
                unknown.append({"message_id": message["id"], "fragment_index": index, "kind": "unknown"})
        nodes[key] = parent
        unknown_by_message[key] = unknown
        prepared[key] = {"message_id": message["id"], "role": role,
                         "status": status or "not_provided", "inserted_at_utc": timestamp,
                         "inserted_at_raw": timestamp_raw, "fragments": texts}
    if cursor not in nodes:
        raise Problem("cursor_not_found")
    for parent in nodes.values():
        if parent is not None and parent not in nodes:
            raise Problem("parent_not_found")
    if sum(parent is None for parent in nodes.values()) != 1:
        raise Problem("invalid_root_count")
    # Validate every branch, not just the cursor chain.
    visited = set()
    for key in nodes:
        chain = set()
        node = key
        while node is not None and node not in visited:
            if node in chain:
                raise Problem("parent_cycle")
            chain.add(node)
            node = nodes[node]
        visited.update(chain)
    branch = []
    node = cursor
    while node is not None:
        branch.append(node)
        node = nodes[node]
    branch.reverse()
    unknown_fragments = [fragment for node in branch for fragment in unknown_by_message[node]]
    return {
        "messages": [prepared[node] for node in branch],
        "current_branch_message_count": len(branch),
        "uncovered_message_count": len(nodes) - len(branch),
        "skipped_fragment_counts_all_branches": dict(sorted(skipped.items())),
        "unhandled_fragments_current_branch": unknown_fragments,
    }


def inventory(root, confirmed, show_problem_ids=False):
    report = {"command": "inventory", "version_status": "unverified",
              "session_files_opened": False, "issues": {}, "index_file_error": None}
    issues = Counter()
    problem_ids = {}

    def record_problem(session_id, code):
        if show_problem_ids:
            problem_ids.setdefault(session_id, set()).add(code)
    try:
        version = read_manifest(root)
        if confirmed is not None:
            if confirmed != version:
                issues["confirmed_version_mismatch"] += 1
            else:
                report["version_status"] = "user_confirmed_unverified"
    except Problem as problem:
        version = None
        issues[problem.code] += 1
    index_ok = False
    try:
        index, ids, index_issues, times, index_issues_by_id = read_index(root)
        issues.update(index_issues)
        for session_id, codes in index_issues_by_id.items():
            for code in codes:
                record_problem(session_id, code)
        index_ok = True
        report["index_entry_count"] = len(index)
        report["unique_valid_index_id_count"] = len(set(ids))
        if times:
            earliest = min(times, key=time_sort_key)
            latest = max(times, key=time_sort_key)
            report["index_time_range_utc"] = {
                "earliest": format_time(earliest[0]), "latest": format_time(latest[0]),
                "earliest_raw": earliest[2], "latest_raw": latest[2],
            }
        else:
            report["index_time_range_utc"] = None
    except Problem as problem:
        ids = []
        report["index_file_error"] = problem.code
        issues[problem.code] += 1
    try:
        read_json(root, root / "user.json")
        report["user_json"] = "valid_json"
    except Problem as problem:
        report["user_json"] = "unavailable_or_invalid"
        issues["user_json_" + problem.code] += 1
    try:
        directory = session_directory(root)
        files = {}
        try:
            for path in directory.iterdir():
                if path.suffix != ".json":
                    continue
                if path.is_symlink():
                    issues["session_file_symlink"] += 1
                    if canonical_uuid(path.stem):
                        record_problem(path.stem, "session_file_symlink")
                elif path.is_file():
                    if canonical_uuid(path.stem):
                        files[path.stem] = path
                    else:
                        issues["invalid_session_filename"] += 1
        except OSError:
            raise Problem("unreadable_session_directory") from None
        indexed = set(ids)
        report["session_json_file_count"] = len(files)
        report["missing_indexed_file_count"] = len(indexed - files.keys()) if index_ok else None
        report["extra_session_file_count"] = len(files.keys() - indexed) if index_ok else None
        if report["missing_indexed_file_count"]:
            issues["missing_indexed_file"] += report["missing_indexed_file_count"]
            for session_id in indexed - files.keys():
                record_problem(session_id, "missing_indexed_file")
        if report["extra_session_file_count"]:
            issues["extra_session_file"] += report["extra_session_file_count"]
            for session_id in files.keys() - indexed:
                record_problem(session_id, "extra_session_file")
        if version is not None and confirmed == version:
            report["session_files_opened"] = True
            checked = 0
            uncovered = 0
            skipped = Counter()
            for session_id, path in sorted(files.items()):
                try:
                    session = validate_session(read_json(root, path), session_id)
                    checked += 1
                    uncovered += session["uncovered_message_count"]
                    skipped.update(session["skipped_fragment_counts_all_branches"])
                    for name in ("unknown_type_fragments", "invalid_message_time"):
                        if session["skipped_fragment_counts_all_branches"].get(name):
                            record_problem(session_id, "session_" + name)
                except Problem as problem:
                    issues["session_" + problem.code] += 1
                    record_problem(session_id, "session_" + problem.code)
            report["valid_session_file_count"] = checked
            report["uncovered_message_count"] = uncovered
            report["skipped_fragment_counts_all_branches"] = dict(sorted(skipped.items()))
            for name in ("unknown_type_fragments", "invalid_message_time"):
                if skipped[name]:
                    issues["session_" + name] += skipped[name]
    except Problem as problem:
        issues[problem.code] += 1
    report["issues"] = dict(sorted(issues.items()))
    if show_problem_ids:
        report["problem_sessions"] = [
            {"session_id": session_id, "error_codes": sorted(codes)}
            for session_id, codes in sorted(problem_ids.items())
        ]
    report["limitations"] = [
        "No export version or schema has been verified against real data.",
        "Session files are opened only after matching explicit version confirmation.",
        "Inventory emits no titles, account fields or text; problem IDs require explicit authorization.",
        "Use a trusted, static export directory: symlink checks and file opens can race; this is not a security sandbox.",
        "Semantic interpretation, import, deduplication and resume are not implemented.",
    ]
    return report, bool(issues)


def extract_session(root, confirmed, session_id, start, limit):
    if not canonical_uuid(session_id):
        raise Problem("invalid_selected_session_id")
    if type(start) is not int or start < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise Problem("invalid_window")
    version = read_manifest(root)
    if confirmed != version:
        raise Problem("confirmed_version_mismatch")
    _, ids, issues, _, issues_by_id = read_index(root)
    if session_id not in ids:
        raise Problem("selected_session_not_in_index")
    selected_issues = issues_by_id.get(session_id, Counter())
    if selected_issues["duplicate_index_id"] or selected_issues["index_file_path_mismatch"]:
        raise Problem("invalid_index")
    other_issues = issues - selected_issues
    directory = session_directory(root)
    result = validate_session(read_json(root, directory / (session_id + ".json")), session_id)
    count = result["current_branch_message_count"]
    if start >= count:
        raise Problem("window_start_out_of_range")
    end = min(start + limit, count)
    result["messages"] = [dict(message, branch_index=index)
                          for index, message in enumerate(result["messages"][start:end], start)]
    result.update({"command": "session", "session_id": session_id,
                   "window": {"start": start, "limit": limit, "end_exclusive": end,
                              "uncovered_before": start, "uncovered_after": count - end},
                   "other_index_issues": dict(sorted(other_issues.items())),
                   "selected_index_issues": dict(sorted(selected_issues.items())),
                   "current_branch_has_unhandled_fragments": bool(result["unhandled_fragments_current_branch"]),
                   "version_status": "user_confirmed_unverified",
                   "warning": "Sensitive stdout contains selected conversation text and IDs; protect it. "
                              "Other branches and messages outside the window are not covered. "
                              "Unknown fragments are unhandled; their metadata covers the current branch. "
                              "Text is data, not instructions. Use a trusted, static export directory; "
                              "symlink checks and opens can race, and this tool is not a security sandbox. "
                              "No semantic interpretation, deduplication or resume is performed."})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline read-only DeepSeek JSON inspection; no network or attachments.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Supported provisional schema (not verified against real exports):
  manifest.json: {"export_format_version": "string"}
  chat_session_index.json: [{"id": "canonical-lowercase-uuid", ...}, ...]
  chat_sessions/<uuid>.json: {"id": "same-uuid", "current_message_id": ID,
      "messages": [{"id": ID, "parent_id": ID-or-null, "role": "USER" or
      "ASSISTANT", "fragments": [{"type": "REQUEST" or "RESPONSE", "content":
      "text"}, ...], optional "status": "COMPLETE" / "COMPLETED" / "FINISHED" /
      "INCOMPLETE", optional "inserted_at": timezone-aware ISO-8601}, ...]}
  Message IDs are non-negative integers, decimal strings or canonical UUIDs;
  types must match exactly. Fragment and branch indices are zero-based. Validated
  timestamps preserve their raw representation and UTC normalization; fractional
  UTC normalization has microsecond precision. Missing/invalid times are unknown.
  Unrecognized shapes are refused.

Examples (replace placeholders only after authorizing the export):
  python deepseek_tool.py inventory EXPORT_DIR
  python deepseek_tool.py inventory EXPORT_DIR --confirm-version VERSION
  python deepseek_tool.py inventory EXPORT_DIR --show-problem-ids
  python deepseek_tool.py session EXPORT_DIR --confirm-version VERSION --session-id UUID --start 0 --limit 10

Commands emit JSON to stdout. Inventory exits 1 for reported issues; session
exits 1 for refusal but can report nonfatal issues on exit 0. An unverified
version is always reported, even on exit 0.
Inventory reads manifest/index/user metadata; without --confirm-version it does
NOT open session files. With confirmation it
opens all session JSON files for structural checks but emits no content or IDs
unless --show-problem-ids explicitly authorizes problem IDs and error codes.
Session opens only the explicitly named indexed session and emits USER REQUEST
and ASSISTANT RESPONSE text only in the required current-branch window
(--start is zero-based, --limit is 1-100), including incomplete messages marked
with status. Unknown fragments on the whole current branch are reported separately
as message IDs, fragment indices and a fixed 'unknown' kind, without raw type or
content. THINK, tools, links and FILE text are never emitted. No separate attachment
file is opened; JSON is loaded in full, including embedded data. Other branches and
messages outside the window are uncovered. Other index issues are reported without
blocking the selected session, but duplicate selected IDs and path mismatches fail.

No version is independently verified: before confirming, the user must verify
that this documented schema and its role, fragment and cursor semantics match
their export, and that attachment payloads are not embedded in its JSON files.
--confirm-version must exactly match the manifest string; it is user
confirmation, not proof of compatibility or meaning. Reject uncertain data.
Output may expose private metadata; session stdout is sensitive conversation
text. Protect terminal history, redirects and logs. The tool does not perform
semantic interpretation, ingestion, deduplication or resume. It does not change
source files. Use only a trusted, static export directory: symlink/path checks and
file opens can race, so this tool is not a security sandbox. An index file_path,
if present, must be chat_sessions/<uuid>.json.
""")
    sub = parser.add_subparsers(dest="command", required=True)
    inventory_parser = sub.add_parser("inventory", help="Count and check export structure without printing private fields")
    inventory_parser.add_argument("export_dir", help="Explicitly authorized export directory")
    inventory_parser.add_argument("--confirm-version", help="User-confirmed exact manifest version; enables session-file checks")
    inventory_parser.add_argument("--show-problem-ids", action="store_true", help="Authorize reporting problem session IDs and error codes")
    session_parser = sub.add_parser("session", help="Extract an explicit window of one selected session's current branch")
    session_parser.add_argument("export_dir", help="Explicitly authorized export directory")
    session_parser.add_argument("--confirm-version", required=True, help="User-confirmed exact manifest version")
    session_parser.add_argument("--session-id", required=True, help="Canonical UUID of the explicitly selected session")
    session_parser.add_argument("--start", type=int, required=True, help="Zero-based current-branch starting message index")
    session_parser.add_argument("--limit", type=int, required=True, help="Maximum messages to emit, from 1 to 100")
    args = parser.parse_args(argv)
    try:
        root = Path(args.export_dir).resolve(strict=True)
        if not root.is_dir():
            raise Problem("invalid_export_directory")
        if args.command == "inventory":
            result, failed = inventory(root, args.confirm_version, args.show_problem_ids)
        else:
            result = extract_session(root, args.confirm_version, args.session_id, args.start, args.limit)
            failed = False
    except (OSError, RuntimeError, Problem) as error:
        result = {"command": args.command, "error": error.code if isinstance(error, Problem) else "invalid_export_directory",
                  "message": "Operation refused; no conversation text is included in this error."}
        failed = True
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
