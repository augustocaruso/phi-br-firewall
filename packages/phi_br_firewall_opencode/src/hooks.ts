import type { Hooks, PluginInput } from "@opencode-ai/plugin"
import type { PhiRunner } from "./phi.js"

const failurePlaceholder = "[PHI_REDACTION_FAILED]"

type OpenCodeClient = PluginInput["client"]
type HookOptions = {
  client?: OpenCodeClient
}

function isPhiText(text: string) {
  return text.trim().startsWith("/phi ")
}

type TextPart = { type: string; text?: string; synthetic?: boolean; [key: string]: unknown }

function phiText(text: string) {
  return text.trim().replace(/^\/phi\s+/, "")
}

async function replacePhiParts(
  parts: TextPart[],
  runner: PhiRunner,
  sessionID?: string,
) {
  const firstTextPart = parts.find((part) => part.type === "text")
  if (!firstTextPart?.text || !isPhiText(firstTextPart.text)) return false
  const result = await runner(phiText(firstTextPart.text), sessionID)
  if (!result.ok) {
    replaceCommandParts(parts, failureMessage(result.reason))
    return true
  }
  replaceCommandParts(parts, result.scrubbed_text)
  return true
}

function replaceCommandParts(parts: TextPart[], text: string) {
  parts.splice(0, parts.length, {
    type: "text",
    text,
    synthetic: true,
  })
}

function failureMessage(reason: string) {
  const safeReason = reason.replace(/[^A-Za-z0-9_.:-]/g, "_").slice(0, 80) || "unknown"
  return `${failurePlaceholder}\nResponda ao usuario exatamente: "Phi bloqueou esta mensagem antes do modelo. Motivo: ${safeReason}."`
}

async function printVisibleRedactedInput(
  client: OpenCodeClient | undefined,
  sessionID: string | undefined,
  text: string,
) {
  if (!client || !sessionID) return
  try {
    await client.session.prompt({
      path: { id: sessionID },
      body: {
        noReply: true,
        parts: [
          {
            type: "text",
            text,
            ignored: true,
          },
        ],
      },
    })
  } catch {
    // The redacted model payload below is still the enforcement path.
  }
}

export function createPhiHooks(runner: PhiRunner, options: HookOptions = {}): Hooks {
  return {
    async config(config) {
      config.command ??= {}
      config.command.phi = {
        template: "$ARGUMENTS",
        description: "Redact PHI locally before sending text to the model",
      }
    },
    async "chat.message"(input, output) {
      await replacePhiParts(output.parts as TextPart[], runner, input.sessionID)
    },
    async "experimental.chat.messages.transform"(_input, output) {
      for (const message of output.messages) {
        const parts = message.parts as TextPart[]
        const firstTextPart = parts.find((part) => part.type === "text")
        const sessionID =
          firstTextPart && "sessionID" in firstTextPart
            ? String(firstTextPart.sessionID)
            : undefined
        await replacePhiParts(parts, runner, sessionID)
      }
    },
    async "command.execute.before"(input, output) {
      if (input.command !== "phi") return
      const result = await runner(input.arguments, input.sessionID)
      if (!result.ok) {
        replaceCommandParts(output.parts as TextPart[], failureMessage(result.reason))
        return
      }
      replaceCommandParts(output.parts as TextPart[], result.scrubbed_text)
      await printVisibleRedactedInput(options.client, input.sessionID, result.scrubbed_text)
    },
  }
}
