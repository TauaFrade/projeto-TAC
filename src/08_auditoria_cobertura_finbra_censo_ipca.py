"""Auditoria de cobertura para o painel FINBRA + Censo Escolar + IPCA.

Objetivo:
- Verificar cobertura municipio-ano (2020-2024) para os insumos do indicador.
- Aplicar o recorte acordado no FINBRA:
  Coluna = Despesas Liquidadas
  Subfuncoes = 12.361, 12.362, 12.365, 12.367, 12.368
- Medir completude, faltantes e consistencia minima antes da etapa de modelagem.

Saidas:
- data/processed/auditoria_cobertura_municipio_ano.csv
- data/processed/auditoria_cobertura_resumo_ano.csv
- data/processed/auditoria_cobertura_faltantes.csv

Uso:
  python src/08_auditoria_cobertura_finbra_censo_ipca.py
  python src/08_auditoria_cobertura_finbra_censo_ipca.py --anos 2020 2021 2022 2023 2024
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("data/raw")
FINBRA_DIR = ROOT / "finbra"
CENSO_DIR = ROOT / "censo_escolar"
IPCA_FILE = ROOT / "IPCA" / "IPCA_numero_indice.json"

OUT_DIR = Path("data/processed")
OUT_MUN_ANO = OUT_DIR / "auditoria_cobertura_municipio_ano.csv"
OUT_RESUMO = OUT_DIR / "auditoria_cobertura_resumo_ano.csv"
OUT_FALTANTES = OUT_DIR / "auditoria_cobertura_faltantes.csv"

SUBFUNCOES_ALVO = {
    "12.361",  # Ensino Fundamental
    "12.362",  # Ensino Medio
    "12.365",  # Educacao Infantil
    "12.367",  # Educacao Especial
    "12.368",  # Educacao Basica
}

DEPENDENCIAS_PUBLICAS = {2, 3}  # Estadual, Municipal
SITUACAO_FUNCIONAMENTO_ATIVA = 1


def normalize_text(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    s = str(value).strip()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def parse_br_number(value: object) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    s = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def find_single_csv(base_dir: Path) -> Path:
    csvs = sorted(base_dir.rglob("*.csv")) + sorted(base_dir.rglob("*.CSV"))
    if not csvs:
        raise FileNotFoundError(f"Nenhum CSV encontrado em {base_dir}")
    if len(csvs) == 1:
        return csvs[0]

    # Prioriza arquivo de microdados, se existir.
    ranked = sorted(
        csvs,
        key=lambda p: (
            "microdados_ed_basica" not in p.name.lower(),
            len(str(p)),
            p.name.lower(),
        ),
    )
    return ranked[0]


def detect_csv_encoding(path: Path) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            pd.read_csv(path, sep=";", encoding=enc, nrows=2)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def extract_subfuncao_code(conta: object) -> str | None:
    s = str(conta or "")
    m = re.match(r"^\s*(\d{2}\.\d{3})\b", s)
    if not m:
        return None
    return m.group(1)


def load_finbra_year(ano: int) -> pd.DataFrame:
    year_dir = FINBRA_DIR / str(ano)
    csv_path = year_dir / "finbra_municipios.csv"
    if not csv_path.exists():
        # fallback compatível com nome anterior
        fallback = year_dir / "finbra.csv"
        if fallback.exists():
            csv_path = fallback
        else:
            raise FileNotFoundError(f"FINBRA municipal nao encontrado em {year_dir}")

    enc = detect_csv_encoding(csv_path)

    usecols = [
        "Cod.IBGE",
        "Coluna",
        "Conta",
        "Valor",
    ]

    df = pd.read_csv(
        csv_path,
        sep=";",
        encoding=enc,
        skiprows=3,
        usecols=usecols,
        dtype={"Cod.IBGE": "string", "Coluna": "string", "Conta": "string", "Valor": "string"},
        low_memory=False,
    )

    df["Cod.IBGE"] = df["Cod.IBGE"].str.strip()
    df = df[df["Cod.IBGE"].str.fullmatch(r"\d{7}", na=False)].copy()

    col_norm = df["Coluna"].map(normalize_text)
    df = df[col_norm == "despesas liquidadas"].copy()

    df["SUBFUNCAO"] = df["Conta"].map(extract_subfuncao_code)
    df = df[df["SUBFUNCAO"].isin(SUBFUNCOES_ALVO)].copy()

    df["VALOR_NUM"] = df["Valor"].map(parse_br_number)

    agg = (
        df.groupby("Cod.IBGE", as_index=False)
        .agg(
            FINBRA_N_SUBFUNCOES_PRESENTES=("SUBFUNCAO", "nunique"),
            FINBRA_VALOR_TOTAL_ALVO=("VALOR_NUM", "sum"),
        )
        .rename(columns={"Cod.IBGE": "CO_MUNICIPIO"})
    )

    agg["ANO"] = ano
    agg["FINBRA_HAS_ANY"] = True
    agg["FINBRA_HAS_ALL_5"] = agg["FINBRA_N_SUBFUNCOES_PRESENTES"] == len(SUBFUNCOES_ALVO)
    agg["FINBRA_VALOR_TOTAL_ALVO"] = agg["FINBRA_VALOR_TOTAL_ALVO"].round(2)
    agg["FINBRA_VALOR_TOTAL_POSITIVO"] = agg["FINBRA_VALOR_TOTAL_ALVO"] > 0

    return agg


def load_censo_year(ano: int) -> pd.DataFrame:
    year_dir = CENSO_DIR / str(ano)
    csv_path = find_single_csv(year_dir)
    enc = detect_csv_encoding(csv_path)

    usecols = [
        "NU_ANO_CENSO",
        "CO_MUNICIPIO",
        "TP_DEPENDENCIA",
        "TP_SITUACAO_FUNCIONAMENTO",
        "QT_MAT_BAS",
        "QT_MAT_FUND",
        "QT_MAT_MED",
        "QT_MAT_INF",
        "QT_MAT_ESP",
    ]

    df = pd.read_csv(
        csv_path,
        sep=";",
        encoding=enc,
        usecols=usecols,
        dtype={
            "NU_ANO_CENSO": "Int64",
            "CO_MUNICIPIO": "string",
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

    df["CO_MUNICIPIO"] = df["CO_MUNICIPIO"].str.strip()
    df = df[df["CO_MUNICIPIO"].str.fullmatch(r"\d{7}", na=False)].copy()
    df = df[df["NU_ANO_CENSO"] == ano].copy()

    # Recorte para rede publica em funcionamento.
    df = df[
        df["TP_DEPENDENCIA"].isin(DEPENDENCIAS_PUBLICAS)
        & (df["TP_SITUACAO_FUNCIONAMENTO"] == SITUACAO_FUNCIONAMENTO_ATIVA)
    ].copy()

    for c in ["QT_MAT_BAS", "QT_MAT_FUND", "QT_MAT_MED", "QT_MAT_INF", "QT_MAT_ESP"]:
        df[c] = df[c].fillna(0)

    agg = (
        df.groupby("CO_MUNICIPIO", as_index=False)
        .agg(
            CENSO_MAT_BAS=("QT_MAT_BAS", "sum"),
            CENSO_MAT_FUND=("QT_MAT_FUND", "sum"),
            CENSO_MAT_MED=("QT_MAT_MED", "sum"),
            CENSO_MAT_INF=("QT_MAT_INF", "sum"),
            CENSO_MAT_ESP=("QT_MAT_ESP", "sum"),
        )
    )

    agg["CENSO_MAT_ALVO_SUM"] = (
        agg["CENSO_MAT_FUND"] + agg["CENSO_MAT_MED"] + agg["CENSO_MAT_INF"] + agg["CENSO_MAT_ESP"]
    )
    agg["CENSO_HAS_ANY"] = True
    agg["CENSO_MAT_BAS_POSITIVO"] = agg["CENSO_MAT_BAS"] > 0
    agg["CENSO_MAT_ALVO_POSITIVO"] = agg["CENSO_MAT_ALVO_SUM"] > 0
    agg["ANO"] = ano

    return agg


def load_ipca_coverage_years() -> set[int]:
    if not IPCA_FILE.exists():
        return set()

    data = json.loads(IPCA_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) < 2:
        return set()

    month_counter: dict[int, int] = {}
    for row in data[1:]:
        code = str(row.get("D3C", ""))
        if len(code) < 6 or not code[:6].isdigit():
            continue
        year = int(code[:4])
        month_counter[year] = month_counter.get(year, 0) + 1

    return {y for y, n in month_counter.items() if n >= 12}


def build_panel(anos: list[int]) -> pd.DataFrame:
    finbra_frames = []
    censo_frames = []

    for ano in anos:
        finbra_frames.append(load_finbra_year(ano))
        censo_frames.append(load_censo_year(ano))

    finbra = pd.concat(finbra_frames, ignore_index=True)
    censo = pd.concat(censo_frames, ignore_index=True)

    chaves = pd.concat(
        [
            finbra[["ANO", "CO_MUNICIPIO"]],
            censo[["ANO", "CO_MUNICIPIO"]],
        ],
        ignore_index=True,
    ).drop_duplicates()

    panel = chaves.merge(finbra, on=["ANO", "CO_MUNICIPIO"], how="left")
    panel = panel.merge(censo, on=["ANO", "CO_MUNICIPIO"], how="left")

    bool_cols = [
        "FINBRA_HAS_ANY",
        "FINBRA_HAS_ALL_5",
        "FINBRA_VALOR_TOTAL_POSITIVO",
        "CENSO_HAS_ANY",
        "CENSO_MAT_BAS_POSITIVO",
        "CENSO_MAT_ALVO_POSITIVO",
    ]
    for c in bool_cols:
        panel[c] = panel[c].fillna(False)

    num_cols = [
        "FINBRA_N_SUBFUNCOES_PRESENTES",
        "FINBRA_VALOR_TOTAL_ALVO",
        "CENSO_MAT_BAS",
        "CENSO_MAT_FUND",
        "CENSO_MAT_MED",
        "CENSO_MAT_INF",
        "CENSO_MAT_ESP",
        "CENSO_MAT_ALVO_SUM",
    ]
    for c in num_cols:
        panel[c] = panel[c].fillna(0)

    ipca_years = load_ipca_coverage_years()
    panel["IPCA_ANO_DISPONIVEL"] = panel["ANO"].isin(ipca_years)

    panel["PRONTO_INDICADOR_BASE"] = (
        panel["FINBRA_HAS_ANY"]
        & panel["CENSO_HAS_ANY"]
        & panel["CENSO_MAT_ALVO_POSITIVO"]
        & panel["IPCA_ANO_DISPONIVEL"]
    )

    panel["PRONTO_INDICADOR_ESTRITO"] = (
        panel["FINBRA_HAS_ALL_5"]
        & panel["FINBRA_VALOR_TOTAL_POSITIVO"]
        & panel["CENSO_HAS_ANY"]
        & panel["CENSO_MAT_ALVO_POSITIVO"]
        & panel["IPCA_ANO_DISPONIVEL"]
    )

    return panel.sort_values(["ANO", "CO_MUNICIPIO"]).reset_index(drop=True)


def build_year_summary(panel: pd.DataFrame) -> pd.DataFrame:
    resumo = (
        panel.groupby("ANO", as_index=False)
        .agg(
            MUNICIPIOS_UNIAO_BASES=("CO_MUNICIPIO", "nunique"),
            MUNICIPIOS_FINBRA_ANY=("FINBRA_HAS_ANY", "sum"),
            MUNICIPIOS_FINBRA_ALL_5=("FINBRA_HAS_ALL_5", "sum"),
            MUNICIPIOS_CENSO_ANY=("CENSO_HAS_ANY", "sum"),
            MUNICIPIOS_CENSO_MAT_ALVO_POS=("CENSO_MAT_ALVO_POSITIVO", "sum"),
            MUNICIPIOS_COM_IPCA=("IPCA_ANO_DISPONIVEL", "sum"),
            MUNICIPIOS_PRONTO_BASE=("PRONTO_INDICADOR_BASE", "sum"),
            MUNICIPIOS_PRONTO_ESTRITO=("PRONTO_INDICADOR_ESTRITO", "sum"),
        )
        .copy()
    )

    resumo["PCT_PRONTO_BASE"] = (
        100 * resumo["MUNICIPIOS_PRONTO_BASE"] / resumo["MUNICIPIOS_UNIAO_BASES"]
    ).round(2)
    resumo["PCT_PRONTO_ESTRITO"] = (
        100 * resumo["MUNICIPIOS_PRONTO_ESTRITO"] / resumo["MUNICIPIOS_UNIAO_BASES"]
    ).round(2)
    resumo["PCT_FINBRA_ALL_5"] = (
        100 * resumo["MUNICIPIOS_FINBRA_ALL_5"] / resumo["MUNICIPIOS_UNIAO_BASES"]
    ).round(2)

    return resumo


def build_missing_table(panel: pd.DataFrame) -> pd.DataFrame:
    faltantes = panel.copy()
    cond_ipca = (~faltantes["IPCA_ANO_DISPONIVEL"].fillna(False)).to_numpy(dtype=bool)
    cond_finbra_any = (~faltantes["FINBRA_HAS_ANY"].fillna(False)).to_numpy(dtype=bool)
    cond_censo_any = (~faltantes["CENSO_HAS_ANY"].fillna(False)).to_numpy(dtype=bool)
    cond_censo_mat = (~faltantes["CENSO_MAT_ALVO_POSITIVO"].fillna(False)).to_numpy(dtype=bool)
    cond_finbra_all = (~faltantes["FINBRA_HAS_ALL_5"].fillna(False)).to_numpy(dtype=bool)

    faltantes["MOTIVO_FALTA"] = np.select(
        [
            cond_ipca,
            cond_finbra_any,
            cond_censo_any,
            cond_censo_mat,
            cond_finbra_all,
        ],
        [
            "ipca_ano_indisponivel",
            "sem_finbra_subfuncao_alvo",
            "sem_censo_publico_ativo",
            "censo_matricula_alvo_zero",
            "finbra_subfuncao_incompleta",
        ],
        default="ok",
    )

    faltantes = faltantes[faltantes["MOTIVO_FALTA"] != "ok"].copy()
    return faltantes[
        [
            "ANO",
            "CO_MUNICIPIO",
            "MOTIVO_FALTA",
            "FINBRA_HAS_ANY",
            "FINBRA_HAS_ALL_5",
            "FINBRA_N_SUBFUNCOES_PRESENTES",
            "CENSO_HAS_ANY",
            "CENSO_MAT_ALVO_POSITIVO",
            "IPCA_ANO_DISPONIVEL",
            "PRONTO_INDICADOR_BASE",
            "PRONTO_INDICADOR_ESTRITO",
        ]
    ].sort_values(["ANO", "MOTIVO_FALTA", "CO_MUNICIPIO"])


def main(anos: list[int]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    panel = build_panel(anos)
    resumo = build_year_summary(panel)
    faltantes = build_missing_table(panel)

    panel.to_csv(OUT_MUN_ANO, index=False, encoding="utf-8-sig")
    resumo.to_csv(OUT_RESUMO, index=False, encoding="utf-8-sig")
    faltantes.to_csv(OUT_FALTANTES, index=False, encoding="utf-8-sig")

    print("Auditoria concluida.")
    print(f"- {OUT_MUN_ANO}")
    print(f"- {OUT_RESUMO}")
    print(f"- {OUT_FALTANTES}")
    print("\nResumo por ano:")
    print(resumo.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--anos", nargs="+", type=int, default=[2020, 2021, 2022, 2023, 2024])
    args = parser.parse_args()
    main(args.anos)
