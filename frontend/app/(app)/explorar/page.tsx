"use client";
import { useState } from "react";
import { ConcentracaoUso, MapaHora, ModeloTempo, VersoesModelo } from "@/components/AnaliseAmpliada";
import { BarrasTema, CabecalhoPagina, Painel } from "@/components/Graficos";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { R, useI18n } from "@/lib/i18n";
import type { Concentracao, FatorNivel, ModelosTempo, UsoHora } from "@/lib/tipos";

const GRUPOS = ["dispositivo", "sistema", "navegador"] as const;
type Grupo = (typeof GRUPOS)[number];

export default function Explorar() {
  const { pais } = useApp();
  const { t } = useI18n();
  const q = `pais=${encodeURIComponent(pais)}`;
  const hora = useApi<UsoHora>(`/explorar/uso-hora?${q}`);
  const modelos = useApi<ModelosTempo>(`/explorar/modelos?${q}`);
  const conc = useApi<Concentracao>(`/explorar/concentracao?${q}`);
  const [grupo, setGrupo] = useState<Grupo>("dispositivo");
  const disp = useApi<FatorNivel[]>(`/retencao/fatores?${q}&fator=${grupo}`);
  const idi = useApi<FatorNivel[]>(`/retencao/fatores?${q}&fator=idioma_x_navegador`);
  const carregando = <p className="carregando" role="status">{t("comum.carregando")}</p>;
  const vazio = <p className="vazio">{t("ex.semDados")}</p>;
  const erro = hora.erro ?? modelos.erro ?? conc.erro ?? disp.erro ?? idi.erro;
  const rotulo: Record<Grupo, string> = { dispositivo: t("ex.dispDispositivo"), sistema: t("ex.dispSistema"), navegador: t("ex.dispNavegador") };

  return (
    <>
      <CabecalhoPagina eyebrow={t("ex.eyebrow")} titulo={t("ex.h1a")} destaque={t("ex.h1b")} desc={t("ex.desc")} />
      <div className="aviso"><R texto={t("ex.aviso")} /></div>
      {erro && <p className="aviso alerta" role="alert">{t("comum.erro", { erro })}</p>}

      <Painel nota="nt.hora" className="bloco" titulo={t("ex.horaTitulo")} pergunta={t("ex.horaPergunta")}>
        {hora.carregando ? carregando : hora.dados && hora.dados.total > 0 ? <MapaHora dados={hora.dados} /> : vazio}
      </Painel>

      <div className="grade2">
        <Painel nota="nt.modtempo" titulo={t("ex.modTitulo")} pergunta={t("ex.modPergunta")}>
          {modelos.carregando ? carregando : modelos.dados?.meses.length ? <ModeloTempo dados={modelos.dados.meses} /> : vazio}
        </Painel>
        <Painel titulo={t("ex.verTitulo")} pergunta={t("ex.verPergunta")}>
          {modelos.carregando ? carregando : modelos.dados?.versoes.length ? <VersoesModelo dados={modelos.dados.versoes} /> : vazio}
        </Painel>
      </div>

      <Painel className="bloco" titulo={t("ex.conTitulo")} pergunta={t("ex.conPergunta")}>
        {conc.carregando ? carregando : conc.dados ? <ConcentracaoUso dados={conc.dados} /> : vazio}
      </Painel>

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
