import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, buildStartPayload, friendlyApiError, requestJson } from "../src/lib/api.ts";
import { masteryLabel, stateCategory, summarizeStates } from "../src/lib/state.ts";

const undiagnosed = {
  concept_id: 1, concept: "Conceito de teste", status: "DEVELOPING",
  mastery: null, evidence_count: 0, evidence_confidence: 0, next_review_at: null,
};

test("mastery null is always NOT_DIAGNOSED and never displays internal prior", () => {
  assert.equal(stateCategory(undiagnosed), "NOT_DIAGNOSED");
  assert.equal(masteryLabel(undiagnosed), "Ainda não diagnosticado");
  assert.equal(masteryLabel(undiagnosed).includes("35%"), false);
  assert.deepEqual(summarizeStates([undiagnosed]), {
    NOT_DIAGNOSED: 1, LEARNING: 0, REVIEW: 0, MASTERED: 0,
  });
});

test("session start payload uses temporary student 1 and chosen minutes", () => {
  assert.deepEqual(buildStartPayload(40), { student_id: 1, available_minutes: 40 });
  assert.throws(() => buildStartPayload(35));
});

test("API 409 is typed and explained in Portuguese", async () => {
  await assert.rejects(
    requestJson("/sessions/1/answer", { method: "POST" }, async () => new Response(
      JSON.stringify({ detail: "conflict" }), { status: 409, headers: { "Content-Type": "application/json" } },
    )),
    (error) => error instanceof ApiError && error.status === 409 &&
      friendlyApiError(error).includes("atividade já mudou"),
  );
});

test("missing content and network failures have friendly messages", async () => {
  assert.match(friendlyApiError(new ApiError(422, "invalid", "Plano sem atividades disponíveis"), "start"),
    /Não há conteúdo ou exercícios suficientes/);
  await assert.rejects(requestJson("/sessions/start", { method: "POST" }, async () => new Response(
    JSON.stringify({ detail: "Plano sem atividades disponíveis" }), { status: 422 },
  )), (error) => error instanceof ApiError && error.detail === "Plano sem atividades disponíveis");
  await assert.rejects(requestJson("/subjects", {}, async () => { throw new TypeError("network"); }),
    (error) => error instanceof ApiError && error.status === 0 &&
      friendlyApiError(error).includes("indisponível"));
});
