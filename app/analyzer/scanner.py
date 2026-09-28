"""Project scanner — walks a directory tree collecting signals.

Read-only by design. It never modifies files.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Extensions / files we consider source code (for counting & scanning)
CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".go", ".rs", ".rb", ".php", ".cs",
    ".scala", ".swift", ".html", ".css", ".scss", ".vue", ".svelte",
    ".sql", ".prisma", ".graphql",
}

# Files / directories to always ignore
IGNORE_FILE_PREFIXES = ("changelog", "changes", "history", "news")

IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", "out",
    ".next", ".nuxt", ".svelte-kit", ".output", ".parcel-cache",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".tox", ".nox", "coverage", "target", ".idea", ".vscode", ".arena",
    ".cache", ".local", ".npm", "vendor",
    # Docs & changelogs — they mention many integrations without using them
    "docs", "doc", "changelog", "changes", "CHANGES", "CHANGELOG",
    "examples", "example", "samples", "sample",
    "tests", "test", "__tests__", "spec", "specs",
    "site-packages",
}

MAX_FILE_SIZE = 512 * 1024  # 512 KB cap for source scanning
MAX_FILES_SCANNED = 2000


@dataclass
class ScanResult:
    root: Path
    project_name: str
    files: list[Path] = field(default_factory=list)
    files_by_ext: dict[str, int] = field(default_factory=dict)
    file_language: dict[Path, str] = field(default_factory=dict)
    markers: dict[str, Any] = field(default_factory=dict)
    package_json: dict | None = None
    requirements_txt: list[str] = field(default_factory=list)
    pyproject_toml: dict | None = None
    docker_files: list[Path] = field(default_factory=list)
    env_files: list[Path] = field(default_factory=list)
    ci_files: list[Path] = field(default_factory=list)
    readme_content: str = ""
    total_lines: int = 0

    # Contents cache (only for relevant/small files)
    _contents: dict[Path, str] = field(default_factory=dict)

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)


def _read_text_safe(path: Path, max_bytes: int = MAX_FILE_SIZE) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def scan_directory(root: str | Path) -> ScanResult:
    root = Path(root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    result = ScanResult(root=root, project_name=root.name)

    # Walk
    files_scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # prune ignored dirs in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".git")]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                if fpath.is_symlink():
                    continue
            except OSError:
                continue
            lname = fname.lower()
            # Skip changelog / history files (full of incidental mentions)
            if any(lname.startswith(p) for p in IGNORE_FILE_PREFIXES):
                continue
            # Skip files that look like docs text/reStructuredText/markdown for dep detection
            # (we still want README for summary)
            result.files.append(fpath)
            ext = fpath.suffix.lower()
            result.files_by_ext[ext] = result.files_by_ext.get(ext, 0) + 1
            files_scanned += 1
            if files_scanned > MAX_FILES_SCANNED:
                break

            # Language classification by extension
            lang = _ext_to_lang(ext, fname)
            if lang:
                result.file_language[fpath] = lang

            # Key markers
            lname = fname.lower()
            if lname == "package.json":
                content = _read_text_safe(fpath)
                if content:
                    import json as _json
                    try:
                        result.package_json = _json.loads(content)
                    except Exception:
                        pass
            elif lname == "requirements.txt":
                content = _read_text_safe(fpath)
                if content:
                    result.requirements_txt = [
                        ln.strip() for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")
                    ]
            elif lname in ("pyproject.toml", "poetry.lock", "pipfile"):
                if lname == "pyproject.toml":
                    content = _read_text_safe(fpath)
                    if content:
                        try:
                            import tomllib
                        except ModuleNotFoundError:
                            try:
                                import tomli as tomllib  # type: ignore
                            except ModuleNotFoundError:
                                tomllib = None  # type: ignore
                        if tomllib:
                            try:
                                result.pyproject_toml = tomllib.loads(content)
                            except Exception:
                                pass
            elif lname.startswith("dockerfile") or lname in ("docker-compose.yml", "docker-compose.yaml"):
                result.docker_files.append(fpath)
            elif lname.endswith(".env") or lname.startswith(".env"):
                # Record path but NEVER store contents
                result.env_files.append(fpath)
            elif dirpath.endswith(".github/workflows") or lname in (".gitlab-ci.yml", "jenkinsfile"):
                result.ci_files.append(fpath)
            elif lname.lower() in ("readme.md", "readme", "readme.rst", "readme.txt"):
                if not result.readme_content:
                    content = _read_text_safe(fpath, max_bytes=64 * 1024)
                    if content:
                        result.readme_content = content
        if files_scanned > MAX_FILES_SCANNED:
            break

    return result


def _ext_to_lang(ext: str, fname: str) -> str | None:
    mapping = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript (JSX)",
        ".ts": "TypeScript",
        ".tsx": "TypeScript (TSX)",
        ".mjs": "JavaScript",
        ".cjs": "JavaScript",
        ".java": "Java",
        ".kt": "Kotlin",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
        ".scala": "Scala",
        ".swift": "Swift",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".vue": "Vue",
        ".svelte": "Svelte",
        ".sql": "SQL",
        ".prisma": "Prisma",
        ".graphql": "GraphQL",
    }
    if ext in mapping:
        return mapping[ext]
    if fname == "Dockerfile" or fname.startswith("Dockerfile."):
        return "Dockerfile"
    return None


def read_content(result: ScanResult, path: Path) -> str | None:
    """Read a file from the scan result. Cached."""
    if path in result._contents:
        return result._contents[path]
    content = _read_text_safe(path)
    result._contents[path] = content
    return content


def grep_pattern(result: ScanResult, pattern: str, exts: set[str] | None = None,
                max_files: int = 200) -> list[tuple[Path, list[str]]]:
    """Simple regex grep across scanned source files. Returns (path, matching lines)."""
    rx = re.compile(pattern, re.IGNORECASE)
    hits: list[tuple[Path, list[str]]] = []
    for fpath in result.files:
        if exts and fpath.suffix.lower() not in exts:
            continue
        content = read_content(result, fpath)
        if not content:
            continue
        matching = []
        for ln in content.splitlines():
            if rx.search(ln):
                matching.append(ln.strip()[:200])
        if matching:
            hits.append((fpath, matching))
            if len(hits) >= max_files:
                break
    return hits


def file_count_by_language(result: ScanResult) -> dict[str, int]:
    counts: dict[str, int] = {}
    for lang in result.file_language.values():
        counts[lang] = counts.get(lang, 0) + 1
    return counts
