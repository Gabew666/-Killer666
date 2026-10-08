# Grafo de conhecimento

Arestas: **pré-requisito → conceito dependente**. Força em (0,1], sem ciclos, auto-dependências ou duplicações. NetworkX valida antes do commit.

Soft gating é padrão; `is_essential` precisa ser marcado explicitamente para permitir hard gate crítico. O seed não presume nenhum hard gate. O planner pode revisar a base e introduzir o dependente na mesma sessão, sem fingir que a revisão já aumentou mastery.

Exemplos: proposições → operadores → implicação/tabela verdade → equivalência → CNF/DNF; representação → fatos/regras → inferência → encadeamento; espaço de estados → grafos/árvores → busca; grafos + g(n) + heurística + f(n) → A*.

f(n) pode ser definido antes de estudar o algoritmo A*, evitando ciclo artificial. Dependências entre disciplinas são permitidas. Urgência de prova pode se propagar aos ancestrais, com desconto e origem rastreável. O grafo seed de 30 conceitos não pretende representar toda a ementa oficial.
