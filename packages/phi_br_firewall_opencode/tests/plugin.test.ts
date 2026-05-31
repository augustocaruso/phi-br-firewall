import { describe, expect, test } from "vitest"
import { createPhiHooks } from "../src/hooks.js"
import { server } from "../src/plugin.js"

const pluginInput = {
  client: {} as never,
  project: {} as never,
  directory: "/tmp/phi-test",
  worktree: "/tmp/phi-test",
  experimental_workspace: { register() {} },
  serverUrl: new URL("http://localhost"),
  $: {} as never,
}

describe("Phi OpenCode plugin", () => {
  test("entrypoint exposes only the server plugin function", async () => {
    const module = await import("../src/plugin.js")

    expect(Object.keys(module).sort()).toEqual(["server"])
  })

  test("registers the phi command in OpenCode config", async () => {
    const hooks = await server(pluginInput)
    const config = {}

    await hooks.config?.(config as never)

    expect(config).toEqual({
      command: {
        phi: {
          template: "$ARGUMENTS",
          description: "Redact PHI locally before sending text to the model",
        },
      },
    })
  })

  test("uses runner redacted text for command output without replacing the parts array", async () => {
    const hooks = createPhiHooks(async (text, sessionID) => {
      expect(text).toBe("Paciente Joao CPF 123.456.789-09")
      expect(sessionID).toBe("session-1")
      return {
        ok: true,
        scrubbed_text: "Paciente [PACIENTE_001] CPF [CPF_001]",
        session_id: "phi-session-1",
        summary: { entities_replaced: 2, entity_types: ["BR_CPF", "BR_PATIENT_NAME"] },
      }
    })

    const output = { parts: [] as Array<{ type: "text"; text: string; synthetic?: boolean }> }
    const originalParts = output.parts

    await hooks["command.execute.before"]?.(
      {
        command: "phi",
        sessionID: "session-1",
        arguments: "Paciente Joao CPF 123.456.789-09",
      },
      output as never,
    )

    expect(output.parts).toBe(originalParts)
    expect(output.parts).toEqual([
      {
        type: "text",
        text: "Paciente [PACIENTE_001] CPF [CPF_001]",
        synthetic: true,
      },
    ])
    expect(JSON.stringify(output.parts)).not.toContain("Joao")
    expect(JSON.stringify(output.parts)).not.toContain("123.456.789-09")
  })

  test("aborts command execution instead of sending a diagnostic prompt when redaction fails", async () => {
    const hooks = createPhiHooks(async () => ({
      ok: false,
      reason: "audit_failed",
    }))

    const output = { parts: [] as Array<{ type: "text"; text: string; synthetic?: boolean }> }
    const originalParts = output.parts

    await expect(
      hooks["command.execute.before"]?.(
        {
          command: "phi",
          sessionID: "session-1",
          arguments: "Paciente Joao CPF 123.456.789-09",
        },
        output as never,
      ),
    ).rejects.toThrow("PHI_REDACTION_FAILED")

    expect(output.parts).toBe(originalParts)
    expect(output.parts).toEqual([
      {
        type: "text",
        text: "[PHI_REDACTION_FAILED]",
        synthetic: true,
      },
    ])
    expect(JSON.stringify(output.parts)).not.toContain("Joao")
    expect(JSON.stringify(output.parts)).not.toContain("123.456.789-09")
    expect(JSON.stringify(output.parts)).not.toContain("phi check")
  })

  test("aborts slash phi chat messages without leaking raw text when redaction fails", async () => {
    const hooks = createPhiHooks(async () => ({
      ok: false,
      reason: "cli_timeout",
    }))

    const output = {
      message: {} as never,
      parts: [
        {
          id: "part-1",
          sessionID: "session-1",
          messageID: "message-1",
          type: "text",
          text: "/phi Paciente Joao CPF 123.456.789-09",
          metadata: "raw: Paciente Joao CPF 123.456.789-09",
        },
      ],
    }
    const originalParts = output.parts

    await expect(
      hooks["chat.message"]?.(
        {
          sessionID: "session-1",
        },
        output as never,
      ),
    ).rejects.toThrow("PHI_REDACTION_FAILED")

    expect(output.parts).toBe(originalParts)
    expect(output.parts).toEqual([
      {
        type: "text",
        text: "[PHI_REDACTION_FAILED]",
        synthetic: true,
      },
    ])
    expect(JSON.stringify(output.parts)).not.toContain("Joao")
    expect(JSON.stringify(output.parts)).not.toContain("123.456.789-09")
    expect(JSON.stringify(output.parts)).not.toContain("phi check")
  })

  test("ignores non-phi commands", async () => {
    const hooks = createPhiHooks(async () => {
      throw new Error("runner should not be called")
    })

    const output = { parts: [] as Array<{ type: "text"; text: string; synthetic?: boolean }> }

    await hooks["command.execute.before"]?.(
      {
        command: "other",
        sessionID: "session-1",
        arguments: "Paciente Joao CPF 123.456.789-09",
      },
      output as never,
    )

    expect(output.parts).toEqual([])
  })

  test("redacts slash phi chat messages before model dispatch", async () => {
    const hooks = createPhiHooks(async (text, sessionID) => {
      expect(text).toBe("Paciente Joao CPF 123.456.789-09")
      expect(sessionID).toBe("session-1")
      return {
        ok: true,
        scrubbed_text: "Paciente [PACIENTE_001] CPF [CPF_001]",
        session_id: "phi-session-1",
        summary: { entities_replaced: 2, entity_types: ["BR_CPF", "BR_PATIENT_NAME"] },
      }
    })

    const output = {
      message: {} as never,
      parts: [
        {
          id: "part-1",
          sessionID: "session-1",
          messageID: "message-1",
          type: "text",
          text: "/phi Paciente Joao CPF 123.456.789-09",
          metadata: "raw: Paciente Joao CPF 123.456.789-09",
        },
      ],
    }
    const originalParts = output.parts

    await hooks["chat.message"]?.(
      {
        sessionID: "session-1",
      },
      output as never,
    )

    expect(output.parts).toBe(originalParts)
    expect(output.parts).toEqual([
      {
        type: "text",
        text: "Paciente [PACIENTE_001] CPF [CPF_001]",
        synthetic: true,
      },
    ])
    expect(JSON.stringify(output.parts)).not.toContain("Joao")
    expect(JSON.stringify(output.parts)).not.toContain("123.456.789-09")
    expect(JSON.stringify(output.parts)).not.toContain("raw:")
  })

  test("redacts slash phi messages during model transform", async () => {
    const hooks = createPhiHooks(async (text, sessionID) => {
      expect(text).toBe("Paciente Joao CPF 123.456.789-09")
      expect(sessionID).toBe("session-1")
      return {
        ok: true,
        scrubbed_text: "Paciente [PACIENTE_001] CPF [CPF_001]",
        session_id: "phi-session-1",
        summary: { entities_replaced: 2, entity_types: ["BR_CPF", "BR_PATIENT_NAME"] },
      }
    })

    const output = {
      messages: [
        {
          info: {} as never,
          parts: [
            {
              id: "part-1",
              sessionID: "session-1",
              messageID: "message-1",
              type: "text",
              text: "/phi Paciente Joao CPF 123.456.789-09",
              metadata: "raw: Paciente Joao CPF 123.456.789-09",
            },
          ],
        },
      ],
    }
    const originalParts = output.messages[0]?.parts

    await hooks["experimental.chat.messages.transform"]?.({}, output as never)

    expect(output.messages[0]?.parts).toBe(originalParts)
    expect(output.messages[0]?.parts).toEqual([
      {
        type: "text",
        text: "Paciente [PACIENTE_001] CPF [CPF_001]",
        synthetic: true,
      },
    ])
    expect(JSON.stringify(output.messages)).not.toContain("Joao")
    expect(JSON.stringify(output.messages)).not.toContain("123.456.789-09")
    expect(JSON.stringify(output.messages)).not.toContain("raw:")
  })
})
