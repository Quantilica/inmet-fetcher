# INMET — Banco de Dados Meteorológicos (`inmet`)

O `inmet-fetcher` coleta os dados históricos horários das estações meteorológicas automáticas do Instituto Nacional de Meteorologia (INMET), publicados no portal de dados históricos do instituto, e os converte para o lake em Parquet particionado por ano.

| Dataset | O que é | Origem | Período | Página |
|---|---|---|---|---|
| `bdmep` | Observações horárias das estações automáticas: precipitação, pressão, radiação, temperatura, umidade e vento, com os metadados da estação | ZIP anual do portal de dados históricos do INMET | 2000 em diante | [bdmep](datasets/bdmep.md) |

## Como o INMET publica

- O portal [dados históricos](https://portal.inmet.gov.br/dadoshistoricos) lista um arquivo ZIP por ano, rotulado "automática". A página não traz descrição das variáveis, licença ou termo de uso (conferido em 2026-11-09).
- Cada ZIP contém um CSV por estação, com oito linhas de metadados no topo e uma linha por hora.
- O ZIP do ano corrente é republicado ao longo do ano e cada versão traz o ano inteiro até a data de corte (o de 2026 estava marcado "Até 31/10/2026" em 2026-11-09). O fetcher guarda cada versão baixada com a data de coleta no nome (`<arquivo>@AAAAMMDD`); o lake converte a versão mais recente.

## Quebras que valem para o conjunto

| Desde | Mudança |
|---|---|
| 2019 | Layout do CSV: datas `AAAA/MM/DD` e hora `HHMM UTC`, com valor ausente em branco; até 2018 a data era `AAAA-MM-DD`, a hora `HH:MM` e o valor ausente `-9999` |
