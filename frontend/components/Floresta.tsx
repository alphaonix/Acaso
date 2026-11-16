"use client";
import { dec, num, pp } from "@/lib/formato";
import { useI18n } from "@/lib/i18n";
import { resisteACorrecao } from "@/lib/estatistica";
import { tAjustado, tContraste, tFator, tMetodo } from "@/lib/traducao-dados";
import type { Efeito } from "@/lib/tipos";

/** valor com sinal e uma casa, sem a unidade (a unidade esta no eixo): 8.72 -> "+8,7" */
const sinal = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${dec(Math.abs(v))}`;

/**
 * Efeito de cada fator no retorno, no desenho do projeto de referencia: nome + n, trilho com a barra do IC 95% e o ponto do efeito,
 * valor em pp e o selo da conclusao. A escala e simetrica e ajustada ao maior intervalo.
 */
export function Floresta({ efeitos, total }: { efeitos: Efeito[]; total: number }) {
  const { t, idioma } = useI18n();
  const maximo = Math.max(...efeitos.flatMap((e) => [Math.abs(e.ic_lo), Math.abs(e.ic_hi), Math.abs(e.efeito_pp)]));
  const lim = Math.max(5, Math.ceil(maximo / 5) * 5);
  const pos = (v: number) => ((v + lim) / (2 * lim)) * 100;
  return (
    <div>
      {efeitos.map((e) => {
        const neg = e.efeito_pp < 0;
        const conclusivo = e.ic_lo > 0 || e.ic_hi < 0;
        const resiste = conclusivo && resisteACorrecao(e, total);   // distinguivel de zero mesmo contando os `total` fatores testados
        const fator = tFator(e.fator, idioma);
        const contraste = tContraste(e.contraste, idioma);
        const ic = `${pp(e.ic_lo)} ${t("fl.a")} ${pp(e.ic_hi)}`;
        const resumo = t("fl.resumo", { fator, contraste, efeito: pp(e.efeito_pp), lo: pp(e.ic_lo), hi: pp(e.ic_hi), conclusao: resiste ? t("fl.sigResiste") : conclusivo ? t("fl.sigIndicio") : t("fl.nsig") });
        return (
          <div key={`${e.fator}|${e.contraste}`} className="fl2-linha" role="group" aria-label={resumo}>
            <div className="fl2-nome">
              <span>{fator} <span className={`badge ${e.tipo}`}>{e.tipo === "alavanca" ? t("fl.alavanca") : t("fl.perfil")}</span></span>
              <small>{contraste} · n = {num(e.n)}</small>
            </div>
            <div className="fl2-trilho" title={`${t("fl.efeitoCab")}: ${pp(e.efeito_pp)} (IC 95%: ${ic})`} aria-hidden="true">
              <i className="fl2-zero" />
              <i className={`fl2-ic ${neg ? "neg" : "pos"}`} style={{ left: `${pos(e.ic_lo)}%`, width: `${pos(e.ic_hi) - pos(e.ic_lo)}%` }} />
              <i className={`fl2-ponto ${neg ? "neg" : "pos"}`} style={{ left: `${pos(e.efeito_pp)}%` }} />
            </div>
            <div className={`fl2-val ${neg ? "neg" : "pos"}`}>{sinal(e.efeito_pp)}</div>
            <div className="fl2-sel"><span className={`fl2-selo ${resiste ? "ok" : conclusivo ? "indicio" : "mudo"}`} title={conclusivo && !resiste ? t("fl.indicioDica", { n: total }) : undefined}>{resiste ? t("fl.resiste") : conclusivo ? t("fl.indicio") : t("fl.inconclusivo")}</span></div>
            <details className="detalhe-efeito fl2-det">
              <summary>{t("fl.detalhes")}</summary>
              <dl>
                <dt>{t("fl.efeitoCab")}</dt><dd>{pp(e.efeito_pp)} [{pp(e.ic_lo)}; {pp(e.ic_hi)}]</dd>
                <dt>{t("fl.bruto")}</dt><dd>{pp(e.efeito_bruto_pp)} [{pp(e.bruto_ic_lo)}; {pp(e.bruto_ic_hi)}]</dd>
                <dt>{t("fl.comparados")}</dt><dd>{t("fl.comparadosTxt", { n1: num(e.n_tratados), n0: num(e.n_controle), taxa: dec(e.taxa_controle * 100) })}</dd>
                <dt>{t("fl.parecidos")}</dt><dd>{t("fl.parecidosTxt", { p: dec(e.sobreposicao) })} {e.sobreposicao < 70 ? t("fl.parecidosBaixa") : ""}</dd>
                <dt>{t("fl.robustez")}</dt><dd>{e.e_value_ic <= 1 ? t("fl.robustezZero") : t("fl.robustezTxt", { ev: dec(e.e_value_ic) })}</dd>
                <dt>{t("fl.ajustado")}</dt><dd>{tAjustado(e.ajustado_por, idioma)}</dd>
                <dt>{t("fl.metodo")}</dt><dd>{tMetodo(e.metodo, idioma)}</dd>
                <dt>{t("fl.fonte")}</dt><dd>{t("fl.fonteTxt")}</dd>
              </dl>
            </details>
          </div>
        );
      })}
      <div className="fl2-linha fl2-eixo" aria-hidden="true">
        <span />
        <span className="fl2-eixo-rot"><span>{`−${lim} pp`}</span><span>0</span><span>{`+${lim} pp`}</span></span>
        <span /><span />
      </div>
    </div>
  );
}
