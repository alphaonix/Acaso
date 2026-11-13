"use client";
import { useState } from "react";
import { BarrasTema, CabecalhoPagina, Painel } from "@/components/Graficos";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { R, useI18n } from "@/lib/i18n";
import type { FatorNivel } from "@/lib/tipos";

const GRUPOS = ["dispositivo", "sistema", "navegador"] as const;
type Grupo = (typeof GRUPOS)[number];

export default function Explorar() {
  const { pais } = useApp();
  const { t } = useI18n();
  const q = `pais=${encodeURIComponent(pais)}`;
  const [grupo, setGrupo] = useState<Grupo>("dispositivo");
  const disp = useApi<FatorNivel[]>(`/retencao/fatores?${q}&fator=${grupo}`);
  const idi = useApi<FatorNivel[]>(`/retencao/fatores?${q}&fator=idioma_x_navegador`);
  const carregando = <p className="carregando" role="status">{t("comum.carregando")}</p>;
  const vazio = <p className="vazio">{t("ex.semDados")}</p>;
  const erro = disp.erro ?? idi.erro;
  const rotulo: Record<Grupo, string> = { dispositivo: t("ex.dispDispositivo"), sistema: t("ex.dispSistema"), navegador: t("ex.dispNavegador") };

  return (
    <>
      <CabecalhoPagina eyebrow={t("ex.eyebrow")} titulo={t("ex.h1a")} destaque={t("ex.h1b")} desc={t("ex.desc")} />
      <div className="aviso"><R texto={t("ex.aviso")} /></div>
      {erro && <p className="aviso alerta" role="alert">{t("comum.erro", { erro })}</p>}

      <div className="grade2">
        <Painel nota="ex.dispAviso" titulo={t("ex.dispTitulo")} pergunta={t("ex.dispPergunta")}>
          <div className="pilulas" role="group" aria-label={t("ex.dispGrupo")}>
            {GRUPOS.map((g) => <button key={g} type="button" className="pilula" aria-pressed={grupo === g} onClick={() => setGrupo(g)}>{rotulo[g]}</button>)}
          </div>
          {disp.carregando ? carregando : disp.dados?.some((x) => x.taxa != null) ? <BarrasTema dados={disp.dados} /> : vazio}
        </Painel>
        <Painel nota="ex.idiAviso" titulo={t("ex.idiTitulo")} pergunta={t("ex.idiPergunta")}>
          {idi.carregando ? carregando : idi.dados?.some((x) => x.taxa != null) ? <BarrasTema dados={idi.dados} /> : vazio}
        </Painel>
      </div>
    </>
  );
}
