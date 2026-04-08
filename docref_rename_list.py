"""
Rename drawing files to the 7-block document reference only (plus extension)
and write report.txt (or report-1.txt, report-2.txt, … if the base name exists)
with parallel columns for spreadsheets.

Uses win_longpath for deep OneDrive/UNC paths (\\?\ prefix + MoveFileW fallback on Windows).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

from docref_core import (
    basename_without_ext,
    default_whitelist_path,
    load_whitelist,
    parse_name_without_ext,
    pdf_dwg_notes,
)
from win_longpath import (
    list_directory,
    next_available_report_path,
    open_text_write,
    path_exists,
    path_isfile,
    path_length_report_lines,
    rename_file,
    warn_if_component_too_long,
)

REPORT_NAME = "report.txt"


def get_base_path():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_script_basename():
    return os.path.basename(sys.executable if getattr(sys, "frozen", False) else __file__)


def should_skip_processing(name: str, script_basename: str) -> bool:
    n = name.lower()
    sb = script_basename.lower()
    if n == sb:
        return True
    if n == "docref_whitelist.json":
        return True
    if n == REPORT_NAME.lower():
        return True
    if n in ("docref_core.py", "docref_rename_list.py", "win_longpath.py"):
        return True
    if n.endswith(".txt"):
        return True
    if n.endswith(".exe"):
        return True
    if n.endswith(".bat"):
        return True
    return False


def collect_unique_stems_in_order(filenames: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for f in filenames:
        stem = basename_without_ext(f)
        k = stem.lower()
        if k not in seen:
            seen.add(k)
            out.append(stem)
    return out


def run(target_folder: str | None = None) -> str | None:
    if target_folder is None:
        target_folder = get_base_path()
    else:
        target_folder = os.path.abspath(target_folder)

    script_basename = get_script_basename()
    report_path = next_available_report_path(target_folder, REPORT_NAME)

    try:
        all_names = [
            f
            for f in list_directory(target_folder)
            if path_isfile(os.path.join(target_folder, f))
            and not should_skip_processing(f, script_basename)
        ]
    except OSError as e:
        print(f"Cannot list folder: {e}")
        return None

    wl = load_whitelist(default_whitelist_path(target_folder))
    lines: list[str] = []

    lines.append("=" * 70)
    lines.append("DOC REF RENAME + LIST REPORT (FNamePro)")
    lines.append("=" * 70)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Folder: {target_folder}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("=== Path length diagnostics ===")
    lines.extend(path_length_report_lines(target_folder, all_names))
    lines.append("")
    lines.append("=" * 70)
    lines.append("")

    if not all_names:
        lines.append("No files to process.")
        with open_text_write(report_path) as rf:
            rf.write("\n".join(lines))
        print("No files to process.")
        return report_path

    ordered_stems = collect_unique_stems_in_order(all_names)
    refs: list[str] = []
    titles: list[str] = []
    revs: list[str] = []
    note_items: list[str] = []

    for stem in ordered_stems:
        pr = parse_name_without_ext(stem, wl)
        if pr.doc_ref:
            refs.append(pr.doc_ref)
            titles.append(pr.title or "")
            revs.append(pr.revision_pc or "")
        else:
            refs.append("")
            titles.append(pr.title or "")
            revs.append("")
            note_items.append(f"Unparsed stem (not renamed): {stem}")
        note_items.extend(f"Whitelist: {stem}: {n}" for n in pr.whitelist_notes)
        if pr.other_revisions:
            note_items.append(f"Non-P/C revision removed from stem {stem!r}: {pr.other_revisions!r}")
        note_items.extend(pr.warnings)

    lines.append("=== Unique stems (no extension), first-seen order ===")
    lines.extend(ordered_stems)
    lines.append("")
    lines.append("=== Document references ===")
    lines.extend(refs)
    lines.append("")
    lines.append("=== Document titles ===")
    lines.extend(titles)
    lines.append("")
    lines.append("=== P/C revision codes ===")
    lines.extend(revs)
    lines.append("")
    lines.append("=== File operations ===")

    renamed = 0
    skipped_same = 0
    skipped_dup = 0
    skipped_no_parse = 0
    errors: list[str] = []

    for fname in all_names:
        stem = basename_without_ext(fname)
        _, ext = os.path.splitext(fname)
        pr = parse_name_without_ext(stem, wl)
        if not pr.doc_ref:
            skipped_no_parse += 1
            msg = f"⊘ SKIP (unparsed): {fname}"
            lines.append(msg)
            print(msg)
            continue
        new_name = f"{pr.doc_ref}{ext}"
        comp_warn = warn_if_component_too_long(new_name)
        if comp_warn:
            lines.append(f"⚠ LENGTH: {fname} → {new_name}: {comp_warn}")
            note_items.append(f"{fname!r}: {comp_warn}")

        if new_name == fname:
            skipped_same += 1
            msg = f"⊘ NO CHANGE: {fname}"
            lines.append(msg)
            print(msg)
            continue

        old_path = os.path.join(target_folder, fname)
        new_path = os.path.join(target_folder, new_name)

        if path_exists(new_path) and os.path.normcase(os.path.abspath(old_path)) != os.path.normcase(
            os.path.abspath(new_path)
        ):
            skipped_dup += 1
            msg = f"⚠ SKIP (target exists): {fname} → {new_name}"
            if pr.windows_copy_markers_removed:
                msg += (
                    " (duplicate 'Copy'/(n) suffix was removed before parsing; "
                    "target name is already in use.)"
                )
                note_items.append(
                    f"{fname!r}: skipped rename to {new_name!r} — file exists; "
                    "Windows duplicate copy marker(s) were stripped from the name first."
                )
            lines.append(msg)
            print(msg)
            continue

        try:
            rename_file(old_path, new_path)
            renamed += 1
            msg_a = f"✓ RENAMED: {fname}"
            msg_b = f"   → {new_name}"
            lines.append(msg_a)
            lines.append(msg_b)
            lines.append(
                f"   (full path lengths: old={len(os.path.abspath(old_path))} new={len(os.path.abspath(new_path))})"
            )
            if pr.windows_copy_markers_removed:
                lines.append(
                    "   Note: Windows duplicate 'Copy'/(n) suffix was removed before deriving the new name "
                    f"(original file was {fname!r})."
                )
            print(msg_a)
            print(msg_b)
        except OSError as e:
            errors.append(f"{fname}: {e}")
            msg = f"❌ ERROR: {fname}: {e}"
            lines.append(msg)
            if sys.platform == "win32":
                lines.append(
                    "   Hint: enable long paths (LongPathsEnabled) or shorten folder depth; "
                    "extended paths were used."
                )
            print(msg)

    note_items.extend(pdf_dwg_notes(all_names))

    lines.append("")
    lines.append("=== Summary ===")
    lines.append(f"Renamed: {renamed}")
    lines.append(f"No change needed: {skipped_same}")
    lines.append(f"Skipped (unparsed): {skipped_no_parse}")
    lines.append(f"Skipped (duplicate target): {skipped_dup}")
    lines.append(f"Errors: {len(errors)}")
    lines.append("")
    lines.append("=== Notes ===")
    if note_items:
        lines.extend(note_items)
    else:
        lines.append("(none)")
    if errors:
        lines.append("")
        lines.append("=== Errors ===")
        lines.extend(errors)

    with open_text_write(report_path) as rf:
        rf.write("\n".join(lines))

    print(f"\nReport saved: {os.path.basename(report_path)}")
    return report_path


if __name__ == "__main__":
    run()
