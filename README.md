# ATLAS · Adaptive Learning System

Núcleo local de aprendizado adaptativo: “Tenho X minutos. O que devo estudar agora?”
O backend v0.1 reúne currículo de IA Simbólica, grafo, avaliação determinística, modelo de evidências, revisão, planejamento explicável e execução interativa de sessões. O restante da sessão muda após uma resposta real. **O frontend pertence ao próximo marco.** Não depende de LLM.

## Instalação e execução

Python 3.12+. Na raiz do checkout:

```sh
python -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
.venv/bin/python -m app.seed
.venv/bin/python -m pytest
.venv/bin/python -m app.examples
.venv/bin/python -m app.runtime_example
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API documentada em `/docs`: saúde, currículo, estado, planejamento e execução. `POST /sessions/plan` apenas prevê. `POST /sessions/start` com `{"student_id":1,"available_minutes":40}` cria a sessão e retorna a atividade atual. Use `POST /sessions/{id}/answer` com `activity_id`, `answer`, `response_time`, `hints_used` e `self_confidence` para responder a um exercício; use `POST /sessions/{id}/advance` com `activity_id` para concluir uma atividade sem questão. Ambos aceitam `actual_minutes` opcional e retornam a próxima atividade. `GET /sessions/{id}` recupera o estado e o histórico de decisões; `POST /sessions/{id}/finish` conclui ou abandona (`{"abandon":true}`). A API nunca envia `answer_spec` ou a alternativa correta.

Banco padrão: `data/atlas.db` (ignorado pelo Git). Configure `ATLAS_DATABASE_URL` para outro banco SQLAlchemy e `ATLAS_TIMEZONE` para outro fuso (default `America/Sao_Paulo`). Timestamps são persistidos em UTC. Nenhum segredo é necessário. O serviço é local e não tem autenticação; não o exponha publicamente.

Seed idempotente: Gabriel, 30 conceitos, relações, questões e avaliação de 13 a 17/10/2026 com escopo provisório explícito. Não representa necessariamente a ementa oficial. Reexecutar preserva estados, respostas e conteúdo já existente.

## Estrutura

```text
backend/app/
  api/ core/ db/ models/ schemas/ seed/
  services/{curriculum,knowledge_graph,mastery,repetition,evaluation,planner}/
  services/{session_decision,session_runtime}.py
backend/tests/
docs/
data/                     # SQLite local
```

`frontend/` será criado somente no marco da interface. Para bancos SQLite v0.1 existentes, a inicialização acrescenta apenas as colunas opcionais do runtime, preservando dados. Isso ainda não é um sistema de migrations versionadas; faça backup antes de atualizações futuras. PostgreSQL ainda não foi validado.

Veja [arquitetura](docs/ARCHITECTURE.md), [modelo de aprendizado](docs/LEARNING_MODEL.md), [grafo](docs/KNOWLEDGE_GRAPH.md) e [roadmap](docs/ROADMAP.md). Mastery é uma estimativa heurística; consulte sempre a confiança da evidência e sua quantidade.

Um [exemplo reproduzível de runtime](docs/RUNTIME_EXAMPLE.json) acompanha a sequência de um diagnóstico errado de heurística, explicação, prática, A* e revisão agendada, com os minutos restantes após cada passo. Usa banco sintético em memória.
