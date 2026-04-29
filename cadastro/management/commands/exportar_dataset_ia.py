from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

from cadastro.models import ValidacaoDocumentoIA


def _flatten_sample(validacao: ValidacaoDocumentoIA) -> dict[str, Any]:
    log = validacao.log_ia if isinstance(validacao.log_ia, dict) else {}
    etapas = log.get("etapas", {}) if isinstance(log.get("etapas"), dict) else {}
    classificacao = etapas.get("classificacao_documento", {}) if isinstance(etapas.get("classificacao_documento"), dict) else {}
    features = etapas.get("features_documento", {}) if isinstance(etapas.get("features_documento"), dict) else {}
    valid = etapas.get("validacao", {}) if isinstance(etapas.get("validacao"), dict) else {}
    decisao_feat = etapas.get("decisao_operacional_features", {}) if isinstance(etapas.get("decisao_operacional_features"), dict) else {}
    return {
        "solicitacao_id": validacao.solicitacao_id,
        "status_validacao_final": validacao.status_validacao,
        "pipeline_version": (log.get("pipeline") or {}).get("version"),
        "timings_ms": log.get("timings_ms", {}),
        "classificacao_documento": classificacao,
        "features_documento": features,
        "validacao_regras": valid,
        "decisao_operacional_features": decisao_feat,
    }


class Command(BaseCommand):
    help = "Exporta dataset ML-ready a partir de ValidacaoDocumentoIA.log_ia"

    def add_arguments(self, parser):
        parser.add_argument("--output", type=str, default="/var/www/ciptea/dataset_ia.jsonl")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        output = Path(options["output"]).expanduser().resolve()
        limit = int(options.get("limit") or 0)
        qs = ValidacaoDocumentoIA.objects.select_related("solicitacao").order_by("-atualizado_em")
        if limit > 0:
            qs = qs[:limit]
        rows = [_flatten_sample(v) for v in qs]

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        self.stdout.write(self.style.SUCCESS(f"Dataset exportado: {output}"))
        self.stdout.write(self.style.SUCCESS(f"Amostras: {len(rows)}"))
