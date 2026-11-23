"""Modelos integrais ENEM — gasto municipal e estadual.

Especificacao principal:
nota ~ grupo_acessivel
     + gasto_municipal_z
     + gasto_especial_municipal_z
     + gasto_estadual_z
     + gasto_especial_estadual_z
     + interacoes grupo x gasto
     + ano + UF + capital/interior

Erros-padrão: clusterizados por município de prova.

Saidas:
- data/processed/modelos_integrados_municipal_estadual.csv
- data/processed/modelos_integrados_municipal_estadual_diagnosticos.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

BASE_PATH = Path("data/processed/enem_2023_2025_com_gastos_municipal_estadual.parquet")
OUT_DIR = Path("data/processed")
OUT_MODELOS = OUT_DIR / "modelos_integrados_municipal_estadual.csv"
OUT_DIAG = OUT_DIR / "modelos_integrados_municipal_estadual_diagnosticos.csv"

NOTAS = {
    "NU_NOTA_CN": "Ciencias da Natureza",
    "NU_NOTA_CH": "Ciencias Humanas",
    "NU_NOTA_LC": "Linguagens",
    "NU_NOTA_MT": "Matematica",
    "NU_NOTA_REDACAO": "Redacao",
}

GASTO_COLS = {
    "GASTO_MUNICIPAL_Z": "LOG_GASTO_REAL_POR_MATRICULA_TRIENIO",
    "GASTO_MUNICIPAL_ESPECIAL_Z": None,
    "GASTO_ESTADUAL_Z": "LOG_GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO",
    "GASTO_ESTADUAL_ESPECIAL_Z": "LOG_GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO",
}


def zscore(series: pd.Series) -> pd.Series:
    mean = series.mean()
    std = series.std(ddof=1)
    if pd.isna(std) or std <= 0:
        raise ValueError("Desvio-padrao invalido para padronizacao")
    return (series - mean) / std


def main() -> None:
    if not BASE_PATH.exists():
        raise FileNotFoundError(f"Base integrada nao encontrada: {BASE_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    needed = [
        "ANO", "UF_PROVA", "UF_PROVA_COD", "CAPITAL_PROVA",
        "GRUPO_RECORTE", "TRIENIO_COMPLETO_COMBINADO",
        "CO_MUNICIPIO_PROVA_IBGE", "GASTO_REAL_POR_MATRICULA_TRIENIO",
        "LOG_GASTO_REAL_POR_MATRICULA_TRIENIO",
        "LOG_GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO",
        "LOG_GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO",
        "LOG_GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO",
    ] + list(NOTAS)

    df = pd.read_parquet(BASE_PATH, columns=needed)
    df = df[
        df["GRUPO_RECORTE"].isin(["acessivel", "regular"])
        & df["TRIENIO_COMPLETO_COMBINADO"]
        & df["CO_MUNICIPIO_PROVA_IBGE"].notna()
    ].copy()

    df["GRUPO_ACESSIVEL"] = (df["GRUPO_RECORTE"] == "acessivel").astype("int8")
    df["ANO"] = pd.to_numeric(df["ANO"], errors="coerce").astype("int64")
    df["UF_PROVA"] = pd.to_numeric(df["UF_PROVA"], errors="coerce")
    df["UF_PROVA"] = df["UF_PROVA"].fillna(df["UF_PROVA_COD"])
    df = df[df["UF_PROVA"].notna()].copy()
    df["UF_PROVA"] = df["UF_PROVA"].astype("int64")
    df["CAPITAL_PROVA"] = df["CAPITAL_PROVA"].fillna(False).astype("int8")
    df["MUNICIPIO_CLUSTER"] = pd.Categorical(df["CO_MUNICIPIO_PROVA_IBGE"].astype("int64")).codes

    gasto_cols = {
        "GASTO_MUNICIPAL_Z": "LOG_GASTO_REAL_POR_MATRICULA_TRIENIO",
        "GASTO_MUNICIPAL_ESPECIAL_Z": "LOG_GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO",
        "GASTO_ESTADUAL_Z": "LOG_GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO",
        "GASTO_ESTADUAL_ESPECIAL_Z": "LOG_GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO",
    }

    for zname, source in gasto_cols.items():
        df[zname] = zscore(df[source])

    df = df.dropna(subset=[
        "GASTO_MUNICIPAL_Z", "GASTO_MUNICIPAL_ESPECIAL_Z",
        "GASTO_ESTADUAL_Z", "GASTO_ESTADUAL_ESPECIAL_Z",
    ]).copy()

    formula = (
        "NOTA ~ GRUPO_ACESSIVEL"
        " + GASTO_MUNICIPAL_Z + GASTO_MUNICIPAL_ESPECIAL_Z"
        " + GASTO_ESTADUAL_Z + GASTO_ESTADUAL_ESPECIAL_Z"
        " + GRUPO_ACESSIVEL:GASTO_MUNICIPAL_Z"
        " + GRUPO_ACESSIVEL:GASTO_MUNICIPAL_ESPECIAL_Z"
        " + GRUPO_ACESSIVEL:GASTO_ESTADUAL_Z"
        " + GRUPO_ACESSIVEL:GASTO_ESTADUAL_ESPECIAL_Z"
        " + C(ANO) + C(UF_PROVA) + C(CAPITAL_PROVA)"
    )

    coef_rows = []
    diag_rows = []

    for area_col, area_name in NOTAS.items():
        sub = df[[
            "GRUPO_ACESSIVEL", "GASTO_MUNICIPAL_Z", "GASTO_MUNICIPAL_ESPECIAL_Z",
            "GASTO_ESTADUAL_Z", "GASTO_ESTADUAL_ESPECIAL_Z", "ANO", "UF_PROVA",
            "CAPITAL_PROVA", "MUNICIPIO_CLUSTER",
        ]].copy()
        sub["NOTA"] = df[area_col]
        sub = sub.dropna(subset=["NOTA"])

        n = len(sub)
        n_acc = int(sub["GRUPO_ACESSIVEL"].sum())
        n_reg = int(n - n_acc)

        if n < 100 or n_acc < 20 or n_reg < 20:
            diag_rows.append({"AREA": area_col, "AREA_NOME": area_name, "N": n,
                              "STATUS": "amostra_insuficiente"})
            continue

        model = smf.ols(formula=formula, data=sub)
        matrix_rank = int(np.linalg.matrix_rank(model.exog))
        n_columns = int(model.exog.shape[1])

        if matrix_rank < n_columns:
            diag_rows.append({
                "AREA": area_col,
                "AREA_NOME": area_name,
                "N": n,
                "N_ACESSIVEL": n_acc,
                "N_REGULAR": n_reg,
                "N_MUNICIPIOS": int(sub["MUNICIPIO_CLUSTER"].nunique()),
                "RANK_MATRIZ": matrix_rank,
                "COLUNAS_MATRIZ": n_columns,
                "STATUS": "matriz_singular",
            })
            continue

        fit = model.fit(
            cov_type="cluster",
            cov_kwds={"groups": sub["MUNICIPIO_CLUSTER"]},
        )

        terms = [
            "GRUPO_ACESSIVEL",
            "GASTO_MUNICIPAL_Z",
            "GASTO_MUNICIPAL_ESPECIAL_Z",
            "GASTO_ESTADUAL_Z",
            "GASTO_ESTADUAL_ESPECIAL_Z",
            "GRUPO_ACESSIVEL:GASTO_MUNICIPAL_Z",
            "GRUPO_ACESSIVEL:GASTO_MUNICIPAL_ESPECIAL_Z",
            "GRUPO_ACESSIVEL:GASTO_ESTADUAL_Z",
            "GRUPO_ACESSIVEL:GASTO_ESTADUAL_ESPECIAL_Z",
        ]

        ci = fit.conf_int()
        for term in terms:
            if term not in fit.params:
                continue
            coef = float(fit.params[term])
            se = float(fit.bse[term])
            pval = float(fit.pvalues[term])
            coef_rows.append({
                "AREA": area_col,
                "AREA_NOME": area_name,
                "TERMO": term,
                "COEFICIENTE": round(coef, 6),
                "ERRO_PADRAO_CLUSTER": round(se, 6),
                "P_VALOR": pval,
                "P_VALOR_FMT": "<1e-300" if pval < 1e-300 else f"{pval:.3e}",
                "IC95_INF": round(float(ci.loc[term, 0]), 6),
                "IC95_SUP": round(float(ci.loc[term, 1]), 6),
                "SIGNIFICANTE_5PCT": bool(pval < 0.05),
            })

        diag_rows.append({
            "AREA": area_col,
            "AREA_NOME": area_name,
            "N": n,
            "N_ACESSIVEL": n_acc,
            "N_REGULAR": n_reg,
            "N_MUNICIPIOS": int(sub["MUNICIPIO_CLUSTER"].nunique()),
            "R_QUADRADO": round(float(fit.rsquared), 6),
            "R_QUADRADO_AJUSTADO": round(float(fit.rsquared_adj), 6),
            "STATUS": "concluido",
        })

    pd.DataFrame(coef_rows).to_csv(OUT_MODELOS, index=False, encoding="utf-8-sig")
    pd.DataFrame(diag_rows).to_csv(OUT_DIAG, index=False, encoding="utf-8-sig")

    print("Modelos integrados concluidos.")
    print(f"- {OUT_MODELOS}")
    print(f"- {OUT_DIAG}")
    print("\nDiagnosticos:")
    print(pd.DataFrame(diag_rows).to_string(index=False))


if __name__ == "__main__":
    main()
