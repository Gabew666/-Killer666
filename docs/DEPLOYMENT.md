# Preparação para hospedagem do ATLAS

Frontend e API são serviços separados; nenhum provedor é obrigatório. Este marco prepara os artefatos e valida persistência, sem publicar serviços. Python 3.12, Node.js 22.18+ e PostgreSQL 16 foram os alvos de validação.

## Configuração

Configure valores reais na plataforma de hospedagem/gerenciador de segredos, nunca em arquivos versionados. Os nomes abaixo são exemplos; os hosts reais e credenciais não pertencem ao Git.

| Serviço | Variável | Uso |
| --- | --- | --- |
| Backend | `ATLAS_CONTENT_MODE=real` | Currículo institucional DRAFT + diagnóstico autoral ATLAS |
| Backend | `ATLAS_DATABASE_URL` | PostgreSQL persistente, preferencialmente `postgresql+psycopg://…`; `postgresql://` e `postgres://` também aceitos |
| Backend | `ATLAS_SCHEMA_MODE=migrations` | Exige Alembic atualizado, sem `create_all`/ALTER na inicialização |
| Backend | `ATLAS_CORS_ORIGINS` | Origens exatas do frontend HTTPS, separadas por vírgula, sem caminho ou barra final; nunca `*` |
| Backend | `ATLAS_TIMEZONE=America/Sao_Paulo` | Apresentação e calendário; timestamps persistem UTC |
| Backend | `PORT` | Porta fornecida pela hospedagem; imagem usa 8000 se omitida |
| Frontend | `NEXT_PUBLIC_ATLAS_API_URL` | URL pública HTTPS da API, obrigatória **durante o build e no processo Next**, sem credenciais |

Para PostgreSQL remoto use TLS conforme o serviço, preferindo verificação de certificado/hostname (`sslmode=verify-full` e CA adequada). A URL é consumida apenas em runtime/Alembic, não copiada para a imagem. `NEXT_PUBLIC_*` é público no JavaScript do celular e nunca deve conter senha ou token. Mantenha a mesma URL configurada também no `npm start`; alterar a URL da API requer rebuild do frontend.

SQLite continua como padrão local de desenvolvimento/testes. `Settings.from_env` escolhe `migrations` por padrão para PostgreSQL e `auto` para SQLite; `auto` mantém a inicialização aditiva legada. Para produção use explicitamente `migrations`, mesmo se optar por SQLite com volume persistente. Uma aplicação sem a migration atual falha com instrução de executar Alembic.

## Migrations e bancos existentes

Antes de atualizar banco com progresso, faça backup e teste a restauração em banco separado. Pare instâncias que possam escrever durante a primeira adoção da baseline. Configure `ATLAS_DATABASE_URL` pelo ambiente e execute uma vez no job de release, antes de iniciar a API:

```sh
cd backend
python -m pip install -r requirements.txt
alembic upgrade head
alembic current
alembic check
```

A revisão `0001_baseline` congela o schema atual, incluindo índices, constraints e FKs. Não importa os modelos futuros dentro da revisão. Em banco vazio cria tabelas; em schema atual pré-Alembic adota tabelas existentes; em SQLite v0.1 com as lacunas aditivas conhecidas acrescenta campos opcionais sem reescrever linhas. Campos originais ausentes causam erro explícito. Não altera mastery, tentativas ou revisões. Schemas arbitrários e mudança de SQLite para PostgreSQL **não** são conversões automáticas: copiar dados requer migração planejada e verificada. Colunas legadas aditivas podem manter sua nulabilidade/default anteriores; divergências reportadas por `alembic check` precisam de revisão antes de uma migration futura.

Não use `alembic stamp head` para mascarar schema incompleto. A baseline recusa downgrade destrutivo; para rollback de dados use backup validado. Migrations futuras devem ser geradas (`alembic revision --autogenerate -m "…"`), revisadas e testadas em cópia do banco. A baseline necessita conexão online para inspecionar tabelas existentes; não suporta `upgrade --sql`.

Alembic cuida do schema; o bootstrap da aplicação cuida do conteúdo. No modo real, carrega 9 unidades, 40 conceitos, 32 dependências e 28 questões `ATLAS_AUTHORED_DIAGNOSTIC`, idempotentemente. Não cria avaliações nem pesos supostos. Não reutilize um banco provisório no modo real; a proteção contra mistura permanece ativa.

## Backend em container

O contexto de build deve ser a raiz do repositório para incluir o currículo institucional:

```sh
docker build -f backend/Dockerfile -t atlas-backend .
```

A imagem não inclui `.env`, banco local, frontend ou segredo. Se o ambiente de build utiliza proxy com CA própria, BuildKit aceita o secret opcional `build_ca` (`--secret id=build_ca,src=CAMINHO_DA_CA`); a CA é montada só durante pip e não entra na imagem. Mantenha verificação TLS habilitada. Executa como usuário sem privilégios, com um processo uvicorn; recebe `PORT`. Configure as variáveis anteriores no runtime. `ATLAS_DATABASE_URL` e `ATLAS_CORS_ORIGINS` são obrigatórias no comando de inicialização da imagem.

Execute `alembic upgrade head` usando a mesma imagem e configuração de banco em um job único de release. Depois inicie o comando padrão. Não execute migrations simultâneas em vários processos. Use PostgreSQL persistente fora da imagem e configure backups/restore no serviço de banco. Recriar a imagem ou container da API não pode recriar o banco. CORS não substitui controle de acesso.

`GET /health` verifica a conexão do banco, retorna 200 com `status=ok`, `database=ok` e `content_mode=real`. Falha de conexão retorna 503 sem expor host, URL ou SQL. A aplicação só entra em serviço depois de validar schema e importar conteúdo; configure health check HTTP nesse endpoint. A imagem já tem HEALTHCHECK usando a porta configurada.

## Frontend separado e celular

```sh
cd frontend
npm ci
npm test
# Configure NEXT_PUBLIC_ATLAS_API_URL na plataforma antes deste comando.
npm run build
npm start
```

O build de produção sem URL explícita falha; localhost permanece apenas como fallback de desenvolvimento. O CI compila com `https://api.example.com`, um placeholder público de validação que precisa ser substituído na hospedagem. Não é um endpoint publicado.

Use HTTPS nos dois serviços para acesso pelo celular e manifesto PWA. Configure a origem HTTPS exata do frontend no backend e verifique o preflight CORS. A API deve ser acessível pelo dispositivo; localhost no celular aponta para o próprio celular. O manifesto existente permanece; este marco não implementa offline nem altera telas.

## CI e integração PostgreSQL

`.github/workflows/ci.yml` executa pytest, npm ci/test/build em push/PR. O job backend inicia PostgreSQL 16 e fornece `ATLAS_TEST_POSTGRES_URL`. O teste cria um schema aleatório exclusivo, aplica Alembic e valida bootstrap/sessão/resposta/revisão/progresso após restart; remove somente o schema que criou. Não aponte essa variável para um banco de produção. A autenticação `trust` do serviço CI é apenas para a instância isolada de teste; produção precisa de autenticação e conexões restritas.

Para executar localmente contra PostgreSQL real, configure a URL de uma instância de teste e rode:

```sh
cd backend
python -m pytest -q
```

Sem `ATLAS_TEST_POSTGRES_URL`, a integração PostgreSQL é marcada SKIPPED explicitamente; os testes SQLite continuam executando. O teste PostgreSQL não usa banco em memória.

## Fluxo mínimo de aceitação

1. Migrar banco persistente vazio e iniciar API em `real`.
2. Confirmar health e contagens 9/40/32/28; nenhuma questão provisória.
3. Frontend consulta subjects/state, inicia sessão de 20 minutos, responde questão e recebe feedback/adaptação.
4. Conferir StudentConceptState, ExerciseAttempt, ReviewSchedule e StudySession no banco e API sem gabarito.
5. Reiniciar processo/container da API, consultar mesma sessão e estado: evidência/revisão devem permanecer.
6. Verificar CORS apenas para origem permitida e acesso HTTPS pelo celular após a futura hospedagem.

Os passos de persistência e cliente HTTP podem ser executados localmente sem deploy. O acesso pelo celular a uma URL hospedada só poderá ser verificado no marco de publicação.

Limites atuais: `student_id=1`, sem autenticação e sem controle completo de concorrência entre clientes. Para o primeiro uso, mantenha acesso restrito à instância; múltiplos usuários/processos escrevendo simultaneamente exigem controle adicional. Backup e restauração operacional dependem da futura hospedagem. Nenhuma URL pública foi publicada neste marco.

## Resultados deste marco

- Base anterior: 128 testes backend aprovados.
- Final: **142 testes backend aprovados, zero falhos e zero skipped**, com PostgreSQL 16 real em container e volume persistente; um aviso de depreciação Starlette/AnyIO.
- Frontend: `npm ci` concluído, **6 testes aprovados, zero falhos**, build Next.js/TypeScript concluído com URL explícita. Build sem URL falhou com a mensagem esperada.
- Imagem backend construída e executada como UID 10001; migrations executadas pela imagem, porta configurada em 8017, health check `healthy`.
- Smoke HTTP: Next.js em modo produção + cliente `api.ts` → FastAPI em Docker → PostgreSQL. Sessão de 20 minutos, acerto, feedback e INSERT_CONFIRMATION, saldo 16 minutos. Reinício real do container backend preservou mesma sessão, próxima atividade, mastery, evidence_count, evidence_confidence e revisão. Contagens após reinício: 9/40/32/28, uma tentativa, uma revisão e uma sessão.
- O ambiente cloud exigiu cache npm em `/tmp` e, para Docker, resolução do proxy e CA via secret temporário de BuildKit. Nenhuma verificação TLS foi desativada e nenhum segredo/CA entrou na imagem ou no Git.
- CI foi criado; os comandos foram executados localmente. A execução remota do GitHub Actions dependerá do push. O smoke usou páginas HTTP e o cliente API real, sem teste visual de navegador ou celular físico. Não houve deploy.
