"""Baixa o WildChat-1M e junta todos os paises em wildchat_todos.parquet.

O pais vira um filtro no dashboard e na analise (country), entao nada e descartado aqui.

Uso:
    pip install huggingface_hub pyarrow
    huggingface-cli login        # cole um token (Settings > Access Tokens)
    python etl/download_full.py

Antes: abra https://huggingface.co/datasets/allenai/WildChat-1M e aceite os termos, se pedir.
Cada arquivo e baixado, copiado para a saida e apagado, entao o disco nao enche (a saida
final tem alguns GB).
"""
import os
import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download

REPO = "allenai/WildChat-1M"
SAIDA = r"C:\Users\wande\Desktop\Acaso\data\raw\wildchat_todos.parquet"

api = HfApi()
arquivos = sorted(f for f in api.list_repo_files(REPO, repo_type="dataset") if f.endswith(".parquet"))
print(f"{len(arquivos)} arquivos parquet encontrados")

writer = None
total = 0
for i, nome in enumerate(arquivos, 1):
    caminho = hf_hub_download(REPO, nome, repo_type="dataset")
    tabela = pq.read_table(caminho)
    if writer is None:
        writer = pq.ParquetWriter(SAIDA, tabela.schema)
    writer.write_table(tabela.cast(writer.schema))
    total += tabela.num_rows
    print(f"[{i}/{len(arquivos)}] {nome}: {tabela.num_rows} linhas (acumulado {total})")
    del tabela
    try:
        os.remove(os.path.realpath(caminho))
    except OSError:
        pass

if writer:
    writer.close()
print(f"Pronto: {total} conversas em {SAIDA} ({os.path.getsize(SAIDA)/1e9:.2f} GB)")
