"""
Shared logic for document-reference parsing, optional whitelist validation,
and drawing-set notes (e.g. PDF without paired DWG).

Parse workflow (after normalizing underscores to dashes):
0. Strip Windows Explorer duplicate suffixes: trailing " - Copy", " - Copy (n)", " (n)", or "(n)".
1. Strip a revision token at the very end (after the title), e.g. ... LAYOUT - P01 / -P01 / P01.
2. Match the 7-block document reference prefix (6 segments + document number).
3. Drop a spurious short numeric segment between specialisation and document number
   (e.g. ...-W-2-55026 -> ...-W-55026 after normalising underscores).
4. Parse the tail after the doc ref: optional revision (P01, C01, etc.) with flexible
   spaces/dashes, then the document title (canonical ' - ' or heuristic separators).
5. Merge P/C and other revisions; note conflicts if both end and mid revisions differ.
6. Validate the seven blocks and cross-check against the optional whitelist
   (fnmatch patterns and/or min_length / max_length per block).
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any

BLOCK_LABELS = [
    "Project Code",
    "Company Code",
    "Block",
    "Level",
    "Document Type",
    "Specialisation",
    "Document Number",
]

REVISION_PC = re.compile(r"^[PC]\d{1,2}$", re.IGNORECASE)
REVISION_OTHER = re.compile(r"^[A-Z]\d{1,2}$", re.IGNORECASE)

# Six non-numeric prefix blocks, then document number (digits or digits-digits).
_CORE_DOC_REF = re.compile(r"^((?:[^-]+-){6}\d+(?:-\d+)?)(.*)$")


@dataclass
class ParseResult:
    doc_ref: str | None
    """Seven logical blocks joined by dashes (no trailing revision segments)."""
    revision_pc: str | None
    """Revision like P01 / C02 if detected (not part of doc_ref)."""
    other_revisions: list[str] = field(default_factory=list)
    """Non-P/C revision tokens (e.g. A01)."""
    title: str | None = None
    warnings: list[str] = field(default_factory=list)
    whitelist_notes: list[str] = field(default_factory=list)
    windows_copy_markers_removed: bool = False
    """True if trailing ' - Copy' / '(n)' style suffixes were stripped before parsing."""


def normalize_stem(name_without_ext: str) -> str:
    """Underscores are treated as dashes everywhere."""
    return name_without_ext.replace("_", "-").strip()


def strip_windows_duplicate_suffix(stem: str) -> tuple[str, list[str]]:
    """
    Remove Explorer-style duplicate filename tails, repeatedly from the end:
    ' - Copy', ' - Copy (2)', ' (2)', or '(2)' glued to the last token (e.g. P13(2)).

    Returns (cleaned_stem, list of the literal substrings that were removed).
    """
    removed: list[str] = []
    s = stem.rstrip()
    while True:
        prev = s
        m = re.search(r"\s*-\s*copy(?:\s*\(\d+\))?\s*$", s, re.IGNORECASE)
        if m:
            frag = s[m.start() :]
            removed.append(frag.strip())
            s = s[: m.start()].rstrip()
            continue
        m = re.search(r"\s+\(\d+\)\s*$", s)
        if m:
            frag = s[m.start() :]
            removed.append(frag.strip())
            s = s[: m.start()].rstrip()
            continue
        m = re.search(r"\(\d+\)\s*$", s)
        if m:
            frag = s[m.start() :]
            removed.append(frag.strip())
            s = s[: m.start()].rstrip()
            continue
        if s == prev:
            break
    return s, removed


def _norm_rev_token(raw: str) -> str:
    return raw[0].upper() + raw[1:]


def _clean_title(raw: str | None) -> str | None:
    if not raw:
        return None
    t = raw.lstrip("-").strip()
    return t or None


def _strip_trailing_revision_suffix(s: str) -> tuple[str, str | None, list[str]]:
    """
    Remove one revision token at the end of the string (after the title).
    Accepts flexible separators: ' - P01', '-P01', ' P01', '- P01', etc.
    """
    rest = s.rstrip()
    trail_pc: str | None = None
    trail_other: list[str] = []

    m = re.search(
        r"(?:\s*-\s*|\s+|-)\s*([A-Z]\d{1,2})\s*$",
        rest,
        re.IGNORECASE,
    )
    if not m:
        return rest, None, []

    tok = _norm_rev_token(m.group(1))
    if not REVISION_OTHER.match(tok):
        return rest, None, []

    start = m.start()
    rest = rest[:start].rstrip()

    if REVISION_PC.match(tok):
        trail_pc = tok[0].upper() + tok[1:]
    else:
        trail_other.append(tok[0].upper() + tok[1:])

    return rest, trail_pc, trail_other


def _parse_tail_after_docref(tail: str) -> tuple[str | None, list[str], str | None, bool]:
    """
    After the 7-block doc ref: optional mid revision, then title.
    Returns (mid_pc, mid_other_revs, title, title_heuristic).
    """
    mid_pc: str | None = None
    mid_other: list[str] = []
    if not tail or not tail.strip():
        return None, [], None, False

    # Keep leading spaces so canonical " - TITLE" is not collapsed to "-TITLE".
    raw = tail.rstrip()
    ts = raw.strip()

    def set_mid(r: str) -> None:
        nonlocal mid_pc
        tok = _norm_rev_token(r)
        if REVISION_PC.match(tok):
            mid_pc = tok[0].upper() + tok[1:]
        else:
            mid_other.append(tok[0].upper() + tok[1:])

    # Mid revision only (whole tail, trimmed)
    mo = re.fullmatch(r"(?:\s*-\s*|\s+|-)\s*([A-Z]\d{1,2})\s*", ts, re.IGNORECASE)
    if mo:
        set_mid(mo.group(1))
        return mid_pc, mid_other, None, False

    # Mid revision + title (flexible gap) — before blind " - " split on raw
    mp = re.match(
        r"^(?:\s*-\s*|\s+|-)\s*([A-Z]\d{1,2})(?:\s*-\s+|\s+-\s+|\s+-\s*|\s+|-\s*)(.+)$",
        ts,
        re.IGNORECASE,
    )
    if mp:
        set_mid(mp.group(1))
        return mid_pc, mid_other, _clean_title(mp.group(2)), True

    # Mid revision + title: single dash between rev and title (-C01-DRAINAGE...)
    mrd = re.match(r"^(?:\s*-\s*|\s+|-)\s*([A-Z]\d{1,2})-\s*(.+)$", ts, re.IGNORECASE)
    if mrd:
        set_mid(mrd.group(1))
        return mid_pc, mid_other, _clean_title(mrd.group(2)), True

    # Title only: canonical space-dash-space (use raw so leading " - " is preserved)
    m = re.search(r"\s+-\s+", raw)
    if m:
        return None, [], _clean_title(raw[m.end() :]), False

    # Space-dash then letter (no space after dash): "51457 -BLOCK..."
    m = re.search(r"\s+-\s*(?=[A-Za-z])", raw)
    if m:
        return None, [], _clean_title(raw[m.end() :]), True

    # Dash then revision-only or title
    dm = re.match(r"^-\s*(.+)$", ts)
    if dm:
        rest = dm.group(1).strip()
        if re.fullmatch(r"[A-Z]\d{1,2}", rest, re.IGNORECASE):
            set_mid(rest)
            return mid_pc, mid_other, None, False
        return None, [], _clean_title(rest), True

    # Space then title
    sm = re.match(r"^\s+(.+)$", ts)
    if sm:
        return None, [], _clean_title(sm.group(1)), True

    # Title starts with a letter (no separator)
    if re.match(r"^[A-Za-z]", ts):
        return None, [], _clean_title(ts), True

    return None, [], None, True


def _pop_trailing_revisions(parts: list[str]) -> tuple[list[str], str | None, list[str]]:
    """Remove trailing letter+digit segments from dash-split parts (safety net)."""
    pc_rev: str | None = None
    other: list[str] = []
    while parts and REVISION_OTHER.match(parts[-1]):
        tok = parts.pop()
        if REVISION_PC.match(tok):
            if pc_rev is not None:
                other.insert(0, pc_rev)
            pc_rev = tok[0].upper() + tok[1:]
        else:
            other.insert(0, tok)
    return parts, pc_rev, other


def _strip_spurious_docnum_segment(parts: list[str]) -> tuple[list[str], str | None]:
    """
    Remove an extra numeric segment between the six prefix blocks and the document
    number, e.g. ...-W-2-55026 -> ...-W-55026 when ``2`` is a spurious insert.

    Heuristic: two trailing all-digit segments after six prefix blocks, where the
    penultimate segment is shorter than the final (typical main document number).
    Equal-length pairs are kept (e.g. 51457-51458 compound numbers).
    """
    if len(parts) < 8:
        return parts, None
    if not (parts[-1].isdigit() and parts[-2].isdigit()):
        return parts, None
    if len(parts) - 2 < 6:
        return parts, None
    short, main = parts[-2], parts[-1]
    if len(short) < len(main):
        return parts[:-2] + [main], short
    return parts, None


def _extract_body_and_docnum(parts: list[str]) -> tuple[list[str], str] | None:
    if not parts:
        return None
    if parts[-1].isdigit():
        if len(parts) >= 2 and parts[-2].isdigit():
            doc_num = f"{parts[-2]}-{parts[-1]}"
            body = parts[:-2]
        else:
            doc_num = parts[-1]
            body = parts[:-1]
    else:
        return None
    if len(body) != 6:
        return None
    return body, doc_num


def _apply_whitelist(
    body: list[str],
    doc_num: str,
    whitelist: dict[str, Any] | None,
) -> list[str]:
    notes: list[str] = []
    if not whitelist or not whitelist.get("blocks"):
        return notes
    blocks_cfg = whitelist["blocks"]
    if not isinstance(blocks_cfg, list) or len(blocks_cfg) == 0:
        return notes
    segments = body + [doc_num]
    for i, seg in enumerate(segments):
        if i >= len(blocks_cfg):
            break
        entry = blocks_cfg[i]
        if not isinstance(entry, dict):
            continue
        label = entry.get("name") or (BLOCK_LABELS[i] if i < len(BLOCK_LABELS) else f"block_{i+1}")
        slen = len(seg)

        mn = entry.get("min_length")
        if isinstance(mn, int) and slen < mn:
            notes.append(
                f"Block {i + 1} ({label}): value {seg!r} has length {slen}, below min_length {mn}"
            )
        mx = entry.get("max_length")
        if isinstance(mx, int) and slen > mx:
            notes.append(
                f"Block {i + 1} ({label}): value {seg!r} has length {slen}, above max_length {mx}"
            )

        patterns = entry.get("patterns") or entry.get("allowed") or []
        if not patterns:
            continue
        ok = any(fnmatch.fnmatch(seg, p) or fnmatch.fnmatch(seg.upper(), p.upper()) for p in patterns)
        if not ok:
            notes.append(
                f"Block {i + 1} ({label}): value {seg!r} did not match whitelist patterns {patterns!r}"
            )
    return notes


def parse_name_without_ext(
    name_without_ext: str,
    whitelist: dict[str, Any] | None = None,
) -> ParseResult:
    """
    Parse a filename stem (no extension) into doc ref (7 blocks), revisions, title.
    """
    warnings: list[str] = []
    copy_removed = False

    # 0a. Normalize: underscores -> dashes
    n = normalize_stem(name_without_ext)

    # 0b. Windows duplicate filename tails (" - Copy", "(2)", etc.)
    n, copy_tails = strip_windows_duplicate_suffix(n)
    if copy_tails:
        copy_removed = True
        tail_desc = "; ".join(repr(t) for t in copy_tails)
        warnings.append(
            f"{name_without_ext!r}: removed Windows duplicate filename suffix(es): {tail_desc}."
        )

    # 1. Revision at end (after title)
    n, trail_pc, trail_other = _strip_trailing_revision_suffix(n)

    # 2. Seven-block doc ref + tail
    m = _CORE_DOC_REF.match(n)
    if not m:
        warnings.append(
            f"{name_without_ext!r}: could not parse 7-block document reference "
            "(need 6 prefix blocks + numeric document number)."
        )
        return ParseResult(
            doc_ref=None,
            revision_pc=trail_pc,
            other_revisions=trail_other,
            title=None,
            warnings=warnings,
            windows_copy_markers_removed=copy_removed,
        )

    base = m.group(1).strip()
    # rstrip only: leading space before " - TITLE" must be preserved for canonical detection.
    tail = m.group(2).rstrip()

    # 3. Tail: mid revision + title (flexible separators)
    mid_pc, mid_other, title, title_heuristic = _parse_tail_after_docref(tail)
    if title_heuristic:
        warnings.append(
            f"{name_without_ext!r}: title/stem split used a non-standard separator heuristic; "
            "verify the detected title."
        )

    # 4. Merge P/C revision (trailing after title takes precedence if both differ)
    revision_pc = trail_pc if trail_pc else mid_pc
    if trail_pc and mid_pc and trail_pc != mid_pc:
        warnings.append(
            f"{name_without_ext!r}: conflicting P/C revisions after doc ref ({mid_pc}) vs after title "
            f"({trail_pc}); using {revision_pc}."
        )

    other_rev = list(trail_other)
    other_rev.extend(mid_other)

    # 5. Doc ref segments (safety: pop stray letter+digit segments glued on base)
    parts = [p for p in base.split("-") if p != ""]
    parts, pop_pc, pop_other = _pop_trailing_revisions(parts)
    if pop_pc:
        if revision_pc and revision_pc != pop_pc:
            warnings.append(
                f"{name_without_ext!r}: P/C revision also present as dash-suffix on doc ref ({pop_pc}); "
                "merged with field revision."
            )
        revision_pc = revision_pc or pop_pc
    if pop_other:
        other_rev.extend(pop_other)

    parts, spurious = _strip_spurious_docnum_segment(parts)
    if spurious is not None:
        warnings.append(
            f"{name_without_ext!r}: removed spurious numeric segment {spurious!r} "
            "between specialisation and document number."
        )

    extracted = _extract_body_and_docnum(parts)
    if extracted is None:
        if other_rev:
            warnings.append(
                f"{name_without_ext!r}: removed revision-like segment(s) {other_rev!r} but could not form "
                "6+document-number blocks."
            )
        warnings.append(
            f"{name_without_ext!r}: could not parse 7-block document reference "
            "(need 6 prefix blocks + numeric document number)."
        )
        return ParseResult(
            doc_ref=None,
            revision_pc=revision_pc,
            other_revisions=other_rev,
            title=title,
            warnings=warnings,
            windows_copy_markers_removed=copy_removed,
        )

    body, doc_num = extracted
    doc_ref = "-".join(body + [doc_num])

    # 6. Whitelist cross-check
    wl_notes = _apply_whitelist(body, doc_num, whitelist)

    return ParseResult(
        doc_ref=doc_ref,
        revision_pc=revision_pc,
        other_revisions=other_rev,
        title=title,
        warnings=warnings,
        whitelist_notes=wl_notes,
        windows_copy_markers_removed=copy_removed,
    )


def load_whitelist(config_path: str) -> dict[str, Any] | None:
    abs_p = os.path.abspath(config_path)
    candidates = [abs_p]
    if sys.platform == "win32":
        try:
            from win_longpath import to_extended_path

            ext = to_extended_path(abs_p)
            if ext not in candidates:
                candidates.append(ext)
        except ImportError:
            pass
    for p in candidates:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            continue
    return None


def default_whitelist_path(base_path: str) -> str:
    return os.path.join(base_path, "docref_whitelist.json")


def basename_without_ext(filename: str) -> str:
    return os.path.splitext(filename)[0]


def pdf_dwg_notes(filenames: list[str]) -> list[str]:
    """
    If most PDF basenames in the folder have a DWG sibling, note PDFs that lack a DWG.
    """
    by_base: dict[str, set[str]] = {}
    for f in filenames:
        base, ext = os.path.splitext(f)
        ext_l = ext.lower()
        if ext_l not in (".pdf", ".dwg"):
            continue
        by_base.setdefault(base.lower(), set()).add(ext_l)

    pdf_bases = [b for b, exts in by_base.items() if ".pdf" in exts]
    if not pdf_bases:
        return []

    with_dwg = sum(1 for b in pdf_bases if ".dwg" in by_base.get(b, set()))
    ratio = with_dwg / len(pdf_bases)
    if ratio < 0.5:
        return []

    notes: list[str] = []
    for b in sorted(pdf_bases):
        if ".dwg" not in by_base.get(b, set()):
            for f in filenames:
                root, ext = os.path.splitext(f)
                if ext.lower() != ".pdf":
                    continue
                if root.lower() == b:
                    notes.append(f"PDF without paired DWG (majority of PDFs have DWG): {root}")
                    break
    return notes
