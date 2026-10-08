# Esquema final — Fase 1

13 tabelas, SQLAlchemy + SQLite, com `PRAGMA foreign_keys=ON`. IDs simples inteiros, salvo chaves compostas indicadas. JSON guarda rubricas, respostas e snapshots; não há arquivos pessoais desnecessários. Campos temporais têm contrato UTC, inclusive no roundtrip SQLite.

| Tabela | Campos e vínculos principais |
|---|---|
| students | id, name, created_at |
| subjects | id, name único |
| concepts | id, subject_id, slug, name, description, difficulty, importance, estimated_minutes, created_at; subject+slug único |
| concept_dependencies | id, concept_id, prerequisite_concept_id, dependency_strength, is_essential; par único |
| assessments | id, subject_id, name, start_date, end_date, importance; subject+name+start_date único |
| assessment_concepts | **PK assessment_id+concept_id**, weight (0,1] |
| student_concept_states | **PK student_id+concept_id**; mastery nullable, retention, retention_calculated_at, self_confidence nullable, evidence_confidence, evidence_count, delayed_evidence_count, independent_correct, stability_days, times_seen/attempted/correct, last_seen/attempt/correct/independent_at, difficulty_success_rate, difficulty_attempt_weight, next_review_at, status |
| study_sessions | id, student_id, available_minutes, planned_minutes, created_at, completed_at, status, plan_snapshot |
| session_activities | id, session_id, position, concept_id nullable, exercise_id nullable, activity_type, estimated_minutes, instructions, completed_at; session+position único |
| exercises | id, concept_id, slug único, exercise_type, prompt, options, answer_spec, explanation, difficulty, error_map |
| exercise_attempts | id, student_id, exercise_id, activity_id nullable, attempt_kind, answer, correct, score, error_type, concepts_involved, evaluator_confidence, feedback, hints_used, attempt_number, response_time (segundos), self_confidence, is_independent, occurred_at; student+exercise+attempt_number único |
| review_schedules | id, student_id, concept_id, stage, due_at, updated_at; student+concept único |
| learning_events | id, student_id, concept_id nullable, attempt_id nullable/único, event_type, payload, occurred_at |

## Integridade e limites

- Intervalos, forças, pesos, tempos e datas têm restrições de banco e/ou validação Pydantic.
- Ciclos e referências inexistentes são rejeitados pelo Curriculum/KnowledgeGraph antes de gravar a aresta.
- Uma revisão corrente por aluno/conceito; histórico de decisões em LearningEvent.
- Um registro por tentativa, inclusive retries. Nunca sobrescrever uma resposta antiga com o acerto posterior.
- `LearningService` exige transação do chamador. Atualiza tentativa, estado, revisão e evento atomicamente. Conflitos de numeração em chamadas concorrentes geram erro de unicidade; interface concorrente/idempotência de requisição fica para a API de execução no próximo marco.
- `next_review_at` e `retention` são snapshots auxiliares. O scheduler sincroniza o primeiro com ReviewSchedule; leituras recalculam retenção no instante solicitado.
- Um plano salvo não prova execução. O marco atual permite gerar e persistir planos e registrar evidência pelos serviços Python; não oferece endpoints de execução interativa.
- Datas de avaliação não são timestamps UTC: representam dias de calendário no fuso configurado. O relógio UTC é convertido para esse fuso ao calcular urgência.
- Inicialização usa `create_all`, sem modificar tabelas existentes. Mudanças futuras exigirão migrations e estratégia de backup antes de atualizar bancos com progresso.
