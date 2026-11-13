"use client";
import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, ErrorBar, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Kpi } from "@/components/Graficos";
import { R, useI18n } from "@/lib/i18n";
import { dec, mesAno, num, pct, pp } from "@/lib/formato";
import type { Concentracao, Curva, Estrato, FamiliaModelo, ModelosTempo, UsoHora, VersaoModelo } from "@/lib/tipos";

const EIXO = { fontSize: 12, fill: "var(--texto-mudo)" };
const marcas = (topo: number) => { const passo = topo > 40 ? 10 : 5; return Array.from({ length: Math.floor(topo / passo) + 1 }, (_, i) => i * passo); };
const Dica = ({ linhas }: { linhas: React.ReactNode }) => <div className="tip-graf">{linhas}</div>;

/* ---------------- Curva de retorno: % acumulada de quem voltou em ate d dias ---------------- */
export function CurvaRetorno({ curva }: { curva: Curva }) {
  const { t } = useI18n();
  const pts = curva.pontos.filter((p) => p.taxa != null)
    .map((p) => ({ dias: p.dias, taxa: p.taxa! * 100, faixa: [p.ic_lo! * 100, p.ic_hi! * 100], v: p.voltaram, n: p.usuarios, lo: p.ic_lo, hi: p.ic_hi }));
  if (!pts.length) return <p className="vazio">{t("co.curvaSem")}</p>;
  const topo = Math.ceil((Math.max(...pts.map((p) => p.faixa[1])) + 2) / 5) * 5;
  const v7 = curva.voltou_7d, v30 = curva.voltou_30d;
  return (
    <div>
      <div role="img" className="graf-flex" style={{ minHeight: 280 }} aria-label={t("co.curvaAria")}>
        <ResponsiveContainer width="100%" height="100%" minHeight={280}>
          <ComposedChart data={pts} margin={{ top: 18, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--borda)" vertical={false} />
            <XAxis dataKey="dias" type="number" domain={[0, 30]} ticks={[0, 1, 3, 7, 14, 21, 30]} tick={EIXO} stroke="var(--borda)" tickLine={false} />
            <YAxis unit="%" tick={EIXO} stroke="var(--borda)" tickLine={false} width={44} domain={[0, topo]} ticks={marcas(topo)} />
            <Tooltip content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload;
              return <Dica linhas={<><strong>{t("co.curvaDias", { d: dec(p.dias) })}</strong><br />{t("grafico.retorno")} <b>{pct(p.taxa / 100)}</b><br />{t("grafico.ic", { lo: pct(p.lo), hi: pct(p.hi) })}<br />{t("grafico.voltaram", { v: num(p.v), n: num(p.n) })}</>} />;
            }} />
            <ReferenceLine x={1} stroke="var(--graf-3)" strokeDasharray="4 4" label={{ value: "24 h", position: "top", fill: "var(--texto-suave)", fontSize: 12 }} />
            <ReferenceLine x={7} stroke="var(--graf-3)" strokeDasharray="4 4" label={{ value: "7 d", position: "top", fill: "var(--texto-suave)", fontSize: 12 }} />
            <Area dataKey="faixa" stroke="none" fill="var(--graf-1)" fillOpacity={0.16} isAnimationActive={false} />
            <Line dataKey="taxa" stroke="var(--graf-1)" strokeWidth={2.5} dot={{ r: 3.5, fill: "var(--graf-1)" }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="dica" style={{ textAlign: "center" }}>{t("co.curvaEixo")}</p>
      {v7 && v30 && v30.voltaram > 0 && <p className="dica" style={{ marginTop: "0.4rem" }}><R texto={t("co.curvaNota", { n: num(v30.usuarios), p: pct(v7.voltaram / v30.voltaram) })} /></p>}
    </div>
  );
}

/* ---------------- Saudacao e recusa dentro de cada familia de modelo ---------------- */
export function EstratosModelo({ dados }: { dados: Estrato[] }) {
  const { t, idioma } = useI18n();
  const ordem = { saudacao: 0, recusa: 1 } as const;
  const linhas = [...dados].sort((a, b) => ordem[a.fator] - ordem[b.fator] || a.familia.localeCompare(b.familia));
  const difs = linhas.flatMap((l) => (l.diferenca ? [l.diferenca.ic_lo, l.diferenca.ic_hi] : []));
  if (!linhas.length) return <p className="vazio">{t("fa.estSem2")}</p>;
  const lo = Math.min(-5, ...difs) - 2, hi = Math.max(5, ...difs) + 2;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div>
      <div className="tabela-rolagem">
        <table className="tabela">
          <thead><tr><th>{t("fa.estFator")}</th><th>{t("fa.estModelo")}</th><th className="num">{t("fa.estCom")}</th><th className="num">{t("fa.estSem")}</th><th>{t("fa.estDif")}</th></tr></thead>
          <tbody>
            {linhas.map((l) => {
              const d = l.diferenca;
              const cruza = d ? d.ic_lo <= 0 && d.ic_hi >= 0 : false;
              return (
                <tr key={`${l.fator}-${l.familia}`}>
                  <td>{t(l.fator === "saudacao" ? "fa.estSaudacao" : "fa.estRecusa")}</td>
                  <td><b>{l.familia}</b></td>
                  <td className="num">{l.tratado ? `${pct(l.tratado.taxa)} (n=${num(l.tratado.elegiveis)})` : "—"}</td>
                  <td className="num">{l.comparacao ? `${pct(l.comparacao.taxa)} (n=${num(l.comparacao.elegiveis)})` : "—"}</td>
                  <td>
                    {d ? (
                      <div className="est-dif">
                        <span><b style={{ color: cruza ? "var(--texto-suave)" : "var(--erro)" }}>{pp(d.pp)}</b> <small>[{pp(d.ic_lo)}; {pp(d.ic_hi)}]{cruza ? ` · ${t("fa.estZero")}` : ""}</small></span>
                        <div className="est-trilho" aria-hidden="true">
                          <i className="est-zero" style={{ left: x(0) }} />
                          <i className="est-faixa" style={{ left: x(d.ic_lo), width: `calc(${x(d.ic_hi)} - ${x(d.ic_lo)})`, background: cruza ? "var(--graf-neutro)" : "var(--erro)" }} />
                          <i className="est-ponto" style={{ left: x(d.pp), background: cruza ? "var(--texto-suave)" : "var(--erro)" }} />
                        </div>
                      </div>
                    ) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="dica" style={{ marginTop: "0.6rem" }}><R texto={t("fa.estNota")} /></p>
    </div>
  );
}

/* ---------------- Quando usam: mapa de calor dia da semana x hora ---------------- */

/** Compara cada faixa com o que se esperaria se o uso fosse igual em todas as horas da semana
 *  (expediente seg-sex 9h-18h = 45/168 das horas; madrugada 22h-6h = 8/24; fim de semana = 2/7). */
export function faixasHora(d: UsoHora) {
  const soma = (f: (c: UsoHora["celulas"][number]) => boolean) => d.celulas.filter(f).reduce((a, c) => a + c.conversas, 0);
  const tot = d.total || 1;
  const porHora = Array.from({ length: 24 }, (_, h) => soma((c) => c.hora === h));
  const faixa = (obs: number, esp: number) => ({ obs, esp, juizo: (obs / esp > 1.1 ? "acima" : obs / esp < 0.9 ? "abaixo" : "igual") as "acima" | "abaixo" | "igual" });
  return {
    exp: faixa(soma((c) => c.dia_semana <= 5 && c.hora >= 9 && c.hora < 18) / tot, 45 / 168),
    mad: faixa(soma((c) => c.hora >= 22 || c.hora < 6) / tot, 8 / 24),
    fim: faixa(soma((c) => c.dia_semana >= 6) / tot, 2 / 7),
    pico: porHora.indexOf(Math.max(...porHora)),
  };
}
export function MapaHora({ dados }: { dados: UsoHora }) {
  const { t } = useI18n();
  const por = new Map(dados.celulas.map((c) => [`${c.dia_semana}-${c.hora}`, c.conversas]));
  const max = Math.max(1, ...dados.celulas.map((c) => c.conversas));
  const dias = [1, 2, 3, 4, 5, 6, 7] as const;
  return (
    <div>
      <div className="hora-mapa" role="img" aria-label={t("ex.horaAria")}>
        <span />
        {Array.from({ length: 24 }, (_, h) => <small key={h} className="hora-cab">{h % 3 === 0 ? h : ""}</small>)}
        {dias.map((d) => (
          <div key={d} className="hora-linha">
            <small className="hora-dia">{t(`ex.d${d}` as "ex.d1")}</small>
            {Array.from({ length: 24 }, (_, h) => {
              const n = por.get(`${d}-${h}`) ?? 0;
              const f = n / max;
              return <i key={h} className="hora-celula" title={t("ex.horaCel", { dia: t(`ex.d${d}` as "ex.d1"), h, n: num(n), p: pct(dados.total ? n / dados.total : 0) })}
                style={{ background: n === 0 ? "var(--borda-suave)" : `color-mix(in srgb, var(--roxo) ${Math.round(10 + f * 85)}%, var(--superficie))` }} />;
            })}
          </div>
        ))}
      </div>
      <div className="legenda-graf">
        <span>{t("ex.horaMenos")}</span>
        <span className="hora-escala" aria-hidden="true" />
        <span>{t("ex.horaMais")}</span>
      </div>
      {dados.total > 0 && (() => {
        const f = faixasHora(dados);
        const j = (x: { juizo: "acima" | "abaixo" | "igual" }) => t(x.juizo === "acima" ? "ex.acima" : x.juizo === "abaixo" ? "ex.abaixo" : "ex.igual");
        return <p className="dica" style={{ marginTop: "0.6rem" }}><R texto={t("ex.horaResumo", { a: pct(f.exp.obs), ea: pct(f.exp.esp), ja: j(f.exp), b: pct(f.mad.obs), eb: pct(f.mad.esp), jb: j(f.mad), c: pct(f.fim.obs), ec: pct(f.fim.esp), jc: j(f.fim), pico: f.pico })} /> {t("ex.horaFuso", { fuso: dados.fuso })} {dados.fuso_aproximado ? t("ex.horaAprox") : ""}</p>;
      })()}
    </div>
  );
}

/* ---------------- Modelo no tempo: % de conversas com GPT-4 por mes ---------------- */
export function ModeloTempo({ dados }: { dados: ModelosTempo["meses"] }) {
  const { t } = useI18n();
  const linhas = dados.map((m) => ({ mes: m.mes, conversas: m.conversas, g: m.conversas_gpt4, p: m.conversas ? (m.conversas_gpt4 / m.conversas) * 100 : 0 }));
  return (
    <div>
      <div role="img" className="graf-flex" style={{ minHeight: 260 }} aria-label={t("ex.modAria")}>
        <ResponsiveContainer width="100%" height="100%" minHeight={260}>
          <ComposedChart data={linhas} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--borda)" vertical={false} />
            <XAxis dataKey="mes" tickFormatter={mesAno} tick={EIXO} stroke="var(--borda)" tickLine={false} minTickGap={16} />
            <YAxis yAxisId="p" unit="%" domain={[0, 100]} tick={EIXO} stroke="var(--borda)" tickLine={false} width={44} />
            <YAxis yAxisId="c" orientation="right" tick={EIXO} stroke="var(--borda)" tickLine={false} width={44} />
            <Tooltip cursor={{ fill: "var(--acento-fundo)" }} content={({ active, payload }) => active && payload?.length ? (
              <Dica linhas={t("ex.modTip", { mes: mesAno(payload[0].payload.mes), p: pct(payload[0].payload.p / 100), g: num(payload[0].payload.g), n: num(payload[0].payload.conversas) })} />
            ) : null} />
            <Bar yAxisId="c" dataKey="conversas" fill="var(--graf-2)" fillOpacity={0.45} radius={[4, 4, 0, 0]} />
            <Line yAxisId="p" dataKey="p" stroke="var(--graf-1)" strokeWidth={2.5} dot={{ r: 3.5, fill: "var(--graf-1)" }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="legenda-graf">
        <span><i style={{ background: "var(--graf-1)" }} />{t("ex.modGpt4")}</span>
        <span><i style={{ background: "var(--graf-2)", opacity: 0.6 }} />{t("ex.modConversas")}</span>
      </div>
    </div>
  );
}

/* ---------------- Comparacao entre modelos: cartoes por familia, barras por versao e tabela ---------------- */
const COR_FAMILIA = { "GPT-4": "var(--graf-1)", "GPT-3.5": "var(--graf-2)" } as const;

export function CartoesModelos({ familias }: { familias: FamiliaModelo[] }) {
  const { t } = useI18n();
  return (
    <div className="kpis kpis4">
      {familias.flatMap((f) => [
        <Kpi key={`${f.familia}-r`} rotulo={`${f.familia} · ${t("vg.modRetorno")}`} valor={f.retorno.taxa != null ? pct(f.retorno.taxa) : "—"}
          delta={f.retorno.taxa != null ? t("vg.modCardSub", { lo: pct(f.retorno.ic_lo), hi: pct(f.retorno.ic_hi), v: num(f.voltaram_7d), n: num(f.elegiveis) }) : t("vg.modPequena")} />,
        ...(f.recusa ? [<Kpi key={`${f.familia}-c`} rotulo={`${f.familia} · ${t("vg.modRecusa")}`} valor={f.recusa.taxa != null ? pct(f.recusa.taxa) : "—"}
          delta={f.recusa.taxa != null ? t("vg.modCardSubConv", { lo: pct(f.recusa.ic_lo), hi: pct(f.recusa.ic_hi), v: num(f.com_recusa), n: num(f.conversas) }) : t("vg.modPequena")} />] : []),
      ])}
    </div>
  );
}

/** Barras horizontais com IC por versao do modelo, coloridas pela familia. `campo` escolhe retorno ou recusa. */
export function BarrasVersoes({ versoes, campo }: { versoes: VersaoModelo[]; campo: "retorno" | "recusa" }) {
  const { t } = useI18n();
  const linhas = versoes.filter((v) => v[campo].taxa != null).map((v) => {
    const x = v[campo];
    return { nome: v.modelo.replace("gpt-", "").replace("-turbo", "").replace("-preview", ""), familia: v.familia, taxa: x.taxa! * 100, erro: [(x.taxa! - x.ic_lo!) * 100, (x.ic_hi! - x.taxa!) * 100],
      lo: x.ic_lo, hi: x.ic_hi, n: campo === "retorno" ? v.elegiveis : v.conversas_texto, k: campo === "retorno" ? v.voltaram_7d : v.com_recusa, modelo: v.modelo };
  });
  if (!linhas.length) return <p className="vazio">{t("ex.semDados")}</p>;
  const topo = Math.ceil((Math.max(...linhas.map((l) => l.taxa + l.erro[1])) + 2) / 5) * 5;
  return (
    <div>
      <div role="img" className="graf-flex" style={{ minHeight: linhas.length * 40 + 50 }} aria-label={linhas.map((l) => `${l.modelo} ${l.taxa.toFixed(1)}%`).join("; ")}>
        <ResponsiveContainer width="100%" height="100%" minHeight={linhas.length * 40 + 50}>
          <BarChart data={linhas} layout="vertical" margin={{ left: 4, right: 24, top: 4, bottom: 4 }}>
            <CartesianGrid stroke="var(--borda)" horizontal={false} />
            <XAxis type="number" unit="%" tick={EIXO} stroke="var(--borda)" tickLine={false} domain={[0, topo]} ticks={marcas(topo)} />
            <YAxis type="category" dataKey="nome" tick={EIXO} stroke="var(--borda)" tickLine={false} width={96} interval={0} />
            <Tooltip cursor={{ fill: "var(--acento-fundo)" }} content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const l = payload[0].payload;
              return <Dica linhas={<><strong>{l.modelo}</strong><br />{t(campo === "retorno" ? "vg.modRetorno" : "vg.modRecusa")} <b>{pct(l.taxa / 100)}</b><br />{t("grafico.ic", { lo: pct(l.lo), hi: pct(l.hi) })}<br />{t(campo === "retorno" ? "vg.modTipRet" : "vg.modTipRec", { v: num(l.k), n: num(l.n) })}</>} />;
            }} />
            <Bar dataKey="taxa" radius={[0, 6, 6, 0]}>
              {linhas.map((l) => <Cell key={l.modelo} fill={COR_FAMILIA[l.familia]} />)}
              <ErrorBar dataKey="erro" direction="x" stroke="var(--texto-suave)" strokeWidth={1.5} width={5} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="legenda-graf">
        <span><i style={{ background: COR_FAMILIA["GPT-3.5"] }} />GPT-3.5</span>
        <span><i style={{ background: COR_FAMILIA["GPT-4"] }} />GPT-4</span>
      </div>
    </div>
  );
}

/* ---------------- Tabela por versao: retorno e recusa lado a lado ---------------- */
export function VersoesModelo({ dados }: { dados: VersaoModelo[] }) {
  const { t } = useI18n();
  const celula = (x: { taxa: number | null; ic_lo: number | null; ic_hi: number | null }) => x.taxa == null ? <span className="dica">{t("vg.modPequena")}</span> : <span><b>{pct(x.taxa)}</b> <small>[{pct(x.ic_lo)}; {pct(x.ic_hi)}]</small></span>;
  return (
    <div>
      <div className="tabela-rolagem">
        <table className="tabela">
          <thead><tr><th>{t("ex.verModelo")}</th><th className="num">{t("ex.verElegiveis")}</th><th>{t("ex.verRetorno")}</th><th className="num">{t("ex.verConversas")}</th><th>{t("ex.verRecusa")}</th><th className="num">{t("ex.verTam")}</th></tr></thead>
          <tbody>
            {dados.map((d) => (
              <tr key={d.modelo}>
                <td><code>{d.modelo}</code></td>
                <td className="num">{num(d.elegiveis)}</td>
                <td>{celula(d.retorno)}</td>
                <td className="num">{num(d.conversas)}</td>
                <td>{d.recusa_possivel ? celula(d.recusa) : "—"}</td>
                <td className="num">{d.resp_media_chars == null ? "—" : num(d.resp_media_chars)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="dica" style={{ marginTop: "0.6rem" }}>{t("ex.verNota")}</p>
    </div>
  );
}

/* ---------------- Concentracao do uso ---------------- */
export const LIMITE_CONCENTRACAO = 0.25;   // alerta quando as 10 pessoas mais ativas passam de 25% das conversas

export function ConcentracaoUso({ dados }: { dados: Concentracao }) {
  const { t } = useI18n();
  if (!dados.faixas.length || dados.top10_pct == null) return <p className="vazio">{t("ex.semDados")}</p>;
  const linhas = dados.faixas.map((f) => ({ ...f, pessoas: f.pct_pessoas * 100, conversasPct: f.pct_conversas * 100 }));
  return (
    <div>
      {dados.top10_pct >= LIMITE_CONCENTRACAO && <p className="aviso">{t("ex.conAlerta", { x: pct(dados.top10_pct), lim: pct(LIMITE_CONCENTRACAO) })}</p>}
      <p><R texto={t("ex.conResumo", { a: pct(dados.pessoas_1_conversa_pct), b: pct(dados.top10_pct), c: pct(dados.maior_pct) })} /></p>
      <div role="img" className="graf-flex" style={{ minHeight: 250 }} aria-label={t("ex.conAria")}>
        <ResponsiveContainer width="100%" height="100%" minHeight={250}>
          <BarChart data={linhas} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--borda)" vertical={false} />
            <XAxis dataKey="faixa" tick={EIXO} stroke="var(--borda)" tickLine={false} />
            <YAxis unit="%" tick={EIXO} stroke="var(--borda)" tickLine={false} width={44} domain={[0, 100]} ticks={[0, 20, 40, 60, 80, 100]} />
            <Tooltip cursor={{ fill: "var(--acento-fundo)" }} content={({ active, payload }) => active && payload?.length ? (
              <Dica linhas={t("ex.conTip", { faixa: payload[0].payload.faixa, u: num(payload[0].payload.usuarios), pu: pct(payload[0].payload.pct_pessoas), c: num(payload[0].payload.conversas), pc: pct(payload[0].payload.pct_conversas) })} />
            ) : null} />
            <Bar dataKey="pessoas" fill="var(--graf-2)" radius={[5, 5, 0, 0]} />
            <Bar dataKey="conversasPct" fill="var(--graf-1)" radius={[5, 5, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="dica" style={{ textAlign: "center" }}>{t("ex.conEixo")}</p>
      <div className="legenda-graf">
        <span><i style={{ background: "var(--graf-2)" }} />{t("ex.conPessoas")}</span>
        <span><i style={{ background: "var(--graf-1)" }} />{t("ex.conConversas")}</span>
      </div>
      {dados.retorno_com?.taxa != null && dados.retorno_sem_top10?.taxa != null && (
        <p style={{ marginTop: "0.6rem" }}><R texto={t("ex.conRetorno", { a: pct(dados.retorno_com.taxa), va: num(dados.retorno_com.voltaram), ea: num(dados.retorno_com.elegiveis), b: pct(dados.retorno_sem_top10.taxa), vb: num(dados.retorno_sem_top10.voltaram), eb: num(dados.retorno_sem_top10.elegiveis), d: pp((dados.retorno_sem_top10.taxa - dados.retorno_com.taxa) * 100) })} /></p>
      )}
      <p className="dica" style={{ marginTop: "0.6rem" }}>{t("ex.conNota")}</p>
    </div>
  );
}
