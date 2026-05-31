import { spawn } from "node:child_process"
import { existsSync } from "node:fs"
import { dirname, join, parse } from "node:path"

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
export type PhiRunner = (text: string, sessionID?: string) => Promise<PhiRedactResult>

type CliPayload = {
  ok?: unknown
  scrubbed_text?: unknown
  session_id?: unknown
  summary?: unknown
  reason?: unknown
}

export const runPhiCli: PhiRunner = async (text) => {
  const result = await runProcess(resolvePhiCommand(), ["scrub-stdin", "--json"], text)
  if (!result.ok) return { ok: false, reason: result.reason }

  let payload: CliPayload
  try {
    payload = JSON.parse(result.stdout) as CliPayload
  } catch {
    return { ok: false, reason: "invalid_json" }
  }

  if (payload.ok !== true) {
    return {
      ok: false,
      reason: typeof payload.reason === "string" ? payload.reason : "redaction_failed",
    }
  }

  if (typeof payload.scrubbed_text !== "string" || payload.scrubbed_text.length === 0) {
    return { ok: false, reason: "missing_scrubbed_text" }
  }
  if (typeof payload.session_id !== "string") {
    return { ok: false, reason: "missing_session_id" }
  }
  if (!isSummary(payload.summary)) {
    return { ok: false, reason: "invalid_summary" }
  }

  return {
    ok: true,
    scrubbed_text: payload.scrubbed_text,
    session_id: payload.session_id,
    summary: payload.summary,
  }
}

function resolvePhiCommand() {
  if (process.env.PHI_CLI_COMMAND) return process.env.PHI_CLI_COMMAND

  let directory = process.cwd()
  const root = parse(directory).root
  while (true) {
    const candidate = join(directory, ".venv", "bin", "phi")
    if (existsSync(candidate)) return candidate
    if (directory === root) return "phi"
    directory = dirname(directory)
  }
}

function runProcess(
  command: string,
  args: string[],
  stdin: string,
): Promise<{ ok: true; stdout: string } | { ok: false; reason: string }> {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      stdio: ["pipe", "pipe", "pipe"],
      env: process.env,
    })
    let stdout = ""

    child.stdout.setEncoding("utf8")
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk
    })
    child.stderr.resume()

    child.on("error", () => {
      resolve({ ok: false, reason: "cli_spawn_failed" })
    })

    child.on("close", (code) => {
      if (code !== 0) {
        resolve({ ok: false, reason: "cli_exit_nonzero" })
        return
      }
      resolve({ ok: true, stdout })
    })

    child.stdin.end(stdin)
  })
}

function isSummary(value: unknown): value is PhiRedactSuccess["summary"] {
  if (typeof value !== "object" || value === null) return false
  const summary = value as { entities_replaced?: unknown; entity_types?: unknown }
  return (
    typeof summary.entities_replaced === "number" &&
    Array.isArray(summary.entity_types) &&
    summary.entity_types.every((entity) => typeof entity === "string")
  )
}
