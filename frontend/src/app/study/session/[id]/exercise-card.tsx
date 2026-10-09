"use client";

import { useState, type FormEvent } from "react";
import type { Exercise } from "@/lib/api";
import type { StudyGuide } from "@/lib/study-guides";

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
    const value: unknown = JSON.parse(input);
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("Use um objeto JSON válido.");
    return value;
  }
  return input.trim();
}

export default function ExerciseCard({
  exercise, strategy, guide, busy, onSubmit,
}: {
  exercise: Exercise;
  strategy: string | null;
  guide: StudyGuide | null;
  busy: boolean;
  onSubmit: (answer: unknown, hintsUsed: number, confidence: number | null) => Promise<void>;
}) {
  const [selected, setSelected] = useState<number | boolean | null>(null);
  const [input, setInput] = useState("");
  const [usedHelp, setUsedHelp] = useState(false);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      setError("");
      await onSubmit(parseAnswer(exercise, selected, input), usedHelp ? 1 : 0, confidence);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Confira sua resposta.");
    }
  }

  return <form onSubmit={(e) => void submit(e)} className="answer-form">
    {strategy === "diagnostic" && <div className="notice warning" style={{marginBottom:"1rem"}}>
      <strong>Diagnóstico rápido</strong>
      <p>Responda sem consultar se puder. Errar aqui serve para o ATLAS decidir o que ensinar em seguida.</p>
    </div>}
    {strategy !== "diagnostic" && guide && <div className="notice success" style={{marginBottom:"1rem"}}>
      <strong>Antes de responder</strong>
      <p>{guide.quickCheck}</p>
    </div>}

    <fieldset disabled={busy}>
      <legend>{exercise.prompt}</legend>
      {exercise.type === "MULTIPLE_CHOICE" && exercise.options?.map((option, index) => (
        <label className={`option ${selected === index ? "selected" : ""}`} key={index}>
          <input type="radio" name="answer" checked={selected === index} onChange={() => setSelected(index)} />
          <span>{option}</span>
        </label>
      ))}
      {exercise.type === "TRUE_FALSE" && [{value:true,label:"Verdadeiro"},{value:false,label:"Falso"}].map((option) => (
        <label className={`option ${selected === option.value ? "selected" : ""}`} key={String(option.value)}>
          <input type="radio" name="answer" checked={selected === option.value} onChange={() => setSelected(option.value)} />
          <span>{option.label}</span>
        </label>
      ))}
      {(exercise.type === "SHORT_EXACT" || exercise.type === "NUMERIC") && (
        <input className="answer-input" value={input} onChange={(e) => setInput(e.target.value)}
          inputMode={exercise.type === "NUMERIC" ? "decimal" : "text"}
          placeholder={exercise.type === "NUMERIC" ? "Digite um número" : "Digite sua resposta"} />
      )}
      {exercise.type === "STRUCTURED" && (
        <textarea className="answer-input" rows={5} value={input} onChange={(e) => setInput(e.target.value)} />
      )}
    </fieldset>

    <div style={{margin:"1rem 0"}}>
      <p className="muted" style={{fontSize:".86rem",marginBottom:".55rem"}}>Quão confiante você está?</p>
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:".45rem"}}>
        {[.25,.5,.75,1].map((value) => <button type="button" key={value}
          onClick={() => setConfidence(value)}
          style={{minHeight:"42px",borderRadius:"10px",border:`1px solid ${confidence===value ? "var(--accent)" : "var(--border)"}`,background:"var(--surface-raised)",color:"var(--text)"}}>
          {Math.round(value*100)}%
        </button>)}
      </div>
    </div>

    <label className="hint-check">
      <input type="checkbox" checked={usedHelp} onChange={(e) => setUsedHelp(e.target.checked)} />
      Consultei material, resposta anterior ou alguma dica.
    </label>
    {error && <div className="notice error" style={{marginBottom:"1rem"}}>{error}</div>}
    <button className="button primary full-width" type="submit" disabled={busy}>{busy ? "Analisando…" : "Responder"}</button>
  </form>;
}
