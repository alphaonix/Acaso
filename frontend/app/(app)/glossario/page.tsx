"use client";
import { CabecalhoPagina, Painel } from "@/components/Graficos";
import { useApi } from "@/lib/api";
import { num, pctFino } from "@/lib/formato";
import { useI18n } from "@/lib/i18n";
import type { Chave } from "@/lib/idiomas/pt";
import type { Qualidade } from "@/lib/tipos";

const DEFINICOES = ["usuario", "retorno", "elegivel", "primeira", "inicio", "fuso", "margem", "pp", "coorte", "alavanca", "indicio", "ab"] as const;

/** Transparencia: definicoes, privacidade e problemas de qualidade encontrados. Formulas e SQL ficam na documentacao. */
export default function Glossario() {
  const { t } = useI18n();
  const q = useApi<Qualidade>("/qualidade");

  return (
    <>
      <CabecalhoPagina eyebrow={t("gl.eyebrow")} titulo={t("gl.h1a")} destaque={t("gl.h1b")} desc={t("gl.desc")} />

      <Painel className="bloco" titulo={t("gl.defTitulo")} pergunta={t("gl.defPergunta")}>
        <dl className="def-lista def-duas">
          {DEFINICOES.map((k) => <div key={k}><dt>{t(`gl.d.${k}.t`)}</dt><dd>{t(`gl.d.${k}.d`)}</dd></div>)}
        </dl>
      </Painel>

      <Painel className="bloco" titulo={t("gl.privTitulo")}>
        <div className="priv-grade priv-tres">
          <div>
            <p className="priv-tit ok">{t("gl.mostra")}</p>
            <ul>{(["gl.m1", "gl.m2", "gl.m3", "gl.m4"] as const).map((k) => <li key={k}>{t(k)}</li>)}</ul>
          </div>
          <div>
            <p className="priv-tit nao">{t("gl.nunca")}</p>
            <ul>{(["gl.n1", "gl.n2", "gl.n3", "gl.n4"] as const).map((k) => <li key={k}>{t(k)}</li>)}</ul>
          </div>
          <div>
            <p className="priv-tit">{t("gl.protTitulo")}</p>
            <ul>{(["gl.p1", "gl.p2", "gl.p3", "gl.p4", "gl.p5"] as const).map((k) => <li key={k}>{t(k)}</li>)}</ul>
          </div>
        </div>
      </Painel>
      <Painel className="bloco" titulo={t("gl.probTitulo")} pergunta={t("gl.probPergunta")}>
        {q.erro && <p className="aviso alerta" role="alert">{t("comum.erro", { erro: q.erro })}</p>}
        <div className="rolagem-x">
          <table className="tabela tabela-q">
            <thead><tr><th>{t("gl.colProblema")}</th><th>{t("gl.colAfetadas")}</th><th>{t("gl.colTratamento")}</th></tr></thead>
            <tbody>
              {(q.dados?.problemas ?? []).map((p) => (
                <tr key={p.codigo}>
                  <td>{t(`gl.q.${p.codigo}.p` as Chave)}{p.escopo === "brasil" && <span className="badge perfil" style={{ marginLeft: 8 }}>{t("gl.soBrasil")}</span>}</td>
                  <td className="afetadas"><b>{num(p.afetadas)}</b> <small>({pctFino(p.total ? p.afetadas / p.total : 0)} {t("gl.deTotal", { n: num(p.total) })})</small></td>
                  <td>{t(`gl.q.${p.codigo}.t` as Chave)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Painel>
    </>
  );
}
