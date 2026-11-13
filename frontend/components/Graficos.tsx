"use client";
import { bandeiraDe } from "@/lib/bandeiras";
import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, ErrorBar, Line, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { nomePais } from "@/lib/pais";
import { dataCurta, dataLonga, mesAno, num, pct, pp } from "@/lib/formato";
import { Definicao } from "@/components/Definicao";
import { R, useI18n } from "@/lib/i18n";
import type { Chave } from "@/lib/idiomas/pt";
import { tNivel } from "@/lib/traducao-dados";
import type { Comparacao, Coorte, Decomposicao as Decomp, FatorNivel, Uso } from "@/lib/tipos";

const EIXO = { fontSize: 12, fill: "var(--texto-mudo)" };
/** marcas do eixo de porcentagem de 5 em 5 (ou 10 em 10 se o eixo for longo), terminando em `topo` */
const marcas = (topo: number) => { const passo = topo > 40 ? 10 : 5; return Array.from({ length: Math.floor(topo / passo) + 1 }, (_, i) => i * passo); };

/** Moldura de cada grafico: titulo, a pergunta que responde, o grafico, e a FONTE (de onde vem o numero). */
/** `nota` = texto padrao do painel: rotulo em negrito, o que mostra, o limite e o que fazer. `tipo` "alerta" (laranja) para cuidado, indicio e hipotese. */
export function Painel({ titulo, pergunta, nota, tipo = "info", className = "", children }: {
  titulo: string; pergunta?: string; nota?: Chave; tipo?: "info" | "alerta"; className?: string; children: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <section className={`cartao painel ${className}`}>
      <header className="painel-cab"><h2>{titulo}</h2>{pergunta && <p>{pergunta}</p>}</header>
      {nota && <div className="aviso"><R texto={t(nota)} /></div>}
      <div className="painel-corpo">{children}</div>
    </section>
  );
}
function Dica({ linhas }: { linhas: React.ReactNode }) {
  return <div className="tip-graf">{linhas}</div>;
}

/* ---------------- Modelo na 1a conversa (rosca) ---------------- */
export function RoscaModelo({ dados }: { dados: FatorNivel[] }) {
  const cores = ["var(--graf-1)", "var(--graf-2)", "var(--graf-3)"];
  const total = dados.reduce((s, d) => s + d.elegiveis, 0);
  const fatias = dados.map((d) => ({ nome: d.nivel, valor: d.elegiveis, p: total ? d.elegiveis / total : 0 }));
  return (
    <div>
      <div role="img" className="graf-flex" style={{ minHeight: 210 }} aria-label={fatias.map((f) => `${f.nome} ${pct(f.p)}`).join(", ")}>
        <ResponsiveContainer width="100%" height="100%" minHeight={210}>
          <PieChart>
            <Pie data={fatias} dataKey="valor" nameKey="nome" innerRadius={60} outerRadius={90} paddingAngle={3} stroke="none">
              {fatias.map((_, i) => <Cell key={i} fill={cores[i % cores.length]} />)}
            </Pie>
            <Tooltip content={({ active, payload }) => active && payload?.length ? <Dica linhas={<><strong>{payload[0].payload.nome}</strong><br />{pct(payload[0].payload.p)} · {num(payload[0].payload.valor)}</>} /> : null} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="legenda-graf">
        {fatias.map((f, i) => <span key={f.nome}><i style={{ background: cores[i % cores.length] }} />{f.nome} · {pct(f.p)}</span>)}
      </div>
    </div>
  );
}

/* ---------------- Retorno por tema (barras horizontais com IC) ---------------- */
/** Niveis que sobram da classificacao (nao sao temas de verdade): vao para o fim e em cinza. */
const RESIDUAIS = ["Outro", "Vazio"];

export function BarrasTema({ dados }: { dados: FatorNivel[] }) {
  const { t, idioma } = useI18n();
  const topoTema = Math.ceil((Math.max(0, ...dados.filter((d) => d.taxa != null).map((d) => (d.ic_hi ?? d.taxa!) * 100)) + 2) / 5) * 5;
  const linhas = dados.filter((d) => d.taxa != null)
    .map((d) => ({ nome: tNivel(d.nivel, idioma), residual: RESIDUAIS.includes(d.nivel), taxa: d.taxa! * 100, erro: [(d.taxa! - (d.ic_lo ?? 0)) * 100, ((d.ic_hi ?? 0) - d.taxa!) * 100], n: d.elegiveis, v: d.voltaram_7d, lo: d.ic_lo, hi: d.ic_hi }))
    .sort((a, b) => Number(a.residual) - Number(b.residual) || b.taxa - a.taxa);   // "Outro" e "Vazio" por ultimo e em cinza: nao sao temas
  return (
    <div role="img" className="graf-flex" style={{ minHeight: Math.max(220, linhas.length * 34 + 40) }} aria-label={linhas.map((l) => `${l.nome} ${l.taxa.toFixed(1)}%`).join("; ")}>
      <ResponsiveContainer width="100%" height="100%" minHeight={Math.max(220, linhas.length * 34 + 40)}>
        <BarChart data={linhas} layout="vertical" margin={{ left: 4, right: 24, top: 4, bottom: 4 }}>
          <CartesianGrid stroke="var(--borda)" horizontal={false} />
          <XAxis type="number" unit="%" tick={EIXO} stroke="var(--borda)" tickLine={false} domain={[0, topoTema]} ticks={marcas(topoTema)} />
          <YAxis type="category" dataKey="nome" tick={EIXO} stroke="var(--borda)" tickLine={false} width={170} />
          <Tooltip cursor={{ fill: "var(--acento-fundo)" }} content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const l = payload[0].payload;
            return <Dica linhas={<><strong>{l.nome}</strong><br />{t("grafico.retorno")} <b>{pct(l.taxa / 100)}</b><br />{t("grafico.ic", { lo: pct(l.lo), hi: pct(l.hi) })}<br />{t("grafico.voltaram", { v: num(l.v), n: num(l.n) })}</>} />;
          }} />
          <Bar dataKey="taxa" fill="var(--graf-1)" radius={[0, 6, 6, 0]}>
            {linhas.map((l) => <Cell key={l.nome} fill={l.residual ? "var(--graf-neutro)" : "var(--graf-1)"} />)}
            <ErrorBar dataKey="erro" direction="x" stroke="var(--texto-suave)" strokeWidth={1.5} width={5} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ---------------- Uso diario (area + linha, com filtro de periodo) ---------------- */
export function AreaUso({ dados }: { dados: Uso[] }) {
  const { t } = useI18n();
  const [janela, setJanela] = useState<30 | 90 | 0>(90);
  const fim = dados.length ? new Date(`${dados[dados.length - 1].dia.slice(0, 10)}T00:00:00Z`).getTime() : 0;
  const vis = janela === 0 ? dados : dados.filter((d) => fim - new Date(`${d.dia.slice(0, 10)}T00:00:00Z`).getTime() < janela * 86400000);
  const ops: [30 | 90 | 0, string][] = [[30, t("graf.d30")], [90, t("graf.d90")], [0, t("graf.tudo")]];
  return (
    <div>
      <div className="pilulas" role="group" aria-label={t("graf.periodo")}>
        {ops.map(([k, r]) => <button key={k} type="button" className="pilula" aria-pressed={janela === k} onClick={() => setJanela(k)}>{r}</button>)}
      </div>
      <div role="img" className="graf-flex" style={{ minHeight: 250 }} aria-label={t("graf.usoAria")}>
        <ResponsiveContainer width="100%" height="100%" minHeight={250}>
          <AreaChart data={vis} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <defs><linearGradient id="gUso" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--graf-1)" stopOpacity={0.45} /><stop offset="100%" stopColor="var(--graf-1)" stopOpacity={0.02} /></linearGradient></defs>
            <CartesianGrid stroke="var(--borda)" vertical={false} />
            <XAxis dataKey="dia" tickFormatter={dataCurta} tick={EIXO} stroke="var(--borda)" tickLine={false} minTickGap={36} />
            <YAxis tick={EIXO} stroke="var(--borda)" tickLine={false} width={40} />
            <Tooltip content={({ active, payload }) => active && payload?.length ? (
              <Dica linhas={<><strong>{dataLonga(payload[0].payload.dia)}</strong><br />{t("graf.conversas")}: <b>{num(payload[0].payload.conversas)}</b><br />{t("graf.ativos")}: <b>{num(payload[0].payload.usuarios_ativos)}</b></>} />
            ) : null} />
            <Area dataKey="conversas" stroke="var(--graf-1)" fill="url(#gUso)" strokeWidth={2} />
            <Area dataKey="usuarios_ativos" stroke="var(--graf-2)" fill="none" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="legenda-graf">
        <span><i style={{ background: "var(--graf-1)" }} />{t("graf.conversas")}</span>
        <span><i style={{ background: "var(--graf-2)" }} />{t("graf.ativos")}</span>
      </div>
    </div>
  );
}

/* ---------------- Turnos x retorno (barras = % de usuarios, linha = retorno) ---------------- */
const ORDEM_TURNOS = ["1 turno", "2-3 turnos", "4-6 turnos", "7+ turnos"];
export function TurnosRetorno({ dados }: { dados: FatorNivel[] }) {
  const { t, idioma } = useI18n();
  const total = dados.reduce((s, d) => s + d.elegiveis, 0);
  const linhas = [...dados].sort((a, b) => ORDEM_TURNOS.indexOf(a.nivel) - ORDEM_TURNOS.indexOf(b.nivel))
    .map((d) => ({ faixa: tNivel(d.nivel, idioma), pct: total ? (d.elegiveis / total) * 100 : 0, retorno: d.taxa == null ? null : d.taxa * 100, n: d.elegiveis, d }));
  return (
    <div>
      <div role="img" className="graf-flex" style={{ minHeight: 260 }} aria-label={t("graf.turnosAria")}>
        <ResponsiveContainer width="100%" height="100%" minHeight={260}>
          <ComposedChart data={linhas} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--borda)" vertical={false} />
            <XAxis dataKey="faixa" tick={EIXO} stroke="var(--borda)" tickLine={false} />
            <YAxis unit="%" tick={EIXO} stroke="var(--borda)" tickLine={false} width={44} />
            <Tooltip cursor={{ fill: "var(--acento-fundo)" }} content={({ active, payload }) => active && payload?.length ? (
              <Dica linhas={<><strong>{payload[0].payload.faixa}</strong><br />{t("graf.pctUsuarios")}: <b>{pct(payload[0].payload.pct / 100)}</b> ({num(payload[0].payload.n)})<br />{t("grafico.retorno")} <b>{pct(payload[0].payload.d.taxa)}</b><br />{t("grafico.ic", { lo: pct(payload[0].payload.d.ic_lo), hi: pct(payload[0].payload.d.ic_hi) })}</>} />
            ) : null} />
            <Bar dataKey="pct" fill="var(--graf-2)" radius={[6, 6, 0, 0]} />
            <Line dataKey="retorno" stroke="var(--graf-1)" strokeWidth={2.5} dot={{ r: 4, fill: "var(--graf-1)" }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="legenda-graf">
        <span><i style={{ background: "var(--graf-2)" }} />{t("graf.pctUsuarios")}</span>
        <span><i style={{ background: "var(--graf-1)" }} />{t("graf.retornoPct")}</span>
      </div>
    </div>
  );
}

/* ---------------- Coortes: novos por semana ---------------- */
export function BarrasNovos({ coortes }: { coortes: Coorte[] }) {
  const { t } = useI18n();
  return (
    <div>
      <div role="img" className="graf-flex" style={{ minHeight: 260 }} aria-label={t("graf.novosAria")}>
        <ResponsiveContainer width="100%" height="100%" minHeight={260}>
          <BarChart data={coortes} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--borda)" vertical={false} />
            <XAxis dataKey="semana" tickFormatter={dataCurta} tick={EIXO} stroke="var(--borda)" tickLine={false} minTickGap={28} />
            <YAxis tick={EIXO} stroke="var(--borda)" tickLine={false} width={40} />
            <Tooltip cursor={{ fill: "var(--acento-fundo)" }} content={({ active, payload }) => active && payload?.length ? (
              <Dica linhas={<><strong>{dataLonga(payload[0].payload.semana)}</strong><br />{t("col.novos")}: <b>{num(payload[0].payload.novos)}</b><br />{t("col.elegiveis")}: {num(payload[0].payload.elegiveis)}</>} />
            ) : null} />
            <Bar dataKey="novos" radius={[5, 5, 0, 0]}>
              {coortes.map((c) => <Cell key={c.semana} fill={c.amostra_pequena ? "var(--graf-neutro)" : "var(--graf-1)"} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="legenda-graf">
        <span><i style={{ background: "var(--graf-1)" }} />{t("graf.amostraOk")}</span>
        <span><i style={{ background: "var(--graf-neutro)" }} />{t("graf.amostraPeq")}</span>
      </div>
    </div>
  );
}

/* ---------------- Mapa de calor do retorno por semana ---------------- */
export function MapaCalor({ coortes }: { coortes: Coorte[] }) {
  const { t } = useI18n();
  const taxas = coortes.filter((c) => c.taxa != null).map((c) => c.taxa as number);
  const min = Math.min(...taxas), max = Math.max(...taxas);
  const forca = (v: number) => (max === min ? 0.5 : (v - min) / (max - min));
  return (
    <div className="calor" role="list">
      {coortes.map((c) => {
        if (c.taxa == null) {
          return <div key={c.semana} role="listitem" className="calor-celula" title={t("co.pequena")} style={{ background: "var(--borda-suave)", color: "var(--texto-mudo)" }}>
            <small>{dataCurta(c.semana)}</small><b>—</b><small>n={num(c.elegiveis)}</small></div>;
        }
        const f = forca(c.taxa);
        return (
          <div key={c.semana} role="listitem" className="calor-celula" title={`${pct(c.taxa)} · IC ${pct(c.ic_lo)} – ${pct(c.ic_hi)}`}
            style={{ background: `color-mix(in srgb, var(--roxo) ${Math.round(12 + f * 78)}%, var(--superficie))`, color: f > 0.5 ? "#fff" : "var(--texto-forte)" }}>
            <small>{dataCurta(c.semana)}</small><b>{pct(c.taxa)}</b><small>{t("co.calorN", { n: num(c.elegiveis) })}</small>
          </div>
        );
      })}
    </div>
  );
}

/* ---------------- Decomposicao: mudou o perfil (mix) ou a taxa? ---------------- */
const FATORES_DEC = ["tema", "turnos_da_primeira_conversa", "modelo", "periodo_do_dia"] as const;

export function Decomposicao({ pais }: { pais: string }) {
  const { t, idioma } = useI18n();
  const [fator, setFator] = useState<(typeof FATORES_DEC)[number]>("tema");
  const [de, setDe] = useState<string | null>(null);
  const [para, setPara] = useState<string | null>(null);
  const q = `/retencao/decomposicao?pais=${encodeURIComponent(pais)}&fator=${fator}${de && para ? `&de=${de}&para=${para}` : ""}`;
  const r = useApi<Decomp>(q);
  const d = r.dados;
  const mudar = (f: (typeof FATORES_DEC)[number]) => { setFator(f); setDe(null); setPara(null); };

  return (
    <div>
      <p className="dica" style={{ margin: "0 0 0.3rem" }}>{t("co.decPor")}</p>
      <div className="pilulas" role="group" aria-label={t("co.decPor")}>
        {FATORES_DEC.map((f) => <button key={f} type="button" className="pilula" aria-pressed={fator === f} onClick={() => mudar(f)}>{t(`co.f.${f}`)}</button>)}
      </div>
      {r.erro && <p className="aviso alerta" role="alert">{r.erro}</p>}
      {d && !d.disponivel && <p className="vazio">{t("co.decIndisp")}</p>}
      {d?.disponivel && d.componentes_pp && d.delta_pp != null && (() => {
        const c = d.componentes_pp!;
        const escala = Math.max(Math.abs(c.mix), Math.abs(c.taxa), Math.abs(c.interacao), Math.abs(d.delta_pp!), 1);
        const itens: [string, number][] = [[t("co.decMix"), c.mix], [t("co.decTaxa"), c.taxa], [t("co.decInter"), c.interacao]];
        const dentro = Math.abs(c.taxa) >= Math.abs(c.mix) + Math.abs(c.interacao);
        const mostraRet = d.niveis!.some((n) => (n.n_de ?? 0) >= 30 || (n.n_para ?? 0) >= 30);   // perfis com menos de 30 pessoas nao mostram retorno
        return (
          <>
            <div className="dec-controles">
              <label>{t("co.decDe")}
                <select value={d.de} onChange={(e) => { setDe(e.target.value); setPara(d.para!); }}>
                  {d.meses.map((m) => <option key={m.mes} value={m.mes}>{mesAno(m.mes)}</option>)}
                </select></label>
              <label>{t("co.decPara")}
                <select value={d.para} onChange={(e) => { setPara(e.target.value); setDe(d.de!); }}>
                  {d.meses.map((m) => <option key={m.mes} value={m.mes}>{mesAno(m.mes)}</option>)}
                </select></label>
            </div>
            <p className="dica"><R texto={t("co.decResumo", { de: mesAno(d.de!), para: mesAno(d.para!), a: pct(d.taxa_de), b: pct(d.taxa_para), delta: pp(d.delta_pp!) })} /></p>
            {itens.map(([nome, v]) => (
              <div className="dec-linha" key={nome}>
                <div className="topo-l"><span>{nome}</span><b style={{ color: v < 0 ? "var(--erro)" : "var(--acento-texto)" }}>{pp(v)}</b></div>
                <div className="dec-trilho" aria-hidden="true">
                  <div className="dec-barra" style={{ background: v < 0 ? "var(--erro)" : "var(--roxo)", [v < 0 ? "right" : "left"]: "50%", width: `${(Math.abs(v) / escala) * 50}%` }} />
                </div>
              </div>
            ))}
            <p><strong>{t(Math.abs(d.delta_pp!) < 2 ? "co.decLeituraPequena" : dentro ? "co.decLeituraTaxa" : "co.decLeituraMix")}</strong></p>
            <p className="dica"><R texto={t("co.decExplica", { delta: pp(d.delta_pp!) })} /></p>
            {Math.min(d.n_de ?? 0, d.n_para ?? 0) < 300 && <p className="aviso alerta">{t("co.decAmostra", { a: num(d.n_de), b: num(d.n_para) })}</p>}
            <div className="dec-detalhe">
              <p className="dec-detalhe-titulo">{t("co.decNiveis")}</p>
              <div className="tabela-rolagem">
              <table className="tabela tabela-compacta">
                <thead><tr><th>{t("co.decPerfil")}</th><th className="num">{t("co.decPeso", { m: mesAno(d.de!) })}</th><th className="num">{t("co.decPeso", { m: mesAno(d.para!) })}</th>{mostraRet && <><th className="num">{t("co.decRet", { m: mesAno(d.de!) })}</th><th className="num">{t("co.decRet", { m: mesAno(d.para!) })}</th></>}</tr></thead>
                <tbody>
                  {d.niveis!.map((n) => (
                    <tr key={n.nivel}><td>{tNivel(n.nivel, idioma)}</td><td className="num">{pct(n.peso_de)}</td><td className="num">{pct(n.peso_para)}</td>
                      {mostraRet && <><td className="num">{(n.n_de ?? 0) >= 30 ? <>{pct(n.taxa_de)}<small className="n-menor">n={num(n.n_de)}</small></> : <small className="n-menor" title={t("co.decPequenoDica")}>{t("co.decPequeno")}</small>}</td><td className="num">{(n.n_para ?? 0) >= 30 ? <>{pct(n.taxa_para)}<small className="n-menor">n={num(n.n_para)}</small></> : <small className="n-menor" title={t("co.decPequenoDica")}>{t("co.decPequeno")}</small>}</td></>}
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
              <p className="dica" style={{ marginTop: "0.4rem" }}>{t(mostraRet ? "co.decPequenoNota" : "co.decNenhum")}</p>
            </div>
          </>
        );
      })()}
    </div>
  );
}


/* ---------------- Cartao de indicador (KPI) e cabecalho de pagina, no mesmo desenho do projeto de referencia ---------------- */
export function Kpi({ rotulo, valor, delta, dica, defId }: { rotulo: string; valor: string; delta?: string; dica?: string; defId?: string }) {
  return (
    <div className="kpi">
      <p className="kpi-rot">{rotulo} {defId && <Definicao id={defId} />}</p>
      <p className="kpi-val">{valor}</p>
      {delta && <p className="kpi-delta">{delta}</p>}
      {dica && <p className="kpi-dica">{dica}</p>}
    </div>
  );
}

export function CabecalhoPagina({ eyebrow, titulo, destaque, desc }: { eyebrow: string; titulo: string; destaque: string; desc: string }) {
  return (
    <div className="cab-pagina">
      <p className="cab-eyebrow">{eyebrow}</p>
      <h1>{titulo} <span>{destaque}</span></h1>
      <p className="cab-desc">{desc}</p>
    </div>
  );
}

/* ---------------- Comparacao entre paises: o pais selecionado frente aos maiores e a media geral ---------------- */

/** Rotulo do eixo: posicao (ranking pela estimativa), nome e bandeira do pais; o selecionado vai em destaque. */
/** Em tela estreita o grafico de barras da lugar a uma lista (posicao, bandeira, nome, taxa e uma barra fina com a margem de erro). */
function useEstreito(px: number) {
  const [e, setE] = useState(false);
  useEffect(() => {
    const m = window.matchMedia(`(max-width: ${px}px)`);
    const f = () => setE(m.matches);
    f();
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, [px]);
  return e;
}

function ListaPaises({ linhas, pais, geral, topo }: { linhas: { pais: string; iso2: string | null; nome: string; taxa: number; erro: number[]; robusto: boolean }[]; pais: string; geral: number; topo: number }) {
  const { t } = useI18n();
  const x = (v: number) => `${Math.min(100, Math.max(0, (v / topo) * 100))}%`;
  return (
    <ol className="comp-lista" aria-label={t("comp.aria")}>
      {linhas.map((l, i) => {
        if (l.pais === "__sep__") return <li key="sep" className="comp-divisa">{t("comp.divisa", { n: num(MIN_POSICAO) })}</li>;
        const B = bandeiraDe(l.iso2);
        return (
          <li key={l.pais} className={`${l.pais === pais ? "sel" : ""} ${l.robusto ? "" : "peq"}`}>
            <div className="comp-lin">
              <span className="pos">{l.robusto ? `${i + 1}º` : "·"}</span>
              {B ? <B className="bandeira" aria-hidden={true} /> : <span className="bandeira" />}
              <span className="nm">{l.nome}</span>
              <b>{pct(l.taxa / 100)}</b>
            </div>
            <div className="comp-trilho" aria-hidden="true">
              <i className="barra" style={{ width: x(l.taxa) }} />
              <i className="ic" style={{ left: x(l.taxa - l.erro[0]), width: `calc(${x(l.taxa + l.erro[1])} - ${x(l.taxa - l.erro[0])})` }} />
              <i className="media" style={{ left: x(geral) }} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** Abaixo disso o intervalo e largo demais para dar posicao: o pais aparece na lista, sem numero. */
const MIN_POSICAO = 1000;

function TickPais({ x, y, nome, linhas, pais }: { x: number; y: number; nome: string; linhas: { pais: string; nome: string; iso2: string | null; robusto: boolean }[]; pais: string }) {
  if (nome === "__sep__") return null;
  const i = linhas.findIndex((l) => l.nome === nome);
  const l = linhas[i];
  const B = bandeiraDe(l?.iso2);
  const sel = l?.pais === pais;
  const cor = sel ? "var(--texto)" : "var(--texto-suave)";
  return (
    <g>
      <text x={x - 192} y={y} dy={4} textAnchor="start" fontSize={12} fill="var(--texto-mudo)" style={{ fontVariantNumeric: "tabular-nums" }}>{l?.robusto ? `${i + 1}º` : "·"}</text>
      <text x={x - 30} y={y} dy={4} textAnchor="end" fontSize={12} fontWeight={sel ? 700 : 400} fill={cor}>{nome}</text>
      {B ? <B x={x - 24} y={y - 7} width={20} height={14} /> : null}
    </g>
  );
}

export function ComparacaoPaises({ dados, pais }: { dados: Comparacao; pais: string }) {
  const { t, idioma } = useI18n();
  const { paises } = useApp();
  const info = new Map(paises.map((p) => [p.pais, p]));
  const nome = (c: string) => { const p = info.get(c); return p ? nomePais(p, idioma, t("pais.desconhecido")) : c; };
  const geral = dados.geral;
  // lista FIXA: todos os paises com amostra minima, na mesma ordem para qualquer pais selecionado (so o destaque muda)
  const lista = dados.paises.filter((p) => p.pais !== "Desconhecido");
  const sel = lista.find((p) => p.pais === pais);
  const linhas = lista.map((p) => ({
    pais: p.pais, iso2: info.get(p.pais)?.iso2 ?? null, nome: nome(p.pais), taxa: p.taxa * 100, erro: [(p.taxa - p.ic_lo) * 100, (p.ic_hi - p.taxa) * 100], n: p.elegiveis, v: p.voltaram_7d, lo: p.ic_lo, hi: p.ic_hi, robusto: p.elegiveis >= MIN_POSICAO,
  })).sort((a, b) => Number(b.robusto) - Number(a.robusto) || b.taxa - a.taxa);   // primeiro quem tem amostra para ter posicao; depois os demais, sem posicao
  // linha em branco entre quem tem amostra para ter posicao e os demais: a reference line tracejada marca a divisa
  const corte = linhas.findIndex((l) => !l.robusto);
  const SEP = { pais: "__sep__", iso2: null, nome: "__sep__", taxa: 0, erro: [0, 0], n: 0, v: 0, lo: 0, hi: 0, robusto: false };
  const dadosGraf = corte > 0 ? [...linhas.slice(0, corte), SEP, ...linhas.slice(corte)] : linhas;
  const atual = linhas.find((l) => l.pais === pais);
  const dif = atual ? atual.taxa - geral.taxa * 100 : null;
  const max = Math.max(...linhas.map((l) => l.taxa + l.erro[1]), geral.taxa * 100);
  const rolagem = useRef<HTMLDivElement>(null);
  const estreito = useEstreito(640);
  const posicao = linhas.findIndex((l) => l.pais === pais);
  useEffect(() => { if (rolagem.current && posicao >= 0) rolagem.current.scrollTop = Math.max(0, posicao * 30 - 120); }, [pais, posicao]);

  return (
    <div>
      {atual && dif != null && (
        <>
          <p className="comp-resumo"><R texto={t("comp.resumo", { pais: atual.nome, taxa: pct(atual.taxa / 100), geral: pct(geral.taxa), dif: pp(dif) })} /></p>
          <p className="comp-resumo"><R texto={t(atual.hi < geral.taxa ? "comp.sigAbaixo" : atual.lo > geral.taxa ? "comp.sigAcima" : "comp.sigIgual")} /></p>
        </>
      )}
      {!sel && <p className="aviso alerta">{t("comp.semAmostra")}</p>}
      <div className="comp-rolagem" ref={rolagem}>
      {estreito ? <ListaPaises linhas={dadosGraf} pais={pais} geral={geral.taxa * 100} topo={Math.ceil((max + 2) / 5) * 5} /> : (
      <div role="img" className="graf-flex" style={{ minHeight: dadosGraf.length * 30 + 56 }} aria-label={t("comp.aria")}>
        <ResponsiveContainer width="100%" height="100%" minHeight={dadosGraf.length * 30 + 56}>
          <BarChart data={dadosGraf} layout="vertical" margin={{ left: 4, right: 28, top: 22, bottom: 4 }}>
            <defs>
              <pattern id="listras-pais" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="7" height="7" style={{ fill: "color-mix(in srgb, var(--roxo) 12%, var(--superficie))" }} />
                <rect width="3" height="7" style={{ fill: "color-mix(in srgb, var(--roxo) 45%, var(--superficie))" }} />
              </pattern>
            </defs>
            <CartesianGrid stroke="var(--borda)" horizontal={false} />
            <XAxis type="number" unit="%" tick={EIXO} stroke="var(--borda)" tickLine={false} domain={[0, Math.ceil((max + 2) / 5) * 5]} ticks={marcas(Math.ceil((max + 2) / 5) * 5)} />
            <YAxis type="category" dataKey="nome" stroke="var(--borda)" tickLine={false} width={196} interval={0}
              tick={(p: { x: number; y: number; payload: { value: string } }) => <TickPais x={p.x} y={p.y} nome={p.payload.value} linhas={linhas} pais={pais} />} />
            <Tooltip cursor={{ fill: "var(--acento-fundo)" }} content={({ active, payload }) => {
              if (!active || !payload?.length || payload[0].payload.pais === "__sep__") return null;
              const l = payload[0].payload;
              return <Dica linhas={<><strong>{l.nome}</strong><br />{t("grafico.retorno")} <b>{pct(l.taxa / 100)}</b><br />{t("grafico.ic", { lo: pct(l.lo), hi: pct(l.hi) })}<br />{t("grafico.voltaram", { v: num(l.v), n: num(l.n) })}</>} />;
            }} />
            <ReferenceLine x={geral.taxa * 100} stroke="var(--graf-3)" strokeDasharray="5 4" strokeWidth={2}
              label={{ value: t("comp.geral", { v: pct(geral.taxa) }), position: "top", fill: "var(--texto-suave)", fontSize: 12 }} />
            {corte > 0 && <ReferenceLine y="__sep__" stroke="var(--texto-mudo)" strokeDasharray="6 5" strokeWidth={1.5}
              label={{ value: t("comp.divisa", { n: num(MIN_POSICAO) }), position: "insideTopRight", fill: "var(--texto-suave)", fontSize: 12 }} />}
            <Bar dataKey="taxa" radius={[0, 6, 6, 0]}>
              {dadosGraf.map((l) => <Cell key={l.pais} fill={l.pais === "__sep__" ? "transparent" : l.pais === pais ? "var(--graf-1)" : l.pais === "Brazil" ? "color-mix(in srgb, var(--roxo) 62%, var(--superficie))" : l.robusto ? "color-mix(in srgb, var(--roxo) 32%, var(--superficie))" : "url(#listras-pais)"} />)}
              <ErrorBar dataKey="erro" direction="x" stroke="var(--texto-suave)" strokeWidth={1.5} width={5} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>)}
      </div>
      <div className="legenda-graf">
        <span><i style={{ background: "var(--graf-1)" }} />{t("comp.selecionado")}</span>
        {pais !== "Brazil" && <span><i style={{ background: "color-mix(in srgb, var(--roxo) 62%, var(--superficie))" }} />{t("comp.brasil")}</span>}
        <span><i style={{ background: "color-mix(in srgb, var(--roxo) 32%, var(--superficie))" }} />{t("comp.outros")}</span>
        <span><i className="leg-listras" />{t("comp.semPosicao", { n: num(MIN_POSICAO) })}</span>
        <span><i style={{ background: "var(--graf-3)", borderRadius: 2, height: "0.2rem", width: "0.9rem" }} />{t("comp.mediaGeral")}</span>
      </div>
      <p className="dica" style={{ marginTop: "0.6rem" }}><R texto={t("comp.eleg")} /></p>
      <p className="dica" style={{ marginTop: "0.6rem" }}>{t("comp.nota", { min: num(MIN_POSICAO), top: linhas.length, rank: linhas.filter((l) => l.robusto).length, n: num(geral.elegiveis), v: num(geral.voltaram_7d) })}</p>
    </div>
  );
}