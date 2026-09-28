"""Generate the implementation prompt for a selected opportunity.

The output is a self-contained prompt that an AI coding agent can use
to implement the JEV integration without having to reread the full analysis.

It MUST be grounded in the REAL files found in the target repository.
It MUST NOT invent filenames that don't exist.
"""
from __future__ import annotations

from typing import Any

from .models import AnalysisReport, JEVOpportunity
from .scanner import ScanResult


def build_prompt(report: AnalysisReport, opp_index: int, scan: ScanResult | None = None) -> str:
    if opp_index < 0 or opp_index >= len(report.opportunities):
        return "# Erro\n\nOportunidade não encontrada."
    opp = report.opportunities[opp_index]

    # Resolve real existing files that seem related; only list files that exist in the scan
    real_files: list[str] = []
    if scan is not None:
        existing_rel = {scan.rel(f) for f in scan.files}
        for candidate in opp.affected_files:
            if candidate in existing_rel:
                real_files.append(candidate)
    else:
        real_files = list(opp.affected_files)

    lines: list[str] = []
    lines.append(f"# Implementação — {opp.use_case}")
    lines.append("")
    lines.append(f"**Projeto:** {report.project_name}")
    lines.append(f"**Recomendação:** {opp.recommendation} | **Score de utilidade:** {opp.utility_score}/10")
    lines.append("")

    # 1. Objetivo
    lines.append("## 1. Objetivo")
    lines.append("")
    lines.append(opp.benefit)
    lines.append("")
    lines.append(f"**Onde JEV entra no fluxo:** {opp.entry_point}")
    lines.append("")

    # 2. Contexto arquitetural
    lines.append("## 2. Contexto arquitetural do projeto")
    lines.append("")
    lines.append(report.architecture_summary)
    lines.append("")
    if report.stack.frameworks:
        lines.append(f"- Frameworks: {', '.join(report.stack.frameworks)}")
    if report.stack.databases:
        lines.append(f"- Bancos/caches: {', '.join(report.stack.databases)}")
    if report.stack.languages:
        lines.append(f"- Linguagens: {', '.join(report.stack.languages[:5])}")
    if report.stack.services:
        lines.append(f"- Serviços/integrações detectados: {', '.join(report.stack.services[:8])}")
    lines.append("")

    # 3. Fluxo atual
    lines.append("## 3. Fluxo atual (evidências encontradas)")
    lines.append("")
    if opp.flow_evidence:
        for ev in opp.flow_evidence[:8]:
            lines.append(f"- `{ev}`")
    else:
        lines.append("- (Nenhuma evidência de arquivo específico foi localizada — confirme o fluxo antes de implementar.)")
    lines.append("")
    lines.append(f"**Solução atual/alternativa sem JEV:** {opp.current_solution}")
    lines.append("")

    # 4. Fluxo proposto
    lines.append("## 4. Fluxo proposto com JEV")
    lines.append("")
    lines.append(f"1. **Entrada chega** no ponto: {opp.entry_point}")
    lines.append("2. **Normalização** da entrada (limpeza de texto, extração de metadados já existentes).")
    lines.append("3. **Chamada ao JEV** com um schema de saída tipado (JSON).")
    lines.append("4. **Validação determinística** da resposta (campos obrigatórios, tipos, ranges, listas de permissão).")
    lines.append("5. **Fallback** se JEV falhar / devolver resposta inválida / exceder timeout.")
    lines.append("6. **Execução da ação de negócio** com a decisão já validada.")
    lines.append("7. **Logs e métricas** de acurácia, latência e fallback.")
    lines.append("")

    # 5. Arquivos afetados
    lines.append("## 5. Arquivos existentes provavelmente afetados")
    lines.append("")
    if real_files:
        for f in real_files[:15]:
            lines.append(f"- `{f}`")
    else:
        lines.append("- (Nenhum arquivo específico foi identificado com confiança — investigue o ponto de entrada do fluxo antes de editar.)")
    lines.append("")
    lines.append("**IMPORTANTE:** Não altere o comportamento de negócio além do necessário para introduzir JEV no ponto descrito. Preserve compatibilidade com o fluxo atual e mantenha o código antigo como fallback.")
    lines.append("")

    # 6. Novos arquivos sugeridos
    lines.append("## 6. Novos arquivos sugeridos (nomes genéricos; ajuste à estrutura real)")
    lines.append("")
    lines.append("Escolha nomes e pastas compatíveis com o padrão existente no projeto. Exemplos:")
    lines.append("")
    lines.append(f"- Um módulo cliente para JEV (ex.: `jev_client.py` ou `src/lib/jev.ts`).")
    lines.append(f"- Um módulo com o schema de entrada/saída tipado (ex.: `schemas/{_slug(opp.category)}_schema.py` ou `src/schemas/{_slug(opp.category)}.ts`).")
    lines.append(f"- Um serviço que encapsula a decisão de negócio (ex.: `services/{_slug(opp.category)}_service.py` ou `src/services/{_slug(opp.category)}.ts`).")
    lines.append(f"- Testes unitários e de integração cobrindo os caminhos de sucesso, fallback e respostas inválidas.")
    lines.append("")

    # 7. Interfaces / APIs
    lines.append("## 7. APIs / Interfaces")
    lines.append("")
    lines.append("Implemente o cliente JEV com uma interface inspirada no código abaixo (ajuste a linguagem):")
    lines.append("")
    lines.append("```ts")
    lines.append(f"interface JEV{_class_name(opp.category)}Input {{")
    lines.append("  // Dados relevantes do evento/request (normalizados)")
    lines.append("  text?: string;")
    lines.append("  userId?: string;")
    lines.append("  metadata?: Record<string, unknown>;")
    lines.append("}")
    lines.append("")
    lines.append(f"interface JEV{_class_name(opp.category)}Output {{")
    lines.append("  decision: string;       // ex.: ROUTED_TO_SUPPORT | EXTRACTED | MODERATION_FLAG")
    lines.append("  confidence: number;     // 0..1")
    lines.append("  reason?: string;        // explicação curta para logs/auditoria")
    lines.append("  entities?: Record<string, unknown>; // quando aplicável")
    lines.append("}")
    lines.append("")
    lines.append(f"interface JEVClient {{")
    lines.append(f"  classify{_class_name(opp.category)}(input: JEV{_class_name(opp.category)}Input, opts?: {{ timeoutMs?: number }}): Promise<JEV{_class_name(opp.category)}Output>;")
    lines.append("}")
    lines.append("```")
    lines.append("")

    # 8. Tipos e contratos
    lines.append("## 8. Tipos e contratos de dados")
    lines.append("")
    lines.append("- Defina um schema de saída FECHADO para o JEV (campos, tipos, enums quando aplicável).")
    lines.append("- Valide TODA resposta contra o schema antes de usar (ex.: Pydantic/Zod).")
    lines.append("- Trate campos livres como não confiáveis; nunca concatene o texto devolvido pelo JEV direto em queries SQL, HTML não-escapado, ou chamadas de pagamento.")
    lines.append("")

    # 9. Erros e fallback
    lines.append("## 9. Tratamento de erros e fallback")
    lines.append("")
    lines.append("- Timeout configurável (sugestão: 300-500ms para caminho síncrono; mais para assíncrono).")
    lines.append("- Se JEV falhar (timeout, erro HTTP, resposta inválida), **cair para a solução anterior** (regras, humano, ou não-ação), sem quebrar o fluxo do usuário.")
    lines.append("- Nunca deixe o JEV ser ponto único de falha de um fluxo crítico.")
    lines.append("- Garanta rate-limit e retry com backoff apenas em erros transitórios.")
    lines.append("")

    # 10. Segurança
    lines.append("## 10. Segurança")
    lines.append("")
    lines.append("- NÃO envie segredos, tokens, chaves de API ou senhas ao JEV.")
    lines.append("- Reduza PII ao mínimo necessário (idealmente nenhuma). Se precisar, opere em conformidade com LGPD/GDPR.")
    lines.append("- Nunca use a decisão do JEV como fonte da verdade para valores monetários, autenticação, autorização, ou emissão de documentos legais.")
    lines.append("- Saída do JEV deve ser tratada como dado não confiável (validar, escapar, escapar novamente se for renderizar).")
    lines.append("- Chamadas devem autenticar-se com credenciais vindas de variáveis de ambiente, NUNCA hardcoded.")
    lines.append("")

    # 11. Observabilidade / logs
    lines.append("## 11. Observabilidade e logs")
    lines.append("")
    lines.append("- Logue cada decisão JEV com: id de correlação, intenção/categoria retornada, confiança, latência em ms, se caiu em fallback, e motivo do fallback.")
    lines.append("- NÃO logue conteúdo sensível em texto puro.")
    lines.append("- Registre métricas: contador de requisições, taxa de fallback, distribuição de latência, distribuição de decisões por classe.")
    lines.append("- Exponha um dashboard mínimo (Grafana/DataDog/Sentry) ou, no mínimo, logs estruturados.")
    lines.append("")

    # 12. Métricas de sucesso
    lines.append("## 12. Métricas de sucesso")
    lines.append("")
    lines.append("- Taxa de acurácia (amostra auditada) — alvo inicial ≥ 85%.")
    lines.append("- Taxa de fallback < 2% em produção estabilizada.")
    lines.append("- Latência p95 abaixo do threshold definido.")
    lines.append("- Impacto de negócio: _defina um indicador mensurável antes do deploy_ (ex.: redução de x% no tempo de roteamento, y% de taxa de resposta automática).")
    lines.append("")

    # 13. Testes
    lines.append("## 13. Testes")
    lines.append("")
    lines.append("- Testes unitários para o cliente JEV (usando mocks do transporte HTTP).")
    lines.append("- Testes de fallback: erro de rede, timeout, resposta inválida, confiança baixa.")
    lines.append("- Testes do schema: respostas fora do formato são rejeitadas.")
    lines.append("- Testes de integração com um pequeno conjunto de exemplos reais (golden set).")
    lines.append("- Testes de regressão para garantir que o fluxo antigo continua funcionando quando JEV está desabilitado por flag.")
    lines.append("")

    # 14. Critérios de aceite
    lines.append("## 14. Critérios objetivos de aceite")
    lines.append("")
    lines.append(f"- [ ] JEV é chamado apenas no ponto: {opp.entry_point}")
    lines.append("- [ ] Existe uma feature flag para desligar JEV sem redeploy de código.")
    lines.append("- [ ] O fallback cobre: timeout, erro 5xx, resposta inválida, baixa confiança.")
    lines.append("- [ ] Toda resposta é validada por schema tipado.")
    lines.append("- [ ] Nenhum segredo/PII desnecessária é enviado.")
    lines.append("- [ ] Logs estruturados e métricas implementados.")
    lines.append("- [ ] O comportamento existente é preservado quando JEV está desabilitado.")
    lines.append("- [ ] Testes cobrem caminho feliz e de falha.")
    lines.append("- [ ] Decisões monetárias/de autorização/de validação determinística permanecem fora de JEV.")
    lines.append("")

    # 15. Riscos / limitações
    lines.append("## 15. Riscos e limitações conhecidos")
    lines.append("")
    for r in opp.risks:
        lines.append(f"- {r}")
    lines.append("")
    if opp.cons:
        lines.append("**Contra-indicações / pontos de atenção:**")
        lines.append("")
        for c in opp.cons:
            lines.append(f"- {c}")
        lines.append("")

    # 16. Escala e gatilhos
    lines.append("## 16. Quando esta implementação se justifica")
    lines.append("")
    lines.append(opp.trigger_scale)
    lines.append("")

    # 17. Soluções alternativas consideradas
    lines.append("## 17. Alternativas consideradas (comparação)")
    lines.append("")
    if opp.comparison:
        lines.append("| Solução | Custo | Latência | Previsibilidade | Quando usar |")
        lines.append("|---|---|---|---|---|")
        for name, m in opp.comparison.items():
            lines.append(f"| {name} | {m.get('custo','-')} | {m.get('latência','-')} | {m.get('previsibilidade','-')} | {m.get('quando_usar','-')} |")
        lines.append("")

    # 18. Instruções gerais
    lines.append("## 18. Instruções gerais para o agente que implementar")
    lines.append("")
    lines.append("- **Preserve o comportamento existente.** Não remova a lógica atual; ela vira fallback.")
    lines.append("- Faça o menor PR possível: cliente JEV + schema + integração no ponto do fluxo + testes + flag.")
    lines.append("- Não mova ou renomeie arquivos existentes a menos que seja estritamente necessário.")
    lines.append("- Adicione documentação curta (comentários no ponto de integração) explicando POR QUE JEV foi colocado ali.")
    lines.append("- Não invente credenciais, chaves ou suposições sobre a API do JEV: use uma interface com variável de ambiente (ex.: `JEV_API_KEY`, `JEV_BASE_URL`) e deixe o cliente falhar claramente se não configurado.")
    lines.append("")

    return "\n".join(lines)


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s.lower())[:40].strip("_") or "generic"


def _class_name(s: str) -> str:
    parts = [p.capitalize() for p in _slug(s).split("_") if p]
    return "".join(parts) or "Generic"
