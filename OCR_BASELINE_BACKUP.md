# Backup de baseline OCR (28/04/2026)

Registro do resultado validado antes da otimização de performance.

## Contexto
- Arquivo de referência: `laudo_teste.jpg`
- Comando:
  - `python manage.py teste_triagem_ia ./laudo_teste.jpg --tipo laudo`
- Parâmetros usados:
  - `OCR_FALLBACK_TESSERACT=1`
  - `OCR_TESSERACT_LANG=por+osd`
  - `OCR_MIN_TEXT_CHARS=120`
  - `OCR_MIN_ALPHA_RATIO=0.55`
  - `OCR_MIN_LONG_TOKEN_RATIO=0.35`
  - `OCR_TESSERACT_ROTATIONS=0,90,180,270`

## Resultado validado
- `selected_engine`: `tesseract`
- `best_variant`: `gray_autocontrast`
- `best_rotation`: `180`
- `quality_score`: `4.807423609156073`
- `cid_hint`: `true`
- validação laudo:
  - `ok: true`
  - `status: APROVADO_IA`
  - `motivo: CID identificado: F840`
  - `score: 100`

## Objetivo da otimização seguinte
Reduzir tempo de execução com estratégia de parada antecipada (*early stop*), preservando o mesmo resultado funcional acima.
