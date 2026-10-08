# Arquitetura — runtime v0.1

Monólito modular Python/FastAPI, SQLAlchemy, SQLite, Pydantic e NetworkX. Um aluno local, nenhuma autenticação complexa ou LLM. O frontend MVP Next.js/TypeScript apenas apresenta decisões do backend.

Fluxo: CurriculumPackage JSON → CurriculumValidator → CurriculumImporter → currículo no banco → grafo → estado do aluno → AdaptivePlanner → SessionBuilder → SessionRuntime → atividade/resposta → Evaluator + LearningService → evidência/mastery/revisão → SessionDecisionEngine → próxima atividade.

## Módulos

- `core`: configurações imutáveis, UTC e fuso de calendário configurável.
- `db` / `models`: entidades curriculares, de aprendizagem e runtime, chaves estrangeiras e restrições.
- `seed`: currículo provisório e questões determinísticas reproduzíveis, usado somente em `ATLAS_CONTENT_MODE=provisional`.
- `bootstrap`: seleciona `provisional` ou `real` e rejeita bancos mistos; `real` importa o pacote institucional em DRAFT sem apagar o estado do aluno.
- `services/diagnostics`: escopo inicial de 14 conceitos reais e registro idempotente de questões autorais do ATLAS, com proveniência derivada do conceito institucional.
- `services/curriculum`: formato versionado, validação integral antes de gravar, importação transacional e relatório; também inserção validada de dependências e escopo de avaliação.
- `services/knowledge_graph`: DAG, ancestrais, dependências e lacunas.
- `services/mastery`: estimativas puras a partir de evidência qualificada.
- `services/repetition`: revisão desacoplada, intervalos substituíveis.
- `services/evaluation`: cinco formatos determinísticos e protocolo `SemanticEvaluator` futuro.
- `services/planner`: score decomposto, urgência por conceito e soft gating. `SessionBuilder` escolhe a estratégia e compõe as atividades segundo o estado observado.
- `services/learning`: transação de tentativa, estado, revisão e evento; persistência de planos.
- `services/session_decision`: regras puras depois de uma tentativa, sem banco nem LLM.
- `services/session_runtime`: máquina de estados persistida, cursor da atividade, orçamento, saltos e histórico.
- `api` / `schemas`: execução mínima, além de saúde/currículo/estado/planejamento; sem gabaritos.
- `frontend/src/app`: dashboard, sessão e progresso no App Router; CSS mobile-first, sem biblioteca visual pesada.
- `frontend/src/lib/api.ts`: URL configurável única, tipos públicos, chamadas HTTP e tradução básica de erros. `state.ts` só classifica e formata o estado recebido; não calcula domínio.

## Decisões aceitas

1. **Incerteza explícita.** `mastery`, `retention`, `self_confidence`, `evidence_confidence` e `evidence_count` são distintos. Mastery é nulo antes de observações. Baixa confiança é exposta inclusive quando mastery é alto. A confiança é heurística, não intervalo estatístico calibrado.
2. **Soft gating por padrão.** Lacunas reduzem a prioridade do conteúdo avançado e inserem revisão preparatória. Não proíbem A* na mesma sessão. Hard gating requer relação `is_essential=true` e domínio observado abaixo do limiar crítico; o planner procura a base, sem ficar preso ao alvo bloqueado.
3. **Avaliações com escopo explícito.** `AssessmentConcept` associa conceitos e pesos. A disciplina não concede boost automático. Ancestrais podem receber urgência herdada com desconto e explicação.
4. **Tentativas diferentes.** FIRST_ATTEMPT, RETRY e DELAYED_RECALL registram dicas, número por questão/aluno, segundos de resposta e timestamp. Repetições próximas não contam como novas evidências independentes. Recuperação tardia exige intervalo sem exposição ao conceito e sem dicas para fortalecer evidência.
5. **Tempo.** Todos os timestamps são normalizados para UTC. Janelas de prova são datas locais interpretadas por `Settings.timezone`; `ATLAS_TIMEZONE` altera o default, sem ramificações específicas para São Paulo na lógica.
6. **Avaliação determinística.** MULTIPLE_CHOICE, TRUE_FALSE, SHORT_EXACT, NUMERIC e STRUCTURED. Resposta curta é correspondência normalizada com alternativas cadastradas, não análise semântica. STRUCTURED valida campos por rubricas determinísticas. O protocolo semântico não tem implementação nem dependência externa.
7. **Consistência.** Tentativa, estado, revisão e evento pertencem à mesma transação. O serviço não faz commit escondido. Unicidade impede duplicar número de tentativa ou revisão corrente; sessões mantêm snapshot do plano.
8. **Runtime.** A sessão passa por PLANNED → IN_PROGRESS → COMPLETED ou ABANDONED. Uma resposta só é aceita para a atividade atual. Repeti-la retorna conflito; concluir ou abandonar bloqueia novas respostas. Exercícios exigem `/answer`; atividades sem exercício usam `/advance`.
9. **Currículo separado do aluno.** Pacotes são snapshots versionados com proveniência por item. O importador altera apenas tabelas curriculares, não `StudentConceptState`, tentativas, revisões nem sessões. O seed provisório não é substituído automaticamente. A validação checa referências, rubricas e ciclos, e a importação usa savepoint para rollback completo. Versões anteriores permanecem auditáveis; veja [contrato de importação](CURRICULUM_PACKAGE.md).
10. **Bootstrap explícito.** Default `provisional` preserva o comportamento anterior. `real` valida e importa `uniasselvi-ia-simbolica-2026-2` v0.1.0 em transação, cria somente o aluno local necessário e falha se houver conteúdo fora desse pacote ou de diagnósticos autorais vinculados. `/health` informa o modo ativo. Não há conversão automática de banco provisório para real: use um banco separado ou uma migração planejada.
11. **Questões diagnósticas distintas.** Os 14 alvos iniciais são chaves de conceitos do currículo real. O pacote institucional contém zero questões e zero avaliações. `register_atlas_diagnostic` aceita somente esses conceitos, marca `ATLAS_AUTHORED_DIAGNOSTIC`, deriva material/página da proveniência do conceito e não altera domínio do aluno. O bootstrap carrega 28 questões de um pacote JSON autoral separado, duas por alvo. Chaves são imutáveis e recarga idêntica retorna UNCHANGED. Até haver duas questões autorais para cada alvo, `/sessions/start` e `/sessions/plan` respondem 422 com a cobertura faltante. Questões do seed têm `PROVISIONAL_SEED` e nunca entram no planner do modo real.

## Session Builder adaptativo

O ranking continua a escolher **o que** merece atenção. `SessionBuilder` escolhe **como** estudar cada conceito:

| Estratégia | Critério inicial | Estrutura |
|---|---|---|
| DIAGNOSTIC | mastery desconhecido, menos de 3 evidências ou confiança <0,35 | recuperação com questão → correção → ponto de decisão; sem explicação antes da resposta |
| LEARNING | mastery <0,60, domínio efetivo <0,45 ou prática recente assistida em conceito ainda não consolidado | recuperação curta → explicação → prática guiada → prática independente → correção → síntese |
| REVIEW | revisão vencida ou retenção <0,60 com mastery ≥0,60 | recuperação sem consulta → segunda questão se disponível → correção → síntese |
| PRACTICE | conhecimento observado, estável e fora dos casos anteriores | recuperação rápida → exercício independente → correção → síntese |

O primeiro exercício diagnóstico sinaliza `decision_after=true` e aciona uma decisão real depois da correção. O soft gating não insere explicação preparatória antes desse diagnóstico. O motor pode inserir explicação, prática guiada, confirmação independente ou remediação de pré-requisito. Itens condicionais só aparecem após o resultado; itens pulados mantêm `status=SKIPPED`, motivo e tempo realizado nulo. Planejar ou ler não concede mastery.

## Tempo, auditoria e API

`remaining_minutes = available_minutes - used_minutes`. Uma atividade concluída consome `actual_minutes` informado ou, na ausência dele, sua estimativa. `actual_minutes` da sessão soma somente tempos informados; `used_minutes` é o orçamento cobrado inclusive pelas estimativas. O runtime valida e recusa tempos maiores que o saldo. Antes de ativar o próximo item, remove atividades futuras do fim até que o plano restante caiba. `planned_minutes` acompanha o plano ainda executável mais o tempo já consumido, sempre até o orçamento. O snapshot original fica em `plan_snapshot`.

Cada resposta atualiza tentativa, estado, revisão, atividades e `LearningEvent(SESSION_DECISION)` na mesma transação. O evento registra decisão, motivo, saldo, IDs inseridos e pulados. O endpoint público apresenta só a questão da atividade atual, sem rubrica ou gabarito; após uma tentativa, retorna acerto, tipo de erro e feedback curto sem alternativa correta. `GET /sessions/{id}` permite retomar a sessão após reiniciar o processo.

`POST /sessions/start` gera e inicia plano; `GET /sessions/{id}` lê estado; `POST /sessions/{id}/answer` avalia; `POST /sessions/{id}/advance` conclui instruções sem questão; `POST /sessions/{id}/finish` conclui ou abandona.

## Frontend MVP e acesso do navegador

O dashboard consulta `/student/state` e `/subjects`, oferece 20/40/60 minutos e armazena apenas o ID da sessão ativa em `localStorage` para retomada no mesmo navegador. A rota `/session/[id]` usa o estado público de `/sessions/{id}`, envia respostas com tempo de resposta e declaração de dica, avança atividades sem exercício e fecha uma sessão sem atividade corrente. A conclusão mostra tempo, atividades e razões de decisão. `/progress` nunca mostra o prior de 0,35 como mastery observado: `mastery=null` é exibido como “Ainda não diagnosticado”. O browser não recebe rubricas nem gabaritos.

O backend libera CORS apenas para origens configuradas em `ATLAS_CORS_ORIGINS`, com defaults locais e sem curinga. `NEXT_PUBLIC_ATLAS_API_URL` define o endereço visto pelo navegador no momento do build. O manifesto PWA contém nome, cores e ícone; offline e service worker ficam para outro marco. A retomada depende do `localStorage` do mesmo navegador, pois ainda não há listagem de sessões por aluno. Respostas estruturadas são inseridas como JSON no MVP. O erro 422 do modo real usa o mesmo estado público de falta de exercícios que o dashboard já apresenta.

## Evolução

A estrutura fica na raiz do checkout. `create_all` inicializa tabelas novas. Um ajuste aditivo e idempotente via `ALTER TABLE` acrescenta colunas opcionais do runtime e os campos curriculares em `concepts` no SQLite v0.1 preexistente; não transforma nem apaga dados. Alembic oferece baseline congelada do schema atual e preserva dados de bancos existentes. Em produção o startup exige revisão atual (`ATLAS_SCHEMA_MODE=migrations`), sem DDL automático. PostgreSQL 16 usa psycopg e foi validado com bootstrap real e persistência após restart. Docker executa a API sem banco/segredo embutidos; CI inclui serviço PostgreSQL. O build frontend exige URL pública explícita. Ver DEPLOYMENT.md para rollout e backup. A autenticação e concorrência entre vários usuários ficam fora do escopo local. Nenhum dado é enviado a serviços externos no uso normal.

Futuro MaterialIngestionService → extração/chunking → embeddings/vector store → curriculum mapping → tutor/exercícios. Preservar proveniência e revisar conteúdo antes de alterar currículo. Provider LLM opcional com configuração explícita, sem controlar domínio, prioridade ou calendário.
