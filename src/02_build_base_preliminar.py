"""Monta uma base preliminar consolidada (2023-2025) para analises rapidas.

Objetivo:
- Ler os parquet gerados em data/interim/enem_<ano>.parquet.
- Filtrar participantes com caderno em pelo menos uma area.
- Criar variaveis auxiliares para analises de apresentacao.
- Salvar uma base unica em data/processed/enem_2023_2025_preliminar.parquet.

Uso:
  python src/02_build_base_preliminar.py
  python src/02_build_base_preliminar.py --anos 2023 2024
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

AREAS = ["CN", "CH", "LC", "MT"]
IN_DIR = Path("data/interim")
OUT_PATH = Path("data/processed/enem_2023_2025_preliminar.parquet")


def colunas_prova(df: pd.DataFrame) -> list[str]:
    return [f"CO_PROVA_{a}" for a in AREAS if f"CO_PROVA_{a}" in df.columns]


def carregar_ano(ano: int) -> pd.DataFrame:
    path = IN_DIR / f"enem_{ano}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

    df = pd.read_parquet(path)
    df["ANO"] = ano

    prova_cols = colunas_prova(df)
    if not prova_cols:
        raise ValueError(f"Nao encontrei CO_PROVA_* em {path}")

    # Compareceu a ao menos uma prova objetiva.
    df["COMPARECEU_OBJETIVA"] = df[prova_cols].notna().any(axis=1)

    # Recorte principal para a apresentacao preliminar.
    df["GRUPO_RECORTE"] = df["GRUPO"].replace(
        {
            "libras": "acessivel",
            "braile_ledor": "acessivel",
            "regular": "regular",
            "outro_atend": "fora_recorte",
        }
    )

    return df


def main(anos: list[int]) -> None:
    frames = [carregar_ano(a) for a in anos]
    base = pd.concat(frames, ignore_index=True)

    # Mantem apenas quem tem caderno para analise de desempenho.
    base = base.loc[base["COMPARECEU_OBJETIVA"]].copy()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    base.to_parquet(OUT_PATH, index=False)

    print(f"Base consolidada salva em: {OUT_PATH}")
    print("Resumo de linhas por ano e grupo:")
    print(base.groupby(["ANO", "GRUPO"]).size().to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--anos", nargs="+", type=int, default=[2023, 2024, 2025])
    args = parser.parse_args()
    main(args.anos)
