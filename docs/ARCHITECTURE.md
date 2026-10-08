# Arquitetura — Fase 1

Monólito modular Python/FastAPI, SQLAlchemy, SQLite, Pydantic e NetworkX. Um aluno local, nenhuma autenticação complexa ou LLM. O futuro frontend Next.js apenas apresenta decisões do backend.

Fluxo: currículo → grafo → estado do aluno → planner → sessão → exercício/avaliação → evidência → mastery + revisão → histórico → próximo planejamento.

## Módulos

- `core`: configurações imutáveis, UTC e fuso de calendário configurável.
- `db` / `models`: 13 entidades, chaves estrangeiras e restrições.
- `seed`: currículo provisório e questões determinísticas reproduzíveis.
- `services/curriculum`: inserção validada de dependências e escopo de avaliação.
- `services/knowledge_graph`: DAG, ancestrais, dependências e lacunas.
- `services/mastery`: estimativas puras a partir de evidência qualificada.
- `services/repetition`: revisão desacoplada, intervalos substituíveis.
- `services/evaluation`: cinco formatos determinísticos e protocolo `SemanticEvaluator` futuro.
- `services/planner`: score decomposto, urgência por conceito e soft gating. `SessionBuilder` escolhe a estratégia e compõe as atividades segundo o estado observado.
- `services/learning`: transação de tentativa, estado, revisão e evento; persistência de planos.
- `api` / `schemas`: API mínima de saúde, currículo, estado e planejamento, sem gabaritos.

## Decisões aceitas

1. **Incerteza explícita.** `mastery`, `retention`, `self_confidence`, `evidence_confidence` e `evidence_count` são distintos. Mastery é nulo antes de observações. Baixa confiança é exposta inclusive quando mastery é alto. A confiança é heurística, não intervalo estatístico calibrado.
2. **Soft gating por padrão.** Lacunas reduzem a prioridade do conteúdo avançado e inserem revisão preparatória. Não proíbem A* na mesma sessão. Hard gating requer relação `is_essential=true` e domínio observado abaixo do limiar crítico; o planner procura a base, sem ficar preso ao alvo bloqueado.
3. **Avaliações com escopo explícito.** `AssessmentConcept` associa conceitos e pesos. A disciplina não concede boost automático. Ancestrais podem receber urgência herdada com desconto e explicação.
4. **Tentativas diferentes.** FIRST_ATTEMPT, RETRY e DELAYED_RECALL registram dicas, número por questão/aluno, segundos de resposta e timestamp. Repetições próximas não contam como novas evidências independentes. Recuperação tardia exige intervalo sem exposição ao conceito e sem dicas para fortalecer evidência.
5. **Tempo.** Todos os timestamps são normalizados para UTC. Janelas de prova são datas locais interpretadas por `Settings.timezone`; `ATLAS_TIMEZONE` altera o default, sem ramificações específicas para São Paulo na lógica.
6. **Avaliação determinística.** MULTIPLE_CHOICE, TRUE_FALSE, SHORT_EXACT, NUMERIC e STRUCTURED. Resposta curta é correspondência normalizada com alternativas cadastradas, não análise semântica. STRUCTURED valida campos por rubricas determinísticas. O protocolo semântico não tem implementação nem dependência externa.
7. **Consistência.** Tentativa, estado, revisão e evento pertencem à mesma transação. O serviço não faz commit escondido. Unicidade impede duplicar número de tentativa ou revisão corrente; sessões mantêm snapshot do plano.
8. **Fase 1.** API mínima e serviços testáveis; frontend e execução interativa de atividades permanecem no próximo marco. Não alegar v0.1 completa.

## Session Builder adaptativo

O ranking continua a escolher **o que** merece atenção. `SessionBuilder` escolhe **como** estudar cada conceito:

| Estratégia | Critério inicial | Estrutura |
|---|---|---|
| DIAGNOSTIC | mastery desconhecido, menos de 3 evidências ou confiança <0,35 | recuperação com questão → correção → ponto de decisão; sem explicação antes da resposta |
| LEARNING | mastery <0,60, domínio efetivo <0,45 ou prática recente assistida em conceito ainda não consolidado | recuperação curta → explicação → prática guiada → prática independente → correção → síntese |
| REVIEW | revisão vencida ou retenção <0,60 com mastery ≥0,60 | recuperação sem consulta → segunda questão se disponível → correção → síntese |
| PRACTICE | conhecimento observado, estável e fora dos casos anteriores | recuperação rápida → exercício independente → correção → síntese |

Cada bloco diagnóstico sinaliza `decision_after=true`. O soft gating não insere explicação preparatória antes desse diagnóstico. A avaliação da resposta pode orientar novo planejamento do tempo restante; o plano estático não supõe qual ramo será necessário. O sistema não concede mastery por planejar, ler ou seguir uma instrução. Blocos respeitam o orçamento inclusive em sessões de 10 minutos. Quando só existe uma questão de revisão, não inventa uma segunda.

## Evolução

A estrutura fica na raiz do checkout, evitando pasta intermediária redundante. `create_all` inicializa o primeiro schema; não é sistema de migrations. Antes de mudar schema em instâncias com dados, introduzir migrações versionadas e backup. PostgreSQL precisa de driver e validação próprios. Nenhum dado é enviado a serviços externos no uso normal.

Futuro MaterialIngestionService → extração/chunking → embeddings/vector store → curriculum mapping → tutor/exercícios. Preservar proveniência e revisar conteúdo antes de alterar currículo. Provider LLM opcional com configuração explícita, sem controlar domínio, prioridade ou calendário.
