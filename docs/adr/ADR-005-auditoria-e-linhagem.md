# ADR-005: auditoria e linhagem entre camadas

Status: aceita (12/11/2026).

## Contexto
Com bronze, silver e gold (ADR-004), faltava **enxergar o caminho do dado**: quantas linhas há em cada camada, o que foi excluído
de uma para a outra e por quê, quais valores vazios (nulos) existiam e o que se fez com eles, como o dado era antes e como ficou,
e se os números batem entre as camadas. O PDF pede isso na seção 4.1 ("o que registraria em cada camada para investigar um número
errado depois"), e a pessoa de negócio, que não usa SQL, também precisa ver.

## Opções
1. **Só consultar bronze e silver direto.** Serve a quem usa SQL; não serve à tela, porque a API não tem acesso a bronze e silver
   (elas contêm texto de conversa).
2. **Schema `auditoria` preenchido pelo ETL, mais uma tela que o lê.** Guarda só contagens, nomes de coluna e identificadores
   técnicos; a API pode lê-lo.
3. **Ferramenta de linhagem/qualidade** (OpenLineage, dbt docs, Great Expectations). Mais robusto em escala, mais peças e
   configuração para uma entrega local.

## Decisão
Opção 2.
- **Linhagem por linha:** `silver.fato_conversa.bronze_id` guarda de qual linha da bronze veio cada conversa. Dá para provar, linha
  a linha, o que passou e o que não passou.
- **Schema `auditoria`** (migração 006; a 008 cria a visão `auditoria.camadas` e a 009 remove a contagem por tabela e o funil, redundantes), com **só a última carga** (o ETL o esvazia e
  recarrega na mesma transação; o histórico das cargas fica em `ops.etl_execucao` e `ops.qa_resultado`):
  `camadas` (visão: conversas em bronze, silver e gold, com as excluídas e a conferência), `fluxo_pais` (o funil bronze → excluídas → silver → gold, por país e total),
  `nulos` (vazios antes e depois, com a ação: preenchido, mantido, excluído, derivado, não usado), `registro_excluido` (as linhas
  excluídas, com o motivo e a linha que ficou no lugar) e `antes_depois` (exemplos em `campo=valor`, sem texto e sem IP).
- **Conferências por transição:** cada uma das 65 verificações de `ops.qa_resultado` diz qual passagem protege (bronze x arquivos,
  bronze → silver, silver interna, silver → gold, efeitos, números validados). A principal é a lei de conservação:
  **linhas da bronze = conversas da silver + linhas excluídas**.
- **Sem tela no dashboard (decisão de 12/11):** a primeira versão tinha uma tela "Linhagem dos dados" (e o endpoint `/api/linhagem`). Foi removida: o dashboard é para o cliente, que não precisa dela. A auditoria continua no schema `auditoria` (consulta no DBeaver, `docs/VALIDACAO.md`, rodada 7) e nas conferências do ETL (`ops.qa_resultado`, registradas em `ops.qa_resultado`). A API não lê mais o schema `auditoria`.

## Consequências
- **Correção após o primeiro uso:** a versão inicial acumulava as cargas; quem somava as linhas de uma camada via 3x o valor real
  (3 cargas misturadas). Agora a auditoria guarda só a última carga. E, como as tabelas de uma camada têm granularidades diferentes
  (conversa, usuário, resumo), somar linhas de tabelas não serve: a visão `auditoria.camadas` conta **a mesma unidade (conversas)**
  em cada camada, com as excluídas e a conferência (`confere`). A contagem por tabela e o funil foram removidos por redundância.
- **Privacidade:** a auditoria guarda, das poucas linhas excluídas, o número da linha e o **hash da conversa** (um hash do conteúdo, não
  reversível). Nunca texto, IP, user-agent nem identificador de usuário. Como não há tela, o cliente não vê nada disso.
- As tabelas `ops` (`etl_execucao`, `qa_resultado`, `bronze_lote`) **continuam necessárias**: a auditoria se apoia nelas
  (`execucao_id`) e a API as lê para a saúde dos dados e para a tela de qualidade.
- Os exemplos de antes e depois cobrem os tratamentos do Brasil (os únicos com texto); a exclusão e o funil cobrem todos os países.
- A auditoria roda dentro da transação da carga: se o portão de qualidade falhar, nada é publicado, nem a auditoria daquela carga.
