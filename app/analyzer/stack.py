"""Detect technology stack from scan results."""
from __future__ import annotations

from typing import Any

from .models import StackInfo
from .scanner import ScanResult, file_count_by_language


# —— Framework signatures ——
# Each hint is a SUBSTRING that must appear in a DEPENDENCY NAME (from package.json/requirements/pyproject).
# For code-level signals, rely on the second entry which is more specific (import patterns) checked via _code_contains.
PY_FRAMEWORK_SIGNATURES = {
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "Starlette": ["starlette"],
    "SQLAlchemy": ["sqlalchemy"],
    "Alembic": ["alembic"],
    "Pydantic": ["pydantic"],
    "Celery": ["celery"],
    "Django REST Framework": ["djangorestframework", "rest_framework"],
    "LangChain": ["langchain"],
    "LlamaIndex": ["llama-index", "llama_index"],
    "Pytest": ["pytest"],
    "Streamlit": ["streamlit"],
}

JS_FRAMEWORK_SIGNATURES = {
    "React": ["react"],
    "Next.js": ["next"],
    "Vue": ["vue"],
    "Nuxt": ["nuxt", "nuxt3"],
    "Angular": ["@angular/core"],
    "Svelte": ["svelte"],
    "Express": ["express"],
    "NestJS": ["@nestjs/core", "@nestjs/common"],
    "Koa": ["koa"],
    "TypeORM": ["typeorm"],
    "Prisma": ["@prisma/client"],
    "Axios": ["axios"],
    "Tailwind": ["tailwindcss"],
    "Vite": ["vite"],
    "Jest": ["jest"],
}

DB_SIGNATURES = {
    "PostgreSQL": ["psycopg", "psycopg2", "pg8000", "asyncpg", "postgresql", "pg"],
    "MySQL": ["mysql", "mariadb", "pymysql", "mysql2"],
    "SQLite": ["sqlite3", "aiosqlite"],
    "MongoDB": ["pymongo", "mongodb", "mongoose", "motor"],
    "Redis": ["redis", "ioredis", "aioredis"],
    "Cassandra": ["cassandra-driver"],
    "Elasticsearch": ["elasticsearch", "@elastic/elasticsearch"],
    "Firebase": ["firebase-admin", "firebase"],
    "Supabase": ["supabase", "@supabase/supabase-js"],
    "DynamoDB": ["boto3", "@aws-sdk/client-dynamodb"],
    "RabbitMQ": ["pika", "aio-pika", "amqp", "amqplib"],
    "Kafka": ["kafka-python", "confluent-kafka", "kafkajs"],
    "SQS": ["boto3", "@aws-sdk/client-sqs"],
    "BullMQ": ["bullmq", "bull"],
}

INFRA_SIGNATURES = {
    "Docker": ["Dockerfile", "docker-compose"],
    "Kubernetes": ["k8s", "kubernetes", "deployment.yaml", "deployment.yml", "kind: Deployment"],
    "AWS": ["aws-", "boto3", "@aws-sdk", "amazonaws"],
    "GCP": ["google-cloud", "@google-cloud", "firebase"],
    "Azure": ["azure"],
    "Vercel": ["vercel"],
    "Cloudflare": ["cloudflare"],
    "Nginx": ["nginx"],
    "Terraform": [".tf", "terraform"],
}

AUTH_SIGNATURES = {
    "JWT": ["jwt", "jsonwebtoken", "pyjwt", "jose"],
    "OAuth": ["oauth", "openid", "oidc"],
    "Auth0": ["auth0"],
    "Clerk": ["clerk"],
    "Supabase Auth": ["supabase"],
    "Firebase Auth": ["firebase/auth"],
    "NextAuth/Auth.js": ["next-auth", "nextauth", "auth.js", "nextauth"],
    "bcrypt": ["bcrypt"],
    "Session/Auth Cookie": ["session", "cookie", "csrf"],
}


def detect_stack(scan: ScanResult) -> StackInfo:
    info = StackInfo()

    # Languages
    lang_counts = file_count_by_language(scan)
    info.languages = [l for l, _ in sorted(lang_counts.items(), key=lambda x: -x[1])]

    # Frameworks — check package.json + requirements.txt + file-content hints
    deps = _collect_dependencies(scan)

    # Code-level imports (only .py/.js/.ts files, excluding docs/tests/examples)
    code_hits = _grep_deps_code(scan)

    for fw, hints in PY_FRAMEWORK_SIGNATURES.items():
        if _any_match(deps, hints) or _code_has(code_hits, hints):
            info.frameworks.append(fw)
    for fw, hints in JS_FRAMEWORK_SIGNATURES.items():
        if _any_match(deps, hints) or _code_has(code_hits, hints):
            info.frameworks.append(fw)

    # Dedup preserving order
    info.frameworks = _dedup(info.frameworks)

    # Databases
    for db, hints in DB_SIGNATURES.items():
        if _any_match(deps, hints) or _code_has(code_hits, hints):
            info.databases.append(db)
    info.databases = _dedup(info.databases)

    # Infrastructure
    if scan.docker_files:
        info.infrastructures.append("Docker")
    for infra, hints in INFRA_SIGNATURES.items():
        if infra == "Docker":
            continue
        if _any_match(deps, hints) or _file_marker(scan, hints):
            info.infrastructures.append(infra)
    info.infrastructures = _dedup(info.infrastructures)

    # Package managers
    if scan.package_json:
        info.package_managers.append("npm/yarn/pnpm")
    if scan.requirements_txt or scan.pyproject_toml:
        info.package_managers.append("pip")
    if (scan.root / "poetry.lock").exists():
        info.package_managers.append("poetry")
    if (scan.root / "Pipfile").exists():
        info.package_managers.append("pipenv")
    info.package_managers = _dedup(info.package_managers)

    # Services (detected via filename / deps)
    if _any_match(deps, ["stripe", "@stripe"]):
        info.services.append("Stripe (payments)")
    if _any_match(deps, ["paypal"]):
        info.services.append("PayPal")
    if _any_match(deps, ["mercadopago"]):
        info.services.append("MercadoPago")
    if _any_match(deps, ["twilio", "sendgrid", "resend", "nodemailer", "smtplib"]):
        info.services.append("Email/SMS")
    if _any_match(deps, ["whatsapp", "twilio", "meta-whatsapp", "wppconnect", "baileys"]):
        info.services.append("WhatsApp")
    if _any_match(deps, ["slack", "@slack"]):
        info.services.append("Slack")
    if _any_match(deps, ["discord"]):
        info.services.append("Discord")
    if _any_match(deps, ["telegram"]):
        info.services.append("Telegram")
    if _any_match(deps, ["openai", "anthropic", "gemini", "cohere", "groq"]):
        info.services.append("LLM provider")
    if _any_match(deps, ["sentry"]):
        info.services.append("Sentry")
    if _any_match(deps, ["newrelic", "datadog"]):
        info.services.append("APM/Datadog/NewRelic")
    info.services = _dedup(info.services)

    # Auth
    for a, hints in AUTH_SIGNATURES.items():
        if _any_match(deps, hints) or _file_marker(scan, hints):
            info.services.append(f"Auth: {a}")
    info.services = _dedup(info.services)

    return info


def _collect_dependencies(scan: ScanResult) -> set[str]:
    deps: set[str] = set()
    if scan.package_json:
        for key in ("dependencies", "devDependencies"):
            deps.update((scan.package_json.get(key) or {}).keys())
    for line in scan.requirements_txt:
        # strip version specifiers
        name = re_split_name(line)
        if name:
            deps.add(name.lower())
    if scan.pyproject_toml:
        # Try poetry / pep621 shapes
        project = scan.pyproject_toml.get("project", {}) or {}
        for dep in project.get("dependencies", []) or []:
            deps.add(re_split_name(dep).lower())
        poetry = (scan.pyproject_toml.get("tool") or {}).get("poetry", {}) or {}
        for key in ("dependencies", "dev-dependencies"):
            for name in (poetry.get(key) or {}).keys():
                deps.add(name.lower())
    # NOTE: filenames are checked separately via _file_marker,
    # they should NOT be mixed into the dependency set (it causes false positives).
    return deps


def re_split_name(dep_line: str) -> str:
    import re
    m = re.match(r"^([A-Za-z0-9_\-\.]+)", dep_line.strip())
    return m.group(1) if m else ""


def _grep_deps_code(scan: ScanResult) -> set[str]:
    """Scan a small sample of source files for import lines to detect frameworks."""
    hits: set[str] = set()
    exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
    skip_seg = {"docs", "doc", "test", "tests", "examples", "example", "samples", "sample"}
    checked = 0
    for fpath in scan.files:
        if checked >= 200:
            break
        parts = set(p.lower() for p in fpath.parts)
        if parts & skip_seg:
            continue
        if fpath.suffix.lower() not in exts:
            continue
        try:
            content = None
            # use cached reader if available
            if hasattr(scan, "_contents") and fpath in scan._contents:
                content = scan._contents[fpath]
            else:
                content = None
            if content is None:
                from .scanner import read_content
                content = read_content(scan, fpath)
            if not content:
                continue
            # Look at first ~200 real code lines for import statements
            in_doc = False
            code_lines = 0
            for ln in content.splitlines():
                s = ln.strip()
                if not s:
                    continue
                # Skip docstring blocks / comments
                if s.startswith('"""') or s.startswith("'''"):
                    in_doc = not in_doc
                    if s.count('"""') == 2 or s.count("'''") == 2:
                        in_doc = not in_doc
                    continue
                if in_doc:
                    continue
                if s.startswith("#"):
                    continue
                l = s.lower()
                if l.startswith(("import ", "from ", "const ", "let ", "var ")) or "require(" in l or "from '" in l or 'from "' in l:
                    hits.add(l)
                code_lines += 1
                if code_lines >= 200:
                    break
            checked += 1
        except Exception:
            continue
    return hits


def _code_has(code_hits: set[str], hints: list[str]) -> bool:
    import re
    for h in hints:
        h_low = h.lower()
        # Build a regex that matches the hint as a dotted module path, not as a random substring
        # Accept: "h", "h.", "'h", '"h', "@h/", "=h", "/h"
        pat = re.compile(r"(^|['\"@/=\s])" + re.escape(h_low) + r"(\b|['\"/\s])")
        for line in code_hits:
            if pat.search(line):
                return True
    return False


def _any_match(deps: set[str], hints: list[str]) -> bool:
    import re
    for d in deps:
        d_low = d.lower().replace('_', '-').replace('.', '-')
        for h in hints:
            h_low = h.lower().replace('_', '-').replace('.', '-')
            if not h_low:
                continue
            # For dependency names, compare against cleaned name (stop at version specifier)
            name = re.split(r"[<>=!~;\[\(\s]", d_low, 1)[0]
            if name == h_low or name.startswith(h_low + '-') or name.endswith('-' + h_low):
                return True
    return False


def _file_marker(scan: ScanResult, hints: list[str]) -> bool:
    # Cheap lookups: check if any hint appears as a filename
    for f in scan.files[:600]:
        name = f.name.lower()
        for h in hints:
            if h.lower() in name:
                return True
    return False


def _dedup(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
