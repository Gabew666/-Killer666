import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "ATLAS — Aprendizado Adaptativo",
  description: "Sessões de estudo adaptativas, no seu tempo.",
  manifest: "/manifest.webmanifest",
  applicationName: "ATLAS",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0a1020",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="site-header">
          <nav className="nav wrap" aria-label="Navegação principal">
            <Link href="/" className="brand">ATLAS<span className="brand-dot">.</span></Link>
            <Link href="/progress" className="nav-link">Progresso</Link>
          </nav>
        </header>
        <main className="wrap main-content">{children}</main>
      </body>
    </html>
  );
}
