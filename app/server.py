"""FastAPI server for JEV Project Analyzer."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .analyzer.evaluator import build_report
from .analyzer.models import AnalysisReport
from .analyzer.prompt_builder import build_prompt
from .analyzer.scanner import scan_directory
from .analyzer.sources import resolve


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR.parent / "static"

app = FastAPI(title="JEV Project Analyzer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory store of analyses (MVP — single process, no DB).
@dataclass
class StoredAnalysis:
    id: str
    report: AnalysisReport
    # We keep the scan result available so the prompt builder can verify file existence.
    # For MVP we store the report (fully sufficient for dashboard) and a set of
    # file paths that existed at scan time, to filter affected files.
    existing_files: set[str] = field(default_factory=set)


_store: dict[str, StoredAnalysis] = {}


class AnalyzeRequest(BaseModel):
    source: str


class AnalyzeResponse(BaseModel):
    analysis_id: str
    counts: dict[str, Any]


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    try:
        resolved = resolve(req.source)
    except (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        scan = scan_directory(resolved.local_path)
        report = build_report(scan, source_type=resolved.source_type, source_path=resolved.source_label)

        if resolved.source_type == "github":
            # Warn that clone is temporary
            report.warnings.append(
                "Análise de repositório do GitHub feita por clone raso (depth=1). "
                "Apenas repositórios públicos funcionam sem credenciais. "
                "O clone temporário é limpo após o servidor reiniciar."
            )

        analysis_id = uuid.uuid4().hex[:12]
        existing_files = {scan.rel(f) for f in scan.files}
        _store[analysis_id] = StoredAnalysis(
            id=analysis_id,
            report=report,
            existing_files=existing_files,
        )
        return AnalyzeResponse(analysis_id=analysis_id, counts=report.summary())
    except Exception as e:
        # Cleanup if needed
        try:
            resolved.cleanup()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Erro durante a análise: {e}")


@app.get("/api/analysis/{analysis_id}")
def get_analysis(analysis_id: str) -> dict[str, Any]:
    stored = _store.get(analysis_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    return stored.report.to_dict()


@app.get("/api/analysis/{analysis_id}/prompt/{opp_index}")
def get_prompt(analysis_id: str, opp_index: int) -> dict[str, Any]:
    stored = _store.get(analysis_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    if opp_index < 0 or opp_index >= len(stored.report.opportunities):
        raise HTTPException(status_code=404, detail="Índice de oportunidade inválido.")

    # Build a minimal fake scan result containing only the existing files set
    # so the prompt builder filters affected files correctly.
    class _MiniScan:
        def __init__(self, files_rel: set[str]):
            self._files_rel = files_rel

        def rel(self, p):  # noqa: D401
            return str(p) if not isinstance(p, str) else p

        @property
        def files(self):
            return [Path(f) for f in self._files_rel]

    mini = _MiniScan(stored.existing_files)
    prompt = build_prompt(stored.report, opp_index, scan=mini)  # type: ignore[arg-type]
    return {
        "use_case": stored.report.opportunities[opp_index].use_case,
        "prompt": prompt,
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "analyses": len(_store)}


# ---- Static frontend ----
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
