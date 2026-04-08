import os
import sys

from docref_core import (
    basename_without_ext,
    default_whitelist_path,
    load_whitelist,
    parse_name_without_ext,
    pdf_dwg_notes,
)
from win_longpath import list_directory, open_text_write, path_isfile

OUTPUT_NAME = "filelist.txt"


def get_base_path():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_script_basename():
    return os.path.basename(sys.executable if getattr(sys, "frozen", False) else __file__)


def should_skip_file(name: str, script_basename: str) -> bool:
    n = name.lower()
    sb = script_basename.lower()
    if n == sb:
        return True
    if n == OUTPUT_NAME.lower():
        return True
    if n == "list_files.bat":
        return True
    if n == "docref_whitelist.json":
        return True
    if n == "docref_core.py":
        return True
    if n == "win_longpath.py":
        return True
    if n == "report.txt":
        return True
    if n == "fnamereport.txt":
        return True
    if n.endswith(".exe") and n not in (sb,):
        return True
    if n.startswith("filerenamer_report_") and n.endswith(".txt"):
        return True
    if n.startswith("filerenamer_inplace_report_") and n.endswith(".txt"):
        return True
    if n.startswith("docref_report_") and n.endswith(".txt"):
        return True
    return False


def list_folder_files(base_path: str, script_basename: str) -> list[str]:
    out = []
    for item in list_directory(base_path):
        path = os.path.join(base_path, item)
        if path_isfile(path) and not should_skip_file(item, script_basename):
            out.append(item)
    return out


def write_filelist(base_path: str) -> str | None:
    script_basename = get_script_basename()
    all_files = list_folder_files(base_path, script_basename)
    if not all_files:
        return None

    whitelist = load_whitelist(default_whitelist_path(base_path))

    seen_base: set[str] = set()
    ordered_stems: list[str] = []
    for f in all_files:
        stem = basename_without_ext(f)
        key = stem.lower()
        if key not in seen_base:
            seen_base.add(key)
            ordered_stems.append(stem)

    refs: list[str] = []
    titles: list[str] = []
    rev_lines: list[str] = []
    unparseable: list[str] = []
    wl_all: list[str] = []

    for stem in ordered_stems:
        pr = parse_name_without_ext(stem, whitelist)
        for note in pr.whitelist_notes:
            wl_all.append(f"{stem}: {note}")
        if pr.doc_ref:
            refs.append(pr.doc_ref)
            titles.append(pr.title or "")
            if pr.revision_pc:
                rev_lines.append(pr.revision_pc)
            else:
                rev_lines.append("")
        else:
            refs.append("")
            titles.append(pr.title or "")
            rev_lines.append("")
            unparseable.append(stem)
        if pr.other_revisions:
            wl_all.append(f"{stem}: removed non-P/C revision token(s) {pr.other_revisions!r}")

    notes: list[str] = []
    notes.extend(pdf_dwg_notes(all_files))
    if unparseable:
        notes.append("Could not derive 7-block document reference for these stems (see alternate list below):")
        for s in unparseable:
            notes.append(f"  - {s}")
    if wl_all:
        notes.append("Whitelist / revision notes:")
        notes.extend(f"  - {x}" for x in wl_all)

    out_path = os.path.join(base_path, OUTPUT_NAME)
    with open_text_write(out_path) as f:
        f.write("=== Unique filename stems (no extension), first-seen folder order ===\n")
        for s in ordered_stems:
            f.write(s + "\n")
        f.write("\n=== Document references (same order; blank if not parsed) ===\n")
        for r in refs:
            f.write(r + "\n")
        f.write("\n=== Document titles (same order) ===\n")
        for t in titles:
            f.write(t + "\n")
        f.write("\n=== P/C revision codes (same order; blank if none) ===\n")
        for rv in rev_lines:
            f.write(rv + "\n")
        f.write("\n=== Alternate: stems that did not match the 7-block pattern ===\n")
        if unparseable:
            for s in unparseable:
                f.write(s + "\n")
        else:
            f.write("(none)\n")
        f.write("\n=== Notes ===\n")
        if notes:
            for line in notes:
                f.write(line + "\n")
        else:
            f.write("(none)\n")

    return out_path


def main():
    base_path = get_base_path()
    path = write_filelist(base_path)
    if path:
        print(f"Wrote {OUTPUT_NAME}")
        print(path)
    else:
        print("No files found to list (excluding this tool and report outputs).")


if __name__ == "__main__":
    main()
