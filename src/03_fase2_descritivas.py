"""Gera tabelas descritivas da fase 2 para resultados preliminares.

Saidas:
- data/processed/fase2_n_por_grupo.csv
- data/processed/fase2_n_por_recorte.csv
- data/processed/fase2_notas_descritivas.csv
- data/processed/fase2_gaps_acessivel_vs_regular.csv

Uso:
  python src/03_fase2_descritivas.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_PATH = Path("data/processed/enem_2023_2025_preliminar.parquet")
OUT_DIR = Path("data/processed")
NOTAS = ["NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "NU_NOTA_REDACAO"]


def tabela_n_por_grupo(df: pd.DataFrame) -> pd.DataFrame:
    tab = (
        df.groupby(["ANO", "GRUPO"], dropna=False)
        .size()
        .reset_index(name="N")
        .sort_values(["ANO", "N"], ascending=[True, False])
    )
    return tab


def tabela_n_por_recorte(df: pd.DataFrame) -> pd.DataFrame:
    tab = (
        df.groupby(["ANO", "GRUPO_RECORTE"], dropna=False)
        .size()
        .reset_index(name="N")
        .sort_values(["ANO", "N"], ascending=[True, False])
    )

    totais = tab.groupby("ANO")["N"].transform("sum")
    tab["PCT_ANO"] = (100 * tab["N"] / totais).round(4)
    return tab


def tabela_notas_descritivas(df: pd.DataFrame) -> pd.DataFrame:
    long = df.melt(
        id_vars=["ANO", "GRUPO", "GRUPO_RECORTE"],
        value_vars=NOTAS,
        var_name="AREA",
        value_name="NOTA",
    )

    desc = (
        long.dropna(subset=["NOTA"])
        .groupby(["ANO", "GRUPO", "GRUPO_RECORTE", "AREA"], dropna=False)["NOTA"]
        .agg(
            N="count",
            MEDIA="mean",
            MEDIANA="median",
            P25=lambda s: s.quantile(0.25),
            P75=lambda s: s.quantile(0.75),
            DESVIO_PADRAO="std",
        )
        .reset_index()
        .sort_values(["ANO", "AREA", "GRUPO"])
    )

    for c in ["MEDIA", "MEDIANA", "P25", "P75", "DESVIO_PADRAO"]:
        desc[c] = desc[c].round(3)

    return desc


def tabela_gaps_recorte(df: pd.DataFrame) -> pd.DataFrame:
    long = df.melt(
        id_vars=["ANO", "GRUPO_RECORTE"],
        value_vars=NOTAS,
        var_name="AREA",
        value_name="NOTA",
    )

    # Mantem somente o confronto principal da apresentacao.
    sub = long[long["GRUPO_RECORTE"].isin(["acessivel", "regular"])].copy()

    media = (
        sub.dropna(subset=["NOTA"])
        .groupby(["ANO", "AREA", "GRUPO_RECORTE"])["NOTA"]
        .mean()
        .unstack("GRUPO_RECORTE")
        .reset_index()
    )

    n_validos = (
        sub.dropna(subset=["NOTA"])
        .groupby(["ANO", "AREA", "GRUPO_RECORTE"])
        .size()
        .unstack("GRUPO_RECORTE")
        .reset_index()
        .rename(columns={"acessivel": "N_ACESSIVEL", "regular": "N_REGULAR"})
    )

    out = media.merge(n_validos, on=["ANO", "AREA"], how="left")
    out = out.rename(columns={"acessivel": "MEDIA_ACESSIVEL", "regular": "MEDIA_REGULAR"})
    out["GAP_ACESSIVEL_MENOS_REGULAR"] = (out["MEDIA_ACESSIVEL"] - out["MEDIA_REGULAR"]).round(3)
    out["MEDIA_ACESSIVEL"] = out["MEDIA_ACESSIVEL"].round(3)
    out["MEDIA_REGULAR"] = out["MEDIA_REGULAR"].round(3)

    return out.sort_values(["ANO", "AREA"])


def main() -> None:
    if not BASE_PATH.exists():
        raise FileNotFoundError(
            f"Base preliminar nao encontrada em {BASE_PATH}. Rode antes: src/02_build_base_preliminar.py"
        )

    df = pd.read_parquet(BASE_PATH)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    t1 = tabela_n_por_grupo(df)
    t2 = tabela_n_por_recorte(df)
    t3 = tabela_notas_descritivas(df)
    t4 = tabela_gaps_recorte(df)

    p1 = OUT_DIR / "fase2_n_por_grupo.csv"
    p2 = OUT_DIR / "fase2_n_por_recorte.csv"
    p3 = OUT_DIR / "fase2_notas_descritivas.csv"
    p4 = OUT_DIR / "fase2_gaps_acessivel_vs_regular.csv"

    t1.to_csv(p1, index=False, encoding="utf-8-sig")
    t2.to_csv(p2, index=False, encoding="utf-8-sig")
    t3.to_csv(p3, index=False, encoding="utf-8-sig")
    t4.to_csv(p4, index=False, encoding="utf-8-sig")

    print("Tabelas geradas:")
    print(f"- {p1}")
    print(f"- {p2}")
    print(f"- {p3}")
    print(f"- {p4}")

    print("\nResumo rapido (gap acessivel - regular):")
    print(t4.to_string(index=False))


if __name__ == "__main__":
    main()
