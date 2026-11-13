"use client";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/lib/contexto";
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

export function SeletorPais() {
  const { paises, pais, setPais } = useApp();
  const { t, idioma } = useI18n();
  const [aberto, setAberto] = useState(false);   // fechado mostra so o pais; ao abrir a lista traz os usuarios de cada um
  return (
    <label className="seletor" title={t("topo.pais")}>
      <span className="sr-only">{t("topo.pais")}</span>
      <svg {...ico} width={16} height={16}><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></svg>
      <select value={pais} onMouseDown={() => setAberto(true)} onBlur={() => setAberto(false)} onKeyDown={(e) => { if (e.key === "Escape") setAberto(false); }}
        onChange={(e) => { setPais(e.target.value); setAberto(false); }}>
        {paises.map((p) => <option key={p.pais} value={p.pais}>{nomePais(p, idioma, t("pais.desconhecido"))}{aberto ? ` · ${num(p.usuarios)} ${t("topo.usuarios")}` : ""}</option>)}
      </select>
    </label>
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
