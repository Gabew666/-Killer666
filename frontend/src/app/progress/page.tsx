"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { atlasApi, friendlyApiError, type StudentState } from "@/lib/api";
import { masteryLabel, percent, stateCategory } from "@/lib/state";

const labels = {
  NOT_DIAGNOSED: "Não diagnosticado",
  LEARNING: "Em aprendizagem",
  REVIEW: "Em revisão",
  MASTERED: "Dominado",
};

export default function ProgressPage() {
  const [states, setStates] = useState<StudentState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    atlasApi.getStudentState().then((items) => {
      if (live) setStates(items);
    }).catch((cause) => {
      if (live) setError(friendlyApiError(cause));
    }).finally(() => {
      if (live) setLoading(false);
    });
    return () => { live = false; };
  }, []);

  return (
    <div className="page-stack">
      <div className="page-title">
        <Link href="/" className="back-link">← Início</Link>
        <p className="eyebrow">Seu caminho</p>
        <h1>Progresso</h1>
        <p className="muted">Estimativas do ATLAS com a quantidade e confiança das evidências.</p>
      </div>
      {loading && <div className="card" role="status">Carregando conceitos…</div>}
      {error && <div className="notice error" role="alert">{error}</div>}
      {!loading && !error && states.length === 0 && <div className="card">Ainda não há conceitos cadastrados.</div>}
      {!loading && !error && states.length > 0 && (
        <div className="concept-list">
          {states.map((state) => {
            const category = stateCategory(state);
            return (
              <article className="card concept-card" key={state.concept_id}>
                <div className="concept-topline">
                  <h2>{state.concept}</h2>
                  <span className={`badge badge-${category.toLowerCase()}`}>{labels[category]}</span>
                </div>
                <dl className="detail-grid">
                  <div><dt>Domínio estimado</dt><dd>{masteryLabel(state)}</dd></div>
                  <div><dt>Evidências independentes</dt><dd>{state.evidence_count}</dd></div>
                  <div><dt>Confiança da estimativa</dt><dd>{percent(state.evidence_confidence)}</dd></div>
                  {state.next_review_at && <div><dt>Próxima revisão</dt><dd>{new Date(state.next_review_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" })}</dd></div>}
                </dl>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
