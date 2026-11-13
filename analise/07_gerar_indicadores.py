"""Gera docs/INDICADORES.md a partir do CATALOGO (a mesma fonte do botao "i" e dos testes do SQL de referencia).
Rodar na raiz do repositorio:  python -I analise/07_gerar_indicadores.py"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "etl"))
from pipeline.definicoes import AMOSTRA_MINIMA, CATALOGO  # noqa: E402

CAB = """# Indicadores: definição, fórmula, denominador e consulta de referência

Gerado a partir de `etl/pipeline/definicoes.py` (`CATALOGO`), a fonte única que também alimenta o botão "i" do dashboard (que mostra só a fórmula).
A consulta de referência usa o parâmetro `:pais` e as tabelas do banco analítico (ver `docs/arquitetura.md`).
"""

blocos = [CAB]
for i in CATALOGO:
    blocos.append(f"""## {i['nome']} (`{i['indicador_id']}`)

- **Pergunta:** {i['pergunta']}
- **Fórmula:** {i['formula']}
- **Denominador:** {i['denominador']}
- **Unidade:** {i['unidade']}
- **Período de referência:** {i['periodo_referencia']}
- **Amostra mínima:** {i['amostra_minima']} (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** {i['fonte']}

```sql
{i['sql_referencia']}
```
""")
(RAIZ / "docs" / "INDICADORES.md").write_text("\n".join(blocos), encoding="utf-8", newline="\n")
print(f"{len(CATALOGO)} indicadores escritos (amostra minima {AMOSTRA_MINIMA})")