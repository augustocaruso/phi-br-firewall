import { chmod, mkdir, mkdtemp, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { afterEach, describe, expect, test } from "vitest"
import { createPhiRunner } from "../src/phi.js"

const originalPhiCliCommand = process.env.PHI_CLI_COMMAND
const originalCwd = process.cwd()

afterEach(() => {
  if (originalPhiCliCommand === undefined) {
    delete process.env.PHI_CLI_COMMAND
  } else {
    process.env.PHI_CLI_COMMAND = originalPhiCliCommand
  }
  process.chdir(originalCwd)
})

async function makeProjectPhi(projectDir: string, script: string) {
  const binDir = join(projectDir, ".venv", "bin")
  await mkdir(binDir, { recursive: true })
  const phiPath = join(binDir, "phi")
  await writeFile(phiPath, `#!/bin/sh\n${script}`, { encoding: "utf8" })
  await chmod(phiPath, 0o755)
  return phiPath
}

describe("phi CLI runner", () => {
  test("resolves project-local phi from the OpenCode worktree instead of process cwd", async () => {
    delete process.env.PHI_CLI_COMMAND
    const root = await mkdtemp(join(tmpdir(), "phi-runner-"))
    const projectDir = join(root, "project")
    const nestedDir = join(projectDir, "nested")
    const otherDir = join(root, "other")
    await mkdir(nestedDir, { recursive: true })
    await mkdir(otherDir, { recursive: true })
    await makeProjectPhi(
      projectDir,
      String.raw`
raw="$(cat)"
case "$*" in
  *Joao*|*935.411.347-80*) echo '{"ok":false,"reason":"raw_in_args"}'; exit 0 ;;
esac
if [ "$*" != "api redact --json" ]; then
  echo '{"ok":false,"reason":"wrong_args"}'
  exit 0
fi
if [ "$raw" = "Paciente Joao CPF 935.411.347-80" ]; then
  echo '{"ok":true,"action":"redact","redacted_text":"Paciente [PACIENTE_001] CPF [CPF_001]","session_id":"phi-test","summary":{"entities_replaced":2,"entity_types":["BR_PATIENT_NAME","BR_CPF"]}}'
else
  echo '{"ok":false,"reason":"stdin_missing"}'
fi
`,
    )

    process.chdir(otherDir)
    const runner = createPhiRunner({ searchStart: nestedDir })

    const result = await runner("Paciente Joao CPF 935.411.347-80")

    expect(result).toEqual({
      ok: true,
      scrubbed_text: "Paciente [PACIENTE_001] CPF [CPF_001]",
      session_id: "phi-test",
      summary: { entities_replaced: 2, entity_types: ["BR_PATIENT_NAME", "BR_CPF"] },
    })
  })

  test("fails closed when the CLI exits before consuming stdin", async () => {
    delete process.env.PHI_CLI_COMMAND
    const projectDir = await mkdtemp(join(tmpdir(), "phi-runner-exit-"))
    await makeProjectPhi(projectDir, "exit 1\n")
    const runner = createPhiRunner({ searchStart: projectDir })

    const result = await runner("Paciente Joao CPF 935.411.347-80".repeat(100_000))

    expect(result.ok).toBe(false)
    expect(JSON.stringify(result)).not.toContain("Joao")
    expect(JSON.stringify(result)).not.toContain("935.411.347-80")
  })

  test("times out and fails closed when the CLI hangs", async () => {
    delete process.env.PHI_CLI_COMMAND
    const projectDir = await mkdtemp(join(tmpdir(), "phi-runner-timeout-"))
    await makeProjectPhi(projectDir, "sleep 5\n")
    const runner = createPhiRunner({ searchStart: projectDir, timeoutMs: 25 })

    const result = await runner("Paciente Joao CPF 935.411.347-80")

    expect(result).toEqual({ ok: false, reason: "cli_timeout" })
  })
})
