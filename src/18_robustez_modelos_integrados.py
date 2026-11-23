"""Analises de robustez dos modelos integrados municipal-estaduais.

Roteiro:
- modelos por ano;
- Libras e Braile/ledor separadamente;
- gasto municipal separado do gasto estadual;
- nível absoluto e logaritmo;
- interação grupo x gasto quando identificável;
- erros-padrão clusterizados por município de prova.

Saídas:
- data/processed/robustez_modelos_integrados.csv
- data/processed/robustez_modelos_resumo.csv
- data/processed/robustez_modelos_registro.txt
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

BASE_PATH = Path("data/processed/enem_2023_2025_com_gastos_municipal_estadual.parquet")
OUT_DIR = Path("data/processed")
OUT_MODEL = OUT_DIR / "robustez_modelos_integrados.csv"
OUT_RESUME = OUT_DIR / "robustez_modelos_resumo.csv"
OUT_LOG = OUT_DIR / "robustez_modelos_registro.txt"

NOTAS = {
    "NU_NOTA_CN": "Ciencias da Natureza",
    "NU_NOTA_CH": "Ciencias Humanas",
    "NU_NOTA_LC": "Linguagens",
    "NU_NOTA_MT": "Matematica",
    "NU_NOTA_REDACAO": "Redacao",
}


def zscore(series: pd.Series) -> pd.Series:
    mean = series.mean()
    std = series.std(ddof=1)
    if pd.isna(std) or std <= 0:
        return pd.Series(np.nan, index=series.index)
    return (series - mean) / std


def fit_model(sub: pd.DataFrame, area: str, formula: str, scenario: str) -> pd.DataFrame:
    sub = sub.copy()
    sub["CLUSTER"] = pd.Categorical(sub["CO_MUNICIPIO_PROVA_IBGE"].astype("int64")).codes

    sub = sub.dropna(subset=[c for c in sub.columns if c.startswith("GASTO_") or c in [area, "GRUPO_ACESSIVEL"]])

    n = len(sub)
    n_acc = int(sub["GRUPO_ACESSIVEL"].sum()) if "GRUPO_ACESSIVEL" in sub else 0

    if n < 500 or n_acc < 30:
        return pd.DataFrame([{
            "CENARIO": scenario,
            "AREA": area,
            "STATUS": "amostra_insuficiente",
            "N": n,
            "N_ACESSIVEL": n_acc,
            "N_REGULAR": int(n - n_acc),
            "N_MUNICIPIOS": int(sub["CLUSTER"].nunique()) if len(sub) else 0,
        }])

    try:
        model = smf.ols(formula=formula, data=sub)
    except Exception as exc:
        return pd.DataFrame([{
            "CENARIO": scenario,
            "AREA": area,
            "STATUS": "erro_formula",
            "N": n,
            "N_ACESSIVEL": n_acc,
            "N_REGULAR": int(n - n_acc),
            "ERRO": str(exc),
        }])

    rank = int(np.linalg.matrix_rank(model.exog))
    cols = int(model.exog.shape[1])

    if rank < cols:
        return pd.DataFrame([{
            "CENARIO": scenario,
            "AREA": area,
            "STATUS": "matriz_singular",
            "N": n,
            "N_ACESSIVEL": n_acc,
            "N_REGULAR": int(n - n_acc),
            "N_MUNICIPIOS": int(sub["CLUSTER"].nunique()),
            "RANK_MATRIZ": rank,
            "COLUNAS_MATRIZ": cols,
        }])

    try:
        fit = model.fit(cov_type="cluster", cov_kwds={"groups": sub["CLUSTER"]})
    except Exception as exc:
        return pd.DataFrame([{
            "CENARIO": scenario,
            "AREA": area,
            "STATUS": "erro_ajuste",
            "N": n,
            "N_ACESSIVEL": n_acc,
            "N_REGULAR": int(n - n_acc),
            "ERRO": str(exc),
        }])

    rows = []
    ci = fit.conf_int()
    for term in fit.params.index:
        if term in {"Intercept"}:
            continue
        coef = float(fit.params[term])
        pval = float(fit.pvalues[term])
        rows.append({
            "CENARIO": scenario,
            "AREA": area,
            "STATUS": "concluido",
            "N": n,
            "N_ACESSIVEL": n_acc,
            "N_REGULAR": int(n - n_acc),
            "N_MUNICIPIOS": int(sub["CLUSTER"].nunique()),
            "R_QUADRADO": round(float(fit.rsquared), 6),
            "TERMO": term,
            "COEFICIENTE": round(coef, 6),
            "ERRO_PADRAO_CLUSTER": round(float(fit.bse[term]), 6),
            "P_VALOR": pval,
            "P_VALOR_FMT": "<1e-300" if pval < 1e-300 else f"{pval:.3e}",
            "IC95_INF": round(float(ci.loc[term, 0]), 6),
            "IC95_SUP": round(float(ci.loc[term, 1]), 6),
            "SIGNIFICANTE_5PCT": bool(pval < 0.05),
        })

    return pd.DataFrame(rows)


def prepare_base() -> pd.DataFrame:
    if not BASE_PATH.exists():
        raise FileNotFoundError(f"Base integrada nao encontrada: {BASE_PATH}")

    needed = [
        "ANO", "UF_PROVA", "UF_PROVA_COD", "CAPITAL_PROVA",
        "GRUPO", "GRUPO_RECORTE", "TRIENIO_COMPLETO_COMBINADO",
        "CO_MUNICIPIO_PROVA_IBGE",
        "GASTO_REAL_POR_MATRICULA_TRIENIO",
        "LOG_GASTO_REAL_POR_MATRICULA_TRIENIO",
        "GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO",
        "LOG_GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO",
        "GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO",
        "LOG_GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO",
        "GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO",
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
    df["UF_PROVA"] = df["UF_PROVA"].fillna(pd.to_numeric(df["UF_PROVA_COD"], errors="coerce"))
    df = df[df["UF_PROVA"].notna()].copy()
    df["UF_PROVA"] = df["UF_PROVA"].astype("int64")
    df["CAPITAL_PROVA"] = df["CAPITAL_PROVA"].fillna(False).astype("int8")

    # Padronizacao alternativa para especificacoes de robustez.
    for source, zname in {
        "GASTO_REAL_POR_MATRICULA_TRIENIO": "GASTO_MUNICIPAL_Z",
        "GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO": "GASTO_MUNICIPAL_ESPECIAL_Z",
        "GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO": "GASTO_ESTADUAL_Z",
        "GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO": "GASTO_ESTADUAL_ESPECIAL_Z",
    }.items():
        df[zname] = zscore(df[source])

    for source, zname in {
        "LOG_GASTO_REAL_POR_MATRICULA_TRIENIO": "GASTO_MUNICIPAL_LOG_Z",
        "LOG_GASTO_MUNICIPAL_ESPECIAL_POR_MATRICULA_TRIENIO": "GASTO_MUNICIPAL_ESPECIAL_LOG_Z",
        "LOG_GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO": "GASTO_ESTADUAL_LOG_Z",
        "LOG_GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO": "GASTO_ESTADUAL_ESPECIAL_LOG_Z",
    }.items():
        df[zname] = zscore(df[source])

    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = prepare_base()

    frames = []

    controls = "+ C(ANO) + C(UF_PROVA) + C(CAPITAL_PROVA)"

    # 1. Especificacoes municipais e estaduais separadas.
    for area in NOTAS:
        municipal = df.dropna(subset=["GASTO_MUNICIPAL_Z", "GASTO_MUNICIPAL_ESPECIAL_Z"]).copy()
        f_mun = (
            area
            + " ~ GRUPO_ACESSIVEL + GASTO_MUNICIPAL_Z + GASTO_MUNICIPAL_ESPECIAL_Z"
            + " + GRUPO_ACESSIVEL:GASTO_MUNICIPAL_Z"
            + " + GRUPO_ACESSIVEL:GASTO_MUNICIPAL_ESPECIAL_Z"
            + controls
        )
        frames.append(fit_model(municipal, area, f_mun, "municipal_separado_log_padronizado"))

        estadual = df.dropna(subset=["GASTO_ESTADUAL_Z", "GASTO_ESTADUAL_ESPECIAL_Z"]).copy()
        f_est = (
            area
            + " ~ GRUPO_ACESSIVEL + GASTO_ESTADUAL_Z + GASTO_ESTADUAL_ESPECIAL_Z"
            + " + GRUPO_ACESSIVEL:GASTO_ESTADUAL_Z"
            + " + GRUPO_ACESSIVEL:GASTO_ESTADUAL_ESPECIAL_Z"
            + controls
        )
        frames.append(fit_model(estadual, area, f_est, "estadual_separado_log_padronizado"))

    # 2. Robustez por ano.
    for ano in [2023, 2024, 2025]:
        sub = df[df["ANO"] == ano].copy()
        sub = sub.dropna(subset=["GASTO_MUNICIPAL_Z", "GASTO_ESTADUAL_Z"])
        for area in NOTAS:
            formula = (
                area
                + " ~ GRUPO_ACESSIVEL + GASTO_MUNICIPAL_Z + GASTO_ESTADUAL_Z"
                + " + GRUPO_ACESSIVEL:GASTO_MUNICIPAL_Z"
                + " + GRUPO_ACESSIVEL:GASTO_ESTADUAL_Z"
                + " + C(UF_PROVA) + C(CAPITAL_PROVA)"
            )
            frames.append(fit_model(sub, area, formula, f"ano_{ano}_municipal_estadual"))

    # 3. Robustez por modalidade para amostras suficientes.
    for modalidade in ["libras", "braile_ledor"]:
        sub = df[df["GRUPO"].isin([modalidade, "regular"])].copy()
        sub["GRUPO_MODALIDADE"] = (sub["GRUPO"] == modalidade).astype("int8")

        sub = sub.dropna(subset=["GASTO_MUNICIPAL_Z", "GASTO_ESTADUAL_Z"])

        # Amostra secundaria controlada para robustez por modalidade.
        if len(sub) > 300_000:
            regular = sub[sub["GRUPO"] == "regular"]
            modalidade_rows = sub[sub["GRUPO"] == modalidade]
            n_regular = min(295_000, len(regular))
            if n_regular > 0:
                regular = regular.sample(n=n_regular, random_state=42)
            sub = pd.concat([regular, modalidade_rows], ignore_index=True)

        for area in NOTAS:
            sub["GRUPO_ACESSIVEL"] = sub["GRUPO_MODALIDADE"]
            formula = (
                area
                + " ~ GRUPO_ACESSIVEL + GASTO_MUNICIPAL_Z + GASTO_ESTADUAL_Z"
                + " + GRUPO_ACESSIVEL:GASTO_MUNICIPAL_Z"
                + " + GRUPO_ACESSIVEL:GASTO_ESTADUAL_Z"
                + controls
            )
            frames.append(fit_model(sub, area, formula, f"modalidade_{modalidade}"))

    result = pd.concat(frames, ignore_index=True)

    status = (
        result.groupby(["CENARIO", "STATUS"], as_index=False)
        .size()
        .rename(columns={"size": "N_RESULTADOS"})
    )

    result.to_csv(OUT_MODEL, index=False, encoding="utf-8-sig")
    status.to_csv(OUT_RESUME, index=False, encoding="utf-8-sig")

    lines = [
        "ROBUSTEZ DOS MODELOS INTEGRADOS",
        "",
        "Escopo:",
        "- especificacoes municipais separadas",
        "- especificacoes estaduais separadas",
        "- modelos por ano",
        "- Libras e Braile-ledor separadamente",
        "- log padronizado versus gasto padronizado em nivel",
        "",
        "Interpretacao:",
        "- nao apresentar robustez como resultado principal quando a matriz for singular",
        "- nao interpretar coeficiente por si sem cobertura e tamanho amostral",
        "- manter linguagem associativa",
        "",
        "Status por cenario:",
    ]
    for _, r in status.iterrows():
        lines.append(f"- {r['CENARIO']}: {r['STATUS']} = {r['N_RESULTADOS']}")

    OUT_LOG.write_text("\n".join(lines), encoding="utf-8")

    print("Robustez concluida.")
    print(f"- {OUT_MODEL}")
    print(f"- {OUT_RESUME}")
    print(f"- {OUT_LOG}")
    print("\nResumo:")
    print(status.to_string(index=False))


if __name__ == "__main__":
    main()
