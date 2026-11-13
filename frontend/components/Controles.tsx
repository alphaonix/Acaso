"use client";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/lib/contexto";
import { bandeiraDe } from "@/lib/bandeiras";
import { num } from "@/lib/formato";
import { IDIOMAS, useI18n } from "@/lib/i18n";
import { nomePais } from "@/lib/pais";
import { useTema } from "@/lib/tema";

const ico = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, focusable: false };

export function SeletorIdioma() {
  const { idioma, setIdioma, t } = useI18n();
  return (
    <div className="seg" role="group" aria-label={t("topo.idioma")}>
      {IDIOMAS.map((i) => (
        <button key={i.codigo} type="button" aria-pressed={i.codigo === idioma} title={i.nome} lang={i.locale} onClick={() => setIdioma(i.codigo)}>{i.rotulo}</button>
      ))}
    </div>
  );
}

export function BotaoTema() {
  const { tema, alternar } = useTema();
  const { t } = useI18n();
  const rotulo = tema === "claro" ? t("topo.temaParaEscuro") : t("topo.temaParaClaro");
  return (
    <button type="button" className="icone-btn" onClick={alternar} aria-label={rotulo} title={rotulo}>
      {tema === "claro"
        ? <svg {...ico}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
        : <svg {...ico}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>}
    </button>
  );
}

/** Bandeira em SVG (pacote country-flag-icons, sem chamada externa); sem codigo ISO, um globo. */
function Flag({ iso2 }: { iso2: string | null }) {
  const B = bandeiraDe(iso2);
  if (B) return <B className="bandeira" aria-hidden={true} />;
  return <svg {...ico} className="bandeira bandeira-globo" width={16} height={16}><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></svg>;
}

/** Lista propria (listbox acessivel): a bandeira aparece no campo e em cada pais; fechada mostra so o nome, aberta traz os usuarios. */
export function SeletorPais() {
  const { paises, pais, setPais } = useApp();
  const { t, idioma } = useI18n();
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(0);
  const raiz = useRef<HTMLDivElement>(null);
  const lista = useRef<HTMLUListElement>(null);
  const nome = (p: (typeof paises)[number]) => nomePais(p, idioma, t("pais.desconhecido"));
  const atual = paises.find((p) => p.pais === pais);

  const abrir = () => { setAtivo(Math.max(0, paises.findIndex((p) => p.pais === pais))); setAberto(true); };
  const escolher = (i: number) => { if (paises[i]) setPais(paises[i].pais); setAberto(false); raiz.current?.querySelector("button")?.focus(); };

  useEffect(() => {
    if (!aberto) return;
    lista.current?.focus();
    const fora = (e: MouseEvent) => { if (!raiz.current?.contains(e.target as Node)) setAberto(false); };
    document.addEventListener("mousedown", fora);
    return () => document.removeEventListener("mousedown", fora);
  }, [aberto]);
  useEffect(() => { if (aberto) lista.current?.children[ativo]?.scrollIntoView({ block: "nearest" }); }, [aberto, ativo]);

  const tecla = (e: React.KeyboardEvent) => {
    const n = paises.length;
    if (e.key === "ArrowDown") { e.preventDefault(); setAtivo((a) => Math.min(n - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setAtivo((a) => Math.max(0, a - 1)); }
    else if (e.key === "Home") { e.preventDefault(); setAtivo(0); }
    else if (e.key === "End") { e.preventDefault(); setAtivo(n - 1); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); escolher(ativo); }
    else if (e.key === "Escape" || e.key === "Tab") { setAberto(false); raiz.current?.querySelector("button")?.focus(); }
    else if (e.key.length === 1) {                       // digitar a inicial salta para o primeiro pais com ela
      const k = e.key.toLowerCase();
      const i = paises.findIndex((p, idx) => idx > ativo && nome(p).toLowerCase().startsWith(k));
      const j = i >= 0 ? i : paises.findIndex((p) => nome(p).toLowerCase().startsWith(k));
      if (j >= 0) setAtivo(j);
    }
  };

  return (
    <div className="seletor" ref={raiz}>
      <button type="button" className="seletor-btn" title={t("topo.pais")} aria-label={`${t("topo.pais")}: ${atual ? nome(atual) : ""}`}
        aria-haspopup="listbox" aria-expanded={aberto} onClick={() => (aberto ? setAberto(false) : abrir())}>
        <Flag iso2={atual?.iso2 ?? null} />
        <span className="seletor-nome">{atual ? nome(atual) : ""}</span>
        <svg {...ico} width={12} height={12} strokeWidth={3} className="seletor-seta"><path d="M6 9l6 6 6-6" /></svg>
      </button>
      {aberto && (
        <ul className="seletor-lista" role="listbox" tabIndex={-1} ref={lista} aria-label={t("topo.pais")} aria-activedescendant={`pais-op-${ativo}`} onKeyDown={tecla}>
          {paises.map((p, i) => (
            <li key={p.pais} id={`pais-op-${i}`} role="option" aria-selected={p.pais === pais} className={`seletor-op${i === ativo ? " ativo" : ""}${p.pais === pais ? " atual" : ""}`}
              onMouseEnter={() => setAtivo(i)} onClick={() => escolher(i)}>
              <Flag iso2={p.iso2} /><span className="seletor-op-nome">{nome(p)}</span><span className="seletor-op-n">{num(p.usuarios)} {t("topo.usuarios")}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
export function MenuUsuario({ onSair }: { onSair: () => void }) {
  const { usuario } = useApp();
  const { t } = useI18n();
  const [aberto, setAberto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setAberto(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setAberto(false); };
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fora); document.removeEventListener("keydown", esc); };
  }, [aberto]);
  const [fotoFalhou, setFotoFalhou] = useState(false);
  const iniciais = (usuario?.nome ?? "?").split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
  return (
    <div className="menu-usuario" ref={ref}>
      <button type="button" className="avatar" aria-haspopup="menu" aria-expanded={aberto} aria-label={`${t("topo.conta")}: ${usuario?.nome ?? ""}`} onClick={() => setAberto(!aberto)}>{usuario?.foto && !fotoFalhou ? <img src={usuario.foto} alt="" referrerPolicy="no-referrer" className="avatar-foto" onError={() => setFotoFalhou(true)} /> : iniciais}</button>
      {aberto && (
        <div className="menu-painel" role="menu">
          <div className="menu-id"><b>{usuario?.nome}</b><span>{usuario?.email}</span></div>
          <button type="button" role="menuitem" className="menu-item" onClick={onSair}>{t("topo.sair")}</button>
        </div>
      )}
    </div>
  );
}
