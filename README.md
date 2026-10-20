# inmet-fetcher

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square) ![Python](https://img.shields.io/badge/python-3.12+-blue.svg?style=flat-square)

O **inmet-fetcher** é um pacote do ecossistema Quantilica para acessar dados históricos do **BDMEP (Banco de Dados Meteorológicos para Ensino e Pesquisa)** do INMET. Automatiza o download de arquivos ZIP por ano, trata codificações, limpa cabeçalhos e padroniza dados em formato estruturado.

> 📚 **Documentação Completa:** Consulte a documentação oficial do ecossistema em [https://docs.quantilica.com](https://docs.quantilica.com).

---

## Funcionalidades

- **Download paralelo**: Baixe múltiplos anos simultaneamente com `--workers N`
- **Leitura estrita**: Latin-1 decodificado explicitamente, colunas mapeadas pelo nome do cabeçalho (não pela posição), valores ausentes (`-9999` ou campo vazio) viram nulo e qualquer outro valor não numérico levanta `ValueError`
- **Dois layouts**: até 2018 (`AAAA-MM-DD`, `HH:MM`, `-9999`) e a partir de 2019 (`AAAA/MM/DD`, `HHMM UTC`, campo vazio); vírgula decimal sem zero à esquerda (`,2`) lida como `0.2`
- **Datas em UTC**: `data` + `hora` viram `data_hora` (`Datetime` com fuso UTC, como diz o cabeçalho do INMET)
- **Sem horas repetidas**: só a versão mais recente de cada ano é lida, e só o recorte que termina por último quando o ZIP traz dois por estação (ex.: 2026)
- **Colunas em snake_case**: Nomes padronizados, sem caracteres especiais
- **Metadados por estação**: Lat, Lon, Altitude, UF, Código WMO incluídos
- **Filtros na leitura**: Por UF, estação, intervalo de datas
- **Exportação**: Parquet com o contrato `BDMEP_CONTRACT` (Polars)

---

## Instalação

```bash
pip install git+https://github.com/Quantilica/inmet-fetcher.git
```

---

## CLI

O pacote instala o comando `inmet-fetcher` com três subcomandos: `sync`, `read` e `stations`.

### `inmet-fetcher sync` — Baixar dados

```bash
# Um ano
inmet-fetcher sync 2023 -o ./dados

# Intervalo de anos
inmet-fetcher sync 2018:2023 -o ./dados

# Múltiplos anos/intervalos, 8 downloads paralelos
inmet-fetcher sync 2010 2015 2020:2023 -o ./dados --workers 8

# Sem anos, sincroniza todos os anos disponíveis
inmet-fetcher sync -o ./dados
```

### `inmet-fetcher read` — Ler e exportar

```bash
# Exportar tudo em Parquet
inmet-fetcher read -o ./dados --save-as dados.parquet

# Filtrar por UF e ano, exportar CSV
inmet-fetcher read -o ./dados --years 2022:2023 --uf SP,RJ --save-as sp_rj.csv --format csv

# Filtrar por estação e período
inmet-fetcher read -o ./dados --station A701 --start 2020-01-01 --end 2020-12-31 --save-as a701.parquet
```

### `inmet-fetcher stations` — Catálogo de estações

```bash
inmet-fetcher stations -o ./dados --save-as estacoes.csv
```

---

## API Python

A leitura requer o extra `analysis` (Polars). O download é feito pela CLI
(`inmet-fetcher sync`).

```python
from pathlib import Path

import polars as pl

import inmet_fetcher as inmet

data_dir = Path("./dados")

# Ler com filtros (datas sem fuso são tratadas como UTC)
df = inmet.read(
    data_dir,
    years=[2022, 2023],
    uf=["SP", "RJ", "MG"],
    start="2022-06-01",
    end="2023-05-31",
)

# Temperatura média por estado
print(df.group_by("uf").agg(pl.col("temperatura_ar").mean()))

# Catálogo de estações
estacoes = inmet.read_stations(data_dir)
print(estacoes.select("codigo_wmo", "estacao", "uf", "latitude", "longitude"))
```

---

## Colunas Disponíveis

| Coluna | Descrição |
| :--- | :--- |
| `data_hora` | Data e hora em UTC (`Datetime`, fuso UTC) |
| `precipitacao` | Precipitação Total (mm) |
| `pressao_atmosferica` | Pressão ao Nível da Estação (mB) |
| `pressao_atmosferica_maxima` | Pressão Máxima (mB) |
| `pressao_atmosferica_minima` | Pressão Mínima (mB) |
| `radiacao` | Radiação Global (kJ/m²) |
| `temperatura_ar` | Temperatura Bulbo Seco (°C) |
| `temperatura_orvalho` | Temperatura Ponto de Orvalho (°C) |
| `temperatura_maxima` | Temperatura Máxima (°C) |
| `temperatura_minima` | Temperatura Mínima (°C) |
| `umidade_relativa` | Umidade Relativa do Ar (%) |
| `vento_velocidade` | Velocidade do Vento (m/s) |
| `vento_rajada` | Rajada Máxima (m/s) |
| `vento_direcao` | Direção do Vento (°) |
| `estacao` | Nome da Estação |
| `codigo_wmo` | Código WMO da Estação |
| `uf` | Unidade Federativa |
| `latitude` / `longitude` | Coordenadas geográficas |
| `altitude` | Altitude (m) |

---

## Fonte de Dados

Dados obtidos do portal do **Instituto Nacional de Meteorologia (INMET)**: [https://portal.inmet.gov.br/dadoshistoricos](https://portal.inmet.gov.br/dadoshistoricos)

> Use e atribua crédito ao INMET em pesquisas e aplicações.

---

## Desenvolvimento

```bash
git clone https://github.com/Quantilica/inmet-fetcher.git
cd inmet-fetcher
uv sync --dev
uv run pytest
```

## Licença

MIT — veja [LICENSE](LICENSE).
