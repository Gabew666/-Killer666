"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { atlasApi, friendlyApiError, type Session, type StudentState, type Subject } from "@/lib/api";
import { readActiveSessionId, clearActiveSessionId, saveActiveSessionId } from "@/lib/session-storage";
import { summarizeStates } from "@/lib/state";

const durations = [20, 40, 60] as const;

export default function Dashboard() {
  const router = useRouter();
  const [states, setStates] = useState<StudentState[]>([]);
  const [stateLoaded, setStateLoaded] = useState(false);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [active, setActive] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    async function load() {
      const [stateResult, subjectResult] = await Promise.allSettled([
        atlasApi.getStudentState(), atlasApi.getSubjects(),
      ]);
      if (!live) return;
      if (stateResult.status === "fulfilled") {
        setStates(stateResult.value);
        setStateLoaded(true);
      }
      if (subjectResult.status === "fulfilled") setSubjects(subjectResult.value);
      if (stateResult.status === "rejected" || subjectResult.status === "rejected") {
        setError(friendlyApiError(stateResult.status === "rejected" ? stateResult.reason : subjectResult.status === "rejected" ? subjectResult.reason : null));
      }
      const id = readActiveSessionId();
      if (id) {
        try {
          const session = await atlasApi.getSession(id);
          if (live && session.status === "IN_PROGRESS") setActive(session);
          else if (live) clearActiveSessionId();
        } catch (cause) {
          if (live) {
            if (cause instanceof Error && "status" in cause && cause.status === 404) clearActiveSessionId();
            else setError(friendlyApiError(cause));
          }
        }
      }
      if (live) setLoading(false);
    }
    void load();
    return () => { live = false; };
  }, []);

  async function start(minutes: number) {
    if (starting !== null) return;
    setStarting(minutes);
    setError("");
    try {
      const session = await atlasApi.startSession(minutes);
      saveActiveSessionId(session.id);
      router.push(`/session/${session.id}`);
    } catch (cause) {
      setError(friendlyApiError(cause, "start"));
      setStarting(null);
    }
  }

  const summary = summarizeStates(states);

  return (
    <div className="page-stack">
      <section className="hero">
        <p className="eyebrow">Seu estudo, no seu ritmo</p>
        <h1>ATLAS</h1>
        <p className="hero-subtitle">Aprendizado Adaptativo</p>
        <p className="hero-copy">Uma sessão focada no que faz sentido para você agora.</p>
      </section>

      {error && <div className="notice error" role="alert">{error}</div>}

      {active && (
        <section className="card accent-card">
          <div>
            <p className="eyebrow">Em andamento</p>
            <h2>Continue sua sessão</h2>
            <p>{active.remaining_minutes} min restantes de {active.available_minutes} min</p>
          </div>
          <Link className="button primary" href={`/session/${active.id}`}>Continuar sessão <span aria-hidden>→</span></Link>
        </section>
      )}

      <section className="card" aria-labelledby="time-heading">
        <div className="section-heading">
          <span className="section-icon" aria-hidden>◷</span>
          <div>
            <p className="eyebrow">Começar agora</p>
            <h2 id="time-heading">Quanto tempo você tem hoje?</h2>
          </div>
        </div>
        <div className="duration-grid">
          {durations.map((minutes) => (
            <button className="duration-button" type="button" key={minutes}
              disabled={starting !== null} onClick={() => void start(minutes)}>
              <strong>{minutes}</strong><span>minutos</span>
              <span className="duration-arrow" aria-hidden>↗</span>
            </button>
          ))}
        </div>
        {starting !== null && <p className="muted" role="status">Preparando sessão de {starting} minutos…</p>}
      </section>

      <section className="card" aria-labelledby="summary-heading">
        <div className="section-heading between">
          <div>
            <p className="eyebrow">Visão geral</p>
            <h2 id="summary-heading">Seu aprendizado</h2>
          </div>
          <Link href="/progress" className="text-link">Ver progresso →</Link>
        </div>
        {loading ? <p className="muted" role="status">Carregando estado…</p> : !stateLoaded ? (
          <p className="muted">O resumo está indisponível no momento.</p>
        ) : (
          <>
            <p className="muted subject-line">{subjects.length ? subjects.map((s) => s.name).join(" · ") : "Nenhuma disciplina disponível"}</p>
            <div className="stat-grid">
              <div className="stat"><strong>{summary.NOT_DIAGNOSED}</strong><span>Não diagnosticados</span></div>
              <div className="stat"><strong>{summary.LEARNING}</strong><span>Em aprendizagem</span></div>
              <div className="stat"><strong>{summary.REVIEW}</strong><span>Em revisão</span></div>
              <div className="stat"><strong>{summary.MASTERED}</strong><span>Dominados</span></div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
