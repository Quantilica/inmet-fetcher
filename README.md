# 🌧️ INMET BDMEP Data: Dados Meteorológicos do Brasil ao seu alcance

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

O **inmet-bdmep-data** é uma ferramenta para desenvolvedores, cientistas e analistas de dados brasileiros que precisam acessar o **BDMEP (Banco de Dados Meteorológicos para Ensino e Pesquisa)** do INMET.

Esqueça o trabalho braçal de baixar dezenas de arquivos ZIP manualmente, lidar com codificações `latin-1`, limpar cabeçalhos inconsistentes e padronizar nomes de colunas. Este pacote faz o trabalho sujo.

---

## ✨ Funcionalidades

- 📥 **Download paralelo**: Baixe múltiplos anos simultaneamente com `--workers N`
- 🧹 **Limpeza automática**: Remove linhas vazias e trata valores nulos (`-9999`)
- 🕒 **Padronização de datas**: Combina `data` + `hora` em `datetime` nativo
- 🏷️ **Colunas em snake_case**: Nomes padronizados, sem caracteres especiais
- 🗺️ **Metadados por estação**: Lat, Lon, Altitude, UF, Código WMO incluídos
- 🔍 **Filtros na leitura**: Por UF, estação, intervalo de datas
- 💾 **Exportação**: Parquet, CSV ou JSON
- 🐼 **pandas** e **polars** suportados

---

## 🚀 Instalação

```bash
pip install git+https://github.com/dankkom/inmet-bdmep-data.git
```

---

## 🛠️ CLI

O pacote instala o comando `inmet` com três subcomandos.

### `inmet fetch` — Baixar dados

```bash
# Um ano
inmet fetch 2023 --data-dir ./dados

# Intervalo de anos
inmet fetch 2018:2023 --data-dir ./dados

# Múltiplos anos/intervalos, 8 downloads paralelos
inmet fetch 2010 2015 2020:2023 --data-dir ./dados --workers 8
```

### `inmet read` — Ler e exportar

```bash
# Exportar tudo em Parquet
inmet read --data-dir ./dados --output dados.parquet

# Filtrar por UF e ano, exportar CSV
inmet read --data-dir ./dados --years 2022:2023 --uf SP,RJ --output sp_rj.csv --format csv

# Filtrar por estação e período
inmet read --data-dir ./dados --station A701 --start 2020-01-01 --end 2020-12-31 --output a701.parquet

# Usar polars como engine
inmet read --data-dir ./dados --uf MG --output mg.parquet --engine polars
```

### `inmet stations` — Catálogo de estações

```bash
# Listar todas as estações
inmet stations --data-dir ./dados --output estacoes.csv
```

---

## 🐍 API Python

```python
import inmet_bdmep as inmet
from pathlib import Path

data_dir = Path("./dados")

# Baixar anos com 4 workers
inmet.fetch([2020, 2021, 2022, 2023], data_dir, workers=4)

# Ler com filtros
df = inmet.read(
    data_dir,
    years=[2022, 2023],
    uf=["SP", "RJ", "MG"],
    start="2022-06-01",
    end="2023-05-31",
)

# Temperatura média por estado
print(df.groupby("uf")["temperatura_ar"].mean())

# Catálogo de estações
estacoes = inmet.read_stations(data_dir)
print(estacoes[["codigo_wmo", "estacao", "uf", "latitude", "longitude"]])
```

---

## 📊 Colunas Disponíveis

| Coluna | Descrição |
| :--- | :--- |
| `data_hora` | Data e hora (Timestamp) |
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

## 📖 Fonte de Dados

Dados obtidos do portal do **Instituto Nacional de Meteorologia (INMET)**: [https://portal.inmet.gov.br/dadoshistoricos](https://portal.inmet.gov.br/dadoshistoricos)

> Use e atribua crédito ao INMET em pesquisas e aplicações.

---

## 📄 Licença

[MIT](LICENSE)
