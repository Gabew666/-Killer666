# ATLAS — instruções permanentes

1. Não over-engineer. Escolha soluções simples e documente ambiguidades.
2. Não introduza dependências sem necessidade.
3. Toda mudança no algoritmo adaptativo precisa de teste.
4. Lógica pedagógica crítica fica no backend.
5. O frontend não decide prioridade pedagógica.
6. Não introduza LLM como dependência estrutural do planner.
7. Mantenha componentes desacoplados.
8. Prefira código legível a abstrações excessivas.
9. Ao alterar arquitetura, atualize `docs/`.
10. Antes de concluir uma tarefa, execute os testes pertinentes.
11. Nunca apague testes para fazer build passar.
12. Não envie dados do aluno a serviços externos sem configuração explícita.
13. Use o checkout existente: cada tarefa cloud já é isolada. Não crie worktrees sem pedido explícito.

Validação da Fase 1: `cd backend && .venv/bin/python -m pytest`.
Exemplos reproduzíveis: `cd backend && .venv/bin/python -m app.examples`.
