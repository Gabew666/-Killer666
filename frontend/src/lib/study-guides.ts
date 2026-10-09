export type StudyGuide = {
  concept: string;
  title: string;
  source: string;
  summary: string;
  why: string;
  keyPoints: string[];
  example: { title: string; steps: string[]; takeaway: string };
  mistakes: string[];
  quickCheck: string;
};

export const STUDY_GUIDES: Record<string, StudyGuide> = {
  "Fundamentos da IA simbólica": {
    concept: "Fundamentos da IA simbólica",
    title: "Fundamentos da IA Simbólica",
    source: "Livro Digital · Temas 1 e 3",
    summary: "Na IA simbólica, o conhecimento é representado explicitamente por símbolos e manipulado por regras lógicas. Fatos, relações e regras formam uma estrutura que o sistema pode usar para raciocinar e justificar conclusões.",
    why: "É a base da disciplina: busca, redes semânticas, frames e inferência dependem da ideia de representar conhecimento de forma explícita.",
    keyPoints: [
      "Símbolos podem representar conceitos, objetos, relações, constantes, variáveis e funções.",
      "Regras lógicas transformam fatos conhecidos em novas conclusões.",
      "O caminho entre fatos, regras e conclusão pode ser explicado.",
      "Lógica formal é uma das bases do paradigma simbólico.",
    ],
    example: { title: "Regra explícita", steps: ["Fato: PedidoPago.", "Fato: HaEstoque.", "Regra: PedidoPago ∧ HaEstoque → AutorizarEnvio.", "As duas condições são verdadeiras, então deriva-se AutorizarEnvio."], takeaway: "A conclusão pode ser rastreada até fatos e regras explícitos." },
    mistakes: ["Achar que IA simbólica apenas memoriza respostas.", "Pensar que símbolo significa somente uma letra."],
    quickCheck: "Você consegue apontar os fatos, a regra aplicada e a conclusão?",
  },
  "Formulação de problemas em IA": {
    concept: "Formulação de problemas em IA",
    title: "Formulação de problemas em IA",
    source: "Livro Digital · Tema 2",
    summary: "Formular um problema significa transformar uma situação em uma estrutura que a IA possa explorar: estado inicial, ações, transições, objetivo e, quando necessário, custos.",
    why: "Um algoritmo de busca depende da modelagem. Se estados ou objetivos estiverem mal definidos, a busca pode explorar coisas irrelevantes ou nem reconhecer a solução.",
    keyPoints: ["Estado inicial: onde o problema começa.", "Ações: o que pode ser feito.", "Transição: como uma ação altera o estado.", "Teste de objetivo: como reconhecer a solução.", "Custo: como comparar caminhos quando necessário."],
    example: { title: "Robô levando uma caixa", steps: ["Inicial: robô e caixa na sala A.", "Ações: mover, pegar, soltar.", "Transições atualizam posições.", "Objetivo: caixa na sala B."], takeaway: "Primeiro modele o problema; depois escolha o algoritmo." },
    mistakes: ["Definir o objetivo como uma ação intermediária.", "Guardar detalhes que não mudam nenhuma decisão."],
    quickCheck: "Você consegue dizer onde começa, o que pode fazer e como sabe que terminou?",
  },
  "Espaço de estados": {
    concept: "Espaço de estados", title: "Espaço de estados", source: "Livro Digital · Temas 2 e 6",
    summary: "Um estado descreve uma configuração relevante do problema em determinado momento. O espaço de estados reúne as configurações possíveis e as transições entre elas.",
    why: "As buscas em IA percorrem estados. Entender essa representação prepara você para BFS, DFS, heurísticas e A*.",
    keyPoints: ["Estados guardam informações relevantes para decisões.", "Ações ligam estados por transições.", "Estados podem ser tuplas, listas ou outras estruturas.", "Combinar variáveis pode fazer o número de estados crescer rapidamente."],
    example: { title: "Aspirador em duas salas", steps: ["Posição: A ou B.", "Cada sala: limpa ou suja.", "O estado registra posição e condição das salas.", "Aspirar ou mover produz um novo estado."], takeaway: "Estado é uma fotografia lógica da situação usada para decidir a próxima ação." },
    mistakes: ["Confundir estado com ação.", "Guardar informação irrelevante e aumentar o espaço sem necessidade."],
    quickCheck: "Se duas configurações exigem decisões diferentes, elas provavelmente precisam ser estados diferentes.",
  },
  "Lógica proposicional": {
    concept: "Lógica proposicional", title: "Lógica proposicional", source: "Livro Digital · Tema 3",
    summary: "A lógica proposicional trabalha com proposições verdadeiras ou falsas e operadores que permitem combiná-las.",
    why: "Ela fornece uma linguagem formal para escrever regras e verificar consequências lógicas.",
    keyPoints: ["¬p nega p.", "p ∧ q exige ambos verdadeiros.", "p ∨ q exige pelo menos um verdadeiro.", "p → q representa 'se p, então q'.", "p ↔ q expressa equivalência."],
    example: { title: "Regra de acesso", steps: ["p: usuário autenticado.", "q: usuário possui permissão.", "Acesso exige p ∧ q.", "Se p=true e q=false, o acesso é falso."], takeaway: "O operador determina como os valores das proposições são combinados." },
    mistakes: ["Ler p → q como se q também implicasse p.", "Confundir conjunção e disjunção."],
    quickCheck: "Traduza cada símbolo para uma frase antes de calcular.",
  },
  "Lógica de predicados": {
    concept: "Lógica de predicados", title: "Lógica de predicados", source: "Livro Digital · Tema 3",
    summary: "A lógica de predicados amplia a lógica proposicional para representar objetos, propriedades, relações, variáveis, funções e quantificadores.",
    why: "Ela permite representar conhecimento mais rico, como relações entre pacientes, sintomas, objetos ou categorias.",
    keyPoints: ["Predicados representam propriedades ou relações.", "Constantes identificam objetos específicos.", "Variáveis podem assumir objetos do domínio.", "∀ significa 'para todo'.", "∃ significa 'existe'."],
    example: { title: "Todo sensor é dispositivo", steps: ["Use Sensor(x) e Dispositivo(x).", "A frase fala de todos os sensores.", "Forma: ∀x (Sensor(x) → Dispositivo(x))."], takeaway: "Quantificadores permitem falar formalmente sobre conjuntos de objetos." },
    mistakes: ["Trocar ∀ por ∃.", "Inverter uma implicação."],
    quickCheck: "Identifique objetos, propriedades/relações e só depois escolha o quantificador.",
  },
  "Busca em largura (BFS)": {
    concept: "Busca em largura (BFS)", title: "Busca em largura (BFS)", source: "Livro Digital · Tema 4",
    summary: "BFS explora o espaço de estados por níveis: primeiro os estados próximos da raiz, depois os níveis seguintes.",
    why: "É uma estratégia não informada central para entender como a organização da fronteira muda a ordem da busca.",
    keyPoints: ["Normalmente usa fila FIFO.", "Nós gerados primeiro são expandidos primeiro.", "Explora por profundidade crescente.", "Com passos de mesmo custo, encontra uma solução no menor número de passos."],
    example: { title: "Árvore simples", steps: ["R tem filhos A e B.", "A tem C; B tem D.", "A fila mantém a ordem por níveis.", "Expansão: R, A, B, C, D."], takeaway: "BFS termina um nível antes de aprofundar." },
    mistakes: ["Usar pilha e obter DFS.", "Confundir menor número de passos com menor custo quando custos variam."],
    quickCheck: "Todos os vizinhos aparecem antes dos netos? Isso é comportamento de BFS.",
  },
  "Busca em profundidade (DFS)": {
    concept: "Busca em profundidade (DFS)", title: "Busca em profundidade (DFS)", source: "Livro Digital · Tema 4",
    summary: "DFS segue um ramo o máximo possível antes de voltar para explorar alternativas.",
    why: "Contrasta diretamente com BFS e ajuda a entender como a fronteira controla a exploração.",
    keyPoints: ["Pode usar pilha ou recursão.", "Aprofunda um caminho antes de voltar.", "Pode usar menos memória que BFS em muitos cenários.", "A ordem dos sucessores influencia a trajetória."],
    example: { title: "Árvore simples", steps: ["R tem A e B.", "A tem C; B tem D.", "Escolhendo o filho esquerdo primeiro:", "Expansão: R, A, C, B, D."], takeaway: "DFS prioriza profundidade, não proximidade." },
    mistakes: ["Esperar sempre o caminho mais curto.", "Esquecer controle de visitados em grafos com ciclos."],
    quickCheck: "O algoritmo entra fundo em um ramo antes de voltar?",
  },
  "Busca heurística": {
    concept: "Busca heurística", title: "Busca heurística", source: "Livro Digital · Temas 4 e 9",
    summary: "Busca heurística usa informação adicional para estimar quais caminhos parecem mais promissores e reduzir exploração desnecessária.",
    why: "É a ponte entre busca não informada e algoritmos como Greedy e A*.",
    keyPoints: ["h(n) estima custo ou esforço restante.", "Heurística orienta; não é necessariamente o custo real.", "Uma boa estimativa pode reduzir o espaço explorado.", "As garantias dependem de como a heurística é usada."],
    example: { title: "Distância até o destino", steps: ["Você quer chegar a um ponto da cidade.", "Para cada posição, estime a distância restante.", "Use a estimativa para priorizar caminhos promissores."], takeaway: "h(n) olha para o que ainda falta, não para o custo já pago." },
    mistakes: ["Confundir h(n) com g(n).", "Tratar qualquer heurística como garantia de solução ótima."],
    quickCheck: "O valor mede o passado do caminho ou estima o que falta?",
  },
  "Algoritmo A*": {
    concept: "Algoritmo A*", title: "Algoritmo A*", source: "Livro Digital · Tema 4",
    summary: "A* combina custo já percorrido e estimativa do restante: f(n)=g(n)+h(n).",
    why: "Ele equilibra informação real do caminho e uma previsão do futuro, sendo um exemplo central de busca informada.",
    keyPoints: ["g(n): custo do início até n.", "h(n): estimativa de n até o objetivo.", "f(n)=g(n)+h(n).", "A fronteira prioriza menor f.", "Garantias dependem das propriedades da heurística e do problema."],
    example: { title: "Escolha entre X e Y", steps: ["X: g=2, h=6 → f=8.", "Y: g=5, h=1 → f=6.", "A* prioriza Y."], takeaway: "A* combina custo acumulado e estimativa restante." },
    mistakes: ["Usar apenas h(n) e obter comportamento guloso.", "Confundir custo já percorrido com estimativa."],
    quickCheck: "Escreva g, h e f separadamente antes de escolher.",
  },
  "Representação de conhecimento": {
    concept: "Representação de conhecimento", title: "Representação do conhecimento", source: "Livro Digital · Temas 3 e 5",
    summary: "Representar conhecimento é organizar conceitos, objetos, relações, fatos e regras em estruturas manipuláveis pelo sistema.",
    why: "Sem uma representação adequada, o sistema não consegue usar informação de forma estruturada para inferir, explicar ou decidir.",
    keyPoints: ["Variáveis assumem valores.", "Constantes representam valores ou objetos fixos.", "Relações conectam conceitos.", "Funções mapeiam entradas para valores.", "A representação deve permitir as inferências necessárias."],
    example: { title: "Permissão explícita", steps: ["Fato: Tecnica(Lia).", "Regra: Tecnica(x) → PodeInspecionar(x).", "Conclusão: PodeInspecionar(Lia)."], takeaway: "A estrutura transforma informação armazenada em algo utilizável pelo raciocínio." },
    mistakes: ["Guardar dados sem relações.", "Escolher estrutura que não suporta as inferências necessárias."],
    quickCheck: "O sistema consegue derivar algo novo ou apenas guardar informação?",
  },
  "Inferência lógica": {
    concept: "Inferência lógica", title: "Inferência lógica", source: "Livro Digital · Tema 5",
    summary: "Inferência é o processo de derivar novas conclusões a partir de fatos e regras representados.",
    why: "É quando a base de conhecimento deixa de ser apenas armazenamento e passa a produzir conclusões justificáveis.",
    keyPoints: ["Premissas são fatos disponíveis.", "Regras conectam premissas a conclusões.", "Conclusões intermediárias podem alimentar novas regras.", "A conclusão precisa ser sustentada pelas premissas e regras."],
    example: { title: "Cadeia de regras", steps: ["Fato: TemperaturaAlta.", "Regra 1: TemperaturaAlta → Alerta.", "Regra 2: Alerta → Verificar.", "Conclusão: Verificar."], takeaway: "Inferências podem ocorrer em várias etapas encadeadas." },
    mistakes: ["Tratar chute como inferência.", "Ignorar uma premissa necessária."],
    quickCheck: "Você consegue reconstruir o caminho completo da premissa à conclusão?",
  },
  "Agentes inteligentes": {
    concept: "Agentes inteligentes", title: "Agentes inteligentes", source: "Livro Digital · Tema 6",
    summary: "Um agente recebe percepções do ambiente, pode manter um estado interno e escolhe ações de acordo com essas informações.",
    why: "A ideia de agente conecta percepção, estado, representação e decisão em um ciclo de comportamento.",
    keyPoints: ["Percepções informam sobre o ambiente.", "A função de agente mapeia percepções/estados para ações.", "Estados internos resumem informações relevantes.", "Máquinas de estados finitos modelam estados e transições."],
    example: { title: "Aspirador simples", steps: ["Percepção: posição A, quadrado sujo.", "Regra: se está sujo, aspirar.", "Depois da ação, uma nova percepção atualiza o estado."], takeaway: "Perceber e agir são etapas diferentes do ciclo do agente." },
    mistakes: ["Confundir percepção com ação.", "Achar que todo agente exige um modelo interno complexo."],
    quickCheck: "Separe: o que percebe, o que sabe do estado e o que faz.",
  },
  "Redes semânticas": {
    concept: "Redes semânticas", title: "Redes semânticas", source: "Livro Digital · Temas 7 e 9",
    summary: "Redes semânticas organizam conhecimento como nós e relações. Nós representam entidades ou conceitos; arestas expressam relações entre eles.",
    why: "Elas tornam conexões explícitas e permitem navegar pelo conhecimento e apoiar inferências.",
    keyPoints: ["Nós representam conceitos ou entidades.", "Arestas representam relações.", "Rótulo e direção da relação importam.", "Hierarquias podem apoiar herança ou navegação."],
    example: { title: "Carro elétrico", steps: ["Nó central: Carro Elétrico.", "Conecte Sustentabilidade, Bateria e Veículos Ecológicos.", "Cada conceito pode se ligar a conceitos mais específicos."], takeaway: "O significado emerge também das relações entre os nós." },
    mistakes: ["Supor que toda relação é transitiva.", "Ignorar rótulo ou direção da aresta."],
    quickCheck: "Você consegue completar a frase: 'A relação de X com Y é...'?",
  },
  "Frames": {
    concept: "Frames", title: "Frames e sistemas baseados em conhecimento", source: "Livro Digital · Tema 8",
    summary: "Frames representam entidades ou situações em estruturas com slots. Slots guardam atributos, valores ou referências e podem ter facetas, valores-padrão, restrições e herança.",
    why: "Frames organizam conhecimento contextual e repetitivo de forma modular e permitem reutilizar propriedades.",
    keyPoints: ["O nome identifica o frame.", "Slots são campos de informação.", "Facetas adicionam padrões, condições ou restrições.", "Superframes fornecem propriedades herdáveis.", "Procedimentos associados podem calcular valores automaticamente."],
    example: { title: "Veículo e Carro", steps: ["Veículo define propriedades gerais.", "Carro herda slots de Veículo.", "Carro adiciona número de portas.", "Um valor específico pode substituir um padrão herdado."], takeaway: "Herança reduz redundância e organiza características gerais e específicas." },
    mistakes: ["Tratar frame como uma lista sem relações.", "Achar que valor-padrão nunca pode ser substituído."],
    quickCheck: "Identifique frame, slots, valores e relação de herança.",
  },
};

export const PRIORITY_CONCEPTS = Object.keys(STUDY_GUIDES);

export function guideFor(concept?: string | null): StudyGuide | null {
  return concept ? STUDY_GUIDES[concept] ?? null : null;
}
