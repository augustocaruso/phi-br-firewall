import { describe, expect, test } from "vitest"
import { resolvePhiSearchStart } from "../src/workspace.js"

describe("OpenCode workspace resolution", () => {
  test("uses the real worktree for project sessions", () => {
    expect(
      resolvePhiSearchStart({
        directory: "/Users/augustocaruso/Documents/project",
        worktree: "/Users/augustocaruso/Documents/project",
      }),
    ).toBe("/Users/augustocaruso/Documents/project")
  })

  test("falls back to the session directory when OpenCode reports root as worktree", () => {
    expect(
      resolvePhiSearchStart({
        directory: "/Users/augustocaruso",
        worktree: "/",
      }),
    ).toBe("/Users/augustocaruso")
  })
})
