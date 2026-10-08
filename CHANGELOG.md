# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Não lançado]

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
