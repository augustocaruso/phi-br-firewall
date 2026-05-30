# phi-br-presidio-firewall

Local-first PHI/PII redaction for Brazilian Portuguese clinical text.

The MVP uses Microsoft Presidio for local detection, stable local placeholders for reversible pseudonymization, and an OpenCode `/phi` command so raw clinical text is redacted before it reaches a model.

Currently implemented baseline verification command:

```bash
phi check
```

Planned public MVP commands:

```bash
phi redact
phi restore
phi status
phi purge
```

Runtime mappings live under `.tmp/phi/` and are ignored by Git.

## OpenCode proof

Task 2 proved the command-replacement path with synthetic text only:

```bash
opencode run --command phi --title phi-proof-task2-20260530 "Paciente Joao CPF 123.456.789-09" --format json --print-logs --log-level INFO
```

The OpenCode session database stored `PHI proof replacement: [PACIENTE_001] [CPF_001]` for the user text part and did not store the synthetic raw name or CPF in that proof session.
