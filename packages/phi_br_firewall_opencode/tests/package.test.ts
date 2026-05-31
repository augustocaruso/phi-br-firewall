import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, test } from "vitest"

const packageDir = resolve(dirname(fileURLToPath(import.meta.url)), "..")

describe("OpenCode package manifest", () => {
  test("exposes a server plugin entrypoint for opencode plugin install", async () => {
    const manifest = JSON.parse(
      await readFile(resolve(packageDir, "package.json"), "utf8"),
    ) as {
      main?: unknown
      exports?: Record<string, unknown>
    }

    expect(manifest.main).toBe("./src/plugin.ts")
    expect(manifest.exports?.["./server"]).toBe("./src/plugin.ts")
  })
})
