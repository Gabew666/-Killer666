# Banco diagnóstico ATLAS v0.1.0

Questões autorais, não oficiais da instituição nem da prova. O JSON versionado está em `backend/content/diagnostics/ia_simbolica_v0.1.json`. Nenhum Assessment ou peso foi criado; currículo institucional permanece DRAFT, com 9 unidades, 40 conceitos e 32 dependências.

| Conceito | Questões | Habilidades |
| --- | ---: | --- |
| fundamentos-ia-simbolica | 2 | abordagem simbólica; justificativa por regras |
| formulacao-de-problemas-ia | 2 | elementos da formulação; teste de objetivo |
| espaco-de-estados | 2 | significado do estado; contagem de configurações |
| logica-proposicional | 2 | conjunção; avaliação de expressão |
| logica-de-predicados | 2 | predicados/quantificadores; tradução universal |
| bfs | 2 | fila e níveis; ordem de expansão |
| dfs | 2 | aprofundamento; ordem de expansão |
| busca-heuristica | 2 | estimativa restante; distância Manhattan |
| a-star | 2 | composição de f; seleção na fronteira |
| representacao-de-conhecimento | 2 | finalidade; formalização de fato/regra |
| inferencia-logica | 2 | derivação; encadeamento de regras |
| agentes-inteligentes | 2 | ciclo do agente; percepção versus ação |
| redes-semanticas | 2 | estrutura relacional; transitividade explicitada |
| frames | 2 | slots; substituição de padrão |

Total: 28. Tipos: 22 MULTIPLE_CHOICE, 3 NUMERIC, 2 TRUE_FALSE e 1 SHORT_EXACT. Dificuldades estimadas: 0,4 e 0,6 por conceito. Proveniência derivada automaticamente do conceito pelo serviço; autoria ATLAS e versão diagnóstica registradas separadamente.

## Validação executada neste marco

- Base antes das alterações: 119 testes backend aprovados.
- Final: `cd backend && .venv/bin/python -m pytest -q`: 128 aprovados, zero falhos. Um aviso de depreciação de Starlette/AnyIO.
- `cd frontend && npm test`: 4 aprovados, zero falhos.
- `cd frontend && npm run build`: concluído, compilação e TypeScript válidos.
- Integração SQLite vazio: contagens institucionais, 28 exercícios autorais, nenhum provisional, reinicialização sem duplicação, progresso/revisão preservados, POST start 201, acerto independente seguido de segunda questão do mesmo conceito e duas evidências após os dois acertos. API sem gabaritos.
- Pacotes inválidos e conflito em último item: rollback, nenhuma inserção parcial. Recarga idêntica: 28 UNCHANGED.
- Smoke HTTP usando o cliente real `frontend/src/lib/api.ts` contra FastAPI em SQLite temporário: dashboard (subjects/state) → start 20 → questão de formulação → resposta errada → feedback → INSERT_GUIDED_PRACTICE → EXPLANATION, saldo 20 → 16. Sessão encerrada pelo cliente. Não foi um teste visual em navegador; nenhum componente visual foi alterado.

Limites: duas questões por conceito dão cobertura inicial, não um banco ilimitado para confirmações inéditas; dificuldades ainda precisam de calibração com alunos. Sem deploy neste marco.
