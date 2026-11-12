"use client";
import { AreaUso, BarrasTema, CabecalhoPagina, ComparacaoPaises, Kpi, Painel, RoscaModelo } from "@/components/Graficos";
import { LinhaRetorno } from "@/components/LinhaRetorno";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { dataLonga, dec, num, pct } from "@/lib/formato";
import { R, useI18n } from "@/lib/i18n";
import { nomePais } from "@/lib/pais";
import type { Comparacao, Coorte, FatorNivel, Resumo, Uso } from "@/lib/tipos";

export default function VisaoGeral() {
  const { pais, paisAtual } = useApp();
  const { t, idioma } = useI18n();
  const q = `pais=${encodeURIComponent(pais)}`;
  const resumo = useApi<Resumo>(`/retencao/resumo?${q}`);
  const coortes = useApi<Coorte[]>(`/retencao/coortes?${q}`);
  const modelos = useApi<FatorNivel[]>(`/retencao/fatores?${q}&fator=modelo`);
  const temas = useApi<FatorNivel[]>(`/retencao/fatores?${q}&fator=tema`);
  const uso = useApi<Uso[]>(`/uso/diario?${q}`);
  const comp = useApi<Comparacao>("/retencao/comparacao");
  const r = resumo.dados;
  const semanas = coortes.dados ?? [];
  const pequenas = semanas.filter((c) => c.amostra_pequena).length;

  return (
    <>
      <CabecalhoPagina eyebrow={t("vg.eyebrow")} titulo={t("vg.h1a")} destaque={t("vg.h1b")} desc={t("vg.desc")} />

      {paisAtual?.fuso_aproximado && <p className="aviso alerta"><R texto={t("vg.fuso", { fuso: paisAtual.fuso })} /></p>}
      {(resumo.erro || coortes.erro) && <p className="aviso alerta" role="alert">{t("comum.erro", { erro: resumo.erro ?? coortes.erro ?? "" })}</p>}

      <div className="kpis">
        <Kpi rotulo={t("vg.novos")} defId="usuarios_novos" valor={r ? num(r.novos) : "…"}
          delta={r?.primeira_semana && r.ultima_semana ? t("vg.periodo", { a: dataLonga(r.primeira_semana), b: dataLonga(r.ultima_semana) }) : ""} dica={t("vg.novosDica")} />
        <Kpi rotulo={t("vg.retorno")} defId="retorno_7d" valor={r ? pct(r.taxa) : "…"}
          delta={r && r.taxa != null ? t("vg.retornoSub", { lo: pct(r.ic_lo), hi: pct(r.ic_hi), v: num(r.voltaram_7d), n: num(r.elegiveis) }) : r ? t("vg.amostraPequena") : ""} dica={t("vg.retornoDica")} />
        <Kpi rotulo={t("vg.conversas")} defId="conversas" valor={r ? num(r.conversas) : "…"}
          delta={r && r.novos ? t("vg.conversasSub", { n: dec(r.conversas / r.novos) }) : ""} dica={t("vg.conversasDica")} />
        <Kpi rotulo={t("vg.turnos")} defId="turnos_medios" valor={r ? dec(r.turnos_medios) : "…"}
          delta={r ? t("vg.turnosSub", { m: dec(r.turnos_mediana) }) : ""} dica={t("vg.turnosDica")} />
        <Kpi rotulo={t("vg.recusa")} defId="recusa_primeira_conversa" valor={r ? (r.recusa_taxa != null ? pct(r.recusa_taxa) : "—") : "…"}
          delta={r ? (r.recusa_taxa != null ? t("vg.recusaSub", { lo: pct(r.recusa_ic_lo), hi: pct(r.recusa_ic_hi), v: num(r.recusa_usuarios), n: num(r.recusa_elegiveis) }) : t("vg.recusaSemTexto")) : ""} dica={t("vg.recusaDica")} />
        <Kpi rotulo={t("vg.gpt4")} defId="uso_gpt4" valor={r ? pct(r.pct_gpt4) : "…"} delta={t("vg.gpt4Sub")} dica={t("vg.gpt4Dica")} />
      </div>

      <div className="grade3">
        <Painel titulo={t("vg.graficoTitulo")} pergunta={t("vg.graficoDica")}>
          {coortes.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : semanas.length === 0 ? <p className="vazio">{t("vg.semDados")}</p> : <LinhaRetorno coortes={semanas} />}
          {pequenas > 0 && <p className="dica" style={{ marginTop: "0.6rem" }}>{t("vg.pequenas", { n: pequenas, total: semanas.length })}</p>}
        </Painel>
        <Painel titulo={t("vg.modeloTitulo")} pergunta={t("vg.modeloPergunta")}>
          {modelos.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : (modelos.dados?.length ? <RoscaModelo dados={modelos.dados} /> : <p className="vazio">{t("vg.semDados")}</p>)}
        </Painel>
      </div>

      <div className="grade2">
        <Painel titulo={t("vg.usoTitulo")} pergunta={t("vg.usoPergunta")}>
          {uso.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : (uso.dados?.length ? <AreaUso dados={uso.dados} /> : <p className="vazio">{t("vg.semDados")}</p>)}
        </Painel>
        <Painel titulo={t("vg.temaTitulo")} pergunta={t("vg.temaPergunta")}>
          {temas.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : (temas.dados?.some((x) => x.taxa != null) ? <BarrasTema dados={temas.dados} /> : <p className="vazio">{t("vg.temaSemTexto")}</p>)}
        </Painel>
      </div>

      <Painel className="bloco" titulo={t("comp.titulo", { pais: paisAtual ? nomePais(paisAtual, idioma, t("pais.desconhecido")) : pais })} pergunta={t("comp.pergunta")}>
        {comp.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : comp.dados ? <ComparacaoPaises dados={comp.dados} pais={pais} /> : <p className="vazio">{t("vg.semDados")}</p>}
      </Painel>
    </>
  );
}