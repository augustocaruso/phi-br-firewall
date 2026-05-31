# GitHub Beta Distribution Design

## Goal

Make `phi-br-firewall` installable by trusted early users from GitHub without
publishing to PyPI or npm yet.

The beta distribution must install two local pieces:

1. the Python `phi` CLI, installed with `uv tool install`;
2. the OpenCode plugin, loaded from a generated wrapper in the user's global
   OpenCode plugin directory.

## Public Positioning

This release is a local-first safety tool, not a de-identification guarantee.
The README and installer must say that Phi reduces PHI/PII leakage risk but is
not perfect, can miss identifiers, and requires human review before sending
clinical text to an external model or service.

## Installation Contract

The first beta install path is GitHub-only:

```bash
curl -fsSL https://raw.githubusercontent.com/augustocaruso/phi-br-firewall/main/scripts/install.sh | bash
```

The installer:

1. ensures `uv` exists, using Astral's official installer when missing;
2. clones or updates the GitHub repository under
   `~/.local/share/phi-br-firewall/repo` by default;
3. installs the CLI from that local checkout with `uv tool install --force`;
4. writes `~/.config/opencode/plugins/phi-br-firewall.ts`;
5. runs `phi check`;
6. tells the user to restart OpenCode and use `/phi <texto>`.

The installer does not edit `opencode.json`. This avoids JSON/JSONC mutation
and uses OpenCode's documented global plugin autoload directory instead.

## Uninstall Contract

`scripts/uninstall.sh` removes the generated OpenCode wrapper and uninstalls
the `uv` tool. It does not delete clinical mapping sessions by default because
those may live in project-local `.tmp/phi` directories. Users should run
`phi purge --all` from relevant projects before uninstalling if they want to
remove active mappings.

## Non-Goals

- No PyPI publication in this step.
- No npm publication in this step.
- No auto-update daemon.
- No claim of HIPAA, LGPD, or institutional compliance.
- No silent deletion of patient mapping files outside the managed install
  directory.

## Verification

Before publishing:

1. run Python tests and static checks;
2. run OpenCode plugin typecheck and tests;
3. run `phi check`;
4. validate `scripts/install.sh` with a temporary OpenCode config directory;
5. confirm OpenCode sees `/phi` after installing through the generated wrapper.
