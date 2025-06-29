import argparse
from pathlib import Path

from inmet_bdmep.fetcher import download_year


def expand_years(*years: str) -> list[int]:
    year_list = []
    for y in years:
        if ":" in y:
            start, end = y.split(":")
            year_list.extend(list(range(int(start), int(end) + 1)))
        else:
            year_list.append(int(y))
    return year_list


def get_args():
    parser = argparse.ArgumentParser(
        description="Download INMET BDMEP data",
    )
    parser.add_argument(
        "years",
        nargs="+",
        help="Years to download",
    )
    parser.add_argument(
        "--data-dir",
        dest="data_dir",
        type=Path,
        required=True,
        help="Destination directory",
    )
    args = parser.parse_args()
    return args


def main():
    args = get_args()
    data_dir = args.data_dir
    years = expand_years(*args.years)
    for year in years:
        download_year(year, data_dir)


if __name__ == "__main__":
    main()
