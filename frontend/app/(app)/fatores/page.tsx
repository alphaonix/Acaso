"use client";
import { useState } from "react";
import { Floresta } from "@/components/Floresta";
import { EstratosModelo } from "@/components/AnaliseAmpliada";
import { BarrasTema, CabecalhoPagina, Painel, TurnosRetorno } from "@/components/Graficos";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { R, useI18n } from "@/lib/i18n";
import { nomePais } from "@/lib/pais";
import { resisteACorrecao } from "@/lib/estatistica";
import { dec, pct, pp } from "@/lib/formato";
import type { Efeito, Estrato, FatorNivel } from "@/lib/tipos";

type Filtro = "todos" | "alavanca" | "perfil";
const GRUPOS = ["dispositivo", "sistema", "navegador"] as const;
type Grupo = (typeof GRUPOS)[number];

export default function Fatores() {
  const { pais, paisAtual } = useApp();
  const { t, idioma } = useI18n();
  const efeitos = useApi<Efeito[]>(`/efeitos?pais=${encodeURIComponent(pais)}`);
  const turnos = useApi<FatorNivel[]>(`/retencao/fatores?pais=${encodeURIComponent(pais)}&fator=turnos_da_primeira_conversa`);
  const resumo = useApi<{ elegiveis: number }>(`/retencao/resumo?pais=${encodeURIComponent(pais)}`);
  const estratos = useApi<Estrato[]>(`/retencao/estratos?pais=${encodeURIComponent(pais)}`);
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [ordem, setOrdem] = useState<"tamanho" | "confianca">("tamanho");   // o enunciado pede por tamanho do efeito; a confianca e a alternativa
  const [grupo, setGrupo] = useState<Grupo>("dispositivo");
  const disp = useApi<FatorNivel[]>(`/retencao/fatores?pais=${encodeURIComponent(pais)}&fator=${grupo}`);
  const idi = useApi<FatorNivel[]>(`/retencao/fatores?pais=${encodeURIComponent(pais)}&fator=idioma_x_navegador`);
  const rotulo: Record<Grupo, string> = { dispositivo: t("ex.dispDispositivo"), sistema: t("ex.dispSistema"), navegador: t("ex.dispNavegador") };
  const todos = efeitos.dados ?? [];
  // padrao: pelo tamanho do efeito (valor absoluto). Alternativa: resistentes a correcao, depois indicios, depois inconclusivos; em cada grupo, pelo tamanho
  const rank = (e: Efeito) => (resisteACorrecao(e, todos.length) ? 0 : e.ic_lo > 0 || e.ic_hi < 0 ? 1 : 2);
  const porTamanho = (a: Efeito, b: Efeito) => Math.abs(b.efeito_pp) - Math.abs(a.efeito_pp);
  const lista = todos.filter((e) => filtro === "todos" || e.tipo === filtro).sort((a, b) => (ordem === "confianca" ? rank(a) - rank(b) || porTamanho(a, b) : porTamanho(a, b)));
  const ef = (fator: string, inicio?: string) => todos.find((e) => e.fator === fator && (!inicio || e.contraste.startsWith(inicio)));
  const sa = ef("Tema do primeiro pedido", "Saudação"), re = ef("Recusa na primeira resposta"), mo = ef("Modelo"), lo = ef("Tamanho da primeira resposta");
  // impacto = parcela de pessoas com o fator x efeito (em pp); vale so se o efeito for causal
  const elegiveis = resumo.dados?.elegiveis ?? 0;
  const pts = (x: number) => t(x < 0 ? "vg.pontosMenos" : "vg.pontosMais", { v: dec(Math.abs(x)) });
  const imp = (e?: Efeito) => { if (!e || !elegiveis) return null; const k = e.n_tratados / elegiveis, g = (x: number) => `${dec(Math.abs(x) * k)} pp`; const [a, b] = [Math.abs(e.ic_lo), Math.abs(e.ic_hi)].sort((x, y) => x - y); return { sh: pct(k), imp: g(e.efeito_pp), il: g(a), ih: g(b) }; };
  const ic = (e?: Efeito) => (e ? { e: pp(e.efeito_pp), lo: pp(e.ic_lo), hi: pp(e.ic_hi) } : null);
  const dif = (fator: string, fam: string) => estratos.dados?.find((e) => e.fator === fator && e.familia === fam)?.diferenca?.pp;
  const [s35, s4, r35, r4] = [dif("saudacao", "GPT-3.5"), dif("saudacao", "GPT-4"), dif("recusa", "GPT-3.5"), dif("recusa", "GPT-4")];
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
          <div className="pilulas" role="group" aria-label={t("fa.ordemAria")} style={{ marginTop: "0.5rem" }}>
            {([["tamanho", t("fa.ordemTamanho")], ["confianca", t("fa.ordemConfianca")]] as const).map(([k, texto]) => <button key={k} type="button" className="pilula" aria-pressed={ordem === k} onClick={() => setOrdem(k)}>{texto}</button>)}
          </div>
          {efeitos.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : <Floresta efeitos={lista} total={todos.length} />}
        </Painel>
      )}

      {todos.length > 0 && (
        <div className="grade2">
          <Painel nota="nt.turnos" titulo={t("fa.turnosTitulo")} pergunta={t("fa.turnosPergunta")}>
            {turnos.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : turnos.dados?.length ? <TurnosRetorno dados={turnos.dados} /> : <p className="vazio">{t("vg.semDados")}</p>}
          </Painel>
          <Painel nota="nt.achados" titulo={t("fa.achadosTitulo")} pergunta={t("fa.achadosPergunta")}>
            <ol className="achados">
              {sa && imp(sa) && <li><span className="num-achado">1</span><div><b>{t("fa.a1t")}</b><p><R texto={t("fa.a1d", { ...ic(sa)!, ...imp(sa)!, e: pts(sa.efeito_pp), nota: t(resisteACorrecao(sa, todos.length) ? "fa.nResiste" : "fa.nIndicio") })} /></p></div></li>}
              {re && imp(re) && <li><span className="num-achado">2</span><div><b>{t("fa.a2t")}</b><p><R texto={t("fa.a2d", { ...ic(re)!, ...imp(re)!, e: pts(re.efeito_pp), nota: t(resisteACorrecao(re, todos.length) ? "fa.nResiste" : "fa.nIndicio") })} /></p></div></li>}
              {mo && lo && <li><span className="num-achado">3</span><div><b>{t("fa.a3t")}</b><p><R texto={t("fa.a3d", { e1: ic(mo)!.e, lo1: ic(mo)!.lo, hi1: ic(mo)!.hi, e2: ic(lo)!.e })} /></p></div></li>}
              {s35 != null && s4 != null && r35 != null && r4 != null && <li><span className="num-achado">4</span><div><b>{t("fa.a4t")}</b><p><R texto={t("fa.a4d", { s35: pp(s35), s4: pp(s4), r35: pp(r35), r4: pp(r4) })} /></p></div></li>}
            </ol>
          </Painel>
        </div>
      )}

      {todos.length > 0 && (
        <Painel className="bloco" titulo={t("fa.estTitulo")} pergunta={t("fa.estPergunta")}>
          {estratos.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : estratos.dados ? <EstratosModelo dados={estratos.dados} /> : <p className="vazio">{t("vg.semDados")}</p>}
        </Painel>
      )}

      <div className="grade2">
        <Painel nota="ex.dispAviso" titulo={t("ex.dispTitulo")} pergunta={t("ex.dispPergunta")}>
          <div className="pilulas" role="group" aria-label={t("ex.dispGrupo")}>
            {GRUPOS.map((g) => <button key={g} type="button" className="pilula" aria-pressed={grupo === g} onClick={() => setGrupo(g)}>{rotulo[g]}</button>)}
          </div>
          {disp.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : disp.dados?.some((x) => x.taxa != null) ? <BarrasTema dados={disp.dados} /> : <p className="vazio">{t("ex.semDados")}</p>}
        </Painel>
        <Painel nota="ex.idiAviso" titulo={t("ex.idiTitulo")} pergunta={t("ex.idiPergunta")}>
          {idi.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : idi.dados?.some((x) => x.taxa != null) ? <BarrasTema dados={idi.dados} /> : <p className="vazio">{t("ex.semDados")}</p>}
        </Painel>
      </div>
    </>
  );
}