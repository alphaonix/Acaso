import type { Coorte } from "@/lib/tipos";

/** O retorno esta subindo, caindo ou estavel? Compara a 1a metade dos meses com a 2a (taxas agrupadas) e
 *  diz "estavel" quando a margem de erro (95%, aproximacao normal) da diferenca inclui zero. */
export function tendencia(meses: Coorte[]) {
  const m = meses.filter((x) => x.elegiveis > 0).sort((a, b) => a.semana.localeCompare(b.semana));
  if (m.length < 4) return null;
  const k = Math.floor(m.length / 2), a = m.slice(0, k), b = m.slice(k);
  const soma = (xs: Coorte[]) => ({ n: xs.reduce((s, x) => s + x.elegiveis, 0), v: xs.reduce((s, x) => s + x.voltaram_7d, 0) });
  const A = soma(a), B = soma(b);
  if (A.n < 60 || B.n < 60) return null;
  const p1 = A.v / A.n, p2 = B.v / B.n, d = p2 - p1;
  const se = Math.sqrt((p1 * (1 - p1)) / A.n + (p2 * (1 - p2)) / B.n);
  const lo = d - 1.96 * se, hi = d + 1.96 * se;
  return { p1, p2, d, lo, hi, de1: a[0].semana, de2: a[a.length - 1].semana, para1: b[0].semana, para2: b[b.length - 1].semana,
           sinal: lo > 0 ? ("sobe" as const) : hi < 0 ? ("cai" as const) : ("estavel" as const) };
}