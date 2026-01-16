"""Condition terminology helpers (synonyms and normalization)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DEFAULT_SYNONYMS: Dict[str, List[str]] = {
    "diabetes": [
        "diabetes mellitus",
        "diabetic",
        "type 2 diabetes",
        "type 1 diabetes",
        "t2dm",
        "t1dm",
    ],
    "hypertension": ["high blood pressure", "elevated blood pressure", "htn"],
    "depression": [
        "major depressive disorder",
        "mdd",
        "depressive disorder",
        "clinical depression",
    ],
    "heart failure": [
        "cardiac failure",
        "chf",
        "congestive heart failure",
        "hf",
    ],
    "stroke": [
        "cerebrovascular accident",
        "cva",
        "brain infarction",
        "ischemic stroke",
    ],
    "breast cancer": [
        "breast neoplasm",
        "breast carcinoma",
        "mammary cancer",
    ],
    "asthma": ["bronchial asthma", "asthmatic", "reactive airway disease"],
    "copd": [
        "chronic obstructive pulmonary disease",
        "emphysema",
        "chronic bronchitis",
    ],
    "alzheimer": ["alzheimer disease", "alzheimer's disease", "ad", "dementia"],
    "parkinson": [
        "parkinson disease",
        "parkinson's disease",
        "pd",
        "parkinsonian",
    ],
    "autism": ["autism spectrum disorder", "asd", "autistic disorder"],
    "covid-19": ["covid", "coronavirus", "sars-cov-2"],
    "cystic fibrosis": ["cf", "mucoviscidosis"],
}

DEFAULT_SYNONYM_PATH = Path(__file__).resolve().parent / "data" / "condition_synonyms.json"


def load_synonyms(path: Optional[Path | str] = None) -> Dict[str, List[str]]:
    """Load condition synonyms from JSON with defaults as fallback."""
    source = Path(path) if path else DEFAULT_SYNONYM_PATH
    synonyms: Dict[str, List[str]] = {}

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
    except Exception:
        payload = {}

    for key, values in payload.items():
        if not isinstance(key, str) or not isinstance(values, list):
            continue
        cleaned_key = key.strip().lower()
        cleaned_values = [
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        ]
        if cleaned_key and cleaned_values:
            synonyms[cleaned_key] = cleaned_values

    for key, values in DEFAULT_SYNONYMS.items():
        synonyms.setdefault(key, list(values))

    return synonyms


def normalize_condition(raw: str) -> str:
    """Normalize a raw condition string into a canonical label."""
    if not raw:
        return ""
    primary = raw.strip().lower()

    if any(token in primary for token in ("diabetes", "diabetic", "t1dm", "t2dm")):
        return "diabetes"
    if any(token in primary for token in ("hypertension", "blood pressure")):
        return "hypertension"
    if any(token in primary for token in ("cancer", "neoplasm", "carcinoma", "tumor")):
        if "breast" in primary:
            return "breast cancer"
        if "lung" in primary:
            return "lung cancer"
        return "cancer"
    if any(token in primary for token in ("heart failure", "cardiac failure", "chf")):
        return "heart failure"
    if any(token in primary for token in ("stroke", "cerebrovascular")):
        return "stroke"
    if any(token in primary for token in ("covid", "sars-cov", "coronavirus")):
        return "covid-19"
    if any(token in primary for token in ("depression", "depressive")):
        return "depression"
    if any(token in primary for token in ("autism", "autistic", "asd")):
        return "autism"
    if "asthma" in primary:
        return "asthma"
    if "psoriasis" in primary:
        return "psoriasis"
    if "arthritis" in primary:
        return "arthritis"

    return primary
