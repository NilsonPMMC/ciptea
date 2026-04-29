from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
except Exception:  # pragma: no cover - ambiente sem dependencias IA
    DocumentFile = None
    ocr_predictor = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - ambiente sem dependencias IA
    SentenceTransformer = None

try:
    import pytesseract
except Exception:  # pragma: no cover - ambiente sem dependencias IA
    pytesseract = None

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover - ambiente sem dependencias IA
    cv2 = None
    np = None


# Carregamento global: evita re-instanciar a cada request/task.
OCR_MODEL = ocr_predictor(pretrained=True) if ocr_predictor else None
SEMANTIC_MODEL = SentenceTransformer("all-MiniLM-L6-v2") if SentenceTransformer else None
OCR_MIN_TEXT_CHARS = int(os.getenv("OCR_MIN_TEXT_CHARS", "100"))
OCR_FALLBACK_TESSERACT = os.getenv("OCR_FALLBACK_TESSERACT", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OCR_TESSERACT_LANG = os.getenv("OCR_TESSERACT_LANG", "por+osd")
OCR_MIN_ALPHA_RATIO = float(os.getenv("OCR_MIN_ALPHA_RATIO", "0.45"))
OCR_MIN_LONG_TOKEN_RATIO = float(os.getenv("OCR_MIN_LONG_TOKEN_RATIO", "0.20"))
OCR_TESSERACT_ROTATIONS = tuple(
    int(v.strip())
    for v in os.getenv("OCR_TESSERACT_ROTATIONS", "0,90,180,270").split(",")
    if v.strip()
)
OCR_FAST_ROTATIONS = tuple(
    int(v.strip())
    for v in os.getenv("OCR_FAST_ROTATIONS", "0,180").split(",")
    if v.strip()
)
OCR_EARLY_STOP_SCORE = float(os.getenv("OCR_EARLY_STOP_SCORE", "4.3"))
OCR_TESSERACT_PSMS = tuple(
    v.strip()
    for v in os.getenv("OCR_TESSERACT_PSMS", "6,11").split(",")
    if v.strip()
)
OCR_IDENTITY_KEYWORD_BONUS = float(os.getenv("OCR_IDENTITY_KEYWORD_BONUS", "0.25"))


def _normalize_document_kind(document_kind: str | None) -> str:
    return (document_kind or "").strip().upper()


def preprocess_image(image_path: str | Path) -> str:
    """
    Prepara imagem para OCR: reduz timbre colorido (grayscale + autocontraste),
    leve nitidez, limita o maior lado a 1500px e grava *_pre* ao lado do original.

    Sem isso, laudos com papel timbrado/logos costumam gerar lixo no docTR (CRNN).
    """
    path = Path(image_path)
    with Image.open(path) as img:
        img = img.convert("RGB")
        # Cabeçalhos roxos/azuis e logos saturam o detector de texto
        gray = ImageOps.autocontrast(img.convert("L"), cutoff=1)
        img = gray.convert("RGB")
        img = ImageEnhance.Sharpness(img).enhance(1.12)

        # Limite de pixels no maior lado (RAM no worker / Celery).
        max_px = 1500
        max_side = max(img.size)
        if max_side > max_px:
            scale = max_px / float(max_side)
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        target_path = path.with_name(f"{path.stem}_pre{path.suffix}")
        img.save(target_path, optimize=True, quality=92)
    return str(target_path)


def _contains_cid_hint(text: str) -> bool:
    body = (text or "").upper().replace(" ", "")
    body = body.replace("O", "0")
    return bool(re.search(r"F[\W_]*8[\W_]*4(?:[\W_]*\d+)?", body) or re.search(r"6[\W_]*A[\W_]*0[\W_]*2(?:[\W_]*\d+)?", body))


def _contains_cpf_hint(text: str) -> bool:
    body = (text or "").upper()
    normalized = (
        body.replace("O", "0")
        .replace("I", "1")
        .replace("L", "1")
        .replace("S", "5")
        .replace("B", "8")
    )
    return bool(re.search(r"\d{3}\D?\d{3}\D?\d{3}\D?\d{2}", normalized))


def _cpf_candidates_from_text(text: str) -> list[str]:
    body = (text or "").upper()
    normalized = (
        body.replace("O", "0")
        .replace("I", "1")
        .replace("L", "1")
        .replace("S", "5")
        .replace("B", "8")
    )
    found = re.findall(r"\d{3}\D?\d{3}\D?\d{3}\D?\d{2}", normalized)
    candidates: set[str] = set()
    for token in found:
        digits = re.sub(r"\D", "", token)
        if len(digits) == 11:
            candidates.add(digits)
    return sorted(candidates)


def _identity_keyword_hits(text: str) -> int:
    body = (text or "").upper()
    tokens = ("NOME", "CPF", "RG", "FILIACAO", "NASCIMENTO", "DOCUMENTO")
    return sum(1 for t in tokens if t in body)


def _text_quality_metrics(text: str) -> dict[str, float | bool]:
    body = (text or "").strip()
    length = len(body)
    if length == 0:
        return {
            "length": 0.0,
            "alpha_ratio": 0.0,
            "long_token_ratio": 0.0,
            "cid_hint": False,
            "quality_score": 0.0,
            "quality_ok": False,
        }
    alnum_chars = [c for c in body if c.isalnum()]
    alpha_ratio = (
        sum(1 for c in alnum_chars if c.isalpha()) / float(len(alnum_chars))
        if alnum_chars
        else 0.0
    )
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]+", body)
    long_tokens = [t for t in tokens if sum(ch.isalpha() for ch in t) >= 3]
    long_token_ratio = len(long_tokens) / float(len(tokens)) if tokens else 0.0
    cid_hint = _contains_cid_hint(body)
    cpf_hint = _contains_cpf_hint(body)
    length_score = min(length / float(max(OCR_MIN_TEXT_CHARS, 1)), 2.0)
    quality_score = (
        (1.6 if cid_hint else 0.0)
        + (0.9 if cpf_hint else 0.0)
        + (1.2 * min(alpha_ratio, 1.0))
        + (1.2 * min(long_token_ratio, 1.0))
        + (0.6 * length_score)
    )
    quality_ok = (
        length >= OCR_MIN_TEXT_CHARS
        and alpha_ratio >= OCR_MIN_ALPHA_RATIO
        and long_token_ratio >= OCR_MIN_LONG_TOKEN_RATIO
    ) or cid_hint
    return {
        "length": float(length),
        "alpha_ratio": alpha_ratio,
        "long_token_ratio": long_token_ratio,
        "cid_hint": cid_hint,
        "cpf_hint": cpf_hint,
        "quality_score": quality_score,
        "quality_ok": quality_ok,
    }


def _candidate_rank(metrics: dict[str, float | bool], text: str, document_kind: str) -> tuple[float, int]:
    score = float(metrics.get("quality_score", 0.0) or 0.0)
    if document_kind in {"RG_BENEF", "RG_RESP"}:
        score += _identity_keyword_hits(text) * OCR_IDENTITY_KEYWORD_BONUS
        if metrics.get("cpf_hint"):
            score += 1.0
    return (score, len(text or ""))


def _extract_lines_from_doctr_export(export: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for page in export.get("pages", []):
        for block in page.get("blocks", []):
            for line in block.get("lines", []):
                words = [w.get("value", "").strip() for w in line.get("words", []) if w.get("value")]
                if words:
                    lines.append(" ".join(words))
    return lines


def _extract_text_with_doctr(document_path: str | Path) -> dict[str, Any]:
    path = Path(document_path)
    if OCR_MODEL is None or DocumentFile is None:
        return {
            "text": "",
            "ok": False,
            "motivo": "Modelo OCR (docTR) indisponivel no ambiente.",
            "engine": "doctr",
            "preprocessed_path": str(path),
        }

    processed_path = str(path)
    if path.suffix.lower() != ".pdf":
        processed_path = preprocess_image(path)
        doc = DocumentFile.from_images(processed_path)
    else:
        doc = DocumentFile.from_pdf(str(path))
    result = OCR_MODEL(doc)
    export = result.export()
    text = "\n".join(_extract_lines_from_doctr_export(export)).strip()
    quality = _text_quality_metrics(text)
    return {
        "text": text,
        "ok": True,
        "motivo": "",
        "pages": len(export.get("pages", [])),
        "preprocessed_path": processed_path,
        "engine": "doctr",
        "quality_ok": bool(quality["quality_ok"]),
        "quality_score": quality["quality_score"],
        "cid_hint": bool(quality["cid_hint"]),
        "cpf_hint": bool(quality["cpf_hint"]),
        "alpha_ratio": quality["alpha_ratio"],
        "long_token_ratio": quality["long_token_ratio"],
    }


def _build_tesseract_variants(base: Image.Image, document_kind: str) -> list[tuple[str, Image.Image]]:
    variants: list[tuple[str, Image.Image]] = [("base", base.copy())]
    if document_kind == "LAUDO":
        # Para laudo escaneado/fotografado: aumenta legibilidade para OCR clássico.
        g = ImageOps.autocontrast(base.convert("L"), cutoff=2)
        variants.append(("gray_autocontrast", g.convert("RGB")))
        up2 = g.resize((g.width * 2, g.height * 2), Image.Resampling.LANCZOS)
        variants.append(("up2x", up2.convert("RGB")))
        denoise = up2.filter(ImageFilter.MedianFilter(size=3))
        variants.append(("up2x_denoise", denoise.convert("RGB")))
        binary = denoise.point(lambda p: 255 if p > 165 else 0, mode="1").convert("RGB")
        variants.append(("up2x_denoise_binary", binary))
    elif document_kind in {"RG_BENEF", "RG_RESP"}:
        g = ImageOps.autocontrast(base.convert("L"), cutoff=1)
        variants.append(("gray_autocontrast", g.convert("RGB")))
        denoise = g.filter(ImageFilter.MedianFilter(size=3))
        variants.append(("gray_denoise", denoise.convert("RGB")))
        binary = denoise.point(lambda p: 255 if p > 175 else 0, mode="1").convert("RGB")
        variants.append(("gray_binary", binary))
        variants.append(("flip_h", ImageOps.mirror(base.convert("RGB"))))
        variants.append(("flip_v", ImageOps.flip(base.convert("RGB"))))
        for name, img in _build_identity_opencv_variants(base):
            variants.append((name, img))
    return variants


def _build_identity_opencv_variants(base: Image.Image) -> list[tuple[str, Image.Image]]:
    """
    Variantes com OpenCV para RG:
    - deskew aproximado
    - threshold adaptativo
    - morfologia leve para reforcar caracteres
    """
    if cv2 is None or np is None:
        return []
    try:
        rgb = np.array(base.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        adapt = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        morph = cv2.morphologyEx(adapt, cv2.MORPH_OPEN, kernel)

        inv = cv2.bitwise_not(adapt)
        coords = np.column_stack(np.where(inv > 0))
        angle = 0.0
        if coords.shape[0] > 200:
            raw_angle = cv2.minAreaRect(coords)[-1]
            angle = -(90 + raw_angle) if raw_angle < -45 else -raw_angle
        h, w = adapt.shape[:2]
        matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        deskew = cv2.warpAffine(
            adapt,
            matrix,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

        variants: list[tuple[str, Image.Image]] = [
            ("cv_adaptive", Image.fromarray(adapt).convert("RGB")),
            ("cv_morph_open", Image.fromarray(morph).convert("RGB")),
            ("cv_deskew", Image.fromarray(deskew).convert("RGB")),
        ]
        return variants
    except Exception:
        return []


def _extract_rg_roi_cpf_candidates(image: Image.Image) -> list[str]:
    """
    OCR focado em região provável do CPF no RG/CIN.
    Retorna apenas candidatos em formato de 11 dígitos.
    """
    if cv2 is None or np is None:
        return []
    try:
        rgb = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape[:2]
        y1, y2 = int(h * 0.50), int(h * 0.95)
        x1, x2 = int(w * 0.15), int(w * 0.98)
        roi = gray[y1:y2, x1:x2]
        if roi.size == 0:
            return []

        roi = cv2.GaussianBlur(roi, (3, 3), 0)
        thr = cv2.adaptiveThreshold(
            roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9
        )
        up = cv2.resize(thr, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        pil_roi = Image.fromarray(up).convert("RGB")

        ocr_texts: list[str] = []
        if pytesseract is not None:
            for psm in OCR_TESSERACT_PSMS:
                config = f"--psm {psm} -c tessedit_char_whitelist=0123456789.-/"
                ocr_texts.append(
                    pytesseract.image_to_string(pil_roi, lang=OCR_TESSERACT_LANG, config=config) or ""
                )
        else:
            with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                pil_roi.save(tmp.name, format="PNG")
                for psm in OCR_TESSERACT_PSMS:
                    proc = subprocess.run(
                        [
                            "tesseract",
                            tmp.name,
                            "stdout",
                            "-l",
                            OCR_TESSERACT_LANG,
                            "--psm",
                            str(psm),
                            "-c",
                            "tessedit_char_whitelist=0123456789.-/",
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if proc.returncode == 0 and proc.stdout:
                        ocr_texts.append(proc.stdout)

        candidates: set[str] = set()
        for text in ocr_texts:
            for cpf in _cpf_candidates_from_text(text):
                candidates.add(cpf)
        return sorted(candidates)
    except Exception:
        return []


def _candidate_reaches_early_stop(metrics: dict[str, float | bool]) -> bool:
    score = float(metrics.get("quality_score", 0.0) or 0.0)
    return bool(metrics.get("cid_hint", False)) and score >= OCR_EARLY_STOP_SCORE


def _extract_text_with_tesseract(image_path: str | Path, document_kind: str = "") -> dict[str, Any]:
    path = Path(image_path)
    if path.suffix.lower() == ".pdf":
        return {
            "text": "",
            "ok": False,
            "motivo": "Fallback Tesseract habilitado apenas para imagem (PDF ainda nao suportado).",
            "engine": "tesseract",
            "preprocessed_path": str(path),
        }

    processed_path = preprocess_image(path)
    image = Image.open(processed_path)
    try:
        kind = _normalize_document_kind(document_kind)

        def run_ocr(img: Image.Image, psm: str) -> str:
            if pytesseract is not None:
                config = f"--psm {psm}"
                return (pytesseract.image_to_string(img, lang=OCR_TESSERACT_LANG, config=config) or "").strip()
            with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                img.save(tmp.name, format="PNG")
                try:
                    proc = subprocess.run(
                        ["tesseract", tmp.name, "stdout", "-l", OCR_TESSERACT_LANG, "--psm", str(psm)],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                except FileNotFoundError:
                    raise
                if proc.returncode != 0:
                    raise RuntimeError((proc.stderr or "Falha no binario tesseract.").strip())
                return (proc.stdout or "").strip()

        candidates: list[dict[str, Any]] = []
        variants = _build_tesseract_variants(image, kind)
        total_variants = len(variants)
        for idx, (variant_name, variant_image) in enumerate(variants):
            try:
                rotations = OCR_FAST_ROTATIONS if idx < max(total_variants - 1, 1) else OCR_TESSERACT_ROTATIONS
                for angle in rotations:
                    rotated = variant_image.rotate(angle, expand=True) if angle else variant_image
                    for psm in OCR_TESSERACT_PSMS:
                        text = run_ocr(rotated, psm=psm)
                        metrics = _text_quality_metrics(text)
                        candidate = {
                            "angle": angle,
                            "variant": variant_name,
                            "psm": str(psm),
                            "text": text,
                            "metrics": metrics,
                        }
                        candidates.append(candidate)
                        # Curto-circuito: quando já encontramos CID com score alto, evita varrer combinações restantes.
                        if _candidate_reaches_early_stop(metrics):
                            best = candidate
                            chosen_text = best["text"] or ""
                            m = best["metrics"]
                            return {
                                "text": chosen_text,
                                "ok": True,
                                "motivo": "Early stop no fallback Tesseract (CID identificado com alta confianca).",
                                "engine": "tesseract",
                                "preprocessed_path": processed_path,
                                "quality_ok": bool(m["quality_ok"]),
                                "quality_score": m["quality_score"],
                                "cid_hint": bool(m["cid_hint"]),
                                "cpf_hint": bool(m["cpf_hint"]),
                                "alpha_ratio": m["alpha_ratio"],
                                "long_token_ratio": m["long_token_ratio"],
                                "best_rotation": best["angle"],
                                "best_variant": best.get("variant", "base"),
                                "best_psm": best.get("psm", "6"),
                                "rotations_tested": list(rotations),
                                "variants_tested": sorted({c.get("variant", "base") for c in candidates}),
                                "psms_tested": list(OCR_TESSERACT_PSMS),
                            }
            finally:
                variant_image.close()

        best = max(
            candidates,
            key=lambda c: _candidate_rank(c["metrics"], c["text"], kind),
        )
        chosen_text = best["text"] or ""
        m = best["metrics"]
        cpf_candidates: list[str] = []
        if kind in {"RG_BENEF", "RG_RESP"}:
            variants_for_roi = _build_tesseract_variants(image, kind)
            variant_map = {name: img for name, img in variants_for_roi}
            selected_variant = variant_map.get(best.get("variant", "base"))
            try:
                if selected_variant is not None:
                    angle = int(best.get("angle", 0) or 0)
                    selected_rotated = (
                        selected_variant.rotate(angle, expand=True) if angle else selected_variant
                    )
                    cpf_candidates = _extract_rg_roi_cpf_candidates(selected_rotated)
            finally:
                for _, img in variants_for_roi:
                    img.close()
        return {
            "text": chosen_text,
            "ok": True,
            "motivo": "",
            "engine": "tesseract",
            "preprocessed_path": processed_path,
            "quality_ok": bool(m["quality_ok"]),
            "quality_score": m["quality_score"],
            "cid_hint": bool(m["cid_hint"]),
            "cpf_hint": bool(m["cpf_hint"]),
            "alpha_ratio": m["alpha_ratio"],
            "long_token_ratio": m["long_token_ratio"],
            "best_rotation": best["angle"],
            "best_variant": best.get("variant", "base"),
            "best_psm": best.get("psm", "6"),
            "rotations_tested": list(OCR_TESSERACT_ROTATIONS),
            "variants_tested": sorted({c.get("variant", "base") for c in candidates}),
            "psms_tested": list(OCR_TESSERACT_PSMS),
            "cpf_candidates": cpf_candidates,
        }
    except FileNotFoundError:
        return {
            "text": "",
            "ok": False,
            "motivo": "Binario 'tesseract' nao encontrado no PATH do servidor.",
            "engine": "tesseract",
            "preprocessed_path": processed_path,
        }
    except RuntimeError as exc:
        return {
            "text": "",
            "ok": False,
            "motivo": str(exc),
            "engine": "tesseract",
            "preprocessed_path": processed_path,
        }
    finally:
        image.close()


def extract_text_from_document(document_path: str | Path, document_kind: str = "") -> dict[str, Any]:
    """
    OCR principal com docTR e fallback opcional para Tesseract em baixa qualidade.
    """
    kind = _normalize_document_kind(document_kind)
    primary = _extract_text_with_doctr(document_path)
    engines_tried = [primary.get("engine", "doctr")]
    selected = primary

    if not primary.get("ok"):
        return {
            **primary,
            "engines_tried": engines_tried,
            "selected_engine": primary.get("engine", "doctr"),
        }

    should_try_tesseract = OCR_FALLBACK_TESSERACT and not primary.get("quality_ok", False)
    if should_try_tesseract:
        secondary = _extract_text_with_tesseract(document_path, document_kind=kind)
        engines_tried.append("tesseract")
        if secondary.get("ok") and (
            float(secondary.get("quality_score", 0.0)) > float(primary.get("quality_score", 0.0))
            or (
                float(secondary.get("quality_score", 0.0)) == float(primary.get("quality_score", 0.0))
                and len(secondary.get("text", "")) > len(primary.get("text", ""))
            )
        ):
            selected = secondary
            selected["motivo"] = "Fallback Tesseract selecionado por melhor qualidade de texto OCR."
        else:
            detalhe = secondary.get("motivo", "")
            if detalhe:
                selected["motivo"] = f"docTR mantido (fallback Tesseract: {detalhe})"
            else:
                selected["motivo"] = "docTR mantido (fallback Tesseract sem ganho de texto)."

    selected["engines_tried"] = engines_tried
    selected["selected_engine"] = selected.get("engine", "doctr")
    return selected
