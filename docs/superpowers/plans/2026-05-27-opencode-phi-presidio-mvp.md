# OpenCode Phi Presidio MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable local PHI/PII redaction workflow for Brazilian Portuguese clinical text with OpenCode `/phi`, clipboard CLI commands, Presidio detection, reversible local placeholders, and automatic expired-session cleanup.

**Architecture:** Python owns all PHI detection, pseudonymization, mapping, restoration, audit, clipboard, and session lifecycle logic. OpenCode is a thin runtime adapter that intercepts `/phi <texto livre>`, calls the local `phi` CLI or Python API, and only sends redacted text to the model. Mapping files are local, temporary, never printed, and resolved through a placeholder index so users do not need to pass session ids.

**Tech Stack:** Python 3.11+, `uv`, Microsoft Presidio Analyzer/Anonymizer, Pydantic v2, Typer, Rich, pytest, ruff, mypy, TypeScript, OpenCode plugin API.

---

## Execution Topology

Sequential gates:

1. Repository and packaging baseline must land before tests or CLI work.
2. OpenCode command-replacement proof must land before full plugin integration.
3. Core Presidio recognizers must land before anonymization and audit.
4. Session lifecycle must land before clipboard restore, because restore depends on the placeholder index.
5. Full `/phi` integration lands last, after CLI behavior is tested independently.

Parallel-safe tracks after Task 2:

- Recognizer tests and validators can be built independently from OpenCode proof work.
- CLI clipboard commands can be implemented after the session store interface exists.
- Documentation can be updated after command names and output contracts are fixed.

Join points:

- Task 5 joins recognizers, overlap resolution, and mapping into `scrub_text`.
- Task 7 joins `phi redact`, `phi restore`, lifecycle purge, and macOS clipboard.
- Task 8 joins the tested CLI/core with OpenCode `/phi`.

Ownership:

- Python core files live under `packages/phi_br_core/phi_br_core/`.
- OpenCode adapter files live under `packages/phi_br_firewall_opencode/`.
- Tests live under `tests/`, split by behavior rather than implementation layer.
- Sensitive runtime artifacts live only under `.tmp/phi/`, which is ignored by Git.

## Scope Check

The approved spec covers one integrated MVP: Presidio core, simple CLI, lifecycle, and OpenCode `/phi`. This plan keeps the first implementation in one sequence because each layer depends on the previous one and each task produces testable behavior.

Out of scope for this plan:

- Gemini/Codex hooks.
- clipboard daemon.
- spaCy/Stanza optional NLP.
- encrypted mapping files.
- automatic restoration inside the OpenCode transcript.

## File Structure

Create or modify these files:

- `.gitignore`: already created; protects `.tmp/phi`, mappings, raw clinical text, Python caches, and `node_modules`.
- `pyproject.toml`: Python project, dependencies, scripts, ruff, mypy, pytest config.
- `README.md`: short usage and safety notes for the MVP.
- `packages/phi_br_core/phi_br_core/__init__.py`: public API exports.
- `packages/phi_br_core/phi_br_core/policy.py`: Pydantic policy models.
- `packages/phi_br_core/phi_br_core/models.py`: scan, finding, audit, scrub, session metadata result models.
- `packages/phi_br_core/phi_br_core/entities.py`: entity constants, placeholder prefixes, specificity order.
- `packages/phi_br_core/phi_br_core/validators.py`: CPF, digits, simple CNS helpers.
- `packages/phi_br_core/phi_br_core/analyzer.py`: Presidio registry and analyzer construction.
- `packages/phi_br_core/phi_br_core/recognizers/*.py`: Brazilian healthcare recognizers.
- `packages/phi_br_core/phi_br_core/spans.py`: overlap resolution.
- `packages/phi_br_core/phi_br_core/mapping.py`: mapping persistence and placeholder index.
- `packages/phi_br_core/phi_br_core/sessions.py`: lock, metadata, TTL, purge, active-session index.
- `packages/phi_br_core/phi_br_core/anonymizer.py`: stable pseudonymization.
- `packages/phi_br_core/phi_br_core/audit.py`: post-scrub audit.
- `packages/phi_br_core/phi_br_core/clipboard.py`: macOS clipboard adapter first, extensible interface.
- `packages/phi_br_core/phi_br_core/cli/main.py`: Typer app exposed as `phi`.
- `packages/phi_br_firewall_opencode/package.json`: OpenCode plugin package metadata.
- `packages/phi_br_firewall_opencode/tsconfig.json`: TypeScript config.
- `packages/phi_br_firewall_opencode/src/plugin.ts`: OpenCode server plugin.
- `packages/phi_br_firewall_opencode/src/phi.ts`: local CLI runner and safe result parsing.
- `packages/phi_br_firewall_opencode/tests/plugin.test.ts`: unit tests for command replacement.
- `tests/fixtures/synthetic_notes.py`: synthetic clinical text only.
- `tests/test_policy.py`: policy defaults and path behavior.
- `tests/test_validators.py`: CPF and digit helper tests.
- `tests/test_recognizers.py`: Presidio recognizer behavior.
- `tests/test_spans.py`: overlap resolution tests.
- `tests/test_mapping_sessions.py`: placeholder index, TTL, purge, no recycling while active.
- `tests/test_scrub_restore_roundtrip.py`: scrub/restore behavior.
- `tests/test_audit.py`: residual PHI blocking.
- `tests/test_cli_clipboard.py`: `phi redact` and `phi restore` with fake clipboard.

## Task 1: Repository Baseline And Python Project

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `packages/phi_br_core/phi_br_core/__init__.py`
- Create: `packages/phi_br_core/phi_br_core/cli/__init__.py`
- Create: `packages/phi_br_core/phi_br_core/cli/main.py`
- Test: shell command verification

- [ ] **Step 1: Write the project metadata**

Create `pyproject.toml` with this content:

```toml
[project]
name = "phi-br-presidio-firewall"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "presidio-analyzer",
  "presidio-anonymizer",
  "pydantic>=2",
  "pyyaml",
  "typer",
  "rich"
]

[project.scripts]
phi = "phi_br_core.cli.main:app"

[dependency-groups]
dev = [
  "pytest",
  "ruff",
  "mypy"
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["packages/phi_br_core/phi_br_core"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["packages/phi_br_core"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["phi_br_core"]
```

- [ ] **Step 2: Add a minimal CLI that fails the future check behavior clearly**

Create `packages/phi_br_core/phi_br_core/cli/main.py`:

```python
from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def check() -> None:
    """Verify that phi can start."""
    typer.echo("phi baseline ok")
```

Create empty package files:

```bash
mkdir -p packages/phi_br_core/phi_br_core/cli
touch packages/phi_br_core/phi_br_core/__init__.py
touch packages/phi_br_core/phi_br_core/cli/__init__.py
```

- [ ] **Step 3: Add README safety baseline**

Create `README.md`:

````markdown
# phi-br-presidio-firewall

Local-first PHI/PII redaction for Brazilian Portuguese clinical text.

The MVP uses Microsoft Presidio for local detection, stable local placeholders for reversible pseudonymization, and an OpenCode `/phi` command so raw clinical text is redacted before it reaches a model.

Public commands:

```bash
phi redact
phi restore
phi status
phi purge
```

Runtime mappings live under `.tmp/phi/` and are ignored by Git.
````

- [ ] **Step 4: Sync and verify baseline**

Run:

```bash
uv sync
uv run phi check
```

Expected:

```text
phi baseline ok
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore README.md pyproject.toml packages/phi_br_core
git commit -m "chore: bootstrap phi presidio project"
```

## Task 2: OpenCode Command Replacement Proof

**Files:**
- Create: `packages/phi_br_firewall_opencode/package.json`
- Create: `packages/phi_br_firewall_opencode/tsconfig.json`
- Create: `packages/phi_br_firewall_opencode/src/plugin.ts`
- Create: `packages/phi_br_firewall_opencode/tests/plugin.test.ts`

- [ ] **Step 1: Write a unit test for safe command replacement**

Create `packages/phi_br_firewall_opencode/tests/plugin.test.ts`:

```ts
import { describe, expect, test } from "vitest"
import PhiPlugin from "../src/plugin"

describe("Phi OpenCode plugin", () => {
  test("replaces raw /phi arguments with safe text parts", async () => {
    const hooks = await PhiPlugin.server({
      client: {} as never,
      project: {} as never,
      directory: "/tmp/phi-test",
      worktree: "/tmp/phi-test",
      experimental_workspace: { register() {} },
      serverUrl: new URL("http://localhost"),
      $: {} as never,
    })

    const output = { parts: [] as Array<{ type: "text"; text: string; synthetic?: boolean }> }

    await hooks["command.execute.before"]?.(
      {
        command: "phi",
        sessionID: "session-1",
        arguments: "Paciente Joao CPF 123.456.789-09",
      },
      output,
    )

    expect(output.parts).toEqual([
      {
        type: "text",
        text: "PHI proof replacement: [PACIENTE_001] [CPF_001]",
        synthetic: true,
      },
    ])
  })
})
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd packages/phi_br_firewall_opencode
npm test -- --run tests/plugin.test.ts
```

Expected: FAIL because `package.json`, `vitest`, and `src/plugin.ts` do not exist yet.

- [ ] **Step 3: Add the TypeScript package and proof plugin**

Create `packages/phi_br_firewall_opencode/package.json`:

```json
{
  "name": "phi-br-firewall-opencode",
  "version": "0.1.0",
  "type": "module",
  "private": true,
  "scripts": {
    "test": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@opencode-ai/plugin": "1.14.33"
  },
  "devDependencies": {
    "typescript": "^5.8.2",
    "vitest": "^3.2.4"
  }
}
```

Create `packages/phi_br_firewall_opencode/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "types": ["node", "vitest/globals"],
    "skipLibCheck": true,
    "outDir": "dist"
  },
  "include": ["src/**/*.ts", "tests/**/*.ts"]
}
```

Create `packages/phi_br_firewall_opencode/src/plugin.ts`:

```ts
import type { PluginModule } from "@opencode-ai/plugin"

const PhiPlugin: PluginModule = {
  async server() {
    return {
      async "command.execute.before"(input, output) {
        if (input.command !== "phi") return
        output.parts = [
          {
            type: "text",
            text: "PHI proof replacement: [PACIENTE_001] [CPF_001]",
            synthetic: true,
          },
        ]
      },
    }
  },
}

export default PhiPlugin
```

- [ ] **Step 4: Verify proof package**

Run:

```bash
cd packages/phi_br_firewall_opencode
npm install
npm run typecheck
npm test -- --run tests/plugin.test.ts
```

Expected: typecheck exits 0 and the test passes.

- [ ] **Step 5: Manual OpenCode proof**

Add the local plugin path to a disposable OpenCode project config or launch with a project-local config. Run a session with:

```text
/phi Paciente Joao CPF 123.456.789-09
```

Expected model-facing text contains:

```text
PHI proof replacement: [PACIENTE_001] [CPF_001]
```

Expected model-facing text does not contain:

```text
Joao
123.456.789-09
```

Record the proof command and observation in `README.md` under a short "OpenCode proof" section without including real PHI.

- [ ] **Step 6: Commit**

```bash
git add README.md packages/phi_br_firewall_opencode
git commit -m "test: prove opencode phi command replacement"
```

## Task 3: Policy, Models, Entity Constants, And Validators

**Files:**
- Create: `packages/phi_br_core/phi_br_core/policy.py`
- Create: `packages/phi_br_core/phi_br_core/models.py`
- Create: `packages/phi_br_core/phi_br_core/entities.py`
- Create: `packages/phi_br_core/phi_br_core/validators.py`
- Modify: `packages/phi_br_core/phi_br_core/__init__.py`
- Test: `tests/test_policy.py`
- Test: `tests/test_validators.py`

- [ ] **Step 1: Write failing tests for policy defaults and CPF validation**

Create `tests/test_policy.py`:

```python
from phi_br_core.policy import PhiPolicy


def test_policy_defaults_are_safe() -> None:
    policy = PhiPolicy()

    assert policy.mode == "pseudonymize"
    assert policy.fail_closed is True
    assert policy.language == "pt"
    assert policy.mapping.base_dir == ".tmp/phi"
    assert policy.sessions.ttl_hours == 24
    assert policy.sessions.purge_expired_on_start is True
```

Create `tests/test_validators.py`:

```python
from phi_br_core.validators import only_digits, validate_cpf


def test_only_digits_removes_punctuation() -> None:
    assert only_digits("CPF 123.456.789-09") == "12345678909"


def test_validate_cpf_accepts_valid_synthetic_number() -> None:
    assert validate_cpf("935.411.347-80") is True


def test_validate_cpf_rejects_repeated_digits() -> None:
    assert validate_cpf("000.000.000-00") is False


def test_validate_cpf_rejects_bad_check_digits() -> None:
    assert validate_cpf("935.411.347-81") is False
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_policy.py tests/test_validators.py -v
```

Expected: FAIL because modules do not exist.

- [ ] **Step 3: Implement policy and validators**

Create `packages/phi_br_core/phi_br_core/policy.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MappingPolicy(BaseModel):
    persist: bool = True
    base_dir: str = ".tmp/phi"
    delete_by_default: bool = True
    encrypt_future: bool = True


class DatePolicy(BaseModel):
    strategy: Literal["placeholder", "shift", "preserve_relative"] = "placeholder"
    preserve_relative_dates: bool = True


class AgePolicy(BaseModel):
    strategy: Literal["placeholder", "age_band", "preserve"] = "age_band"


class SessionPolicy(BaseModel):
    ttl_hours: int = 24
    purge_expired_on_start: bool = True
    max_sessions: int = 20
    delete_by_default: bool = True


class PhiPolicy(BaseModel):
    mode: Literal["pseudonymize", "redact", "audit_only"] = "pseudonymize"
    fail_closed: bool = True
    language: str = "pt"
    min_score: float = 0.45
    audit_threshold: float = 0.35
    mapping: MappingPolicy = Field(default_factory=MappingPolicy)
    dates: DatePolicy = Field(default_factory=DatePolicy)
    ages: AgePolicy = Field(default_factory=AgePolicy)
    sessions: SessionPolicy = Field(default_factory=SessionPolicy)
```

Create `packages/phi_br_core/phi_br_core/validators.py`:

```python
from __future__ import annotations


def only_digits(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def validate_cpf(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False

    numbers = [int(digit) for digit in digits]
    first_sum = sum(numbers[index] * (10 - index) for index in range(9))
    first_digit = (first_sum * 10) % 11
    if first_digit == 10:
        first_digit = 0
    if first_digit != numbers[9]:
        return False

    second_sum = sum(numbers[index] * (11 - index) for index in range(10))
    second_digit = (second_sum * 10) % 11
    if second_digit == 10:
        second_digit = 0
    return second_digit == numbers[10]
```

Create `packages/phi_br_core/phi_br_core/entities.py` with entity constants and placeholder mapping from the approved spec.

Create `packages/phi_br_core/phi_br_core/models.py` with Pydantic models:

```python
from __future__ import annotations

from pydantic import BaseModel


class PhiFinding(BaseModel):
    entity_type: str
    text: str
    start: int
    end: int
    score: float


class PhiScanResult(BaseModel):
    findings: list[PhiFinding]


class PhiAuditResult(BaseModel):
    safe: bool
    residual_findings: list[PhiFinding]


class PhiScrubSummary(BaseModel):
    entities_replaced: int
    entity_types: list[str]


class PhiScrubResult(BaseModel):
    ok: bool
    action: str
    scrubbed_text: str
    mapping_path: str
    session_id: str
    audit: PhiAuditResult
    summary: PhiScrubSummary
```

- [ ] **Step 4: Export public names**

Modify `packages/phi_br_core/phi_br_core/__init__.py`:

```python
from phi_br_core.policy import PhiPolicy

__all__ = ["PhiPolicy"]
```

- [ ] **Step 5: Run tests and quality checks**

Run:

```bash
uv run pytest tests/test_policy.py tests/test_validators.py -v
uv run ruff check packages tests
uv run mypy packages/phi_br_core/phi_br_core
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/phi_br_core tests/test_policy.py tests/test_validators.py
git commit -m "feat: add phi policy models and validators"
```

## Task 4: Presidio Analyzer And Brazilian Recognizers

**Files:**
- Create: `packages/phi_br_core/phi_br_core/analyzer.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/__init__.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/cpf.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/cns.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/crm.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/cep.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/phone_br.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/clinical_ids.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/dates_br.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/names_context.py`
- Create: `packages/phi_br_core/phi_br_core/recognizers/institutions.py`
- Test: `tests/test_recognizers.py`

- [ ] **Step 1: Write failing recognizer tests**

Create `tests/test_recognizers.py`:

```python
from phi_br_core.analyzer import build_analyzer
from phi_br_core.policy import PhiPolicy


def entity_types_for(text: str) -> set[str]:
    analyzer = build_analyzer(PhiPolicy())
    results = analyzer.analyze(text=text, language="pt", score_threshold=0.35)
    return {result.entity_type for result in results}


def test_detects_valid_cpf() -> None:
    assert "BR_CPF" in entity_types_for("Paciente com CPF 935.411.347-80.")


def test_rejects_invalid_cpf() -> None:
    assert "BR_CPF" not in entity_types_for("Numero 935.411.347-81.")


def test_detects_cns_with_context() -> None:
    assert "BR_CNS" in entity_types_for("CNS 898001160000000 registrado.")


def test_detects_crm_with_uf_prefix() -> None:
    assert "BR_CRM" in entity_types_for("Atendido pela Dra Ana CRM-DF 12345.")


def test_detects_phone_and_cep() -> None:
    types = entity_types_for("Telefone (61) 99999-9999, CEP 70000-000.")
    assert "BR_PHONE" in types
    assert "BR_CEP" in types


def test_detects_contextual_clinical_ids() -> None:
    types = entity_types_for("Prontuario 123456. Guia 987654321. Laudo 554433.")
    assert "BR_CLINICAL_RECORD_ID" in types
    assert "BR_AUTHORIZATION_ID" in types
    assert "BR_EXAM_ID" in types


def test_does_not_detect_medication_numbers_as_clinical_ids() -> None:
    types = entity_types_for("quetiapina 100 mg, PA 120x80, HbA1c 6,5%.")
    assert "BR_CLINICAL_RECORD_ID" not in types
    assert "BR_VISIT_ID" not in types


def test_detects_patient_and_professional_names_by_context() -> None:
    types = entity_types_for("Paciente Joao da Silva avaliado pela Dra Ana Souza.")
    assert "BR_PATIENT_NAME" in types
    assert "BR_HEALTHCARE_PROFESSIONAL_NAME" in types
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_recognizers.py -v
```

Expected: FAIL because analyzer and recognizers do not exist.

- [ ] **Step 3: Implement analyzer registry**

Create `packages/phi_br_core/phi_br_core/analyzer.py`:

```python
from __future__ import annotations

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

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


def build_registry() -> RecognizerRegistry:
    registry = RecognizerRegistry()
    try:
        registry.load_predefined_recognizers(languages=["pt", "en"])
    except Exception:
        registry = RecognizerRegistry()

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
    registry = build_registry()
    return AnalyzerEngine(registry=registry, supported_languages=[policy.language, "en"])
```

- [ ] **Step 4: Implement recognizers**

Implement each recognizer as a focused `PatternRecognizer`. CPF must override validation by filtering invalid results or lowering invalid scores below threshold. Clinical IDs must require context in the regex itself so isolated medication doses and lab values do not match.

Minimum CPF recognizer shape:

```python
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpArtifacts
from presidio_analyzer.recognizer_result import RecognizerResult

from phi_br_core.validators import validate_cpf


class CpfRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity="BR_CPF",
            patterns=[
                Pattern(
                    name="cpf_formatted_or_digits",
                    regex=r"\b(?:CPF[:\s]*)?\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
                    score=0.85,
                )
            ],
            context=["cpf", "cadastro", "documento"],
            supported_language="pt",
        )

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts)
        return [result for result in results if validate_cpf(text[result.start : result.end])]
```

Minimum CRM pattern must include both `CRM-DF 12345` and `CRM 12345 DF`. Minimum name recognizer must avoid the medication allowlist from the spec.

- [ ] **Step 5: Run recognizer tests**

Run:

```bash
uv run pytest tests/test_recognizers.py -v
uv run ruff check packages tests
uv run mypy packages/phi_br_core/phi_br_core
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/phi_br_core/phi_br_core/analyzer.py packages/phi_br_core/phi_br_core/recognizers tests/test_recognizers.py
git commit -m "feat: add presidio analyzer and brazilian recognizers"
```

## Task 5: Overlap Resolution, Mapping, Sessions, And Stable Anonymizer

**Files:**
- Create: `packages/phi_br_core/phi_br_core/spans.py`
- Create: `packages/phi_br_core/phi_br_core/mapping.py`
- Create: `packages/phi_br_core/phi_br_core/sessions.py`
- Create: `packages/phi_br_core/phi_br_core/anonymizer.py`
- Test: `tests/test_spans.py`
- Test: `tests/test_mapping_sessions.py`
- Test: `tests/test_scrub_restore_roundtrip.py`

- [ ] **Step 1: Write failing overlap and mapping tests**

Create `tests/test_spans.py`:

```python
from phi_br_core.models import PhiFinding
from phi_br_core.spans import resolve_overlaps


def finding(entity_type: str, text: str, start: int, end: int, score: float) -> PhiFinding:
    return PhiFinding(entity_type=entity_type, text=text, start=start, end=end, score=score)


def test_resolve_overlaps_keeps_more_specific_entity() -> None:
    findings = [
        finding("BR_DATE", "12345", 7, 12, 0.60),
        finding("BR_CRM", "CRM-DF 12345", 0, 12, 0.85),
    ]

    resolved = resolve_overlaps(findings)

    assert [item.entity_type for item in resolved] == ["BR_CRM"]
```

Create `tests/test_mapping_sessions.py`:

```python
from datetime import UTC, datetime, timedelta

from phi_br_core.mapping import PlaceholderIndex
from phi_br_core.sessions import SessionStore


def test_placeholder_index_resolves_multiple_sessions(tmp_path) -> None:
    index = PlaceholderIndex(tmp_path / "index.json")
    index.assign("PACIENTE_001", "phi-a")
    index.assign("CPF_002", "phi-b")

    assert index.resolve(["PACIENTE_001", "CPF_002"]) == {
        "PACIENTE_001": "phi-a",
        "CPF_002": "phi-b",
    }


def test_session_store_purges_expired_sessions(tmp_path) -> None:
    store = SessionStore(tmp_path)
    now = datetime(2026, 5, 27, 20, 0, tzinfo=UTC)
    expired = store.create(source="test", now=now - timedelta(hours=25), ttl_hours=24)
    active = store.create(source="test", now=now, ttl_hours=24)

    purged = store.purge_expired(now=now)

    assert expired.session_id in purged
    assert store.session_path(expired.session_id).exists() is False
    assert store.session_path(active.session_id).exists() is True
```

- [ ] **Step 2: Write failing roundtrip test**

Create `tests/test_scrub_restore_roundtrip.py`:

```python
from phi_br_core.anonymizer import StablePlaceholderAnonymizer
from phi_br_core.models import PhiFinding


def test_stable_anonymizer_reuses_placeholder_for_same_value(tmp_path) -> None:
    anonymizer = StablePlaceholderAnonymizer(base_dir=tmp_path)
    findings = [
        PhiFinding(entity_type="BR_PATIENT_NAME", text="Joao da Silva", start=9, end=22, score=0.80),
        PhiFinding(entity_type="BR_CPF", text="935.411.347-80", start=28, end=42, score=0.95),
        PhiFinding(entity_type="BR_PATIENT_NAME", text="Joao da Silva", start=53, end=66, score=0.80),
    ]

    result = anonymizer.scrub(
        "Paciente Joao da Silva, CPF 935.411.347-80. Paciente Joao da Silva retornou.",
        findings,
        source="test",
    )

    assert result.scrubbed_text == (
        "Paciente [PACIENTE_001], CPF [CPF_001]. Paciente [PACIENTE_001] retornou."
    )
    assert anonymizer.restore(result.scrubbed_text, result.mapping_path) == (
        "Paciente Joao da Silva, CPF 935.411.347-80. Paciente Joao da Silva retornou."
    )
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_spans.py tests/test_mapping_sessions.py tests/test_scrub_restore_roundtrip.py -v
```

Expected: FAIL because implementation modules do not exist.

- [ ] **Step 4: Implement overlap resolution**

Create `spans.py` with deterministic resolution:

```python
from __future__ import annotations

from phi_br_core.entities import ENTITY_SPECIFICITY
from phi_br_core.models import PhiFinding


def resolve_overlaps(findings: list[PhiFinding]) -> list[PhiFinding]:
    ordered = sorted(
        findings,
        key=lambda item: (
            item.start,
            -ENTITY_SPECIFICITY.get(item.entity_type, 0),
            -item.score,
            -(item.end - item.start),
        ),
    )
    accepted: list[PhiFinding] = []
    for candidate in ordered:
        if any(candidate.start < item.end and item.start < candidate.end for item in accepted):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda item: item.start)
```

- [ ] **Step 5: Implement sessions, mapping, and anonymizer**

Implement `SessionStore` with atomic directory deletion and `metadata.json`. Implement `PlaceholderIndex` with atomic JSON writes. Implement `StablePlaceholderAnonymizer` so it replaces spans from end to start, assigns prefixes from `ENTITY_TO_PLACEHOLDER_PREFIX`, writes `.tmp/phi/<session_id>/mapping.json`, updates the global index, and restores by replacing bracketed placeholders from mapping items.

Mapping file shape:

```json
{
  "session_id": "phi-20260527-200000-a1b2c3",
  "items": {
    "PACIENTE_001": {
      "value": "Joao da Silva",
      "entity_type": "BR_PATIENT_NAME"
    }
  }
}
```

- [ ] **Step 6: Run mapping and roundtrip tests**

Run:

```bash
uv run pytest tests/test_spans.py tests/test_mapping_sessions.py tests/test_scrub_restore_roundtrip.py -v
uv run ruff check packages tests
uv run mypy packages/phi_br_core/phi_br_core
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add packages/phi_br_core/phi_br_core/spans.py packages/phi_br_core/phi_br_core/mapping.py packages/phi_br_core/phi_br_core/sessions.py packages/phi_br_core/phi_br_core/anonymizer.py tests/test_spans.py tests/test_mapping_sessions.py tests/test_scrub_restore_roundtrip.py
git commit -m "feat: add stable placeholder sessions and mapping"
```

## Task 6: Scan, Scrub, Audit, Restore Public API

**Files:**
- Create: `packages/phi_br_core/phi_br_core/core.py`
- Create: `packages/phi_br_core/phi_br_core/audit.py`
- Modify: `packages/phi_br_core/phi_br_core/__init__.py`
- Test: `tests/test_audit.py`
- Test: `tests/test_core_api.py`

- [ ] **Step 1: Write failing public API and audit tests**

Create `tests/test_core_api.py`:

```python
from phi_br_core import PhiPolicy, audit_text, restore_text, scan_text, scrub_text


def test_scan_scrub_restore_public_api(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = "Paciente Joao da Silva, CPF 935.411.347-80."

    scan = scan_text(text, policy)
    assert "BR_CPF" in {finding.entity_type for finding in scan.findings}

    scrub = scrub_text(text, policy)
    assert scrub.ok is True
    assert "[CPF_001]" in scrub.scrubbed_text
    assert "935.411.347-80" not in scrub.scrubbed_text

    restored = restore_text(scrub.scrubbed_text, scrub.mapping_path)
    assert restored == text
```

Create `tests/test_audit.py`:

```python
from phi_br_core import PhiPolicy, audit_text


def test_audit_blocks_residual_cpf() -> None:
    result = audit_text("Texto ainda contem CPF 935.411.347-80.", PhiPolicy())

    assert result.safe is False
    assert "BR_CPF" in {finding.entity_type for finding in result.residual_findings}


def test_audit_accepts_placeholder_text() -> None:
    result = audit_text("Paciente [PACIENTE_001], CPF [CPF_001].", PhiPolicy())

    assert result.safe is True
    assert result.residual_findings == []
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_core_api.py tests/test_audit.py -v
```

Expected: FAIL because public API functions do not exist.

- [ ] **Step 3: Implement API functions**

Create `core.py`:

```python
from __future__ import annotations

from phi_br_core.analyzer import build_analyzer
from phi_br_core.anonymizer import StablePlaceholderAnonymizer
from phi_br_core.audit import audit_text
from phi_br_core.models import PhiFinding, PhiScanResult, PhiScrubResult
from phi_br_core.policy import PhiPolicy
from phi_br_core.spans import resolve_overlaps


def scan_text(text: str, policy: PhiPolicy) -> PhiScanResult:
    analyzer = build_analyzer(policy)
    results = analyzer.analyze(text=text, language=policy.language, score_threshold=policy.min_score)
    findings = [
        PhiFinding(
            entity_type=result.entity_type,
            text=text[result.start : result.end],
            start=result.start,
            end=result.end,
            score=float(result.score),
        )
        for result in results
    ]
    return PhiScanResult(findings=resolve_overlaps(findings))


def scrub_text(text: str, policy: PhiPolicy) -> PhiScrubResult:
    scan = scan_text(text, policy)
    anonymizer = StablePlaceholderAnonymizer(base_dir=policy.mapping.base_dir)
    result = anonymizer.scrub(text, scan.findings, source="core")
    audit = audit_text(result.scrubbed_text, policy)
    result.audit = audit
    result.ok = audit.safe
    return result


def restore_text(text: str, mapping_path: str) -> str:
    anonymizer = StablePlaceholderAnonymizer.from_mapping_path(mapping_path)
    return anonymizer.restore(text, mapping_path)
```

Create `audit.py` with a stricter threshold using `policy.audit_threshold`.

Update `__init__.py` to export `build_analyzer`, `scan_text`, `scrub_text`, `audit_text`, and `restore_text`.

- [ ] **Step 4: Run API tests**

Run:

```bash
uv run pytest tests/test_core_api.py tests/test_audit.py -v
uv run pytest -v
uv run ruff check packages tests
uv run mypy packages/phi_br_core/phi_br_core
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/phi_br_core/phi_br_core tests/test_core_api.py tests/test_audit.py
git commit -m "feat: expose scan scrub audit restore api"
```

## Task 7: CLI Clipboard, Status, Purge, And Check

**Files:**
- Create: `packages/phi_br_core/phi_br_core/clipboard.py`
- Modify: `packages/phi_br_core/phi_br_core/cli/main.py`
- Test: `tests/test_cli_clipboard.py`

- [ ] **Step 1: Write failing CLI tests with fake clipboard**

Create `tests/test_cli_clipboard.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from phi_br_core.cli.main import app


runner = CliRunner()


def test_redact_and_restore_clipboard(monkeypatch, tmp_path: Path) -> None:
    clipboard = {"text": "Paciente Joao da Silva, CPF 935.411.347-80."}

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("phi_br_core.clipboard.read_clipboard", lambda: clipboard["text"])
    monkeypatch.setattr("phi_br_core.clipboard.write_clipboard", lambda value: clipboard.update(text=value))

    redact = runner.invoke(app, ["redact"])
    assert redact.exit_code == 0
    assert "[PACIENTE_001]" in clipboard["text"]
    assert "[CPF_001]" in clipboard["text"]
    assert "935.411.347-80" not in clipboard["text"]

    restore = runner.invoke(app, ["restore"])
    assert restore.exit_code == 0
    assert clipboard["text"] == "Paciente Joao da Silva, CPF 935.411.347-80."
    assert "935.411.347-80" not in restore.stdout


def test_status_does_not_print_phi(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "active_sessions" in result.stdout
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_cli_clipboard.py -v
```

Expected: FAIL because commands do not exist.

- [ ] **Step 3: Implement macOS clipboard adapter**

Create `clipboard.py`:

```python
from __future__ import annotations

import subprocess


def read_clipboard() -> str:
    completed = subprocess.run(["pbpaste"], check=True, capture_output=True, text=True)
    return completed.stdout


def write_clipboard(value: str) -> None:
    subprocess.run(["pbcopy"], input=value, check=True, text=True)
```

- [ ] **Step 4: Implement CLI commands**

Modify `cli/main.py` so every command acquires lifecycle behavior before action. `redact` reads clipboard, calls `scrub_text`, writes scrubbed text back to clipboard, and prints safe status. `restore` reads clipboard, resolves placeholder owners through the active index, restores, writes back to clipboard, and prints safe status. `status` prints counts only. `purge` deletes expired sessions by default and supports `--all`.

Safe success output for `restore`:

```json
{
  "ok": true,
  "action": "clipboard_restored",
  "printed_phi": false
}
```

- [ ] **Step 5: Verify CLI behavior**

Run:

```bash
uv run pytest tests/test_cli_clipboard.py -v
uv run phi check
uv run ruff check packages tests
uv run mypy packages/phi_br_core/phi_br_core
```

Expected: all pass; `phi check` reports Presidio initialization, custom recognizers, scrub, audit, and writable `.tmp/phi`.

- [ ] **Step 6: Commit**

```bash
git add packages/phi_br_core/phi_br_core/clipboard.py packages/phi_br_core/phi_br_core/cli/main.py tests/test_cli_clipboard.py
git commit -m "feat: add phi clipboard lifecycle cli"
```

## Task 8: Integrate OpenCode `/phi` With The Tested CLI

**Files:**
- Create: `packages/phi_br_firewall_opencode/src/phi.ts`
- Modify: `packages/phi_br_firewall_opencode/src/plugin.ts`
- Modify: `packages/phi_br_firewall_opencode/tests/plugin.test.ts`

- [ ] **Step 1: Replace proof test with CLI-backed redaction test**

Modify `packages/phi_br_firewall_opencode/tests/plugin.test.ts` so the plugin receives a fake runner:

```ts
import { describe, expect, test } from "vitest"
import { createPhiHooks } from "../src/plugin"

describe("Phi OpenCode plugin", () => {
  test("uses redacted text from the local phi runner", async () => {
    const hooks = createPhiHooks(async () => ({
      ok: true,
      scrubbed_text: "Paciente [PACIENTE_001], CPF [CPF_001].",
      session_id: "phi-test",
      summary: { entities_replaced: 2, entity_types: ["BR_PATIENT_NAME", "BR_CPF"] },
    }))
    const output = { parts: [] as Array<{ type: "text"; text: string; synthetic?: boolean }> }

    await hooks["command.execute.before"]?.(
      {
        command: "phi",
        sessionID: "session-1",
        arguments: "Paciente Joao da Silva, CPF 935.411.347-80.",
      },
      output,
    )

    expect(output.parts[0].text).toBe("Paciente [PACIENTE_001], CPF [CPF_001].")
    expect(output.parts[0].text).not.toContain("Joao")
    expect(output.parts[0].text).not.toContain("935.411.347-80")
  })

  test("blocks model-facing text when redaction fails", async () => {
    const hooks = createPhiHooks(async () => ({
      ok: false,
      reason: "audit_failed",
    }))
    const output = { parts: [] as Array<{ type: "text"; text: string; synthetic?: boolean }> }

    await hooks["command.execute.before"]?.(
      {
        command: "phi",
        sessionID: "session-1",
        arguments: "Paciente Joao da Silva, CPF 935.411.347-80.",
      },
      output,
    )

    expect(output.parts[0].text).toContain("PHI redaction failed locally")
    expect(output.parts[0].text).not.toContain("Joao")
    expect(output.parts[0].text).not.toContain("935.411.347-80")
  })
})
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd packages/phi_br_firewall_opencode
npm test -- --run tests/plugin.test.ts
```

Expected: FAIL because `createPhiHooks` and `src/phi.ts` do not exist.

- [ ] **Step 3: Implement safe CLI runner**

Create `src/phi.ts` with a runner that invokes the local `phi` command in a no-raw-output mode. The runner must pass raw text through stdin, parse JSON, and never log raw arguments.

Expected TypeScript result shape:

```ts
export type PhiRedactSuccess = {
  ok: true
  scrubbed_text: string
  session_id: string
  summary: { entities_replaced: number; entity_types: string[] }
}

export type PhiRedactFailure = {
  ok: false
  reason: string
}

export type PhiRedactResult = PhiRedactSuccess | PhiRedactFailure
```

- [ ] **Step 4: Implement `createPhiHooks`**

Modify `src/plugin.ts` to export `createPhiHooks(runner)` for tests and default plugin server for OpenCode. On success, set `output.parts` to one synthetic text part containing `scrubbed_text`. On failure, set a safe blocking text part:

```text
PHI redaction failed locally. The raw prompt was not sent. Run `phi check` and retry.
```

- [ ] **Step 5: Verify TypeScript tests and Python tests**

Run:

```bash
cd packages/phi_br_firewall_opencode
npm run typecheck
npm test -- --run tests/plugin.test.ts
cd ../..
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 6: Manual OpenCode integration test**

Run OpenCode with the local plugin and submit synthetic text:

```text
/phi Estruture em SOAP: Paciente Joao da Silva, CPF 935.411.347-80.
```

Expected model-facing text includes:

```text
[PACIENTE_001]
[CPF_001]
```

Expected model-facing text excludes:

```text
Joao da Silva
935.411.347-80
```

Record command and result in README without raw real patient data.

- [ ] **Step 7: Commit**

```bash
git add README.md packages/phi_br_firewall_opencode
git commit -m "feat: integrate opencode phi command with local redaction"
```

## Task 9: Final Verification And Documentation Pass

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-27-opencode-phi-presidio-design.md` only if implementation changes the accepted contract.

- [ ] **Step 1: Add final README usage**

Document:

```bash
uv sync
uv run phi check
uv run phi redact
uv run phi restore
uv run phi status
uv run phi purge
```

Document OpenCode usage:

```text
/phi <texto livre com prontuario sintetico ou real localmente>
```

State that mappings live in `.tmp/phi/`, expire by default, and are never sent to the model.

- [ ] **Step 2: Run full verification**

Run:

```bash
uv run pytest -v
uv run ruff check packages tests
uv run mypy packages/phi_br_core/phi_br_core
cd packages/phi_br_firewall_opencode
npm run typecheck
npm test -- --run
```

Expected: every command exits 0.

- [ ] **Step 3: Inspect sensitive files before final commit**

Run:

```bash
git status --short
find .tmp -maxdepth 3 -type f 2>/dev/null | sort
git check-ignore .tmp/phi/example/mapping.json raw_clinical/example.txt paciente-real.txt
```

Expected:

```text
.tmp/phi/example/mapping.json
raw_clinical/example.txt
paciente-real.txt
```

The `find .tmp` command may print test artifacts; purge them before commit:

```bash
rm -rf .tmp
```

- [ ] **Step 4: Commit docs and final cleanup**

```bash
git add README.md docs/superpowers/specs/2026-05-27-opencode-phi-presidio-design.md
git commit -m "docs: document phi mvp usage and safety"
```

## Self-Review Checklist

Spec coverage:

- OpenCode-first `/phi <texto livre>` is covered by Tasks 2 and 8.
- Presidio-first core is covered by Tasks 3, 4, and 6.
- Stable reversible placeholders are covered by Task 5.
- `phi redact` and `phi restore` clipboard UX are covered by Task 7.
- Automatic `purge --expired` on every command is covered by Tasks 5 and 7.
- Multiple simultaneous sessions without manual session ids are covered by Task 5 and Task 7.
- No automatic restore inside OpenCode transcript is preserved by Task 8.
- Sensitive file ignore rules are covered before this plan and rechecked in Task 9.

Plan constraints:

- Every implementation task starts with failing tests or an explicit proof.
- Raw clinical text in tests is synthetic.
- No task requires external PHI/PII detection APIs.
- No command prints mappings or restored PHI by design.
