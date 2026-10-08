import assert from "node:assert/strict";
import test from "node:test";
import { resolveApiUrl } from "../src/lib/api-url.ts";

test("production requires explicit backend URL while development keeps localhost", () => {
  assert.throws(() => resolveApiUrl(undefined, true), /obrigatória/);
  assert.throws(() => resolveApiUrl("  ", true), /obrigatória/);
  assert.equal(resolveApiUrl(undefined, false), "http://localhost:8000");
  assert.equal(resolveApiUrl("https://api.example.com/", true), "https://api.example.com");
});

test("public backend URL cannot contain secrets or unsupported protocols", () => {
  for (const value of ["file:///tmp/api", "https://user:secret@example.com", "https://example.com?token=x"]) {
    assert.throws(() => resolveApiUrl(value, true), /HTTP\(S\)/);
  }
});
