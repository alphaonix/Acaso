"use client";
import { useRouter } from "next/navigation";
import { useApp } from "@/lib/contexto";
import { R, useI18n } from "@/lib/i18n";
import { tIndicador } from "@/lib/traducao-dados";

/** Tela de abertura (BDR-002): papel do painel, resumo de cada indicador e o que ele nunca mostra. */
export default function Sobre() {
  const { catalogo } = useApp();
  const { t, idioma } = useI18n();
  const router = useRouter();
  function entrar() {
    try { localStorage.setItem("visto_sobre", "1"); } catch { /* sem storage */ }
    router.push("/visao-geral");
  }
  return (
    <>
      <h1>{t("so.titulo")}</h1>
      <p className="pergunta"><R texto={t("so.sub")} /></p>

      <section className="cartao largo">
        <h2>{t("so.servePara")}</h2>
        <p><R texto={t("so.p1")} /></p>
        <ul className="lista-sobre">
          <li><R texto={t("so.l1")} /></li>
          <li><R texto={t("so.l2")} /></li>
          <li><R texto={t("so.l3")} /></li>
          <li><R texto={t("so.l4")} /></li>
        </ul>
      </section>

      <section className="cartao largo">
        <h2>{t("so.indicadores")}</h2>
        <ul className="lista-sobre">
          {catalogo.filter((c) => !["turnos_medios", "uso_gpt4"].includes(c.indicador_id)).map((c) => { const i = tIndicador(c, idioma); return <li key={i.indicador_id}><strong>{i.nome}</strong> ({i.unidade}): {i.pergunta}</li>; })}
        </ul>
        <p className="dica"><R texto={t("so.indicadoresDica")} /></p>
      </section>

      <section className="cartao largo">
        <h2>{t("so.cuidados")}</h2>
        <ul className="lista-sobre">
          <li><R texto={t("so.c1")} /></li>
          <li><R texto={t("so.c2")} /></li>
          <li><R texto={t("so.c3")} /></li>
        </ul>
      </section>

      <section className="cartao largo">
        <h2>{t("so.priv")}</h2>
        <p><R texto={t("so.priv1")} /></p>
        <p><R texto={t("so.priv2")} /></p>
      </section>

      <button className="btn" onClick={entrar}>{t("so.entendi")}</button>
    </>
  );
}
