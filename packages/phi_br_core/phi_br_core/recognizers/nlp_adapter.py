from __future__ import annotations

import re
from typing import Any, Protocol

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from phi_br_core.entities import BR_ADDRESS, BR_INSTITUTION, BR_PERSON_NAME
from phi_br_core.policy import NlpPolicy


class NlpCallable(Protocol):
    def __call__(self, text: str) -> Any:
        """Return an object with an ``ents`` iterable."""
        ...


_SUPPORTED_ENTITIES = [BR_PERSON_NAME, BR_INSTITUTION, BR_ADDRESS]
_LABEL_TO_ENTITY = {
    "PER": BR_PERSON_NAME,
    "PERSON": BR_PERSON_NAME,
    "PESSOA": BR_PERSON_NAME,
    "ORG": BR_INSTITUTION,
    "ORGANIZATION": BR_INSTITUTION,
    "LOC": BR_ADDRESS,
    "GPE": BR_ADDRESS,
    "LOCATION": BR_ADDRESS,
    "LUGAR": BR_ADDRESS,
}
_ADMIN_FIELD_LABELS = {
    "acompanhante",
    "atendimento",
    "autorizacao",
    "autorização",
    "cep",
    "clinica",
    "clínica",
    "cnpj",
    "cns",
    "convenio",
    "convênio",
    "cpf",
    "crm",
    "data",
    "dn",
    "email",
    "endereco",
    "endereço",
    "estado civil",
    "exame",
    "filhos",
    "guia",
    "hospital",
    "idade",
    "instituicao",
    "instituição",
    "irmaos",
    "irmãos",
    "laudo",
    "mae",
    "mãe",
    "nascimento",
    "naturalidade",
    "paciente",
    "pai",
    "pedido",
    "procedencia",
    "procedência",
    "profissao",
    "profissão",
    "prontuario",
    "prontuário",
    "religiao",
    "religião",
    "registro",
    "reside",
    "rg",
    "ses",
    "telefone",
}
_CLINICAL_FALSE_POSITIVE_TERMS = {
    "ac folico",
    "ac urico",
    "anti-hbs",
    "azuma",
    "beg",
    "bi",
    "bt",
    "ca",
    "calcio",
    "cálcio",
    "cl",
    "cloro",
    "cloretos",
    "clozapina",
    "cpk",
    "cr",
    "ct",
    "da",
    "di",
    "ds",
    "eas",
    "ecg",
    "eeg",
    "ect",
    "fal",
    "fc",
    "indico",
    "internado",
    "gj",
    "glicemia",
    "hb",
    "hba1c",
    "hbsag",
    "hcv",
    "hdl",
    "hiv",
    "hm",
    "ht",
    "k",
    "lab",
    "ldl",
    "leuco",
    "leuc",
    "lorazepam",
    "liquor",
    "luftal",
    "macrogol",
    "magnesio",
    "magnésio",
    "medica",
    "médica",
    "mg",
    "na",
    "nr",
    "nt",
    "olanzapina",
    "pa",
    "pad",
    "parênquima",
    "parênquima cerebral",
    "pas",
    "pcr",
    "peso",
    "plaq",
    "plaquetas",
    "potassio",
    "potássio",
    "risperidona",
    "sat",
    "seg",
    "sodio",
    "sódio",
    "t4l",
    "tec",
    "tc",
    "tgo",
    "tgp",
    "tgl",
    "trig",
    "tsh",
    "transtorno",
    "ur",
    "ureia",
    "vcmi",
    "vcm",
    "ventriculos",
    "ventrículos",
    "vitamina b1",
    "vitamina b12",
    "vitamina b6",
    "vitamina d",
}
_MEDICATION_TERMS = {
    "aripiprazol",
    "buspirona",
    "clonazepam",
    "clozapina",
    "divalproato",
    "escitalopram",
    "fluoxetina",
    "lamotrigina",
    "litio",
    "lítio",
    "lorazepam",
    "mirtazapina",
    "olanzapina",
    "quetiapina",
    "risperidona",
    "sertralina",
    "valproato",
    "venlafaxina",
    "zolpidem",
}
_MONTH_TERMS = {
    "janeiro",
    "fevereiro",
    "marco",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
}
_INSTITUTION_KEYWORDS = {
    "caps",
    "clínica",
    "clinica",
    "consultório",
    "consultorio",
    "hospital",
    "hub",
    "hbdf",
    "hcb",
    "hmib",
    "hran",
    "hrt",
    "iges",
    "ihbdf",
    "instituto",
    "laboratório",
    "laboratorio",
    "ubs",
    "upa",
}
_LOCATION_CONTEXT_RE = re.compile(
    r"(?:endere[cç]o|naturalidade|proced[eê]ncia|residentes?|reside(?:m)?|"
    r"mora(?:m)?|mudou|viveu|morou|nasceu|procedente)\s+(?:em|para|na|no|de|do|da)?\s*$",
    flags=re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(r"^\[[A-Z][A-Z0-9_]*_\d{3}(?::|\||\])")
_TRAILING_DATE_FRAGMENT_RE = re.compile(
    r"\s+(?:dia|em)\s+\d{1,2}$",
    flags=re.IGNORECASE,
)


class NlpEntityRecognizer(EntityRecognizer):
    """Optional NLP-backed recognizer for broad person, institution, and place spans."""

    def __init__(self, policy: NlpPolicy, nlp: NlpCallable | None = None) -> None:
        self._policy = policy
        self._nlp = nlp
        super().__init__(
            supported_entities=_SUPPORTED_ENTITIES,
            supported_language="pt",
            context=["paciente", "hospital", "clínica", "cidade", "naturalidade"],
        )

    def load(self) -> None:
        if self._policy.enabled:
            self._load_nlp()

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        del nlp_artifacts
        if not self._policy.enabled:
            return []

        requested = set(entities)
        if not requested.intersection(_SUPPORTED_ENTITIES):
            return []

        nlp = self._load_nlp()
        if nlp is None:
            return []

        doc = nlp(text)
        results: list[RecognizerResult] = []
        for entity in getattr(doc, "ents", []):
            entity_type = _LABEL_TO_ENTITY.get(str(getattr(entity, "label_", "")).upper())
            if entity_type is None or entity_type not in requested:
                continue
            span = _safe_span(text, entity)
            if span is None:
                continue
            start, end = span
            if entity_type in {BR_INSTITUTION, BR_ADDRESS}:
                start, end = _trim_trailing_date_fragment(text, start, end)
                if end <= start:
                    continue
            value = text[start:end]
            if _is_admin_field_label(value):
                continue
            if _is_clinical_false_positive(value):
                continue
            if entity_type == BR_PERSON_NAME and _reject_person_span(text, start, end):
                continue
            if entity_type == BR_INSTITUTION and not _has_institution_signal(value):
                continue
            if entity_type == BR_ADDRESS and not _has_location_context(text, start, value):
                continue
            results.append(
                RecognizerResult(
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    score=self._policy.min_score,
                )
            )
        return results

    def _load_nlp(self) -> NlpCallable | None:
        if self._nlp is not None:
            return self._nlp
        self._nlp = load_spacy_model(self._policy)
        return self._nlp


def nlp_model_available(policy: NlpPolicy) -> bool:
    return load_spacy_model(policy) is not None


def load_spacy_model(policy: NlpPolicy) -> NlpCallable | None:
    if policy.provider != "spacy":
        return None
    try:
        import spacy
    except Exception:
        return None
    try:
        return spacy.load(policy.model)
    except Exception:
        return None


def _safe_span(text: str, entity: Any) -> tuple[int, int] | None:
    try:
        start = int(entity.start_char)
        end = int(entity.end_char)
    except (AttributeError, TypeError, ValueError):
        return None
    if start < 0 or end > len(text) or end <= start:
        return None

    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end <= start:
        return None

    value = text[start:end]
    if "\n" in value or "\r" in value:
        return None
    if "[" in value or "]" in value:
        return None
    if _is_inside_placeholder(text, start, end):
        return None
    return start, end


def _is_admin_field_label(value: str) -> bool:
    normalized = _normalize(value).rstrip(":")
    return normalized in _ADMIN_FIELD_LABELS


def _is_clinical_false_positive(value: str) -> bool:
    normalized = _normalize(value)
    if normalized in _CLINICAL_FALSE_POSITIVE_TERMS:
        return True
    words = set(re.findall(r"[a-zà-ú0-9]+", normalized))
    if words & _MONTH_TERMS:
        return True
    return bool(words & _MEDICATION_TERMS)


def _reject_person_span(text: str, start: int, end: int) -> bool:
    value = text[start:end].strip()
    if re.search(r"[\d/]", value):
        return True
    if len(value.split()) > 1:
        return False
    if value.isupper() and len(value) <= 5:
        return True
    return False


def _has_institution_signal(value: str) -> bool:
    normalized = _normalize(value)
    words = set(re.findall(r"[a-zà-ú0-9]+", normalized))
    return bool(words & _INSTITUTION_KEYWORDS)


def _has_location_context(text: str, start: int, value: str) -> bool:
    if re.search(r"-[A-Z]{2}\b", value):
        return True
    prefix = text[max(0, start - 70) : start]
    return _LOCATION_CONTEXT_RE.search(prefix) is not None


def _is_inside_placeholder(text: str, start: int, end: int) -> bool:
    open_index = text.rfind("[", 0, start + 1)
    if open_index == -1:
        return False

    close_before = text.rfind("]", 0, start + 1)
    if close_before > open_index:
        return False

    close_after = text.find("]", end)
    if close_after == -1:
        return False

    placeholder_text = text[open_index : close_after + 1]
    if "\n" in placeholder_text:
        return False
    return _PLACEHOLDER_RE.match(placeholder_text) is not None


def _trim_trailing_date_fragment(text: str, start: int, end: int) -> tuple[int, int]:
    value = text[start:end]
    match = _TRAILING_DATE_FRAGMENT_RE.search(value)
    if match is None or text[end : end + 1] not in {"/", "-", "."}:
        return start, end
    return start, start + match.start()


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().rstrip(":").split())
