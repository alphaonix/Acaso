"""Do dado bruto ate a SEMENTE, em um comando (a semente versionada em data/seed/ nasceu daqui).

  1. Baixa o WildChat-1M do Hugging Face (publico, sem login; 14 arquivos Parquet, ~3,3 GB) para data/raw/.
     A revisao do dataset esta fixada (REVISAO), entao o resultado e o mesmo em qualquer dia.
  2. Gera a semente com o DuckDB:
       data/seed/wildchat_brasil.parquet         Brasil, bruto completo (com texto) + primeira_resposta_ts      ~22 MB
       data/seed/wildchat_outros_paises.parquet  demais paises, so metadados (SEM texto) + primeira_resposta_ts  ~35 MB
  3. Confere as contagens (837.989 conversas, 11.621 do Brasil).

Uso (a partir da raiz do projeto):
  docker compose --profile base run --rm baixar-base                  # baixa e gera a semente
  docker compose --profile base run --rm baixar-base --so-semente     # refaz a semente de data/raw ja baixado
  docker compose --profile base run --rm baixar-base --teste          # baixa so 1 arquivo e gera numa pasta de teste (nao mexe na semente)
Depois, para o banco usar a semente nova:  docker compose run --rm etl python main.py --recarregar

Por que a semente existe no repositorio mesmo assim: `docker compose up` sobe em poucos minutos e sem internet para dados (ADR-002).
So depende da biblioteca padrao e do DuckDB (que o ETL ja usa).
"""
import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

import duckdb

REPO = "allenai/WildChat-1M"
REVISAO = "7d6490e462285cf85d91eabea0f9a954fbddcd1f"      # commit do dataset no Hugging Face (17/10/2024); fixa o que se baixa
ARQUIVOS = [f"data/train-{i:05d}-of-00014.parquet" for i in range(14)]
URL = "https://huggingface.co/datasets/{repo}/resolve/{rev}/{arq}"
TOTAL_ESPERADO, BRASIL_ESPERADO = 837_989, 11_621

RAIZ = Path(__file__).resolve().parents[2]
DADOS = Path(os.environ.get("DATA_DIR") or RAIZ / "data")

# Mesma regra para todos os paises: o inicio da conversa e o horario da 1a resposta do assistente (a mensagem 2; as do usuario nao tem horario).
INICIO = "struct_extract(list_extract(conversation, 2), 'timestamp') AS primeira_resposta_ts"


def baixar(destino: Path, arquivos: list[str]) -> list[Path]:
    """Baixa cada arquivo (pula os que ja estao completos; tenta 3 vezes) e devolve os caminhos locais."""
    destino.mkdir(parents=True, exist_ok=True)
    locais = []
    for i, arq in enumerate(arquivos, 1):
        local = destino / Path(arq).name
        url = URL.format(repo=REPO, rev=REVISAO, arq=arq)
        for tentativa in range(1, 4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "baixar-base"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    tamanho = int(r.headers.get("Content-Length") or 0)
                    if local.exists() and tamanho and local.stat().st_size == tamanho:
                        print(f"[{i}/{len(arquivos)}] {local.name}: ja baixado ({tamanho / 1e6:.0f} MB)", flush=True)
                        break
                    parcial = local.with_suffix(".parte")
                    lido, t0 = 0, time.time()
                    with open(parcial, "wb") as f:
                        while bloco := r.read(1 << 20):
                            f.write(bloco)
                            lido += len(bloco)
                    if tamanho and lido != tamanho:
                        raise OSError(f"download incompleto ({lido} de {tamanho} bytes)")
                    parcial.replace(local)
                    print(f"[{i}/{len(arquivos)}] {local.name}: {lido / 1e6:.0f} MB em {time.time() - t0:.0f}s", flush=True)
                    break
            except OSError as e:
                print(f"[{i}/{len(arquivos)}] {local.name}: falhou ({e}); tentativa {tentativa} de 3", flush=True)
                if tentativa == 3:
                    sys.exit(f"Nao consegui baixar {url}")
                time.sleep(5 * tentativa)
        locais.append(local)
    return locais


def gerar_semente(fontes: list[Path], saida: Path, conferir: bool = True) -> None:
    """Escreve os dois Parquet da semente a partir dos arquivos brutos (todos os paises; nada e descartado em silencio)."""
    saida.mkdir(parents=True, exist_ok=True)
    lista = "[" + ", ".join("'" + f.as_posix() + "'" for f in sorted(fontes)) + "]"
    # A ordem das linhas fica FIXA (arquivo e linha dentro dele): sem isso a leitura em paralelo de varios arquivos embaralha as linhas
    # e a semente muda de bytes a cada execucao, embora o conteudo seja o mesmo.
    bruto = f"read_parquet({lista}, union_by_name = true, filename = true, file_row_number = true)"
    ordem = "ORDER BY filename, file_row_number"
    con = duckdb.connect()
    con.execute(f"""COPY (SELECT * EXCLUDE (filename, file_row_number), {INICIO} FROM {bruto} WHERE country = 'Brazil' {ordem})
      TO '{(saida / "wildchat_brasil.parquet").as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
    con.execute(f"""COPY (
      SELECT conversation_hash, model, turn, language, country, state, hashed_ip, header, timestamp, toxic, redacted,
             {INICIO}
      FROM {bruto} WHERE country IS DISTINCT FROM 'Brazil' {ordem})   -- inclui country nulo (1.060 linhas)
      TO '{(saida / "wildchat_outros_paises.parquet").as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
    contagens = {}
    for f in sorted(saida.glob("*.parquet")):
        contagens[f.name] = con.execute(f"SELECT count(*) FROM read_parquet('{f.as_posix()}')").fetchone()[0]
        print(f"{f.name}: {contagens[f.name]} linhas, {f.stat().st_size / 1e6:.1f} MB")
    if conferir:
        total, brasil = sum(contagens.values()), contagens.get("wildchat_brasil.parquet")
        if (total, brasil) != (TOTAL_ESPERADO, BRASIL_ESPERADO):
            sys.exit(f"Contagens diferentes do esperado: {total} conversas ({brasil} do Brasil); esperado {TOTAL_ESPERADO} ({BRASIL_ESPERADO}).")
        print(f"Conferido: {total} conversas, {brasil} do Brasil. Para o banco usar: docker compose run --rm etl python main.py --recarregar")


def main() -> None:
    ap = argparse.ArgumentParser(description="Baixa o WildChat-1M e gera a semente.")
    ap.add_argument("--so-semente", action="store_true", help="nao baixa; refaz a semente a partir de data/raw")
    ap.add_argument("--teste", action="store_true", help="baixa so 1 arquivo e gera em data/teste_baixar (nao altera data/seed)")
    ap.add_argument("--saida", type=Path, help="pasta da semente (padrao: data/seed)")
    args = ap.parse_args()

    bruto = DADOS / "raw"
    if args.teste:
        saida, arquivos = DADOS / "teste_baixar" / "seed", ARQUIVOS[:1]
        bruto = DADOS / "teste_baixar" / "raw"
    else:
        saida, arquivos = args.saida or DADOS / "seed", ARQUIVOS
    if args.so_semente:
        fontes = sorted(bruto.glob("train-*.parquet")) or sorted(bruto.glob("wildchat_todos.parquet"))
        if not fontes:
            sys.exit(f"Nada em {bruto}: rode sem --so-semente para baixar.")
    else:
        fontes = baixar(bruto, arquivos)
    gerar_semente(fontes, saida, conferir=not args.teste)


if __name__ == "__main__":
    main()
