"""Input source adapters (local path, GitHub URL).

All access is read-only. We never push, commit or modify the target repo.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ResolvedSource:
    source_type: str   # 'local' | 'github'
    source_label: str  # original user input
    local_path: Path   # path to read from
    cleanup_dir: Optional[Path] = None  # directory to remove after analysis (temp clones)

    def cleanup(self) -> None:
        if self.cleanup_dir and self.cleanup_dir.exists():
            shutil.rmtree(self.cleanup_dir, ignore_errors=True)


# Keep clones for the lifetime of the server so prompts can reference file paths;
# use a temp root under the workspace.
TMP_ROOT = Path(__file__).resolve().parents[2] / ".jev_clones"
TMP_ROOT.mkdir(parents=True, exist_ok=True)


def resolve(source: str) -> ResolvedSource:
    """Resolve a user-provided source string to a directory on disk.

    Accepts:
      - absolute local path
      - relative local path (resolved against CWD)
      - github URL of the form https://github.com/owner/repo(.git)
      - github shorthand owner/repo
    """
    source = source.strip()
    if not source:
        raise ValueError("Informe um caminho ou URL do repositório.")

    # GitHub URL
    gh = _parse_github(source)
    if gh is not None:
        owner, repo = gh
        return _clone_github(owner, repo, source)

    # Local path
    p = Path(source).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()
    if not p.exists():
        raise FileNotFoundError(f"Caminho não encontrado: {p}")
    if not p.is_dir():
        raise NotADirectoryError(f"O caminho informado não é um diretório: {p}")
    return ResolvedSource(source_type="local", source_label=source, local_path=p)


def _parse_github(source: str) -> Optional[tuple[str, str]]:
    """Return (owner, repo) or None."""
    s = source.rstrip("/")
    # Full URL
    m = re.match(r"^(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", s)
    if m:
        return m.group(1), m.group(2)
    # owner/repo shorthand
    m = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$", s)
    if m:
        return m.group(1), m.group(2)
    return None


def _clone_github(owner: str, repo: str, label: str) -> ResolvedSource:
    """Clone a public GitHub repo. Private repos will fail — surface clearly."""
    url = f"https://github.com/{owner}/{repo}.git"
    dest = TMP_ROOT / f"{owner}_{repo}_{uuid.uuid4().hex[:8]}"
    try:
        # Shallow clone for speed; no auth — public repos only.
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(
                "Não foi possível clonar o repositório.\n"
                f"url: {url}\n"
                f"stderr: {stderr}\n\n"
                "Repositórios privados exigem credenciais SSH/HTTPS que não estão configuradas nesta ferramenta. "
                "Para repositórios privados, faça um clone local e informe o caminho em 'Caminho local'."
            )
    except FileNotFoundError:
        raise RuntimeError("'git' não está instalado no ambiente; não foi possível clonar.")
    except subprocess.TimeoutExpired:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError("Timeout ao clonar (120s). Tente um repositório menor ou informar caminho local.")

    return ResolvedSource(
        source_type="github",
        source_label=label,
        local_path=dest,
        cleanup_dir=dest,
    )
