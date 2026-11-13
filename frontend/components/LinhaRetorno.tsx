"use client";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dataCurta, dataLonga, mesAno, num, pct } from "@/lib/formato";
import { useI18n } from "@/lib/i18n";
import type { Coorte } from "@/lib/tipos";

type Ponto = { semana: string; rotulo: string; taxa: number | null; faixa: [number, number] | null; c: Coorte };

function Dica({ active, payload, mensal }: { active?: boolean; payload?: { payload: Ponto }[]; mensal?: boolean }) {
  const { t } = useI18n();
  if (!active || !payload?.length) return null;
  const { c } = payload[0].payload;
  return (
    <div className="tip-graf">
      <strong>{mensal ? t("grafico.tituloMes", { d: mesAno(c.semana) }) : t("grafico.titulo", { d: dataLonga(c.semana) })}</strong>
      <p style={{ margin: "0.3rem 0 0" }}>
        {c.taxa == null
          ? t("grafico.pequena", { n: num(c.elegiveis) })
          : <>{t("grafico.retorno")} <b>{pct(c.taxa)}</b><br />{t("grafico.ic", { lo: pct(c.ic_lo), hi: pct(c.ic_hi) })}<br />{t("grafico.voltaram", { v: num(c.voltaram_7d), n: num(c.elegiveis) })}</>}
      </p>
    </div>
  );
}

/** Linha = taxa de retorno por semana; faixa roxa clara = intervalo de confianca de 95%. Semana sem amostra = lacuna. */
export function LinhaRetorno({ coortes, mensal = false }: { coortes: Coorte[]; mensal?: boolean }) {
  const { t } = useI18n();
  const dados: Ponto[] = coortes.map((c) => ({
    semana: c.semana, rotulo: mensal ? mesAno(c.semana) : dataCurta(c.semana), c,
    taxa: c.taxa == null ? null : c.taxa * 100,
    faixa: c.taxa == null ? null : [(c.ic_lo ?? 0) * 100, (c.ic_hi ?? 0) * 100],
  }));
  return (
    <div role="img" aria-label={t("grafico.aria")}>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={dados} margin={{ top: 10, right: 16, bottom: 4, left: 0 }}>
          <defs><linearGradient id="bandaIC" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--graf-1)" stopOpacity={0.35} /><stop offset="100%" stopColor="var(--graf-1)" stopOpacity={0.05} /></linearGradient></defs>
          <CartesianGrid stroke="var(--borda)" vertical={false} />
          <XAxis dataKey="rotulo" tick={{ fontSize: 11, fill: "var(--texto-mudo)" }} stroke="var(--borda)" tickLine={false} minTickGap={28} />
          <YAxis unit="%" domain={[0, (max: number) => Math.min(100, Math.ceil((max + 5) / 10) * 10)]} tick={{ fontSize: 11, fill: "var(--texto-mudo)" }} stroke="var(--borda)" tickLine={false} width={44} />
          <Tooltip content={<Dica mensal={mensal} />} />
          <Area dataKey="faixa" stroke="none" fill="url(#bandaIC)" />
          <Line dataKey="taxa" stroke="var(--graf-1)" strokeWidth={2.5} dot={{ r: 3, fill: "var(--graf-1)" }} activeDot={{ r: 5 }} connectNulls={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
