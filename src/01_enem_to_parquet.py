"""Lê os microdados do ENEM (2023–2025), seleciona colunas, classifica o grupo
de cada participante pelo código do caderno e salva em Parquet.

Uso (rodar da raiz do projeto):
  python src/01_enem_to_parquet.py --inspect       # só confere cabeçalhos
  python src/01_enem_to_parquet.py                 # converte os três anos
  python src/01_enem_to_parquet.py --anos 2023     # converte só um ano

Estrutura esperada dos dados brutos:
  data/raw/enem/2023/  -> um CSV com "MICRODADOS" no nome
  data/raw/enem/2024/  -> CSVs com "PARTICIPANTES" e "RESULTADOS" no nome
  data/raw/enem/2025/  -> idem

Observações dos dicionários do Inep:
  * Renda familiar: Q006 em 2023; em 2024 e 2025 a Q006 é "possui renda? (sim/não)"
    e a renda familiar é a Q007. Aqui as duas viram a coluna RENDA_FAM (A–Q).
  * 2024 e 2025: NU_SEQUENCIAL (resultados) NÃO permite ligar à NU_INSCRICAO
    (participantes), conforme nota do próprio dicionário. Logo, a renda não pode ser
    associada às notas nesses anos; só 2023 tem renda por participante com nota.
"""
import argparse
from pathlib import Path

import pandas as pd

RAW = Path("data/raw/enem")
OUT = Path("data/interim")
AREAS = ["CN", "CH", "LC", "MT"]

# TX_RESPOSTAS_* ficam de fora: não entram na análise e pesam muito na memória.
WANTED = (
    ["NU_INSCRICAO", "TP_SEXO", "TP_COR_RACA", "TP_ST_CONCLUSAO", "TP_ANO_CONCLUIU",
     "TP_ESCOLA", "TP_ENSINO", "IN_TREINEIRO", "Q006", "Q007", "CO_ESCOLA",
     "CO_MUNICIPIO_ESC", "TP_DEPENDENCIA_ADM_ESC", "TP_LOCALIZACAO_ESC",
     "CO_MUNICIPIO_PROVA", "CO_UF_PROVA", "SG_UF_PROVA",
     "TP_STATUS_REDACAO", "NU_NOTA_REDACAO"]
    + [f"{p}_{a}" for a in AREAS for p in ("TP_PRESENCA", "CO_PROVA", "NU_NOTA")]
)

# Códigos de CO_PROVA_* (qualquer área) por grupo, conforme os dicionários do Inep.
#   libras       = Videoprova Libras (inclui Libras ampliada/superampliada)
#   braile_ledor = Braile (só 2023) e Adaptada Ledor (inclui reaplicação)
#   outro_atend  = Ampliada, Superampliada e Atendimento Especializado (inclui BAM2)
# Nota: no dicionário de 2024 o código de LC "Libras - Superampliada" aparece como
# "405" (provável erro de digitação de 1405); os dois estão listados.
CODIGOS = {
    2023: {
        "libras": [1229, 1199, 1209, 1219],
        "braile_ledor": [1227, 1197, 1207, 1217,        # Braile
                         1228, 1198, 1208, 1218],       # Adaptada Ledor
        "outro_atend": [1225, 1226, 1195, 1196, 1205, 1206, 1215, 1216],
    },
    2024: {
        "libras": [1427, 1428, 1391, 1392, 1393, 1403, 1404, 405, 1405, 1415, 1416],
        "braile_ledor": [1426, 1390, 1402, 1414,        # Adaptada Ledor
                         1380, 1350, 1360, 1370],       # Adaptada Ledor (reaplicação)
        "outro_atend": [1423, 1424, 1387, 1388, 1399, 1400, 1411, 1412,
                        1377, 1378, 1347, 1348, 1357, 1358, 1367, 1368],  # + reaplicação
    },
    2025: {
        "libras": [1491, 1455, 1467, 1479],
        "braile_ledor": [1490, 1454, 1466, 1478],       # Adaptada Ledor
        "outro_atend": [1487, 1488, 1498, 1623, 1634,   # CN (inclui BAM2)
                        1451, 1452, 1495, 1587, 1631,   # CH
                        1463, 1464, 1496, 1599, 1632,   # LC
                        1475, 1476, 1497, 1611, 1633],  # MT
    },
}

# Códigos IBGE (7 dígitos) das 27 capitais. Conferir contra a tabela do IBGE.
CAPITAIS = {
    1200401, 2704302, 1600303, 1302603, 2927408, 2304400, 5300108, 3205309,
    5208707, 2111300, 5103403, 5002704, 3106200, 1501402, 2507507, 4106902,
    2611606, 2211001, 3304557, 2408102, 4314902, 1100205, 1400100, 4205407,
    3550308, 2800308, 1721000,
}
assert len(CAPITAIS) == 27
for _ano, _g in CODIGOS.items():  # um código não pode estar em dois grupos
    _todos = [c for lst in _g.values() for c in lst]
    assert len(_todos) == len(set(_todos)), f"código repetido em {_ano}"


def achar(ano, termo):
    achados = [p for p in (RAW / str(ano)).rglob("*.csv") if termo in p.name.upper()]
    if len(achados) != 1:
        raise FileNotFoundError(
            f"{ano}: esperava 1 CSV com '{termo}' em {RAW / str(ano)}, achei {achados}")
    return achados[0]


def arquivos(ano):
    if ano == 2023:
        return {"unico": achar(ano, "MICRODADOS")}
    return {"part": achar(ano, "PARTICIPANTES"), "res": achar(ano, "RESULTADOS")}


def cabecalho(path):
    return list(pd.read_csv(path, sep=";", nrows=0, encoding="latin-1").columns)


def ler(path, colunas):
    for enc in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, sep=";", encoding=enc, usecols=colunas)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"não consegui decodificar {path}")


def inspecionar(ano):
    print(f"\n===== {ano} =====")
    for nome, path in arquivos(ano).items():
        hdr = cabecalho(path)
        faltam = [c for c in WANTED if c not in hdr]
        print(f"[{nome}] {path.name}: {len(hdr)} colunas")
        print(f"   desejadas que NÃO estão neste arquivo: {faltam}")


def carregar(ano):
    arqs = arquivos(ano)
    if "unico" in arqs:
        hdr = cabecalho(arqs["unico"])
        return ler(arqs["unico"], [c for c in WANTED if c in hdr])
    # 2024/2025: as bases não se ligam (ver docstring). Usa só RESULTADOS.
    hr = cabecalho(arqs["res"])
    print("   Participantes e resultados NÃO são ligáveis (nota do dicionário do Inep).")
    print("   Lendo só RESULTADOS; renda por participante indisponível neste ano.")
    return ler(arqs["res"], [c for c in WANTED if c in hr])


def colunas_prova(df):
    return [f"CO_PROVA_{a}" for a in AREAS if f"CO_PROVA_{a}" in df.columns]


def classificar(df, ano):
    cols = colunas_prova(df)
    grupo = pd.Series("regular", index=df.index)
    for nome in ("outro_atend", "braile_ledor", "libras"):  # libras prevalece se houver conflito
        grupo[df[cols].isin(CODIGOS[ano][nome]).any(axis=1)] = nome
    return grupo


def converter(ano):
    print(f"\n===== {ano} =====")
    df = carregar(ano)
    faltam = [c for c in WANTED if c not in df.columns]
    print(f"   colunas desejadas ausentes: {faltam}")

    # Renda familiar harmonizada (categorias A–Q nos três anos)
    if ano == 2023:
        df["RENDA_FAM"] = df["Q006"]
    else:
        df["RENDA_FAM"] = df["Q007"] if "Q007" in df.columns else pd.NA
    df = df.drop(columns=[c for c in ("Q006", "Q007") if c in df.columns])
    if df["RENDA_FAM"].notna().any():
        print(f"   RENDA_FAM ausente: {df['RENDA_FAM'].isna().mean():.2%} | "
              f"categorias: {sorted(df['RENDA_FAM'].dropna().unique())}")
    else:
        print("   RENDA_FAM indisponível neste ano")

    df["ANO"] = ano
    df["GRUPO"] = classificar(df, ano)

    # UF = 2 primeiros dígitos do código IBGE (7 dígitos). Ex.: Brasília 5300108 -> 53 (DF)
    mun = df["CO_MUNICIPIO_PROVA"]
    df["UF_PROVA"] = (mun // 100000).astype("Int64")
    if "CO_UF_PROVA" in df.columns:
        dif = (df["UF_PROVA"] != df["CO_UF_PROVA"]).sum()
        print(f"   UF derivada x CO_UF_PROVA: {dif} linhas divergentes")
    df["CAPITAL_PROVA"] = mun.isin(CAPITAIS).where(mun.notna())  # True=capital, False=interior

    cols = colunas_prova(df)
    print("   códigos de CO_PROVA encontrados por grupo especial (conferência):")
    for g in ("libras", "braile_ledor", "outro_atend"):
        sub = df[df["GRUPO"] == g]
        cod = pd.concat([sub[c] for c in cols]).dropna().astype(int).value_counts().sort_index()
        print(f"     {g}: {cod.to_dict()}")
    compareceu = df[cols].notna().any(axis=1)
    print("   participantes com caderno (compareceram a ao menos uma prova):")
    print(df.loc[compareceu, "GRUPO"].value_counts().to_string())
    for a in AREAS:
        print(f"   notas válidas {a}:", df.groupby("GRUPO")[f"NU_NOTA_{a}"].count().to_dict())
    print("   notas válidas REDACAO:", df.groupby("GRUPO")["NU_NOTA_REDACAO"].count().to_dict())

    OUT.mkdir(parents=True, exist_ok=True)
    destino = OUT / f"enem_{ano}.parquet"
    df.to_parquet(destino, index=False)
    print(f"   salvo em {destino}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--anos", nargs="+", type=int, default=[2023, 2024, 2025])
    args = ap.parse_args()
    for a in args.anos:
        inspecionar(a) if args.inspect else converter(a)