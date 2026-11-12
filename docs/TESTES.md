# Testes automatizados

Objetivo (PDF 4.1): **a definição de um indicador não pode mudar sem ninguém perceber.** Os testes fixam cada regra de borda da
definição (BDR-001) e reproduzem o incidente do PDF (seção 4.2). São 76 testes, rodam em segundos e **não tocam o banco real**.

```bash
docker compose --profile test run --rm --build testes-etl     # 47 testes: sessão, retorno, elegibilidade, limpeza, tema, recusa, gold, catálogo, incidente
docker compose --profile test run --rm --build testes-api     # 29 testes: decomposição mix x taxa
```
O perfil `test` não sobe com `docker compose up`. Os testes do ETL criam um banco descartável (`retencao_teste`) no mesmo servidor,
aplicam as migrações, inserem conversas **sintéticas** na bronze, rodam a silver e a gold de verdade e conferem o resultado; cada teste
termina em `ROLLBACK` e o banco é apagado no fim.

## O que cada arquivo garante
| Arquivo | Regra fixada |
|---|---|
| `test_sessao_retorno.py` | gap de 30 min (30 min exatos = mesma sessão; 30 min e 1 s = nova); retorno em até 7 dias (7 dias exatos conta; +1 s não); a própria sessão da 1ª experiência não é retorno; elegibilidade (30 dias do início e 7 dias do fim, nas duas bordas); 1ª experiência = 1ª conversa; semana, hora e dia no fuso do país |
| `test_incidente.py` | **teste dourado do incidente**: atualizar o navegador não cria outro usuário; a "primeira vez" é o início da conversa e não o último turno (em UTC); uma conversa longa não é retorno; reproduz na gold o cenário "5 usuários voltam com o Chrome atualizado" e exige 5 novos e 5 retornos, **nenhum "novo" fantasma** |
| `test_limpeza.py` | cópia exata excluída (e só ela); mesmo hash com IP ou início diferente é outra conversa; sem IP ou sem início excluída; país vazio vira "Desconhecido"; **bronze = silver + excluídas**; cada conversa aponta para a linha da bronze |
| `test_variaveis.py` | navegador e sistema sem versão (9 casos); tema do 1º pedido (11 casos); recusa só na abertura da resposta (7 casos); tema e recusa vazios fora do Brasil; duração e tamanhos |
| `test_gold.py` | intervalo de Wilson (valores conhecidos); amostra pequena esconde a taxa; taxa da semana (10 de 40 = 25%); a gold soma o que a silver tem |
| `test_acesso.py` | **nenhuma conta ou senha real no repositório**: sem configuração, uma conta genérica com senha aleatória (mostrada uma vez); a senha da primeira subida é mantida; com `.env`, a senha definida vale e contas fora da lista saem |
| `test_catalogo.py` | o **SQL de referência de cada indicador** (o que o glossário e `docs/INDICADORES.md` mostram) dá o mesmo número que a gold: a fórmula documentada e a consulta executada não se separam (BDR-002) |
| `backend/tests/test_decomposicao.py` | mix + taxa + interação **soma exatamente** a variação (25 casos aleatórios); só o mix; só a taxa; nada mudou; nível que aparece em um mês só |

**Limite declarado:** os testes de tema e recusa fixam o comportamento atual das regras (regressão). Eles **não medem precisão**:
isso vem da amostra manual (`exports/amostra_validacao_*.csv`, `docs/VALIDACAO.md`).

## Prova de que os testes pegam o erro (mutação)
Alterei a definição de propósito e rodei a suíte; cada alteração foi **detectada** (depois revertida):
| Alteração feita | Testes que quebraram |
|---|---|
| gap de sessão 30 → 45 min | 2 (`parâmetros da definição`, `mais de 30 min abre nova sessão`) |
| janela de retorno 7 → 14 dias | 3 (parâmetros, limite de 7 dias, elegibilidade) |
| usuário com user-agent **bruto** (o erro do incidente) | 15 |
| início da conversa = último turno (o erro do incidente) | 4 |

## Duas camadas de proteção
1. **Estes testes** (código): a regra não muda sem quebrar um teste.
2. **O portão do ETL** (dados): a cada carga, 36 conferências comparam a base com os números validados (Power BI e DBeaver) e entre as camadas;
   se algo falhar, a carga é revertida e o dashboard continua no estado anterior.

## Como uma mudança chega à produção (desenho)
1. **Pull request:** roda os 76 testes (`docker compose --profile test run ...`) e o `tsc` do frontend. Sem testes verdes, não faz merge.
2. **Migrações:** arquivos numerados em `db/migrations/`, aplicados em ordem pelo ETL e registrados em `public.schema_migrations`; migração já aplicada nunca é editada (cria-se uma nova).
3. **Ambientes:** `dev` (local, compose), `staging` (cópia na AWS com a mesma semente) e `prod`. A mudança de definição passa por `staging`, onde o portão do ETL compara os números novos com os antigos antes de promover.
4. **Deploy:** imagem nova (ECR) → ECS Fargate; o ETL roda primeiro (migra, carrega, confere); a API só sobe se o portão passar.
5. **Reversão:** a carga é uma transação (se falhar, nada é publicado) e a versão anterior da imagem continua disponível para voltar.