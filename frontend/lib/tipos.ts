export type Pais = {
  pais: string; nome_exibicao: string; iso2: string | null; fuso: string; fuso_aproximado: boolean; idioma_padrao: string;
  tem_texto: boolean; usuarios: number; usuarios_elegiveis: number; conversas: number;
  primeira_data: string | null; ultima_data: string | null;
};
export type Indicador = {
  indicador_id: string; nome: string; pergunta: string; unidade: string; denominador: string;
  formula: string; sql_referencia: string; fonte: string; periodo_referencia: string; amostra_minima: number;
};
export type Resumo = {
  novos: number; elegiveis: number; voltaram_7d: number; taxa: number | null; ic_lo: number | null; ic_hi: number | null;
  primeira_semana: string | null; ultima_semana: string | null;
  voltou_24h?: { voltaram: number; elegiveis: number; taxa: number | null; ic_lo: number | null; ic_hi: number | null };
  conversas: number; turnos_medios: number; turnos_mediana: number; pct_gpt4: number;
  recusa_usuarios: number | null; recusa_elegiveis: number | null; recusa_taxa: number | null; recusa_ic_lo: number | null; recusa_ic_hi: number | null;
};
export type Coorte = {
  semana: string; novos: number; elegiveis: number; voltaram_7d: number;
  taxa: number | null; ic_lo: number | null; ic_hi: number | null; amostra_pequena: boolean;
};
export type Efeito = {
  pais: string; fator: string; contraste: string; tipo: "alavanca" | "perfil";
  n: number; n_tratados: number; n_controle: number; taxa_controle: number;
  efeito_bruto_pp: number; bruto_ic_lo: number; bruto_ic_hi: number;
  efeito_pp: number; ic_lo: number; ic_hi: number; sobreposicao: number;
  e_value: number; e_value_ic: number; metodo: string; ajustado_por: string;
};
export type Qualidade = {
  execucao: { id: number; status: string; iniciado_em: string; finalizado_em: string | null; versao_codigo: string | null;
              linhas_lidas: number | null; linhas_carregadas: number | null } | null;
  verificacoes: { verificacao: string; esperado: string; obtido: string; passou: boolean }[];
  lotes: { arquivo: string; sha256: string; linhas: number }[];
  problemas: { codigo: string; escopo: "todos" | "brasil"; afetadas: number; total: number }[];
};
export type Usuario = { email: string; nome: string; foto?: string | null };

export type FatorNivel = { fator: string; nivel: string; elegiveis: number; voltaram_7d: number; taxa: number | null; ic_lo: number | null; ic_hi: number | null; amostra_pequena: boolean };
export type Uso = { dia: string; conversas: number; usuarios_ativos: number };
export type Decomposicao = {
  disponivel: boolean; fator: string; meses: { mes: string; elegiveis: number; taxa: number }[];
  de?: string; para?: string; n_de?: number; n_para?: number; taxa_de?: number; taxa_para?: number; delta_pp?: number;
  componentes_pp?: { mix: number; taxa: number; interacao: number }; soma_confere?: boolean;
  niveis?: { nivel: string; peso_de: number; peso_para: number; taxa_de: number | null; taxa_para: number | null; n_de: number; n_para: number }[];
};
export type LinhaComparacao = { elegiveis: number; voltaram_7d: number; taxa: number; ic_lo: number; ic_hi: number };
export type Comparacao = { paises: (LinhaComparacao & { pais: string })[]; geral: LinhaComparacao };


export type PontoCurva = { dias: number; usuarios: number; voltaram: number; taxa: number | null; ic_lo: number | null; ic_hi: number | null; amostra_pequena: boolean };
export type Curva = { pontos: PontoCurva[]; voltou_24h: PontoCurva | null; voltou_7d: PontoCurva | null; voltou_30d: PontoCurva | null };
export type TaxaGrupo = { nivel: string; elegiveis: number; voltaram: number; taxa: number | null; ic_lo: number | null; ic_hi: number | null; amostra_pequena: boolean };
export type Estrato = { fator: "recusa" | "saudacao"; familia: "GPT-4" | "GPT-3.5"; tratado: TaxaGrupo | null; comparacao: TaxaGrupo | null; diferenca: { pp: number; ic_lo: number; ic_hi: number } | null };
export type Concentracao = {
  faixas: { faixa: string; usuarios: number; conversas: number; pct_pessoas: number; pct_conversas: number }[];
  retorno_com?: { voltaram: number; elegiveis: number; taxa: number | null; ic_lo: number | null; ic_hi: number | null } | null;
  retorno_sem_top10?: { voltaram: number; elegiveis: number; taxa: number | null; ic_lo: number | null; ic_hi: number | null } | null;
  usuarios: number; conversas: number; top10_pct: number | null; maior_pct: number | null; pessoas_1_conversa_pct: number | null;
};
export type UsoHora = { celulas: { dia_semana: number; hora: number; conversas: number }[]; total: number; pct_expediente: number | null; pct_madrugada: number | null; fuso: string; fuso_aproximado: boolean };
export type TaxaIC = { taxa: number | null; ic_lo: number | null; ic_hi: number | null; amostra_pequena: boolean };
export type VersaoModelo = {
  modelo: string; familia: "GPT-4" | "GPT-3.5"; conversas: number; conversas_texto: number; recusa_possivel: boolean; com_recusa: number; resp_media_chars: number | null;
  elegiveis: number; voltaram_7d: number; retorno: TaxaIC; recusa: TaxaIC;
};
export type FamiliaModelo = { familia: "GPT-4" | "GPT-3.5"; elegiveis: number; voltaram_7d: number; conversas: number; conversas_texto: number; com_recusa: number; retorno: TaxaIC; recusa: TaxaIC | null };
export type ModelosTempo = { meses: { mes: string; conversas: number; conversas_gpt4: number }[]; versoes: VersaoModelo[]; familias: FamiliaModelo[] };