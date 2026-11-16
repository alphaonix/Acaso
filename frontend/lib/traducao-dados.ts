/**
 * Traducao dos textos que VEM DO BANCO (a base os guarda em portugues). Em portugues devolve o original.
 * Termo sem traducao conhecida: devolve o original (nunca quebra a tela).
 */
import type { Indicador } from "./tipos";

type Id = "pt" | "en";

const FATORES: Record<string, string> = {
  "Modelo": "Model",
  "Recusa na primeira resposta": "Refusal in the first response",
  "Tamanho da primeira resposta": "Length of the first response",
  "Turnos da primeira conversa": "Turns in the first conversation",
  "Tamanho do primeiro pedido": "Length of the first request",
  "Horário": "Time of day",
  "Dia da semana": "Day of the week",
  "Idioma": "Language",
  "Tema do primeiro pedido": "Theme of the first request",
};

const TEMAS: Record<string, string> = {
  "Vazio": "Empty", "Saudação": "Greeting", "Prompt de imagem": "Image prompt", "Persona/roleplay": "Persona/roleplay",
  "Adulto/sensível": "Adult/sensitive", "Tecnologia/código": "Technology/code", "Tarefa escolar/acadêmica": "School/academic task",
  "Escrita/edição/tradução": "Writing/editing/translation", "Ficção/criação": "Fiction/creative", "Conhecimento/pergunta": "Knowledge/question",
  "Outro": "Other",
};

const CONTRASTES: Record<string, string> = {
  "GPT-4 em vez de GPT-3.5": "GPT-4 instead of GPT-3.5",
  "Com recusa em vez de sem": "With refusal instead of without",
  "2 ou mais em vez de 1": "2 or more instead of 1",
  "Noite (18-23h) em vez de outros períodos": "Evening (6-11 pm) instead of other periods",
  "Fim de semana em vez de dia útil": "Weekend instead of weekday",
  "Inglês em vez de português": "English instead of Portuguese",
};

const COVARIAVEIS: Record<string, string> = {
  mes: "month of arrival", periodo: "time of day", fds: "weekend", sistema: "operating system", navegador: "browser",
  estado_grp: "state", modelo_fam: "model", tema: "theme", pedido_bin: "request length", idioma_grp: "language",
};

const METODOS: Record<string, string> = {
  "AIPW (duplamente robusto), validação cruzada 5 dobras, regressão logística L2":
    "AIPW (doubly robust), 5-fold cross-fitting, L2 logistic regression",
};

const QA: Record<string, string> = {
  "Conversas na bronze = base completa do WildChat-1M": "Conversations in bronze = full WildChat-1M dataset",
  "Conversas do Brasil (silver)": "Brazil conversations (silver)",
  "Usuarios do Brasil": "Brazil users",
  "Usuarios elegiveis do Brasil": "Brazil eligible users",
  "Retorno em 7 dias do Brasil (4 casas)": "Brazil 7-day return (4 decimals)",
  "Usuarios em Sao Paulo": "Users in São Paulo",
  "Usuarios em Minas Gerais": "Users in Minas Gerais",
  "Conversas com recusa (Brasil)": "Conversations with refusal (Brazil)",
  "Usuarios com recusa na 1a conversa (Brasil)": "Users with refusal in the 1st conversation (Brazil)",
  "Conversas redigidas (Brasil)": "Redacted conversations (Brazil)",
  "Usuarios distintos nas conversas = usuarios (Brasil)": "Distinct users in conversations = users (Brazil)",
  "Retorno recalculado a partir das conversas = voltou_7d da silver (usuarios com divergencia)": "Return recalculated from the conversations = silver voltou_7d (users with a mismatch)",
  "Elegibilidade recalculada = elegivel da silver (usuarios com divergencia)": "Eligibility recalculated = silver elegivel (users with a mismatch)",
  "Primeira vez recalculada = primeira_vez_utc da silver (usuarios com divergencia)": "First use recalculated = silver primeira_vez_utc (users with a mismatch)",
  "Soma de conversas por usuario = conversas (todos os paises)": "Sum of conversations per user = conversations (all countries)",
  "Todo pais (exceto Desconhecido) tem codigo ISO para o nome na lingua da tela": "Every country (except Desconhecido) has an ISO code for the on-screen language name",
  "Uso diario (gold): conversas por dia somam as conversas da silver, todos os paises": "Daily usage (gold): conversations per day add up to the silver conversations, all countries",
  "Retorno mensal por fator (modelo): elegiveis somam os elegiveis da silver, todos os paises": "Monthly return by factor (model): eligible users add up to the silver eligible users, all countries",
  "Retorno por semana (gold): elegiveis somam os elegiveis da silver, todos os paises": "Weekly return (gold): eligible users add up to the silver eligible users, all countries",
  "Nenhum usuario_id em dois paises": "No usuario_id in two countries",
  "Efeitos estimados (Brasil): ha pelo menos um": "Estimated effects (Brazil): at least one",
  "Efeitos: IC contem a estimativa em todas as linhas": "Effects: CI contains the estimate on every row",
  "Efeitos: nenhum grupo com menos de 30 usuarios": "Effects: no group with fewer than 30 users",
  "Gold = silver: elegiveis por semana somam os elegiveis (Brasil)": "Gold = silver: weekly eligible users add up to eligible users (Brazil)",
  "Linhas na tabela bronze.wildchat = linhas dos arquivos de origem": "Rows in table bronze.wildchat = rows in the source files",
  "Bronze: linhas do Brasil = linhas do arquivo wildchat_brasil": "Bronze: Brazil rows = rows in the wildchat_brasil file",
  "Bronze: nenhuma linha do Brasil veio do arquivo dos outros paises": "Bronze: no Brazil row came from the other-countries file",
  "Bronze: mensagens no JSON = 2 x turnos em todas as conversas com texto": "Bronze: messages in the JSON = 2 x turns in every conversation with text",
  "Linhas da bronze = conversas da silver + linhas excluidas": "Bronze rows = silver conversations + excluded rows",
  "Toda conversa da silver aponta para uma linha existente da bronze": "Every silver conversation points to an existing bronze row",
  "Pais nulo na bronze = Desconhecido na silver + excluidas": "Null country in bronze = Desconhecido in silver + excluded",
  "Usuarios por pais: gold.pais = silver.fato_usuario": "Users per country: gold.pais = silver.fato_usuario",
  "Conversas por pais: gold.pais = silver.fato_conversa": "Conversations per country: gold.pais = silver.fato_conversa",
  "Novos por semana (gold) somam os usuarios da silver, todos os paises": "New users per week (gold) add up to silver users, all countries",
  "Fator modelo: elegiveis somam os elegiveis da silver, todos os paises": "Model factor: eligible users add up to silver eligible users, all countries",
  "Usuarios do Brasil por tema (11 temas, na ordem da taxonomia)": "Brazil users per theme (11 themes, in taxonomy order)",
  "Curva de retorno: usuarios do ponto final = usuarios com janela de 30 dias na silver, todos os paises": "Return curve: users at the last point = silver users with a 30-day window, all countries",
  "Curva de retorno: ate 7 dias nunca decresce com os dias (pontos fora de ordem)": "Return curve: up to 7 days never decreases with days (out-of-order points)",
  "Voltou em 24 h implica voltou em 7 dias (usuarios que violam)": "Returned within 24 h implies returned within 7 days (violating users)",
  "Curva em 7 dias: pessoas = elegiveis da silver, todos os paises (a mesma base do retorno em 7 dias)": "Curve at 7 days: people = silver eligible people, all countries (the same base as the 7-day return)",
  "Curva em 7 dias: quem voltou = retorno em 7 dias da silver entre as pessoas elegiveis (diferenca)": "Curve at 7 days: who came back = silver 7-day return among eligible people (difference)",
  "Concentracao: conversas por faixa somam as conversas da silver, todos os paises": "Concentration: conversations per band add up to silver conversations, all countries",
  "Concentracao: usuarios por faixa somam os usuarios da silver, todos os paises": "Concentration: users per band add up to silver users, all countries",
  "Uso por hora: conversas somam as conversas da silver, todos os paises": "Usage by hour: conversations add up to silver conversations, all countries",
  "Modelo por mes: conversas somam as conversas da silver, todos os paises": "Model by month: conversations add up to silver conversations, all countries",
  "Recusa por modelo: conversas com texto somam as conversas com recusa conhecida na silver": "Refusal by model: conversations with text add up to silver conversations with known refusal",
  "Estratos de recusa: elegiveis somam os elegiveis com recusa conhecida na silver": "Refusal strata: eligible users add up to silver eligible users with known refusal",
  "Retorno por versao do modelo: elegiveis somam os elegiveis com recusa conhecida na silver": "Return by model version: eligible users add up to silver eligible users with known refusal",
  "Retorno por versao do modelo: voltaram em 7 dias somam os da silver (usuarios com recusa conhecida)": "Return by model version: 7-day returners add up to silver returners (users with known refusal)",
  "Fator dispositivo: elegiveis somam os elegiveis da silver, todos os paises": "Device factor: eligible users add up to silver eligible users, all countries",
};

const INDICADORES: Record<string, Partial<Record<keyof Indicador, string>>> = {
  retorno_7d: {
    nome: "7-day return",
    pergunta: "Of every 100 people who tried the assistant, how many came back within 7 days?",
    unidade: "user",
    denominador: "Eligible users: first use at least 7 days before the end of the data and after the first 30 days",
    formula: "eligible users with a new session started within 7 days of the first one ÷ eligible users",
    periodo_referencia: "Week of arrival (Monday to Sunday) in the country's time zone",
  },
  usuarios_novos: {
    nome: "New users",
    pergunta: "How many people used the assistant for the first time each week?",
    unidade: "user",
    denominador: "not applicable (count)",
    formula: "count of distinct users by week of the first conversation",
    periodo_referencia: "Week of arrival, in the country's time zone",
  },
  usuarios_elegiveis: {
    nome: "Eligible users",
    pergunta: "How many users have a full window to measure return?",
    unidade: "user",
    denominador: "New users",
    formula: "new users whose first use is more than 30 days after the start and more than 7 days before the end of the data",
    periodo_referencia: "Entire data period of the country",
  },
  conversas: {
    nome: "Conversations",
    pergunta: "How many conversations did the assistant have in the period, and how many per user?",
    unidade: "conversation",
    denominador: "not applicable (count); per user = conversations ÷ users",
    formula: "count of conversations, after removing exact copies",
    periodo_referencia: "Entire data period of the country",
  },
  turnos_medios: {
    nome: "Average turns",
    pergunta: "How many turns (message exchanges) does each user's 1st conversation have on average?",
    unidade: "turn",
    denominador: "Users of the country",
    formula: "average number of turns in each user's 1st conversation; the median is the middle value",
    periodo_referencia: "Entire data period of the country",
  },
  uso_gpt4: {
    nome: "GPT-4 use",
    pergunta: "What share of the 1st conversations used a GPT-4 model?",
    unidade: "user",
    denominador: "Users of the country",
    formula: "users whose 1st conversation used a GPT-4 model ÷ users",
    periodo_referencia: "Entire data period of the country",
  },
  recusa_primeira_conversa: {
    nome: "Refusal in the first response",
    pergunta: "In how many users does the assistant's first response open with a refusal or apology?",
    unidade: "user",
    denominador: "Eligible users from countries with text (only Brazil for now)",
    formula: "eligible users whose first response matches the refusal pattern ÷ eligible users",
    periodo_referencia: "Entire data period of the country",
  },
  voltou_24h_elegivel: {
    nome: "Returned within 24 hours (7-day return base)",
    pergunta: "Of every 100 eligible people, how many come back within 24 hours of the start of the 1st conversation?",
    unidade: "user",
    denominador: "Eligible users (first use more than 30 days after the start and 7 days before the end of the data): the same base as 7-day return",
    formula: "eligible users with a new session started within 24 hours of the start of the 1st conversation ÷ eligible users",
    periodo_referencia: "Entire data period of the country",
  },
  voltou_24h: {
    nome: "Returned within 24 hours",
    pergunta: "Of every 100 people, how many come back within 24 hours of the start of the 1st conversation?",
    unidade: "user",
    denominador: "Users with a full 30-day window (first use more than 30 days after the start and before the end of the data)",
    formula: "users with a new session started within 24 hours of the start of the 1st conversation ÷ users with a 30-day window",
    periodo_referencia: "Entire data period of the country",
  },
  voltou_30d: {
    nome: "Returned within 30 days",
    pergunta: "Of every 100 people, how many come back within 30 days of the start of the 1st conversation?",
    unidade: "user",
    denominador: "Users with a full 30-day window (first use more than 30 days after the start and before the end of the data)",
    formula: "users with a new session started within 30 days of the start of the 1st conversation ÷ users with a 30-day window",
    periodo_referencia: "Entire data period of the country",
  },
  concentracao_top10: {
    nome: "Usage concentration (10 most active)",
    pergunta: "What share of conversations comes from the 10 most active people?",
    unidade: "conversation",
    denominador: "Conversations of the country (after removing exact copies)",
    formula: "conversations of the 10 people with the most conversations ÷ conversations of the country; concentrated-use alert from 25%",
    periodo_referencia: "Entire data period of the country",
  },
  recusa_por_versao: {
    nome: "Refusal by model version",
    pergunta: "In what share of conversations does the first response open with a refusal, for each model version?",
    unidade: "conversation",
    denominador: "Conversations with text, of the model version",
    formula: "conversations of the version whose first response matches the refusal pattern ÷ conversations of the version",
    periodo_referencia: "Entire data period of the country",
  },
};

const NIVEIS: Record<string, string> = {
  "1 turno": "1 turn", "2-3 turnos": "2-3 turns", "4-6 turnos": "4-6 turns", "7+ turnos": "7+ turns",
  "Madrugada (0-5h)": "Early morning (0-5h)", "Manhã (6-11h)": "Morning (6-11h)", "Tarde (12-17h)": "Afternoon (12-17h)", "Noite (18-23h)": "Evening (18-23h)",
  "Dia útil": "Weekday", "Fim de semana": "Weekend",
  "Celular": "Mobile", "Computador": "Desktop", "Pedido no idioma do navegador": "Request in the browser language",
  "Inglês (navegador em outro idioma)": "English (browser in another language)", "Outro idioma (nem o do navegador, nem inglês)": "Other language (neither the browser's nor English)",
  "Com recusa": "With refusal", "Sem recusa": "Without refusal", "Outro tema": "Other theme",
};
/** Nivel de um fator (tema, turnos, periodo do dia...) na lingua da tela. */
export const tNivel = (n: string, i: Id) => (i === "en" ? NIVEIS[n] ?? TEMAS[n] ?? n : n);
export const tFator = (f: string, i: Id) => (i === "en" ? FATORES[f] ?? f : f);
export const tTema = (t: string, i: Id) => (i === "en" ? TEMAS[t] ?? t : t);
export const tMetodo = (m: string, i: Id) => (i === "en" ? METODOS[m] ?? m : m);
export const tQa = (v: string, i: Id) => (i === "en" ? QA[v] ?? v : v);

export function tContraste(c: string, i: Id): string {
  if (i !== "en") return c;
  if (CONTRASTES[c]) return CONTRASTES[c];
  let m = c.match(/^Longa \(>= (\d+) caracteres\) em vez de curta$/);
  if (m) return `Long (>= ${m[1]} characters) instead of short`;
  m = c.match(/^Longo \(>= (\d+) caracteres\) em vez de curto$/);
  if (m) return `Long (>= ${m[1]} characters) instead of short`;
  const partes = c.split(" em vez de ");
  if (partes.length === 2) return `${TEMAS[partes[0]] ?? partes[0]} instead of ${TEMAS[partes[1]] ?? partes[1]}`;
  return c;
}

export function tAjustado(s: string, i: Id): string {
  if (i !== "en") return s.replaceAll("_", " ");
  return s.split(",").map((x) => x.trim()).map((x) => COVARIAVEIS[x] ?? x.replaceAll("_", " ")).join(", ");
}

/** Devolve o indicador com os textos no idioma pedido (SQL e fonte tecnica nao se traduzem). */
export function tIndicador(ind: Indicador, i: Id): Indicador {
  if (i !== "en") return ind;
  return { ...ind, ...(INDICADORES[ind.indicador_id] ?? {}) } as Indicador;
}
