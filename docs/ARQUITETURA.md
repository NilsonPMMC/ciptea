# Arquitetura do CIPTEA

## Visão geral

O sistema é dividido em:

- **Frontend SPA** (`frontend/`): fluxo cidadão e páginas operacionais.
- **API Backend** (`cadastro/`, `core/`): regras de negócio, persistência e endpoints REST.
- **Processamento assíncrono** (Celery + Redis): triagem documental por IA/OCR.

## Backend

### Módulos principais

- `cadastro/models.py`
  - Entidades de domínio: `Beneficiario`, `Responsavel`, `Solicitacao`, `Documento`, `ValidacaoDocumentoIA`, `Historico`.
- `cadastro/views.py`
  - Viewsets REST e actions de fluxo cidadão (consulta, correção, triagem IA, renovação).
- `cadastro/tasks.py`
  - Orquestração da triagem de documentos por etapas.
- `cadastro/ai_services.py`
  - OCR com docTR e fallback Tesseract; modelos carregados em escopo global.
- `cadastro/document_classifier.py` / `cadastro/document_features.py`
  - Classificação e extração de sinais para decisão de triagem.

### Configuração

- `core/settings/base.py`: base de banco, DRF, CORS, Celery.
- `core/settings/dev.py`: ambiente de desenvolvimento.
- `core/settings/prod.py`: hardening de produção.
- `core/urls.py`: router DRF e endpoints públicos (`/api/...`).

## Frontend

- `frontend/src/views/cidadao/Dashboard.vue`
  - Formulário principal + painel de acompanhamento da triagem IA.
- `frontend/src/stores/cadastro.js`
  - Estado global do fluxo e integração com API.
- `frontend/src/services/api.js`
  - Cliente Axios com base URL por variável de ambiente.

## Assíncrono e filas

### Estratégia

- Fila padrão: `ciptea` para tasks gerais.
- Fila dedicada: `ia_tasks` para triagem IA pesada.

### Tasks IA

- `process_ciptea_documents`
- `process_ciptea_document_step`
- `finalize_ciptea_triagem`

Todas roteadas para `ia_tasks` em `core/celery.py`.

## Pipeline de triagem (alto nível)

1. Enfileira solicitação da triagem.
2. Determina quais documentos precisam ser processados/reprocessados.
3. Processa por etapa documental.
4. Consolida decisão final:
   - `APROVADO_IA`
   - `REVISAO_MANUAL`

## Decisões técnicas relevantes

- Processamento de IA desacoplado da request HTTP (Celery).
- Isolamento de capacidade para IA com worker dedicado.
- Reprocessamento incremental por documento para evitar custo desnecessário.
- Reenfileiramento seguro quando novos documentos são enviados durante estado `PROCESSANDO`.
