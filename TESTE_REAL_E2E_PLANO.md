# Plano E2E de Teste Real (Munícipe + PAC)

Data base: 2026-04-28

## Objetivo
Validar ponta a ponta o fluxo real:
1. Frontend recebe upload do munícipe.
2. Backend orquestra OCR + classificação + features + validação.
3. Resultado volta para munícipe e painel PAC com justificativa.

## Escopo
- Entrada: `LAUDO`, `RG/CNH` e `COMP_RES`.
- Saída técnica esperada:
  - OCR com metadados (`engine`, `variant`, `rotation`, `psm`);
  - classificação de tipo de documento;
  - features estruturadas e `overall_feature_confidence`;
  - decisão operacional (`APROVACAO_SUGERIDA|REVISAO_ASSISTIDA|REVISAO_MANUAL`);
  - validação final (`APROVADO_IA|REVISAO_MANUAL`).

## Onda 1 (base operacional) - concluída
- Decisão operacional por features no backend.
- Output da decisão no comando local de teste.
- Thresholds parametrizados por env.

## Onda 2 (calibração) - concluída
- Comando de calibração em lote:
  - `python manage.py calibrar_features_ia --samples-file /var/www/ciptea/calibration_samples.json --output /var/www/ciptea/calibration_report.json`
- Relatório gerado com sugestões de threshold.

## Onda 3 (ML-ready) - concluída
- Versionamento de pipeline no `log_ia`.
- Telemetria de tempo por etapa (`timings_ms`).
- Exportador de dataset:
  - `python manage.py exportar_dataset_ia --output /var/www/ciptea/dataset_ia.jsonl --limit 50`

## Execução de hoje (bateria técnica)
Comando executado:

```bash
python manage.py check
python manage.py teste_triagem_ia ./laudo_teste.jpg --tipo laudo
python manage.py teste_triagem_ia ./rg_nilson.jpg --tipo identidade --nome "Nilson Carvalho de Moraes" --cpf "29832481864" --data-nascimento 1981-08-13
python manage.py teste_triagem_ia ./rg_theo.jpeg --tipo identidade --nome "Theo de Souza Moraes" --cpf "56835247843" --data-nascimento 2015-04-27
python manage.py teste_triagem_ia ./cnh_nilson.pdf --tipo identidade --nome "Nilson Carvalho de Moraes" --cpf "29832481864" --data-nascimento 1981-08-13
python manage.py teste_triagem_ia ./comprovante_endereco.pdf --tipo endereco --responsaveis "Nilson Carvalho de Moraes"
```

Resumo:
- `laudo_teste.jpg`: aprovado IA.
- `rg_nilson.jpg`: aprovado IA.
- `rg_theo.jpeg`: aprovado IA via fallback semântico de menor.
- `cnh_nilson.pdf`: aprovado IA.
- `comprovante_endereco.pdf`: revisão manual (data antiga).

## Go/No-Go para piloto de frontend
Go condicional para piloto controlado:
- `FEATURE_DECISION_ENFORCE=0` no início (shadow mode).
- PAC acompanha decisões e feedback semanal.
- Após estabilização, avaliar ativar enforcement.
