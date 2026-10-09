"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiError, friendlyApiError, requestJson, atlasApi, type AnswerResult, type Session, type StudentState } from "@/lib/api";
import { clearActiveSessionId, readActiveSessionId } from "@/lib/session-storage";
import { guideFor } from "@/lib/study-guides";
import ExerciseCard from "./exercise-card";
import LessonPanel from "./lesson-panel";

const activityLabels: Record<string, string> = {
  RECALL: "Diagnóstico / recordação", EXPLANATION: "Aula guiada", EXAMPLE: "Exemplo resolvido",
  GUIDED_EXERCISE: "Prática guiada", INDEPENDENT_EXERCISE: "Prática independente",
  QUIZ: "Verificação", CODE_EXERCISE: "Código", ERROR_REVIEW: "Revisão do erro",
  SUMMARY: "Síntese", MOCK_EXAM: "Simulado", BREAK: "Pausa",
};

export default function SessionStudyClient() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [session, setSession] = useState<Session | null>(null);
  const [states, setStates] = useState<StudentState[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState<{correct:boolean; reason:string; concept:string|null} | null>(null);
  const startedAt = useRef(Date.now());
  const finishing = useRef(false);

  async function refresh() {
    setSession(await atlasApi.getSession(id));
  }

  async function finish(sessionId: number) {
    if (finishing.current) return;
    finishing.current = true;
    try {
      const closed = await atlasApi.finish(sessionId);
      setSession(closed);
      clearActiveSessionId();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) await refresh();
      else setError(friendlyApiError(cause));
    } finally {
      finishing.current = false;
    }
  }

  useEffect(() => {
    let live = true;
    Promise.allSettled([atlasApi.getSession(id), atlasApi.getStudentState()]).then(([s, st]) => {
      if (!live) return;
      if (s.status === "fulfilled") setSession(s.value); else setError(friendlyApiError(s.reason));
      if (st.status === "fulfilled") setStates(st.value);
      setLoading(false);
    });
    return () => { live = false; };
  }, [id]);

  const current = session?.current_activity;
  useEffect(() => {
    startedAt.current = Date.now();
  }, [current?.id]);

  useEffect(() => {
    if (!session || session.status !== "IN_PROGRESS" || session.current_activity || finishing.current) return;
    void finish(session.id);
  }, [session]);

  const concept = states.find((item) => item.concept_id === current?.concept_id)?.concept ?? null;
  const guide = guideFor(concept);
  const completed = session?.activities.filter((item) => item.status === "COMPLETED").length ?? 0;
  const skipped = session?.activities.filter((item) => item.status === "SKIPPED").length ?? 0;
  const total = Math.max(1, (session?.activities.length ?? 0) - skipped);
  const progress = Math.min(100, Math.round(completed / total * 100));

  function actualMinutes() {
    const elapsed = Math.max(1, Math.ceil((Date.now() - startedAt.current) / 60000));
    return Math.min(current?.estimated_minutes ?? elapsed, elapsed);
  }

  async function submit(answer: unknown, hintsUsed: number, confidence: number | null) {
    if (!session || !current) return;
    setBusy(true);
    setError("");
    const answeredConcept = concept;
    try {
      const result = await requestJson<AnswerResult>(`/sessions/${session.id}/answer`, {
        method: "POST",
        body: JSON.stringify({
          activity_id: current.id,
          answer,
          hints_used: hintsUsed,
          response_time: Math.min(86400, Math.max(0, (Date.now() - startedAt.current) / 1000)),
          self_confidence: confidence,
          actual_minutes: actualMinutes(),
        }),
      });
      setSession(result.session);
      setFeedback({correct: result.feedback.correct, reason: result.decision.reason, concept: answeredConcept});
    } catch (cause) {
      setError(friendlyApiError(cause));
      if (cause instanceof ApiError && cause.status === 409) await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function advance() {
    if (!session || !current) return;
    setBusy(true);
    setError("");
    try {
      const updated = await requestJson<Session>(`/sessions/${session.id}/advance`, {
        method: "POST",
        body: JSON.stringify({activity_id: current.id, actual_minutes: actualMinutes()}),
      });
      setSession(updated);
      setFeedback(null);
    } catch (cause) {
      setError(friendlyApiError(cause));
      if (cause instanceof ApiError && cause.status === 409) await refresh();
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="card">Montando sua sessão…</div>;
  if (!session) return <div className="page-stack"><div className="notice error">{error || "Sessão indisponível."}</div><Link className="button secondary" href="/study">Voltar</Link></div>;

  const ended = session.status === "COMPLETED" || session.status === "ABANDONED" || !current;

  return <div className="page-stack session-page">
    <div className="page-title">
      <Link href="/study" className="back-link">← Plano de estudo</Link>
      <p className="eyebrow">Sessão adaptativa #{session.id}</p>
      <h1>{ended ? "Sessão concluída" : concept ?? "Hora de estudar"}</h1>
    </div>

    {!ended && <section className="card" style={{padding:"1rem 1.2rem"}}>
      <div style={{display:"flex",justifyContent:"space-between",gap:"1rem",marginBottom:".55rem"}}>
        <span className="muted">Progresso da sessão</span><strong>{progress}%</strong>
      </div>
      <div style={{height:"8px",background:"var(--surface-raised)",borderRadius:"99px",overflow:"hidden"}}>
        <div style={{height:"100%",width:`${progress}%`,background:"var(--accent)",transition:"width .2s"}} />
      </div>
      <div style={{display:"flex",justifyContent:"space-between",marginTop:".65rem",fontSize:".82rem"}} className="muted">
        <span>{completed} etapas concluídas</span><span>{session.remaining_minutes} min disponíveis</span>
      </div>
    </section>}

    {error && <div className="notice error">{error}</div>}

    {feedback && !ended && <div className={`notice ${feedback.correct ? "success" : "warning"}`}>
      <strong>{feedback.correct ? "Boa — evidência registrada" : "Encontramos uma lacuna"}</strong>
      <p>{feedback.correct ? "O ATLAS vai confirmar ou avançar conforme a confiança dessa evidência." : "Em vez de apenas repetir perguntas, a próxima etapa vai revisar o conceito antes de testar novamente."}</p>
      <p style={{fontSize:".85rem"}}>{feedback.reason}</p>
    </div>}

    {ended ? <section className="card completion-card">
      <span className="completion-mark">✓</span>
      <h2>Estudo registrado</h2>
      <p className="muted">O ATLAS salvou suas respostas, tempo real aproximado, uso de ajuda e confiança declarada.</p>
      <div className="stat-grid completion-stats">
        <div className="stat"><strong>{session.used_minutes}</strong><span>Min contabilizados</span></div>
        <div className="stat"><strong>{completed}</strong><span>Etapas feitas</span></div>
        <div className="stat"><strong>{session.decisions.length}</strong><span>Adaptações</span></div>
        <div className="stat"><strong>{session.remaining_minutes}</strong><span>Min restantes</span></div>
      </div>
      <Link href="/study" className="button primary">Ver próximo foco</Link>
    </section> : <section className="card activity-card" key={current.id}>
      <div className="activity-meta">
        <span className="badge">{activityLabels[current.activity_type] ?? current.activity_type}</span>
        <span>{current.estimated_minutes} min previstos</span>
      </div>
      <p className="eyebrow">Conceito atual</p>
      <h2>{concept ?? "Atividade da sessão"}</h2>
      {current.adaptation_reason && <p className="adaptation-note">Por que isso apareceu agora? {current.adaptation_reason}</p>}

      {current.exercise ? <ExerciseCard key={current.id} exercise={current.exercise} strategy={current.strategy} guide={guide} busy={busy} onSubmit={submit} /> : <>
        {guide && ["EXPLANATION","EXAMPLE","ERROR_REVIEW"].includes(current.activity_type)
          ? <LessonPanel guide={guide} mode={current.activity_type} />
          : <p className="activity-instructions">{current.instructions}</p>}
        {guide && current.activity_type === "SUMMARY" && <div className="notice success"><strong>Explique sem olhar</strong><p>{guide.quickCheck}</p></div>}
        <button className="button primary full-width" style={{marginTop:"1.2rem"}} onClick={() => void advance()} disabled={busy}>
          {busy ? "Salvando…" : current.activity_type === "EXPLANATION" ? "Entendi, praticar →" : "Concluí esta etapa →"}
        </button>
      </>}
    </section>}
  </div>;
}
