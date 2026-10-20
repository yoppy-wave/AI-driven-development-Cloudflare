import { scanSource } from "../.github/scripts/check_security.cjs";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

describe("JavaScript/TypeScript sensitive logging", () => {
  test.each([
    'console.log("request completed", requestId)',
    'logger.info("token refreshed")',
    'console.log({token: "[REDACTED]"})',
    'console.info(tokenCount)',
    'save(password)',
    'const code = "console.log(token)"',
  ])("allows safe code: %s", source => expect(scanSource(source, "safe.ts")).toEqual([]));

  test.each([
    'console.log(password)', 'logger.info("value", accessToken)',
    'console.error(user.password)', 'console.log(headers["Authorization"])',
    'logger.debug({api_key: value})', 'console.log(`token=${value}`)',
    'console.log(config.get("API_KEY"))', 'console.log({...credentials})',
    'const audit = createLogger(); audit.info(token)',
    'import {info as report} from "logger"; report(password)',
    'console.log("Bearer abc123")',
  ])("rejects sensitive code: %s", source => {
    const findings = scanSource(source, "unsafe.ts");
    expect(findings[0]).toContain("unsafe.ts:1: sensitive value");
    expect(findings[0]).not.toContain("abc123");
  });

  test("reports line numbers and parse errors", () => {
    expect(scanSource("\nconsole.log(token)", "unsafe.ts")[0]).toContain(":2:");
    expect(scanSource("console.log(", "bad.ts")[0]).toContain("parse error");
  });

  test("CLI returns failure without exposing the logged value", () => {
    const directory = mkdtempSync(join(tmpdir(), "security-fixture-"));
    try {
      const file = join(directory, "unsafe.js");
      writeFileSync(file, 'console.log("Bearer abc123")');
      const result = spawnSync(process.execPath, [resolve(".github/scripts/check_security.cjs")], {
        input: JSON.stringify([file]), encoding: "utf8",
      });
      expect(result.status).toBe(1);
      expect(result.stderr).toContain("sensitive value");
      expect(result.stderr).not.toContain("abc123");
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
