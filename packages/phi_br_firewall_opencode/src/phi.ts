import { spawn } from "node:child_process"
import { existsSync } from "node:fs"
import { dirname, join, parse, resolve } from "node:path"

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

export type PhiRunnerOptions = {
  command?: string
  searchStart?: string
  timeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 15_000

type CliPayload = {
  ok?: unknown
  redacted_text?: unknown
  scrubbed_text?: unknown
  session_id?: unknown
  summary?: unknown
  reason?: unknown
}

export function createPhiRunner(options: PhiRunnerOptions = {}): PhiRunner {
  return async (text) => {
    const searchStart = options.searchStart ?? process.cwd()
    const result = await runProcess(
      resolvePhiCommand(searchStart, options.command),
      ["api", "redact", "--json"],
      text,
      {
        cwd: searchStart,
        timeoutMs: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
      },
    )
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

    const redactedText =
      typeof payload.redacted_text === "string"
        ? payload.redacted_text
        : payload.scrubbed_text
    if (typeof redactedText !== "string" || redactedText.length === 0) {
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
      scrubbed_text: redactedText,
      session_id: payload.session_id,
      summary: payload.summary,
    }
  }
}

export const runPhiCli: PhiRunner = createPhiRunner()

function resolvePhiCommand(searchStart: string, command = process.env.PHI_CLI_COMMAND) {
  if (command) return command

  let directory = resolve(searchStart)
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
  options: { cwd: string; timeoutMs: number },
): Promise<{ ok: true; stdout: string } | { ok: false; reason: string }> {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      stdio: ["pipe", "pipe", "pipe"],
      env: process.env,
      cwd: options.cwd,
    })
    let stdout = ""
    let settled = false

    const settle = (result: { ok: true; stdout: string } | { ok: false; reason: string }) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      resolve(result)
    }

    const timeout = setTimeout(() => {
      if (!child.killed) child.kill("SIGKILL")
      settle({ ok: false, reason: "cli_timeout" })
    }, options.timeoutMs)

    child.stdout.setEncoding("utf8")
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk
    })
    child.stderr.resume()
    child.stdin.on("error", () => {
      if (!child.killed) child.kill("SIGKILL")
      settle({ ok: false, reason: "stdin_pipe_failed" })
    })

    child.on("error", () => {
      settle({ ok: false, reason: "cli_spawn_failed" })
    })

    child.on("close", (code) => {
      if (code !== 0) {
        settle({ ok: false, reason: "cli_exit_nonzero" })
        return
      }
      settle({ ok: true, stdout })
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
