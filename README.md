# ATLAS · Adaptive Learning System

Núcleo local de aprendizado adaptativo: “Tenho X minutos. O que devo estudar agora?”
O backend v0.1 reúne currículo de IA Simbólica, grafo, avaliação determinística, modelo de evidências, revisão, planejamento explicável e execução interativa de sessões. O restante da sessão muda após uma resposta real. O frontend MVP é um webapp mobile-first em Next.js, preparado para PWA. Não depende de LLM.

`ATLAS_CONTENT_MODE=provisional` (default) mantém o seed antigo para desenvolvimento e testes. `ATLAS_CONTENT_MODE=real` importa de forma idempotente o [currículo institucional em DRAFT](curricula/uniasselvi/inteligencia_artificial_simbolica_2026-2.v0.1.0.json): 9 unidades, 40 conceitos e 32 pré-requisitos, sem avaliações ou questões inventadas. Use **um banco SQLite vazio e separado** ao mudar para `real`, por exemplo:

```sh
cd backend
ATLAS_CONTENT_MODE=real ATLAS_DATABASE_URL=sqlite:///../data/atlas-real.db .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

O bootstrap recusa misturar o currículo real com o seed provisório e preserva o banco antigo sem apagá-lo. O modo `real` cria apenas o aluno local `student_id=1` se ainda não existir. Enquanto faltarem questões diagnósticas autorais, `/sessions/start` responde 422 com a cobertura ausente; o dashboard mostra o estado de falta de exercícios. Nenhum exercício provisório é tratado como oficial.

Currículos reais podem ser preparados como pacotes JSON versionados e validados antes da importação. O [exemplo](examples/curriculum_package.example.json) é **DEMONSTRAÇÃO fictícia**, não uma ementa oficial. O conteúdo do seed provisório não foi substituído.

## Instalação e execução

Python 3.12+. Na raiz do checkout:

```sh
python -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
.venv/bin/python -m pytest
```

O comando `python -m app.seed` é opcional e exclusivo do modo `provisional`. O modo `real` não o executa e o comando recusa `ATLAS_CONTENT_MODE=real`. Para demonstração provisória, inicie `uvicorn` sem mudar o modo default. `python -m app.examples` e `python -m app.runtime_example` são exemplos locais separados do bootstrap real.

API documentada em `/docs`: saúde, currículo, estado, planejamento e execução. `POST /sessions/plan` apenas prevê. `POST /sessions/start` com `{"student_id":1,"available_minutes":40}` cria a sessão e retorna a atividade atual. Use `POST /sessions/{id}/answer` com `activity_id`, `answer`, `response_time`, `hints_used` e `self_confidence` para responder a um exercício; use `POST /sessions/{id}/advance` com `activity_id` para concluir uma atividade sem questão. Ambos aceitam `actual_minutes` opcional e retornam a próxima atividade. `GET /sessions/{id}` recupera o estado e o histórico de decisões; `POST /sessions/{id}/finish` conclui ou abandona (`{"abandon":true}`). A API nunca envia `answer_spec` ou a alternativa correta.

### Frontend MVP

Use Node.js 22+ e npm. Em outro terminal, com o backend em execução:

```sh
cd frontend
npm ci
cp .env.local.example .env.local
npm run dev
```

Abra `http://localhost:3000`. `NEXT_PUBLIC_ATLAS_API_URL` aponta para o FastAPI visto pelo navegador (default local `http://localhost:8000`); ajuste antes do build para outro ambiente. `ATLAS_CORS_ORIGINS` no backend aceita origens explícitas separadas por vírgula, como `https://atlas.exemplo.com`; o default só libera `localhost:3000` e `127.0.0.1:3000`. Não use `*` em produção. Para validar: `cd frontend && npm test && npm run build`; os testes do backend continuam em `cd backend && .venv/bin/python -m pytest`.

O dashboard mostra disciplinas e um resumo do estado, inicia sessões de 20/40/60 minutos e oferece retomada pelo ID guardado no `localStorage` deste navegador. A tela de sessão responde ou avança atividades e conclui automaticamente quando não resta atividade. `/progress` mostra mastery somente quando medido, junto da confiança e quantidade de evidências. Respostas `STRUCTURED` usam JSON conforme o enunciado. Se não houver conteúdo suficiente para montar sessão, a tela mostra o erro explicitamente.

Banco padrão: `data/atlas.db` (ignorado pelo Git). Configure `ATLAS_DATABASE_URL` para outro banco SQLAlchemy e `ATLAS_TIMEZONE` para outro fuso (default `America/Sao_Paulo`). Timestamps são persistidos em UTC. Nenhum segredo é necessário. O serviço é local e não tem autenticação; não o exponha publicamente.

Seed idempotente no modo `provisional`: Gabriel, 30 conceitos, relações, questões e avaliação de 13 a 17/10/2026 com escopo provisório explícito. Não representa necessariamente a ementa oficial. Reexecutar preserva estados, respostas e conteúdo já existente. Suas novas questões recebem `origin_type=PROVISIONAL_SEED`.

Para conferir um pacote antes de importá-lo, execute na pasta `backend`:

```sh
.venv/bin/python -m app.services.curriculum validate ../examples/curriculum_package.example.json
.venv/bin/python -m app.services.curriculum import caminho/do/pacote.json
```

O segundo comando grava no banco configurado por `ATLAS_DATABASE_URL` ou no banco padrão; `--database-url` permite escolher outro. Importar é uma ação explícita: executar o seed ou iniciar a API não importa o exemplo. O relatório JSON mostra registros criados, alterados e inalterados. Consulte [formato e política de versões](docs/CURRICULUM_PACKAGE.md) antes de montar um pacote institucional.

## Estrutura

```text
backend/app/
  api/ core/ db/ models/ schemas/ seed/
  services/{curriculum,knowledge_graph,mastery,repetition,evaluation,planner}/
  services/{session_decision,session_runtime}.py
backend/tests/
frontend/src/app/{page.tsx,progress/,session/[id]/}
frontend/src/lib/{api,state,session-storage}.ts
frontend/public/manifest.webmanifest
docs/
data/                     # SQLite local
```

O frontend usa `student_id=1` temporariamente, não tem autenticação e não busca sessões antigas fora do ID salvo no navegador. O manifesto permite instalação básica; não há service worker nem uso offline. Para bancos SQLite v0.1 existentes, a inicialização acrescenta colunas opcionais do runtime, currículo e proveniência de exercícios, preservando dados. Isso ainda não é um sistema de migrations versionadas; faça backup antes de atualizações futuras. PostgreSQL ainda não foi validado.

Veja [arquitetura](docs/ARCHITECTURE.md), [modelo de aprendizado](docs/LEARNING_MODEL.md), [grafo](docs/KNOWLEDGE_GRAPH.md), [pacote curricular](docs/CURRICULUM_PACKAGE.md) e [roadmap](docs/ROADMAP.md). Mastery é uma estimativa heurística; consulte sempre a confiança da evidência e sua quantidade.

Um [exemplo reproduzível de runtime](docs/RUNTIME_EXAMPLE.json) acompanha a sequência de um diagnóstico errado de heurística, explicação, prática, A* e revisão agendada, com os minutos restantes após cada passo. Usa banco sintético em memória.
