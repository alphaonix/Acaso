"use client";
import { CurvaRetorno } from "@/components/AnaliseAmpliada";
import { BarrasNovos, CabecalhoPagina, Decomposicao, Kpi, MapaCalor, Painel } from "@/components/Graficos";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { useI18n } from "@/lib/i18n";
import { num, pct } from "@/lib/formato";
import type { Coorte, Curva, PontoCurva } from "@/lib/tipos";

export default function Coortes() {
  const { pais } = useApp();
  const { t } = useI18n();
  const coortes = useApi<Coorte[]>(`/retencao/coortes?pais=${encodeURIComponent(pais)}`);
  const curva = useApi<Curva>(`/retencao/curva?pais=${encodeURIComponent(pais)}`);
  const semanas = coortes.dados ?? [];
  const cartao = (chave: "co.kpi24" | "co.kpi7" | "co.kpi30", p: PontoCurva | null | undefined, id: string, dica: "co.kpiDica" | "co.kpi7Dica") => (
    <Kpi rotulo={t(chave)} defId={id} valor={p ? (p.taxa != null ? pct(p.taxa) : "—") : "…"}
      delta={p && p.taxa != null ? t("co.kpiSub", { lo: pct(p.ic_lo), hi: pct(p.ic_hi), v: num(p.voltaram), n: num(p.usuarios) }) : p ? t("vg.amostraPequena") : ""} dica={t(dica)} />
  );
  return (
    <>
      <CabecalhoPagina eyebrow={t("co.eyebrow")} titulo={t("co.h1a")} destaque={t("co.h1b")} desc={t("co.desc")} />
      {coortes.erro && <p className="aviso alerta" role="alert">{t("comum.erro", { erro: coortes.erro })}</p>}

      <div className="kpis kpis3">
        {cartao("co.kpi24", curva.dados?.voltou_24h, "voltou_24h", "co.kpiDica")}
        {cartao("co.kpi7", curva.dados?.voltou_7d, "retorno_7d", "co.kpi7Dica")}
        {cartao("co.kpi30", curva.dados?.voltou_30d, "voltou_30d", "co.kpiDica")}
      </div>
      <Painel nota="nt.curva" className="bloco" titulo={t("co.curvaTitulo")} pergunta={t("co.curvaPergunta")}>
        {curva.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : curva.dados ? <CurvaRetorno curva={curva.dados} /> : <p className="vazio">{t("vg.semDados")}</p>}
      </Painel>

      <div className="grade3 topo">
        <div className="pilha">
          <Painel nota="nt.novos" titulo={t("co.novosTitulo")} pergunta={t("co.novosPergunta")}>
            {coortes.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : semanas.length ? <BarrasNovos coortes={semanas} /> : <p className="vazio">{t("vg.semDados")}</p>}
          </Painel>
          <Painel nota="nt.calor" tipo="alerta" titulo={t("co.calorTitulo")} pergunta={t("co.calorPergunta")}>
            {semanas.length ? <MapaCalor coortes={semanas} /> : <p className="vazio">{t("vg.semDados")}</p>}
          </Painel>
        </div>
        <Painel nota="nt.decomp" titulo={t("co.decTitulo")} pergunta={t("co.decPergunta")}>
          <Decomposicao pais={pais} />
        </Painel>
      </div>
    </>
  );
}