"use client";
import { useState } from "react";
import { Floresta } from "@/components/Floresta";
import { CabecalhoPagina, Painel, TurnosRetorno } from "@/components/Graficos";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { R, useI18n } from "@/lib/i18n";
import { nomePais } from "@/lib/pais";
import { pp } from "@/lib/formato";
import type { Efeito, FatorNivel } from "@/lib/tipos";

type Filtro = "todos" | "alavanca" | "perfil";

export default function Fatores() {
  const { pais, paisAtual } = useApp();
  const { t, idioma } = useI18n();
  const efeitos = useApi<Efeito[]>(`/efeitos?pais=${encodeURIComponent(pais)}`);
  const turnos = useApi<FatorNivel[]>(`/retencao/fatores?pais=${encodeURIComponent(pais)}&fator=turnos_da_primeira_conversa`);
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const todos = efeitos.dados ?? [];
  const lista = todos.filter((e) => filtro === "todos" || e.tipo === filtro);
  const ef = (fator: string, inicio?: string) => todos.find((e) => e.fator === fator && (!inicio || e.contraste.startsWith(inicio)));
  const sa = ef("Tema do primeiro pedido", "Saudação"), re = ef("Recusa na primeira resposta"), mo = ef("Modelo"), lo = ef("Tamanho da primeira resposta");
  const ic = (e?: Efeito) => (e ? { e: pp(e.efeito_pp), lo: pp(e.ic_lo), hi: pp(e.ic_hi) } : null);
  const opcoes: [Filtro, string][] = [["todos", t("fa.todos")], ["alavanca", t("fa.alavancas")], ["perfil", t("fa.perfil")]];

  return (
    <>
      <CabecalhoPagina eyebrow={t("fa.eyebrow")} titulo={t("fa.h1a")} destaque={t("fa.h1b")} desc={t("fa.desc")} />

      <div className="aviso"><R texto={t("fa.comoLer")} /></div>

      {efeitos.erro && <p className="aviso alerta" role="alert">{t("comum.erro", { erro: efeitos.erro })}</p>}
      {!efeitos.carregando && !efeitos.erro && todos.length === 0 ? (
        <section className="cartao">
          <p className="vazio">
            <R texto={t("fa.vazio")} /><br />
            {t("fa.vazioSel")} {paisAtual && !paisAtual.tem_texto ? t("fa.vazioSemTexto", { nome: nomePais(paisAtual, idioma, t("pais.desconhecido")) }) : ""}
          </p>
        </section>
      ) : (
        <Painel titulo={t("fa.efeitoTitulo")} pergunta={t("fa.efeitoPergunta")}>
          <div className="pilulas" role="group" aria-label={t("fa.filtroAria")}>
            {opcoes.map(([k, texto]) => <button key={k} type="button" className="pilula" aria-pressed={filtro === k} onClick={() => setFiltro(k)}>{texto}</button>)}
          </div>
          {efeitos.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : <Floresta efeitos={lista} />}
        </Painel>
      )}

      {todos.length > 0 && (
        <div className="grade2">
          <Painel titulo={t("fa.turnosTitulo")} pergunta={t("fa.turnosPergunta")}>
            {turnos.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : turnos.dados?.length ? <TurnosRetorno dados={turnos.dados} /> : <p className="vazio">{t("vg.semDados")}</p>}
          </Painel>
          <Painel titulo={t("fa.achadosTitulo")} pergunta={t("fa.achadosPergunta")}>
            <ol className="achados">
              {sa && <li><span className="num-achado">1</span><div><b>{t("fa.a1t")}</b><p>{t("fa.a1d", { ...ic(sa)! })}</p></div></li>}
              {re && <li><span className="num-achado">2</span><div><b>{t("fa.a2t")}</b><p>{t("fa.a2d", { ...ic(re)! })}</p></div></li>}
              {mo && lo && <li><span className="num-achado">3</span><div><b>{t("fa.a3t")}</b><p>{t("fa.a3d", { e1: ic(mo)!.e, lo1: ic(mo)!.lo, hi1: ic(mo)!.hi, e2: ic(lo)!.e })}</p></div></li>}
            </ol>
          </Painel>
        </div>
      )}
    </>
  );
}