"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Tema = "claro" | "escuro";
const Contexto = createContext<{ tema: Tema; alternar: () => void } | null>(null);

export function useTema() {
  const c = useContext(Contexto);
  if (!c) throw new Error("useTema fora do TemaProvider");
  return c;
}

/** O tema inicial (preferencia salva ou do sistema) ja foi aplicado por um script no <head>, antes da pintura, sem piscar. */
export function TemaProvider({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>("claro");
  useEffect(() => { setTema(document.documentElement.dataset.tema === "escuro" ? "escuro" : "claro"); }, []);
  const alternar = () => {
    const novo: Tema = tema === "claro" ? "escuro" : "claro";
    setTema(novo);
    document.documentElement.dataset.tema = novo;
    try { localStorage.setItem("tema", novo); } catch { /* sem storage */ }
  };
  return <Contexto.Provider value={{ tema, alternar }}>{children}</Contexto.Provider>;
}
