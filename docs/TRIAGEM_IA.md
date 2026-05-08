# Triagem IA - Fluxo e Reprocessamento

## Objetivo

Automatizar a avaliacao inicial dos documentos anexados na solicitacao CIPTEA, com decisao entre:

- `APROVADO_IA`
- `REVISAO_MANUAL`

## Etapas de documento

- `LAUDO`
- `IDENTIDADE` (RG_BENEF)
- `ENDERECO` (COMP_RES)
- `RESPONSAVEL` (RG_RESP, quando aplicavel)

Mapeadas em `cadastro/tasks.py` (`DOC_STEP_MAP`).

## Pipeline tecnico

1. `process_ciptea_documents(solicitacao_id)`
   - carrega docs atuais
   - detecta etapas para reprocessar
   - monta orquestracao e encadeia tasks
2. `process_ciptea_document_step(solicitacao_id, etapa)`
   - OCR por documento (docTR + fallback Tesseract)
   - classificador e extracao de features
   - validacao por regra de negocio
3. `finalize_ciptea_triagem(solicitacao_id)`
   - consolida resultado final e atualiza `ValidacaoDocumentoIA`

## Reprocessamento incremental

O sistema nao reprocessa tudo sempre. A selecao usa:

- `doc_ids_processados` / `doc_arquivos_processados` (historico em log)
- IDs e arquivos atuais no banco

Somente documentos alterados entram em novo lote.

## Correcao importante: multiplos reenvios

Cenario tratado:
- usuario reenvia mais de um documento divergente
- triagem ja estava em `PROCESSANDO`

Ajuste aplicado em `cadastro/views.py`:

- quando status e `PROCESSANDO`, o enqueue so e bloqueado se **nao** houver documento novo
- compara `doc_ids_alvo` (ultimo lote) com IDs atuais
- havendo diferenca, nova triagem e enfileirada

Resultado:
- todos os documentos reenviados entram no acompanhamento, sem perder itens do lote.

## Variaveis de ambiente relevantes

- `IA_TASK_SOFT_TIME_LIMIT`, `IA_TASK_TIME_LIMIT`
- `IA_DOC_STEP_SOFT_TIME_LIMIT`, `IA_DOC_STEP_TIME_LIMIT`
- `IA_FAST_PATH`, `IA_FAST_PATH_MIN_TEXT_LEN`
- `FEATURE_CONF_APPROVE_MIN`, `FEATURE_CONF_ASSIST_MIN`, `FEATURE_DECISION_ENFORCE`
- `OCR_*` e `DOC_CLASSIFIER_*`

## Observabilidade

Dados de auditoria em `ValidacaoDocumentoIA.log_ia`:

- etapas OCR / classificacao / features / validacao
- orquestracao (`documentos`, `doc_ids_alvo`, `doc_arquivos_alvo`)
- tempos (`timings_ms`)

Para troubleshooting, combine:
- `triagem-ia` endpoint
- logs de worker IA no `journalctl`
- estado das filas no Redis/Celery inspect
