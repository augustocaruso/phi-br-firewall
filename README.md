# phi-br-firewall

Local-first PHI/PII redaction for Brazilian Portuguese clinical text.

Phi uses Microsoft Presidio plus Brazilian healthcare recognizers to redact
text before it reaches an AI model. It keeps reversible placeholder mappings on
your machine so you can restore text locally when needed.

## Important Disclaimer

Phi reduces the risk of leaking PHI/PII, but it is not perfect and must not be
treated as a guarantee of de-identification. It can miss names, institutions,
addresses, dates, gendered clues, rare identifiers, or context-specific details.

Always review redacted text before sending it to any external model or service.
This project is not a HIPAA, LGPD, institutional compliance, or medical safety
certification.

## Install Beta From GitHub

macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/augustocaruso/phi-br-firewall/main/scripts/install.sh | bash
```

The installer:

1. installs `uv` if it is missing;
2. clones this repo into `~/.local/share/phi-br-firewall/repo`;
3. installs the `phi` CLI with `uv tool install`;
4. installs an OpenCode plugin wrapper in `~/.config/opencode/plugins/`;
5. runs `phi check`.

Then restart OpenCode and use:

```text
/phi <texto livre com prontuario>
```

To inspect the installer before running it:

```bash
curl -fsSL https://raw.githubusercontent.com/augustocaruso/phi-br-firewall/main/scripts/install.sh -o /tmp/phi-install.sh
less /tmp/phi-install.sh
bash /tmp/phi-install.sh
```

To update, run the installer again.

To uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/augustocaruso/phi-br-firewall/main/scripts/uninstall.sh | bash
```

## Mental Model

Phi has two jobs:

1. detect PHI/PII locally with Presidio plus Brazilian healthcare recognizers;
2. replace each value with a stable placeholder while keeping the reversible
   mapping local.

Example:

```text
Paciente Joao da Silva, CPF 935.411.347-80.
```

becomes:

```text
Paciente [PACIENTE_001], CPF [CPF_001].
```

The model sees the placeholder text. The mapping stays local.

## OpenCode Workflow

In OpenCode:

```text
/phi Paciente Joao da Silva, CPF 935.411.347-80. Resuma o caso.
```

The plugin redacts the prompt locally, prints the redacted input in the
transcript, and sends only the redacted text to the model.

If redaction fails, the plugin fails closed: the raw prompt is not sent to the
model.

## Clipboard Workflow

Copy clinical text to the clipboard, then run:

```bash
phi redact
```

The clipboard is replaced with redacted text. The command prints only a small
JSON status object, never the original clinical text.

After an LLM returns text containing placeholders, copy that text and run:

```bash
phi restore
```

The clipboard is replaced with locally restored text. Restore avoids printing
the recovered PHI to stdout.

Useful lifecycle commands:

```bash
phi check
phi status
phi purge
phi purge --all
```

Every public command runs expired-session cleanup first.

## Programmatic API

Use `phi api` when another program or agent needs stdin/stdout behavior without
touching the clipboard:

```bash
printf '%s' 'Paciente Joao da Silva, CPF 935.411.347-80.' | phi api redact --json
```

The response contains redacted text only:

```json
{
  "ok": true,
  "action": "redact",
  "redacted_text": "Paciente [PACIENTE_001], CPF [CPF_001].",
  "session_id": "phi-...",
  "summary": {
    "entities_replaced": 2,
    "entity_types": ["BR_CPF", "BR_PATIENT_NAME"]
  }
}
```

To restore placeholders through stdout:

```bash
printf '%s' 'Paciente [PACIENTE_001], CPF [CPF_001].' | phi api restore --json
```

Successful restore output contains PHI by definition and is marked explicitly:

```json
{
  "ok": true,
  "action": "restore",
  "restored_text": "Paciente Joao da Silva, CPF 935.411.347-80.",
  "contains_phi": true,
  "sessions_used": ["phi-..."]
}
```

Python callers can use the same non-clipboard contract:

```python
from phi_br_core import PhiPolicy, redact_text, restore_active_text

policy = PhiPolicy()
redacted = redact_text(raw_text, policy)
restored = restore_active_text(redacted.redacted_text, policy)
```

## Sessions And Mappings

Runtime mappings live under the current working directory by default:

```text
.tmp/phi/<session_id>/mapping.json
```

The placeholder index lives at:

```text
.tmp/phi/index.json
```

These files are ignored by Git. They are needed for reversible restore, so keep
them only as long as the session is useful. Use `phi purge --all` from the
relevant project folder to remove local sessions.

Multiple active sessions can coexist. Phi resolves ownership from the
placeholder numbers in the text, so users do not need to pass session IDs.

## Current Limitations

- Beta quality. Expect false negatives and false positives.
- MVP recognizers are Presidio-first with regex/context heuristics, not a full
  Portuguese clinical NLP pipeline.
- Local mappings are not encrypted yet.
- Redaction does not remove every clinically identifying clue.
- Restore is local and placeholder-based; it does not rewrite free prose that no
  longer contains placeholders.
- You are responsible for reviewing redacted text before model use.

## Development

```bash
uv sync
uv run pytest -v
uv run ruff check packages tests
uv run mypy packages/phi_br_core/phi_br_core

cd packages/phi_br_firewall_opencode
npm run typecheck
npm test -- --run
```

Manual local install from a checkout:

```bash
uv tool install -e . --force
phi check
```
