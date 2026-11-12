"use client";
import { BarrasNovos, CabecalhoPagina, Decomposicao, MapaCalor, Painel } from "@/components/Graficos";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { useI18n } from "@/lib/i18n";
import type { Coorte } from "@/lib/tipos";

export default function Coortes() {
  const { pais } = useApp();
  const { t } = useI18n();
  const coortes = useApi<Coorte[]>(`/retencao/coortes?pais=${encodeURIComponent(pais)}`);
  const semanas = coortes.dados ?? [];
  return (
    <>
      <CabecalhoPagina eyebrow={t("co.eyebrow")} titulo={t("co.h1a")} destaque={t("co.h1b")} desc={t("co.desc")} />
      {coortes.erro && <p className="aviso alerta" role="alert">{t("comum.erro", { erro: coortes.erro })}</p>}

      <div className="grade3 topo">
        <div className="pilha">
          <Painel titulo={t("co.novosTitulo")} pergunta={t("co.novosPergunta")}>
            {coortes.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : semanas.length ? <BarrasNovos coortes={semanas} /> : <p className="vazio">{t("vg.semDados")}</p>}
          </Painel>
          <Painel titulo={t("co.calorTitulo")} pergunta={t("co.calorPergunta")}>
            {semanas.length ? <MapaCalor coortes={semanas} /> : <p className="vazio">{t("vg.semDados")}</p>}
          </Painel>
        </div>
        <Painel titulo={t("co.decTitulo")} pergunta={t("co.decPergunta")}>
          <Decomposicao pais={pais} />
        </Painel>
      </div>
    </>
  );
}