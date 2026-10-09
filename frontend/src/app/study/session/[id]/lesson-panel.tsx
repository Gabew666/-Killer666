import type { StudyGuide } from "@/lib/study-guides";

export default function LessonPanel({ guide, mode }: { guide: StudyGuide; mode: string }) {
  if (mode === "EXAMPLE") {
    return <div style={{display:"grid",gap:".8rem"}}>
      <p className="eyebrow">Exemplo resolvido</p>
      <h3>{guide.example.title}</h3>
      <ol style={{margin:"0",paddingLeft:"1.25rem",lineHeight:1.65}}>
        {guide.example.steps.map((step) => <li key={step}>{step}</li>)}
      </ol>
      <div className="notice success"><strong>Ideia central</strong><p>{guide.example.takeaway}</p></div>
    </div>;
  }

  if (mode === "ERROR_REVIEW") {
    return <div style={{display:"grid",gap:".8rem"}}>
      <p className="eyebrow">Onde costuma dar errado</p>
      <ul style={{margin:"0",paddingLeft:"1.25rem",lineHeight:1.65}}>
        {guide.mistakes.map((item) => <li key={item}>{item}</li>)}
      </ul>
      <div className="notice warning"><strong>Cheque antes de seguir</strong><p>{guide.quickCheck}</p></div>
    </div>;
  }

  return <div style={{display:"grid",gap:".9rem"}}>
    <div>
      <p className="eyebrow">Aula guiada</p>
      <h3>{guide.title}</h3>
      <p className="activity-instructions">{guide.summary}</p>
    </div>
    <div className="notice success"><strong>Por que isso importa?</strong><p>{guide.why}</p></div>
    <div>
      <h3>Pontos-chave</h3>
      <ul style={{margin:"0",paddingLeft:"1.25rem",lineHeight:1.65}}>
        {guide.keyPoints.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
    <div style={{padding:"1rem",border:"1px solid var(--border)",borderRadius:"14px",background:"var(--surface-raised)"}}>
      <p className="eyebrow">Exemplo resolvido</p>
      <h3>{guide.example.title}</h3>
      <ol style={{margin:"0",paddingLeft:"1.25rem",lineHeight:1.65}}>
        {guide.example.steps.map((step) => <li key={step}>{step}</li>)}
      </ol>
      <p className="muted" style={{marginTop:".8rem",marginBottom:0}}>{guide.example.takeaway}</p>
    </div>
    <p className="muted" style={{fontSize:".82rem"}}>{guide.source} · síntese autoral do ATLAS baseada no material da disciplina.</p>
  </div>;
}
