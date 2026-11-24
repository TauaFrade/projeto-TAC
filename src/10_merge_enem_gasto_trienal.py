"""Integra base ENEM com indicador municipal trienal de gasto por matricula.

Entradas:
- data/processed/enem_2023_2025_preliminar.parquet
- data/processed/indicador_gasto_trienal_enem_municipio.csv

Saidas:
- data/processed/enem_2023_2025_com_gasto_trienal.parquet
- data/processed/enem_2023_2025_com_gasto_trienal_cobertura_ano.csv
- data/processed/enem_2023_2025_com_gasto_trienal_cobertura_ano_grupo.csv

Uso:
  python src/10_merge_enem_gasto_trienal.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ENEM_PATH = Path("data/processed/enem_2023_2025_preliminar.parquet")
GASTO_TRIENAL_PATH = Path("data/processed/indicador_gasto_trienal_enem_municipio.csv")

OUT_DIR = Path("data/processed")
OUT_BASE = OUT_DIR / "enem_2023_2025_com_gasto_trienal.parquet"
OUT_COB_ANO = OUT_DIR / "enem_2023_2025_com_gasto_trienal_cobertura_ano.csv"
OUT_COB_ANO_GRUPO = OUT_DIR / "enem_2023_2025_com_gasto_trienal_cobertura_ano_grupo.csv"


def sanitize_municipio_code(series: pd.Series) -> pd.Series:
    # Padroniza para inteiro anulavel e remove valores fora do padrao IBGE (7 digitos).
    s_num = pd.to_numeric(series, errors="coerce").astype("Int64")
    valid = (s_num >= 1_000_000) & (s_num <= 9_999_999)
    return s_num.where(valid)


def build_coverage_by_year(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df.groupby("ANO", as_index=False)
        .agg(
            N_TOTAL=("ANO", "size"),
            N_COM_INDICADOR=("HAS_GASTO_TRIENAL", "sum"),
            N_TRIENIO_COMPLETO=("TRIENIO_COMPLETO", "sum"),
            N_SEM_MUNICIPIO=("MUNICIPIO_PROVA_VALIDO", lambda s: int((~s).sum())),
        )
        .copy()
    )

    out["PCT_COM_INDICADOR"] = (100 * out["N_COM_INDICADOR"] / out["N_TOTAL"]).round(3)
    out["PCT_TRIENIO_COMPLETO"] = (100 * out["N_TRIENIO_COMPLETO"] / out["N_TOTAL"]).round(3)
    out["PCT_SEM_MUNICIPIO"] = (100 * out["N_SEM_MUNICIPIO"] / out["N_TOTAL"]).round(3)
    return out.sort_values("ANO")


def build_coverage_by_year_group(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df.groupby(["ANO", "GRUPO_RECORTE"], as_index=False, dropna=False)
        .agg(
            N_TOTAL=("ANO", "size"),
            N_COM_INDICADOR=("HAS_GASTO_TRIENAL", "sum"),
            N_TRIENIO_COMPLETO=("TRIENIO_COMPLETO", "sum"),
        )
        .copy()
    )
    out["PCT_COM_INDICADOR"] = (100 * out["N_COM_INDICADOR"] / out["N_TOTAL"]).round(3)
    out["PCT_TRIENIO_COMPLETO"] = (100 * out["N_TRIENIO_COMPLETO"] / out["N_TOTAL"]).round(3)
    return out.sort_values(["ANO", "GRUPO_RECORTE"])


def main() -> None:
    if not ENEM_PATH.exists():
        raise FileNotFoundError(f"Base ENEM nao encontrada: {ENEM_PATH}")
    if not GASTO_TRIENAL_PATH.exists():
        raise FileNotFoundError(f"Indicador trienal nao encontrado: {GASTO_TRIENAL_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    enem = pd.read_parquet(ENEM_PATH)
    gasto = pd.read_csv(GASTO_TRIENAL_PATH)

    # Padroniza chaves de merge.
    enem["CO_MUNICIPIO_PROVA_IBGE"] = sanitize_municipio_code(enem["CO_MUNICIPIO_PROVA"])
    enem["MUNICIPIO_PROVA_VALIDO"] = enem["CO_MUNICIPIO_PROVA_IBGE"].notna()

    gasto["CO_MUNICIPIO"] = sanitize_municipio_code(gasto["CO_MUNICIPIO"])
    gasto["ANO_ENEM"] = pd.to_numeric(gasto["ANO_ENEM"], errors="coerce").astype("Int64")

    keep_gasto = [
        "CO_MUNICIPIO",
        "ANO_ENEM",
        "N_ANOS_DISPONIVEIS",
        "TRIENIO_COMPLETO",
        "TRIENIO_INICIO",
        "TRIENIO_FIM",
        "GASTO_REAL_POR_MATRICULA_TRIENIO",
        "DESPESA_REAL_ALVO_TRIENIO_MEDIA",
        "CENSO_MAT_ALVO_TRIENIO_MEDIA",
    ]
    gasto = gasto[keep_gasto].drop_duplicates(subset=["CO_MUNICIPIO", "ANO_ENEM"])

    merged = enem.merge(
        gasto,
        left_on=["CO_MUNICIPIO_PROVA_IBGE", "ANO"],
        right_on=["CO_MUNICIPIO", "ANO_ENEM"],
        how="left",
    )

    merged["HAS_GASTO_TRIENAL"] = merged["GASTO_REAL_POR_MATRICULA_TRIENIO"].notna()
    merged["TRIENIO_COMPLETO"] = merged["TRIENIO_COMPLETO"].fillna(False)
    merged["N_ANOS_DISPONIVEIS"] = merged["N_ANOS_DISPONIVEIS"].fillna(0).astype("Int64")

    # Conveniencia para modelagem: log do indicador (somente onde > 0).
    merged["LOG_GASTO_REAL_POR_MATRICULA_TRIENIO"] = np.where(
        merged["GASTO_REAL_POR_MATRICULA_TRIENIO"] > 0,
        np.log(merged["GASTO_REAL_POR_MATRICULA_TRIENIO"]),
        np.nan,
    )

    cob_ano = build_coverage_by_year(merged)
    cob_ano_grupo = build_coverage_by_year_group(merged)

    merged.to_parquet(OUT_BASE, index=False)
    cob_ano.to_csv(OUT_COB_ANO, index=False, encoding="utf-8-sig")
    cob_ano_grupo.to_csv(OUT_COB_ANO_GRUPO, index=False, encoding="utf-8-sig")

    print("Integracao ENEM x gasto trienal concluida.")
    print(f"- {OUT_BASE}")
    print(f"- {OUT_COB_ANO}")
    print(f"- {OUT_COB_ANO_GRUPO}")
    print("\nCobertura por ano:")
    print(cob_ano.to_string(index=False))


if __name__ == "__main__":
    main()
