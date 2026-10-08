# Modelo de aprendizagem — v0.1 / Fase 1

Modelo heurístico explicável, ainda não calibrado psicometricamente. Não equivale a nota ou probabilidade de aprovação.

## Cinco medidas distintas

- `mastery`: conhecimento estimado [0,1], nulo sem resposta independente; prior interno 0,35. Estado público `NOT_DIAGNOSED` enquanto for nulo, mesmo após exposição, prática assistida ou revisão vencida.
- `retention`: retenção calculada para o instante consultado. A persistência guarda também `retention_calculated_at`; leituras recalculam para evitar snapshot obsoleto.
- `self_confidence`: última confiança declarada pelo aluno, opcional; não prova domínio.
- `evidence_confidence`: confiança heurística na estimativa, não confundida com autoavaliação.
- `evidence_count`: evidências independentes sob regra operacional explícita, não total de respostas.

Mastery 0,85 com uma evidência tem baixa confiabilidade e ainda demanda diagnóstico. A API retorna as cinco medidas e uma indicação de evidência insuficiente. Nunca promover a MASTERED só por um acerto.

## Independência

Primeira resposta sem dicas a uma questão nova conta uma evidência. A mesma questão só pode contar novamente após 24 horas desde sua última tentativa **e** desde a última exposição ao conceito. Respostas próximas são RETRY, mesmo após recarregar a aplicação; contador vem do banco. DELAYED_RECALL sem dicas vale uma nova evidência. Acertos após dicas/retries são prática, não novas evidências independentes. Independência é uma aproximação: itens parecidos podem ser correlacionados.

## Fórmulas

Detalhes e constantes ficam em `MasteryConfig`, `ReviewConfig` e `PlannerConfig`.

`retention(t) = exp(-elapsed_days(last_seen_at, t) / stability_days)`.
Exposição recente restaura disponibilidade imediata, mas não aumenta estabilidade nem mastery. Recuperação tardia independente e correta aumenta estabilidade; erro independente a reduz.

Dificuldade: `d = 0.7 + 0.55 * difficulty`.
Dicas tornam a resposta prática assistida: ficam no histórico, sem nova evidência independente nem alteração de mastery. Não há fator de dica no alvo da evidência independente.
Espaçamento: `s = 0.65 + 0.35 * min(days_since_exposure / 3, 1)` (primeira exposição usa 0,65).
Alvo de acerto independente: `target = min(1, d * s)`.
Alpha: `0.28 * (0.8 + 0.2 * historical_independent_success_rate)`; recuperação tardia multiplica por 1,25.
Acerto independente: `mastery += alpha * max(0, target - mastery)`.
Erro independente: `mastery *= 1 - alpha * (1 + 0.25 * self_confidence)` (confiança omitida usa 0,5).
Prática não independente não altera mastery nem evidência; registra exposição e desempenho.

`evidence_confidence = (1 - exp(-evidence_count / 8)) * (0.8 + 0.2 * min(delayed_evidence_count / 3, 1))`.
Mesmo que mastery já seja 0,85, uma evidência imediata produz confiança ≈0,094. Evidência tardia também testa a estimativa ao longo do tempo. Confiança não significa alta habilidade: muitos erros também podem sustentar uma estimativa baixa.

Estabilidade inicial 1 dia. Acerto tardio: `max(stability * 1.8, elapsed_days * 1.5)`, limitado a 90 dias. Erro independente: `max(0.5, stability * 0.6)`. Repetições imediatas não aumentam estabilidade.

## Revisão

Intervalos: 1, 3, 7, 14, 30 dias. Primeira exposição/tentativa agenda +1 dia. Somente acerto independente de recuperação tardia, em revisão vencida, avança o estágio. Erro volta a +1 dia. Acerto antes do vencimento não empurra a revisão para a frente. Dicas/retries não avançam estágio. `next_review_at` é espelhado no estado na mesma transação.

## Planner explicável

Componentes ponderados (soma = score, sem promessa de faixa [0,1]):

| Componente | Peso default |
|---|---:|
| exam_urgency | 5,0 |
| knowledge_gap | 2,0 |
| review_urgency | 3,0 |
| importance | 1,0 |
| prerequisite_value | 1,5 |
| recent_errors | 2,0 |
| mastery_penalty | −2,0 |
| prerequisite_gap (soft gate) | −2,0 |

`exam_urgency = importance_da_prova * weight_do_conceito * 14/(14 + dias_até_início)`, zero após a janela. Ancestrais herdam máximo do boost de descendentes com fator `0.9 ** distância`; o retorno separa escopo direto e contribuição herdada. Não há boost por simples vínculo à disciplina.

Lacuna = `1 - mastery * retention`; desconhecido usa prior 0,35. Revisão = `min(2, 1 + overdue_days/7)` se vencida, senão zero. Valor de pré-requisito pondera importância e lacunas dos descendentes. Erros recentes = média de erros ponderados por `exp(-days/7)` das cinco tentativas mais recentes. Penalidade de domínio usa mastery × retenção × confiança da evidência quando mastery ≥0,8.

Lacuna de pré-requisito = média ponderada de `max(0, (0.6 - mastery_do_pré)/0.6)`; desconhecido usa prior. É uma penalidade, não proibição. A escolha de um alvo com base fraca injeta revisão de sua base antes de aprofundar. Sob prova próxima, o conjunto base+alvo pode superar estudar apenas conceitos isolados. Hard gate somente em arestas explicitamente essenciais com mastery <0,2 (ou desconhecido).

O retorno inclui componentes, sinais brutos, motivos, pré-requisitos frágeis, bloqueios e a ordem final de atividades. Ordem pedagógica e ranking bruto são distintos: revisão preparatória pode vir antes do conceito de maior score.

## Tempo e limites

Reserva 8% do orçamento, com arredondamento conservador; faixa 10–240 min. Blocos incluem recuperação, explicação curta, exercício, correção e síntese. Sessões ≥120 min incluem pausas. Conteúdo escasso pode produzir sessão menor. Geração não cria evidência nem presume aprendizagem.

Os cinco tipos determinísticos corrigem somente rubricas cadastradas. SHORT_EXACT não reconhece sinônimos não cadastrados; NUMERIC usa tolerância explícita; STRUCTURED exige os campos da rubrica. Diagnóstico por distrator é hipótese. Erro em A* pode sugerir investigar heurística, mas não reduz automaticamente o domínio dela. A cobertura seed e o escopo da avaliação são provisórios até receber material institucional.

O Session Builder usa o estado observado para montar blocos DIAGNOSTIC, LEARNING, REVIEW ou PRACTICE. DIAGNOSTIC não contém explicação antes da resposta e marca um ponto para decisão posterior; não traduz o prior interno em mastery público. LEARNING dá mais tempo a explicação e aplicação guiada; REVIEW enfatiza recuperação sem consulta; PRACTICE enfatiza exercício independente. Uma resposta assistida recente pode solicitar LEARNING em vez de PRACTICE, sem alterar mastery ou evidence_count. O plano gerado é uma previsão: a decisão posterior só pode usar uma tentativa efetivamente registrada.

## Decisão durante a sessão

`SessionDecisionEngine` recebe a tentativa já corrigida, o estado atualizado e `remaining_minutes`. Diagnóstico correto sem evidência suficiente propõe confirmação em questão distinta; erro propõe explicação curta, prática guiada e, se houver tempo/item novo, nova recuperação. Acerto com dica exige confirmação sem dica. Revisão tardia correta permite avançar; revisão errada recebe remediação. Erro em prática com pré-requisito observado fraco dirige a remediação à base. Quando faltam minutos, usa feedback e síntese previstos e mantém a revisão agendada. O runtime só insere decisões que cabem no saldo e registra por que pulou itens futuros.

Uma prática guiada repetindo a questão do erro é RETRY: o acerto ajuda o aluno, mas não vira nova evidência independente. Uma questão distinta posterior pode criar evidência. Nenhuma atividade pulada aumenta `used_minutes` nem `actual_minutes`; o tempo real informado e a estimativa usada como fallback permanecem separados.
