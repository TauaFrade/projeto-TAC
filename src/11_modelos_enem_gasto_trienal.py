"""Modelos lineares de associacao entre gasto municipal trienal e notas do ENEM.

Premissas:
- Amostra: GRUPO_RECORTE em {'acessivel', 'regular'}.
- Triênio completo (TRIENIO_COMPLETO=True).
- Município de prova válido (CO_MUNICIPIO_PROVA_IBGE não nulo).
- Nota válida por área (missing da área excluído daquela regressão).
- Erros-padrão robustos agrupados pelo município de prova.

Saídas:
- data/processed/modelos_ols_gasto_trienal.csv
- data/processed/modelos_ols_gasto_trienal_diagnosticos.csv

Uso:
  python src/11_modelos_enem_gasto_trienal.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

BASE_PATH = Path("data/processed/enem_2023_2025_com_gasto_trienal.parquet")
OUT_DIR = Path("data/processed")
OUT_MODELOS = OUT_DIR / "modelos_ols_gasto_trienal.csv"
OUT_DIAG = OUT_DIR / "modelos_ols_gasto_trienal_diagnosticos.csv"

NOTAS = {
    "NU_NOTA_CN": "Ciencias da Natureza",
    "NU_NOTA_CH": "Ciencias Humanas",
    "NU_NOTA_LC": "Linguagens",
    "NU_NOTA_MT": "Matematica",
    "NU_NOTA_REDACAO": "Redacao",
}


def magnitude_label(effect: float) -> str:
    abs_effect = abs(effect)
    if abs_effect < 0.2:
        return "desprezivel"
    if abs_effect < 0.5:
        return "pequeno"
    if abs_effect < 0.8:
        return "medio"
    return "grande"


def main() -> None:
    if not BASE_PATH.exists():
        raise FileNotFoundError(f"Base integrada nao encontrada: {BASE_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    needed = [
        "ANO",
        "GRUPO_RECORTE",
        "TRIENIO_COMPLETO",
        "CO_MUNICIPIO_PROVA_IBGE",
        "UF_PROVA",
        "CAPITAL_PROVA",
        "LOG_GASTO_REAL_POR_MATRICULA_TRIENIO",
    ] + list(NOTAS)

    df = pd.read_parquet(BASE_PATH, columns=needed)

    df = df[
        df["GRUPO_RECORTE"].isin(["acessivel", "regular"])
        & (df["TRIENIO_COMPLETO"] == True)
        & df["CO_MUNICIPIO_PROVA_IBGE"].notna()
        & df["LOG_GASTO_REAL_POR_MATRICULA_TRIENIO"].notna()
    ].copy()

    df["GRUPO_ACESSIVEL"] = (df["GRUPO_RECORTE"] == "acessivel").astype("int8")
    df["ANO"] = pd.to_numeric(df["ANO"], errors="coerce").astype("int64")
    df["UF_PROVA"] = pd.to_numeric(df["UF_PROVA"], errors="coerce")
    df = df[df["UF_PROVA"].notna()].copy()
    df["UF_PROVA"] = df["UF_PROVA"].astype("int64")
    df["CAPITAL_PROVA"] = df["CAPITAL_PROVA"].fillna(False).astype("int8")
    df["MUNICIPIO_CLUSTER"] = pd.to_numeric(
        df["CO_MUNICIPIO_PROVA_IBGE"], errors="coerce"
    ).astype("int64")

    gasto_mean = df["LOG_GASTO_REAL_POR_MATRICULA_TRIENIO"].mean()
    gasto_std = df["LOG_GASTO_REAL_POR_MATRICULA_TRIENIO"].std(ddof=1)
    if pd.isna(gasto_std) or gasto_std <= 0:
        raise ValueError("Desvio-padrao do gasto logaritmico invalido")

    df["GASTO_LOG_Z"] = (
        df["LOG_GASTO_REAL_POR_MATRICULA_TRIENIO"] - gasto_mean
    ) / gasto_std

    formula = (
        "NOTA ~ GRUPO_ACESSIVEL + GASTO_LOG_Z "
        "+ GRUPO_ACESSIVEL:GASTO_LOG_Z "
        "+ C(ANO) + C(UF_PROVA) + C(CAPITAL_PROVA)"
    )

    coef_rows: list[dict] = []
    diag_rows: list[dict] = []

    for area_col, area_name in NOTAS.items():
        sub = df[[
            "GRUPO_ACESSIVEL",
            "GASTO_LOG_Z",
            "ANO",
            "UF_PROVA",
            "CAPITAL_PROVA",
            "MUNICIPIO_CLUSTER",
        ]].copy()

        sub["NOTA"] = df[area_col]
        sub = sub.dropna(subset=["NOTA"])

        n = len(sub)
        n_acessivel = int(sub["GRUPO_ACESSIVEL"].sum())
        n_regular = int(n - n_acessivel)
        n_municipios = int(sub["MUNICIPIO_CLUSTER"].nunique())

        if n < 100 or n_acessivel < 20 or n_regular < 20:
            diag_rows.append({
                "AREA": area_col,
                "AREA_NOME": area_name,
                "N": n,
                "N_ACESSIVEL": n_acessivel,
                "N_REGULAR": n_regular,
                "N_MUNICIPIOS": n_municipios,
                "STATUS": "amostra_insuficiente",
            })
            continue

        model = smf.ols(formula=formula, data=sub)
        fitted = model.fit(
            cov_type="cluster",
            cov_kwds={"groups": sub["MUNICIPIO_CLUSTER"]},
        )

        terms = [
            "Intercept",
            "GRUPO_ACESSIVEL",
            "GASTO_LOG_Z",
            "GRUPO_ACESSIVEL:GASTO_LOG_Z",
        ]

        for term in terms:
            if term not in fitted.params:
                continue
            coef = float(fitted.params[term])
            se = float(fitted.bse[term])
            pval = float(fitted.pvalues[term])
            ci = fitted.conf_int().loc[term]

            coef_rows.append({
                "AREA": area_col,
                "AREA_NOME": area_name,
                "TERMO": term,
                "COEFICIENTE": round(coef, 6),
                "ERRO_PADRAO_CLUSTER": round(se, 6),
                "P_VALOR": pval,
                "IC95_INF": round(float(ci.iloc[0]), 6),
                "IC95_SUP": round(float(ci.iloc[1]), 6),
                "SIGNIFICANTE_5PCT": bool(pval < 0.05),
            })

        interaction = fitted.params.get("GRUPO_ACESSIVEL:GASTO_LOG_Z", np.nan)
        diag_rows.append({
            "AREA": area_col,
            "AREA_NOME": area_name,
            "N": n,
            "N_ACESSIVEL": n_acessivel,
            "N_REGULAR": n_regular,
            "N_MUNICIPIOS": n_municipios,
            "R_QUADRADO": round(float(fitted.rsquared), 6),
            "R_QUADRADO_AJUSTADO": round(float(fitted.rsquared_adj), 6),
            "INTERACAO_EFETO": round(float(interaction), 6) if pd.notna(interaction) else np.nan,
            "INTERACAO_SIGNIFICANTE_5PCT": bool(fitted.pvalues.get("GRUPO_ACESSIVEL:GASTO_LOG_Z", 1) < 0.05),
            "STATUS": "concluido",
        })

    coef_table = pd.DataFrame(coef_rows)
    diag_table = pd.DataFrame(diag_rows)

    coef_table["P_VALOR_FMT"] = coef_table["P_VALOR"].map(
        lambda p: "<1e-300" if p < 1e-300 else f"{p:.3e}"
    )

    coef_table.to_csv(OUT_MODELOS, index=False, encoding="utf-8-sig")
    diag_table.to_csv(OUT_DIAG, index=False, encoding="utf-8-sig")

    print("Modelos OLS concluidos.")
    print(f"- {OUT_MODELOS}")
    print(f"- {OUT_DIAG}")
    print("\nDiagnosticos:")
    print(diag_table.to_string(index=False))


if __name__ == "__main__":
    main()
