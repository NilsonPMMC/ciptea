from __future__ import annotations

import os
import json
import logging
import unicodedata
from datetime import datetime
from time import perf_counter

from celery import chain, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

from .ai_validators import validate_address, validate_identity, validate_laudo
from .document_classifier import assess_expected_document
from .document_features import extract_document_features
from .models import Documento, Solicitacao, ValidacaoDocumentoIA

logger = logging.getLogger(__name__)

FEATURE_CONF_APPROVE_MIN = int(os.getenv("FEATURE_CONF_APPROVE_MIN", "75"))
FEATURE_CONF_ASSIST_MIN = int(os.getenv("FEATURE_CONF_ASSIST_MIN", "60"))
PIPELINE_VERSION = os.getenv("IA_PIPELINE_VERSION", "2026-05-wave4-multi-rg")
IA_TASK_SOFT_TIME_LIMIT = int(os.getenv("IA_TASK_SOFT_TIME_LIMIT", "240"))
IA_TASK_TIME_LIMIT = int(os.getenv("IA_TASK_TIME_LIMIT", "300"))
IA_DOC_STEP_SOFT_TIME_LIMIT = int(os.getenv("IA_DOC_STEP_SOFT_TIME_LIMIT", "180"))
IA_DOC_STEP_TIME_LIMIT = int(os.getenv("IA_DOC_STEP_TIME_LIMIT", "240"))
FEATURE_DECISION_ENFORCE = os.getenv("FEATURE_DECISION_ENFORCE", "0").strip().lower() in {"1", "true", "yes", "on"}
IA_FAST_PATH = os.getenv("IA_FAST_PATH", "0").strip().lower() in {"1", "true", "yes", "on"}
IA_FAST_PATH_MIN_TEXT_LEN = int(os.getenv("IA_FAST_PATH_MIN_TEXT_LEN", "120"))

# Removemos o RESPONSAVEL daqui, pois agora ele é mapeado dinamicamente
DOC_STEP_MAP = {
    "LAUDO": {"db_tipo": "LAUDO", "log_key": "laudo", "expected": "LAUDO"},
    "IDENTIDADE": {"db_tipo": "RG_BENEF", "log_key": "identidade", "expected": "RG_BENEF"},
    "ENDERECO": {"db_tipo": "COMP_RES", "log_key": "endereco", "expected": "COMP_RES"},
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

def _obter_log_seguro(validacao: ValidacaoDocumentoIA, request_id=None, solicitacao_id=None, init_if_empty=False) -> dict:
    log_raw = validacao.log_ia
    if isinstance(log_raw, str):
        try:
            log_dict = json.loads(log_raw)
        except Exception:
            log_dict = {}
    else:
        log_dict = log_raw if isinstance(log_raw, dict) else {}
        
    if not log_dict and init_if_empty and request_id and solicitacao_id:
        return _init_log(request_id, solicitacao_id)
    return log_dict

def _save_validacao(validacao: ValidacaoDocumentoIA, log: dict, status_validacao: str = "PROCESSANDO"):
    validacao.status_validacao = status_validacao
    validacao.log_ia = log
    validacao.save(update_fields=["status_validacao", "log_ia", "atualizado_em"])

def _get_dict(field_value):
    if isinstance(field_value, dict):
        return field_value
    if isinstance(field_value, str):
        try:
            return json.loads(field_value)
        except Exception:
            pass
    return {}

def _etapas_para_reprocessar(validacao: ValidacaoDocumentoIA, documentos_atuais: dict) -> list[str]:
    # Lógica agnóstica: compara qualquer dicionário de documentos (sejam models.Documento ou models.Responsavel)
    log_atual = _get_dict(validacao.log_ia)
    etapas_log = _get_dict(log_atual.get("etapas"))
    orq_log = _get_dict(etapas_log.get("orquestracao"))
    
    ids_anteriores = orq_log.get("doc_ids_processados") or orq_log.get("doc_ids_alvo") or {}
    arqs_anteriores = orq_log.get("doc_arquivos_processados") or orq_log.get("doc_arquivos_alvo") or {}

    etapas = []
    for etapa, doc_obj in documentos_atuais.items():
        if not doc_obj:
            continue
            
        # Pega o arquivo seja da tabela Documento ou Responsavel
        arquivo = getattr(doc_obj, 'documento_identidade', getattr(doc_obj, 'arquivo', None))
        if not arquivo:
            continue
            
        id_atual = str(doc_obj.id)
        arq_atual = str(arquivo.name)
        
        id_anterior_str = str(ids_anteriores.get(etapa)) if ids_anteriores.get(etapa) is not None else None
        arq_anterior_str = str(arqs_anteriores.get(etapa)) if arqs_anteriores.get(etapa) is not None else None
        
        if (not id_anterior_str) or (id_atual != id_anterior_str) or (arq_atual != arq_anterior_str):
            logger.info(f"[CIPTEA-DELTA] Etapa '{etapa}' reprocessada. ID({id_atual} vs {id_anterior_str}) | ARQ({arq_atual} vs {arq_anterior_str})")
            etapas.append(etapa)
        else:
            logger.info(f"[CIPTEA-DELTA] Etapa '{etapa}' ignorada. Arquivo intocado.")
            
    return etapas

def _run_validator_for_step(k: str, solicitacao: Solicitacao, ocr: dict) -> dict:
    text = ocr.get("text", "")
    
    if k == "laudo":
        return validate_laudo(text)
        
    if k == "identidade":
        return validate_identity(
            text,
            expected_name=solicitacao.beneficiario.nome_completo,
            expected_cpf=solicitacao.beneficiario.cpf,
            cpf_candidates=ocr.get("cpf_candidates") or [],
            expected_birth_date=solicitacao.beneficiario.data_nascimento,
        )
        
    if k == "endereco":
        beneficiario = solicitacao.beneficiario
        nomes_aceitos = list(beneficiario.responsaveis.values_list("nome", flat=True))
        if beneficiario.nome_completo:
            nomes_aceitos.append(beneficiario.nome_completo)
            
        return validate_address(
            text=text,
            responsible_names_list=nomes_aceitos,
            logradouro_banco=beneficiario.logradouro,
            numero_banco=beneficiario.numero,
            cep_banco=beneficiario.cep
        )
        
    # Tratamento dinâmico para os N Responsáveis
    if k.startswith("responsavel_"):
        idx = int(k.split("_")[1])
        try:
            resp = solicitacao.beneficiario.responsaveis.all().order_by("id")[idx]
            
            # NOVO: Bypass inteligente para Próprio Beneficiário
            if resp.perfil == 'PROPRIO':
                return {
                    "ok": True, 
                    "status": "APROVADO_IA", 
                    "motivo": "Autovalidado (Próprio Beneficiário).", 
                    "score": 100
                }
                
            return validate_identity(
                text,
                expected_name=resp.nome,
                expected_cpf=resp.cpf,
                cpf_candidates=ocr.get("cpf_candidates") or [],
                expected_birth_date=resp.data_nascimento,
            )
        except IndexError:
            return {"ok": False, "status": "REVISAO_MANUAL", "motivo": "Dados do responsável não encontrados."}

def _usar_classificador_completo(ocr: dict, result: dict) -> bool:
    if not IA_FAST_PATH:
        return True
    text_len = len((ocr.get("text") or "").strip())
    if text_len < IA_FAST_PATH_MIN_TEXT_LEN:
        return True
    if not bool(result.get("ok")):
        return True
    return False

@shared_task(bind=True, soft_time_limit=IA_DOC_STEP_SOFT_TIME_LIMIT, time_limit=IA_DOC_STEP_TIME_LIMIT, autoretry_for=(SoftTimeLimitExceeded,), retry_backoff=True, retry_kwargs={"max_retries": 1})
def process_ciptea_document_step(self, solicitacao_id: int, etapa: str):
    from .ai_services import extract_text_from_document

    try:
        solicitacao = Solicitacao.objects.select_related("beneficiario").get(id=solicitacao_id)
        validacao = ValidacaoDocumentoIA.objects.get(solicitacao=solicitacao)
    except (Solicitacao.DoesNotExist, ValidacaoDocumentoIA.DoesNotExist):
        return {"ok": False, "motivo": "Solicitacao/validacao nao encontrada."}

    log = _obter_log_seguro(validacao, self.request.id, solicitacao_id, init_if_empty=True)
    etapas = log.setdefault("etapas", {})
    etapas.setdefault("ocr", {"ok": True, "detalhes": {}})
    etapas.setdefault("classificacao_documento", {})
    etapas.setdefault("features_documento", {})
    etapas.setdefault("validacao", {})
    timings = log.setdefault("timings_ms", {})
    
    t0 = perf_counter()

    # Mapeamento Dinâmico (Tabela Fixa vs Tabela Responsável)
    if etapa.startswith("RESPONSAVEL_"):
        idx = int(etapa.split("_")[1])
        try:
            resp_obj = solicitacao.beneficiario.responsaveis.all().order_by("id")[idx]
            arquivo_fisico = resp_obj.documento_identidade
            expected_kind = "RG_RESP"
            k = f"responsavel_{idx}"
            doc_ausente_msg = f"Documento do responsável {idx+1} ausente."
        except IndexError:
            return {"ok": False, "motivo": "Índice de responsável inválido."}
    else:
        cfg = DOC_STEP_MAP.get(etapa)
        if not cfg:
            return {"ok": False, "motivo": f"Etapa desconhecida: {etapa}"}
        doc_obj = _latest_doc(solicitacao, cfg["db_tipo"])
        arquivo_fisico = doc_obj.arquivo if doc_obj else None
        expected_kind = cfg["expected"]
        k = cfg["log_key"]
        doc_ausente_msg = f"Documento {cfg['db_tipo']} ausente."

    try:
        if not arquivo_fisico:
            etapas["ocr"]["ok"] = False
            etapas["ocr"]["detalhes"][k] = {"ok": False, "motivo": doc_ausente_msg}
            etapas["validacao"][k] = {"ok": False, "motivo": "Documento ausente para análise."}
            timings[f"{k}_total"] = int((perf_counter() - t0) * 1000)
            _save_validacao(validacao, log)
            
            # Se for Responsável, marca na tabela dele também
            if etapa.startswith("RESPONSAVEL_"):
                resp_obj.status_documento = 'REJEITADO'
                resp_obj.motivo_rejeicao_documento = 'Documento ausente.'
                resp_obj.save(update_fields=['status_documento', 'motivo_rejeicao_documento'])
                
            return {"ok": False, "etapa": etapa}

        ocr = extract_text_from_document(arquivo_fisico.path, document_kind=expected_kind)
        etapas["ocr"]["detalhes"][k] = ocr
        
        if not ocr.get("ok"):
            etapas["ocr"]["ok"] = False
            etapas["validacao"][k] = {"ok": False, "motivo": "OCR inconclusivo para este documento."}
            timings[f"{k}_total"] = int((perf_counter() - t0) * 1000)
            _save_validacao(validacao, log)
            
            if etapa.startswith("RESPONSAVEL_"):
                resp_obj.status_documento = 'REJEITADO'
                resp_obj.motivo_rejeicao_documento = 'OCR Inconclusivo (Foto ruim).'
                resp_obj.save(update_fields=['status_documento', 'motivo_rejeicao_documento'])
                
            return {"ok": False, "etapa": etapa}

        result = _run_validator_for_step(k, solicitacao, ocr)

        if _usar_classificador_completo(ocr, result):
            cls = assess_expected_document(expected_kind, ocr.get("text", ""))
            feat = extract_document_features(expected_kind, cls.get("predicted_type", ""), ocr.get("text", ""))
            cls["strategy"] = "full_classifier"
        else:
            cls = {"predicted_type": expected_kind, "confidence": 1.0, "should_block": False, "strategy": "fast_path_expected_type"}
            feat = extract_document_features(expected_kind, expected_kind, ocr.get("text", ""))

        etapas["classificacao_documento"][k] = cls
        etapas["features_documento"][k] = feat
        etapas["validacao"][k] = result
        timings[f"{k}_total"] = int((perf_counter() - t0) * 1000)
        _save_validacao(validacao, log)
        
        # Salva o resultado direto na tabela do Responsável
        if etapa.startswith("RESPONSAVEL_"):
            resp_obj.status_documento = 'APROVADO' if result.get("ok") else 'REJEITADO'
            resp_obj.motivo_rejeicao_documento = result.get("motivo") or ""
            resp_obj.save(update_fields=['status_documento', 'motivo_rejeicao_documento'])

        return {"ok": bool(result.get("ok")), "etapa": etapa}
        
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        etapas["ocr"]["ok"] = False
        etapas["validacao"][k] = {"ok": False, "motivo": f"Falha na etapa {etapa}: {exc}"}
        log["erro"] = str(exc)
        timings[f"{k}_total"] = int((perf_counter() - t0) * 1000)
        _save_validacao(validacao, log)
        
        if etapa.startswith("RESPONSAVEL_"):
            resp_obj.status_documento = 'REJEITADO'
            resp_obj.motivo_rejeicao_documento = f"Erro no servidor: {str(exc)[:50]}"
            resp_obj.save(update_fields=['status_documento', 'motivo_rejeicao_documento'])
            
        return {"ok": False, "etapa": etapa}

@shared_task(bind=True, soft_time_limit=IA_DOC_STEP_SOFT_TIME_LIMIT, time_limit=IA_DOC_STEP_TIME_LIMIT)
def finalize_ciptea_triagem(self, solicitacao_id: int):
    try:
        solicitacao = Solicitacao.objects.select_related("beneficiario").get(id=solicitacao_id)
        validacao = ValidacaoDocumentoIA.objects.get(solicitacao=solicitacao)
        responsaveis = list(solicitacao.beneficiario.responsaveis.all().order_by("id"))
    except (Solicitacao.DoesNotExist, ValidacaoDocumentoIA.DoesNotExist):
        return {"ok": False, "motivo": "Solicitacao/validacao nao encontrada."}

    log = _obter_log_seguro(validacao, self.request.id, solicitacao_id, init_if_empty=True)
    etapas = log.get("etapas", {})
    val = etapas.get("validacao", {})
    cls = etapas.get("classificacao_documento", {})
    feats = etapas.get("features_documento", {})

    # Features Base
    feature_overall = {
        "laudo": int((feats.get("laudo") or {}).get("overall_feature_confidence", 0)),
        "identidade": int((feats.get("identidade") or {}).get("overall_feature_confidence", 0)),
        "endereco": int((feats.get("endereco") or {}).get("overall_feature_confidence", 0)),
    }
    
    # Features Responsáveis
    for i in range(len(responsaveis)):
        k = f"responsavel_{i}"
        feature_overall[k] = int((feats.get(k) or {}).get("overall_feature_confidence", 0))

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

    base_keys = ["laudo", "identidade", "endereco"]
    resp_keys = [f"responsavel_{i}" for i in range(len(responsaveis))]
    all_keys = base_keys + resp_keys

    should_block = any(bool((cls.get(k) or {}).get("should_block")) for k in all_keys)
    if should_block:
        etapas["classificacao_documento"]["block_reason"] = "Tipo de documento divergente com alta confianca."

    all_ok = all(bool((val.get(k) or {}).get("ok")) for k in all_keys)
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

    orq = etapas.get("orquestracao") if isinstance(etapas.get("orquestracao"), dict) else {}
    if orq.get("doc_ids_alvo"):
        orq["doc_ids_processados"] = orq["doc_ids_alvo"]
    if orq.get("doc_arquivos_alvo"):
        orq["doc_arquivos_processados"] = orq["doc_arquivos_alvo"]

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
    doc_end = _latest_doc(solicitacao, "COMP_RES")
    responsaveis = list(solicitacao.beneficiario.responsaveis.all().order_by("id"))

    log = _obter_log_seguro(validacao, self.request.id, solicitacao_id, init_if_empty=True)
    log["task_id"] = self.request.id
    log["started_at"] = timezone.now().isoformat()
    log.setdefault("timings_ms", {})
    log.setdefault("etapas", {})
    log["etapas"].setdefault("ocr", {"ok": True, "detalhes": {}})
    log["etapas"].setdefault("classificacao_documento", {})
    log["etapas"].setdefault("features_documento", {})
    log["etapas"].setdefault("validacao", {})

    missing = []
    if not doc_laudo: missing.append("Laudo medico")
    if not doc_tea: missing.append("Identificacao TEA")
    if not doc_end: missing.append("Comprovante de endereco")
    
    if missing:
        log["etapas"]["precheck"] = {"ok": False, "motivo": f"Documentos obrigatorios ausentes: {', '.join(missing)}"}
        validacao.log_ia = log
        validacao.status_validacao = "REVISAO_MANUAL"
        validacao.save(update_fields=["status_validacao", "log_ia", "atualizado_em"])
        return {"ok": False, "status_validacao": "REVISAO_MANUAL"}

    # Monta a estrutura dinâmica com Textos/Arquivos base e RGs dos responsáveis
    documentos_atuais = {
        "LAUDO": doc_laudo,
        "IDENTIDADE": doc_tea,
        "ENDERECO": doc_end,
    }
    doc_ids_alvo = {
        "LAUDO": doc_laudo.id,
        "IDENTIDADE": doc_tea.id,
        "ENDERECO": doc_end.id,
    }
    doc_arquivos_alvo = {
        "LAUDO": doc_laudo.arquivo.name if doc_laudo.arquivo else None,
        "IDENTIDADE": doc_tea.arquivo.name if doc_tea.arquivo else None,
        "ENDERECO": doc_end.arquivo.name if doc_end.arquivo else None,
    }

    # Adiciona a lista de responsáveis de forma ilimitada/dinâmica
    for i, resp in enumerate(responsaveis):
        k = f"RESPONSAVEL_{i}"
        documentos_atuais[k] = resp
        doc_ids_alvo[k] = resp.id
        doc_arquivos_alvo[k] = resp.documento_identidade.name if resp.documento_identidade else None

    # O Delta Blindado processa tudo agora
    docs_orquestrados = _etapas_para_reprocessar(validacao, documentos_atuais)

    # Limpa apenas os logs reprocessados
    for etapa in docs_orquestrados:
        if etapa.startswith("RESPONSAVEL_"):
            k = f"responsavel_{etapa.split('_')[1]}"
        else:
            k = DOC_STEP_MAP.get(etapa, {}).get("log_key")
            
        if k:
            (log["etapas"]["ocr"].get("detalhes") or {}).pop(k, None)
            log["etapas"]["classificacao_documento"].pop(k, None)
            log["etapas"]["features_documento"].pop(k, None)
            log["etapas"]["validacao"].pop(k, None)

    log["etapas"]["orquestracao"] = {
        "ok": True,
        "modo": "tarefas-separadas",
        "documentos": docs_orquestrados,
        "doc_ids_alvo": doc_ids_alvo,
        "doc_arquivos_alvo": doc_arquivos_alvo,
    }
    
    validacao.log_ia = log
    validacao.status_validacao = "PROCESSANDO"
    validacao.save(update_fields=["status_validacao", "log_ia", "atualizado_em"])

    steps = [process_ciptea_document_step.si(solicitacao_id, etapa) for etapa in docs_orquestrados]
    steps.append(finalize_ciptea_triagem.si(solicitacao_id))
    fluxo = chain(*steps)
    fluxo.delay()
    
    return {"ok": True, "status_validacao": "PROCESSANDO", "log_ia": log}