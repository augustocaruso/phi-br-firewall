import { parse, resolve } from "node:path"

export type OpenCodeWorkspaceInput = {
  directory: string
  worktree?: string
}

export function resolvePhiSearchStart(input: OpenCodeWorkspaceInput) {
  const worktree = input.worktree ? resolve(input.worktree) : undefined
  if (worktree && worktree !== parse(worktree).root) return worktree
  return input.directory
}
