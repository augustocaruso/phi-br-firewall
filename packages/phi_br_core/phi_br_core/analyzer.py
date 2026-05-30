from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from presidio_analyzer import (
    AnalyzerEngine,
    EntityRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_analyzer.context_aware_enhancers import ContextAwareEnhancer
from presidio_analyzer.nlp_engine import NlpArtifacts, NlpEngine
from spacy.tokens import Doc
from spacy.vocab import Vocab

from phi_br_core.policy import PhiPolicy
from phi_br_core.recognizers.cep import CepRecognizer
from phi_br_core.recognizers.clinical_ids import ClinicalIdRecognizer
from phi_br_core.recognizers.cns import CnsRecognizer
from phi_br_core.recognizers.cpf import CpfRecognizer
from phi_br_core.recognizers.crm import CrmRecognizer
from phi_br_core.recognizers.dates_br import DateBrRecognizer
from phi_br_core.recognizers.institutions import InstitutionRecognizer
from phi_br_core.recognizers.names_context import ClinicalNameContextRecognizer
from phi_br_core.recognizers.phone_br import PhoneBrRecognizer


class _SimpleNlpEngine(NlpEngine):
    def __init__(self, languages: list[str]) -> None:
        self._languages = languages
        self._loaded = False
        self._vocab = Vocab()

    def load(self) -> None:
        self._loaded = True

    def is_loaded(self) -> bool:
        return self._loaded

    def process_text(self, text: str, language: str) -> NlpArtifacts:
        words: list[str] = []
        spaces: list[bool] = []
        indices: list[int] = []
        for match in re.finditer(r"\w+|[^\w\s]", text, flags=re.UNICODE):
            words.append(match.group(0))
            indices.append(match.start())
            spaces.append(match.end() < len(text) and text[match.end()].isspace())

        doc = Doc(self._vocab, words=words, spaces=spaces)
        lemmas = [word.lower() for word in words]
        return NlpArtifacts(
            entities=[],
            tokens=doc,
            tokens_indices=indices,
            lemmas=lemmas,
            nlp_engine=self,
            language=language,
        )

    def process_batch(
        self,
        texts: Iterable[str],
        language: str,
        batch_size: int = 1,
        n_process: int = 1,
        **kwargs: object,
    ) -> Iterator[tuple[str, NlpArtifacts]]:
        del batch_size, n_process, kwargs
        for text in texts:
            yield text, self.process_text(text, language)

    def is_stopword(self, word: str, language: str) -> bool:
        del language
        return word.lower() in {
            "a",
            "o",
            "as",
            "os",
            "de",
            "da",
            "do",
            "das",
            "dos",
            "e",
        }

    def is_punct(self, word: str, language: str) -> bool:
        del language
        return bool(re.fullmatch(r"\W+", word, flags=re.UNICODE))

    def get_supported_entities(self) -> list[str]:
        return []

    def get_supported_languages(self) -> list[str]:
        return self._languages


class _NoOpContextAwareEnhancer(ContextAwareEnhancer):
    def __init__(self) -> None:
        super().__init__(
            context_similarity_factor=0,
            min_score_with_context_similarity=0,
            context_prefix_count=0,
            context_suffix_count=0,
        )

    def enhance_using_context(
        self,
        text: str,
        raw_results: list[RecognizerResult],
        nlp_artifacts: NlpArtifacts,
        recognizers: list[EntityRecognizer],
        context: list[str] | None = None,
    ) -> list[RecognizerResult]:
        del text, nlp_artifacts, recognizers, context
        return raw_results


def _languages_for(policy: PhiPolicy) -> list[str]:
    languages: list[str] = []
    for language in (policy.language, "en"):
        if language not in languages:
            languages.append(language)
    return languages


def build_registry(languages: list[str] | None = None) -> RecognizerRegistry:
    supported_languages = languages if languages is not None else ["pt", "en"]
    registry = RecognizerRegistry(supported_languages=supported_languages)
    try:
        registry.load_predefined_recognizers(languages=supported_languages)
    except Exception:
        registry = RecognizerRegistry(supported_languages=supported_languages)

    registry.add_recognizer(CpfRecognizer())
    registry.add_recognizer(CnsRecognizer())
    registry.add_recognizer(CrmRecognizer())
    registry.add_recognizer(CepRecognizer())
    registry.add_recognizer(PhoneBrRecognizer())
    registry.add_recognizer(ClinicalIdRecognizer())
    registry.add_recognizer(DateBrRecognizer())
    registry.add_recognizer(InstitutionRecognizer())
    registry.add_recognizer(ClinicalNameContextRecognizer())
    return registry


def build_analyzer(policy: PhiPolicy) -> AnalyzerEngine:
    languages = _languages_for(policy)
    registry = build_registry(languages)
    return AnalyzerEngine(
        registry=registry,
        nlp_engine=_SimpleNlpEngine(languages),
        supported_languages=languages,
        default_score_threshold=policy.min_score,
        context_aware_enhancer=_NoOpContextAwareEnhancer(),
    )
