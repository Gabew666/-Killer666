"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError, atlasApi, friendlyApiError, type Exercise, type Session, type StudentState } from "@/lib/api";
import { clearActiveSessionId, readActiveSessionId } from "@/lib/session-storage";

const activityLabels: Record<string, string> = {
  RECALL: "Recordação", EXPLANATION: "Explicação", EXAMPLE: "Exemplo",
  GUIDED_EXERCISE: "Prática guiada", INDEPENDENT_EXERCISE: "Exercício",
  QUIZ: "Quiz", CODE_EXERCISE: "Exercício de código", ERROR_REVIEW: "Revisão do erro",
  SUMMARY: "Síntese", MOCK_EXAM: "Simulado", BREAK: "Pausa",
};

function parseAnswer(exercise: Exercise, selected: number | boolean | null, input: string): unknown {
  if (exercise.type === "MULTIPLE_CHOICE" || exercise.type === "TRUE_FALSE") {
    if (selected === null) throw new Error("Escolha uma resposta antes de continuar.");
    return selected;
  }
  if (!input.trim()) throw new Error("Digite sua resposta antes de continuar.");
  if (exercise.type === "NUMERIC") {
    const value = Number(input.trim().replace(",", "."));
    if (!Number.isFinite(value)) throw new Error("Digite um número válido.");
    return value;
  }
  if (exercise.type === "STRUCTURED") {
    try {
      const value: unknown = JSON.parse(input);
      if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error();
      return value;
    } catch {
      throw new Error("Digite um objeto JSON válido com os campos pedidos no enunciado.");
    }
  }
  return input.trim();
}

export default function SessionPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [session, setSession] = useState<Session | null>(null);
  const [states, setStates] = useState<StudentState[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState<{ correct: boolean; reason: string } | null>(null);
  const [selected, setSelected] = useState<number | boolean | null>(null);
  const [input, setInput] = useState("");
  const [usedHint, setUsedHint] = useState(false);
  const startedAt = useRef(Date.now());
  const finishing = useRef(false);

  async function refresh() {
    const updated = await atlasApi.getSession(id);
    setSession(updated);
  }

  async function completeSession(sessionId: number) {
    if (finishing.current) return;
    finishing.current = true;
    setError("");
    try {
      const closed = await atlasApi.finish(sessionId);
      setSession(closed);
      if (readActiveSessionId() === closed.id) clearActiveSessionId();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        try { await refresh(); } catch { setError(friendlyApiError(cause)); }
      } else setError(friendlyApiError(cause));
    } finally {
      finishing.current = false;
    }
  }

  useEffect(() => {
    let live = true;
    if (!Number.isSafeInteger(id) || id < 1) {
      setError("Sessão inexistente. Volte ao início e tente novamente.");
      setLoading(false);
      return;
    }
    Promise.allSettled([atlasApi.getSession(id), atlasApi.getStudentState()]).then(([sessionResult, stateResult]) => {
      if (!live) return;
      if (sessionResult.status === "fulfilled") setSession(sessionResult.value);
      else setError(friendlyApiError(sessionResult.reason));
      if (stateResult.status === "fulfilled") setStates(stateResult.value);
      setLoading(false);
    });
    return () => { live = false; };
  }, [id]);

  const current = session?.current_activity;
  useEffect(() => {
    setSelected(null);
    setInput("");
    setUsedHint(false);
    startedAt.current = Date.now();
  }, [current?.id]);

  useEffect(() => {
    if (!session || session.status !== "IN_PROGRESS" || session.current_activity || finishing.current) return;
    void completeSession(session.id);
  }, [session]);

  useEffect(() => {
    if (session?.status === "COMPLETED" || session?.status === "ABANDONED") {
      if (readActiveSessionId() === session.id) clearActiveSessionId();
    }
  }, [session]);

  async function submitAnswer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !current?.exercise || busy) return;
    let answer: unknown;
    try {
      answer = parseAnswer(current.exercise, selected, input);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Confira sua resposta.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await atlasApi.answer(session.id, {
        activity_id: current.id,
        answer,
        response_time: Math.min(86400, Math.max(0, (Date.now() - startedAt.current) / 1000)),
        hints_used: usedHint ? 1 : 0,
      });
      setSession(result.session);
      setFeedback({ correct: result.feedback.correct, reason: result.decision.reason });
    } catch (cause) {
      setError(friendlyApiError(cause));
      if (cause instanceof ApiError && cause.status === 409) {
        try { await refresh(); } catch { /* Keep the conflict message visible. */ }
      }
    } finally {
      setBusy(false);
    }
  }

  async function advance() {
    if (!session || !current || busy) return;
    setBusy(true);
    setError("");
    try {
      setSession(await atlasApi.advance(session.id, current.id));
      setFeedback(null);
    } catch (cause) {
      setError(friendlyApiError(cause));
      if (cause instanceof ApiError && cause.status === 409) {
        try { await refresh(); } catch { /* Keep the conflict message visible. */ }
      }
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="card" role="status">Carregando sessão…</div>;
  if (!session) return <div className="page-stack"><div className="notice error" role="alert">{error || "Sessão indisponível."}</div><Link className="button secondary" href="/">Voltar ao início</Link></div>;

  const concept = states.find((item) => item.concept_id === current?.concept_id)?.concept;
  const completed = session.activities.filter((item) => item.status === "COMPLETED").length;
  const ended = session.status === "COMPLETED" || session.status === "ABANDONED" || !current;

  return (
    <div className="page-stack session-page">
      <div className="page-title">
        <Link href="/" className="back-link">← Início</Link>
        <p className="eyebrow">Sessão #{session.id}</p>
        <h1>{ended ? (session.status === "ABANDONED" ? "Sessão encerrada" : "Sessão concluída") : "Hora de estudar"}</h1>
      </div>

      <div className="time-strip" aria-label="Tempo da sessão">
        <div><span>Disponível</span><strong>{session.available_minutes} min</strong></div>
        <div><span>Restante</span><strong>{session.remaining_minutes} min</strong></div>
      </div>

      {error && <div className="notice error" role="alert">{error}</div>}
      {feedback && <div className={`notice ${feedback.correct ? "success" : "warning"}`} role="status">
        <strong>{feedback.correct ? "Correto" : "Incorreto"}</strong>
        {feedback.reason && <p>{feedback.reason}</p>}
      </div>}

      {ended ? (
        <section className="card completion-card">
          <span className="completion-mark" aria-hidden>✓</span>
          <h2>{session.status === "IN_PROGRESS" ? "Finalizando sua sessão…" : "Bom trabalho hoje"}</h2>
          <div className="stat-grid completion-stats">
            <div className="stat"><strong>{session.used_minutes}</strong><span>Min usados</span></div>
            <div className="stat"><strong>{session.remaining_minutes}</strong><span>Min restantes</span></div>
            <div className="stat"><strong>{completed}</strong><span>Atividades concluídas</span></div>
            <div className="stat"><strong>{session.decisions.length}</strong><span>Decisões adaptativas</span></div>
          </div>
          {session.decisions.length > 0 && (
            <div className="decision-list">
              <h3>Adaptações realizadas</h3>
              <ul>{session.decisions.map((item, index) => <li key={index}>{item.reason}</li>)}</ul>
            </div>
          )}
          {session.status === "IN_PROGRESS" && error && (
            <button className="button secondary full-width" type="button" onClick={() => void completeSession(session.id)}>
              Tentar concluir sessão
            </button>
          )}
          <Link href="/" className="button primary">Voltar ao início</Link>
        </section>
      ) : (
        <section className="card activity-card" key={current.id}>
          <div className="activity-meta"><span className="badge">{activityLabels[current.activity_type] || current.activity_type}</span><span>{current.estimated_minutes} min previstos</span></div>
          <p className="eyebrow">Conceito atual</p>
          <h2>{concept || (current.concept_id ? `Conceito #${current.concept_id}` : "Atividade da sessão")}</h2>
          <p className="activity-instructions">{current.instructions}</p>
          {current.adaptation_reason && <p className="adaptation-note">Por que esta atividade? {current.adaptation_reason}</p>}

          {current.exercise ? (
            <form onSubmit={(event) => void submitAnswer(event)} className="answer-form">
              <fieldset disabled={busy}>
                <legend>{current.exercise.prompt}</legend>
                {current.exercise.type === "MULTIPLE_CHOICE" && current.exercise.options?.map((option, index) => (
                  <label className={`option ${selected === index ? "selected" : ""}`} key={index}>
                    <input type="radio" name="answer" checked={selected === index} onChange={() => setSelected(index)} />
                    <span>{option}</span>
                  </label>
                ))}
                {current.exercise.type === "TRUE_FALSE" && ([{ value: true, label: "Verdadeiro" }, { value: false, label: "Falso" }]).map((option) => (
                  <label className={`option ${selected === option.value ? "selected" : ""}`} key={String(option.value)}>
                    <input type="radio" name="answer" checked={selected === option.value} onChange={() => setSelected(option.value)} />
                    <span>{option.label}</span>
                  </label>
                ))}
                {(current.exercise.type === "SHORT_EXACT" || current.exercise.type === "NUMERIC") && (
                  <input className="answer-input" value={input} onChange={(event) => setInput(event.target.value)}
                    inputMode={current.exercise.type === "NUMERIC" ? "decimal" : "text"}
                    placeholder={current.exercise.type === "NUMERIC" ? "Digite um número" : "Digite sua resposta"}
                    aria-label="Sua resposta" />
                )}
                {current.exercise.type === "STRUCTURED" && (
                  <>
                    <textarea className="answer-input" rows={5} value={input} onChange={(event) => setInput(event.target.value)}
                      placeholder={'{"campo": "valor"}'} aria-label="Resposta estruturada em JSON" />
                    <p className="field-hint">Use JSON com os campos pedidos no enunciado. Números e verdadeiro/falso não usam aspas.</p>
                  </>
                )}
                <label className="hint-check"><input type="checkbox" checked={usedHint} onChange={(event) => setUsedHint(event.target.checked)} /> Usei uma dica nesta resposta</label>
              </fieldset>
              <button className="button primary full-width" type="submit" disabled={busy}>{busy ? "Enviando…" : "Responder"}</button>
            </form>
          ) : (
            <button className="button primary full-width" type="button" onClick={() => void advance()} disabled={busy}>
              {busy ? "Continuando…" : "Continuar"}
            </button>
          )}
        </section>
      )}
    </div>
  );
}
