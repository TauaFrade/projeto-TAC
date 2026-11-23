"""Indicadores estaduais anuais e trienais de gasto em educacao.

Premissas:
- Dados: FINBRA estadual em data/raw/finbra/<ano>/finbra_estados.csv.
- Despesas liquidadas.
- Gasto geral: subfuncoes disponiveis entre 12.361, 12.362, 12.365, 12.367, 12.368.
- Gasto Educacao Especial: subfuncao 12.367 separadamente.
- Matrículas: Censo Escolar publico estadual por UF.
- Correção: IPCA numero-indice medio anual.

Saidas:
- data/processed/indicador_gasto_estadual_municipio_ano_real.csv
- data/processed/indicador_gasto_estadual_trienal_enem_uf.csv
- data/processed/indicador_gasto_estadual_trienal_enem_resumo.csv
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

FINBRA_DIR = Path("data/raw/finbra")
CENSO_DIR = Path("data/raw/censo_escolar")
IPCA_PATH = Path("data/raw/IPCA/IPCA_numero_indice.json")
OUT_DIR = Path("data/processed")

OUT_ANUAL = OUT_DIR / "indicador_gasto_estadual_municipio_ano_real.csv"
OUT_TRIENAL = OUT_DIR / "indicador_gasto_estadual_trienal_enem_uf.csv"
OUT_RESUMO = OUT_DIR / "indicador_gasto_estadual_trienal_enem_resumo.csv"

SUBFUNCOES_ALVO = {"12.361", "12.362", "12.365", "12.367", "12.368"}

UF_CODES = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR",
    42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
}
SIGLA_TO_CODE = {v: k for k, v in UF_CODES.items()}


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value).strip())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def parse_br_number(value: object) -> float:
    if value is None:
        return np.nan
    s = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def extract_subfuncao(conta: object) -> str | None:
    match = re.match(r"^\s*(\d{2}\.\d{3})\b", str(conta or ""))
    return match.group(1) if match else None


def find_single_csv(base_dir: Path) -> Path:
    csvs = sorted(set([p.resolve() for p in base_dir.rglob("*.csv")]))
    csvs_lower = sorted(set([p.resolve() for p in base_dir.rglob("*.CSV")]))
    csvs = sorted(set(csvs + csvs_lower))
    if len(csvs) == 1:
        return csvs[0]
    candidates = [p for p in csvs if "microdados_ed_basica" in p.name.lower()]
    if len(candidates) == 1:
        return candidates[0]
    if not csvs:
        raise FileNotFoundError(f"Nenhum CSV encontrado em {base_dir}")
    raise RuntimeError(f"Ambiguidade de arquivos CSV em {base_dir}: {csvs}")


def detect_encoding(path: Path) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            pd.read_csv(path, sep=";", encoding=enc, nrows=2)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def load_ipca_media_anual() -> pd.DataFrame:
    raw = json.loads(IPCA_PATH.read_text(encoding="utf-8"))
    rows = []
    for rec in raw[1:]:
        code = str(rec.get("D3C", ""))
        if len(code) < 6 or not code[:6].isdigit():
            continue
        try:
            indice = float(str(rec.get("V")).replace(",", "."))
        except (TypeError, ValueError):
            continue
        rows.append({"ANO": int(code[:4]), "MES": int(code[4:6]), "IPCA_INDICE": indice})

    ipca = pd.DataFrame(rows)
    anual = (
        ipca.groupby("ANO", as_index=False)
        .agg(IPCA_MEDIA_ANUAL=("IPCA_INDICE", "mean"), N_MESES=("MES", "nunique"))
    )
    return anual[anual["N_MESES"] >= 12].copy()


def load_finbra_estadual(ano: int) -> pd.DataFrame:
    path = FINBRA_DIR / str(ano) / "finbra_estados.csv"
    if not path.exists():
        raise FileNotFoundError(f"Arquivo estadual nao encontrado: {path}")

    enc = detect_encoding(path)
    df = pd.read_csv(
        path,
        sep=";",
        encoding=enc,
        skiprows=3,
        dtype={"Cod.IBGE": "string", "UF": "string", "Coluna": "string", "Conta": "string", "Valor": "string"},
        low_memory=False,
    )

    df["COD_UF"] = pd.to_numeric(df["Cod.IBGE"], errors="coerce").astype("Int64")
    df["UF_SIGLA"] = df["UF"].str.strip().str.upper()
    df["COLUNA_NORM"] = df["Coluna"].map(normalize_text)
    df["SUBFUNCAO"] = df["Conta"].map(extract_subfuncao)
    df["VALOR_NUM"] = df["Valor"].map(parse_br_number)

    liquidadas = df[df["COLUNA_NORM"] == "despesas liquidadas"].copy()

    geral = liquidadas[liquidadas["SUBFUNCAO"].isin(SUBFUNCOES_ALVO)].copy()
    geral_agg = (
        geral.groupby(["COD_UF", "UF_SIGLA"], as_index=False)
        .agg(
            FINBRA_EST_VALOR_GERAL=("VALOR_NUM", "sum"),
            N_SUBFUNCOES_GERAL=("SUBFUNCAO", "nunique"),
        )
    )

    esp = liquidadas[liquidadas["SUBFUNCAO"] == "12.367"].copy()
    esp_agg = (
        esp.groupby(["COD_UF", "UF_SIGLA"], as_index=False)
        .agg(FINBRA_EST_VALOR_EDU_ESPECIAL=("VALOR_NUM", "sum"))
    )

    out = geral_agg.merge(esp_agg, on=["COD_UF", "UF_SIGLA"], how="left")
    out["FINBRA_EST_VALOR_EDU_ESPECIAL"] = out["FINBRA_EST_VALOR_EDU_ESPECIAL"].fillna(0)
    out["ANO"] = ano
    return out


def load_censo_estadual(ano: int) -> pd.DataFrame:
    path = find_single_csv(CENSO_DIR / str(ano))
    enc = detect_encoding(path)

    usecols = [
        "NU_ANO_CENSO",
        "CO_UF",
        "TP_DEPENDENCIA",
        "TP_SITUACAO_FUNCIONAMENTO",
        "QT_MAT_BAS",
        "QT_MAT_FUND",
        "QT_MAT_MED",
        "QT_MAT_INF",
        "QT_MAT_ESP",
    ]

    df = pd.read_csv(
        path,
        sep=";",
        encoding=enc,
        usecols=usecols,
        dtype={
            "NU_ANO_CENSO": "int64",
            "CO_UF": "int64",
            "TP_DEPENDENCIA": "Int64",
            "TP_SITUACAO_FUNCIONAMENTO": "Int64",
            "QT_MAT_BAS": "float64",
            "QT_MAT_FUND": "float64",
            "QT_MAT_MED": "float64",
            "QT_MAT_INF": "float64",
            "QT_MAT_ESP": "float64",
        },
        low_memory=False,
    )

    df = df[df["NU_ANO_CENSO"] == ano].copy()
    df = df[
        (df["TP_DEPENDENCIA"] == 2)
        & (df["TP_SITUACAO_FUNCIONAMENTO"] == 1)
    ].copy()

    mat_cols = ["QT_MAT_BAS", "QT_MAT_FUND", "QT_MAT_MED", "QT_MAT_INF", "QT_MAT_ESP"]
    for col in mat_cols:
        df[col] = df[col].fillna(0)

    agg = (
        df.groupby("CO_UF", as_index=False)
        .agg(
            CENSO_EST_MAT_BAS=("QT_MAT_BAS", "sum"),
            CENSO_EST_MAT_FUND=("QT_MAT_FUND", "sum"),
            CENSO_EST_MAT_MED=("QT_MAT_MED", "sum"),
            CENSO_EST_MAT_INF=("QT_MAT_INF", "sum"),
            CENSO_EST_MAT_ESP=("QT_MAT_ESP", "sum"),
        )
    )

    agg["CENSO_EST_MAT_ALVO_SUM"] = (
        agg["CENSO_EST_MAT_FUND"]
        + agg["CENSO_EST_MAT_MED"]
        + agg["CENSO_EST_MAT_INF"]
        + agg["CENSO_EST_MAT_ESP"]
    )
    agg["ANO"] = ano
    return agg


def build_anual(ano_base_ipca: int, anos: list[int]) -> pd.DataFrame:
    ipca = load_ipca_media_anual()
    base_ipca = ipca[ipca["ANO"] == ano_base_ipca]
    if base_ipca.empty:
        raise ValueError(f"Ano-base IPCA {ano_base_ipca} nao encontrado")
    indice_base = float(base_ipca.iloc[0]["IPCA_MEDIA_ANUAL"])

    frames = []
    for ano in anos:
        gasto = load_finbra_estadual(ano)
        censo = load_censo_estadual(ano)

        merge = gasto.merge(censo, left_on=["COD_UF", "ANO"], right_on=["CO_UF", "ANO"], how="left")
        frames.append(merge)

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.merge(ipca[["ANO", "IPCA_MEDIA_ANUAL"]], on="ANO", how="left")

    panel["ANO_BASE_IPCA"] = ano_base_ipca
    panel["FATOR_DEFLATOR_ANO_BASE"] = indice_base / panel["IPCA_MEDIA_ANUAL"]

    panel["GASTO_ESTADUAL_REAL_GERAL"] = panel["FINBRA_EST_VALOR_GERAL"] * panel["FATOR_DEFLATOR_ANO_BASE"]
    panel["GASTO_ESTADUAL_REAL_EDU_ESPECIAL"] = panel["FINBRA_EST_VALOR_EDU_ESPECIAL"] * panel["FATOR_DEFLATOR_ANO_BASE"]

    panel["GASTO_ESTADUAL_REAL_POR_MATRICULA"] = (
        panel["GASTO_ESTADUAL_REAL_GERAL"] / panel["CENSO_EST_MAT_ALVO_SUM"]
    )
    panel["GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_ESP"] = (
        panel["GASTO_ESTADUAL_REAL_EDU_ESPECIAL"] / panel["CENSO_EST_MAT_ESP"]
    )

    panel["INDICADOR_ESTADUAL_GERAL_VALIDO"] = (
        panel["GASTO_ESTADUAL_REAL_POR_MATRICULA"].notna()
        & np.isfinite(panel["GASTO_ESTADUAL_REAL_POR_MATRICULA"])
        & (panel["CENSO_EST_MAT_ALVO_SUM"] > 0)
    )
    panel["INDICADOR_ESTADUAL_ESPECIAL_VALIDO"] = (
        panel["GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_ESP"].notna()
        & np.isfinite(panel["GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_ESP"])
        & (panel["CENSO_EST_MAT_ESP"] > 0)
    )

    keep = [
        "ANO", "COD_UF", "UF_SIGLA", "ANO_BASE_IPCA", "IPCA_MEDIA_ANUAL",
        "FATOR_DEFLATOR_ANO_BASE", "N_SUBFUNCOES_GERAL", "FINBRA_EST_VALOR_GERAL",
        "FINBRA_EST_VALOR_EDU_ESPECIAL", "CENSO_EST_MAT_BAS", "CENSO_EST_MAT_FUND",
        "CENSO_EST_MAT_MED", "CENSO_EST_MAT_INF", "CENSO_EST_MAT_ESP",
        "CENSO_EST_MAT_ALVO_SUM", "GASTO_ESTADUAL_REAL_GERAL",
        "GASTO_ESTADUAL_REAL_EDU_ESPECIAL", "GASTO_ESTADUAL_REAL_POR_MATRICULA",
        "GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_ESP",
        "INDICADOR_ESTADUAL_GERAL_VALIDO", "INDICADOR_ESTADUAL_ESPECIAL_VALIDO",
    ]
    return panel[keep].sort_values(["ANO", "COD_UF"]).reset_index(drop=True)


def build_trienal(anual: pd.DataFrame, anos_enem: list[int]) -> pd.DataFrame:
    frames = []
    for ano_enem in anos_enem:
        janela = [ano_enem - 3, ano_enem - 2, ano_enem - 1]
        sub = anual[anual["ANO"].isin(janela)].copy()

        sub = sub[sub["INDICADOR_ESTADUAL_GERAL_VALIDO"]].copy()
        agg = (
            sub.groupby(["COD_UF", "UF_SIGLA"], as_index=False)
            .agg(
                N_ANOS_DISPONIVEIS_GERAL=("ANO", "nunique"),
                GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO=("GASTO_ESTADUAL_REAL_POR_MATRICULA", "mean"),
                GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO=("GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_ESP", "mean"),
            )
        )
        agg["ANO_ENEM"] = ano_enem
        agg["TRIENIO_INICIO"] = janela[0]
        agg["TRIENIO_FIM"] = janela[-1]
        agg["TRIENIO_COMPLETO_GERAL"] = agg["N_ANOS_DISPONIVEIS_GERAL"] == 3
        frames.append(agg)

    return pd.concat(frames, ignore_index=True).sort_values(["ANO_ENEM", "COD_UF"])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    anual = build_anual(ano_base_ipca=2024, anos=[2020, 2021, 2022, 2023, 2024])
    trienal = build_trienal(anual, anos_enem=[2023, 2024, 2025])

    resumo = (
        trienal.groupby("ANO_ENEM", as_index=False)
        .agg(
            UFS_COM_DADO=("UF_SIGLA", "nunique"),
            UFS_TRIENIO_COMPLETO=("TRIENIO_COMPLETO_GERAL", "sum"),
            GASTO_ESTADUAL_MEDIANA=("GASTO_ESTADUAL_REAL_POR_MATRICULA_TRIENIO", "median"),
            GASTO_ESTADUAL_ESPECIAL_MEDIANA=("GASTO_ESTADUAL_ESPECIAL_REAL_POR_MATRICULA_TRIENIO", "median"),
        )
    )
    resumo["PCT_UFS_TRIENIO_COMPLETO"] = (
        100 * resumo["UFS_TRIENIO_COMPLETO"] / resumo["UFS_COM_DADO"]
    ).round(2)

    anual.to_csv(OUT_ANUAL, index=False, encoding="utf-8-sig")
    trienal.to_csv(OUT_TRIENAL, index=False, encoding="utf-8-sig")
    resumo.to_csv(OUT_RESUMO, index=False, encoding="utf-8-sig")

    print("Indicadores estaduais gerados.")
    print(f"- {OUT_ANUAL}")
    print(f"- {OUT_TRIENAL}")
    print(f"- {OUT_RESUMO}")
    print("\nResumo por ano ENEM:")
    print(resumo.to_string(index=False))


if __name__ == "__main__":
    main()
