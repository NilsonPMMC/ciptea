# CIPTEA

Sistema web para cadastro, acompanhamento e triagem documental da CIPTEA (Carteira de Identificação da Pessoa com Transtorno do Espectro Autista), com backend Django/DRF, frontend Vue 3 e pipeline assíncrono de validação por IA com Celery.

## Stack principal

- Backend: Django + Django REST Framework
- Frontend: Vue 3 + Vite + Vuetify + Pinia + Axios
- Fila assíncrona: Celery + Redis
- OCR/IA: docTR, Tesseract (fallback), Sentence Transformers
- Banco: PostgreSQL (produção) ou SQLite (desenvolvimento)

## Estrutura do projeto

- `cadastro/`: domínio principal (models, views, serializers, tasks e validações IA)
- `core/`: configuração Django (`settings`, `urls`, `celery`)
- `frontend/`: SPA do cidadão e fluxo administrativo
- `deploy/celery/`: unit files de workers Celery
- `docs/`: documentação operacional e técnica complementar

## Requisitos

- Python 3.10+
- Node.js (conforme `frontend/package.json`: `^20.19.0 || >=22.12.0`)
- Redis
- PostgreSQL (opcional em dev, obrigatório em prod)
- Tesseract OCR instalado no servidor (para fallback OCR)

## Configuração de ambiente (backend)

1. Criar e ativar venv.
2. Instalar dependências:

```bash
pip install -r requirements.txt
```

3. Configurar variáveis no `.env` (exemplos de grupos):
   - Django: `DJANGO_ENV`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
   - Banco: `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
   - Celery/Redis: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
   - IA/OCR: `OCR_*`, `IA_*`, `FEATURE_*`, `DOC_CLASSIFIER_*`

4. Aplicar migrações:

```bash
python manage.py migrate
```

5. Subir backend:

```bash
python manage.py runserver
```

## Configuração de ambiente (frontend)

Dentro de `frontend/`:

```bash
npm install
npm run dev
```

Observação:
- A base da API é resolvida por `VITE_API_BASE_URL` ou fallback para `window.location.origin + /api/`.

## Filas Celery (modelo atual)

O projeto usa separação de filas:

- Fila padrão: `ciptea` (worker principal)
- Fila de IA: `ia_tasks` (worker dedicado)

Tasks de triagem IA roteadas para `ia_tasks`:
- `cadastro.tasks.process_ciptea_documents`
- `cadastro.tasks.process_ciptea_document_step`
- `cadastro.tasks.finalize_ciptea_triagem`

Detalhes operacionais em `docs/CELERY_OPERACAO.md`.

## Subindo workers em desenvolvimento

Worker principal:

```bash
celery -A core worker -l info -Q ciptea -n worker_main@%h
```

Worker IA:

```bash
celery -A core worker -l info -Q ia_tasks --concurrency=2 --max-tasks-per-child=10 -n worker_ia@%h
```

## Principais endpoints

Base: `/api/`

- `beneficiarios/`
- `solicitacoes/`
- `documentos/`
- `solicitacoes/{id}/triagem-ia/`
- `solicitacoes/{id}/solicitar-correcao-ia/`
- `carteira/pdf/{protocolo}/`
- `token/` e `token/refresh/`

## Fluxo de triagem IA (resumo)

1. Cidadão envia cadastro e anexos.
2. Backend enfileira `process_ciptea_documents`.
3. Pipeline identifica apenas os documentos alterados e processa por etapa.
4. Finaliza com `APROVADO_IA` ou `REVISAO_MANUAL`.
5. Em divergência, cidadão pode reenviar documentos e o reprocessamento considera todos os itens atualizados.

Detalhes em `docs/TRIAGEM_IA.md`.

## Troubleshooting rápido

- Triagem não anda:
  - validar Redis ativo
  - validar workers `celery-ciptea` e `celery-ciptea-ia`
  - checar logs de ambos
- Task de IA indo para fila errada:
  - conferir `core/celery.py` (routes/queues/routing_key)
  - conferir workers consumindo `-Q ciptea` e `-Q ia_tasks`
- OCR fallback falhando:
  - verificar presença do binário `tesseract` no PATH

## Documentação complementar

- `docs/ARQUITETURA.md`
- `docs/CELERY_OPERACAO.md`
- `docs/TRIAGEM_IA.md`
