"""
Undo renames performed by FName (FNameReport*.txt) and FNamePro (report*.txt).

Scans the exe/script folder for all such reports (by name pattern), orders them
oldest to newest by file modification time, parses ✓ RENAMED lines, composes
a net map current_name -> original_name (later reports win if the same target
name appears again), then renames back using win_longpath.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Iterable

from win_longpath import (
    list_directory,
    path_exists,
    path_isfile,
    rename_file,
    to_extended_path,
)

RENAMED_PREFIX = "\u2713 RENAMED:"  # ✓ RENAMED:
ARROW_LINE = re.compile(r"^\s*\u2192\s*(.+?)\s*$")  # → newname


def get_base_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def is_rename_report_file(name: str) -> bool:
    n = name.lower()
    if re.fullmatch(r"fnamereport(?:-\d+)?\.txt", n):
        return True
    if re.fullmatch(r"report(?:-\d+)?\.txt", n):
        return True
    return False


def discover_report_paths(folder: str) -> list[str]:
    out: list[tuple[float, str]] = []
    for item in list_directory(folder):
        path = os.path.join(folder, item)
        if not path_isfile(path) or not is_rename_report_file(item):
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        out.append((mtime, path))
    out.sort(key=lambda x: (x[0], os.path.basename(x[1]).lower()))
    return [p for _, p in out]


def parse_renamed_pairs(lines: Iterable[str]) -> list[tuple[str, str]]:
    """(original_name, new_name) in file order."""
    pairs: list[tuple[str, str]] = []
    it = iter(lines)
    for line in it:
        if not line.startswith(RENAMED_PREFIX):
            continue
        old = line[len(RENAMED_PREFIX) :].strip()
        if not old:
            continue
        try:
            nxt = next(it)
        except StopIteration:
            break
        m = ARROW_LINE.match(nxt)
        if not m:
            continue
        new = m.group(1).strip()
        if new:
            pairs.append((old, new))
    return pairs


def _open_read_text(path: str):
    abs_p = os.path.abspath(path)
    candidates = [abs_p]
    if sys.platform == "win32":
        ext = to_extended_path(abs_p)
        if ext not in candidates:
            candidates.insert(0, ext)
    last_err: OSError | None = None
    for p in candidates:
        try:
            return open(p, encoding="utf-8", errors="replace")
        except OSError as e:
            last_err = e
    if last_err:
        raise last_err
    raise OSError(path)


def load_report_pairs(path: str) -> list[tuple[str, str]]:
    try:
        with _open_read_text(path) as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    return parse_renamed_pairs(lines)


def compose_current_to_original(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """
    Apply forward renames in order; return map {current_on_disk: original_name}.
    If the same target name is renamed again later, the later pair wins (same
    rule as re-running the tools on the folder).
    """
    current_to_original: dict[str, str] = {}
    for old, new in pairs:
        source = current_to_original.pop(old, old)
        current_to_original[new] = source
    return current_to_original


def undo_folder(folder: str, *, dry_run: bool) -> tuple[int, int, list[str]]:
    """
    Returns (done_count, skipped_count, messages).
    """
    reports = discover_report_paths(folder)
    if not reports:
        return 0, 0, ["No FNameReport*.txt or report*.txt files found in this folder."]

    all_pairs: list[tuple[str, str]] = []
    msgs: list[str] = []
    for rp in reports:
        pairs = load_report_pairs(rp)
        if pairs:
            msgs.append(f"From {os.path.basename(rp)}: {len(pairs)} rename line(s)")
        all_pairs.extend(pairs)

    if not all_pairs:
        return 0, 0, msgs + ["No ✓ RENAMED entries found in those reports."]

    net = compose_current_to_original(all_pairs)
    if not net:
        return 0, 0, msgs + ["Nothing to undo (empty composition)."]

    msgs.append(f"Net undo: {len(net)} file(s) to restore to earlier name(s).")

    done = 0
    skipped = 0
    for current, original in sorted(net.items(), key=lambda x: x[0].lower()):
        cur_path = os.path.join(folder, current)
        orig_path = os.path.join(folder, original)
        if current == original:
            skipped += 1
            continue
        if not path_isfile(cur_path):
            msgs.append(f"SKIP (missing): {current!r} — cannot rename back to {original!r}")
            skipped += 1
            continue
        if path_exists(orig_path):
            if os.path.normcase(os.path.abspath(cur_path)) == os.path.normcase(
                os.path.abspath(orig_path)
            ):
                skipped += 1
                continue
            msgs.append(f"SKIP (exists): {original!r} already exists — left {current!r} unchanged")
            skipped += 1
            continue
        if dry_run:
            msgs.append(f"DRY-RUN: {current!r} -> {original!r}")
            done += 1
            continue
        try:
            rename_file(cur_path, orig_path)
            msgs.append(f"OK: {current!r} -> {original!r}")
            done += 1
        except OSError as e:
            msgs.append(f"ERROR: {current!r} -> {original!r}: {e}")
            skipped += 1

    return done, skipped, msgs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Undo FName / FNamePro renames using report files in this folder."
    )
    parser.add_argument(
        "--folder",
        default=None,
        help="Folder containing reports and files (default: folder of this exe/script)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List actions only; do not rename files",
    )
    args = parser.parse_args()
    folder = os.path.abspath(args.folder or get_base_path())

    print("Undo renames from FName / FNamePro reports")
    print(f"Folder: {folder}")
    print()

    done, skipped, msgs = undo_folder(folder, dry_run=args.dry_run)
    for line in msgs:
        print(line)
    print()
    if args.dry_run:
        print(f"Dry-run complete ({done} would run, {skipped} skipped).")
    else:
        print(f"Finished: {done} renamed back, {skipped} skipped.")

    if getattr(sys, "frozen", False):
        print()
        print("Press any key to close this window...")
        if sys.platform == "win32":
            try:
                import msvcrt

                msvcrt.getch()
            except ImportError:
                input("Press Enter to close...")
        else:
            input("Press Enter to close...")


if __name__ == "__main__":
    main()
