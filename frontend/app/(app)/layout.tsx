"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { BotaoTema, MenuUsuario, SeletorIdioma, SeletorPais } from "@/components/Controles";
import { api, useApi } from "@/lib/api";
import { AppProvider, useApp } from "@/lib/contexto";
import { dataLonga } from "@/lib/formato";
import { useI18n } from "@/lib/i18n";

const LINKS = [
  { href: "/visao-geral", chave: "nav.visao" },
  { href: "/fatores", chave: "nav.fatores" },
  { href: "/coortes", chave: "nav.coortes" },
  { href: "/glossario", chave: "nav.glossario" },
  { href: "/sobre", chave: "nav.sobre" },
] as const;

function Topo() {
  const { t } = useI18n();
  const caminho = usePathname();
  const router = useRouter();
  const [aberto, setAberto] = useState(false);   // menu hamburguer (so aparece em tela estreita)
  useEffect(() => { setAberto(false); }, [caminho]);
  async function sair() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/login");
  }
  return (
    <header className="topo">
      <div className="topo-int">
        <Link href="/visao-geral" className="logo-link" aria-label={t("topo.inicio")} title={t("topo.irInicio")}>
          <img className="logo logo-claro" src="/logo-acaso.svg" alt="" />
          <img className="logo logo-escuro" src="/logo-acaso-branco.svg" alt="" />
        </Link>
        <button type="button" className="hamb" aria-label={t("nav.menu")} aria-expanded={aberto} aria-controls="topo-painel" onClick={() => setAberto(!aberto)}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
            {aberto ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
        <div className="topo-painel" id="topo-painel" data-aberto={aberto}>
          <nav className="nav" aria-label={t("nav.aria")}>
            {LINKS.map((l) => (
              <Link key={l.href} href={l.href} aria-current={caminho === l.href ? "page" : undefined}>{t(l.chave)}</Link>
            ))}
          </nav>
          <div className="acoes">
            <SeletorPais />
            <SeletorIdioma />
            <BotaoTema />
            <MenuUsuario onSair={sair} />
          </div>
        </div>
      </div>
    </header>
  );
}

/** Periodo dos dados do pais selecionado e data da ultima carga: o cliente sabe o quao atual e o que esta vendo. */
function RodapeApp() {
  const { t, idioma } = useI18n();
  const { paisAtual } = useApp();
  const saude = useApi<{ ultima_execucao_etl: { finalizado_em: string } | null }>("/saude");
  const carga = saude.dados?.ultima_execucao_etl?.finalizado_em;
  if (!paisAtual?.primeira_data || !paisAtual.ultima_data) return null;
  const d = (iso: string) => dataLonga(iso);
  return (
    <footer className="rodape-app">
      {t("rodape.base", { a: d(paisAtual.primeira_data), b: d(paisAtual.ultima_data) })}
      {carga ? ` ${t("rodape.carga", { c: new Date(carga).toLocaleDateString(idioma === "en" ? "en-US" : "pt-BR") })}` : ""}
    </footer>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppProvider>
      <Topo />
      <main className="conteudo">{children}</main>
      <RodapeApp />
    </AppProvider>
  );
}
