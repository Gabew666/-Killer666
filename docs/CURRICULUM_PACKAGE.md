# Curriculum Package v0.1

Um pacote JSON declara `package_id` estável, `version` no formato `major.minor.patch`, `content_status` (`DEMONSTRATION`, `DRAFT` ou `VALIDATED`) e os itens de uma disciplina. O [arquivo de exemplo](../examples/curriculum_package.example.json) é inteiramente fictício e **não representa currículo institucional**. O [pacote institucional de IA Simbólica](../curricula/uniasselvi/inteligencia_artificial_simbolica_2026-2.v0.1.0.json) está em `DRAFT`; o aplicativo o carrega apenas com `ATLAS_CONTENT_MODE=real` em banco separado. O seed provisório permanece disponível apenas no modo `provisional`. Não há ingestão de PDF, LLM ou publicação automática.

`subject` tem `key` e `name`. `units` têm chave, nome, descrição e posição. `concepts` têm chave estável, `unit_key`, `parent_key` opcional para subconceitos, descrição, importância e dificuldade de 0 a 1, minutos estimados e objetivos de aprendizagem. `dependencies` ligam `concept_key` a `prerequisite_key`, força de 0 a 1 e `is_essential` (default falso). `assessments` têm janela de datas, importância e `coverage` explícita com peso por conceito. `exercises` têm conceito, um dos cinco tipos determinísticos, enunciado, opções quando aplicável, `answer_spec`, explicação de correção, dificuldade e mapa de erros opcional. `explanations` são textos de ensino associados a conceito.

Cada item aceita `provenance` com `source_id`, `source_name`, `source_type`, `source_reference` e `source_page` opcional. Para conteúdo institucional, preencha esses campos em cada item; a camada apenas registra a referência, sem armazenar documentos. O pacote completo fica em snapshot imutável e a proveniência corrente de cada item também é indexada. Nunca inclua dados pessoais do aluno no pacote.

Na pasta `backend`, valide antes de importar:

```sh
.venv/bin/python -m app.services.curriculum validate ../examples/curriculum_package.example.json
.venv/bin/python -m app.services.curriculum import ../examples/curriculum_package.example.json --database-url sqlite:////tmp/atlas-curriculum-demo.db
```

O primeiro comando não abre nem modifica o banco. O importador sempre executa a mesma validação integral antes de gravar. Rejeita chaves duplicadas, referências inexistentes, ciclos inclusive de subconceitos, rubricas inválidas e avaliações sem escopo válido. Conflitos com conteúdo existente fora do pacote também são rejeitados. Tudo é gravado em uma transação/savepoint; qualquer falha cancela a importação inteira. O cliente da biblioteca deve chamar `commit` depois de `CurriculumImporter().import_package(db, payload)`; o CLI o faz após sucesso.

Reimportar o mesmo `package_id`/`version` com JSON equivalente retorna `UNCHANGED` e não grava itens. Reusar a versão com conteúdo diferente é erro; uma nova versão precisa ser maior que todas as versões já importadas. Chaves estáveis identificam itens na atualização. O relatório fornece quantidades `created`, `updated` e `unchanged` por tipo. Versões anteriores ficam em `curriculum_package_records`; as tabelas de ensino guardam a versão mais recente de cada item. Itens omitidos em uma nova versão são **mantidos** em v0.1, para não quebrar histórico e sessões existentes; esta camada ainda não faz retirada de conteúdo. Planeje desativação explícita e migrations antes de usar omissões como remoção. A revisão de escopo de uma avaliação deve atualizar os pesos dos conceitos declarados; coberturas omitidas também permanecem pela mesma regra aditiva.

Currículo e estado do aluno são separados. O importador não lê nem escreve `student_concept_states`, `exercise_attempts`, `review_schedules` ou sessões. Uma atualização de conceito, questão ou explicação preserva mastery, retenção e evidências já acumuladas. Para uma mudança conceitual que invalide evidência anterior, será necessária uma política de migração pedagógica explícita em outro marco.

O pacote institucional real v0.1.0 tem 9 unidades, 40 conceitos e 32 dependências acíclicas, sem avaliações e sem exercícios. Seu status permanece DRAFT.

## Banco diagnóstico autoral

`backend/content/diagnostics/ia_simbolica_v0.1.json` é um pacote separado, `content_type=ATLAS_AUTHORED_DIAGNOSTIC`, versão `0.1.0`. Contém 28 questões: duas por cada uma das 14 chaves prioritárias. A primeira verifica compreensão (dificuldade 0,4); a segunda verifica aplicação ou uma faceta diferente (0,6). São questões autorais do ATLAS, não perguntas oficiais da instituição ou da prova. Nenhuma avaliação ou peso de prova é criado.

`DiagnosticPackage` valida cada questão com `ExerciseItem`; `validate_diagnostic_package` verifica chaves únicas, duas questões por alvo, tipos móveis determinísticos e rubricas. Proveniência manual é rejeitada. `register_atlas_diagnostic` deriva conceito, autoria ATLAS, pacote/versão institucional, fonte, referência e página; o carregador acrescenta a versão diagnóstica. A fonte institucional é a origem do conceito, não a autoria da questão.

No bootstrap real: currículo → pacote diagnóstico → aluno local, dentro da transação de inicialização. `load_diagnostic_package` retorna contagens `created`/`unchanged`. Chave e conteúdo idênticos retornam UNCHANGED; qualquer alteração de conteúdo/proveniência/versão da mesma chave falha claramente. Para publicar alteração, use nova versão e nova chave; itens anteriores, tentativas e progresso ficam preservados. Todo o pacote é validado antes da escrita; conflitos de banco fazem rollback de todos os registros do carregamento. Não há migrations novas neste marco.

O planner real exige pelo menos duas questões por alvo. Após primeiro acerto independente, o runtime pode inserir confirmação com outra questão do mesmo conceito, respeitando tempo restante. O gabarito fica apenas no banco; a API pública expõe enunciado e opções. A cobertura atual habilita o diagnóstico inicial, mas não é um banco ilimitado: se todas as questões inéditas forem usadas, o runtime só confirma quando existe outra disponível. A dificuldade é estimada, ainda sem calibração com alunos.
