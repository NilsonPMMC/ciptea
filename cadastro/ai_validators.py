from __future__ import annotations

import os
import re
import unicodedata
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

def _normalize_name(text: str) -> str:
    if not text: return ""
    txt_norm = ''.join(c for c in unicodedata.normalize('NFD', str(text)) if unicodedata.category(c) != 'Mn')
    return txt_norm.upper().strip()

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


def validate_laudo(text: str, expected_name: str = None) -> dict[str, Any]:
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

    # NOVO: Validação de Titularidade (Name Matching Seguro e Estrito)
    if expected_name:
        nome_norm = _normalize_name(expected_name)
        texto_norm = _normalize_name(text)

        # 1. Regra de Ouro: O Primeiro Nome TEM que existir na string exata.
        primeiro_nome = nome_norm.split()[0] if nome_norm else ""
        
        # Abandono do Fuzzy aqui. Busca binária simples:
        if primeiro_nome not in texto_norm:
            return {
                "ok": False,
                "status": "REVISAO_MANUAL",
                "motivo": f"CID identificado ({cid_found.group(1)}), mas titularidade falhou (Primeiro nome '{primeiro_nome}' ausente).",
                "score": 30,
            }

        # 2. Se o primeiro nome passou, conferimos o resto (ignorando a ordem das palavras)
        from thefuzz import fuzz
        match_score = fuzz.token_set_ratio(nome_norm, texto_norm)

        if match_score < 75: 
            return {
                "ok": False,
                "status": "REVISAO_MANUAL",
                "motivo": f"CID identificado, mas nome completo diverge do beneficiário ({match_score}% de similaridade).",
                "score": 40,
            }

    return {
        "ok": True,
        "status": "APROVADO_IA",
        "motivo": f"CID identificado: {cid_found.group(1)} e Titularidade validada.",
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


def _normalizar_texto(texto: str) -> str:
    """Remove acentos, converte para minúsculo e limpa pontuações para o Fuzzy Match."""
    if not texto:
        return ""
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^a-z0-9\s]', '', texto.lower()).strip()

def validate_address(
    text: str, 
    responsible_names_list: list[str],
    logradouro_banco: str = "",
    numero_banco: str = "",
    cep_banco: str = ""
) -> dict:
    body = text.upper()
    body_norm = _normalizar_texto(text)

    erros = []

    # 1. Regra de Negócio: Mogi das Cruzes
    cidade_ok = "MOGI DAS CRUZES" in body or "MOGI" in body_norm
    if not cidade_ok:
        erros.append("Comprovante não pertence a Mogi das Cruzes.")

    # 2. Regra de Negócio: Emissão < 90 dias
    date_matches = re.findall(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", body)
    now = timezone.localdate()
    date_ok = False
    parsed_dates = []
    for date_str in date_matches:
        try:
            dt = date_parser.parse(date_str, dayfirst=True).date()
            parsed_dates.append(dt.isoformat())
            if 0 <= (now - dt).days <= 90:
                date_ok = True
                break  # Uma data válida já é suficiente
        except Exception:
            continue
            
    if not date_ok:
        erros.append("Nenhuma data de emissão válida nos últimos 90 dias.")

    # 3. Validação do Titular (Fuzzy)
    names = [n.upper() for n in (responsible_names_list or []) if n]
    best_name_score = 0
    matched_name = None
    for name in names:
        score = fuzz.partial_ratio(name, body)
        if score > best_name_score:
            best_name_score = score
            matched_name = name

    name_ok = bool(names) and best_name_score >= 80
    if not name_ok:
        erros.append(f"Titular divergente (Score: {best_name_score}).")

    # 4. Cross-Reference com a Solicitação (Fuzzy e Regex)
    logradouro_norm = _normalizar_texto(logradouro_banco)
    score_logradouro = fuzz.partial_ratio(logradouro_norm, body_norm) if logradouro_norm else 0
    logradouro_ok = score_logradouro >= 75  # 75% de similaridade é a margem de segurança
    
    if not logradouro_ok:
        erros.append(f"Logradouro divergente da solicitação (Score: {score_logradouro}).")

    # Bônus: Extração de CEP e Número para auditoria/logs
    cep_clean = re.sub(r'\D', '', cep_banco) if cep_banco else ""
    cep_encontrado = bool(cep_clean and cep_clean in re.sub(r'\D', '', body))
    
    numero_clean = re.sub(r'\D', '', str(numero_banco)) if numero_banco else ""
    numero_encontrado = bool(numero_clean and numero_clean in re.sub(r'\D', '', body))

    # APROVAÇÃO: Exige Data, Cidade, Titular e Logradouro
    is_aprovado = date_ok and cidade_ok and name_ok and logradouro_ok

    if not is_aprovado:
        return {
            "ok": False,
            "status": "REVISAO_MANUAL",
            "motivo": " | ".join(erros),
            "score_nome": best_name_score,
            "score_logradouro": score_logradouro,
            "cep_encontrado": cep_encontrado,
            "numero_encontrado": numero_encontrado,
            "datas_encontradas": parsed_dates,
        }

    return {
        "ok": True,
        "status": "APROVADO_IA",
        "motivo": "Comprovante validado: Mogi das Cruzes, data recente e endereço cruzado com a solicitação.",
        "score_nome": best_name_score,
        "nome_encontrado": matched_name,
        "score_logradouro": score_logradouro,
        "cep_encontrado": cep_encontrado,
        "numero_encontrado": numero_encontrado,
        "datas_encontradas": parsed_dates,
    }