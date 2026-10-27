# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.6.0] - 2026-10-27

### Adicionado
- Módulo `inmet_fetcher.lake` e entry point `quantilica.lake`: conversão direta dos arquivos ZIP anuais do INMET-BDMEP para o lake Parquet com particionamento Hive (`ano=`).
- Comandos CLI `convert` e `pipeline` integrados via SDK do `FetcherApp`, com suporte a `--lake`, `--dataset` e `--force`.
- Extra `analysis` atualizado para `quantilica-analytics>=0.8.0`.
- Dependência de base `quantilica-core` atualizada para `>=0.13.0` para conformidade com o contrato de layout Hive.

## [0.5.1] - 2026-10-20

### Corrigido
- Sem o extra `analysis`, importar `inmet_fetcher.reader`, `inmet_fetcher.schema`
  ou `inmet_fetcher.writer` levanta `ImportError` com a instrução de instalação
  (`uv add 'inmet-fetcher[analysis]' --index https://index.quantilica.com/simple/`)
  em vez de `ModuleNotFoundError` cru de `polars`/`quantilica.analytics`.

## [0.5.0] - 2026-10-20

### Corrigido
- O leitor não lia os arquivos reais do INMET (os testes passavam com fixtures
  sintéticas):
  - Latin-1 decodificado explicitamente; antes, lido de um `ZipExtFile`, o
    encoding era ignorado e 6 das 17 medidas perdiam o nome.
  - Todos os campos lidos como texto e convertidos depois; antes, o tipo era
    inferido em 100 linhas e `,2` (vírgula sem zero) derrubava a leitura.
  - Colunas mapeadas pelo nome do cabeçalho, não pela posição; cabeçalho
    desconhecido, coluna faltando ou repetida levantam `ValueError`.
  - Conversão estrita: valor que não é número nem marca de ausente (`-9999`,
    vazio) levanta `ValueError` em vez de virar nulo.
- ZIP com dois recortes da mesma estação (2026: até 31/08 e até 30/09): só o
  que termina por último é lido; antes os dois eram concatenados.
- `find_zipfiles()`/`read()` leem só a versão mais recente de cada ano
  (`latest_only=True`); antes, todas as versões guardadas na pasta eram
  concatenadas, repetindo horas.
- `read_zipfile()` levanta `ValueError` se sobrar par (estação, hora) repetido.
- README: removidos `inmet.fetch()` e `--engine pandas`, que não existem.

### Alterado
- **Incompatível:** `data_hora` passa a ter fuso UTC (`Datetime(time_zone="UTC")`),
  como diz o cabeçalho dos arquivos; `start`/`end` sem fuso são tratados como UTC.
- `read_station_data()`/`read_zipfile()` aceitam `drop_empty=False` para manter as
  horas em que todas as medidas estão ausentes.
- Extra `analysis` inclui `tzdata` no Windows (base de fusos para o UTC).

### Adicionado
- Testes com o início de dois arquivos reais (layout até 2018 e a partir de 2019).

## [0.4.3] - 2026-10-20

### Corrigido
- `pyproject.toml`: extra `analysis` declara `polars>=1.0.0` e `quantilica-analytics>=0.4.0` explicitamente.
  - Dependência `tqdm>=4.66` declarada explicitamente.
  - `src/inmet_fetcher/py.typed` esvaziado conforme PEP 561.

### Alterado
- `cli.py` protege o import do plugin; sem o host a CLI standalone sai com código 1 e orienta `quantilica install inmet`.

## [0.4.2] - 2026-10-02

### Corrigido
- Remoção da diretiva legada `[tool.hatch.metadata] allow-direct-references = true` em `pyproject.toml` para conformidade estrita com o padrão de publicação PEP 503.

## [0.4.1] - 2026-08-31
### Corrigido
- Quitação de dívida de lint (E501/docstrings longas) herdada dos sweeps de
  documentação de 2026-08-14; nenhum comportamento alterado.

## [0.4.0] - 2026-08-07
### Alterado
- Refatoração arquitetural: Remoção de dependências (`quantilica-cli` e `quantilica-catalog`) e limpeza de imports. Os fetchers agora são pacotes de extração puros, dependendo estritamente do `quantilica-core`.

## [0.2.1] - 2026-05-19

Primeira entrada em formato Keep a Changelog; documenta o estado do pacote nesta
versão.

### Adicionado

- Download paralelo de dados do BDMEP/INMET por ano (`--workers N`), com
  tratamento de codificação `latin-1` e limpeza de cabeçalhos inconsistentes.
- Padronização de colunas em snake_case, combinação de `data` + `hora` em
  `datetime`, tratamento de nulos (`-9999`) e metadados por estação (lat, lon,
  altitude, UF, código WMO).
- CLI `inmet-fetcher` com os subcomandos `sync`, `read` e `stations`; exportação
  para Parquet, CSV ou JSON (pandas e polars).

### Histórico anterior

Versões `v0.1.0`/`v0.1.0.1` (2022-08-30) antecedem a adoção deste changelog e
estão registradas nas tags do repositório.
