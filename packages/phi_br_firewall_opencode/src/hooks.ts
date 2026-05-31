import type { Hooks } from "@opencode-ai/plugin"
import type { PhiRunner } from "./phi.js"

const failurePlaceholder = "[PHI_REDACTION_FAILED]"

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
  if (!result.ok) failClosed(parts, result.reason)
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

function failClosed(parts: TextPart[], reason: string): never {
  replaceCommandParts(parts, failurePlaceholder)
  throw new Error(`PHI_REDACTION_FAILED: raw prompt blocked before model dispatch (${reason})`)
}

export function createPhiHooks(runner: PhiRunner): Hooks {
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
      if (!result.ok) failClosed(output.parts as TextPart[], result.reason)
      replaceCommandParts(output.parts as TextPart[], result.scrubbed_text)
    },
  }
}
