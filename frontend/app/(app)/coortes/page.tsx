"use client";
import { CurvaRetorno } from "@/components/AnaliseAmpliada";
import { useState } from "react";
import { BarrasNovos, CabecalhoPagina, Decomposicao, MapaCalor, Painel } from "@/components/Graficos";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { useI18n } from "@/lib/i18n";
import type { Coorte, Curva } from "@/lib/tipos";

export default function Coortes() {
  const { pais } = useApp();
  const { t } = useI18n();
  const coortes = useApi<Coorte[]>(`/retencao/coortes?pais=${encodeURIComponent(pais)}`);
  const curva = useApi<Curva>(`/retencao/curva?pais=${encodeURIComponent(pais)}`);
  const meses = useApi<Coorte[]>(`/retencao/meses?pais=${encodeURIComponent(pais)}`);
  const [visao, setVisao] = useState<"semanal" | "mensal">("semanal");
  const semanas = coortes.dados ?? [];
  const mensal = visao === "mensal" && (meses.dados?.length ?? 0) > 0;
  const celulas = mensal ? (meses.dados ?? []) : semanas;
  const carregando = <p className="carregando" role="status">{t("comum.carregando")}</p>;
  return (
    <>
      <CabecalhoPagina eyebrow={t("co.eyebrow")} titulo={t("co.h1a")} destaque={t("co.h1b")} desc={t("co.desc")} />
      {coortes.erro && <p className="aviso alerta" role="alert">{t("comum.erro", { erro: coortes.erro })}</p>}

      <Painel nota="nt.curva" className="bloco" titulo={t("co.curvaTitulo")} pergunta={t("co.curvaPergunta")}>
        {curva.carregando ? carregando : curva.dados ? <CurvaRetorno curva={curva.dados} marcos /> : <p className="vazio">{t("vg.semDados")}</p>}
      </Painel>

      <Painel nota="nt.novos" className="bloco" titulo={t("co.novosTitulo")} pergunta={t("co.novosPergunta")}>
        {coortes.carregando ? carregando : semanas.length ? <BarrasNovos coortes={semanas} /> : <p className="vazio">{t("vg.semDados")}</p>}
      </Painel>

      <Painel nota="nt.calor" className="bloco" titulo={t("co.calorTitulo")} pergunta={t("co.calorPergunta")}>
        <div className="pilulas" role="group" aria-label={t("vg.visaoAria")}>
          {(["semanal", "mensal"] as const).map((k) => <button key={k} type="button" className="pilula" aria-pressed={visao === k} onClick={() => setVisao(k)}>{t(k === "mensal" ? "vg.porMes" : "vg.porSemana")}</button>)}
        </div>
        {coortes.carregando ? carregando : celulas.length ? <MapaCalor coortes={celulas} mensal={mensal} /> : <p className="vazio">{t("vg.semDados")}</p>}
      </Painel>

      <Painel nota="nt.decomp" className="bloco" titulo={t("co.decTitulo")} pergunta={t("co.decPergunta")}>
        <Decomposicao pais={pais} />
      </Painel>
    </>
  );
}