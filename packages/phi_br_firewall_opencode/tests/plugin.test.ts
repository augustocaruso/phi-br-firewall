import { describe, expect, test } from "vitest"
import PhiPlugin from "../src/plugin.js"

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
  test("registers the phi command in OpenCode config", async () => {
    const hooks = await PhiPlugin(pluginInput)
    const config = {}

    await hooks.config?.(config as never)

    expect(config).toEqual({
      command: {
        phi: {
          template: "$ARGUMENTS",
          description: "PHI proof command",
        },
      },
    })
  })

  test("replaces raw /phi arguments with safe text parts", async () => {
    const hooks = await PhiPlugin(pluginInput)

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
        text: "PHI proof replacement: [PACIENTE_001] [CPF_001]",
        synthetic: true,
      },
    ])
  })

  test("replaces slash phi chat messages before model dispatch", async () => {
    const hooks = await PhiPlugin(pluginInput)

    const output = {
      message: {} as never,
      parts: [
        {
          id: "part-1",
          sessionID: "session-1",
          messageID: "message-1",
          type: "text",
          text: "/phi Paciente Joao CPF 123.456.789-09",
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
        id: "part-1",
        sessionID: "session-1",
        messageID: "message-1",
        type: "text",
        text: "PHI proof replacement: [PACIENTE_001] [CPF_001]",
        synthetic: true,
      },
    ])
  })

  test("replaces slash phi messages during model transform", async () => {
    const hooks = await PhiPlugin(pluginInput)

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
        id: "part-1",
        sessionID: "session-1",
        messageID: "message-1",
        type: "text",
        text: "PHI proof replacement: [PACIENTE_001] [CPF_001]",
        synthetic: true,
      },
    ])
  })
})
