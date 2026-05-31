import type { Plugin } from "@opencode-ai/plugin"
import { createPhiRunner } from "./phi.js"
import { createPhiHooks } from "./hooks.js"
import { resolvePhiSearchStart } from "./workspace.js"

export const server: Plugin = async (input) =>
  createPhiHooks(createPhiRunner({ searchStart: resolvePhiSearchStart(input) }), {
    client: input.client,
  })
