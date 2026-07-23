import argparse
import ast
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# CONFIGURATION
SCRIPT_DIR = Path(__file__).parent.resolve()
DIST_DIR = SCRIPT_DIR.parent.parent
OUTPUT_FILENAME = "shortcuts.plugin"
SRC_DIR = SCRIPT_DIR
HEADER_FILE = SRC_DIR / "header.py"

PRIORITY_FILES = ["header.py"]
PRIORITY_DIRS = ["data", "i18n", "utils", "features", "ui"]
LAST_FILES = ["main.py"]

HEADER_WATERMARK = """
#          @@@@@@@@@@
#        @@@@@@@@@@@@
#       @@@@@        
#       @@@@         
# @@@@@@@@@@@@@@@@@@@
# @@@@@@@@@@@@@@@@@@@
#       @@@@         
#       @@@@         
#       @@@@         
#       @@@@         
#       @@@@         
#       @@@@         
# @@@@@@@@@@@@@@@@@@@
# @@@@@@@@@@@@@@@@@@@
"""

FOOTER_WATERMARK = """
#       @@@@        
# @@@@@@@@@@@@@@@@  
# @@@@@@@@@@@@@@@@  
# @@@@@@@@@@@@@@@@  
# @@@@@@@@@@@@@@@   
# @@@@@@@@@@@@@@@   
# @@@@@@@@@@@@@@@   
# @@@@@@@@@@@@@@@@  
# @@@@@@@@@@@@@@@@  
# @@@@@@@@@@@@@@@@  
"""

captured_imports = defaultdict(set)
captured_from_imports = defaultdict(set)

INTERNAL_MODULES = ("data", "i18n", "utils", "features", "ui")

def get_all_python_files(src: Path) -> list[Path]:
    return [p.relative_to(src) for p in src.rglob("*.py") if p.name not in ("__init__.py", "build.py")]

def get_merge_order(all_files: list[Path]) -> list[Path]:
    order = []
    processed: set[Path] = set()

    for pf in PRIORITY_FILES:
        p = Path(pf)
        if p in all_files:
            order.append(p)
            processed.add(p)

    for pd in PRIORITY_DIRS:
        dir_files = sorted([f for f in all_files if f.parts[0] == pd and f not in processed])
        order.extend(dir_files)
        processed.update(dir_files)

    last_paths = {Path(f) for f in LAST_FILES}
    others = sorted([f for f in all_files if f not in processed and f not in last_paths])
    order.extend(others)
    processed.update(others)

    for lf in LAST_FILES:
        p = Path(lf)
        if p in all_files:
            order.append(p)
            processed.add(p)

    return order

def parse_import_line(line: str):
    line = line.strip()

    from_match = re.match(r"^from ([\w.]+) import (.+)$", line)
    if from_match:
        module, names = from_match.groups()
        for name in names.split(","):
            captured_from_imports[module].add(name.strip())
        return

    import_match = re.match(r"^import ([\w.]+)$", line)
    if import_match:
        module = import_match.group(1)
        _ = captured_imports[module]

def normalize_import_block(import_lines: list[str]) -> str:
    block = " ".join(line.strip() for line in import_lines)
    block = re.sub(r"#.*", "", block)
    block = re.sub(r"\s+", " ", block)
    block = block.replace("( ", "").replace("(", "").replace(" )", "").replace(")", "")
    return block.strip()

def _is_internal(mod_name):
    if not mod_name:
        return False
    top = mod_name.split(".")[0]
    return top in INTERNAL_MODULES or top == "Shortcuts"

def generate_imports_block() -> str:
    lines = []
    for mod in sorted(captured_imports.keys()):
        if _is_internal(mod):
            continue
        lines.append(f"import {mod}")

    for mod in sorted(captured_from_imports.keys()):
        if _is_internal(mod):
            continue
        names = sorted(captured_from_imports[mod])
        lines.append(f"from {mod} import {', '.join(names)}")

    return "\n".join(lines) + "\n"

def process_file_content(file_path: Path) -> list[str]:
    with open(SRC_DIR / file_path, encoding="utf-8") as f:
        lines = f.readlines()

    processed_lines = []
    in_docstring = False
    docstring_char = None

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not in_docstring:
            if stripped.startswith('"""'):
                docstring_char = '"""'
            elif stripped.startswith("'''"):
                docstring_char = "'''"
            else:
                docstring_char = None

        if docstring_char and docstring_char in stripped:
            count = stripped.count(docstring_char)
            if count == 1:
                in_docstring = not in_docstring
                i += 1
                continue
            elif count >= 2:
                if not in_docstring:
                    i += 1
                    continue
                else:
                    in_docstring = False
                    docstring_char = None
                    i += 1
                    continue

        if in_docstring:
            i += 1
            continue

        if stripped.startswith("#"):
            i += 1
            continue

        is_import = stripped.startswith(("import ", "from "))
        if is_import:
            import_lines = [line]
            open_parens = line.count("(") - line.count(")")
            while open_parens > 0 and i + 1 < len(lines):
                i += 1
                next_line = lines[i]
                import_lines.append(next_line)
                open_parens += next_line.count("(") - next_line.count(")")

            block = normalize_import_block(import_lines)
            mod_match = re.match(r"^(?:from|import)\s+([\w.]+)", block)
            mod_name = mod_match.group(1) if mod_match else ""

            if not _is_internal(mod_name):
                parse_import_line(block)
            i += 1
            continue

        processed_lines.append(line)
        i += 1

    file_code = "".join(processed_lines)
    cleaned_code = file_code.strip()
    cleaned_code = re.sub(r"\n{3,}", "\n\n", cleaned_code)
    return [cleaned_code + "\n"]

def build():
    out_file = DIST_DIR / OUTPUT_FILENAME

    print(f"🚀 Building {OUTPUT_FILENAME} from {SRC_DIR}...")

    all_files = get_all_python_files(SRC_DIR)
    merge_order = get_merge_order(all_files)

    body_content = []
    for file_path in merge_order:
        print(f"📦 Merging: {file_path}")
        body_content.append(f"\n# === {file_path} ===\n")
        body_content.extend(process_file_content(file_path))

    imports_block = generate_imports_block()
    combined_code = HEADER_WATERMARK + "\n" + imports_block + "".join(body_content) + "\n\n" + FOOTER_WATERMARK

    DIST_DIR.mkdir(exist_ok=True)
    out_file.write_text(combined_code, encoding="utf-8")
    print(f"🎉 Build successful: {out_file} ({out_file.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    build()
