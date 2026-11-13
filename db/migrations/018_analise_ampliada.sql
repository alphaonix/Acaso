-- Analise ampliada: retorno em 24 h e curva de retorno, estratos por modelo, concentracao de uso, uso por hora, modelo no tempo
-- e o idioma do navegador (para o cruzamento idioma do pedido x idioma do navegador).
ALTER TABLE silver.fato_usuario
  ADD COLUMN voltou_24h boolean NOT NULL DEFAULT false,          -- nova sessao em ate 1 dia depois da 1a vez
  ADD COLUMN dias_ate_voltar numeric,                            -- dias entre a 1a vez e o inicio da 2a sessao (NULL = nao voltou)
  ADD COLUMN janela_30d boolean NOT NULL DEFAULT false,          -- tem 30 dias de janela: base da curva de retorno
  ADD COLUMN idioma_navegador text;                              -- 1a tag de accept-language da 1a conversa, em minusculas (ex.: pt-br)

CREATE TABLE gold.agg_curva_retorno (        -- % que ja voltou (2a sessao) ate N dias; base = usuarios com 30 dias de janela
  pais text NOT NULL, dias numeric NOT NULL, usuarios integer NOT NULL, voltaram integer NOT NULL,
  PRIMARY KEY (pais, dias)
);
CREATE TABLE gold.agg_estrato (               -- retorno de um fator DENTRO de cada familia de modelo
  pais text NOT NULL, fator text NOT NULL, familia text NOT NULL, nivel text NOT NULL,
  elegiveis integer NOT NULL, voltaram_7d integer NOT NULL,
  PRIMARY KEY (pais, fator, familia, nivel)
);
CREATE TABLE gold.agg_recusa_modelo (         -- recusa na 1a resposta por versao do modelo (so onde ha texto)
  pais text NOT NULL, modelo text NOT NULL, conversas integer NOT NULL, com_recusa integer NOT NULL, resp_media_chars integer,
  PRIMARY KEY (pais, modelo)
);
CREATE TABLE gold.agg_concentracao (          -- pessoas e conversas por faixa de conversas por pessoa
  pais text NOT NULL, ordem smallint NOT NULL, faixa text NOT NULL, usuarios integer NOT NULL, conversas integer NOT NULL,
  PRIMARY KEY (pais, ordem)
);
CREATE TABLE gold.agg_uso_hora (              -- conversas por dia da semana e hora local
  pais text NOT NULL, dia_semana smallint NOT NULL, hora smallint NOT NULL, conversas integer NOT NULL,
  PRIMARY KEY (pais, dia_semana, hora)
);
CREATE TABLE gold.agg_modelo_mes (            -- conversas por mes (fuso do pais) e quantas em GPT-4
  pais text NOT NULL, mes date NOT NULL, conversas integer NOT NULL, conversas_gpt4 integer NOT NULL,
  PRIMARY KEY (pais, mes)
);
ALTER TABLE gold.pais
  ADD COLUMN top10_pct numeric,                 -- % das conversas feitas pelas 10 pessoas mais ativas
  ADD COLUMN maior_pct numeric,                 -- % das conversas feitas pela pessoa mais ativa
  ADD COLUMN pessoas_1_conversa_pct numeric;    -- % das pessoas com uma unica conversa