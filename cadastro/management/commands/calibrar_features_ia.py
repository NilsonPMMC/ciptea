from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from cadastro.ai_services import extract_text_from_document
from cadastro.ai_validators import validate_address, validate_identity, validate_laudo
from cadastro.document_classifier import assess_expected_document
from cadastro.document_features import extract_document_features


FEATURE_CONF_APPROVE_MIN = int(os.getenv("FEATURE_CONF_APPROVE_MIN", "75"))
FEATURE_CONF_ASSIST_MIN = int(os.getenv("FEATURE_CONF_ASSIST_MIN", "60"))


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    vals = sorted(values)
    idx = int(round((len(vals) - 1) * p))
    idx = max(0, min(idx, len(vals) - 1))
    return int(vals[idx])


def _decisao_por_threshold(overall: int, approve_min: int, assist_min: int) -> str:
    if overall >= approve_min:
        return "APROVACAO_SUGERIDA"
    if overall >= assist_min:
        return "REVISAO_ASSISTIDA"
    return "REVISAO_MANUAL"


class Command(BaseCommand):
    help = "Calibra thresholds de features em lote de amostras OCR/validação."

    def add_arguments(self, parser):
        parser.add_argument(
            "--samples-file",
            type=str,
            default="",
            help=(
                "Arquivo JSON com lista de amostras. Campos: path, tipo(laudo|identidade|endereco), "
                "nome, cpf, data_nascimento, responsaveis, expected_ok(opcional)."
            ),
        )
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="Arquivo de saída JSON com o relatório de calibração.",
        )

    def handle(self, *args, **options):
        samples_file = (options.get("samples_file") or "").strip()
        if not samples_file:
            raise CommandError("Informe --samples-file com o JSON de amostras.")

        file_path = Path(samples_file).expanduser().resolve()
        if not file_path.is_file():
            raise CommandError(f"Arquivo de amostras não encontrado: {file_path}")

        try:
            samples = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CommandError(f"Falha ao ler JSON de amostras: {exc}") from exc
        if not isinstance(samples, list) or not samples:
            raise CommandError("JSON de amostras deve ser uma lista não vazia.")

        kind_map = {
            "laudo": "LAUDO",
            "identidade": "RG_BENEF",
            "endereco": "COMP_RES",
        }

        rows: list[dict[str, Any]] = []
        for idx, sample in enumerate(samples, start=1):
            if not isinstance(sample, dict):
                raise CommandError(f"Amostra #{idx} inválida (esperado objeto).")
            tipo = (sample.get("tipo") or "").strip().lower()
            if tipo not in kind_map:
                raise CommandError(f"Amostra #{idx} com tipo inválido: {tipo}")

            path = Path(str(sample.get("path") or "")).expanduser().resolve()
            if not path.is_file():
                raise CommandError(f"Amostra #{idx} arquivo não encontrado: {path}")

            self.stdout.write(f"[{idx}/{len(samples)}] {path.name} ({tipo})")
            ocr = extract_text_from_document(str(path), document_kind=kind_map[tipo])
            if not ocr.get("ok"):
                rows.append(
                    {
                        "path": str(path),
                        "tipo": tipo,
                        "ocr_ok": False,
                        "erro": ocr.get("motivo", "OCR falhou"),
                    }
                )
                continue

            texto = ocr.get("text", "")
            cls = assess_expected_document(kind_map[tipo], texto)
            features = extract_document_features(kind_map[tipo], cls.get("predicted_type", ""), texto)
            overall = int(features.get("overall_feature_confidence", 0) or 0)
            decisao = _decisao_por_threshold(overall, FEATURE_CONF_APPROVE_MIN, FEATURE_CONF_ASSIST_MIN)

            if tipo == "laudo":
                validation = validate_laudo(texto)
            elif tipo == "identidade":
                validation = validate_identity(
                    texto,
                    expected_name=sample.get("nome", ""),
                    expected_cpf=sample.get("cpf", ""),
                    cpf_candidates=ocr.get("cpf_candidates") or [],
                    expected_birth_date=sample.get("data_nascimento") or None,
                )
            else:
                responsaveis = sample.get("responsaveis") or []
                if isinstance(responsaveis, str):
                    responsaveis = [r.strip() for r in responsaveis.split(",") if r.strip()]
                validation = validate_address(texto, responsaveis)

            row = {
                "path": str(path),
                "tipo": tipo,
                "ocr_ok": True,
                "predicted_type": cls.get("predicted_type"),
                "classifier_confidence": cls.get("confidence"),
                "overall_feature_confidence": overall,
                "feature_decision": decisao,
                "validation_ok": bool(validation.get("ok", False)),
                "validation_status": validation.get("status"),
                "validation_reason": validation.get("motivo", ""),
                "expected_ok": sample.get("expected_ok"),
                "matches_expected": None,
            }
            if sample.get("expected_ok") is not None:
                row["matches_expected"] = bool(sample.get("expected_ok")) == bool(validation.get("ok", False))
            rows.append(row)

        # Resumo agregado
        by_type: dict[str, dict[str, Any]] = {}
        overall_ok: list[int] = []
        overall_not_ok: list[int] = []
        by_type_ok: dict[str, list[int]] = {}
        by_type_not_ok: dict[str, list[int]] = {}
        for row in rows:
            t = row.get("tipo", "unknown")
            by_type_ok.setdefault(t, [])
            by_type_not_ok.setdefault(t, [])
            by_type.setdefault(
                t,
                {
                    "count": 0,
                    "ocr_fail": 0,
                    "validation_ok": 0,
                    "overall_feature_confidences": [],
                    "feature_decisions": {
                        "APROVACAO_SUGERIDA": 0,
                        "REVISAO_ASSISTIDA": 0,
                        "REVISAO_MANUAL": 0,
                    },
                },
            )
            agg = by_type[t]
            agg["count"] += 1
            if not row.get("ocr_ok"):
                agg["ocr_fail"] += 1
                continue
            ofc = int(row.get("overall_feature_confidence", 0) or 0)
            agg["overall_feature_confidences"].append(ofc)
            if row.get("validation_ok"):
                agg["validation_ok"] += 1
                overall_ok.append(ofc)
                by_type_ok[t].append(ofc)
            else:
                overall_not_ok.append(ofc)
                by_type_not_ok[t].append(ofc)
            dec = row.get("feature_decision") or "REVISAO_MANUAL"
            agg["feature_decisions"][dec] = agg["feature_decisions"].get(dec, 0) + 1

        for agg in by_type.values():
            vals = agg["overall_feature_confidences"]
            agg["avg_overall_feature_confidence"] = round(sum(vals) / len(vals), 2) if vals else 0
            agg["min_overall_feature_confidence"] = min(vals) if vals else 0
            agg["max_overall_feature_confidence"] = max(vals) if vals else 0
            agg["validation_ok_rate"] = round((agg["validation_ok"] / max(agg["count"], 1)) * 100, 2)

        # Sugestão simples de thresholds para onda 2
        # approve: 25º percentil dos casos validados como ok
        # assist: 75º percentil dos casos não-ok (para separar revisão manual)
        suggested_approve = max(60, _percentile(overall_ok, 0.25)) if overall_ok else FEATURE_CONF_APPROVE_MIN
        suggested_assist = max(40, _percentile(overall_not_ok, 0.75)) if overall_not_ok else FEATURE_CONF_ASSIST_MIN
        if suggested_assist >= suggested_approve:
            suggested_assist = max(40, suggested_approve - 10)

        suggested_by_type: dict[str, dict[str, int]] = {}
        alerts: list[str] = []
        for t in by_type.keys():
            ok_vals = by_type_ok.get(t, [])
            not_ok_vals = by_type_not_ok.get(t, [])
            approve_t = max(50, _percentile(ok_vals, 0.25)) if ok_vals else FEATURE_CONF_APPROVE_MIN
            assist_t = max(35, _percentile(not_ok_vals, 0.75)) if not_ok_vals else FEATURE_CONF_ASSIST_MIN
            if assist_t >= approve_t:
                assist_t = max(35, approve_t - 10)
            suggested_by_type[t] = {
                "approve_min": int(approve_t),
                "assist_min": int(assist_t),
            }
            if ok_vals and not_ok_vals:
                # Se negativos estiverem com confiança alta demais, sinaliza baixa separabilidade.
                if max(not_ok_vals) >= min(ok_vals):
                    alerts.append(
                        f"Separação fraca para '{t}': negativos alcançam confiança de positivos; recalibrar features."
                    )

        report = {
            "current_thresholds": {
                "approve_min": FEATURE_CONF_APPROVE_MIN,
                "assist_min": FEATURE_CONF_ASSIST_MIN,
            },
            "suggested_thresholds": {
                "approve_min": suggested_approve,
                "assist_min": suggested_assist,
            },
            "suggested_thresholds_by_type": suggested_by_type,
            "alerts": alerts,
            "summary_by_type": by_type,
            "samples_total": len(rows),
            "samples": rows,
        }

        output_file = (options.get("output") or "").strip()
        if output_file:
            out_path = Path(output_file).expanduser().resolve()
            out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Relatório salvo em: {out_path}"))

        self.stdout.write("\n=== Resumo Calibração ===")
        self.stdout.write(json.dumps(report["current_thresholds"], indent=2, ensure_ascii=False))
        self.stdout.write(json.dumps(report["suggested_thresholds"], indent=2, ensure_ascii=False))
        self.stdout.write(json.dumps(report["summary_by_type"], indent=2, ensure_ascii=False))
