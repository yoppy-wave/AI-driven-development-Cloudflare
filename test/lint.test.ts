import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

test.each([
  ["export const value: number = 1;", 0],
  ["const unused: number = 1;", 1],
])("ESLint CLI enforces the repository rules: %s", (source, expected) => {
  const result = spawnSync(process.execPath, [
    resolve("node_modules/eslint/bin/eslint.js"), "--stdin", "--stdin-filename", "lint-fixture.ts", "--max-warnings", "0",
  ], { input: source, encoding: "utf8" });
  expect(result.status).toBe(expected);
  if (expected) expect(result.stdout).toContain("no-unused-vars");
});
