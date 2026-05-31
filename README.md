# phi-br-presidio-firewall

Local-first PHI/PII redaction for Brazilian Portuguese clinical text.

The MVP uses Microsoft Presidio for local detection, stable local placeholders
for reversible pseudonymization, and an OpenCode `/phi` command so raw clinical
text is redacted before it reaches a model.

## Mental model

`phi` has two jobs:

1. detect PHI/PII locally with Presidio plus Brazilian healthcare recognizers;
2. replace each value with a stable placeholder and keep the reversible mapping
   only on this machine.

Example:

```text
Paciente Joao da Silva, CPF 935.411.347-80.
```

becomes:

```text
Paciente [PACIENTE_001], CPF [CPF_001].
```

The model sees the placeholder text. The mapping stays local.

## Setup

```bash
uv sync
uv run phi check
```

`phi check` verifies imports, Presidio startup, custom recognizers, a simple
scrub/audit pass, and write access to the local session directory.

## Clipboard workflow

Copy clinical text to the clipboard, then run:

```bash
uv run phi redact
```

The clipboard is replaced with the redacted text. The command prints only a
small JSON status object, never the original clinical text.

After the LLM returns text containing placeholders, copy that text to the
clipboard and run:

```bash
uv run phi restore
```

The clipboard is replaced with restored local text. Restore also avoids printing
the recovered PHI to stdout.

Useful lifecycle commands:

```bash
uv run phi status
uv run phi purge
uv run phi purge --all
```

Every public command runs expired-session cleanup first.

## Sessions and mappings

Runtime mappings live under:

```text
.tmp/phi/<session_id>/mapping.json
```

The placeholder index lives at:

```text
.tmp/phi/index.json
```

These files are ignored by Git. They are needed for reversible restore, so keep
them only as long as the session is useful. Use `uv run phi purge --all` to
remove all local sessions.

Multiple active sessions can coexist. The CLI resolves ownership from the
placeholder numbers in the text, so users do not need to pass session ids.

## OpenCode workflow

Load the local OpenCode plugin from:

```text
packages/phi_br_firewall_opencode
```

Then use:

```text
/phi <texto livre com prontuario>
```

The plugin calls the local `phi` CLI through stdin and mutates the OpenCode
message parts in place. On success, only the redacted text is sent onward. On
failure, the model-facing text becomes:

```text
PHI redaction failed locally. The raw prompt was not sent. Run `phi check` and retry.
```

OpenCode does not automatically restore placeholders inside the transcript in
this MVP. Restoration stays local through `phi restore`.

## OpenCode proof

Task 2 proved the command-replacement path with synthetic text only:

```bash
opencode run --command phi --title phi-proof-task2-20260530 "Paciente Joao CPF 123.456.789-09" --format json --print-logs --log-level INFO
```

The OpenCode session database stored
`PHI proof replacement: [PACIENTE_001] [CPF_001]` for the user text part and did
not store the synthetic raw name or CPF in that proof session.

Task 8 added the CLI-backed runner. Automated coverage verifies that the runner
passes raw text via stdin, resolves the project-local `phi`, times out safely,
fails closed on pipe errors, and avoids preserving raw metadata fields in
model-facing OpenCode parts.

## Development checks

```bash
uv run pytest -v
uv run ruff check packages tests
uv run mypy packages/phi_br_core/phi_br_core
cd packages/phi_br_firewall_opencode
npm run typecheck
npm test -- --run
```
