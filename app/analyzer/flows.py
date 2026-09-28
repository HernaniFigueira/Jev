"""Detect flows and decision points in a scanned project.

Heuristic, language-agnostic where possible.
All detection is read-only; results are used to evaluate JEV fit.
"""
from __future__ import annotations

import re
from typing import Any

from .models import FlowPoint, StackInfo
from .scanner import ScanResult, grep_pattern, read_content


# --- Signal definitions -----------------------------------------------------
# Each entry produces a FlowPoint category when matched.

def _code_lines(content: str) -> list[str]:
    """Return lines stripped of comments/docstrings to reduce false positives.
    Best-effort; works well enough for C-style and Python comments.
    """
    out: list[str] = []
    in_py_doc = False
    in_c_block = False
    for raw in content.splitlines():
        s = raw.strip()
        if not s:
            continue
        # Python docstrings
        if s.startswith('"""') or s.startswith("'''"):
            in_py_doc = not in_py_doc
            if s.count('"""') == 2 or s.count("'''") == 2:
                in_py_doc = not in_py_doc
            continue
        if in_py_doc:
            continue
        # C/JS/Java/etc block comments
        if s.startswith("/*"):
            in_c_block = True
        if in_c_block:
            if "*/" in s:
                in_c_block = False
            continue
        # Line comments
        if s.startswith("#") or s.startswith("//"):
            continue
        # .rst/.md references are noisy — skip
        out.append(s)
    return out


SIGNAL_GROUPS: list[dict[str, Any]] = [
    {
        "category": "webhook/entry",
        "name": "Webhook receptor",
        "description": "Endpoint que recebe eventos de serviços externos (WhatsApp, Stripe, GitHub, Slack, Telegram, etc.).",
        "patterns": [
            r"webhook",
            r"@app\.post\([\"']/webhook",
            r"/api/webhook",
            r"stripe\.webhook",
            r"twilio.*webhook",
            r"whatsapp.*webhook",
            r"github.*webhook",
            r"x-hub-signature",
            r"clerk.*webhook",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 1.0,
    },
    {
        "category": "http/api",
        "name": "API endpoint",
        "description": "Rotas HTTP que recebem requests de clientes, frontend ou outros serviços.",
        "patterns": [
            r"@app\.(get|post|put|patch|delete)\(",
            r"@router\.(get|post|put|patch|delete)\(",
            r"app\.(get|post|put|patch|delete)\(",
            r"router\.(get|post|put|patch|delete)\(",
            r"@Get\(|@Post\(|@Put\(|@Delete\(|@Patch\(",
            r"@RequestMapping",
            r"FastAPI\(|APIRouter\(",
            r"express\(",
            r"new Router\(",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php"},
        "weight": 0.3,  # very common; only as supporting evidence
    },
    {
        "category": "messaging/chat",
        "name": "Mensageria / chat",
        "description": "Código que envia/recebe mensagens (WhatsApp, Telegram, chat interno).",
        "patterns": [
            r"whatsapp",
            r"telegram",
            r"send_message",
            r"reply_message",
            r"chatbot",
            r"conversation",
            r"message\.text",
            r"incoming.?message",
            r"wppconnect",
            r"baileys",
            r"twilio",
            r"message\.body",
            r"webhook.*message",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.9,
    },
    {
        "category": "payment",
        "name": "Fluxo de pagamento",
        "description": "Código relacionado a cobrança, checkout, webhooks de pagamento, assinaturas.",
        "patterns": [
            r"stripe",
            r"mercadopago",
            r"paypal",
            r"pagamento|payment",
            r"checkout",
            r"invoice",
            r"subscription",
            r"payment_intent",
            r"charge\b",
            r"webhook.*checkout",
            r"webhook.*payment",
            r"customer\.payment",
            r"boleto|pix",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php", ".sql"},
        "weight": 0.9,
    },
    {
        "category": "auth",
        "name": "Autenticação/autorização",
        "description": "Login, JWT, sessões, RBAC, OAuth, MFA.",
        "patterns": [
            r"jwt",
            r"oauth",
            r"@login_required",
            r"authenticate",
            r"authorization",
            r"Bearer",
            r"auth0|clerk|nextauth|next-auth",
            r"bcrypt|argon2",
            r"login|signin|signup|register",
            r"permission|role|scope",
            r"refresh.?token",
            r"passport",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.7,
    },
    {
        "category": "queue/event",
        "name": "Filas / eventos",
        "description": "Processamento assíncrono via Celery, BullMQ, RabbitMQ, Kafka, SQS, Redis streams.",
        "patterns": [
            r"celery",
            r"@shared_task|@app\.task",
            r"delay\(|apply_async\(",
            r"bullmq|bull\b",
            r"addJob|add_job",
            r"rabbitmq|amqp",
            r"kafka",
            r"\bsqs\b|send_message",
            r"pubsub|pub_sub",
            r"eventEmitter|\.emit\(",
            r"redis.*queue|rq\b",
            r"worker|consumer",
            r"event bus|eventbus",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.9,
    },
    {
        "category": "database",
        "name": "Acesso a banco",
        "description": "Queries, ORMs, migrations.",
        "patterns": [
            r"SELECT|INSERT|UPDATE|DELETE|CREATE TABLE",
            r"prisma|\.findMany|\.findUnique|\.create\(|\.update\(",
            r"session\.query|session\.execute",
            r"sqlalchemy|declarative_base",
            r"cursor\.execute|\.raw\(|knex|sequelize|typeorm",
            r"mongodb|mongoose\.|mongo\.",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".sql", ".prisma", ".go", ".java", ".rb", ".php"},
        "weight": 0.3,
    },
    {
        "category": "classification/routing",
        "name": "Roteamento/classificação manual",
        "description": "Código com muitos if/else ou switch tentando classificar entrada (mensagens, tickets, categorias).",
        "patterns": [
            r"classify|classificação|categor",
            r"intent",
            r"if .*(contains|match|includes)",
            r"switch .*message|switch .*type",
            r"route.*to|enviar para|redirect.*depart",
            r"menu.*opção|opcao",
            r"keywords|palavras?-chave",
            r"setor|department",
            r"ticket.*categor|categor.*ticket",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.85,
    },
    {
        "category": "fraud/risk",
        "name": "Fraude / risco",
        "description": "Detecção de fraude, chargeback, score de risco, anti-spam.",
        "patterns": [
            r"fraud|fraude",
            r"chargeback",
            r"risk.?score|score.*risco",
            r"anti.?spam|antispam",
            r"blacklist|blocklist",
            r"suspicious|suspeit",
            r"banimento|ban\b",
            r"abuse",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php", ".sql"},
        "weight": 0.85,
    },
    {
        "category": "moderation",
        "name": "Moderação de conteúdo",
        "description": "Moderação de texto, imagens, reviews, comentários.",
        "patterns": [
            r"moderat|moderaç",
            r"content.?policy|política de conteúdo",
            r"offensive|ofensiv|palavr",
            r"profan|toxic",
            r"flagged|denunci",
            r"report.*abuse|abuse.*report",
            r"spam.*detect",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.8,
    },
    {
        "category": "chatbot/response_generation",
        "name": "Chatbot / geração de resposta",
        "description": "Geração automática de respostas, FAQ, assistente virtual.",
        "patterns": [
            r"chatbot|chat.?bot|bot.?reply|auto.?reply",
            r"generate.?response|gerar.?resposta",
            r"openai|anthropic|gemini",
            r"completion|chat\.completion",
            r"llm|gpt-|claude",
            r"rag|retrieval.?augmented",
            r"embedding",
            r"assistant|assistente",
            r"faq|perguntas frequentes",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.9,
    },
    {
        "category": "support/ticket",
        "name": "Suporte / tickets",
        "description": "Sistema de atendimento, SLA, tickets, helpdesk.",
        "patterns": [
            r"ticket|helpdesk|help.?desk",
            r"support.?team|equipe.?suporte",
            r"atendente|atendimento",
            r"sla",
            r"zendesk|intercom|freshdesk",
            r"open.*ticket|criar.*chamado",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.75,
    },
    {
        "category": "automation",
        "name": "Automações",
        "description": "Automação de tarefas repetitivas (agendadas ou disparadas por eventos).",
        "patterns": [
            r"cron|schedule|agendad",
            r"automation|automação|automati[sz]e",
            r"@every|beat_schedule",
            r"setInterval\(",
            r"webhook.*trigger",
            r"zapier|n8n|make\.com",
            r"ifttt",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.7,
    },
    {
        "category": "external_integration",
        "name": "Integração externa frágil",
        "description": "Integrações que dependem de dados não estruturados de terceiros (PDF, email, scraping).",
        "patterns": [
            r"scraping|beautifulsoup|cheerio|puppeteer|playwright|selenium",
            r"pdf.?extract|pdfplumber|pypdf|pdf-parse",
            r"imap|smtp|receb.*email",
            r"parse.*email|inbound.?email",
            r"unstructured|não estruturado",
            r"ocr|tesseract",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.75,
    },
    {
        "category": "search/semantic",
        "name": "Busca semântica",
        "description": "Código de busca textual, relevância, recomendação.",
        "patterns": [
            r"full.?text.?search|fts",
            r"elastic|elasticsearch|opensearch",
            r"embedding|vector",
            r"semantic|semântica",
            r"recommend|recomendação",
            r"relevant|relevân",
            r"similarity|similaridade",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.8,
    },
    {
        "category": "onboarding/form",
        "name": "Formulários/onboarding longo",
        "description": "Formulários, cadastros extensos, triagem de entrada.",
        "patterns": [
            r"onboarding|integração|cadastro.*inicial",
            r"form\.|formData|zod|yup|joi|react-hook-form",
            r"validation.*message|validação.*campo",
            r"free.?text|campo.?livre|observações|observacoes",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.4,  # weak signal alone
    },
    {
        "category": "notifications",
        "name": "Notificações",
        "description": "Envio de email, push, SMS. Geralmente baixo valor para JEV.",
        "patterns": [
            r"sendMail|send_email|sendgrid|resend|nodemailer",
            r"notify|notificação|push.?notification",
            r"sms.*send|twilio.*message|send.*sms",
            r"firebase.*messag|fcm",
        ],
        "exts": {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"},
        "weight": 0.3,
    },
]


def _grep_code(scan: ScanResult, pattern: str, exts: set[str] | None = None,
               max_files: int = 80) -> list[tuple[Path, list[str]]]:
    """Like grep_pattern but filters out comments/docstrings before matching."""
    rx = re.compile(pattern, re.IGNORECASE)
    hits: list[tuple[Path, list[str]]] = []
    skip_seg = {"docs", "doc", "test", "tests", "examples", "example", "samples", "sample", "changelog"}
    for fpath in scan.files:
        parts = set(p.lower() for p in fpath.parts)
        if parts & skip_seg:
            continue
        if exts and fpath.suffix.lower() not in exts:
            continue
        content = read_content(scan, fpath)
        if not content:
            continue
        matching = []
        for ln in _code_lines(content):
            if rx.search(ln):
                matching.append(ln.strip()[:200])
        if matching:
            hits.append((fpath, matching))
            if len(hits) >= max_files:
                break
    return hits


def detect_flows(scan: ScanResult, stack: StackInfo) -> list[FlowPoint]:
    flows: list[FlowPoint] = []

    for sig in SIGNAL_GROUPS:
        hit_files: dict[str, list[str]] = {}
        total_hits = 0
        combined = "|".join(f"(?:{p})" for p in sig["patterns"])
        try:
            hits = _grep_code(scan, combined, exts=sig.get("exts"), max_files=80)
        except re.error:
            continue
        for fpath, lines in hits:
            rel = scan.rel(fpath)
            if ".env" in fpath.name:
                continue
            hit_files[rel] = lines[:3]
            total_hits += len(lines)

        if total_hits == 0:
            continue

        # Score confidence by hit density
        file_hits = len(hit_files)
        confidence = min(1.0, 0.25 + 0.15 * min(file_hits, 5) + sig["weight"] * 0.3)
        evidence = []
        for rel, lines in list(hit_files.items())[:5]:
            evidence.append(f"{rel}: {lines[0] if lines else ''}")

        flows.append(FlowPoint(
            name=sig["name"],
            category=sig["category"],
            description=sig["description"],
            evidence=evidence,
            confidence=round(confidence, 2),
            files=list(hit_files.keys())[:10],
            metadata={"hit_files": file_hits, "total_hits": total_hits},
        ))

    return flows


def detect_non_ai_candidates(scan: ScanResult, flows: list[FlowPoint]) -> list[str]:
    """Detect things that should explicitly NOT use AI. Returns descriptions."""
    not_use: list[str] = []

    # CPF/CNPJ/Boleto validation
    cpf_hits = grep_pattern(scan, r"cpf|cnpj|valida.*documento", exts={".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php"}, max_files=10)
    if cpf_hits:
        not_use.append("Validação de CPF/CNPJ/documentos identificadores é regra determinística.")

    # Authentication (password hashing etc.)
    for f in flows:
        if f.category == "auth":
            not_use.append("Autenticação/autorização (hash de senha, JWT, RBAC) deve usar bibliotecas consolidadas, não IA.")
            break

    # Payments - monetary stuff
    for f in flows:
        if f.category == "payment":
            not_use.append("Decisões monetárias críticas (cobrar, reembolsar, calcular valor) não devem usar IA generativa como fonte da verdade.")
            break

    return not_use
