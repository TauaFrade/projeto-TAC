"""Integra base ENEM municipal com indicadores estaduais trienais.

Entradas:
- data/processed/enem_2023_2025_com_gasto_trienal.parquet
- data/processed/indicador_gasto_estadual_trienal_enem_uf.csv

Saidas:
- data/processed/enem_2023_2025_com_gastos_municipal_estadual.parquet
- data/processed/enem_gastos_cobertura_combinada_ano.csv
- data/processed/enem_gastos_cobertura_combinada_ano_grupo.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_MUN = Path("data/processed/enem_2023_2025_com_gasto_trienal.parquet")
BASE_EST = Path("data/processed/indicador_gasto_estadual_trienal_enem_uf.csv")
OUT_DIR = Path("data/processed")
OUT_BASE = OUT_DIR / "enem_2023_2025_com_gastos_municipal_estadual.parquet"
OUT_COB_ANO = OUT_DIR / "enem_gastos_cobertura_combinada_ano.csv"
OUT_COB_GRUPO = OUT_DIR / "enem_gastos_cobertura_combinada_ano_grupo.csv"

UF_CODES = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR",
    42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
}
CODE_TO_UF = {v: k for k, v in UF_CODES.items()}


def uf_from_source(df: pd.DataFrame) -> pd.DataFrame:
    if "UF_PROVA" in df.columns:
        codes = pd.to_numeric(df["UF_PROVA"], errors="coerce")
        df["UF_PROVA_COD"] = codes.astype("Int64")
        df["UF_SIGLA_PROVA"] = df["UF_PROVA_COD"].map(UF_CODES)
    elif "SG_UF_PROVA" in df.columns:
        df["UF_SIGLA_PROVA"] = df["SG_UF_PROVA"].astype("string").str.strip().str.upper()
        df["UF_PROVA_COD"] = df["UF_SIGLA_PROVA"].map(CODE_TO_UF).astype("Int64")
    else:
        raise KeyError("Base nao possui UF_PROVA nem SG_UF_PROVA")
    return df


def main() -> None:
    if not BASE_MUN.exists():
        raise FileNotFoundError(f"Base municipal nao encontrada: {BASE_MUN}")
    if not BASE_EST.exists():
        raise FileNotFoundError(f"Base estadual nao encontrada: {BASE_EST}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(BASE_MUN)
    est = pd.read_csv(BASE_EST)

    df = uf_from_source(df)
    est["COD_UF"] = pd.to_numeric(est["COD_UF"], errors="coerce").astype("Int64")
    est["ANO_ENEM"] = pd.to_numeric(est["ANO_ENEM"], errors="coerce").astype("Int64")

    keep_est = [
        "COD_UF",
        "UF_SIGLA",
        "ANO_ENEM",
        "N_ANOS_DISPONIVEIS_GERAL",
        "GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO",
        "GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO",
        "TRIENIO_INICIO",
        "TRIENIO_FIM",
        "TRIENIO_COMPLETO_GERAL",
    ]
    est = est[keep_est].drop_duplicates(subset=["COD_UF", "ANO_ENEM"])

    out = df.merge(
        est,
        left_on=["UF_PROVA_COD", "ANO"],
        right_on=["COD_UF", "ANO_ENEM"],
        how="left",
    )

    out["HAS_GASTO_MUNICIPAL"] = out["GASTO_REAL_POR_MATRICULA_TRIENIO"].notna()
    out["HAS_GASTO_ESTADUAL"] = out["GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO"].notna()
    out["HAS_GASTO_ESTADUAL_ESPECIAL"] = out["GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO"].notna()
    out["HAS_GASTOS_COMBINADOS"] = out["HAS_GASTO_MUNICIPAL"] & out["HAS_GASTO_ESTADUAL"]

    for col in [
        "GASTO_REAL_POR_MATRICULA_TRIENIO",
        "GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO",
        "GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO",
    ]:
        positive = out[col].astype("float64") > 0
        out[f"LOG_{col}"] = np.where(positive, np.log(out[col].astype("float64")), np.nan)

    out["TRIENIO_COMPLETO_COMBINADO"] = (
        out["TRIENIO_COMPLETO"].fillna(False)
        & out["TRIENIO_COMPLETO_GERAL"].fillna(False)
    )

    cob_ano = (
        out.groupby("ANO", as_index=False)
        .agg(
            N_TOTAL=("ANO", "size"),
            N_COM_MUNICIPAL=("HAS_GASTO_MUNICIPAL", "sum"),
            N_COM_ESTADUAL=("HAS_GASTO_ESTADUAL", "sum"),
            N_COM_COMBINADO=("HAS_GASTOS_COMBINADOS", "sum"),
            N_COM_TRIENIO_COMBINADO=("TRIENIO_COMPLETO_COMBINADO", "sum"),
        )
    )
    for prefix in ["MUNICIPAL", "ESTADUAL", "COMBINADO", "TRIENIO_COMBINADO"]:
        col_src = {
            "MUNICIPAL": "N_COM_MUNICIPAL",
            "ESTADUAL": "N_COM_ESTADUAL",
            "COMBINADO": "N_COM_COMBINADO",
            "TRIENIO_COMBINADO": "N_COM_TRIENIO_COMBINADO",
        }[prefix]
        cob_ano[f"PCT_{prefix}"] = (100 * cob_ano[col_src] / cob_ano["N_TOTAL"]).round(3)

    cob_grupo = (
        out.groupby(["ANO", "GRUPO_RECORTE"], as_index=False, dropna=False)
        .agg(
            N_TOTAL=("ANO", "size"),
            N_COM_MUNICIPAL=("HAS_GASTO_MUNICIPAL", "sum"),
            N_COM_ESTADUAL=("HAS_GASTO_ESTADUAL", "sum"),
            N_COM_COMBINADO=("HAS_GASTOS_COMBINADOS", "sum"),
            N_COM_TRIENIO_COMBINADO=("TRIENIO_COMPLETO_COMBINADO", "sum"),
        )
    )
    cob_grupo["PCT_COMBINADO"] = (100 * cob_grupo["N_COM_COMBINADO"] / cob_grupo["N_TOTAL"]).round(3)
    cob_grupo["PCT_TRIENIO_COMBINADO"] = (100 * cob_grupo["N_COM_TRIENIO_COMBINADO"] / cob_grupo["N_TOTAL"]).round(3)

    # Inclui indicador municipal separado de Educacao Especial.
    especial_mun_path = OUT_DIR / "indicador_gasto_municipal_especial_trienal_enem_municipio.csv"
    if especial_mun_path.exists():
        especial_mun = pd.read_csv(especial_mun_path)
        especial_mun["COD_MUN"] = pd.to_numeric(especial_mun["COD_MUN"], errors="coerce").astype("Int64")
        especial_mun["ANO_ENEM"] = pd.to_numeric(especial_mun["ANO_ENEM"], errors="coerce").astype("Int64")
        especial_mun = especial_mun[[
            "COD_MUN", "ANO_ENEM", "N_ANOS_ESPECIAL",
            "GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO",
            "TRIENIO_COMPLETO_ESPECIAL",
        ]].drop_duplicates(subset=["COD_MUN", "ANO_ENEM"])

        out = out.merge(
            especial_mun,
            left_on=["CO_MUNICIPIO_PROVA_IBGE", "ANO"],
            right_on=["COD_MUN", "ANO_ENEM"],
            how="left",
        )

        positive = out["GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO"].astype("float64") > 0
        out["LOG_GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO"] = np.where(
            positive,
            np.log(out["GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO"].astype("float64")),
            np.nan,
        )

    out.to_parquet(OUT_BASE, index=False)
    cob_ano.to_csv(OUT_COB_ANO, index=False, encoding="utf-8-sig")
    cob_grupo.to_csv(OUT_COB_GRUPO, index=False, encoding="utf-8-sig")

    print("Base municipal-estadual integrada.")
    print(f"- {OUT_BASE}")
    print(f"- {OUT_COB_ANO}")
    print(f"- {OUT_COB_GRUPO}")
    print("\nCobertura combinada por ano:")
    print(cob_ano.to_string(index=False))


if __name__ == "__main__":
    main()
