"""Conteúdo editorial provisório; não presume a ementa da instituição."""

# slug, nome, explicação curta, pré-requisitos, dificuldade, importância
CONCEPTS = [
    ("fundamentos", "Fundamentos de IA simbólica", "IA simbólica representa conhecimento explicitamente por símbolos e regras, permitindo raciocínio sobre representações.", [], .2, .8),
    ("simbolica-conexionista", "IA simbólica vs IA conexionista", "Abordagens simbólicas usam representações e regras explícitas; conexionistas aprendem parâmetros em redes. Sistemas híbridos podem combinar ambas.", ["fundamentos"], .3, .7),
    ("representacao", "Símbolos e representação do conhecimento", "Um símbolo representa uma entidade ou relação dentro de uma interpretação. Sintaxe organiza expressões; semântica lhes dá significado.", ["fundamentos"], .3, .8),
    ("proposicoes", "Proposições", "Uma proposição é uma declaração que, em lógica clássica, pode ser verdadeira ou falsa. Perguntas e ordens não são proposições.", [], .2, .9),
    ("operadores", "Operadores lógicos: AND, OR, NOT", "AND exige ambos os operandos verdadeiros; OR inclusivo exige ao menos um; NOT inverte o valor lógico.", ["proposicoes"], .3, .9),
    ("implicacao", "Implicação", "p → q é falsa somente quando p é verdadeira e q é falsa; equivale a ¬p ∨ q.", ["operadores"], .4, .9),
    ("tabela-verdade", "Tabela verdade", "Uma tabela enumera todas as atribuições de valores. Para n proposições independentes, existem 2^n linhas de valores de entrada.", ["operadores"], .4, .9),
    ("equivalencia", "Equivalência lógica", "Duas fórmulas são equivalentes quando têm os mesmos valores em todas as interpretações. Por De Morgan, ¬(p ∧ q) equivale a ¬p ∨ ¬q.", ["tabela-verdade", "implicacao"], .5, .8),
    ("cnf", "CNF — forma normal conjuntiva", "CNF é uma conjunção de cláusulas, cada uma uma disjunção de literais. Exemplo: (p ∨ q) ∧ (¬p ∨ r).", ["equivalencia"], .6, .9),
    ("dnf", "DNF — forma normal disjuntiva", "DNF é uma disjunção de termos, cada um uma conjunção de literais. Exemplo: (p ∧ q) ∨ (¬p ∧ r).", ["equivalencia"], .6, .7),
    ("regras", "Regras de produção", "Uma regra SE condições ENTÃO conclusão permite derivar conhecimento quando as condições são satisfeitas.", ["representacao", "implicacao"], .4, .9),
    ("fatos", "Fatos e base de conhecimento", "Fatos são afirmações disponíveis ao sistema. A base de conhecimento reúne fatos e regras; o mecanismo de inferência opera sobre ela.", ["representacao"], .3, .9),
    ("inferencia", "Inferência", "Inferência deriva conclusões a partir de premissas e regras. Modus ponens: de p e p → q, conclui-se q.", ["regras", "fatos"], .5, .9),
    ("frente", "Encadeamento para frente", "Parte dos fatos disponíveis, dispara regras aplicáveis e acrescenta conclusões até chegar a um objetivo ou esgotar novas inferências.", ["inferencia"], .5, .9),
    ("tras", "Encadeamento para trás", "Parte de um objetivo e procura regras que o concluam; suas condições tornam-se subobjetivos a verificar.", ["inferencia"], .5, .9),
    ("estados", "Espaço de estados", "Um problema de busca contém estado inicial, ações/transições e teste de objetivo. Um caminho é uma sequência de transições.", [], .3, .9),
    ("arvores", "Árvores", "Uma árvore enraizada organiza nós em relações pai-filho. Cada nó diferente da raiz tem um pai e há um caminho único desde a raiz.", ["estados"], .3, .7),
    ("grafos", "Grafos", "Grafos possuem vértices e arestas. Podem representar estados e transições; diferente de árvores, podem conter ciclos e múltiplos caminhos.", ["estados"], .4, .9),
    ("bfs", "Busca em largura — BFS", "BFS expande por profundidade crescente usando fila FIFO. Encontra caminho com menos arestas; custo mínimo exige custos uniformes.", ["grafos", "arvores"], .5, .8),
    ("dfs", "Busca em profundidade — DFS", "DFS aprofunda um ramo antes de retroceder, usando pilha ou recursão. Não garante caminho mais curto; controle de visitados evita ciclos.", ["grafos", "arvores"], .5, .7),
    ("informada", "Busca informada", "Usa conhecimento adicional, geralmente uma heurística, para ordenar estados candidatos e orientar a busca.", ["grafos"], .5, .8),
    ("heuristica", "Função heurística", "h(n) estima o custo de n até um objetivo. É uma estimativa do que falta, diferente do custo já percorrido g(n).", ["grafos", "informada"], .6, 1.0),
    ("gulosa", "Busca gulosa / Best First", "Busca gulosa prioriza menor h(n), ignorando o custo acumulado g(n). Pode ser rápida, mas não garante solução ótima.", ["heuristica"], .6, .8),
    ("astar", "A*", "A* prioriza menor f(n)=g(n)+h(n). Em busca em grafo sem reabertura, consistência da heurística é uma condição usual para garantir otimalidade com custos não negativos.", ["grafos", "heuristica", "gn", "fn"], .8, 1.0),
    ("gn", "g(n) — custo de caminho", "g(n) é o custo acumulado do estado inicial até n. Soma os custos das arestas do caminho percorrido.", ["grafos"], .4, .9),
    ("hn", "h(n) — estimativa restante", "h(n) estima o custo restante de n ao objetivo. Em um objetivo, uma heurística usual não negativa admissível vale zero.", ["heuristica"], .5, .9),
    ("fn", "f(n) = g(n) + h(n)", "f(n) combina custo acumulado e estimativa restante. Com g(n)=4 e h(n)=6, f(n)=10.", ["gn", "hn"], .5, .9),
    ("admissivel", "Heurística admissível", "Uma heurística é admissível se nunca superestima o custo ótimo restante: h(n) ≤ h*(n).", ["heuristica", "gn"], .7, .9),
    ("consistente", "Heurística consistente", "Consistência exige h(n) ≤ c(n,n') + h(n') em cada aresta. Com h(objetivo)=0, implica admissibilidade em condições usuais.", ["admissivel"], .8, .8),
    ("especialistas", "Sistemas especialistas", "Sistemas especialistas aplicam conhecimento de um domínio, tipicamente fatos/regras e motor de inferência, para apoiar decisões e explicar conclusões.", ["frente", "tras"], .6, .9),
]


def mc(slug, prompt, options, correct_index, explanation, *, difficulty=.5, errors=None):
    return dict(slug=slug, exercise_type="MULTIPLE_CHOICE", prompt=prompt, options=options,
                answer_spec={"correct_index": correct_index}, explanation=explanation,
                difficulty=difficulty, error_map=errors or {})


def question(slug, kind, prompt, spec, explanation, difficulty=.5):
    return dict(slug=slug, exercise_type=kind, prompt=prompt, options=None,
                answer_spec=spec, explanation=explanation, difficulty=difficulty, error_map={})


EXERCISES = {
    "fundamentos": [mc("fundamentos-1", "Qual é uma característica central de IA simbólica?", ["Somente ajustar pesos de neurônios", "Manipular símbolos e regras explícitas", "Dispensar representação"], 1, "Representações explícitas e regras permitem derivar conclusões.", difficulty=.2)],
    "simbolica-conexionista": [question("comparacao-1", "TRUE_FALSE", "Uma abordagem híbrida pode combinar regras simbólicas e redes neurais.", {"value": True}, "As abordagens não são mutuamente exclusivas.", .3)],
    "representacao": [mc("representacao-1", "O que dá significado aos símbolos de uma linguagem formal?", ["Somente sua ordem alfabética", "A quantidade de símbolos", "Uma interpretação semântica"], 2, "A semântica relaciona símbolos aos objetos e relações representados.", difficulty=.3)],
    "proposicoes": [mc("proposicoes-1", "Qual alternativa é uma proposição?", ["Feche a porta!", "Dois é um número par.", "Qual é seu nome?"], 1, "A declaração pode receber valor verdadeiro ou falso.", difficulty=.2)],
    "operadores": [question("operadores-1", "STRUCTURED", "Para p=verdadeiro e q=falso, informe and, or e not_p como booleanos.", {"fields": {"and": {"type": "TRUE_FALSE", "value": False}, "or": {"type": "TRUE_FALSE", "value": True}, "not_p": {"type": "TRUE_FALSE", "value": False}}}, "V AND F = F; V OR F = V; NOT V = F.", .3)],
    "implicacao": [mc("implicacao-1", "Quando p → q é falsa?", ["p falsa e q verdadeira", "p verdadeira e q falsa", "p e q falsas"], 1, "A implicação só falha quando a condição é verdadeira e a conclusão é falsa.", difficulty=.4)],
    "tabela-verdade": [question("tabela-1", "NUMERIC", "Quantas linhas de entrada há em uma tabela verdade com 3 proposições independentes?", {"value": 8, "tolerance": 0}, "São 2³ = 8 combinações.", .4)],
    "equivalencia": [mc("equivalencia-1", "Qual fórmula equivale a ¬(p ∧ q)?", ["¬p ∧ ¬q", "p ∨ q", "¬p ∨ ¬q"], 2, "A lei de De Morgan troca AND por OR e nega cada termo.", difficulty=.5)],
    "cnf": [mc("cnf-1", "Qual expressão está em CNF?", ["(p ∧ q) ∨ (r ∧ s)", "(p ∨ q) ∧ (¬p ∨ r)", "¬(p ∧ q)"], 1, "CNF é uma conjunção de disjunções de literais.", difficulty=.6)],
    "dnf": [mc("dnf-1", "Qual expressão está em DNF?", ["(p ∧ q) ∨ (¬p ∧ r)", "(p ∨ q) ∧ (r ∨ s)", "¬(p ∨ q)"], 0, "DNF é uma disjunção de conjunções de literais.", difficulty=.6)],
    "regras": [mc("regras-1", "A regra SE febre E tosse ENTÃO investigar pode disparar quando:", ["Só febre está estabelecida", "Só tosse está estabelecida", "Febre e tosse estão estabelecidas"], 2, "Todas as condições da conjunção devem ser satisfeitas.", difficulty=.4)],
    "fatos": [question("fatos-1", "TRUE_FALSE", "Uma base de conhecimento pode conter fatos e regras.", {"value": True}, "O motor de inferência usa fatos e regras da base.", .3)],
    "inferencia": [question("inferencia-1", "SHORT_EXACT", "Dadas p e p → q, qual proposição se conclui por modus ponens? Responda com a letra.", {"accepted": ["q"]}, "De p e p → q deriva-se q.", .5)],
    "frente": [mc("frente-1", "De onde parte o encadeamento para frente?", ["Dos fatos disponíveis", "Apenas da conclusão desejada", "De pesos sinápticos"], 0, "É dirigido pelos dados: fatos ativam regras e geram novos fatos.", difficulty=.5)],
    "tras": [mc("tras-1", "O encadeamento para trás transforma condições de uma regra em:", ["Pesos de rede", "Subobjetivos a verificar", "Fatos automaticamente verdadeiros"], 1, "Parte-se do objetivo e investigam-se condições suficientes para concluí-lo.", difficulty=.5)],
    "estados": [mc("estados-1", "Quais elementos definem um problema básico de busca?", ["Apenas uma lista de respostas", "Só custo e memória", "Estado inicial, ações e teste de objetivo"], 2, "As ações conectam estados até algum objetivo.", difficulty=.3)],
    "arvores": [question("arvores-1", "NUMERIC", "Em uma árvore enraizada, quantos pais tem um nó diferente da raiz?", {"value": 1, "tolerance": 0}, "Cada nó não raiz tem exatamente um pai.", .3)],
    "grafos": [question("grafos-1", "TRUE_FALSE", "Um grafo pode conter ciclos e mais de um caminho entre dois vértices.", {"value": True}, "Essas possibilidades distinguem grafos gerais de árvores.", .4)],
    "bfs": [question("bfs-1", "SHORT_EXACT", "Qual estrutura de dados organiza a fronteira de BFS? Use o nome ou a sigla de sua ordem.", {"accepted": ["fila", "FIFO", "fila FIFO"]}, "BFS usa uma fila FIFO para expandir por níveis.", .5), question("bfs-2", "TRUE_FALSE", "BFS garante o menor custo quando as arestas têm custos diferentes.", {"value": False}, "BFS minimiza número de arestas, não custo arbitrário.", .7)],
    "dfs": [question("dfs-1", "SHORT_EXACT", "Qual estrutura LIFO pode implementar a fronteira de DFS?", {"accepted": ["pilha", "stack"]}, "Uma pilha leva a busca a aprofundar antes de retroceder.", .5)],
    "informada": [mc("informada-1", "O que distingue uma busca informada?", ["Nunca usa grafos", "Usa estimativa adicional para orientar a busca", "Sempre examina todos os estados"], 1, "A heurística adiciona uma estimativa útil para ordenar a fronteira.", difficulty=.5)],
    "heuristica": [mc("heuristica-1", "O que uma função heurística h(n) estima?", ["O custo já percorrido", "O custo restante até um objetivo", "A quantidade exata de nós visitados"], 1, "h estima o que falta; g registra o custo já percorrido.", difficulty=.6, errors={"0": {"error_type": "CONCEPTUAL", "concept_slugs": ["gn", "heuristica"]}}), mc("heuristica-2", "A distância em linha reta ao destino pode servir como:", ["Estimativa inferior da distância de uma rota em estradas", "Custo já percorrido até a posição atual", "Garantia de que todas as rotas são iguais"], 0, "Sob distâncias usuais, uma rota não pode ser mais curta que a linha reta entre seus extremos.", difficulty=.7)],
    "gulosa": [question("gulosa-1", "SHORT_EXACT", "Busca gulosa prioriza o menor valor de g(n), h(n) ou f(n)?", {"accepted": ["h(n)", "h"]}, "Busca gulosa usa só a heurística h(n).")] ,
    "astar": [mc("astar-1", "Em A*, o que representa h(n)?", ["Custo já percorrido", "Estimativa do custo restante", "Soma de todos os caminhos"], 1, "g(n) é o custo percorrido; h(n) estima o restante; f(n) soma ambos.", difficulty=.6, errors={"0": {"error_type": "CONCEPTUAL", "concept_slugs": ["heuristica", "gn"]}}), question("astar-2", "STRUCTURED", "A tem g=3,h=6; B tem g=5,h=2. Informe f_a, f_b e escolhido ('A' ou 'B').", {"fields": {"f_a": {"type": "NUMERIC", "value": 9}, "f_b": {"type": "NUMERIC", "value": 7}, "escolhido": {"type": "SHORT_EXACT", "accepted": ["B"]}}}, "f(A)=9; f(B)=7. A* prioriza B, de menor f.", .8)],
    "gn": [question("gn-1", "NUMERIC", "Um caminho percorre arestas de custo 2, 3 e 4. Qual é g(n) no último nó?", {"value": 9, "tolerance": 0}, "O custo acumulado é 2+3+4=9.", .4)],
    "hn": [question("hn-1", "NUMERIC", "No objetivo, qual valor deve ter uma heurística não negativa admissível?", {"value": 0, "tolerance": 0}, "O custo restante ótimo é zero, então 0 ≤ h ≤ 0.", .5)],
    "fn": [question("fn-1", "NUMERIC", "Se g(n)=4 e h(n)=6, quanto vale f(n)?", {"value": 10, "tolerance": 0}, "f(n)=g(n)+h(n)=10.", .5)],
    "admissivel": [question("admissivel-1", "TRUE_FALSE", "Uma heurística admissível pode superestimar o custo ótimo restante.", {"value": False}, "Admissibilidade exige h(n) ≤ h*(n).", .7)],
    "consistente": [question("consistente-1", "TRUE_FALSE", "Uma aresta com custo 2, h(n)=7 e h(n')=3 respeita consistência?", {"value": False}, "Exigiria 7 ≤ 2+3; a desigualdade é falsa.", .8)],
    "especialistas": [mc("especialistas-1", "Qual componente aplica regras aos fatos de um sistema especialista?", ["Somente a interface", "Uma tabela de cores", "O motor de inferência"], 2, "O motor de inferência deriva conclusões a partir da base de conhecimento.", difficulty=.6)],
}

# Escopo inicial exemplificativo; precisa ser conferido com os materiais reais.
ASSESSMENT_SCOPE = {"astar": 1.0, "heuristica": .9, "bfs": .4, "cnf": .8,
                    "frente": .8, "tras": .8, "especialistas": .7}
