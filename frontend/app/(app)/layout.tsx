"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BotaoTema, MenuUsuario, SeletorIdioma, SeletorPais } from "@/components/Controles";
import { api } from "@/lib/api";
import { AppProvider } from "@/lib/contexto";
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
    </header>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppProvider>
      <Topo />
      <main className="conteudo">{children}</main>
    </AppProvider>
  );
}
