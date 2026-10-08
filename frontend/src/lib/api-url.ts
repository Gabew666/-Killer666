export function resolveApiUrl(value: string | undefined, production: boolean): string {
  const configured = value?.trim();
  if (!configured && production) {
    throw new Error("NEXT_PUBLIC_ATLAS_API_URL é obrigatória no build de produção.");
  }
  const url = new URL(configured || "http://localhost:8000");
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error("NEXT_PUBLIC_ATLAS_API_URL deve ser uma URL HTTP(S) pública, sem credenciais.");
  }
  return url.toString().replace(/\/+$/, "");
}
