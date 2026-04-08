import os
import sys
import re
from datetime import datetime

from docref_core import (
    default_whitelist_path,
    load_whitelist,
    parse_name_without_ext,
    strip_windows_duplicate_suffix,
)
from win_longpath import list_directory, open_text_write, path_exists, path_isfile, rename_file

FNAME_REPORT = "FNameReport.txt"

class Logger:
    """Logger that writes to both console and a log file."""
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.log_lines = []
    
    def log(self, message, to_console=True):
        """Log a message to both console and internal buffer."""
        if to_console:
            print(message)
        self.log_lines.append(message)
    
    def save(self):
        """Save all logged messages to the log file."""
        try:
            with open_text_write(self.log_file_path) as f:
                f.write("\n".join(self.log_lines))
            return True
        except Exception as e:
            print(f"Warning: Could not save log file: {e}")
            return False

def get_base_path():
    """
    Get the base path where the script/exe is located.
    This works both when running as a script and as a compiled exe.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def _split_name_and_extension(filename: str) -> tuple[str, str]:
    """Filename stem and extension, with loose extension detection when the dot is missing."""
    name_without_ext, extension = os.path.splitext(filename)
    if not extension:
        ext_match = re.search(r"([a-zA-Z]{3,4})$", name_without_ext)
        if ext_match:
            potential_ext = ext_match.group(1).lower()
            if potential_ext in [
                "pdf",
                "dwg",
                "doc",
                "docx",
                "xls",
                "xlsx",
                "txt",
                "jpg",
                "png",
            ]:
                name_without_ext = name_without_ext[: -len(potential_ext)]
                extension = "." + potential_ext
    return name_without_ext, extension


def _legacy_clean_stem(name_without_ext: str, extension: str, original_filename: str) -> tuple[str, list[str]]:
    """
    Older behaviour: space-dash-title regex and revision strip only.
    Used when docref_core cannot form a 7-block doc ref.
    """
    name_without_ext = name_without_ext.replace("_", "-")
    name_without_ext, copy_notes_raw = strip_windows_duplicate_suffix(name_without_ext)
    notes = [
        f"{original_filename!r}: removed Windows duplicate filename suffix {frag!r}."
        for frag in copy_notes_raw
    ]
    name_without_ext = re.sub(
        r"(-\d+(?:-\d+)?)-[A-Z]\d{1,2}(?=\s|$|-\s|[a-z])",
        r"\1",
        name_without_ext,
    )
    match = re.match(r"^(.+-\d+(?:-\d+)?)\s+-\s*[A-Z]", name_without_ext)
    if match:
        return f"{match.group(1)}{extension}", notes
    cleaned = name_without_ext.strip(" -")
    return f"{cleaned}{extension}", notes


def clean_filename(filename, whitelist=None):
    """
    Same target name as DocRefOrganizer / FileListGenerator when docref_core parses a 7-block ref.
    Otherwise falls back to the legacy space-dash-title regex (no listing/report features).

    Returns (new_filename, info_notes) — info_notes may include copy-suffix and parse warnings.
    """
    name_without_ext, extension = _split_name_and_extension(filename)

    pr = parse_name_without_ext(name_without_ext, whitelist)
    info_notes = list(pr.warnings)

    if pr.doc_ref:
        return f"{pr.doc_ref}{extension}", info_notes

    legacy_name, legacy_notes = _legacy_clean_stem(name_without_ext, extension, filename)
    return legacy_name, info_notes + legacy_notes

def rename_files_inplace(target_folder=None):
    """
    Rename files in-place within the target folder.
    If target_folder is None, uses the folder where the script/exe is located.
    """
    # Get the base path (where the exe or script is located)
    if target_folder is None:
        target_folder = get_base_path()
    else:
        target_folder = os.path.abspath(target_folder)
    
    log_file = os.path.join(target_folder, FNAME_REPORT)
    logger = Logger(log_file)

    # Log header
    logger.log("=" * 70)
    logger.log("FNAME - IN-PLACE RENAME REPORT")
    logger.log("=" * 70)
    logger.log(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.log(f"Target Folder: {target_folder}")
    logger.log("=" * 70)
    logger.log("")
    
    if not path_exists(target_folder):
        error_msg = f"ERROR: Target folder '{target_folder}' does not exist!"
        logger.log(error_msg)
        logger.save()
        return

    all_files = [
        f
        for f in list_directory(target_folder)
        if path_isfile(os.path.join(target_folder, f))
    ]
    
    # Filter out the script/exe and log files
    script_name = os.path.basename(sys.executable if getattr(sys, 'frozen', False) else __file__)
    files = [f for f in all_files if not f.endswith('.txt') and f != script_name and not f.endswith('.exe')]
    
    if not files:
        logger.log("No files found to process!")
        logger.save()
        return
    
    logger.log(f"Found {len(files)} file(s) to process")
    logger.log("")

    whitelist = load_whitelist(default_whitelist_path(target_folder))

    # Process each file - track different types of issues
    renamed_count = 0
    no_change_count = 0
    duplicate_count = 0
    errors = []
    
    duplicates = []
    no_changes = []
    successful = []
    
    def _had_copy_suffix_note(notes: list[str]) -> bool:
        return any("duplicate filename suffix" in n for n in notes)

    for filename in files:
        # Get the cleaned new filename (same doc-ref rules as DocRefOrganizer when parse succeeds)
        new_filename, info_notes = clean_filename(filename, whitelist)
        for note in info_notes:
            logger.log(f"ℹ️  {note}")

        # Full paths
        old_path = os.path.join(target_folder, filename)
        new_path = os.path.join(target_folder, new_filename)

        # Check if filename would change
        if filename == new_filename:
            logger.log(f"⊘ NO CHANGE: {filename}")
            logger.log(f"   → Filename already in correct format")
            logger.log("")
            no_change_count += 1
            no_changes.append(filename)
            continue

        # Check if target filename already exists (and it's not the same file)
        if path_exists(new_path) and os.path.normcase(os.path.abspath(old_path)) != os.path.normcase(
            os.path.abspath(new_path)
        ):
            logger.log(f"⚠️  SKIPPED (DUPLICATE): {filename}")
            logger.log(f"   → {new_filename} already exists in folder")
            if _had_copy_suffix_note(info_notes):
                logger.log(
                    "   (Explorer duplicate suffix was removed before computing target name; "
                    "original may already be the target file.)"
                )
            logger.log("")
            duplicate_count += 1
            duplicates.append({
                'original': filename,
                'target': new_filename,
                'reason': 'Target filename already exists'
            })
        else:
            try:
                rename_file(old_path, new_path)
                logger.log(f"✓ RENAMED: {filename}")
                logger.log(f"   → {new_filename}")
                if _had_copy_suffix_note(info_notes):
                    logger.log("   (Explorer duplicate suffix removed before rename.)")
                logger.log("")
                renamed_count += 1
                successful.append({
                    'original': filename,
                    'renamed': new_filename
                })
            except Exception as e:
                error_msg = f"ERROR renaming {filename}: {e}"
                logger.log(f"❌ ERROR: {filename}")
                logger.log(f"   → {error_msg}")
                logger.log("")
                errors.append(error_msg)
    
    # Detailed Summary Section
    logger.log("=" * 70)
    logger.log("PROCESSING SUMMARY")
    logger.log("=" * 70)
    logger.log(f"Total files processed: {len(files)}")
    logger.log(f"Successfully renamed: {renamed_count} file(s)")
    logger.log(f"No change needed: {no_change_count} file(s)")
    logger.log(f"Skipped (duplicates): {duplicate_count} file(s)")
    logger.log(f"Errors encountered: {len(errors)}")
    logger.log("=" * 70)
    logger.log("")
    
    # Detailed sections for issues
    if duplicates:
        logger.log("DUPLICATE FILES DETAILS:")
        logger.log("-" * 70)
        for i, dup in enumerate(duplicates, 1):
            logger.log(f"{i}. Original: {dup['original']}")
            logger.log(f"   Target: {dup['target']}")
            logger.log(f"   Reason: {dup['reason']}")
            logger.log("")
        logger.log("")
    
    if no_changes:
        logger.log("FILES WITH NO CHANGES NEEDED:")
        logger.log("-" * 70)
        for i, filename in enumerate(no_changes, 1):
            logger.log(f"{i}. {filename}")
        logger.log("")
        logger.log("")
    
    if errors:
        logger.log("ERRORS DETAILS:")
        logger.log("-" * 70)
        for i, error in enumerate(errors, 1):
            logger.log(f"{i}. {error}")
        logger.log("")
        logger.log("")
    
    if successful:
        logger.log("SUCCESSFULLY RENAMED FILES:")
        logger.log("-" * 70)
        for i, item in enumerate(successful, 1):
            logger.log(f"{i}. {item['original']}")
            logger.log(f"   → {item['renamed']}")
        logger.log("")
    
    logger.log("=" * 70)
    logger.log(f"Report saved to: {log_file}")
    logger.log("=" * 70)
    
    # Save the log file
    if logger.save():
        print(f"\n📄 Detailed report saved to: {os.path.basename(log_file)}")
    
    return renamed_count, no_change_count, duplicate_count, len(errors)

if __name__ == "__main__":
    print("=" * 60)
    print("FName - In-place rename")
    print("=" * 60)
    print()
    print("Renames files in this folder; see FNameReport.txt for the log.")
    print()
    
    rename_files_inplace()
    
    # Pause before closing (useful when running as exe)
    print()
    input("Press Enter to exit...")

