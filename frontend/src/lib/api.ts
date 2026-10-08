export type Subject = { id: number; name: string };

export type StudentState = {
  concept_id: number;
  concept: string;
  status: string;
  mastery: number | null;
  evidence_count: number;
  evidence_confidence: number;
  next_review_at: string | null;
};

export type Exercise = {
  id: number;
  type: "MULTIPLE_CHOICE" | "TRUE_FALSE" | "SHORT_EXACT" | "NUMERIC" | "STRUCTURED";
  prompt: string;
  options: string[] | null;
};

export type SessionActivity = {
  id: number;
  concept_id: number | null;
  activity_type: string;
  strategy: string | null;
  status: string;
  estimated_minutes: number;
  actual_minutes: number | null;
  executed: boolean;
  is_conditional: boolean;
  adaptation_reason: string | null;
  instructions?: string;
  exercise?: Exercise | null;
};

export type Session = {
  id: number;
  student_id: number;
  status: "PLANNED" | "IN_PROGRESS" | "COMPLETED" | "ABANDONED";
  available_minutes: number;
  remaining_minutes: number;
  used_minutes: number;
  actual_minutes: number | null;
  adaptation_reason: string | null;
  current_activity: SessionActivity | null;
  activities: SessionActivity[];
  decisions: { decision: string; reason: string; remaining_minutes: number }[];
};

export type AnswerRequest = {
  activity_id: number;
  answer: unknown;
  response_time: number;
  hints_used: number;
};

export type AnswerResult = {
  session: Session;
  feedback: { correct: boolean; message: string };
  decision: { action: string; reason: string; remaining_minutes: number };
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | null;

  constructor(status: number, message: string, detail: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const baseUrl = (process.env.NEXT_PUBLIC_ATLAS_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export function buildStartPayload(availableMinutes: number) {
  if (![20, 40, 60].includes(availableMinutes)) {
    throw new Error("Tempo de sessão inválido");
  }
  return { student_id: 1, available_minutes: availableMinutes };
}

export function friendlyApiError(error: unknown, context = "generic"): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Sessão ou recurso não encontrado. Volte ao início e tente novamente.";
    if (error.status === 409) return "Esta atividade já mudou. Atualize a sessão para continuar.";
    if (error.status === 422 && context === "start") {
      if (error.detail && /atividade|exercício|conteúdo|plano/i.test(error.detail)) {
        return "Não há conteúdo ou exercícios suficientes para criar esta sessão.";
      }
      return "Não foi possível criar a sessão com estas opções. Tente outro tempo.";
    }
    if (error.status === 422) return "Confira a resposta e tente novamente.";
    if (error.status >= 500 || error.status === 0) return "O backend ATLAS está indisponível. Tente novamente em instantes.";
  }
  return "Falha de rede. Confira sua conexão e tente novamente.";
}

async function requestJson<T>(path: string, init: RequestInit = {}, fetcher: typeof fetch = fetch): Promise<T> {
  let response: Response;
  try {
    response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Falha de rede");
  }
  if (!response.ok) {
    let detail: string | null = null;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch { /* Some server errors have no JSON body. */ }
    throw new ApiError(response.status, `Falha HTTP ${response.status}`, detail);
  }
  return (await response.json()) as T;
}

export const atlasApi = {
  getStudentState: () => requestJson<StudentState[]>("/student/state?student_id=1"),
  getSubjects: () => requestJson<Subject[]>("/subjects"),
  startSession: (minutes: number) => requestJson<Session>("/sessions/start", {
    method: "POST", body: JSON.stringify(buildStartPayload(minutes)),
  }),
  getSession: (id: number) => requestJson<Session>(`/sessions/${id}`),
  answer: (id: number, data: AnswerRequest) => requestJson<AnswerResult>(`/sessions/${id}/answer`, {
    method: "POST", body: JSON.stringify(data),
  }),
  advance: (id: number, activityId: number) => requestJson<Session>(`/sessions/${id}/advance`, {
    method: "POST", body: JSON.stringify({ activity_id: activityId }),
  }),
  finish: (id: number) => requestJson<Session>(`/sessions/${id}/finish`, {
    method: "POST", body: JSON.stringify({}),
  }),
};

// Exposed for focused request and error tests without a browser or server.
export { requestJson };
