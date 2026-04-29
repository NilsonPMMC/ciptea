from __future__ import annotations

import re
from datetime import date
from typing import Any

from dateutil import parser as date_parser
from django.utils import timezone


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper()).strip()


def _extract_dates(text: str) -> list[str]:
    body = text or ""
    raw = re.findall(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", body)
    out: list[str] = []
    for token in raw:
        try:
            out.append(date_parser.parse(token, dayfirst=True).date().isoformat())
        except Exception:
            continue
    return sorted(set(out))


def _is_recent_within_days(iso_dates: list[str], days: int = 90) -> bool:
    today = timezone.localdate()
    for token in iso_dates:
        try:
            dt = date_parser.parse(token).date()
        except Exception:
            continue
        diff = (today - dt).days
        if 0 <= diff <= days:
            return True
    return False


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _avg_confidence(values: list[int]) -> int:
    if not values:
        return 0
    return _clamp_score(sum(values) / float(len(values)))


def extract_laudo_features(text: str) -> dict[str, Any]:
    body = _normalize(text)
    compact = re.sub(r"[^A-Z0-9]", "", body).replace("O", "0")
    cid_match = re.search(r"(F84\d*|6A02\d*)", compact)
    crm_match = re.search(r"\bCRM[\s:/-]*([A-Z]{0,2}\d{4,7})", body)
    possui_cid = bool(cid_match)
    possui_tea = bool(re.search(r"\bTEA\b|TRANSTORNO DO ESPECTRO AUTISTA", body))
    possui_dsm = bool(re.search(r"\bDSM\b", body))
    crm_encontrado = crm_match.group(1) if crm_match else ""

    conf_cid = 100 if possui_cid else 0
    conf_tea = 90 if possui_tea else 20
    conf_dsm = 80 if possui_dsm else 20
    conf_crm = 70 if crm_encontrado else 30
    overall = _avg_confidence([conf_cid, conf_tea, conf_dsm, conf_crm])

    return {
        "tipo_detectado_feature": "LAUDO",
        "cid_encontrado": cid_match.group(1) if cid_match else "",
        "possui_cid_tea": possui_cid,
        "crm_encontrado": crm_encontrado,
        "possui_termo_tea": possui_tea,
        "possui_termo_dsm": possui_dsm,
        "feature_confidence": {
            "cid": conf_cid,
            "termo_tea": conf_tea,
            "termo_dsm": conf_dsm,
            "crm": conf_crm,
        },
        "overall_feature_confidence": overall,
    }


def extract_identity_features(text: str) -> dict[str, Any]:
    body = _normalize(text)
    digits = _digits(body)
    cpf_matches = re.findall(r"\d{3}\D?\d{3}\D?\d{3}\D?\d{2}", body)
    cpf_list = sorted({_digits(c) for c in cpf_matches if len(_digits(c)) == 11})
    possui_identidade = bool(
        re.search(r"CARTEIRA DE IDENTIDADE|INSTITUTO DE IDENTIFICACAO|SECRETARIA DA SEGURANCA", body)
    )
    possui_cnh = bool(
        re.search(r"CARTEIRA NACIONAL DE HABILITACAO|SENATRAN|DETRAN|DRIVER LICENSE", body)
    )
    possui_nascimento = bool(re.search(r"NASCIMENTO|DATA DE NASCIMENTO", body))

    conf_cpf = _clamp_score(min(len(cpf_list), 3) * 35 + (10 if cpf_list else 0))
    conf_tipo = 90 if (possui_identidade or possui_cnh) else 25
    conf_nascimento = 85 if possui_nascimento else 30
    overall = _avg_confidence([conf_cpf, conf_tipo, conf_nascimento])

    return {
        "tipo_detectado_feature": "IDENTIDADE",
        "cpf_candidatos_texto": cpf_list[:5],
        "qtd_cpf_candidatos": len(cpf_list),
        "possui_termo_identidade": possui_identidade,
        "possui_termo_cnh": possui_cnh,
        "possui_data_nascimento": possui_nascimento,
        "texto_digitos_tamanho": len(digits),
        "feature_confidence": {
            "cpf_texto": conf_cpf,
            "tipo_documento": conf_tipo,
            "data_nascimento": conf_nascimento,
        },
        "overall_feature_confidence": overall,
    }


def extract_address_features(text: str) -> dict[str, Any]:
    body = _normalize(text)
    dates = _extract_dates(body)
    issuer_patterns = [
        "VIVO",
        "TELEFONICA",
        "SABESP",
        "ENEL",
        "ELETROPAULO",
        "NATURA",
        "PREFEITURA",
        "BANCO",
        "CAIXA",
    ]
    emissor_hits = [p for p in issuer_patterns if p in body]
    possui_cep = bool(re.search(r"\b\d{5}-?\d{3}\b", body))
    possui_endereco = bool(re.search(r"ENDERECO|LOGRADOURO|RUA|AVENIDA|BAIRRO|CEP", body))
    data_recente = _is_recent_within_days(dates, days=90)

    conf_data = 90 if data_recente else (45 if dates else 10)
    conf_endereco = 85 if possui_endereco else 30
    conf_emissor = _clamp_score(min(len(emissor_hits), 3) * 25 + (20 if emissor_hits else 0))
    conf_cep = 85 if possui_cep else 30
    overall = _avg_confidence([conf_data, conf_endereco, conf_emissor, conf_cep])

    return {
        "tipo_detectado_feature": "COMP_RES",
        "datas_encontradas": dates,
        "data_recente_90d": data_recente,
        "emissor_suspeito": emissor_hits[:5],
        "possui_cep": possui_cep,
        "possui_endereco": possui_endereco,
        "feature_confidence": {
            "data_recente": conf_data,
            "endereco": conf_endereco,
            "emissor": conf_emissor,
            "cep": conf_cep,
        },
        "overall_feature_confidence": overall,
    }


def extract_document_features(expected_type: str, predicted_type: str, text: str) -> dict[str, Any]:
    et = (expected_type or "").upper()
    pt = (predicted_type or "").upper()
    identity_like = {"RG_BENEF", "RG_RESP", "CNH"}
    if et == "LAUDO" or pt == "LAUDO":
        return extract_laudo_features(text)
    if et == "COMP_RES" or pt == "COMP_RES":
        return extract_address_features(text)
    if et in identity_like or pt in identity_like:
        return extract_identity_features(text)
    return {
        "tipo_detectado_feature": "UNKNOWN",
        "texto_tamanho": len((text or "").strip()),
        "feature_confidence": {"generic": 20},
        "overall_feature_confidence": 20,
    }
