"use client";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/lib/contexto";
import { useI18n } from "@/lib/i18n";
import { tIndicador } from "@/lib/traducao-dados";

/** Botao "i" ao lado de cada indicador: nome, definicao, formula, unidade, denominador, periodo, fonte e amostra minima (o catalogo inteiro). Fecha ao clicar fora, ao apertar Esc ou ao abrir outro "i". */
export function Definicao({ id }: { id: string }) {
  const { catalogo } = useApp();
  const { t, idioma } = useI18n();
  const bruto = catalogo.find((i) => i.indicador_id === id);
  const [aberto, setAberto] = useState(false);
  const raiz = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: PointerEvent) => { if (!raiz.current?.contains(e.target as Node)) setAberto(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setAberto(false); };
    document.addEventListener("pointerdown", fora);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", fora); document.removeEventListener("keydown", esc); };
  }, [aberto]);

  if (!bruto) return null;
  const ind = tIndicador(bruto, idioma);
  return (
    <span className="definicao" ref={raiz}>
      <button type="button" className="info" aria-expanded={aberto} aria-label={t("df.como", { nome: ind.nome })} onClick={() => setAberto(!aberto)}>i</button>
      {aberto && (
        <div className="popover" role="region" aria-label={t("df.defDe", { nome: ind.nome })}>
          <strong>{ind.nome}</strong>
          <p>{ind.pergunta}</p>
          <dl>
            <dt>{t("df.formula")}</dt><dd>{ind.formula}</dd>
            <dt>{t("df.unidade")}</dt><dd>{ind.unidade}</dd>
            <dt>{t("df.denominador")}</dt><dd>{ind.denominador}</dd>
            <dt>{t("df.periodo")}</dt><dd>{ind.periodo_referencia}</dd>
            <dt>{t("df.fonte")}</dt><dd>{ind.fonte}</dd>
            <dt>{t("df.amostra")}</dt><dd>{t("df.amostraTxt", { n: ind.amostra_minima })}</dd>
          </dl>
        </div>
      )}
    </span>
  );
}
