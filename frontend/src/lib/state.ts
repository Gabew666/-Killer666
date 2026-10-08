import type { StudentState } from "./api";

export type StateCategory = "NOT_DIAGNOSED" | "LEARNING" | "REVIEW" | "MASTERED";

export function stateCategory(state: StudentState): StateCategory {
  if (state.mastery === null) return "NOT_DIAGNOSED";
  if (state.status === "MASTERED") return "MASTERED";
  if (state.status === "REVIEW_DUE") return "REVIEW";
  return "LEARNING";
}

export function summarizeStates(states: StudentState[]) {
  const summary: Record<StateCategory, number> = {
    NOT_DIAGNOSED: 0, LEARNING: 0, REVIEW: 0, MASTERED: 0,
  };
  for (const state of states) summary[stateCategory(state)] += 1;
  return summary;
}

export function masteryLabel(state: StudentState): string {
  return state.mastery === null ? "Ainda não diagnosticado" : `${Math.round(state.mastery * 100)}%`;
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
