---
dataset:
  id: bdmep
  fonte: inmet
  titulo: Dados históricos horários das estações automáticas (BDMEP)
  resumo: Observações meteorológicas horárias das estações automáticas do INMET, uma linha por estação e hora, com os metadados da estação.
  orgao: Instituto Nacional de Meteorologia (INMET)
  pagina_oficial: https://portal.inmet.gov.br/dadoshistoricos
  licenca: "não informado pela fonte; a página de dados históricos não traz licença nem termo de uso (conferido em 2026-11-09)"
  periodicidade: um arquivo por ano, o do ano corrente republicado ao longo do ano (o de 2026 estava marcado "Até 31/10/2026")
  cobertura: {inicio: 2000, fim: em-curso}
  unidade: uma estação em uma hora (UTC)
  granularidade: {espacial: estação meteorológica, temporal: hora}
  formato_bruto: ZIP anual com um CSV por estação, Latin-1, separador ponto e vírgula, vírgula decimal, oito linhas de metadados antes do cabeçalho
  lake: {estado: convertido, particoes: [ano], chave: [codigo_wmo, data_hora], colunas: 26}
  unidades_de_medida:
    precipitacao: mm
    pressao_atmosferica: mB
    pressao_atmosferica_maxima: mB
    pressao_atmosferica_minima: mB
    radiacao: kJ/m²
    temperatura_ar: °C
    temperatura_orvalho: °C
    temperatura_maxima: °C
    temperatura_minima: °C
    temperatura_orvalho_maxima: °C
    temperatura_orvalho_minima: °C
    umidade_relativa_maxima: "%"
    umidade_relativa_minima: "%"
    umidade_relativa: "%"
    vento_direcao: graus
    vento_rajada: m/s
    vento_velocidade: m/s
    latitude: graus decimais
    longitude: graus decimais
    altitude: m
  dados_pessoais: nenhum
  eras:
    - {desde: "2019", mudanca: "Layout do CSV: data AAAA/MM/DD e hora HHMM UTC, valor ausente em branco; até 2018, data AAAA-MM-DD, hora HH:MM e valor ausente -9999"}
  revisado_em: 2026-11-09
  versao_fetcher: 0.6.2
---

# Dados históricos horários das estações automáticas (BDMEP)

## Resumo

Série horária das estações meteorológicas automáticas do INMET: precipitação, pressão atmosférica, radiação global, temperatura do ar e do ponto de orvalho (com máximas e mínimas da hora anterior), umidade relativa e vento. Cada linha traz também os metadados da estação (região, UF, nome, código WMO, coordenadas, altitude e data de fundação). Serve para estudos de clima e tempo por estação.

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `inmet/bdmep` |
| Órgão | Instituto Nacional de Meteorologia (INMET) |
| Página oficial | https://portal.inmet.gov.br/dadoshistoricos |
| Licença | não informado pela fonte; a página de dados históricos não traz licença nem termo de uso (conferido em 2026-11-09) |
| Periodicidade | um arquivo por ano, o do ano corrente republicado ao longo do ano (o de 2026 estava marcado "Até 31/10/2026") |
| Cobertura | 2000 a em-curso |
| Unidade (uma linha) | uma estação em uma hora (UTC) |
| Granularidade | espacial: estação meteorológica; temporal: hora |
| Formato bruto | ZIP anual com um CSV por estação, Latin-1, separador ponto e vírgula, vírgula decimal, oito linhas de metadados antes do cabeçalho |
| Estado no lake | convertido |
| Partições | `ano` |
| Chave | `codigo_wmo`, `data_hora` |
| Colunas | 26 |
| Unidades de medida | `precipitacao`: mm; `pressao_atmosferica`: mB; `pressao_atmosferica_maxima`: mB; `pressao_atmosferica_minima`: mB; `radiacao`: kJ/m²; `temperatura_ar`: °C; `temperatura_orvalho`: °C; `temperatura_maxima`: °C; `temperatura_minima`: °C; `temperatura_orvalho_maxima`: °C; `temperatura_orvalho_minima`: °C; `umidade_relativa_maxima`: %; `umidade_relativa_minima`: %; `umidade_relativa`: %; `vento_direcao`: graus; `vento_rajada`: m/s; `vento_velocidade`: m/s; `latitude`: graus decimais; `longitude`: graus decimais; `altitude`: m |
| Dados pessoais | nenhum |
| Eras | 2019: Layout do CSV: data AAAA/MM/DD e hora HHMM UTC, valor ausente em branco; até 2018, data AAAA-MM-DD, hora HH:MM e valor ausente -9999 |
| Revisado em | 2026-11-09 |
| Versão do fetcher | 0.6.2 |

## Origem e coleta

- O fetcher baixa do portal de dados históricos do INMET um ZIP por ano (`https://portal.inmet.gov.br/uploads/dadoshistoricos/<AAAA>.zip`). No bruto, cada arquivo é `inmet-bdmep_<AAAA>@<AAAAMMDD>.zip`, com a data da coleta; versões novas do mesmo ano ficam lado a lado.
- O ZIP do ano corrente é republicado e cada versão traz o ano inteiro até a data de corte. Na conversão só a versão mais recente do ano é lida, para não repetir horas.
- Cada ZIP traz um CSV por estação, com nome `INMET_<região>_<UF>_<código>_<estação>_<início>_A_<fim>.CSV`. Quando o ZIP traz dois recortes da mesma estação (houve o caso em 2026), o conversor mantém o que termina por último.
- Linhas em que todas as medidas estão ausentes são descartadas.

## Conteúdo

- Uma linha por estação e hora (UTC). Os cabeçalhos dos CSV dizem "Hora UTC".
- Cobertura anunciada: 2000 até o ano corrente (o portal lista os anos de 2000 a 2026; o de 2026 está marcado "Até 31/10/2026"). Conferido em 2026-11-09 pela listagem do bruto: um ZIP por ano de 2000 a 2026 (2026 com duas versões coletadas).
- Conferido numa amostra convertida (anos 2000, 2018, 2019 e 2026): 5 estações em 2000 (com dados a partir de 2000-05-07), 592 em 2018, 588 em 2019 e 565 em 2026 (até 2026-10-31 23:00 UTC). O número de estações varia de um ano para o outro.
- Era: até 2018 o CSV usa data `AAAA-MM-DD`, hora `HH:MM` e `-9999` para valor ausente; desde 2019, data `AAAA/MM/DD`, hora `HHMM UTC` e campo vazio. O conversor trata os dois e o resultado no lake é igual.

## Variáveis

As descrições vêm dos cabeçalhos dos próprios CSV do INMET (conferidos nos arquivos de 2000, 2018 e 2026). A página do INMET não traz dicionário de variáveis; o significado de "hora anterior" nas medidas máxima e mínima é o do cabeçalho ("NA HORA ANT. (AUT)"), sem detalhe adicional pela fonte.

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `precipitacao` | `PRECIPITAÇÃO TOTAL, HORÁRIO` | decimal | Precipitação total horária | mm | todo |
| `pressao_atmosferica` | `PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA` | decimal | Pressão atmosférica ao nível da estação, horária | mB | todo |
| `pressao_atmosferica_maxima` | `PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT)` | decimal | Pressão atmosférica máxima na hora anterior | mB | todo |
| `pressao_atmosferica_minima` | `PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT)` | decimal | Pressão atmosférica mínima na hora anterior | mB | todo |
| `radiacao` | `RADIACAO GLOBAL` | decimal | Radiação global | kJ/m² (o cabeçalho escreve `Kj/m²`) | todo |
| `temperatura_ar` | `TEMPERATURA DO AR - BULBO SECO, HORARIA` | decimal | Temperatura do ar, bulbo seco, horária | °C | todo |
| `temperatura_orvalho` | `TEMPERATURA DO PONTO DE ORVALHO` | decimal | Temperatura do ponto de orvalho | °C | todo |
| `temperatura_maxima` | `TEMPERATURA MÁXIMA NA HORA ANT. (AUT)` | decimal | Temperatura máxima na hora anterior | °C | todo |
| `temperatura_minima` | `TEMPERATURA MÍNIMA NA HORA ANT. (AUT)` | decimal | Temperatura mínima na hora anterior | °C | todo |
| `temperatura_orvalho_maxima` | `TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT)` | decimal | Temperatura máxima do ponto de orvalho na hora anterior | °C | todo |
| `temperatura_orvalho_minima` | `TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT)` | decimal | Temperatura mínima do ponto de orvalho na hora anterior | °C | todo |
| `umidade_relativa_maxima` | `UMIDADE REL. MAX. NA HORA ANT. (AUT)` | decimal | Umidade relativa máxima na hora anterior | % | todo |
| `umidade_relativa_minima` | `UMIDADE REL. MIN. NA HORA ANT. (AUT)` | decimal | Umidade relativa mínima na hora anterior | % | todo |
| `umidade_relativa` | `UMIDADE RELATIVA DO AR, HORARIA` | decimal | Umidade relativa do ar, horária | % | todo |
| `vento_direcao` | `VENTO, DIREÇÃO HORARIA (gr)` | decimal | Direção do vento, horária | graus (°) | todo |
| `vento_rajada` | `VENTO, RAJADA MAXIMA` | decimal | Rajada máxima do vento | m/s | todo |
| `vento_velocidade` | `VENTO, VELOCIDADE HORARIA` | decimal | Velocidade do vento, horária | m/s | todo |
| `data_hora` | `Data` + `Hora UTC` | data e hora com fuso | Momento da observação | UTC | todo |
| `regiao` | `REGIAO:` | texto | Região da estação | `N`, `NE`, `CO`, `SE`, `S` (conferido na amostra) | todo |
| `uf` | `UF:` | texto | Unidade da Federação da estação | sigla (27 valores na amostra) | todo |
| `estacao` | `ESTACAO:` | texto | Nome da estação | — | todo |
| `codigo_wmo` | `CODIGO (WMO):` | texto | Código da estação (formato `A001`, `S102`...) | — | todo |
| `latitude` | `LATITUDE:` | decimal | Latitude da estação | graus decimais | todo |
| `longitude` | `LONGITUDE:` | decimal | Longitude da estação | graus decimais | todo |
| `altitude` | `ALTITUDE:` | decimal | Altitude da estação; nulo quando o campo não é numérico no arquivo | m | todo |
| `data_fundacao` | `DATA DE FUNDACAO:` | data e hora sem fuso | Data de fundação da estação (sempre à meia-noite); o arquivo de 2000 a escreve com ano de dois dígitos (`07/05/00`) | — | todo |
| `ano` | nome do arquivo | inteiro | Ano do ZIP de origem; é a partição | — | todo |

## No lake

- Dataset `inmet/bdmep`, particionado por `ano`; um Parquet por ano.
- Todas as medidas viram decimal de 64 bits. Vírgula decimal vira ponto; `,2` e `-,5` (sem zero à esquerda) valem `0.2` e `-0.5`.
- Valor ausente (`-9999` ou campo vazio) vira nulo. Qualquer outro valor não numérico faz a conversão do ano falhar, em vez de virar nulo.
- Os nomes das medidas são reconhecidos pelo cabeçalho (prefixo sem acento), não pela posição; cabeçalho desconhecido ou repetido falha a conversão.
- `Data` e `Hora UTC` viram `data_hora`, com fuso UTC. Não pode haver duas linhas com a mesma estação e hora no ano; se houver, a conversão falha.
- Os metadados da estação (oito linhas do topo do CSV) viram colunas repetidas em todas as linhas da estação.
- Linhas com todas as medidas ausentes são descartadas, por isso uma estação pode ter horas faltando.

## Cuidados de uso

- **Fuso.** `data_hora` está em UTC; para a hora local do Brasil, converta (a maior parte do país está em UTC−3).
- **Valores ausentes.** Há muitos nulos, em proporção que varia por coluna e ano. Na amostra de 2018, por exemplo, `radiacao` é nula em 2.045.405 de 4.632.236 linhas e `precipitacao` em 241.285; em 2000 `radiacao` é nula em 9.257 de 19.827 linhas. Calcule médias sobre os valores presentes e não trate nulo como zero.
- **Valores atípicos.** A conversão não aplica nenhum filtro de qualidade. Na amostra (2000, 2018, 2019, 2026) há `temperatura_orvalho` de −36,0 °C e `temperatura_ar` mínima de −8,0 °C, `radiacao` de até 47.976,8 e `precipitacao` de até 96,6 mm numa hora; confira esses extremos antes de usar. O INMET não informa se os dados passaram por controle de qualidade.
- **Altitude nula.** Na amostra de 2018, 52.308 linhas têm `altitude` nula e na de 2026, 6.122; em 2000 e 2019 nenhuma. Há também registros com `altitude` igual a 0,0. Não use a altitude como se estivesse sempre preenchida.
- **Máximas e mínimas "da hora anterior".** As colunas `*_maxima` e `*_minima` seguem o cabeçalho do INMET e se referem à hora anterior; a fonte não detalha mais que isso.
- **Ano corrente parcial.** O ZIP do ano corrente cobre só até a data de corte; não compare totais anuais do ano em curso com os de anos fechados.
- **Cobertura desigual.** O número de estações varia muito por ano (5 em 2000 e de 565 a 592 nos demais anos da amostra); séries de médias do país mudam de composição.
- Conferências feitas em 2026-11-09, com o fetcher 0.6.2, sobre uma amostra de quatro anos convertida localmente.

## Exemplos

Temperatura média, mínima e máxima do ar por UF em 2023, sobre os valores presentes:

```python
import polars as pl

obs = pl.scan_parquet("lake/inmet/bdmep/**/*.parquet", hive_partitioning=True)
por_uf = (
    obs.filter(pl.col("ano") == 2023)
    .group_by("uf")
    .agg(
        pl.col("temperatura_ar").mean().alias("media"),
        pl.col("temperatura_ar").min().alias("minima"),
        pl.col("temperatura_ar").max().alias("maxima"),
        pl.col("temperatura_ar").count().alias("medicoes"),
    )
    .sort("uf")
    .collect()
)
```

## Referências

- Dados históricos do INMET: https://portal.inmet.gov.br/dadoshistoricos
