"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useApi } from "./api";
import { useI18n } from "./i18n";
import type { Indicador, Pais, Usuario } from "./tipos";

type Ctx = {
  usuario: Usuario | null; paises: Pais[]; pais: string; paisAtual: Pais | undefined;
  setPais: (p: string) => void; catalogo: Indicador[];
};
const Contexto = createContext<Ctx | null>(null);

export function useApp(): Ctx {
  const c = useContext(Contexto);
  if (!c) throw new Error("useApp fora do AppProvider");
  return c;
}

/** Carrega usuario, paises e catalogo uma vez; guarda o pais escolhido (filtro global, BDR-002). */
export function AppProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const eu = useApi<Usuario>("/auth/me");
  const ps = useApi<Pais[]>("/paises");
  const cat = useApi<Indicador[]>("/catalogo");
  const [escolhido, setEscolhido] = useState("Brazil");
  useEffect(() => {
    try { const s = localStorage.getItem("pais"); if (s) setEscolhido(s); } catch { /* sem storage */ }
  }, []);
  const setPais = (p: string) => {
    setEscolhido(p);
    try { localStorage.setItem("pais", p); } catch { /* sem storage */ }
  };
  if (!eu.dados || !ps.dados) return <p className="carregando" role="status">{t("comum.carregando")}</p>;
  const paisAtual = ps.dados.find((p) => p.pais === escolhido) ?? ps.dados[0];
  return (
    <Contexto.Provider value={{ usuario: eu.dados, paises: ps.dados, pais: paisAtual?.pais ?? "Brazil", paisAtual, setPais, catalogo: cat.dados ?? [] }}>
      {children}
    </Contexto.Provider>
  );
}
