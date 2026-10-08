# Esquema — runtime e Curriculum Package v0.1

17 tabelas, SQLAlchemy + SQLite, com `PRAGMA foreign_keys=ON`. IDs simples inteiros, salvo chaves compostas indicadas. JSON guarda rubricas, respostas e snapshots; não há arquivos pessoais desnecessários. Campos temporais têm contrato UTC, inclusive no roundtrip SQLite.

| Tabela | Campos e vínculos principais |
|---|---|
| students | id, name, created_at |
| subjects | id, name único |
| curriculum_units | id, subject_id, key, name, description, position; subject+key único |
| curriculum_explanations | id, subject_id, concept_id, key, text; subject+key único |
| curriculum_package_records | id, package_id, version, content_hash, content_status, payload JSON, imported_at; package_id+version único |
| curriculum_item_records | id, package_id, item_type, item_key, object_id, latest_version, content_hash, provenance JSON; pacote+tipo+chave único |
| concepts | id, subject_id, unit_id nullable, parent_concept_id nullable, slug, name, description, difficulty, importance, estimated_minutes, learning_objectives JSON nullable, created_at; subject+slug único |
| concept_dependencies | id, concept_id, prerequisite_concept_id, dependency_strength, is_essential; par único |
| assessments | id, subject_id, name, start_date, end_date, importance; subject+name+start_date único |
| assessment_concepts | **PK assessment_id+concept_id**, weight (0,1] |
| student_concept_states | **PK student_id+concept_id**; mastery nullable, retention, retention_calculated_at, self_confidence nullable, evidence_confidence, evidence_count, delayed_evidence_count, independent_correct, stability_days, times_seen/attempted/correct, last_seen/attempt/correct/independent_at, difficulty_success_rate, difficulty_attempt_weight, next_review_at, status |
| study_sessions | id, student_id, available_minutes, planned_minutes, used_minutes, actual_minutes nullable, created_at, planned_at, started_at, completed_at, status, strategy, adaptation_reason, current_activity_id, plan_snapshot |
| session_activities | id, session_id, position, execution_order, block_index, concept_id nullable, exercise_id nullable, activity_type, estimated_minutes, actual_minutes nullable, instructions, planned_at, started_at, completed_at, status, strategy, executed, is_conditional, decision_after, adaptation_reason; session+position único |
| exercises | id, concept_id, slug único, exercise_type, prompt, options, answer_spec, explanation, difficulty, error_map, origin_type nullable, provenance JSON nullable |
| exercise_attempts | id, student_id, exercise_id, activity_id nullable, attempt_kind, answer, correct, score, error_type, concepts_involved, evaluator_confidence, feedback, hints_used, attempt_number, response_time (segundos), self_confidence, is_independent, occurred_at; student+exercise+attempt_number único |
| review_schedules | id, student_id, concept_id, stage, due_at, updated_at; student+concept único |
| learning_events | id, student_id, concept_id nullable, attempt_id nullable/único, event_type, payload, occurred_at |

## Integridade e limites

- Intervalos, forças, pesos, tempos e datas têm restrições de banco e/ou validação Pydantic.
- Ciclos e referências inexistentes são rejeitados pelo Curriculum/KnowledgeGraph antes de gravar a aresta.
- Uma revisão corrente por aluno/conceito; histórico de decisões em LearningEvent.
- Um registro por tentativa, inclusive retries. Nunca sobrescrever uma resposta antiga com o acerto posterior.
- `LearningService` e `SessionRuntime` exigem transação do chamador. Resposta, estado, revisão, decisão, atividades e eventos são atômicos. O runtime rejeita resposta duplicada da mesma atividade com conflito; múltiplos clientes concorrentes ainda precisam de estratégia explícita de controle de versão/transação.
- `next_review_at` e `retention` são snapshots auxiliares. O scheduler sincroniza o primeiro com ReviewSchedule; leituras recalculam retenção no instante solicitado.
- Um plano salvo não prova execução. A execução atual mantém uma atividade corrente, registra começo/fim, e distingue atividades concluídas e puladas. Um evento de decisão audita cada adaptação.
- Datas de avaliação não são timestamps UTC: representam dias de calendário no fuso configurado. O relógio UTC é convertido para esse fuso ao calcular urgência.
- `create_all` inicializa tabelas ausentes. Em SQLite v0.1 existente, a inicialização acrescenta somente colunas opcionais do runtime, `unit_id`, `parent_concept_id`, `learning_objectives` em `concepts` e `origin_type`, `provenance` em `exercises` com `ALTER TABLE`, de modo idempotente; os registros anteriores permanecem. Isso não é migration versionada nem resolve alterações arbitrárias de esquema. Fazer backup e implantar migrations antes de futuras mudanças complexas ou PostgreSQL.
- `curriculum_item_records` mapeia a posse de cada item e sua última proveniência; `curriculum_package_records.payload` conserva o JSON de cada versão para auditoria. Nenhuma tabela de estado do aluno é alterada na importação.
- Questões do seed novo usam `PROVISIONAL_SEED`; questões registradas pelo serviço de diagnóstico real usam `ATLAS_AUTHORED_DIAGNOSTIC` e proveniência com conceito, autoria ATLAS, pacote, fonte e página. Questões do próprio pacote curricular usam `CURRICULUM_PACKAGE`. Registros legados do seed podem ter `origin_type` nulo após o `ALTER TABLE`; o modo real não os admite.
