# Arquitetura — runtime v0.1

Monólito modular Python/FastAPI, SQLAlchemy, SQLite, Pydantic e NetworkX. Um aluno local, nenhuma autenticação complexa ou LLM. O futuro frontend Next.js apenas apresenta decisões do backend.

Fluxo: CurriculumPackage JSON → CurriculumValidator → CurriculumImporter → currículo no banco → grafo → estado do aluno → AdaptivePlanner → SessionBuilder → SessionRuntime → atividade/resposta → Evaluator + LearningService → evidência/mastery/revisão → SessionDecisionEngine → próxima atividade.

## Módulos

- `core`: configurações imutáveis, UTC e fuso de calendário configurável.
- `db` / `models`: entidades curriculares, de aprendizagem e runtime, chaves estrangeiras e restrições.
- `seed`: currículo provisório e questões determinísticas reproduzíveis.
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

## Evolução

A estrutura fica na raiz do checkout. `create_all` inicializa tabelas novas. Um ajuste aditivo e idempotente via `ALTER TABLE` acrescenta colunas opcionais do runtime e os campos curriculares em `concepts` no SQLite v0.1 preexistente; não transforma nem apaga dados. Ainda não há migrations versionadas para mudanças gerais. Antes de mudanças futuras em instâncias com progresso, introduzir migrations e backup. PostgreSQL precisa de driver e validação próprios. A autenticação e concorrência entre vários usuários ficam fora do escopo local. Nenhum dado é enviado a serviços externos no uso normal.

Futuro MaterialIngestionService → extração/chunking → embeddings/vector store → curriculum mapping → tutor/exercícios. Preservar proveniência e revisar conteúdo antes de alterar currículo. Provider LLM opcional com configuração explícita, sem controlar domínio, prioridade ou calendário.
