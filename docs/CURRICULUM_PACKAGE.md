# Curriculum Package v0.1

Um pacote JSON declara `package_id` estável, `version` no formato `major.minor.patch`, `content_status` (`DEMONSTRATION`, `DRAFT` ou `VALIDATED`) e os itens de uma disciplina. O [arquivo de exemplo](../examples/curriculum_package.example.json) é inteiramente fictício e **não representa currículo institucional**. O seed provisório de IA Simbólica permanece como está até a chegada de currículo validado. Não há ingestão de PDF, LLM ou publicação automática.

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

Em SQLite v0.1, a inicialização cria as quatro tabelas novas e adiciona três colunas opcionais em `concepts`. Ainda não existem migrations versionadas; faça backup antes de aplicar em banco com progresso real. Concorrência de importadores e PostgreSQL exigem validação adicional.
