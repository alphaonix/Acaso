"""Variaveis derivadas da 1a experiencia: usuario (navegador normalizado), tema, recusa, tamanhos, duracao.
ATENCAO: os testes de tema e recusa FIXAM o comportamento atual das regras (regressao), eles NAO medem precisao.
A precisao vem da amostra manual (exports/amostra_validacao_*.csv, docs/VALIDACAO.md)."""
import pytest

from pipeline.definicoes import UA_NORM_SQL

from .helpers import C, UA_ANDROID, UA_CHROME_119, UA_CHROME_120, UA_FIREFOX, linhas, rodar, t, uid, usuario

UA_EDGE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
UA_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
UA_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"


@pytest.mark.parametrize("ua, esperado", [
    (UA_CHROME_119, "Chrome/Windows"), (UA_CHROME_120, "Chrome/Windows"),      # a versao NAO muda o usuario
    (UA_EDGE, "Edge/Windows"), (UA_FIREFOX, "Firefox/Windows"), (UA_ANDROID, "Chrome/Android"),
    (UA_IPHONE, "Safari/iOS"), (UA_MAC, "Safari/Mac"), (None, "Outro/Outro"), ("curl/8.0", "Outro/Outro"),
])
def test_navegador_e_sistema_sem_versao(dw, ua, esperado):
    assert linhas(dw, f"SELECT {UA_NORM_SQL.replace(chr(37), chr(37) * 2)} FROM (VALUES (%s::text)) AS t(ua)", (ua,))[0][0] == esperado


TEMAS = [
    ("oi", "Saudação"), ("Olá, tudo bem?", "Saudação"), ("", "Vazio"),
    ("Escreva um código em Python para ordenar uma lista", "Tecnologia/código"),
    ("Traduza este texto para o inglês: bom dia a todos", "Escrita/edição/tradução"),
    ("Resolva a questão 5 da prova de matemática", "Tarefa escolar/acadêmica"),
    ("Crie uma história de aventura com um dragão", "Ficção/criação"),
    ("Atue como um professor de física muito paciente", "Persona/roleplay"),
    ("Quais são as capitais da Europa?", "Conhecimento/pergunta"),
    ("Gere um prompt para midjourney de um gato astronauta", "Prompt de imagem"),
    ("zzzz qqqq", "Outro"),
]


def test_tema_do_primeiro_pedido(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C(f"tema{i}", ini, prompt=p) for i, (p, _) in enumerate(TEMAS)])
    obtido = {i: linhas(dw, "SELECT d.tema FROM silver.fato_usuario u JOIN silver.dim_tema d USING (tema_id) WHERE u.usuario_id = %s", (uid(f"tema{i}"),))[0][0]
              for i, _ in enumerate(TEMAS)}
    assert obtido == {i: esperado for i, (_, esperado) in enumerate(TEMAS)}


RECUSAS = [
    ("Desculpe, mas não posso ajudar com isso.", True), ("Sinto muito, não tenho como fazer isso.", True),
    ("I'm sorry, but I can't assist with that request.", True), ("As an AI language model, I do not have opinions.", True),
    ("DESCULPE, NÃO POSSO ajudar.", True),                                    # maiusculas
    ("Claro! Aqui está a resposta que você pediu.", False),
    ("A capital da França é Paris. " * 20 + "Desculpe pela demora.", False),  # a recusa so conta na ABERTURA (300 primeiros caracteres)
]


def test_recusa_na_abertura_da_primeira_resposta(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C(f"rec{i}", ini, resposta=r) for i, (r, _) in enumerate(RECUSAS)])
    obtido = [usuario(dw, f"rec{i}")["recusa"] for i in range(len(RECUSAS))]
    assert obtido == [esperado for _, esperado in RECUSAS]


def test_texto_so_existe_no_brasil_fora_dele_tema_e_recusa_ficam_vazios(dw):
    rodar(dw, [C("us", t("2023-06-01 10:00"), pais="United States", hash="us1")])
    assert linhas(dw, "SELECT tema_id, recusa FROM silver.fato_conversa WHERE conversation_hash = 'us1'") == [(None, None)]


def test_duracao_e_tamanhos(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("u", ini, fim=t("2023-06-01 10:12"), prompt="12345", resposta="1234567890", hash="dur")])
    assert linhas(dw, "SELECT duracao_s, prompt1_chars, resp1_chars FROM silver.fato_conversa WHERE conversation_hash = 'dur'") == [(720, 5, 10)]