"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { atlasApi, friendlyApiError, type Session, type StudentState } from "@/lib/api";
import { clearActiveSessionId, readActiveSessionId, saveActiveSessionId } from "@/lib/session-storage";
import { PRIORITY_CONCEPTS, STUDY_GUIDES } from "@/lib/study-guides";
import { stateCategory, summarizeStates } from "@/lib/state";

const durations = [20, 40, 60] as const;

function score(state: StudentState) {
  const category = stateCategory(state);
  if (category === "NOT_DIAGNOSED") return 0;
  if (category === "LEARNING") return 1 + (state.mastery ?? 0);
  if (category === "REVIEW") return 3 + (state.mastery ?? 0);
  return 10;
}

export default function StudyDashboard() {
  const router = useRouter();
  const [states, setStates] = useState<StudentState[]>([]);
  const [active, setActive] = useState<Session | null>(null);
  const [starting, setStarting] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    atlasApi.getStudentState().then((items) => live && setStates(items)).catch((e) => live && setError(friendlyApiError(e)));
    const id = readActiveSessionId();
    if (id) atlasApi.getSession(id).then((session) => {
      if (!live) return;
      if (session.status === "IN_PROGRESS") setActive(session);
      else clearActiveSessionId();
    }).catch(() => clearActiveSessionId());
    return () => { live = false; };
  }, []);

  const priority = useMemo(() => states
    .filter((s) => PRIORITY_CONCEPTS.includes(s.concept))
    .sort((a, b) => score(a) - score(b) || PRIORITY_CONCEPTS.indexOf(a.concept) - PRIORITY_CONCEPTS.indexOf(b.concept)), [states]);
  const focus = priority[0];
  const guide = focus ? STUDY_GUIDES[focus.concept] : null;
  const summary = summarizeStates(states);

  async function start(minutes: number) {
    setStarting(minutes);
    setError("");
    try {
      const session = await atlasApi.startSession(minutes);
      saveActiveSessionId(session.id);
      router.push(`/study/session/${session.id}`);
    } catch (e) {
      setError(friendlyApiError(e, "start"));
      setStarting(null);
    }
  }

  return <div className="page-stack">
    <section className="hero">
      <p className="eyebrow">Plano de recuperação</p>
      <h1>ATLAS</h1>
      <p className="hero-subtitle">Aprender, praticar e adaptar</p>
      <p className="hero-copy">Agora a sessão não é só um quiz: o ATLAS usa diagnóstico curto, aula guiada, exemplo e prática antes de avançar.</p>
    </section>

    {error && <div className="notice error">{error}</div>}

    {active && <section className="card accent-card">
      <div><p className="eyebrow">Em andamento</p><h2>Continue sua sessão</h2><p>{active.remaining_minutes} min disponíveis</p></div>
      <Link className="button primary" href={`/study/session/${active.id}`}>Continuar →</Link>
    </section>}

    <section className="card">
      <p className="eyebrow">Prioridade agora</p>
      <h2>{focus?.concept ?? "Construindo sua base"}</h2>
      <p className="hero-copy">{guide?.summary ?? "O ATLAS vai começar pelos conceitos com menos evidência."}</p>
      {guide && <p className="muted">{guide.source} · síntese autoral do ATLAS</p>}
    </section>

    <section className="card">
      <div className="section-heading"><span className="section-icon">◷</span><div><p className="eyebrow">Estudar agora</p><h2>Quanto tempo você tem?</h2></div></div>
      <p className="muted">Se houver erro, a sessão entra em explicação e prática; se houver acerto consistente, avança.</p>
      <div className="duration-grid">
        {durations.map((minutes) => <button key={minutes} className="duration-button" disabled={starting !== null} onClick={() => void start(minutes)}>
          <strong>{minutes}</strong><span>minutos</span><span className="duration-arrow">↗</span>
        </button>)}
      </div>
      {starting !== null && <p className="muted">Preparando sessão…</p>}
    </section>

    <section className="card">
      <div className="section-heading between"><div><p className="eyebrow">Seu aprendizado</p><h2>Mapa geral</h2></div><Link className="text-link" href="/progress">Ver 40 conceitos →</Link></div>
      <div className="stat-grid">
        <div className="stat"><strong>{summary.NOT_DIAGNOSED}</strong><span>Não diagnosticados</span></div>
        <div className="stat"><strong>{summary.LEARNING}</strong><span>Em aprendizagem</span></div>
        <div className="stat"><strong>{summary.REVIEW}</strong><span>Em revisão</span></div>
        <div className="stat"><strong>{summary.MASTERED}</strong><span>Dominados</span></div>
      </div>
    </section>

    <section className="card">
      <p className="eyebrow">Trilha prioritária</p>
      <h2>14 conceitos com guia de estudo</h2>
      <div style={{display:"grid",gap:".6rem"}}>
        {priority.map((s, i) => <div key={s.concept} style={{display:"flex",gap:".8rem",padding:".85rem",border:"1px solid var(--border)",borderRadius:"14px",background:"var(--surface-raised)"}}>
          <strong style={{color:"var(--accent)"}}>{String(i + 1).padStart(2, "0")}</strong>
          <div><strong>{s.concept}</strong><div className="muted" style={{fontSize:".82rem",marginTop:".25rem"}}>{stateCategory(s) === "NOT_DIAGNOSED" ? "Diagnóstico pendente" : `${Math.round((s.mastery ?? 0) * 100)}% estimado`}</div></div>
        </div>)}
      </div>
    </section>
  </div>;
}
