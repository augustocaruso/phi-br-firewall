import type { Plugin } from "@opencode-ai/plugin"
import { createPhiRunner } from "./phi.js"
import { createPhiHooks } from "./hooks.js"

export const server: Plugin = async (input) =>
  createPhiHooks(createPhiRunner({ searchStart: input.worktree ?? input.directory }))
