# JEV Project Analyzer

Uma ferramenta web local que analisa um projeto de software e avalia **onde JEV
(ou qualquer camada de decisão probabilística) pode gerar ROI real** e, tão
importante quanto, **onde NÃO deve ser usado**.

> Princípios: ROI > simplicidade > confiabilidade > novidade tecnológica.

---

## O que ela faz (V1 — MVP)

1. **Entrada de projeto**
   - Caminho local (qualquer diretório)
   - URL do GitHub (repositórios públicos, clone raso via `git`)
   - `owner/repo` (atalho para GitHub)
2. **Análise estática do código** (100% leitura — nenhuma modificação):
   - Detecta stack: linguagens, frameworks, bancos, infra, serviços, auth
   - Detecta fluxos (webhooks, chat, pagamentos, auth, filas, moderação, fraude,
     chatbot, suporte, automações, scraping/PDF, busca, notificações etc.)
3. **Avaliação honesta para cada oportunidade** com:
   - Caso de uso, ponto exato de entrada do JEV no fluxo
   - Score 0–10 **calculado** (impacto + frequência + custo atual + facilidade
     − risco − complexidade − confiança necessária) — com breakdown explícito
   - Benefício, prós/contras, complexidade, impacto em custo, riscos
   - Recomendação **AGORA / DEPOIS / NÃO USAR**
   - Comparação explícita entre **Regra tradicional vs JEV vs LLM vs Embeddings
     vs Humano vs Não fazer nada** (custo, latência, previsibilidade, quando usar)
   - Escala/volume que justifica a adoção
   - Solução atual/alternativa sem JEV
4. **Dashboard** com:
   - Visão geral (nome, stack, resumo arquitetural, contadores)
   - Arquitetura inferida em SVG com nós JEV destacados em azul
   - Matriz impacto × complexidade (bolhas clicáveis = quick wins)
   - Cards individuais de oportunidade com score rings e filtros
   - Lista dos fluxos detectados com evidências
5. **Copiar Prompt de Implementação** por oportunidade:
   - Prompt auto-contido que um agente de programação pode usar
   - Objetivo, contexto arquitetural, fluxo atual vs proposto, arquivos
     reais afetados, novos arquivos, schemas/contratos, tratamento de erros,
     segurança, observabilidade, métricas, fallback, testes, critérios de aceite
   - **Nunca inventa nomes de arquivos** que não existam no repositório

## O que ela **NÃO** faz (por segurança)

- Não modifica nenhum arquivo do projeto analisado
- Não faz commit/push/PR/migrations
- Não lê arquivos `.env` (detecta sua presença e avisa)
- Não implementa automaticamente nada — a implementação cabe ao usuário via
  prompt copiado
- Não expõe segredos

## Limitações conhecidas (V1)

- **Análise apenas estática** (não usa logs, métricas ou dados de produção)
- **Detecção é heurística** (escore não é milagroso; sempre valide com dados reais)
- Repositórios **privados do GitHub** não funcionam sem credenciais configuradas
  (clone local como contorno)
- O clone do GitHub é raso (`--depth 1`) e temporário (limpo ao reiniciar)
- Scores e recomendações precisam de experimentação real antes de produção
  (baseline, dataset, métricas mínimas)

## Como rodar localmente

```bash
cd /home/user/Jev
bash run.sh
```

O script cria um `.venv` se necessário, instala dependências e sobe em
<http://localhost:8000>.

### Rodando com o Python diretamente (sem script)

```bash
cd /home/user/Jev
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.server:app --host 0.0.0.0 --port 8000
```

Depois abra <http://localhost:8000> no navegador.

## Como usar

1. Cole uma das entradas:
   - `/caminho/local/do/projeto`
   - `https://github.com/owner/repo`
   - `owner/repo`
2. Clique em **Analisar**.
3. Veja o dashboard, identifique quick wins (matriz impacto × complexidade).
4. Para cada oportunidade, abra e clique em **📋 Copiar Prompt de Implementação**.
5. Use o prompt com o agente de código de sua preferência.

## Estrutura do código

```
app/
  server.py             # FastAPI app (rotas /api/analyze, /api/analysis/{id})
  analyzer/
    models.py           # Dataclasses de resultado
    scanner.py          # Caminhada de diretório (read-only, ignora .env)
    stack.py            # Detecção de stack (frameworks, DBs, auth, serviços)
    flows.py            # Detecção heurística de fluxos e pontos de decisão
    evaluator.py        # Avaliação de oportunidades JEV (com scores e comparações)
    prompt_builder.py   # Geração do prompt de implementação
    sources.py          # Adapters (local path, GitHub URL/atalho)
static/
  index.html            # UI (Tailwind + Chart.js via CDN)
  app.js                # Lógica do dashboard
run.sh                  # Script de inicialização
requirements.txt        # Dependências Python
```

## Exemplos

- Clique em “Testar este próprio repositório” para ver uma análise do próprio
  analisador (útil para ver o painel funcionando; os acertos para ele mesmo são
  baixos porque ele contém textos de exemplo sobre vários padrões).
- Botão “pallets/flask (GitHub)” clona e analisa o Flask.

## Roadmap (das ideias do usuário, não implementadas no V1)

- Comparador de soluções (parcialmente feito: já mostra tabela de alternativas)
- Score 100% explicável (parcialmente feito: mostra critérios e fórmula)
- Detecção automática de fluxos (feita por regex heurística; não por AST completa)
- Mapa de decisões (nós “decisão probabilística” marcados no SVG)
- Detector de “não use IA” (feito para auth/pagamento/notificações/CPF)
- Simulador de ROI (não implementado)
- Análise com dados/logs reais (não implementado)
- Modo “Arquitetura + Produção” (não implementado)
- Criar experimento com dataset/baseline (não implementado)
- Prompts por etapa: Prototipar / Implementar / Validar (apenas Implementar por
  enquanto)
