# phi-br-presidio-firewall

Local-first PHI/PII redaction for Brazilian Portuguese clinical text.

The MVP uses Microsoft Presidio for local detection, stable local placeholders for reversible pseudonymization, and an OpenCode `/phi` command so raw clinical text is redacted before it reaches a model.

Public commands:

```bash
phi check
phi redact
phi restore
phi status
phi purge
```

Runtime mappings live under `.tmp/phi/` and are ignored by Git.
