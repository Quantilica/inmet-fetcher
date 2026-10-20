"""Reading and parsing logic for INMET BDMEP data.

Each annual ZIP holds one CSV per station: Latin-1, ``;`` separator, eight
metadata lines (``REGIAO:;N``...), a header line and one line per hour, each
ending with ``;``. Two layouts coexist:

- until 2018: ``AAAA-MM-DD`` / ``HH:MM`` and missing values as ``-9999``;
- from 2019: ``AAAA/MM/DD`` / ``HHMM UTC`` and missing values as empty fields.

Decimals use a comma and may omit the leading zero (``,2``, ``-,5``). The
reader decodes Latin-1 explicitly, reads every field as text, maps the
columns by header name (not by position) and converts strictly: a value that
is neither a number nor a missing-value marker raises ``ValueError`` instead
of becoming null. ``data_hora`` is UTC, as the header states.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import IO

import polars as pl
from tqdm import tqdm

from .storage import DataRepository

# Prefixo do cabeçalho já normalizado (sem acento, minúsculo) → coluna. Os
# cabeçalhos variam entre anos (acentos, espaço depois de "MAX."), por isso
# o casamento é por prefixo normalizado e cada coluna deve aparecer uma vez.
_COL_PREFIXES = [
    ("data", "data"),
    ("hora", "hora"),
    ("precipitacao total", "precipitacao"),
    ("pressao atmosferica ao nivel", "pressao_atmosferica"),
    ("pressao atmosferica max", "pressao_atmosferica_maxima"),
    ("pressao atmosferica min", "pressao_atmosferica_minima"),
    ("radiacao global", "radiacao"),
    ("temperatura do ar", "temperatura_ar"),
    ("temperatura do ponto de orvalho", "temperatura_orvalho"),
    ("temperatura maxima", "temperatura_maxima"),
    ("temperatura minima", "temperatura_minima"),
    ("temperatura orvalho max", "temperatura_orvalho_maxima"),
    ("temperatura orvalho min", "temperatura_orvalho_minima"),
    ("umidade rel. max", "umidade_relativa_maxima"),
    ("umidade rel. min", "umidade_relativa_minima"),
    ("umidade relativa do ar", "umidade_relativa"),
    ("vento, direcao", "vento_direcao"),
    ("vento, rajada", "vento_rajada"),
    ("vento, velocidade", "vento_velocidade"),
]

_MEASURE_COLS = [
    "precipitacao",
    "pressao_atmosferica",
    "pressao_atmosferica_maxima",
    "pressao_atmosferica_minima",
    "radiacao",
    "temperatura_ar",
    "temperatura_orvalho",
    "temperatura_maxima",
    "temperatura_minima",
    "temperatura_orvalho_maxima",
    "temperatura_orvalho_minima",
    "umidade_relativa_maxima",
    "umidade_relativa_minima",
    "umidade_relativa",
    "vento_direcao",
    "vento_rajada",
    "vento_velocidade",
]

_META_DTYPES: dict[str, type[pl.DataType]] = {
    "regiao": pl.Utf8,
    "uf": pl.Utf8,
    "estacao": pl.Utf8,
    "codigo_wmo": pl.Utf8,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "altitude": pl.Float64,
    "data_fundacao": pl.Datetime,
}

ENCODING = "latin-1"
METADATA_LINES = 8
MISSING_VALUES = ("", "-9999")
_NUMBER = r"^-?\d+(\.\d+)?$"
# Nome do arquivo de estação: ..._<início DD-MM-AAAA>_A_<fim DD-MM-AAAA>.CSV
_MEMBER_RANGE = re.compile(r"_(\d{2}-\d{2}-\d{4})_A_(\d{2}-\d{2}-\d{4})\.csv$", re.I)


def _normalize(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore")
    return ascii_name.decode().lower().strip()


def _rename_col(name: str) -> str | None:
    normalized = _normalize(name)
    for prefix, column in _COL_PREFIXES:
        if normalized.startswith(prefix):
            return column
    return None


def _read_text(f: IO[bytes] | str | Path | bytes) -> str:
    """Decode a station CSV given as bytes, binary file object or path."""
    if isinstance(f, bytes):
        raw = f
    elif isinstance(f, str | Path):
        raw = Path(f).read_bytes()
    else:
        raw = f.read()
    return raw.decode(ENCODING)


def _parse_float(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _parse_metadata(lines: list[str]) -> dict:
    values = [
        row[1] if len(row) > 1 else "" for row in csv.reader(lines, delimiter=";")
    ]
    if len(values) < METADATA_LINES:
        raise ValueError(f"Esperadas {METADATA_LINES} linhas de metadados")
    regiao, uf, estacao, codigo_wmo, lat, lon, alt, data_fundacao = values[
        :METADATA_LINES
    ]
    if re.match(r"\d{4}-\d{2}-\d{2}$", data_fundacao):
        fundacao = dt.datetime.strptime(data_fundacao, "%Y-%m-%d")
    elif re.match(r"\d{2}/\d{2}/\d{4}$", data_fundacao):
        fundacao = dt.datetime.strptime(data_fundacao, "%d/%m/%Y")
    elif re.match(r"\d{2}/\d{2}/\d{2}$", data_fundacao):
        fundacao = dt.datetime.strptime(data_fundacao, "%d/%m/%y")
    else:
        fundacao = None
    return {
        "regiao": regiao,
        "uf": uf,
        "estacao": estacao,
        "codigo_wmo": codigo_wmo,
        "latitude": _parse_float(lat),
        "longitude": _parse_float(lon),
        "altitude": _parse_float(alt),
        "data_fundacao": fundacao,
    }


def read_metadata(f) -> dict:
    """Read and parse metadata from a station CSV file.

    Args:
        f: The station CSV as bytes, a binary file object (ex: from
            ``ZipFile.open``) or a path.

    Returns:
        A dictionary containing the parsed metadata.
    """
    return _parse_metadata(_read_text(f).splitlines()[:METADATA_LINES])


def _measure_expr(column: str) -> pl.Expr:
    value = pl.col(column).str.strip_chars()
    value = pl.when(value.is_in(MISSING_VALUES)).then(None).otherwise(value)
    value = value.str.replace(",", ".", literal=True)
    # ",2" → "0.2" e "-,5" → "-0.5": o INMET omite o zero antes da vírgula.
    return value.str.replace(r"^(-?)\.", "${1}0.").alias(column)


def _station_frame(text: str, drop_empty: bool = True) -> pl.DataFrame:
    lines = text.splitlines()
    body = "\n".join(lines[METADATA_LINES:])
    raw = pl.read_csv(
        io.StringIO(body),
        separator=";",
        infer_schema=False,
        truncate_ragged_lines=False,
    )
    # Toda linha termina com ";": a última coluna não tem nome e vem vazia.
    unnamed = [c for c in raw.columns if not c.strip()]
    for column in unnamed:
        if raw[column].drop_nulls().str.strip_chars().ne("").any():
            raise ValueError(f"Coluna sem nome com valores: {column!r}")
    named = [c for c in raw.columns if c.strip()]
    mapping = {c: _rename_col(c) for c in named}
    unknown = [c for c, v in mapping.items() if v is None]
    if unknown:
        raise ValueError(f"Cabeçalhos não reconhecidos: {unknown}")
    expected = {"data", "hora", *_MEASURE_COLS}
    mapped = list(mapping.values())
    if len(set(mapped)) != len(mapped) or set(mapped) != expected:
        raise ValueError(f"Cabeçalho fora do layout: {named}")
    d = (
        raw.select(named)
        .rename(mapping)
        .with_columns(_measure_expr(c) for c in _MEASURE_COLS)
    )
    bad = [
        (c, d.filter(pl.col(c).is_not_null() & ~pl.col(c).str.contains(_NUMBER))[c][0])
        for c in _MEASURE_COLS
        if d.filter(pl.col(c).is_not_null() & ~pl.col(c).str.contains(_NUMBER)).height
    ]
    if bad:
        raise ValueError(f"Valores não numéricos: {bad}")
    d = d.with_columns(pl.col(c).cast(pl.Float64, strict=True) for c in _MEASURE_COLS)
    if drop_empty:
        d = d.filter(pl.any_horizontal(pl.col(c).is_not_null() for c in _MEASURE_COLS))
    # "AAAA-MM-DD" ou "AAAA/MM/DD"; "HH:MM" ou "HHMM UTC".
    hora = pl.col("hora").str.replace(" UTC", "", literal=True)
    hora = hora.str.replace(":", "", literal=True)
    d = d.with_columns(
        (pl.col("data").str.replace_all("/", "-", literal=True) + " " + hora)
        .str.to_datetime("%Y-%m-%d %H%M", strict=True, time_zone="UTC")
        .alias("data_hora")
    )
    return d.drop(["data", "hora"])


def read_station_data(f, *, drop_empty: bool = True) -> pl.DataFrame:
    """Read and parse observation data from a station CSV file.

    Args:
        f: The station CSV as bytes, a binary file object (ex: from
            ``ZipFile.open``) or a path.
        drop_empty: Drop hours in which every measurement is missing.

    Returns:
        A Polars DataFrame with the 17 measurements (``Float64``) and
        ``data_hora`` (``Datetime`` in UTC).

    Raises:
        ValueError: If a header is not recognized, a column is missing or
            repeated, or a value is neither a number nor a missing marker.
    """
    return _station_frame(_read_text(f), drop_empty=drop_empty)


def _member_end(filename: str) -> dt.date | None:
    match = _MEMBER_RANGE.search(filename)
    if not match:
        return None
    return dt.datetime.strptime(match.group(2), "%d-%m-%Y").date()


def _latest_member_per_station(
    members: list[tuple[str, dict]],
) -> list[tuple[str, dict]]:
    """Keep one member per station: the extract that ends last.

    Some annual ZIPs (ex: 2026) carry two extracts per station, one ending on
    31/08 and another on 30/09; the later one supersedes the earlier.
    """
    by_station: dict[str, list[tuple[str, dict]]] = {}
    for name, meta in members:
        by_station.setdefault(meta["codigo_wmo"], []).append((name, meta))
    kept = []
    for code, items in by_station.items():
        if len(items) == 1:
            kept.append(items[0])
            continue
        ends = [_member_end(name) for name, _ in items]
        if None in ends or len(set(ends)) != len(ends):
            raise ValueError(
                f"Estação {code} com mais de um arquivo e sem período distinto: "
                f"{[name for name, _ in items]}"
            )
        kept.append(max(zip(ends, items, strict=True), key=lambda pair: pair[0])[1])
    return kept


def _as_utc(value: str) -> dt.datetime:
    moment = dt.datetime.fromisoformat(value)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=dt.UTC)
    return moment.astimezone(dt.UTC)


def read_zipfile(
    filepath: Path,
    *,
    uf: list[str] | None = None,
    station: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    drop_empty: bool = True,
) -> pl.DataFrame:
    """Read and parse all CSV files inside an INMET BDMEP ZIP archive.

    When the ZIP holds more than one extract of the same station, only the
    one ending last is read.

    Args:
        filepath: The path to the ZIP archive.
        uf: Optional list of UFs to filter stations by.
        station: Optional list of WMO station codes to filter by.
        start: Optional start datetime (ISO format; naive values are UTC).
        end: Optional end datetime (ISO format; naive values are UTC).
        drop_empty: Drop hours in which every measurement is missing.

    Returns:
        A Polars DataFrame containing the combined data from the ZIP archive.

    Raises:
        ValueError: On a malformed station file, two extracts of a station
            that cannot be told apart, or a repeated (station, hour).
    """
    frames = []
    with zipfile.ZipFile(filepath) as z:
        names = [info.filename for info in z.infolist() if not info.is_dir()]
        members = [(name, read_metadata(z.read(name))) for name in names]
        members = _latest_member_per_station(members)
        for name, meta in tqdm(
            members, desc=Path(filepath).name, leave=False, dynamic_ncols=True
        ):
            if uf and meta["uf"] not in uf:
                continue
            if station and meta["codigo_wmo"] not in station:
                continue
            try:
                d = read_station_data(z.read(name), drop_empty=drop_empty)
            except (ValueError, pl.exceptions.PolarsError) as exc:
                raise ValueError(f"{filepath}:{name}: {exc}") from exc
            d = d.with_columns(
                [pl.lit(meta[k], dtype=_META_DTYPES[k]).alias(k) for k in _META_DTYPES]
            )
            frames.append(d)
    if not frames:
        return pl.DataFrame()
    data = pl.concat(frames)
    repeated = data.group_by("codigo_wmo", "data_hora").len().filter(pl.col("len") > 1)
    if repeated.height:
        raise ValueError(
            f"{filepath}: {repeated.height} pares (estação, hora) repetidos"
        )
    if start:
        data = data.filter(pl.col("data_hora") >= _as_utc(start))
    if end:
        data = data.filter(pl.col("data_hora") <= _as_utc(end))
    return data


def find_zipfiles(
    data_dir: Path, years: list[int] | None = None, *, latest_only: bool = True
) -> list[Path]:
    """Locate INMET BDMEP ZIPs under ``bdmep/{year}/*.zip`` (Padrão B).

    Args:
        data_dir: The root data directory.
        years: Optional list of years to locate. If None, finds all years.
        latest_only: Return only the most recent ZIP of each year (by the
            date stamped in the file name). The current year's ZIP is
            republished monthly and each version holds the whole year so far,
            so reading several versions would repeat the same hours.

    Returns:
        A list of Path objects for the found ZIP files.
    """
    repo = DataRepository(data_dir)
    zips: list[Path] = []
    if years:
        for year in years:
            year_dir = repo.dataset_path("bdmep", str(year))
            if year_dir.exists():
                zips.extend(sorted(year_dir.glob("*.zip")))
    else:
        bdmep_root = repo.dataset_path("bdmep")
        if bdmep_root.exists():
            zips.extend(sorted(bdmep_root.rglob("*.zip")))

    zips = sorted(set(zips))
    if latest_only:
        latest: dict[Path, Path] = {}
        for path in zips:
            latest[path.parent] = path  # ordenado: o último é o carimbo mais novo
        zips = sorted(latest.values())
    return zips


def read(
    data_dir: Path,
    years: list[int] | None = None,
    uf: list[str] | None = None,
    station: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pl.DataFrame:
    """Read and concatenate observation data from multiple INMET BDMEP ZIP archives.

    Only the most recent ZIP of each year is read (see ``find_zipfiles``).

    Args:
        data_dir: The root data directory containing the ZIP files.
        years: Optional list of years to read.
        uf: Optional list of UFs to filter stations by.
        station: Optional list of WMO station codes to filter by.
        start: Optional start datetime (ISO format; naive values are UTC).
        end: Optional end datetime (ISO format; naive values are UTC).

    Returns:
        A Polars DataFrame containing the combined observation data.

    Raises:
        FileNotFoundError: If no ZIP files are found for the specified criteria.
    """
    zips = find_zipfiles(data_dir, years)
    if not zips:
        raise FileNotFoundError(f"Nenhum ZIP encontrado em {data_dir}")
    frames = [
        read_zipfile(z, uf=uf, station=station, start=start, end=end)
        for z in tqdm(zips, desc="lendo ZIPs", dynamic_ncols=True)
    ]
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames)


def read_stations(data_dir: Path, years: list[int] | None = None) -> pl.DataFrame:
    """Read and compile station metadata from INMET BDMEP ZIP archives.

    Args:
        data_dir: The root data directory containing the ZIP files.
        years: Optional list of years to read.

    Returns:
        A Polars DataFrame containing unique station metadata.

    Raises:
        FileNotFoundError: If no ZIP files are found for the specified criteria.
    """
    zips = find_zipfiles(data_dir, years)
    if not zips:
        raise FileNotFoundError(f"Nenhum ZIP encontrado em {data_dir}")
    records = []
    for filepath in tqdm(zips, desc="lendo ZIPs", dynamic_ncols=True):
        with zipfile.ZipFile(filepath) as z:
            for zf in z.infolist():
                if not zf.is_dir():
                    records.append(read_metadata(z.read(zf.filename)))
    if not records:
        return pl.DataFrame()
    df = pl.DataFrame({k: [r[k] for r in records] for k in records[0]})
    return df.unique(subset=["codigo_wmo"]).sort("codigo_wmo")
