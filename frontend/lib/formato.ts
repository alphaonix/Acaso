/** Formatacao sensivel ao idioma. `definirLocale` e chamado pelo provedor de idioma ANTES de renderizar os filhos. */
let loc = "pt-BR";
export const definirLocale = (l: string) => { loc = l; };

const cache = new Map<string, Intl.NumberFormat | Intl.DateTimeFormat>();
function nf(chave: string, o: Intl.NumberFormatOptions) {
  const k = `n|${loc}|${chave}`;
  let f = cache.get(k) as Intl.NumberFormat | undefined;
  if (!f) { f = new Intl.NumberFormat(loc, o); cache.set(k, f); }
  return f;
}
function df(chave: string, o: Intl.DateTimeFormatOptions) {
  const k = `d|${loc}|${chave}`;
  let f = cache.get(k) as Intl.DateTimeFormat | undefined;
  if (!f) { f = new Intl.DateTimeFormat(loc, { timeZone: "UTC", ...o }); cache.set(k, f); }
  return f;
}
const umaCasa = () => nf("1", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const data = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00Z`);

/** 0,237 -> "23,7%" (pt) ou "23.7%" (en) */
export const pct = (v: number | null | undefined) => (v == null ? "—" : `${umaCasa().format(v * 100)}%`);
/** pontos percentuais com sinal: 8.27 -> "+8,3 pp" */
export const pp = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${umaCasa().format(Math.abs(v))} pp`;
/** percentual com 2 algarismos significativos, para valores muito pequenos (17 de 837.989 = 0,0020%) */
export const pctFino = (v: number) => nf("pf", { style: "percent", maximumSignificantDigits: 2 }).format(v);
export const num = (v: number | null | undefined) => (v == null ? "—" : nf("i", {}).format(v));
export const dec = (v: number) => umaCasa().format(v);
export const dataCurta = (iso: string) => df("c", { day: "2-digit", month: "2-digit", year: "2-digit" }).format(data(iso));
export const mesAno = (iso: string) => df("m", { month: "short", year: "2-digit" }).format(data(iso));
export const dataLonga = (iso: string) => df("l", { day: "2-digit", month: "2-digit", year: "numeric" }).format(data(iso));
