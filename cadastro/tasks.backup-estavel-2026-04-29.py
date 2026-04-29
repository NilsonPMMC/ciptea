from __future__ import annotations

import os
from datetime import datetime
from time import perf_counter

from celery import chain, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

from .ai_validators import validate_address, validate_identity, validate_laudo
from .document_classifier import assess_expected_document
from .document_features import extract_document_features
from .models import Documento, Solicitacao, ValidacaoDocumentoIA

FEATURE_CONF_APPROVE_MIN = int(os.getenv("FEATURE_CONF_APPROVE_MIN", "75"))
FEATURE_CONF_ASSIST_MIN = int(os.getenv("FEATURE_CONF_ASSIST_MIN", "60"))
PIPELINE_VERSION = os.getenv("IA_PIPELINE_VERSION", "2026-04-wave3")
IA_TASK_SOFT_TIME_LIMIT = int(os.getenv("IA_TASK_SOFT_TIME_LIMIT", "240"))
IA_TASK_TIME_LIMIT = int(os.getenv("IA_TASK_TIME_LIMIT", "300"))
IA_DOC_STEP_SOFT_TIME_LIMIT = int(os.getenv("IA_DOC_STEP_SOFT_TIME_LIMIT", "180"))
IA_DOC_STEP_TIME_LIMIT = int(os.getenv("IA_DOC_STEP_TIME_LIMIT", "240"))
FEATURE_DECISION_ENFORCE = os.getenv("FEATURE_DECISION_ENFORCE", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

DOC_STEP_MAP = {
    "LAUDO": {"db_tipo": "LAUDO", "log_key": "laudo", "expected": "LAUDO"},
    "IDENTIDADE": {"db_tipo": "RG_BENEF", "log_key": "identidade", "expected": "RG_BENEF"},
    "ENDERECO": {"db_tipo": "COMP_RES", "log_key": "endereco", "expected": "COMP_RES"},
    "RESPONSAVEL": {"db_tipo": "RG_RESP", "log_key": "responsavel", "expected": "RG_RESP"},
}


def _latest_doc(solicitacao: Solicitacao, tipo: str) -> Documento | None:
    return Documento.objects.filter(solicitacao=solicitacao, tipo=tipo).order_by("-id").first()


def _init_log(task_id: str, solicitacao_id: int) -> dict:
    return {
        "task_id": task_id,
        "solicitacao_id": solicitacao_id,
        "started_at": timezone.now().isoformat(),
        "pipeline": {
            "version": PIPELINE_VERSION,
            "mode": "split-by-document",
            "thresholds": {
                "feature_approve_min": FEATURE_CONF_APPROVE_MIN,
                "feature_assist_min": FEATURE_CONF_ASSIST_MIN,
                "feature_enforce": FEATURE_DECISION_ENFORCE,
            },
        },
        "timings_ms": {},
        "etapas": {
            "ocr": {"ok": True, "detalhes": {}},
            "classificacao_documento": {},
            "features_documento": {},
            "validacao": {},
        },
    }


def _save_validacao(validacao: ValidacaoDocumentoIA, log: dict, status_validacao: str = "PROCESSANDO"):
    validacao.status_validacao = status_validacao
    validacao.log_ia = log
    validacao.save(update_fields=["status_validacao", "log_ia", "atualizado_em"])


def _etapas_para_reprocessar(
    validacao: ValidacaoDocumentoIA,
    doc_laudo: Documento | None,
    doc_tea: Documento | None,
    doc_end: Documento | None,
    doc_resp: Documento | None,
) -> list[str]:
    # Primeira execução: processa fluxo completo.
    log_atual = validacao.log_ia if isinstance(validacao.log_ia, dict) else {}
    validacao_previa = (
        ((log_atual.get("etapas") or {}).get("validacao"))
        if isinstance((log_atual.get("etapas") or {}).get("validacao"), dict)
        else {}
    )
    primeira_execucao = not bool(validacao_previa)
    if primeira_execucao:
        etapas = ["LAUDO", "IDENTIDADE", "ENDERECO"]
        if doc_resp:
            etapas.append("RESPONSAVEL")
        return etapas

    # Reprocessamento parcial: apenas documentos reenviados (status PENDENTE).
    etapas = []
    if doc_laudo and doc_laudo.status == "PENDENTE":
        etapas.append("LAUDO")
    if doc_tea and doc_tea.status == "PENDENTE":
        etapas.append("IDENTIDADE")
    if doc_end and doc_end.status == "PENDENTE":
        etapas.append("ENDERECO")
    if doc_resp and doc_resp.status == "PENDENTE":
        etapas.append("RESPONSAVEL")

    # Fallback de segurança: se não identificou nenhum pendente, mantém fluxo completo.
    if not etapas:
        etapas = ["LAUDO", "IDENTIDADE", "ENDERECO"]
        if doc_resp:
            etapas.append("RESPONSAVEL")
    return etapas


def _validate_responsavel_identity(
    text: str,
    responsaveis: list[tuple[str, str, object]],
    cpf_candidates: list[str] | None = None,
) -> dict:
    """
    Valida RG_RESP contra a lista de responsáveis. Aprova se ao menos um responsável bater.
    """
    if not responsaveis:
        return {
            "ok": True,
            "status": "APROVADO_IA",
            "motivo": "Sem responsável cadastrado para validação desta etapa.",
            "score": 100,
            "matched_responsavel": None,
        }

    resultados = []
    for nome, cpf, data_nasc in responsaveis:
        resultados.append(
            validate_identity(
                text,
                expected_name=nome or "",
                expected_cpf=cpf or "",
                cpf_candidates=cpf_candidates or [],
                expected_birth_date=data_nasc,
            )
        )

    aprovados = [r for r in resultados if r.get("ok")]
    if aprovados:
        melhor = max(aprovados, key=lambda r: int(r.get("score", 0) or 0))
        melhor["motivo"] = melhor.get("motivo") or "Documento do responsável validado."
        return melhor

    melhor = max(resultados, key=lambda r: int(r.get("score", 0) or 0)) if resultados else {}
    return {
        **melhor,
        "ok": False,
        "status": "REVISAO_MANUAL",
        "motivo": melhor.get("motivo") or "Documento do responsável com baixa confiança.",
    }


@shared_task(
    bind=True,
    soft_time_limit=IA_DOC_STEP_SOFT_TIME_LIMIT,
    time_limit=IA_DOC_STEP_TIME_LIMIT,
    autoretry_for=(SoftTimeLimitExceeded,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
)
def process_ciptea_document_step(self, solicitacao_id: int, etapa: str):
    from .ai_services import extract_text_from_document

    cfg = DOC_STEP_MAP.get(etapa)
    if not cfg:
        return {"ok": False, "motivo": f"Etapa desconhecida: {etapa}"}
    try:
        solicitacao = Solicitacao.objects.select_related("beneficiario").get(id=solicitacao_id)
        validacao = ValidacaoDocumentoIA.objects.get(solicitacao=solicitacao)
    except (Solicitacao.DoesNotExist, ValidacaoDocumentoIA.DoesNotExist):
        return {"ok": False, "motivo": "Solicitacao/validacao nao encontrada."}

    log = validacao.log_ia if isinstance(validacao.log_ia, dict) else _init_log(self.request.id, solicitacao_id)
    etapas = log.setdefault("etapas", {})
    etapas.setdefault("ocr", {"ok": True, "detalhes": {}})
    etapas.setdefault("classificacao_documento", {})
    etapas.setdefault("features_documento", {})
    etapas.setdefault("validacao", {})
    timings = log.setdefault("timings_ms", {})
    k = cfg["log_key"]
    t0 = perf_counter()

    try:
        doc = _latest_doc(solicitacao, cfg["db_tipo"])
        if not doc:
            etapas["ocr"]["ok"] = False
            etapas["ocr"]["detalhes"][k] = {"ok": False, "motivo": f"Documento {cfg['db_tipo']} ausente."}
            etapas["validacao"][k] = {"ok": False, "motivo": "Documento ausente para análise."}
            timings[f"{k}_total"] = int((perf_counter() - t0) * 1000)
            _save_validacao(validacao, log)
            return {"ok": False, "etapa": etapa}

        ocr = extract_text_from_document(doc.arquivo.path, document_kind=cfg["expected"])
        etapas["ocr"]["detalhes"][k] = ocr
        if not ocr.get("ok"):
            etapas["ocr"]["ok"] = False
            etapas["validacao"][k] = {"ok": False, "motivo": "OCR inconclusivo para este documento."}
            timings[f"{k}_total"] = int((perf_counter() - t0) * 1000)
            _save_validacao(validacao, log)
            return {"ok": False, "etapa": etapa}

        cls = assess_expected_document(cfg["expected"], ocr.get("text", ""))
        etapas["classificacao_documento"][k] = cls
        etapas["features_documento"][k] = extract_document_features(
            cfg["expected"], cls.get("predicted_type", ""), ocr.get("text", "")
        )

        if k == "laudo":
            result = validate_laudo(ocr.get("text", ""))
        elif k == "identidade":
            result = validate_identity(
                ocr.get("text", ""),
                expected_name=solicitacao.beneficiario.nome_completo,
                expected_cpf=solicitacao.beneficiario.cpf,
                cpf_candidates=ocr.get("cpf_candidates") or [],
                expected_birth_date=solicitacao.beneficiario.data_nascimento,
            )
        elif k == "endereco":
            responsaveis = list(solicitacao.beneficiario.responsaveis.values_list("nome", flat=True))
            result = validate_address(ocr.get("text", ""), responsaveis)
        else:
            responsaveis_info = list(
                solicitacao.beneficiario.responsaveis.values_list("nome", "cpf", "data_nascimento")
            )
            result = _validate_responsavel_identity(
                ocr.get("text", ""),
                responsaveis_info,
                cpf_candidates=ocr.get("cpf_candidates") or [],
            )

        etapas["validacao"][k] = result
        timings[f"{k}_total"] = int((perf_counter() - t0) * 1000)
        _save_validacao(validacao, log)
        return {"ok": bool(result.get("ok")), "etapa": etapa}
    except SoftTimeLimitExceeded:
        # Deixa o Celery reprocessar uma vez (warm cache/modelos).
        raise
    except Exception as exc:
        etapas["ocr"]["ok"] = False
        etapas["validacao"][k] = {"ok": False, "motivo": f"Falha na etapa {etapa}: {exc}"}
        log["erro"] = str(exc)
        timings[f"{k}_total"] = int((perf_counter() - t0) * 1000)
        _save_validacao(validacao, log)
        return {"ok": False, "etapa": etapa}


@shared_task(bind=True, soft_time_limit=IA_DOC_STEP_SOFT_TIME_LIMIT, time_limit=IA_DOC_STEP_TIME_LIMIT)
def finalize_ciptea_triagem(self, solicitacao_id: int):
    try:
        solicitacao = Solicitacao.objects.select_related("beneficiario").get(id=solicitacao_id)
        validacao = ValidacaoDocumentoIA.objects.get(solicitacao=solicitacao)
    except (Solicitacao.DoesNotExist, ValidacaoDocumentoIA.DoesNotExist):
        return {"ok": False, "motivo": "Solicitacao/validacao nao encontrada."}

    log = validacao.log_ia if isinstance(validacao.log_ia, dict) else _init_log(self.request.id, solicitacao_id)
    etapas = log.get("etapas", {})
    val = etapas.get("validacao", {})
    cls = etapas.get("classificacao_documento", {})
    feats = etapas.get("features_documento", {})

    feature_overall = {
        "laudo": int((feats.get("laudo") or {}).get("overall_feature_confidence", 0)),
        "identidade": int((feats.get("identidade") or {}).get("overall_feature_confidence", 0)),
        "endereco": int((feats.get("endereco") or {}).get("overall_feature_confidence", 0)),
    }
    has_doc_resp = bool(getattr(validacao, "arquivo_doc_responsavel", None))
    if has_doc_resp:
        feature_overall["responsavel"] = int((feats.get("responsavel") or {}).get("overall_feature_confidence", 0))
    min_feature_conf = min(feature_overall.values()) if feature_overall else 0
    if min_feature_conf >= FEATURE_CONF_APPROVE_MIN:
        decisao_operacional = "APROVACAO_SUGERIDA"
    elif min_feature_conf >= FEATURE_CONF_ASSIST_MIN:
        decisao_operacional = "REVISAO_ASSISTIDA"
    else:
        decisao_operacional = "REVISAO_MANUAL"

    etapas["decisao_operacional_features"] = {
        "overall_por_documento": feature_overall,
        "min_feature_confidence": min_feature_conf,
        "thresholds": {"approve_min": FEATURE_CONF_APPROVE_MIN, "assist_min": FEATURE_CONF_ASSIST_MIN},
        "decisao_operacional": decisao_operacional,
        "enforced": FEATURE_DECISION_ENFORCE,
    }

    block_keys = ("laudo", "identidade", "endereco", "responsavel") if has_doc_resp else ("laudo", "identidade", "endereco")
    should_block = any(bool((cls.get(k) or {}).get("should_block")) for k in block_keys)
    if should_block:
        etapas["classificacao_documento"]["block_reason"] = "Tipo de documento divergente com alta confianca."

    required_keys = ("laudo", "identidade", "endereco", "responsavel") if has_doc_resp else ("laudo", "identidade", "endereco")
    all_ok = all(bool((val.get(k) or {}).get("ok")) for k in required_keys)
    ocr_ok = bool((etapas.get("ocr") or {}).get("ok", True))
    feature_gate_manual = FEATURE_DECISION_ENFORCE and decisao_operacional == "REVISAO_MANUAL"
    status_final = "APROVADO_IA" if all_ok and ocr_ok and not should_block and not feature_gate_manual else "REVISAO_MANUAL"

    if feature_gate_manual:
        etapas["validacao"]["feature_gate"] = "Decisão operacional por features exigiu revisão manual."

    if log.get("started_at"):
        try:
            started = datetime.fromisoformat(log["started_at"])
            if started.tzinfo is None:
                started = timezone.make_aware(started, timezone.get_current_timezone())
            log.setdefault("timings_ms", {})["total"] = int((timezone.now() - started).total_seconds() * 1000)
        except Exception:
            pass

    _save_validacao(validacao, log, status_validacao=status_final)
    return {"ok": status_final == "APROVADO_IA", "status_validacao": status_final, "log_ia": log}


@shared_task(bind=True, soft_time_limit=IA_TASK_SOFT_TIME_LIMIT, time_limit=IA_TASK_TIME_LIMIT)
def process_ciptea_documents(self, solicitacao_id: int):
    try:
        solicitacao = Solicitacao.objects.select_related("beneficiario").get(id=solicitacao_id)
    except Solicitacao.DoesNotExist:
        return {"ok": False, "motivo": "Solicitacao nao encontrada."}

    validacao, _ = ValidacaoDocumentoIA.objects.get_or_create(solicitacao=solicitacao)
    doc_laudo = _latest_doc(solicitacao, "LAUDO")
    doc_tea = _latest_doc(solicitacao, "RG_BENEF")
    doc_resp = _latest_doc(solicitacao, "RG_RESP")
    doc_end = _latest_doc(solicitacao, "COMP_RES")
    validacao.arquivo_laudo_medico = doc_laudo.arquivo if doc_laudo else None
    validacao.arquivo_doc_tea = doc_tea.arquivo if doc_tea else None
    validacao.arquivo_doc_responsavel = doc_resp.arquivo if doc_resp else None
    validacao.arquivo_comprovante_endereco = doc_end.arquivo if doc_end else None

    log = validacao.log_ia if isinstance(validacao.log_ia, dict) else _init_log(self.request.id, solicitacao_id)
    log["task_id"] = self.request.id
    log["started_at"] = timezone.now().isoformat()
    log.setdefault("timings_ms", {})
    log.setdefault("etapas", {})
    log["etapas"].setdefault("ocr", {"ok": True, "detalhes": {}})
    log["etapas"].setdefault("classificacao_documento", {})
    log["etapas"].setdefault("features_documento", {})
    log["etapas"].setdefault("validacao", {})
    missing = []
    if not doc_laudo:
        missing.append("Laudo medico")
    if not doc_tea:
        missing.append("Documento de identificacao TEA")
    if not doc_end:
        missing.append("Comprovante de endereco")
    if missing:
        log["etapas"]["precheck"] = {"ok": False, "motivo": f"Documentos obrigatorios ausentes: {', '.join(missing)}"}
        validacao.log_ia = log
        validacao.status_validacao = "REVISAO_MANUAL"
        validacao.save(
            update_fields=[
                "status_validacao",
                "log_ia",
                "arquivo_laudo_medico",
                "arquivo_doc_tea",
                "arquivo_doc_responsavel",
                "arquivo_comprovante_endereco",
                "atualizado_em",
            ]
        )
        return {"ok": False, "status_validacao": "REVISAO_MANUAL", "log_ia": log}

    docs_orquestrados = _etapas_para_reprocessar(validacao, doc_laudo, doc_tea, doc_end, doc_resp)

    # Limpa no log apenas os documentos que serão reprocessados.
    key_map = {
        "LAUDO": "laudo",
        "IDENTIDADE": "identidade",
        "ENDERECO": "endereco",
        "RESPONSAVEL": "responsavel",
    }
    for etapa in docs_orquestrados:
        k = key_map.get(etapa)
        if not k:
            continue
        (log["etapas"]["ocr"].get("detalhes") or {}).pop(k, None)
        log["etapas"]["classificacao_documento"].pop(k, None)
        log["etapas"]["features_documento"].pop(k, None)
        log["etapas"]["validacao"].pop(k, None)

    log["etapas"]["orquestracao"] = {
        "ok": True,
        "modo": "tarefas-separadas",
        "documentos": docs_orquestrados,
    }
    validacao.log_ia = log
    validacao.status_validacao = "PROCESSANDO"
    validacao.save(
        update_fields=[
            "status_validacao",
            "log_ia",
            "arquivo_laudo_medico",
            "arquivo_doc_tea",
            "arquivo_doc_responsavel",
            "arquivo_comprovante_endereco",
            "atualizado_em",
        ]
    )

    steps = [process_ciptea_document_step.si(solicitacao_id, etapa) for etapa in docs_orquestrados]
    steps.append(finalize_ciptea_triagem.si(solicitacao_id))
    fluxo = chain(*steps)
    fluxo.delay()
    return {"ok": True, "status_validacao": "PROCESSANDO", "log_ia": log}
