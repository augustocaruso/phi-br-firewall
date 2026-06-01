import type { Plugin } from "@opencode-ai/plugin"
import { createPhiRunner } from "./phi.ts"
import { createPhiHooks } from "./hooks.ts"
import { resolvePhiSearchStart } from "./workspace.ts"

export const server: Plugin = async (input) =>
  createPhiHooks(createPhiRunner({ searchStart: resolvePhiSearchStart(input) }), {
    client: input.client,
  })
