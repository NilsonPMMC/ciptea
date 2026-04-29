# Roadmap CIPTEA (rascunho vivo)

Itens priorizados para evolução técnica e produto. Última atualização: abril/2026.

---

## Curto prazo (próximas iterações)

### Triagem de documentos (IA + humano)

| Prioridade | Item | Contexto |
|------------|------|----------|
| **P0** | **Segundo motor de OCR (fallback ou fusão)** | O pipeline atual (docTR *fast* + pré-processamento Pillow) **não** atingiu leitura confiável em laudos com timbre colorido / PT-BR (ex.: `laudo_teste.jpg` — texto OCR continua ruim; validação de CID falha por causa do OCR, não por ausência de dado no documento). **Sugestão técnica:** integrar **Tesseract** (`por` + `osd`) e/ou **PaddleOCR** como segunda leitura ou votação com docTR; opcionalmente extrair camada de texto em **PDF** nativo quando o anexo for PDF. |
| P1 | Ajuste de custo / estabilidade do worker | Workers Celery com OCR + PyTorch são sensíveis a **OOM** (ex.: SIGABRT). Revisar concorrência (`-c`), limites de memória e timeouts em homolog/prod. |
| P1 | Registros presos em `PROCESSANDO` | Tarefa ou script operacional para reconciliar estado no banco quando o worker morre após gravar `PROCESSANDO` (ex.: marcar revisão manual + `log_ia`). |

### Segurança e API pública

| Prioridade | Item | Contexto |
|------------|------|----------|
| P1 | `GET …/triagem-ia/` sem autenticação | Hoje está em `AllowAny` para o fluxo do cidadão. Evoluir para **protocolo + CPF + data** (padrão `buscar-completo`) ou token de sessão de triagem. |

---

## Médio prazo

- Métricas de qualidade da triagem (taxa de acerto OCR vs. decisão final do PAC).
- Testes automatizados do pipeline (fixtures de imagem/PDF, mocks de Celery).

---

## Apresentação / status atual (reunião)

- **Fluxo:** upload → fila Celery → leitura de status via API (polling no portal).
- **Human-in-the-loop:** falha ou baixa confiança → revisão manual (já alinhado ao desenho).
- **Limite atual:** precisão do **OCR em documentos reais** (timbre, PT-BR) — **roadmap:** segundo motor de OCR (acima); pré-processamento sozinho não resolveu o caso de referência.
