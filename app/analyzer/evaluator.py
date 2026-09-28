"""Evaluate JEV opportunities based on detected flows.

Honest, ROI-oriented scoring. High scores are reserved for flows where
JEV (or, more generally, a probabilistic decision engine) materially
outperforms rules, SQL, conventional LLMs, or no AI.

For this MVP, JEV is treated as a fast, cheap, deterministic-in-expectation
decision layer suitable for:
  - classification/routing at scale
  - intent detection
  - structured extraction from noisy free-text
  - moderation / fraud signals (as one signal, not sole judge)
  - short-answer generation in narrow domains
It is NOT suitable for:
  - monetary / legal source-of-truth decisions
  - anything that requires 100% determinism or auditability
  - pure deterministic transformations (parse CPF, validate email)
  - long-form open generation (conventional LLM is better)
  - arithmetic, SQL, business math
"""
from __future__ import annotations

from typing import Any

from .models import FlowPoint, JEVOpportunity, StackInfo, AnalysisReport
from .scanner import ScanResult as _SR
from .flows import detect_flows, detect_non_ai_candidates


def evaluate(scan: _SR, stack: StackInfo, flows: list[FlowPoint]) -> list[JEVOpportunity]:
    opps: list[JEVOpportunity] = []
    non_ai_notes = detect_non_ai_candidates(scan, flows)

    # Group flow points by category for easier evaluation
    by_cat: dict[str, FlowPoint] = {f.category: f for f in flows}

    # ---- 1) Roteamento / classificação de mensagens ----
    if "messaging/chat" in by_cat or "classification/routing" in by_cat:
        chat = by_cat.get("messaging/chat")
        route = by_cat.get("classification/routing")
        files = []
        evidence = []
        for f in (chat, route):
            if f:
                files += f.files
                evidence += f.evidence
        files = _uniq(files)[:10]
        score = _score(
            impact=9.0, freq=8.5, cost=7.0, conf_needed=6.0, ease=7.5,
            risk=2.5, complexity=3.0,
        )
        opps.append(JEVOpportunity(
            use_case="Roteamento inteligente de mensagens / intenção",
            entry_point="No receptor de mensagens (webhook do WhatsApp/Telegram/chat), após validação da entrada, antes do roteamento para setor/ação. Uma camada JEV classifica a intenção e metadados (setor, urgência, entidade) e o sistema executa a ação com base na decisão.",
            utility_score=score,
            benefit="Reduz drásticamente if/else de keywords; melhora taxa de acerto no roteamento; permite treinar novas intenções sem redeploy.",
            pros=[
                "Alto volume = ganho imediato",
                "Decisão tipicamente curta e de baixa latência — perfil ideal para JEV",
                "Pode operar como classificador rápido e barato antes de um LLM genérico",
                "Facilidade de rollback (basta cair para regras)",
            ],
            cons=[
                "Se o volume é < 500 msgs/dia, regras simples podem bastar",
                "Exige dados rotulados para calibrar",
                "Necessita observabilidade para medir taxa de acerto",
            ],
            implementation_complexity="Baixa",
            cost_impact="Custo marginal por decisão muito baixo; economia com classificação manual e com chamadas desnecessárias a LLMs mais caros. Em volume alto, ROI positivo.",
            risks=[
                "Roteamento incorreto gera frustração do cliente",
                "Dependência de latência do JEV no caminho síncrono",
                "Classificações novas sem calibração podem vazar para produção",
            ],
            recommendation=_rec(score, has_volume_signal=True),
            trigger_scale="Recomendado AGORA a partir de ~1.000 mensagens/mês ou quando houver mais de 4 setores/intenções diferentes; abaixo disso, regras simples são suficientes.",
            current_solution="Provavelmente if/else com palavras-chave ou nenhum roteamento automático.",
            category="routing",
            flow_evidence=evidence[:5],
            affected_files=files,
            comparison={
                "Regra tradicional": {"custo": "Baixo", "latência": "Muito baixa", "previsibilidade": "Alta", "quando_usar": "< 4 intenções e baixo volume"},
                "JEV": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "Muitas intenções, volume alto"},
                "LLM convencional": {"custo": "Alto", "latência": "Média/Alta", "previsibilidade": "Média/Baixa", "quando_usar": "Intenções abertas e raras"},
                "Embeddings": {"custo": "Médio", "latência": "Média", "previsibilidade": "Média", "quando_usar": "Quando intenções são textos longos ou variáveis"},
                "Não fazer nada": {"custo": "Zero", "latência": "Zero", "previsibilidade": "—", "quando_usar": "Atendimento humano suficiente"},
            },
            score_breakdown=_breakdown(impact=9.0, freq=8.5, cost=7.0, conf_needed=6.0, ease=7.5, risk=2.5, complexity=3.0),
        ))

    # ---- 2) Extração de dados estruturados de mensagens (agendamento, no-show, etc.) ----
    if "messaging/chat" in by_cat or "support/ticket" in by_cat or "onboarding/form" in by_cat:
        chat = by_cat.get("messaging/chat")
        support = by_cat.get("support/ticket")
        form = by_cat.get("onboarding/form")
        files = []
        evidence = []
        for f in (chat, support, form):
            if f:
                files += f.files
                evidence += f.evidence
        files = _uniq(files)[:10]
        score = _score(
            impact=7.5, freq=7.0, cost=5.5, conf_needed=7.0, ease=6.5,
            risk=3.5, complexity=4.0,
        )
        opps.append(JEVOpportunity(
            use_case="Extração de entidades (data, horário, nome, serviço, documento) de texto livre",
            entry_point="Quando o usuário envia dados em formato livre (ex.: 'quero agendar amanhã às 14h com a Dra. Juliana'). Após receber a mensagem, antes da lógica de negócio, JEV extrai entidades tipadas que a aplicação valida e persiste.",
            utility_score=score,
            benefit="Elimina parsing frágil baseado em regex; reduz idas e voltas do usuário pedindo dados em formato específico.",
            pros=[
                "Boa tolerância a variações de escrita (erros, abreviações)",
                "Pode devolver JSON tipado diretamente",
                "Falha fácil de detectar e confirmar com o usuário",
            ],
            cons=[
                "Datas/horas são sensíveis — sempre validar contra o domínio (ex.: horário comercial, conflitos)",
                "Requer schema bem definido do que extrair",
                "Hallucinations em dados de documento (CPF) exigem fallback validador",
            ],
            implementation_complexity="Média",
            cost_impact="Baixo custo por chamada; reduz tempo de atendimento humano em fluxos de agendamento/cadastro.",
            risks=[
                "Extrair horário/data errado gera no-show e insatisfação",
                "Não deve ser usado como fonte única de CPF/documentos (validar deterministicamente)",
                "Latência pode impactar chat síncrono",
            ],
            recommendation=_rec(score),
            trigger_scale="AGORA quando há ≥ 50 agendamentos/dia ou atendimento humano fazendo coleta de dados. DEPOIS caso o fluxo já use formulários estruturados.",
            current_solution="Regex / perguntas sequenciais / formulário rígido / extração manual.",
            category="extraction",
            flow_evidence=evidence[:5],
            affected_files=files,
            comparison={
                "Regra tradicional (regex/forms)": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Alta", "quando_usar": "Dados de formato fixo"},
                "JEV": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "Texto livre, variabilidade alta"},
                "LLM convencional": {"custo": "Médio", "latência": "Média", "previsibilidade": "Média/Baixa", "quando_usar": "Entidades complexas ou texto muito longo"},
                "Embeddings": {"custo": "Médio", "latência": "Média", "previsibilidade": "Baixa", "quando_usar": "Raramente sozinho para extração"},
                "Não fazer nada": {"custo": "Zero", "latência": "Zero", "previsibilidade": "—", "quando_usar": "Volumes muito baixos"},
            },
            score_breakdown=_breakdown(impact=7.5, freq=7.0, cost=5.5, conf_needed=7.0, ease=6.5, risk=3.5, complexity=4.0),
        ))

    # ---- 3) Previsão de no-show / cancelamento ----
    if "messaging/chat" in by_cat or "automation" in by_cat or "support/ticket" in by_cat:
        # This is included as DEPOIS by default — needs real historical data
        chat = by_cat.get("messaging/chat")
        auto = by_cat.get("automation")
        files = []
        evidence = []
        for f in (chat, auto):
            if f:
                files += f.files
                evidence += f.evidence
        files = _uniq(files)[:10]
        score = _score(
            impact=6.0, freq=5.0, cost=4.0, conf_needed=8.0, ease=3.5,
            risk=5.5, complexity=6.5,
        )
        opps.append(JEVOpportunity(
            use_case="Previsão de no-show / desistência / risco de cancelamento",
            entry_point="Em jobs agendados (diário/hora em hora) ou no momento da confirmação do agendamento. JEV recebe dados estruturados do agendamento + histórico do cliente e devolve um score de risco de no-show; o sistema dispara lembrete, reagendamento ou ação humana conforme faixa.",
            utility_score=score,
            benefit="Antecipa e reduz faltas; permite priorizar confirmações de maior risco.",
            pros=[
                "ROI claro em operações com agenda (médicas, beleza, serviços)",
                "Pode começar como um classificador simples sem LLM",
            ],
            cons=[
                "PRECISA de dados históricos rotulados (mínimo centenas de exemplos)",
                "JEV não é um modelo de ML genérico — pode não ser a melhor ferramenta se você já tem dados estruturados (modelo tabular com scikit/XGBoost é mais barato e auditável)",
                "Falsos negativos geram custo; falsos positivos geram spam",
            ],
            implementation_complexity="Alta",
            cost_impact="Potencialmente alto: cada no-show evitado gera receita, mas exige dados e calibração contínua.",
            risks=[
                "Sem dados históricos, é adivinhação",
                "Risco de envio de lembretes em excesso (spam)",
                "Mudanças de padrão (feriados, sazonalidade) podem degradar o modelo",
            ],
            recommendation="DEPOIS",
            trigger_scale="Vale a pena quando o no-show atual é ≥ 10% E há histórico de ≥ 1.000 agendamentos rotulados. Antes disso, lembretes por regra (24h antes) são suficientes.",
            current_solution="Lembretes genéricos por regra ou nenhuma ação.",
            category="prediction",
            flow_evidence=evidence[:5],
            affected_files=files,
            comparison={
                "Regra tradicional (lembrete a todos)": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Alta", "quando_usar": "Pequeno volume"},
                "JEV": {"custo": "Médio", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "Quando dados são semiestruturados e contexto misto"},
                "Modelo tabular (XGBoost/LightGBM)": {"custo": "Baixo", "latência": "Muito baixa", "previsibilidade": "Alta", "quando_usar": "QUANDO HÁ DADOS ESTRUTURADOS — normalmente a melhor opção"},
                "LLM convencional": {"custo": "Alto", "latência": "Alta", "previsibilidade": "Baixa", "quando_usar": "Quando há texto livre relevante (ex.: mensagens) e poucos dados"},
                "Não fazer nada": {"custo": "Zero", "latência": "Zero", "previsibilidade": "—", "quando_usar": "Baixo volume ou no-show irrelevante"},
            },
            score_breakdown=_breakdown(impact=6.0, freq=5.0, cost=4.0, conf_needed=8.0, ease=3.5, risk=5.5, complexity=6.5),
        ))

    # ---- 4) Detecção de fraude / risco ----
    if "fraud/risk" in by_cat:
        fraud = by_cat["fraud/risk"]
        files = fraud.files[:10]
        score = _score(
            impact=7.0, freq=6.0, cost=6.0, conf_needed=9.0, ease=4.0,
            risk=7.5, complexity=6.0,
        )
        opps.append(JEVOpportunity(
            use_case="Sinal de fraude / chargeback / abuso como um dos scores",
            entry_point="Após a criação de um pedido/pagamento/conta, em fila assíncrona (não bloqueando o fluxo crítico). JEV recebe sinais estruturados + texto livre (ex.: mensagens do usuário, descrição) e devolve um score de suspeita; este score compõe um ensemble com regras determinísticas e modelos específicos.",
            utility_score=score,
            benefit="Adiciona um sinal probabilístico a um sistema que geralmente é só regra, identificando casos novos não previstos.",
            pros=[
                "Bom para detectar padrões novos (zero-day fraud)",
                "Fora do caminho síncrono crítico, não impacta latência",
                "Pode aproveitar sinais textuais que regras ignoram",
            ],
            cons=[
                "NUNCA deve ser o único juiz — precisa de ensemble",
                "Requer dados rotulados de fraude (tipicamente raros)",
                "Custo marginal relevante em volumes altos",
                "Auditoria é mais difícil que regras",
            ],
            implementation_complexity="Alta",
            cost_impact="Custo moderado; pode economizar muito em chargeback se bem calibrado, mas ROI demora.",
            risks=[
                "Falsos positivos bloqueiam clientes bons",
                "Falsos negativos deixam fraude passar",
                "Adversários adaptativos mudam padrões",
                "Compliance: pode ser necessário explicar decisões",
            ],
            recommendation="DEPOIS",
            trigger_scale="Quando o volume de transações é alto (>5k/mês) e chargeback já é um problema mensurável (>1%). Começar apenas como sinal assíncrono, nunca como bloqueador.",
            current_solution="Regras de fraude (blacklist, velocity, geolocalização) ou nenhuma.",
            category="fraud",
            flow_evidence=fraud.evidence[:5],
            affected_files=files,
            comparison={
                "Regra tradicional": {"custo": "Baixo", "latência": "Muito baixa", "previsibilidade": "Alta", "quando_usar": "Sempre — como primeira camada"},
                "JEV": {"custo": "Médio", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "Adicionar como sinal complementar, em assíncrono"},
                "Modelo dedicado de ML (XGBoost/RF)": {"custo": "Baixo", "latência": "Muito baixa", "previsibilidade": "Alta", "quando_usar": "Normalmente a melhor opção para fraude com dados estruturados"},
                "LLM convencional": {"custo": "Alto", "latência": "Alta", "previsibilidade": "Baixa", "quando_usar": "Apenas para análise de texto livre específico"},
                "Não fazer nada": {"custo": "Zero", "latência": "Zero", "previsibilidade": "—", "quando_usar": "Pequeno volume, sem histórico de fraude"},
            },
            score_breakdown=_breakdown(impact=7.0, freq=6.0, cost=6.0, conf_needed=9.0, ease=4.0, risk=7.5, complexity=6.0),
        ))

    # ---- 5) Moderação de conteúdo ----
    if "moderation" in by_cat:
        mod = by_cat["moderation"]
        files = mod.files[:10]
        score = _score(
            impact=7.5, freq=6.5, cost=6.0, conf_needed=7.5, ease=6.0,
            risk=5.0, complexity=4.0,
        )
        opps.append(JEVOpportunity(
            use_case="Moderação de conteúdo (texto/imagem) como sinal de toxicidade/spam",
            entry_point="Após envio de mensagem/comentário/conteúdo, antes de publicar ou em fila de triagem. JEV classifica o conteúdo em categorias (ok / spam / ofensivo / risco) e o sistema decide entre publicar, enviar para revisão humana ou bloquear.",
            utility_score=score,
            benefit="Reduz carga de moderação humana; detecta variantes que regras de palavras pegam mal.",
            pros=[
                "Alta tolerância a variantes e eufemismos",
                "Boa relação custo/benefício em volume",
            ],
            cons=[
                "Não pode ser o único juiz em banimentos automáticos",
                "Requer política de conteúdo bem definida",
                "Multilíngue se o projeto for internacional",
            ],
            implementation_complexity="Média",
            cost_impact="Custo por decisão baixo; economia significativa em moderação humana para volumes >5k itens/dia.",
            risks=[
                "Falsos positivos em ironia/sarcasmo",
                "Viés de moderação pode gerar problemas de imagem/regulatório",
                "Não é 100% — precisa de apelação humana",
            ],
            recommendation=_rec(score),
            trigger_scale="AGORA a partir de ~1k conteúdos gerados por usuários por dia com equipe de moderação; abaixo disso, moderação reativa é suficiente.",
            current_solution="Denúncias reativas, blocklist de palavras ou revisão humana total.",
            category="moderation",
            flow_evidence=mod.evidence[:5],
            affected_files=files,
            comparison={
                "Regra tradicional (blocklist)": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Alta", "quando_usar": "Sempre — primeira camada"},
                "JEV": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "Boa opção para moderação em escala"},
                "Serviço dedicado (OpenAI Moderation, Perspective API)": {"custo": "Médio", "latência": "Média", "previsibilidade": "Média", "quando_usar": "Se não quiser treinar/calibrar próprio"},
                "LLM convencional": {"custo": "Alto", "latência": "Alta", "previsibilidade": "Média", "quando_usar": "Casos borda enviados para revisão humana assistida"},
                "Somente humano": {"custo": "Alto", "latência": "Alta", "previsibilidade": "Alta", "quando_usar": "Baixo volume ou conteúdo sensível"},
            },
            score_breakdown=_breakdown(impact=7.5, freq=6.5, cost=6.0, conf_needed=7.5, ease=6.0, risk=5.0, complexity=4.0),
        ))

    # ---- 6) Suporte / FAQ / chatbot ----
    if "chatbot/response_generation" in by_cat or "support/ticket" in by_cat:
        bot = by_cat.get("chatbot/response_generation")
        sup = by_cat.get("support/ticket")
        files = []
        evidence = []
        for f in (bot, sup):
            if f:
                files += f.files
                evidence += f.evidence
        files = _uniq(files)[:10]
        # Split into two opps: short answer (JEV) vs long open answers (NOT JEV)
        # Short answers
        score_short = _score(
            impact=7.0, freq=8.0, cost=7.0, conf_needed=6.5, ease=7.0,
            risk=3.0, complexity=3.5,
        )
        opps.append(JEVOpportunity(
            use_case="Respostas curtas e padronizadas (saudações, confirmações, status, dúvidas frequentes)",
            entry_point="Na camada de resposta do chatbot, após classificação de intenção. JEV seleciona o template/resposta curta adequada a partir de um catálogo finito de intenções. Não gera texto livre longo.",
            utility_score=score_short,
            benefit="Escolha de resposta rápida e barata para dúvidas de escopo fechado. Substitui árvores de decisão grandes.",
            pros=[
                "Latência e custo baixos",
                "Respostas controladas (menor risco de hallucination)",
                "Permite medir taxa de sucesso por intenção",
            ],
            cons=[
                "Apenas para catálogo FECHADO de respostas",
                "Se o catálogo for pequeno, regras são mais simples",
            ],
            implementation_complexity="Baixa",
            cost_impact="Reduz drasticamente custo com LLM em intenções triviais e atendimento humano para FAQ.",
            risks=[
                "Responder tópico sensível com genérico pode piorar experiência",
                "É preciso manter o catálogo de respostas curado",
            ],
            recommendation=_rec(score_short),
            trigger_scale="AGORA quando o volume de atendimento é >2k msgs/mês e há um conjunto estável de intenções frequentes.",
            current_solution="Árvore de decisão/menu, atendimento humano, ou LLM para tudo (caro).",
            category="chatbot-short",
            flow_evidence=evidence[:5],
            affected_files=files,
            comparison={
                "Regra/árvore de menu": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Alta", "quando_usar": "Menos de 10 intenções"},
                "JEV": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "Bom para intenções fechadas em volume"},
                "LLM convencional": {"custo": "Médio/Alto", "latência": "Média", "previsibilidade": "Média/Baixa", "quando_usar": "Quando a resposta exige raciocínio"},
                "Embeddings/RAG": {"custo": "Médio", "latência": "Média", "previsibilidade": "Média", "quando_usar": "Base de conhecimento ampla"},
                "Atendimento humano": {"custo": "Alto", "latência": "Alta", "previsibilidade": "Alta", "quando_usar": "Casos complexos/emocionais"},
            },
            score_breakdown=_breakdown(impact=7.0, freq=8.0, cost=7.0, conf_needed=6.5, ease=7.0, risk=3.0, complexity=3.5),
        ))

        # Long open responses — NÃO USAR JEV; usar LLM ou RAG
        opps.append(JEVOpportunity(
            use_case="Geração de respostas longas / abertas (explicações, argumentos, resolução complexa)",
            entry_point="NÃO USE JEV para isso. Se for automatizar, usar LLM convencional com RAG sobre base de conhecimento, ou manter humano.",
            utility_score=2.0,
            benefit="JEV foi desenhado para decisões curtas e estruturadas; respostas longas e abertas exigem um LLM generativo com contexto, onde JEV entrega pouco valor.",
            pros=[
                "Forçar uso de JEV aqui gera rigidez e respostas pobres",
            ],
            cons=[
                "Se usado para respostas longas, a qualidade degrada muito",
                "Risco de respostas sintéticas que parecem certas mas são hallucinations",
            ],
            implementation_complexity="Média",
            cost_impact="JEV mais barato mas com resultado ruim; não vale a economia.",
            risks=[
                "Insatisfação do usuário por respostas genéricas",
                "Informação incorreta em domínios sensíveis",
            ],
            recommendation="NÃO USAR",
            trigger_scale="Nunca como motor principal de respostas longas. JEV pode ser útil para ROTEAR se deve ser LLM, humano ou FAQ, mas não para gerar o texto final.",
            current_solution="LLM com RAG / atendimento humano / respostas pré-escritas longas.",
            category="chatbot-long",
            flow_evidence=evidence[:3],
            affected_files=files,
            comparison={
                "JEV": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Baixa (qualidade)", "quando_usar": "Não recomendado"},
                "LLM + RAG": {"custo": "Médio", "latência": "Média", "previsibilidade": "Média", "quando_usar": "Melhor opção para automatizar respostas longas"},
                "Humano": {"custo": "Alto", "latência": "Alta", "previsibilidade": "Alta", "quando_usar": "Casos sensíveis/complexos"},
                "Templates estáticos": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Alta", "quando_usar": "Respostas 100% previsíveis"},
                "Embeddings + FAQ": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "FAQ ampla"},
            },
            score_breakdown=_breakdown(impact=2.0, freq=6.0, cost=2.0, conf_needed=8.0, ease=5.0, risk=7.0, complexity=5.0),
        ))

    # ---- 7) Pagamentos / transações ----
    if "payment" in by_cat:
        pay = by_cat["payment"]
        files = pay.files[:10]
        score = _score(
            impact=4.0, freq=5.0, cost=3.0, conf_needed=10.0, ease=3.0,
            risk=9.0, complexity=7.0,
        )
        opps.append(JEVOpportunity(
            use_case="Assistência em fluxo de pagamento (classificar falha de pagamento, sugerir meio de pagamento)",
            entry_point="APÓS a confirmação do pagamento (assíncrono), para análise de falhas / retry inteligente / sugestão de meio de pagamento. NUNCA no caminho de cobrança em si.",
            utility_score=score,
            benefit="Pode ajudar a classificar motivo de falha e sugerir retry/alternativa, reduzindo abandono.",
            pros=[
                "Fora do caminho transacional crítico, risco menor",
                "Pode reduzir abandono de checkout se bem calibrado",
            ],
            cons=[
                "Cálculo de valor, desconto, juros, validação de cartão NUNCA podem depender de IA",
                "Requer dados de muitos pagamentos",
                "Compliance (PCI, LGPD) limita quais dados podem ir para o JEV",
            ],
            implementation_complexity="Alta",
            cost_impact="Potencial médio de aumento de receita por redução de abandono; custo operacional baixo por chamada.",
            risks=[
                "Qualquer erro em decisão monetária é caro",
                "Hallucinations em valores são inaceitáveis",
                "Risco regulatório se dados sensíveis vazarem",
            ],
            recommendation="NÃO USAR" if score < 5 else "DEPOIS",
            trigger_scale="DEPOIS — apenas depois de regras determinísticas estabilizadas e com >10k transações/mês com falha mensurável.",
            current_solution="Provedor de pagamento (gateway), regras de retry, cupons manuais.",
            category="payment",
            flow_evidence=pay.evidence[:5],
            affected_files=files,
            comparison={
                "Regra tradicional": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Alta", "quando_usar": "Sempre para decisões monetárias"},
                "JEV": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "Análise assíncrona de falhas"},
                "Modelo de ML (churn/retry)": {"custo": "Médio", "latência": "Baixa", "previsibilidade": "Alta", "quando_usar": "Quando há dados tabulares suficientes"},
                "LLM convencional": {"custo": "Alto", "latência": "Alta", "previsibilidade": "Baixa", "quando_usar": "Não recomendado para pagamentos"},
                "Solução do gateway": {"custo": "Incluso", "latência": "—", "previsibilidade": "Alta", "quando_usar": "Sempre usar primeiro"},
            },
            score_breakdown=_breakdown(impact=4.0, freq=5.0, cost=3.0, conf_needed=10.0, ease=3.0, risk=9.0, complexity=7.0),
        ))

    # ---- 8) Automação de entrada / parsing de email/PDF ----
    if "external_integration" in by_cat:
        ext = by_cat["external_integration"]
        files = ext.files[:10]
        score = _score(
            impact=8.0, freq=6.5, cost=7.5, conf_needed=7.0, ease=6.0,
            risk=5.0, complexity=5.0,
        )
        opps.append(JEVOpportunity(
            use_case="Parsing de dados não-estruturados (email inbound, PDF, OCR, scraping sem DOM estável)",
            entry_point="Após receber o artefato bruto (email, PDF baixado, HTML de scraping) e antes de persistir no sistema. JEV extrai campos tipados de formato livre; a aplicação valida deterministicamente os campos críticos.",
            utility_score=score,
            benefit="Solução tradicional (regex/DOM scraping) quebra constantemente com pequenas mudanças; JEV lida melhor com variabilidade.",
            pros=[
                "Alta variabilidade de entrada é o cenário clássico onde IA ajuda",
                "Pode ser executado de forma assíncrona",
                "Permite tratar fornecedores que não fornecem API",
            ],
            cons=[
                "Campos críticos (valores monetários, documentos) DEVEM ser validados deterministicamente",
                "Requer testes com exemplos reais do fornecedor",
                "Mudanças de layout do fornecedor ainda podem quebrar",
            ],
            implementation_complexity="Média",
            cost_impact="Reduz trabalho manual de digitação; depende do volume de documentos recebidos.",
            risks=[
                "Campo extraído errado pode gerar pedidos/pagamentos incorretos",
                "Necessidade de trilha de auditoria (quando foi parseado, qual valor bruto)",
            ],
            recommendation=_rec(score),
            trigger_scale="AGORA quando há entrada manual repetitiva (≥ 50 documentos/emails por dia) que já é feita por humano por ausência de API.",
            current_solution="Digitação manual / regex frágil / scraping DOM quebradiço.",
            category="unstructured-parsing",
            flow_evidence=ext.evidence[:5],
            affected_files=files,
            comparison={
                "Regex/DOM scraping": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Alta SE formato estável", "quando_usar": "Quando o fornecedor tem API/HTML estável"},
                "JEV": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "Boa opção quando não há API e formato varia"},
                "LLM com visão (PDF/imagem)": {"custo": "Médio", "latência": "Média", "previsibilidade": "Média", "quando_usar": "PDFs com layout complexo, imagens, tabelas"},
                "Serviço dedicado (OCR/parser)": {"custo": "Médio", "latência": "Média", "previsibilidade": "Alta", "quando_usar": "Documentos padronizados (NF-e, boleto)"},
                "Humano": {"custo": "Alto", "latência": "Alta", "previsibilidade": "Alta", "quando_usar": "Baixo volume ou alta criticidade"},
            },
            score_breakdown=_breakdown(impact=8.0, freq=6.5, cost=7.5, conf_needed=7.0, ease=6.0, risk=5.0, complexity=5.0),
        ))

    # ---- 9) Validação de CPF/CNPJ / autenticação / cálculos — NÃO USAR ----
    # These are always hard NÃO USAR, but only present as opportunities if the code suggests them
    # We attach a generic "guard" opportunity whenever there's auth or payment
    if "auth" in by_cat:
        auth = by_cat["auth"]
        opps.append(JEVOpportunity(
            use_case="Autenticação, validação de senhas, verificação de CPF/CNPJ e cálculos determinísticos",
            entry_point="NENHUM — não use JEV ou IA para isso.",
            utility_score=0.5,
            benefit="Nenhum. Regras determinísticas e bibliotecas consolidadas são mais baratas, mais rápidas, auditáveis e corretas.",
            pros=["Bibliotecas padrão fazem isso com 100% de acurácia e zero alucinação."],
            cons=["Usar IA aqui adiciona custo, latência e risco sem nenhum benefício."],
            implementation_complexity="—",
            cost_impact="Aumento de custo sem qualquer retorno.",
            risks=[
                "Falhas de segurança (hash, token JWT mal validados)",
                "Dados sensíveis enviados desnecessariamente",
                "Decisões legais/regulatórias tomadas de forma não auditável",
            ],
            recommendation="NÃO USAR",
            trigger_scale="Nunca. Use bibliotecas consolidadas: passlib/bcrypt para senha, PyJWT/python-jose para JWT, bibliotecas de validação de documentos, cálculos exatos em decimal.",
            current_solution="Bibliotecas de auth/validação (a forma correta).",
            category="anti-pattern-deterministic",
            flow_evidence=auth.evidence[:3],
            affected_files=auth.files[:5],
            comparison={
                "Bibliotecas padrão": {"custo": "Zero", "latência": "Muito baixa", "previsibilidade": "100%", "quando_usar": "Sempre"},
                "JEV/IA": {"custo": "Positivo", "latência": "Maior", "previsibilidade": "Inaceitável", "quando_usar": "Nunca"},
            },
            score_breakdown=_breakdown(impact=0.5, freq=3.0, cost=0.0, conf_needed=10.0, ease=0.0, risk=10.0, complexity=2.0),
        ))

    # ---- 10) Busca semântica ----
    if "search/semantic" in by_cat:
        s = by_cat["search/semantic"]
        files = s.files[:10]
        score = _score(
            impact=6.0, freq=5.0, cost=5.0, conf_needed=6.0, ease=5.0,
            risk=4.0, complexity=5.0,
        )
        opps.append(JEVOpportunity(
            use_case="Busca/recomendação semântica em produtos, conteúdo ou base de conhecimento",
            entry_point="No endpoint de busca, após normalização do termo do usuário. JEV pode atuar como um re-ranker ou classificador de intenção de busca; a busca base pode continuar sendo FTS/Elasticsearch/Postgres ts_vector.",
            utility_score=score,
            benefit="Melhora relevância em buscas de linguagem natural ('quero um presente para minha mãe' em vez de 'camisa azul').",
            pros=[
                "Pode ser adicionado de forma incremental sobre a busca existente",
                "Bom ROI em catálogos/conteúdos grandes",
            ],
            cons=[
                "Primeiro vale investir em busca full-text boa (Postgres FTS, Elasticsearch)",
                "Embeddings + vector DB costumam ser a abordagem mais comum, não JEV",
                "Precisa de avaliação de relevância",
            ],
            implementation_complexity="Média",
            cost_impact="Custo por query baixo; impacto em conversão pode ser alto para e-commerce/conteúdo.",
            risks=[
                "Piorar resultados existentes se mal calibrado",
                "Latência adicional em busca síncrona",
            ],
            recommendation="DEPOIS",
            trigger_scale="DEPOIS de ter busca full-text bem ajustada. Quando buscas com zero resultados ou baixa conversão são mensuráveis (>10% das buscas retornam irrelevante), vale explorar.",
            current_solution="Busca LIKE/ILIKE, full-text search, ou nenhuma busca.",
            category="search",
            flow_evidence=s.evidence[:5],
            affected_files=files,
            comparison={
                "FTS (Postgres/Elasticsearch)": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Alta", "quando_usar": "Primeira opção, sempre"},
                "Embeddings + vector DB": {"custo": "Médio", "latência": "Média", "previsibilidade": "Média", "quando_usar": "Busca semântica clássica"},
                "JEV": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "Média", "quando_usar": "Re-rank e intenção de busca"},
                "LLM para query rewrite": {"custo": "Médio", "latência": "Média", "previsibilidade": "Média", "quando_usar": "Buscas complexas raras"},
                "Humano": {"custo": "Alto", "latência": "Alta", "previsibilidade": "Alta", "quando_usar": "Catálogo pequeno"},
            },
            score_breakdown=_breakdown(impact=6.0, freq=5.0, cost=5.0, conf_needed=6.0, ease=5.0, risk=4.0, complexity=5.0),
        ))

    # ---- 11) Notificações — NÃO USAR IA ----
    if "notifications" in by_cat:
        n = by_cat["notifications"]
        opps.append(JEVOpportunity(
            use_case="Envio de notificações transacionais (email/SMS/push)",
            entry_point="Não introduza JEV/IA para decidir o envio de notificações transacionais (confirmação de compra, reset de senha).",
            utility_score=1.0,
            benefit="Nenhum benefício tangível. Notificações transacionais devem ser 100% determinísticas.",
            pros=["Sistemas de template (MJML, React Email, etc.) são suficientes."],
            cons=["IA aqui introduz atraso e erro em comunicações que o usuário espera receber."],
            implementation_complexity="—",
            cost_impact="Custo extra sem retorno.",
            risks=[
                "Não enviar email de reset de senha por falha de IA é inaceitável",
                "Conteúdo gerado pode vazar dados ou conter alucinações",
            ],
            recommendation="NÃO USAR",
            trigger_scale="Nunca. Use templates determinísticos.",
            current_solution="Serviços de email/SMS com templates.",
            category="anti-pattern-notifications",
            flow_evidence=n.evidence[:3],
            affected_files=n.files[:5],
            comparison={
                "Templates determinísticos": {"custo": "Baixo", "latência": "Baixa", "previsibilidade": "100%", "quando_usar": "Sempre"},
                "JEV/IA": {"custo": "Positivo", "latência": "Maior", "previsibilidade": "Inaceitável", "quando_usar": "Nunca"},
            },
            score_breakdown=_breakdown(impact=1.0, freq=3.0, cost=0.0, conf_needed=10.0, ease=0.0, risk=10.0, complexity=2.0),
        ))

    return opps


# ---- helpers ----

def _score(impact: float, freq: float, cost: float, conf_needed: float,
           ease: float, risk: float, complexity: float) -> float:
    """Compose a 0-10 utility score.

    Formula (visible to users via score_breakdown):
      base = (impact*0.3 + freq*0.25 + cost*0.2 + ease*0.25) 
      penalty = (risk*0.4 + complexity*0.3 + conf_needed*0.2) * 0.5 / 10
      score = clamp(base - penalty*10 + 1? ...) — simplified below.
    """
    # Weights documented; output 0..10
    gain = (impact * 0.30) + (freq * 0.25) + (cost * 0.20) + (ease * 0.10)   # 0..8.5
    penalty = (risk * 0.35) + (complexity * 0.25) + (conf_needed * 0.10)       # 0..7
    # confidence needed: higher confidence requirement -> lower score for probabilistic solutions
    score = (gain * 1.1) - (penalty * 0.55)
    score = max(0.0, min(10.0, score))
    return round(score, 1)


def _breakdown(impact: float, freq: float, cost: float, conf_needed: float,
               ease: float, risk: float, complexity: float) -> dict[str, Any]:
    return {
        "formula": "score = (impacto*0.30 + frequência*0.25 + custo_atual*0.20 + facilidade*0.10)*1.1 - (risco*0.35 + complexidade*0.25 + confiança_exigida*0.10)*0.55",
        "criteria": {
            "impacto (0-10, ganho se der certo)": impact,
            "frequência do fluxo (0-10)": freq,
            "custo/dor atual (0-10)": cost,
            "facilidade de integração (0-10)": ease,
            "risco se falhar (0-10, penaliza)": risk,
            "complexidade (0-10, penaliza)": complexity,
            "confiança necessária (0-10, penaliza)": conf_needed,
        },
    }


def _rec(score: float, has_volume_signal: bool = False) -> str:
    if score >= 8.0:
        return "AGORA"
    if score >= 5.0:
        return "DEPOIS"
    return "NÃO USAR"


def _uniq(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for i in items:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def build_architecture(scan: _SR, stack: StackInfo, flows: list[FlowPoint]) -> tuple[list[dict], list[dict]]:
    """Build a minimal architecture graph for visualization."""
    nodes: list[dict] = []
    edges: list[dict] = []

    def add_node(id_, label, kind="service", jev_here=False):
        nodes.append({"id": id_, "label": label, "kind": kind, "jev_here": jev_here})

    add_node("client", "Cliente / Frontend", "client")

    # Pick front-end framework
    front = next((f for f in ("Next.js", "React", "Vue", "Nuxt", "Angular", "Svelte") if f in stack.frameworks), None)
    if front:
        add_node("frontend", front, "frontend")
    elif any(l in stack.languages for l in ("HTML", "JavaScript", "TypeScript", "JavaScript (JSX)", "TypeScript (TSX)", "Vue", "Svelte")):
        add_node("frontend", "Frontend", "frontend")
    else:
        add_node("frontend", "Interface", "frontend")
    edges.append({"from": "client", "to": "frontend"})

    # Backend
    back = next((f for f in ("FastAPI", "Django", "Flask", "Express", "NestJS", "Koa") if f in stack.frameworks), None)
    back_node = "backend"
    if back:
        add_node("backend", back, "backend")
    elif "Python" in stack.languages:
        add_node("backend", "Backend Python", "backend")
    elif "JavaScript" in stack.languages or "TypeScript" in stack.languages:
        add_node("backend", "Backend Node", "backend")
    else:
        add_node("backend", "Backend", "backend")
    edges.append({"from": "frontend", "to": "backend"})

    # Database nodes
    if stack.databases:
        db_label = ", ".join(stack.databases[:3])
        add_node("db", db_label, "database")
        edges.append({"from": "backend", "to": "db"})

    # External integrations
    external_cats = []
    for f in flows:
        if f.category in ("webhook/entry", "external_integration", "payment", "messaging/chat"):
            external_cats.append(f.category)
    external_cats = _uniq(external_cats)
    ext_id = "ext"
    if external_cats:
        ext_labels = []
        if "messaging/chat" in external_cats:
            ext_labels.append("WhatsApp/Telegram/Chat")
        if "payment" in external_cats:
            ext_labels.append("Gateway de pagamento")
        if "external_integration" in external_cats:
            ext_labels.append("Email/PDF/Scraping")
        if "webhook/entry" in external_cats:
            ext_labels.append("Webhooks externos")
        add_node(ext_id, "Integrações: " + ", ".join(ext_labels), "external")
        edges.append({"from": "ext", "to": "backend"})

    # Queue
    queue_cats = [f for f in flows if f.category == "queue/event"]
    if queue_cats or any(b in stack.databases for b in ("Redis", "RabbitMQ", "Kafka", "SQS")) or \
       any(w in stack.frameworks for w in ("Celery",)):
        add_node("queue", "Filas / Workers", "queue")
        edges.append({"from": "backend", "to": "queue"})

    # Mark JEV insertion points based on top opportunities
    jev_pts = []
    for f in flows:
        if f.category in ("classification/routing", "messaging/chat", "moderation",
                          "external_integration", "fraud/risk"):
            jev_pts.append(f.category)
    if jev_pts:
        add_node("jev", "JEV (camada de decisão)", "jev", jev_here=True)
        # Connect JEV to relevant points
        edges.append({"from": "backend", "to": "jev", "dashed": True, "label": "decisão probabilística"})

    return nodes, edges


def summarize_architecture(stack: StackInfo, flows: list[FlowPoint]) -> str:
    parts = []
    if stack.languages:
        parts.append(f"Linguagens principais: {', '.join(stack.languages[:4])}.")
    if stack.frameworks:
        parts.append(f"Frameworks detectados: {', '.join(stack.frameworks[:6])}.")
    if stack.databases:
        parts.append(f"Dados armazenados em: {', '.join(stack.databases[:4])}.")
    cats = [f.name for f in flows[:6]]
    if cats:
        parts.append(f"Fluxos identificados: {', '.join(cats)}.")
    if not parts:
        return "Projeto pequeno ou com estrutura não identificada pela análise estática."
    return " ".join(parts)


def build_report(scan: _SR, source_type: str, source_path: str) -> AnalysisReport:
    from .stack import detect_stack
    stack = detect_stack(scan)
    flows = detect_flows(scan, stack)
    opps = evaluate(scan, stack, flows)
    nodes, edges = build_architecture(scan, stack, flows)
    arch_summary = summarize_architecture(stack, flows)

    warnings: list[str] = []
    limitations = [
        "Esta análise é estática (baseada apenas em código e nomes de arquivos), sem logs, métricas ou dados de produção.",
        "Os scores são heurísticos. Valide com dados reais antes de implementar.",
        "Para recomendações AGORA, recomendamos criar um experimento (baseline + dataset + métricas) antes de ir a produção.",
        "Nenhum segredo (.env) foi lido ou transmitido.",
    ]
    if scan.env_files:
        warnings.append(
            f"Encontrados {len(scan.env_files)} arquivo(s) .env — conteúdos NÃO foram lidos por segurança."
        )

    return AnalysisReport(
        project_name=scan.project_name,
        source_type=source_type,
        source_path=source_path,
        stack=stack,
        architecture_summary=arch_summary,
        flows=flows,
        opportunities=opps,
        architecture_nodes=nodes,
        architecture_edges=edges,
        warnings=warnings,
        limitations=limitations,
        analysis_mode="static",
        mocked_fields=[],
    )
