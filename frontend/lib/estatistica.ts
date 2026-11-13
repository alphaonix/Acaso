import type { Efeito } from "@/lib/tipos";

// funcao de erro (Abramowitz-Stegun 7.1.26) para a cauda da normal
function erf(x: number) {
  const s = Math.sign(x), a = Math.abs(x), t = 1 / (1 + 0.3275911 * a);
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-a * a);
  return s * y;
}

/** p-valor aproximado (bicaudal) a partir do efeito e do IC 95%: erro-padrao = largura / (2 x 1,96). */
export function pValor(e: Pick<Efeito, "efeito_pp" | "ic_lo" | "ic_hi">) {
  const se = (e.ic_hi - e.ic_lo) / (2 * 1.96);
  if (!(se > 0)) return 1;
  const z = Math.abs(e.efeito_pp) / se;
  return 1 - erf(z / Math.SQRT2);
}

/** O efeito continua distinguivel de zero depois da correcao de Bonferroni para `m` fatores testados (BDR-004)? */
export const resisteACorrecao = (e: Pick<Efeito, "efeito_pp" | "ic_lo" | "ic_hi">, m: number) => m > 0 && pValor(e) < 0.05 / m;