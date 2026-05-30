import type { Plugin } from "@opencode-ai/plugin"

const proofText = "PHI proof replacement: [PACIENTE_001] [CPF_001]"

function isPhiText(text: string) {
  return text.trim().startsWith("/phi ")
}

function replacePhiParts<T extends { type: string; text?: string; synthetic?: boolean }>(parts: T[]) {
  const firstTextPart = parts.find((part) => part.type === "text")
  if (!firstTextPart?.text || !isPhiText(firstTextPart.text)) return false
  parts.splice(0, parts.length, {
    ...firstTextPart,
    text: proofText,
    synthetic: true,
  })
  return true
}

export const PhiPlugin: Plugin = async () => {
  return {
    async config(config) {
      config.command ??= {}
      config.command.phi = {
        template: "$ARGUMENTS",
        description: "PHI proof command",
      }
    },
    async "chat.message"(_input, output) {
      replacePhiParts(output.parts)
    },
    async "experimental.chat.messages.transform"(_input, output) {
      for (const message of output.messages) {
        replacePhiParts(message.parts)
      }
    },
    async "command.execute.before"(input, output) {
      if (input.command !== "phi") return
      output.parts.length = 0
      output.parts.push({
        type: "text",
        text: proofText,
        synthetic: true,
      } as (typeof output.parts)[number])
    },
  }
}

export default PhiPlugin
