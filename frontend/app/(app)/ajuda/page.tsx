"use client";
import { CabecalhoPagina, Painel } from "@/components/Graficos";
import { useApi } from "@/lib/api";
import { num, pctFino } from "@/lib/formato";
import { R, useI18n } from "@/lib/i18n";
import { tQa } from "@/lib/traducao-dados";
import type { Chave } from "@/lib/idiomas/pt";
import type { Qualidade } from "@/lib/tipos";

const DEFINICOES = ["usuario", "retorno", "elegivel", "primeira", "inicio", "fuso", "margem", "pp", "coorte", "alavanca", "indicio", "ab"] as const;

/** Ajuda: para que serve o painel, como ler, palavras e regras, privacidade e problemas de qualidade encontrados. */
export default function Ajuda() {
  const { t, idioma } = useI18n();
  const q = useApi<Qualidade>("/qualidade");
  const conferencias = q.dados?.verificacoes ?? [];
  const passaram = conferencias.filter((c) => c.passou).length;

  return (
    <>
      <CabecalhoPagina eyebrow={t("gl.eyebrow")} titulo={t("gl.h1a")} destaque={t("gl.h1b")} desc={t("gl.desc")} />

      <Painel className="bloco" titulo={t("aj.antes")}>
        <p><R texto={t("so.p1")} /></p>
        <ul className="lista-dados">
          {(["so.c1", "so.c2", "so.c3"] as const).map((k) => <li key={k}><R texto={t(k)} /></li>)}
        </ul>
        <p className="dica" style={{ marginTop: "0.6rem" }}><R texto={t("so.indicadoresDica")} /></p>
      </Painel>

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

      {conferencias.length > 0 && (
        <Painel className="bloco" titulo={t("gl.confTitulo")}>
          <p>{t("gl.confResumo", { ok: num(passaram), n: num(conferencias.length) })}</p>
          <details className="detalhe-efeito">
            <summary>{t("gl.confVer")}</summary>
            <div className="rolagem-x">
              <table className="tabela tabela-q">
                <thead><tr><th>{t("gl.conferencias")}</th><th>OK</th></tr></thead>
                <tbody>{conferencias.map((c, i) => <tr key={i}><td>{tQa(c.verificacao, idioma)}</td><td>{c.passou ? "✓" : "✗"}</td></tr>)}</tbody>
              </table>
            </div>
          </details>
          <details className="detalhe-efeito">
            <summary>{t("gl.origemVer")}</summary>
            <p className="dica">{t("gl.origemCaption")}</p>
            <ul>{(q.dados?.lotes ?? []).map((l) => <li key={l.arquivo}><code>{l.arquivo}</code> · {num(l.linhas)} · sha256 {l.sha256.slice(0, 12)}…</li>)}</ul>
          </details>
        </Painel>
      )}
    </>
  );
}
