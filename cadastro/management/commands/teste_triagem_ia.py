"""
Teste prático de OCR + validadores (sem Celery, sem banco).

Uso:
  cd /var/www/ciptea && source venv/bin/activate
  python manage.py teste_triagem_ia ./meu_arquivo.png --tipo laudo
  python manage.py teste_triagem_ia ./rg.jpg --tipo identidade --nome "Fulano" --cpf "12345678901"
  python manage.py teste_triagem_ia ./conta.pdf --tipo endereco --responsaveis "Maria Silva"

Requer dependências de IA instaladas (python-doctr, thefuzz, etc.).
Suporta imagem/PDF conforme o mesmo pipeline da task (`extract_text_from_document`).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

FEATURE_CONF_APPROVE_MIN = int(os.getenv("FEATURE_CONF_APPROVE_MIN", "75"))
FEATURE_CONF_ASSIST_MIN = int(os.getenv("FEATURE_CONF_ASSIST_MIN", "60"))
FEATURE_DECISION_ENFORCE = os.getenv("FEATURE_DECISION_ENFORCE", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class Command(BaseCommand):
    help = "Roda OCR (docTR) e validadores locais em um arquivo de imagem/PDF suportado pelo fluxo."

    def add_arguments(self, parser):
        parser.add_argument(
            "caminho",
            type=str,
            help="Caminho absoluto ou relativo ao arquivo (ex.: ./laudo.png)",
        )
        parser.add_argument(
            "--tipo",
            choices=("laudo", "identidade", "endereco", "ocr"),
            default="laudo",
            help="Qual validação aplicar ao texto extraído (default: laudo). Use 'ocr' para só OCR.",
        )
        parser.add_argument("--nome", type=str, default="", help="Nome esperado (identidade)")
        parser.add_argument("--cpf", type=str, default="", help="CPF esperado (identidade)")
        parser.add_argument(
            "--data-nascimento",
            type=str,
            default="",
            help="Data de nascimento esperada (identidade), ex.: 2015-04-27",
        )
        parser.add_argument(
            "--responsaveis",
            type=str,
            default="",
            help="Nomes separados por vírgula (endereço)",
        )

    def handle(self, *args, **options):
        # Import tardio: evita carregar docTR/torch ao rodar --help
        from cadastro.document_classifier import assess_expected_document
        from cadastro.document_features import extract_document_features
        from cadastro.ai_services import extract_text_from_document
        from cadastro.ai_validators import validate_address, validate_identity, validate_laudo

        caminho = Path(options["caminho"]).expanduser().resolve()
        if not caminho.is_file():
            raise CommandError(f"Arquivo não encontrado: {caminho}")

        self.stdout.write(self.style.NOTICE(f"Arquivo: {caminho}"))
        self.stdout.write(self.style.NOTICE("Executando OCR (pode demorar na 1ª execução)…"))

        kind_map = {
            "laudo": "LAUDO",
            "identidade": "RG_BENEF",
            "endereco": "COMP_RES",
        }
        ocr = extract_text_from_document(str(caminho), document_kind=kind_map.get(options["tipo"], ""))
        self.stdout.write("\n=== OCR ===")
        self.stdout.write(json.dumps({k: v for k, v in ocr.items() if k != "text"}, indent=2, ensure_ascii=False))
        texto = ocr.get("text") or ""
        preview = texto[:2000] + ("…" if len(texto) > 2000 else "")
        self.stdout.write("\n--- Texto extraído (preview) ---\n" + preview)

        expected_map = {
            "laudo": "LAUDO",
            "identidade": "RG_BENEF",
            "endereco": "COMP_RES",
        }
        if options["tipo"] in expected_map:
            classificacao = assess_expected_document(expected_map[options["tipo"]], texto)
            self.stdout.write("\n=== Classificação por padrão ===")
            self.stdout.write(json.dumps(classificacao, indent=2, ensure_ascii=False))
            features = extract_document_features(
                expected_map[options["tipo"]],
                classificacao.get("predicted_type", ""),
                texto,
            )
            self.stdout.write("\n=== Features extraídas ===")
            self.stdout.write(json.dumps(features, indent=2, ensure_ascii=False))
            overall = int(features.get("overall_feature_confidence", 0) or 0)
            if overall >= FEATURE_CONF_APPROVE_MIN:
                decisao_operacional = "APROVACAO_SUGERIDA"
            elif overall >= FEATURE_CONF_ASSIST_MIN:
                decisao_operacional = "REVISAO_ASSISTIDA"
            else:
                decisao_operacional = "REVISAO_MANUAL"
            self.stdout.write("\n=== Decisão operacional (features) ===")
            self.stdout.write(
                json.dumps(
                    {
                        "overall_feature_confidence": overall,
                        "thresholds": {
                            "approve_min": FEATURE_CONF_APPROVE_MIN,
                            "assist_min": FEATURE_CONF_ASSIST_MIN,
                        },
                        "decisao_operacional": decisao_operacional,
                        "enforced": FEATURE_DECISION_ENFORCE,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )

        if options["tipo"] == "ocr":
            if not ocr.get("ok"):
                raise CommandError(ocr.get("motivo") or "OCR falhou")
            self.stdout.write(self.style.SUCCESS("\nConcluído (somente OCR)."))
            return

        if not ocr.get("ok"):
            raise CommandError(ocr.get("motivo") or "OCR falhou; validações não foram executadas.")

        tipo = options["tipo"]
        if tipo == "laudo":
            resultado = validate_laudo(texto)
        elif tipo == "identidade":
            resultado = validate_identity(
                texto,
                expected_name=options["nome"] or "",
                expected_cpf=options["cpf"] or "",
                cpf_candidates=ocr.get("cpf_candidates") or [],
                expected_birth_date=options["data_nascimento"] or None,
            )
        else:
            nomes = [n.strip() for n in (options["responsaveis"] or "").split(",") if n.strip()]
            resultado = validate_address(texto, nomes)

        self.stdout.write(f"\n=== Validação ({tipo}) ===")
        self.stdout.write(json.dumps(resultado, indent=2, ensure_ascii=False))
        self.stdout.write(self.style.SUCCESS("\nConcluído."))
