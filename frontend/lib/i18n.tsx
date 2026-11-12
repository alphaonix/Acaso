"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { definirLocale } from "./formato";
import { en } from "./idiomas/en";
import { pt, type Chave } from "./idiomas/pt";

export type Idioma = "pt" | "en";
/** Para incluir outro idioma (ex.: espanhol): criar lib/idiomas/es.ts com as mesmas chaves e acrescentar aqui. */
export const IDIOMAS: { codigo: Idioma; rotulo: string; nome: string; locale: string }[] = [
  { codigo: "pt", rotulo: "PT", nome: "Português", locale: "pt-BR" },
  { codigo: "en", rotulo: "EN", nome: "English", locale: "en-US" },
];
const DICIONARIOS: Record<Idioma, Record<Chave, string>> = { pt, en };

type Vars = Record<string, string | number>;
type Ctx = { idioma: Idioma; setIdioma: (i: Idioma) => void; t: (k: Chave, v?: Vars) => string };
const Contexto = createContext<Ctx | null>(null);

export function useI18n(): Ctx {
  const c = useContext(Contexto);
  if (!c) throw new Error("useI18n fora do I18nProvider");
  return c;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [idioma, setIdiomaState] = useState<Idioma>("pt");
  useEffect(() => {
    try {
      const s = localStorage.getItem("idioma");
      setIdiomaState(s === "pt" || s === "en" ? s : navigator.language.toLowerCase().startsWith("en") ? "en" : "pt");
    } catch { /* sem storage */ }
  }, []);
  const locale = IDIOMAS.find((i) => i.codigo === idioma)!.locale;
  definirLocale(locale); // sincrono: os filhos formatam numeros e datas com o locale certo
  useEffect(() => { document.documentElement.lang = locale; }, [locale]);
  const setIdioma = (i: Idioma) => {
    setIdiomaState(i);
    try { localStorage.setItem("idioma", i); } catch { /* sem storage */ }
  };
  const t = useCallback((k: Chave, v?: Vars) => {
    let s: string = DICIONARIOS[idioma][k] ?? pt[k];
    if (v) for (const [nome, valor] of Object.entries(v)) s = s.replaceAll(`{${nome}}`, String(valor));
    return s;
  }, [idioma]);
  return <Contexto.Provider value={{ idioma, setIdioma, t }}>{children}</Contexto.Provider>;
}

/** Renderiza **negrito** e *italico* de um texto do dicionario. */
export function R({ texto }: { texto: string }) {
  const partes = texto.split(/(\*\*.+?\*\*|\*.+?\*)/g);
  return (
    <>
      {partes.map((p, i) =>
        p.startsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong>
          : p.length > 2 && p.startsWith("*") ? <em key={i}>{p.slice(1, -1)}</em> : p)}
    </>
  );
}
