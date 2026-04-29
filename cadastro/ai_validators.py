from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

from dateutil import parser as date_parser
from django.utils import timezone
from thefuzz import fuzz

IDENTITY_MINOR_SEMANTIC_FALLBACK = os.getenv(
    "IDENTITY_MINOR_SEMANTIC_FALLBACK", "1"
).strip().lower() in {"1", "true", "yes", "on"}
IDENTITY_MINOR_NAME_SCORE_MIN = int(os.getenv("IDENTITY_MINOR_NAME_SCORE_MIN", "85"))
IDENTITY_MINOR_KEYWORD_MIN = int(os.getenv("IDENTITY_MINOR_KEYWORD_MIN", "2"))


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _normalize_ocr_for_identity(text: str) -> str:
    body = (text or "").upper()
    return (
        body.replace("O", "0")
        .replace("I", "1")
        .replace("L", "1")
        .replace("S", "5")
        .replace("B", "8")
    )


def _clean_text(text: str | None) -> str:
    return (text or "").strip()


def _parse_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date_parser.parse(str(value), dayfirst=False).date()
    except Exception:
        return None


def _is_minor(value: str | date | None) -> bool:
    dt = _parse_date(value)
    if not dt:
        return False
    today = timezone.localdate()
    years = today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))
    return years < 18


def _identity_keyword_hits(text: str) -> int:
    body = (text or "").upper()
    tokens = ("NOME", "CPF", "RG", "FILIACAO", "NASCIMENTO", "DOCUMENTO", "IDENTIDADE")
    return sum(1 for t in tokens if t in body)


def _birth_date_matches_text(text: str, expected_birth_date: str | date | None) -> bool:
    dt = _parse_date(expected_birth_date)
    if not dt:
        return False
    digits_blob = _digits(_normalize_ocr_for_identity(text))
    ddmmyyyy = dt.strftime("%d%m%Y")
    yyyymmdd = dt.strftime("%Y%m%d")
    return ddmmyyyy in digits_blob or yyyymmdd in digits_blob


def validate_laudo(text: str) -> dict[str, Any]:
    body = _clean_text(text).upper()
    # OCR pode introduzir separadores e confundir O/0; normalizamos para busca robusta.
    compact = re.sub(r"[^A-Z0-9]", "", body).replace("O", "0")
    cid_found = re.search(r"(F84\d*|6A02\d*)", compact)
    if not cid_found:
        return {
            "ok": False,
            "status": "REVISAO_MANUAL",
            "motivo": "CID TEA nao identificado com confianca no laudo.",
            "score": 0,
        }
    return {
        "ok": True,
        "status": "APROVADO_IA",
        "motivo": f"CID identificado: {cid_found.group(1)}",
        "score": 100,
    }


def validate_identity(
    text: str,
    expected_name: str,
    expected_cpf: str,
    cpf_candidates: list[str] | None = None,
    expected_birth_date: str | date | None = None,
) -> dict[str, Any]:
    body = _clean_text(text).upper()
    normalized = _normalize_ocr_for_identity(body)
    reversed_body = body[::-1]
    reversed_norm = normalized[::-1]
    expected_cpf_digits = _digits(expected_cpf)
    if not expected_cpf_digits:
        return {
            "ok": False,
            "status": "REVISAO_MANUAL",
            "motivo": "CPF esperado ausente para validacao automatica.",
            "score": 0,
        }

    expected_cpf_rev = expected_cpf_digits[::-1]
    digit_views = [
        _digits(body),
        _digits(normalized),
        _digits(reversed_body),
        _digits(reversed_norm),
    ]
    candidate_set = set(cpf_candidates or [])
    cpf_ok = any(
        expected_cpf_digits in dv or expected_cpf_rev in dv
        for dv in digit_views
        if dv
    )
    if not cpf_ok and candidate_set:
        cpf_ok = expected_cpf_digits in candidate_set or expected_cpf_rev in candidate_set

    name_expected = (expected_name or "").upper()
    name_score = 0
    if name_expected:
        name_score = max(
            fuzz.partial_ratio(name_expected, body),
            fuzz.partial_ratio(name_expected, reversed_body),
        )
    if not cpf_ok or name_score <= 80:
        keyword_hits = max(_identity_keyword_hits(body), _identity_keyword_hits(reversed_body))
        birth_match = _birth_date_matches_text(body, expected_birth_date) or _birth_date_matches_text(
            reversed_body, expected_birth_date
        )
        if (
            IDENTITY_MINOR_SEMANTIC_FALLBACK
            and not cpf_ok
            and _is_minor(expected_birth_date)
            and name_score >= IDENTITY_MINOR_NAME_SCORE_MIN
            and birth_match
            and keyword_hits >= IDENTITY_MINOR_KEYWORD_MIN
        ):
            return {
                "ok": True,
                "status": "APROVADO_IA",
                "motivo": "Fallback semântico (menor): nome e data de nascimento conferem no documento.",
                "score": name_score,
                "cpf_ok": cpf_ok,
                "birth_match": birth_match,
                "identity_keyword_hits": keyword_hits,
                "cpf_candidates": sorted(candidate_set)[:5],
                "fallback_semantico_menor": True,
            }
        return {
            "ok": False,
            "status": "REVISAO_MANUAL",
            "motivo": "Documento de identificacao com baixa confianca (CPF/nome).",
            "score": name_score,
            "cpf_ok": cpf_ok,
            "birth_match": birth_match,
            "identity_keyword_hits": keyword_hits,
            "cpf_candidates": sorted(candidate_set)[:5],
        }
    return {
        "ok": True,
        "status": "APROVADO_IA",
        "motivo": "Nome e CPF conferem com o cadastro.",
        "score": name_score,
        "cpf_ok": cpf_ok,
        "cpf_candidates": sorted(candidate_set)[:5],
    }


def validate_address(text: str, responsible_names_list: list[str]) -> dict[str, Any]:
    body = _clean_text(text).upper()
    names = [n.upper() for n in (responsible_names_list or []) if n]

    best_name_score = 0
    matched_name = None
    for name in names:
        score = fuzz.partial_ratio(name, body)
        if score > best_name_score:
            best_name_score = score
            matched_name = name

    name_ok = bool(names) and best_name_score >= 80

    date_matches = re.findall(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", body)
    now = timezone.localdate()
    date_ok = False
    parsed_dates: list[str] = []
    for date_str in date_matches:
        try:
            dt = date_parser.parse(date_str, dayfirst=True).date()
            parsed_dates.append(dt.isoformat())
            if 0 <= (now - dt).days <= 90:
                date_ok = True
        except Exception:
            continue

    if not name_ok or not date_ok:
        return {
            "ok": False,
            "status": "REVISAO_MANUAL",
            "motivo": "Comprovante de endereco sem confianca suficiente (nome/data).",
            "score_nome": best_name_score,
            "nome_ok": name_ok,
            "data_recente_ok": date_ok,
            "datas_encontradas": parsed_dates,
        }

    return {
        "ok": True,
        "status": "APROVADO_IA",
        "motivo": "Nome de responsavel e data recente identificados no comprovante.",
        "score_nome": best_name_score,
        "nome_encontrado": matched_name,
        "datas_encontradas": parsed_dates,
    }
