r"""
Windows long-path helpers for OneDrive / UNC / deeply nested folders.

Uses ``\\?\`` (and ``\\?\UNC\``) so full paths can exceed the legacy ~260 limit
when the OS allows. On other platforms, paths are used as normal absolute paths.

Also tries MoveFileW as a fallback when os.replace fails (Windows only).
"""
from __future__ import annotations

import os
import re
import sys

_WIN32_MAX_COMPONENT = 255

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    def to_extended_path(path: str) -> str:
        path = os.fspath(path)
        if path.startswith("\\\\?\\"):
            return path
        abs_path = os.path.abspath(path)
        if abs_path.startswith("\\\\"):
            rest = abs_path[2:].lstrip("\\")
            return "\\\\?\\UNC\\" + rest.replace("/", "\\")
        return "\\\\?\\" + abs_path.replace("/", "\\")

    def path_exists(path: str) -> bool:
        return os.path.exists(to_extended_path(os.path.abspath(path)))

    def path_isfile(path: str) -> bool:
        return os.path.isfile(to_extended_path(os.path.abspath(path)))

    def list_directory(folder: str) -> list[str]:
        return os.listdir(to_extended_path(os.path.abspath(folder)))

    def rename_file(old_path: str, new_path: str) -> None:
        old_a = os.path.abspath(old_path)
        new_a = os.path.abspath(new_path)
        old_e = to_extended_path(old_a)
        new_e = to_extended_path(new_a)
        for o, n in ((old_a, new_a), (old_e, new_e)):
            try:
                os.replace(o, n)
                return
            except OSError:
                continue
        _move_file_w(old_e, new_e)

    def _move_file_w(src: str, dst: str) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        MoveFileW = kernel32.MoveFileW
        MoveFileW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        MoveFileW.restype = wintypes.BOOL
        if not MoveFileW(src, dst):
            err = ctypes.get_last_error()
            raise OSError(err, f"MoveFileW failed: {src!r} -> {dst!r}")

    def open_text_write(path: str):
        return open(
            to_extended_path(os.path.abspath(path)),
            "w",
            encoding="utf-8",
            newline="\n",
        )

else:

    def to_extended_path(path: str) -> str:
        return os.path.abspath(path)

    def path_exists(path: str) -> bool:
        return os.path.exists(os.path.abspath(path))

    def path_isfile(path: str) -> bool:
        return os.path.isfile(os.path.abspath(path))

    def list_directory(folder: str) -> list[str]:
        return os.listdir(os.path.abspath(folder))

    def rename_file(old_path: str, new_path: str) -> None:
        os.replace(os.path.abspath(old_path), os.path.abspath(new_path))

    def open_text_write(path: str):
        return open(os.path.abspath(path), "w", encoding="utf-8", newline="\n")


def next_available_report_path(base_dir: str, filename: str) -> str:
    """
    First path under base_dir that does not exist: name.ext, then name-1.ext,
    name-2.ext, ... (suffix before the extension).
    """
    base_dir = os.path.abspath(base_dir)
    stem, ext = os.path.splitext(filename)
    primary = os.path.join(base_dir, f"{stem}{ext}")
    if not path_exists(primary):
        return primary
    n = 1
    while True:
        candidate = os.path.join(base_dir, f"{stem}-{n}{ext}")
        if not path_exists(candidate):
            return candidate
        n += 1


def is_versioned_report_name(entry_name: str, template_filename: str) -> bool:
    """
    True if entry_name is the template basename or the same stem with -digits
    before the extension (e.g. template ``report.txt`` matches ``report-2.txt``).
    """
    stem, ext = os.path.splitext(template_filename.lower())
    n = entry_name.lower()
    if n == f"{stem}{ext}":
        return True
    return re.fullmatch(re.escape(stem) + r"-\d+" + re.escape(ext), n) is not None


def path_length_report_lines(target_folder: str, filenames: list[str]) -> list[str]:
    if sys.platform != "win32":
        return ["(path length diagnostics: Windows only)"]

    abs_dir = os.path.abspath(target_folder)
    lines = [
        f"Working directory full path length: {len(abs_dir)} characters",
        f"Win32 single-component limit (typical): {_WIN32_MAX_COMPONENT} characters",
        "",
    ]
    long_full: list[tuple[str, int]] = []
    long_name: list[tuple[str, int]] = []
    for name in filenames:
        full = os.path.join(abs_dir, name)
        long_full.append((name, len(full)))
        long_name.append((name, len(name)))
    long_full.sort(key=lambda x: -x[1])
    long_name.sort(key=lambda x: -x[1])

    lines.append("Longest full paths (top 10):")
    for name, ln in long_full[:10]:
        lines.append(f"  {ln} chars: {name[:80]}{'...' if len(name) > 80 else ''}")
    lines.append("")
    lines.append("Longest filename only (top 10):")
    for name, ln in long_name[:10]:
        flag = "  (>=255: may fail on some APIs)" if ln >= _WIN32_MAX_COMPONENT else ""
        lines.append(f"  {ln} chars{flag}: {name[:100]}{'...' if len(name) > 100 else ''}")
    return lines


def warn_if_component_too_long(filename: str) -> str | None:
    base = os.path.basename(filename)
    if len(base) >= _WIN32_MAX_COMPONENT:
        return (
            f"Filename component is {len(base)} chars (limit is often {_WIN32_MAX_COMPONENT}); "
            "rename may still fail."
        )
    return None
