"""Catalogo dos cenarios de simulacao: o que e plantado, onde o defeito COMECA, que origem o detector deve apontar e as explicacoes
(em linguagem simples) de por que aquilo pode ser uma anomalia de verdade ou um alarme falso. O relatorio em PDF usa estes textos.

Campos: camada    onde o defeito comeca (bronze | silver | gold | codigo | nenhuma)
        semente   pasta em /data/cenarios, ou "oficial" (a semente do repositorio)
        esperada  origem que o detector deve apontar (None = nenhum alerta para o Brasil)
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Cenario:
    nome: str
    camada: str
    titulo: str
    defeito: str                      # o que foi plantado, em uma frase
    semente: str
    esperada: str | None
    anomalia_real: str                # por que isto pode ser um problema de verdade
    alarme_falso: str                 # por que isto pode ser um alarme falso
    verificar: list[str] = field(default_factory=list)
    avaliar_semanal: bool = False     # True: o resultado do teste inclui o ALERTA SEMANAL (esperada_semanal = diagnostico esperado, None = nenhum alerta novo)
    esperada_semanal: str | None = None


CATALOGO: dict[str, Cenario] = {c.nome: c for c in [
    # ------------------------------------------------------------------ o incidente do PDF (4.2): navegador atualiza e a pessoa e contada em duplicidade
    Cenario(
        "incidente_navegador", "silver", "Incidente do PDF: o navegador atualiza e a mesma pessoa vira várias",
        "O Chrome passa a lançar versão nova a cada 4 semanas (o texto do user-agent muda para todos os usuários de Chrome) e a regra de pessoa da silver volta a usar o "
        "user-agent bruto, com a versão: o erro do incidente do PDF.",
        "navegador_atualiza", "SILVER",
        "Quem já usava o produto passa a ser contado como gente nova a cada atualização do navegador: as pessoas sobem sem ninguém voltar a mais, e a taxa cai. É o mecanismo "
        "do incidente do PDF (retorno de 31% para 18%). A pista mais direta é 'pessoas por endereço': normalmente perto de 1, sobe quando o mesmo endereço vira várias pessoas "
        "(no incidente, 2.385 endereços viraram 2.895 pessoas).",
        "Pode ser real se o produto passou a ser usado por várias pessoas no mesmo endereço (escola, empresa, rede compartilhada). Nesse caso a mudança é gradual e acompanha o "
        "volume; se for súbita e coincidir com uma atualização de navegador, é mais provável que seja a regra de pessoa. Como o defeito está no código, ele afeta todos os países: "
        "nos grandes (Estados Unidos, Alemanha, Canadá, Reino Unido) o alerta semanal aponta PESSOA_DIVIDIDA; no Brasil, que tem poucas dezenas de novos por semana, "
        "quem o pega é a comparação entre cargas ('pessoas por endereço').",
        ["Ver os alertas: SELECT * FROM auditoria.anomalia_semanal WHERE nova AND diagnostico = 'PESSOA_DIVIDIDA' ORDER BY pais, semana;",
         "Conferir a regra de pessoa: UA_NORM_SQL em etl/comum/definicoes.py (deve tirar a versão do navegador).",
         "Rodar test_incidente.py: o teste dourado do incidente deve quebrar se a regra voltar a usar o user-agent bruto."],
        avaliar_semanal=True, esperada_semanal="PESSOA_DIVIDIDA"),
    Cenario(
        "incidente_navegador_corrigido", "nenhuma", "O mesmo navegador atualizando, com a regra de pessoa correta (a correção do incidente)",
        "A mesma semente do cenário anterior (Chrome atualizando a cada 4 semanas), mas com o código atual, que tira a versão do navegador da regra de pessoa.",
        "navegador_atualiza", None,
        "Este cenário mostra a correção funcionando: as atualizações de navegador não criam pessoas novas, então os números ficam estáveis e nenhum alerta aparece.",
        "Se aparecesse um alerta aqui, seria um alarme falso do detector, ou a correção teria deixado de funcionar.",
        ["Nenhuma ação: o resultado esperado é não ter alerta (nem por carga, nem semanal)."],
        avaliar_semanal=True, esperada_semanal=None),
    Cenario(
        "pico_de_novos_semana", "bronze", "Pico de uma semana: os novos triplicam e ninguém volta a mais",
        "Em uma semana (08/04/2024), a fonte envia cada endereço da semana mais três vezes, com endereços falsos de uma conversa só (por exemplo, um robô ou uma duplicação "
        "na origem). É o formato do incidente do PDF: os 'novos' de uma semana disparam e os que voltaram ficam iguais.",
        "pico_de_novos", None,
        "Uma semana com muito mais 'novos' do que as anteriores, e sem ninguém voltar a mais, infla o denominador: a taxa da semana cai sem que o comportamento tenha mudado. "
        "Na média do país o pico some (um ano de dados), por isso só o alerta semanal enxerga.",
        "Pode ser real se uma campanha ou uma reportagem trouxe muita gente nova de uma vez. Nesse caso os que voltaram costumam subir um pouco depois, e os endereços são "
        "realmente inéditos; o alerta semanal diferencia: se quem voltou sobe junto, o diagnóstico é 'pico de uso', não 'denominador inflado'.",
        ["Ver as semanas: SELECT * FROM auditoria.anomalia_semanal WHERE nova ORDER BY semana;",
         "Comparar as linhas da bronze por semana e procurar endereços que só aparecem uma vez naquela semana.",
         "Perguntar ao produto se houve campanha ou lançamento naquela semana."],
        avaliar_semanal=True, esperada_semanal="DENOMINADOR_INFLADO"),
    # ------------------------------------------------------------------ comeca na BRONZE (o dado de entrada)
    Cenario(
        "bronze_sem_endereco", "bronze", "60% das conversas do Brasil chegam sem endereço",
        "A fonte passou a mandar 60% das conversas do Brasil sem o endereço anonimizado (IP), como se o sistema de origem tivesse falhado.",
        "sem_endereco", "BRONZE",
        "Sem endereço não dá para saber quem é a pessoa. A silver descarta essas conversas e o país encolhe (menos pessoas e menos elegíveis), então "
        "os números do painel passam a representar um grupo menor e diferente. A taxa quase não muda, e por isso o problema passaria despercebido "
        "se olhássemos só a taxa.",
        "Pode ser legítimo se a fonte passou a anonimizar mais (mudança de política de privacidade) ou se um período foi coletado sem rastreio. "
        "O dado é menor, mas não está errado por causa do ETL. Confirme com quem mantém a fonte antes de mexer em qualquer regra.",
        ["Conferir os arquivos de origem e o sha256 em ops.bronze_lote.",
         "SELECT count(*) FILTER (WHERE hashed_ip IS NULL) FROM bronze.wildchat WHERE country = 'Brazil';",
         "Perguntar à fonte se algo mudou na coleta."]),
    Cenario(
        "bronze_volume_cai", "bronze", "A fonte entrega só 40% das conversas do Brasil",
        "Faltam 60% das conversas do Brasil no arquivo de entrada (perda de dados no envio).",
        "volume_cai", "BRONZE",
        "Faltam conversas no meio da história de cada pessoa: quem voltou deixa de parecer que voltou (a segunda visita sumiu). A taxa cai por falta "
        "de dado, não por mudança de comportamento. A pista é o número de linhas do país despencar na bronze.",
        "Pode ser real se o uso do produto no país caiu de verdade (feriado, fim de campanha). Compare com o volume dos outros países na mesma carga: "
        "se só um país caiu muito, desconfie da fonte; se todos caíram, pode ser sazonalidade.",
        ["Comparar linhas por país com a carga anterior: SELECT * FROM auditoria.historico_metrica WHERE camada = 'bronze' AND metrica = 'linhas_por_pais'.",
         "Ver se o tamanho do arquivo de origem mudou (ops.bronze_lote)."]),
    Cenario(
        "bronze_sem_horario", "bronze", "50% das conversas do Brasil chegam sem horário de início",
        "A fonte passou a mandar 50% das conversas do Brasil sem o horário da primeira resposta.",
        "sem_horario", "BRONZE",
        "Sem horário não há como ordenar as visitas nem medir os 7 dias de retorno. A silver descarta essas conversas, o país encolhe e as pessoas "
        "que sobram têm histórias incompletas.",
        "Pode ser legítimo se um tipo novo de conversa (por exemplo, vinda de uma integração automática) não registra horário. O dado é de fato "
        "incompleto, mas a causa é de produto, não de erro do ETL.",
        ["SELECT count(*) FILTER (WHERE primeira_resposta_ts IS NULL) FROM bronze.wildchat WHERE country = 'Brazil';",
         "Ver os motivos de exclusão: SELECT motivo, count(*) FROM auditoria.registro_excluido GROUP BY 1;"]),
    # ------------------------------------------------------------------ comeca na SILVER (limpeza e regras)
    Cenario(
        "silver_elegibilidade", "silver", "A regra de elegibilidade da silver erra",
        "A silver passa a marcar como não elegíveis 80% dos usuários que não voltaram (um erro de código na regra de elegibilidade).",
        "nova", "SILVER",
        "O denominador da taxa (quem conta) encolhe só para quem não voltou, então a taxa sobe sem ninguém ter voltado a mais. A entrada e a gold "
        "estavam normais: o erro está na regra da silver.",
        "Seria legítimo se a definição de elegível mudou de propósito (por exemplo, janela de 7 para 14 dias) e a mudança foi documentada. Nesse "
        "caso, atualize os números validados depois de conferir à mão e registre a decisão.",
        ["Recalcular a elegibilidade a partir das conversas: o recálculo independente (silver_independente) já aponta a divergência.",
         "Olhar o último commit em etl/camadas/silver/sql.py e etl/comum/definicoes.py."]),
    Cenario(
        "silver_retorno_inflado", "silver", "A regra de retorno da silver marca retornos que não existiram",
        "A silver passa a marcar como 'voltou em 7 dias' 30% de quem não voltou (por exemplo, um erro ao contar as visitas).",
        "nova", "SILVER",
        "O numerador infla: a taxa quase dobra sem nenhuma pessoa a mais voltar. A pista é que, entre os que 'voltaram', a proporção dos que voltaram "
        "em 24 horas despenca, porque os retornos novos não existem de verdade.",
        "Pode ser real se uma funcionalidade nova (notificação, e-mail) trouxe muita gente de volta. Nesse caso a proporção de 24 horas costuma "
        "permanecer parecida; se ela mudou muito, é mais provável que seja a regra. O detector só tem essa pista: um erro de retorno que preserve "
        "a proporção de 24 horas seria apontado como 'sem causa técnica'.",
        ["Recalcular os retornos a partir das conversas (silver_interna e silver_independente).",
         "Comparar a taxa de 24 horas com a de 7 dias nas duas cargas."]),
    Cenario(
        "silver_limpeza_exagerada", "silver", "A limpeza da silver descarta metade das conversas",
        "Um filtro novo da silver passa a descartar 50% das conversas do Brasil, apesar de a entrada ter chegado completa.",
        "nova", "SILVER",
        "A entrada está completa, mas metade das conversas não chega à silver. A taxa quase não muda (as pessoas continuam existindo), o que torna "
        "o problema silencioso: os volumes e os gráficos de uso diminuem sem aviso.",
        "Seria legítimo se uma regra de qualidade nova passou a excluir conversas inválidas de propósito (testes automáticos, robôs). Os motivos "
        "ficam em auditoria.registro_excluido: se o motivo novo é conhecido e documentado, é alarme falso.",
        ["SELECT motivo, count(*) FROM auditoria.registro_excluido GROUP BY 1;",
         "Conferir bronze = silver + excluídas (bronze_silver)."]),
    # ------------------------------------------------------------------ comeca na GOLD (o resumo que a tela le)
    Cenario(
        "gold_numerador", "gold", "A gold triplica quem voltou",
        "A agregação da gold passa a multiplicar por 3 o número de pessoas que voltaram no Brasil. A silver continua certa.",
        "nova", "GOLD",
        "A silver está certa, mas a tabela que o painel lê diz outra coisa: o usuário vê um número que não existe nos dados.",
        "Quase nunca é alarme falso: a gold e a silver contam a mesma coisa por construção. Se divergem, é erro de agregação (ou alguém alterou a "
        "tabela por fora: veja auditoria.verificacao).",
        ["Comparar gold.pais com silver.fato_usuario (as conferências silver_gold já fazem isso).",
         "Olhar etl/camadas/gold/sql.py e SELECT * FROM auditoria.verificacao ORDER BY id DESC;"]),
    Cenario(
        "gold_denominador", "gold", "A gold reduz pela metade os elegíveis",
        "A agregação da gold passa a dividir por 2 o número de elegíveis do Brasil. A silver continua certa.",
        "nova", "GOLD",
        "O denominador mostrado no painel fica menor que o real, e a taxa sobe sem motivo. O painel mostraria 'X de Y' que não bate com os dados.",
        "Quase nunca é alarme falso, pelo mesmo motivo do cenário anterior: a gold é um resumo da silver e tem de bater com ela.",
        ["As conferências silver_gold (elegíveis por país) falham.", "Olhar etl/camadas/gold/sql.py."]),
    Cenario(
        "gold_pais_trocado", "gold", "A gold troca os números do Brasil pelos de outro país",
        "A gold grava no Brasil os números de elegíveis e de retorno de outro país (um erro de junção).",
        "nova", "GOLD",
        "Um erro de junção faz um país herdar os números de outro. É perigoso porque os números parecem plausíveis. O Brasil continua certo na "
        "silver; só a gold está trocada.",
        "Não costuma ser alarme falso. Se os dois países tiverem taxas parecidas, o salto da taxa seria pequeno e o alerta só viria pelas "
        "conferências silver_gold.",
        ["SELECT pais, usuarios_elegiveis, voltaram_7d FROM gold.pais ORDER BY 1;",
         "Comparar com SELECT pais, count(*) FILTER (WHERE elegivel) FROM silver.fato_usuario GROUP BY 1;"]),
    # ------------------------------------------------------------------ outros
    Cenario(
        "codigo_mudou", "codigo", "Mesmos arquivos de entrada e o código do ETL mudou",
        "A semente é exatamente a mesma da carga anterior, mas a regra de elegibilidade do código foi alterada.",
        "oficial", "TRANSFORMACAO",
        "Com os mesmos arquivos, o resultado tem de ser idêntico. Se mudou, alguém alterou uma regra, um parâmetro ou o código.",
        "É legítimo quando a mudança foi intencional (uma decisão de negócio registrada em BDR). O alerta, nesse caso, só confirma que a mudança "
        "teve o efeito esperado.",
        ["Ver o último commit e auditoria.mudancas_entre_cargas.", "Se foi intencional, atualizar os números validados depois de conferir à mão."]),
    Cenario(
        "controle_sem_defeito", "nenhuma", "Dados novos e saudáveis (controle)",
        "Chega uma semente nova, quase igual à anterior (1 conversa a menos), sem nenhum defeito.",
        "nova", None,
        "Não há problema: este cenário serve para provar que o detector não alarma à toa quando chegam dados novos e saudáveis.",
        "Se aparecesse um alerta aqui, seria um alarme falso do próprio detector (limites sensíveis demais).",
        ["Nenhuma ação: o resultado esperado é não ter alerta para o Brasil."]),
]}

CAMADA_TITULO = {"bronze": "BRONZE (o dado de entrada)", "silver": "SILVER (limpeza e regras)", "gold": "GOLD (o resumo que a tela lê)",
                 "codigo": "O CÓDIGO DO ETL", "nenhuma": "NENHUMA (controle)"}
