# ATLAS · Adaptive Learning System

Núcleo local de aprendizado adaptativo: “Tenho X minutos. O que devo estudar agora?”
Fase 1 da v0.1: banco persistente, currículo de IA Simbólica, grafo, avaliação determinística, modelo de evidências, revisão e planejamento explicável com estratégias de sessão adaptadas ao estado do aluno. **Frontend e fluxo interativo de sessões pertencem ao próximo marco.** Não depende de LLM.

## Instalação e execução

Python 3.12+. Na raiz do checkout:

```sh
python -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
.venv/bin/python -m app.seed
.venv/bin/python -m pytest
.venv/bin/python -m app.examples
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API mínima documentada em `/docs`: saúde do banco, currículo, estado e planejamento. Exemplo de entrada de `POST /sessions/plan`: `{"student_id":1,"available_minutes":40}`. O planejamento não altera o domínio do aluno.

Banco padrão: `data/atlas.db` (ignorado pelo Git). Configure `ATLAS_DATABASE_URL` para outro banco SQLAlchemy e `ATLAS_TIMEZONE` para outro fuso (default `America/Sao_Paulo`). Timestamps são persistidos em UTC. Nenhum segredo é necessário. O serviço é local e não tem autenticação; não o exponha publicamente.

Seed idempotente: Gabriel, 30 conceitos, relações, questões e avaliação de 13 a 17/10/2026 com escopo provisório explícito. Não representa necessariamente a ementa oficial. Reexecutar preserva estados, respostas e conteúdo já existente.

## Estrutura

```text
backend/app/
  api/ core/ db/ models/ schemas/ seed/
  services/{curriculum,knowledge_graph,mastery,repetition,evaluation,planner}/
backend/tests/
docs/
data/                     # SQLite local
```

`frontend/` será criado somente no marco da interface. Inicialização cria tabelas ausentes; evolução do schema exigirá migrations antes de atualizar bancos existentes. PostgreSQL ainda não foi validado.

Veja [arquitetura](docs/ARCHITECTURE.md), [modelo de aprendizado](docs/LEARNING_MODEL.md), [grafo](docs/KNOWLEDGE_GRAPH.md) e [roadmap](docs/ROADMAP.md). Mastery é uma estimativa heurística; consulte sempre a confiança da evidência e sua quantidade.
