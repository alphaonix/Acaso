"use client";
import { BarrasVersoes, CartoesModelos, ConcentracaoUso, CurvaRetorno, MapaHora, ModeloTempo, VersoesModelo } from "@/components/AnaliseAmpliada";
import { AreaUso, BarrasTema, CabecalhoPagina, ComparacaoPaises, Kpi, Painel, RoscaModelo } from "@/components/Graficos";
import { LinhaRetorno } from "@/components/LinhaRetorno";
import { useApi } from "@/lib/api";
import { useApp } from "@/lib/contexto";
import { dataLonga, dec, num, pct, pp } from "@/lib/formato";
import { R, useI18n } from "@/lib/i18n";
import { nomePais } from "@/lib/pais";
import type { Comparacao, Concentracao, Coorte, Curva, Efeito, FatorNivel, ModelosTempo, Resumo, Uso, UsoHora } from "@/lib/tipos";

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
  const meses = useApi<Coorte[]>(`/retencao/meses?${q}`);
  const curva = useApi<Curva>(`/retencao/curva?${q}`);
  const conc = useApi<Concentracao>(`/explorar/concentracao?${q}`);
  const hora = useApi<UsoHora>(`/explorar/uso-hora?${q}`);
  const modTempo = useApi<ModelosTempo>(`/explorar/modelos?${q}`);
  const efeitos = useApi<Efeito[]>(`/efeitos?${q}`);
  const carregando = <p className="carregando" role="status">{t("comum.carregando")}</p>;
  const c24 = curva.dados?.voltou_24h, c7 = curva.dados?.voltou_7d, c30 = curva.dados?.voltou_30d;
  const ef = (fator: string, inicio?: string) => efeitos.dados?.find((e) => e.fator === fator && (!inicio || e.contraste.startsWith(inicio)));
  const sa = ef("Tema do primeiro pedido", "Saudação"), re = ef("Recusa na primeira resposta");
  const cn = conc.dados;
  const f35 = modTempo.dados?.familias.find((f) => f.familia === "GPT-3.5"), f4 = modTempo.dados?.familias.find((f) => f.familia === "GPT-4");
  const recs = (modTempo.dados?.versoes ?? []).filter((v) => v.recusa.taxa != null).map((v) => v.recusa.taxa as number);
  const r = resumo.dados;
  const semanas = coortes.dados ?? [];
  const pequenas = semanas.filter((c) => c.amostra_pequena).length;
  const mesesOk = (meses.dados ?? []).filter((m) => m.taxa != null).length;
  const usarMeses = semanas.length > 0 && semanas.length - pequenas < 8 && mesesOk >= 3;   // paises pequenos: nenhuma semana alcanca 30 elegiveis

  return (
    <>
      <CabecalhoPagina eyebrow={t("vg.eyebrow")} titulo={t("vg.h1a")} destaque={t("vg.h1b")} desc={t("vg.desc")} />

      {paisAtual?.fuso_aproximado && <p className="aviso"><R texto={t("vg.fuso", { fuso: paisAtual.fuso })} /></p>}
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
        <Kpi rotulo={t("co.kpi24")} defId="voltou_24h" valor={c24 ? pct(c24.taxa) : "…"}
          delta={c24 && c24.taxa != null ? t("vg.kpi24Sub", { v: num(c24.voltaram), n: num(c24.usuarios) }) : ""} dica={t("co.kpiDica")} />
        <Kpi rotulo={t("vg.conc")} defId="concentracao_top10" valor={cn?.top10_pct != null ? pct(cn.top10_pct) : cn ? "—" : "…"}
          delta={cn?.top10_pct != null ? t("vg.concSub") : ""} dica={t("vg.concDica")} />
        <Kpi rotulo={t("vg.gpt4")} defId="uso_gpt4" valor={r ? pct(r.pct_gpt4) : "…"} delta={t("vg.gpt4Sub")} dica={t("vg.gpt4Dica")} />
      </div>

      <Painel className="bloco" titulo={t("vg.destTitulo")} pergunta={t("vg.destPergunta")}>
        <ul className="destaques">
          {c24 && c24.taxa != null && c7 && c30 && c30.voltaram > 0 && <li><R texto={t("vg.dest1", { a: pct(c24.taxa), b: pct(c7.taxa), c: pct(c7.voltaram / c30.voltaram) })} /></li>}
          {sa && <li><R texto={t("vg.dest2", { e: pp(sa.efeito_pp), lo: pp(sa.ic_lo), hi: pp(sa.ic_hi) })} /></li>}
          {re && <li><R texto={t("vg.dest3", { e: pp(re.efeito_pp), lo: pp(re.ic_lo), hi: pp(re.ic_hi) })} /></li>}
          {cn?.top10_pct != null && <li><R texto={t("vg.dest4", { a: pct(cn.top10_pct), b: pct(cn.pessoas_1_conversa_pct) })} /></li>}
          {f4?.retorno.taxa != null && f35?.retorno.taxa != null && f4.recusa?.taxa != null && f35.recusa?.taxa != null && recs.length > 1 && <li><R texto={t("vg.dest6", { a: pct(f4.retorno.taxa), b: pct(f35.retorno.taxa), d: pp((f4.retorno.taxa - f35.retorno.taxa) * 100), c: pct(f4.recusa.taxa), e: pct(f35.recusa.taxa), r1: pct(Math.min(...recs)), r2: pct(Math.max(...recs)) })} /></li>}
          {hora.dados?.pct_expediente != null && <li><R texto={t("vg.dest5", { a: pct(hora.dados.pct_expediente) })} /></li>}
        </ul>
        <p className="dica" style={{ marginTop: "0.8rem" }}>{t("vg.maisExplorar")}</p>
      </Painel>

      <div className="grade3">
        <Painel nota="nt.semanal" titulo={t("vg.graficoTitulo")} pergunta={t("vg.graficoDica")}>
          {coortes.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : semanas.length === 0 ? <p className="vazio">{t("vg.semDados")}</p> : <LinhaRetorno coortes={usarMeses ? (meses.dados ?? []) : semanas} mensal={usarMeses} />}
          {usarMeses ? <p className="dica" style={{ marginTop: "0.6rem" }}><R texto={t("vg.mensalAviso", { n: (meses.dados?.length ?? 0) - mesesOk, total: meses.dados?.length ?? 0 })} /></p>
            : pequenas > 0 && <p className="dica" style={{ marginTop: "0.6rem" }}>{t("vg.pequenas", { n: pequenas, total: semanas.length })}</p>}
        </Painel>
        <Painel nota="nt.rosca" titulo={t("vg.modeloTitulo")} pergunta={t("vg.modeloPergunta")}>
          {modelos.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : (modelos.dados?.length ? <RoscaModelo dados={modelos.dados} /> : <p className="vazio">{t("vg.semDados")}</p>)}
        </Painel>
      </div>

      <Painel nota="vg.modNota" className="bloco" titulo={t("vg.modComparTitulo")} pergunta={t("vg.modComparPergunta")}>
        {modTempo.carregando ? carregando : modTempo.dados?.familias.length ? (
          <>
            <CartoesModelos familias={modTempo.dados.familias} />
            <div className="grade2">
              <div><h3 className="sub-titulo">{t("vg.modRetornoTitulo")}</h3><BarrasVersoes versoes={modTempo.dados.versoes} campo="retorno" /></div>
              <div><h3 className="sub-titulo">{t("vg.modRecusaTitulo")}</h3>{modTempo.dados.versoes.some((v) => v.recusa_possivel) ? <BarrasVersoes versoes={modTempo.dados.versoes} campo="recusa" /> : <p className="vazio"><R texto={t("vg.modSemTexto")} /></p>}</div>
            </div>
            {modTempo.dados.versoes.length > 0 && <VersoesModelo dados={modTempo.dados.versoes} />}
          </>
        ) : <p className="vazio">{t("vg.semDados")}</p>}
      </Painel>

      <div className="grade2">
        <Painel nota="nt.curva" titulo={t("vg.curvaTitulo")} pergunta={t("co.curvaPergunta")}>
          {curva.carregando ? carregando : curva.dados ? <CurvaRetorno curva={curva.dados} /> : <p className="vazio">{t("vg.semDados")}</p>}
        </Painel>
        <Painel nota="nt.hora" titulo={t("vg.horaTitulo")} pergunta={t("ex.horaPergunta")}>
          {hora.carregando ? carregando : hora.dados && hora.dados.total > 0 ? <MapaHora dados={hora.dados} /> : <p className="vazio">{t("vg.semDados")}</p>}
        </Painel>
      </div>

      <div className="grade2">
        <Painel nota="nt.uso" titulo={t("vg.usoTitulo")} pergunta={t("vg.usoPergunta")}>
          {uso.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : (uso.dados?.length ? <AreaUso dados={uso.dados} /> : <p className="vazio">{t("vg.semDados")}</p>)}
        </Painel>
        <Painel nota="nt.tema" titulo={t("vg.temaTitulo")} pergunta={t("vg.temaPergunta")}>
          {temas.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : (temas.dados?.some((x) => x.taxa != null) ? <BarrasTema dados={temas.dados} /> : <p className="vazio"><R texto={t("vg.temaSemTexto")} /></p>)}
        </Painel>
      </div>

      <div className="grade2">
        <Painel nota="nt.modtempo" titulo={t("vg.modTitulo2")} pergunta={t("ex.modPergunta")}>
          {modTempo.carregando ? carregando : modTempo.dados?.meses.length ? <ModeloTempo dados={modTempo.dados.meses} /> : <p className="vazio">{t("vg.semDados")}</p>}
        </Painel>
        <Painel titulo={t("vg.conTitulo2")} pergunta={t("ex.conPergunta")}>
          {conc.carregando ? carregando : conc.dados ? <ConcentracaoUso dados={conc.dados} /> : <p className="vazio">{t("vg.semDados")}</p>}
        </Painel>
      </div>

      <Painel nota="nt.paises" className="bloco" titulo={t("comp.titulo", { pais: paisAtual ? nomePais(paisAtual, idioma, t("pais.desconhecido")) : pais })} pergunta={t("comp.pergunta")}>
        {comp.carregando ? <p className="carregando" role="status">{t("comum.carregando")}</p> : comp.dados ? <ComparacaoPaises dados={comp.dados} pais={pais} /> : <p className="vazio">{t("vg.semDados")}</p>}
      </Painel>
    </>
  );
}