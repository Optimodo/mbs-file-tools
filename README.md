# MBS file tools

Windows utilities for **normalizing engineering drawing filenames** to a **seven-block document reference** (plus extension), with optional **whitelist validation** and support for **very long paths** (OneDrive, deep UNC folders).

**Repository:** [github.com/Optimodo/mbs-file-tools](https://github.com/Optimodo/mbs-file-tools)

---

## What these tools do

All tools operate on the **folder where the executable (or script) lives**. They **list**, **rename**, and **write text reports** on disk. They do **not** connect to the internet, cloud APIs, or remote services—the Python sources in this repository use only the standard library plus local file and Windows path APIs (see [Security and audit](#security-and-audit) below).

### Naming model (summary)

Filenames are interpreted as a **document reference** made of **seven segments** separated by dashes, optionally followed by revision markers and a **title**. Shared logic lives in `docref_core.py`:

1. Normalize underscores to dashes.
2. Strip Windows Explorer-style duplicate suffixes (e.g. ` - Copy`, ` (2)`).
3. Detect and strip trailing revision tokens where applicable.
4. Match the **core doc ref**: six non-numeric blocks plus a document number. The document number may be plain digits (`103402`), a **compound** `digits-digits` value (`675-001`, `51457-51458`), and/or a rare dotted sheet suffix (`51334.2`) kept as a literal `.N` (not rewritten to `-2`) — still one logical block.
5. Strip export **date/originator** tails shaped like `YYMMDD` or `YYMMDD_ORIGINATOR` (e.g. `_260717_WMS`) so they are not mistaken for a compound document number.
6. Optionally validate each block against **`docref_whitelist.json`** (fnmatch patterns and optional min/max length per block). Company codes such as `MBS` and `MAL20` are configured there.

See the module docstring in `docref_core.py` for the full parsing workflow.

### Executables (PyInstaller)

Short names keep command lines and paths manageable under Windows **MAX_PATH** limits. Build everything with **`build_all.bat`** (requires Python and PyInstaller; see [Build](#build)).

| Executable | Source script | Purpose | Output files |
|------------|---------------|---------|--------------|
| **FName.exe** | `rename_files_inplace.py` | Rename files in place to doc ref (or legacy cleanup if parsing does not yield a 7-block ref). | **`FNameReport.txt`**; if that name exists, **`FNameReport-1.txt`**, **`-2.txt`**, … |
| **FList.exe** | `list_files.py` | List files in the folder; parse stems into doc ref / title / notes (no renames). | **`filelist.txt`** with the same **`-1`**, **`-2`**, … scheme if needed |
| **FNamePro.exe** | `docref_rename_list.py` | Same parsing as FList, plus **renames** to doc-ref-only names; includes path-length diagnostics in the report. | **`report.txt`** with the same **`-1`**, **`-2`**, … scheme if needed |
| **FUndo.exe** | `undo_renames_from_reports.py` | **Undoes** successful renames from **FName** / **FNamePro** by reading every **`FNameReport*.txt`** and **`report*.txt`** in the folder (oldest → newest by file time), merging history so **later reports win** if the same target name appears more than once; then renames files back. No new report file. Optional: `python undo_renames_from_reports.py --dry-run`. |

Optional configuration: place **`docref_whitelist.json`** next to the exe (or script). Use **`docref_whitelist.example.json`** as a template; patterns use fnmatch (`*` allows all for a block).

### Long paths (Windows)

`win_longpath.py` is used by all rename/list/undo entry scripts. On Windows it uses **extended-length paths** (`\\?\` prefix) and, for renames, **`MoveFileW`** as a fallback when standard rename fails—helpful under long OneDrive paths. You may still need **long paths enabled** in Windows (Group Policy or `LongPathsEnabled`) for some scenarios.

---

## Requirements

- **Python 3.10+** (for running from source)
- **PyInstaller** (for building exes)—see `requirements.txt`

---

## Run from source

Clone the repo, install dependencies, and run the `.py` files from the project root so `docref_core` and `win_longpath` import correctly:

```bash
pip install -r requirements.txt
python list_files.py
python rename_files_inplace.py
python docref_rename_list.py
python undo_renames_from_reports.py
```

---

## Build

- **All exes:** `build_all.bat`
- **Individual:** `build_inplace.bat`, `build_list_files.bat`, `build_docref.bat`, `build_undo.bat`

Built executables land in **`dist/`** (also committed in this repo so you can download them without building). The **`build/`** folder and **`*.spec`** files are not versioned; batch scripts clean **`build/`** and remove **`*.spec`** after a successful build.

---

## Security and audit

This section is intended for **internal review** or **IT/security** questions about the shipped `.exe` files.

### Source of truth

- The **canonical behavior** is the **Python source** in this repository. The `.exe` files are **frozen bundles** of that source (plus the Python runtime) produced by **PyInstaller**.
- **Mapping for verification:** each executable is built from exactly one entry script, as shown in the table above. **FName**, **FList**, and **FNamePro** import **`docref_core.py`** and **`win_longpath.py`**. **FUndo** imports **`win_longpath.py`** only (no `docref_core`).

### Network and data handling

- Application code in this repo does **not** use HTTP clients, sockets, or subprocess calls to external programs for its core behavior (only standard library file/OS APIs and Windows path helpers).
- **Data stays local:** reads and writes are confined to the **working directory** (the folder containing the exe or script), typical outputs are **`.txt` reports** and **renamed files**; the optional **`docref_whitelist.json`** is read from disk if present.

### Reproducible builds (verify an exe yourself)

1. Clone this repository at a known commit.
2. Install Python and `pip install -r requirements.txt`.
3. Run `build_all.bat` (or the per-tool batch file).
4. Compare your **`dist\*.exe`** to a vendor-supplied binary (file hash, size, or a diff tool your organization prefers).

PyInstaller and Python versions affect byte-for-byte output; matching **the same commit, Python version, and PyInstaller version** is what matters for close reproduction.

### Dependencies

- **Runtime (in exe):** bundled Python interpreter + stdlib + this project’s modules.
- **Build-time:** PyInstaller (see `requirements.txt`).

### Code signing

Binaries built locally are **not** automatically **code-signed**. If your company requires a signed binary, use your **official signing pipeline** or run from **source** until signing is in place.

### Reporting issues

Use [GitHub Issues](https://github.com/Optimodo/mbs-file-tools/issues) on this repository for bugs or change requests.

---

## License

Add a `LICENSE` file when you publish (e.g. MIT or your company’s standard). Until then, treat usage as **internal / at your discretion**.
