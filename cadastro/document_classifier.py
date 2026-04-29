from __future__ import annotations

import os
import re
import unicodedata
from typing import Any


CLASSIFIER_BLOCK_ON_HIGH_MISMATCH = os.getenv(
    "DOC_CLASSIFIER_BLOCK_ON_HIGH_MISMATCH", "0"
).strip().lower() in {"1", "true", "yes", "on"}
CLASSIFIER_MISMATCH_MIN_SCORE = int(os.getenv("DOC_CLASSIFIER_MISMATCH_MIN_SCORE", "75"))
CLASSIFIER_MIN_CONFIDENCE_TO_CLASSIFY = int(
    os.getenv("DOC_CLASSIFIER_MIN_CONFIDENCE_TO_CLASSIFY", "30")
)
_TYPE_ALIASES: dict[str, set[str]] = {
    "RG_BENEF": {"RG_BENEF", "CNH"},
    "RG_RESP": {"RG_RESP", "CNH"},
    "LAUDO": {"LAUDO"},
    "COMP_RES": {"COMP_RES"},
}


_TYPE_PATTERNS_WEIGHTED: dict[str, list[tuple[str, float]]] = {
    "LAUDO": [
        (r"\bLAUDO\b", 1.2),
        (r"\bCID\b", 1.4),
        (r"\bF[\W_]*8[\W_]*4|\b6[\W_]*A[\W_]*0[\W_]*2", 1.6),
        (r"TRANSTORNO\s+DO\s+ESPECTRO\s+AUTISTA|\bTEA\b", 1.2),
        (r"\bDSM\b", 0.8),
        (r"\bMEDIC[OA]\b", 0.8),
        (r"PACIENTE", 0.6),
    ],
    "RG_BENEF": [
        (r"REPUBLICA\s+FEDERATIVA\s+DO\s+BRASIL", 1.0),
        (r"CARTEIRA\s+DE\s+IDENTIDADE|IDENTIFICACAO", 1.1),
        (r"\bNOME\b", 0.8),
        (r"DATA\s+DE\s+NASCIMENTO|NASCIMENTO", 1.0),
        (r"\bCPF\b|\d{3}\D?\d{3}\D?\d{3}\D?\d{2}", 1.3),
        (r"SECRETARIA\s+DA\s+SEGURANCA\s+PUBLICA|INSTITUTO\s+DE\s+IDENTIFICACAO", 0.9),
        (r"ASSINATURA\s+DO\s+DIRETOR|CARTEIRA\s+DE\s+IDENTIDADE", 0.7),
    ],
    "RG_RESP": [
        (r"REPUBLICA\s+FEDERATIVA\s+DO\s+BRASIL", 1.0),
        (r"CARTEIRA\s+DE\s+IDENTIDADE|IDENTIFICACAO", 1.1),
        (r"\bNOME\b", 0.8),
        (r"DATA\s+DE\s+NASCIMENTO|NASCIMENTO", 1.0),
        (r"\bCPF\b|\d{3}\D?\d{3}\D?\d{3}\D?\d{2}", 1.3),
        (r"SECRETARIA\s+DA\s+SEGURANCA\s+PUBLICA|INSTITUTO\s+DE\s+IDENTIFICACAO", 0.9),
        (r"ASSINATURA\s+DO\s+DIRETOR|CARTEIRA\s+DE\s+IDENTIDADE", 0.7),
    ],
    "COMP_RES": [
        (r"VENCIMENTO|EMISSAO|REFERENCIA", 1.0),
        (r"ENDERECO|LOGRADOURO|CEP|BAIRRO|CIDADE", 1.3),
        (r"FATURA|CONTA|AGUA|ENERGIA|VIVO|TELEFONICA|SABESP|ENEL", 1.2),
        (r"VALOR|TOTAL|PAGAMENTO", 0.8),
        (r"MOGI|CRUZES|SP", 0.7),
    ],
    "CNH": [
        (r"CARTEIRA\s+NACIONAL\s+DE\s+HABILITACAO|DRIVER\s+LICENSE|PERMISO", 1.5),
        (r"SENATRAN|SECRETARIA\s+NACIONAL\s+DE\s+TRANSITO|DETRAN", 1.2),
        (r"QR-?CODE", 0.7),
        (r"\bCPF\b|\d{3}\D?\d{3}\D?\d{3}\D?\d{2}", 0.9),
        (r"NACIONALIDADE|HABILITACAO|CATEGORIA", 0.8),
    ],
}


def _normalize(text: str) -> str:
    body = (text or "").upper()
    body = "".join(ch for ch in unicodedata.normalize("NFD", body) if unicodedata.category(ch) != "Mn")
    body = re.sub(r"\s+", " ", body)
    return body


def classify_document_type(text: str) -> dict[str, Any]:
    body = _normalize(text)
    if not body:
        return {
            "predicted_type": "UNKNOWN",
            "confidence": 0,
            "scores": {},
            "hits": {},
        }

    scores: dict[str, float] = {}
    hits: dict[str, list[str]] = {}
    for doc_type, weighted_patterns in _TYPE_PATTERNS_WEIGHTED.items():
        matched_patterns: list[str] = []
        matched_weight = 0.0
        total_weight = sum(weight for _, weight in weighted_patterns)
        for pattern, weight in weighted_patterns:
            if re.search(pattern, body):
                matched_patterns.append(pattern)
                matched_weight += weight
        score = round((matched_weight / float(max(total_weight, 0.0001))) * 100, 2)
        scores[doc_type] = score
        hits[doc_type] = matched_patterns

    predicted = max(scores, key=scores.get) if scores else "UNKNOWN"
    confidence = int(round(scores.get(predicted, 0)))
    if confidence < CLASSIFIER_MIN_CONFIDENCE_TO_CLASSIFY:
        predicted = "UNKNOWN"
    return {
        "predicted_type": predicted,
        "confidence": confidence,
        "scores": scores,
        "hits": hits,
    }


def assess_expected_document(expected_type: str, text: str) -> dict[str, Any]:
    cls = classify_document_type(text)
    predicted = cls["predicted_type"]
    confidence = int(cls["confidence"])
    accepted = _TYPE_ALIASES.get(expected_type, {expected_type})
    mismatch = predicted not in {"UNKNOWN", *accepted}
    high_confidence_mismatch = mismatch and confidence >= CLASSIFIER_MISMATCH_MIN_SCORE
    return {
        **cls,
        "expected_type": expected_type,
        "accepted_types": sorted(accepted),
        "mismatch": mismatch,
        "high_confidence_mismatch": high_confidence_mismatch,
        "should_block": bool(CLASSIFIER_BLOCK_ON_HIGH_MISMATCH and high_confidence_mismatch),
    }
