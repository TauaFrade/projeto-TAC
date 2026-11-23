"""Gera mapas por UF usando malha geografica oficial do IBGE (API v2).

Entradas:
- data/processed/fase5_participacao_uf_sigla.csv
- data/processed/fase5_gap_uf_5areas_sigla_pooled.csv

Saidas (PNG):
- reports/figures_geo/fase5_geo_participacao_uf_2023.png
- reports/figures_geo/fase5_geo_participacao_uf_2024.png
- reports/figures_geo/fase5_geo_participacao_uf_2025.png
- reports/figures_geo/fase5_geo_gap_uf_pooled_NU_NOTA_*.png
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.request import urlopen

import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.patches import Polygon as MplPolygon

import pandas as pd

PART_PATH = Path("data/processed/fase5_participacao_uf_sigla.csv")
GAP_POOL_PATH = Path("data/processed/fase5_gap_uf_5areas_sigla_pooled.csv")
OUT_DIR = Path("reports/figures_geo")

UF_CODES = [11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 32, 33, 35, 41, 42, 43, 50, 51, 52, 53]
UF_NUM_TO_SIGLA = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}

AREAS = ["NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "NU_NOTA_REDACAO"]


def _load_json_from_url(url: str, timeout: int = 35) -> dict:
    with urlopen(url, timeout=timeout) as resp:
        raw = resp.read()
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        txt = gzip.decompress(raw).decode("utf-8")
    return json.loads(txt)


def _extract_polygons(geometry: dict) -> List[List[Tuple[float, float]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    out: List[List[Tuple[float, float]]] = []

    if gtype == "Polygon":
        # Primeiro anel = exterior.
        if coords:
            out.append([(float(x), float(y)) for x, y in coords[0]])
    elif gtype == "MultiPolygon":
        for poly in coords:
            if poly:
                out.append([(float(x), float(y)) for x, y in poly[0]])

    return out


def load_ibge_uf_geoms() -> Dict[str, dict]:
    result: Dict[str, dict] = {}

    for uf_num in UF_CODES:
        url = f"https://servicodados.ibge.gov.br/api/v2/malhas/{uf_num}?formato=application/vnd.geo+json"
        d = _load_json_from_url(url)
        feat = d["features"][0]
        props = feat.get("properties", {})

        sigla = UF_NUM_TO_SIGLA[uf_num]
        centroide = props.get("centroide")
        if not centroide or len(centroide) != 2:
            # fallback simples: media dos vertices
            polys = _extract_polygons(feat["geometry"])
            xs = [x for p in polys for x, _ in p]
            ys = [y for p in polys for _, y in p]
            centroide = [sum(xs) / len(xs), sum(ys) / len(ys)]

        result[sigla] = {
            "uf_num": uf_num,
            "sigla": sigla,
            "centroide": (float(centroide[0]), float(centroide[1])),
            "polygons": _extract_polygons(feat["geometry"]),
        }

    return result


def draw_geo_map(
    values_by_sigla: Dict[str, float],
    geoms: Dict[str, dict],
    title: str,
    out_path: Path,
    cmap: str,
    value_fmt: str,
) -> None:
    vals = [v for v in values_by_sigla.values() if pd.notna(v)]
    if not vals:
        return

    norm = Normalize(vmin=min(vals), vmax=max(vals) if max(vals) > min(vals) else min(vals) + 1e-9)
    cmap_obj = plt.get_cmap(cmap)

    fig, ax = plt.subplots(figsize=(11, 9))
    ax.set_title(title, fontsize=14, weight="bold", pad=12)

    all_x: List[float] = []
    all_y: List[float] = []

    for sigla, g in geoms.items():
        val = values_by_sigla.get(sigla)
        color = "#e6e6e6" if pd.isna(val) else cmap_obj(norm(val))

        for poly in g["polygons"]:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            all_x.extend(xs)
            all_y.extend(ys)
            patch = MplPolygon(poly, closed=True, facecolor=color, edgecolor="white", linewidth=0.8)
            ax.add_patch(patch)

        cx, cy = g["centroide"]
        label = f"{sigla}\n{value_fmt.format(val) if pd.notna(val) else 'NA'}"
        ax.text(cx, cy, label, ha="center", va="center", fontsize=7, color="black")

    ax.set_aspect("equal")
    ax.axis("off")

    if all_x and all_y:
        pad_x = (max(all_x) - min(all_x)) * 0.04
        pad_y = (max(all_y) - min(all_y)) * 0.04
        ax.set_xlim(min(all_x) - pad_x, max(all_x) + pad_x)
        ax.set_ylim(min(all_y) - pad_y, max(all_y) + pad_y)

    sm = ScalarMappable(norm=norm, cmap=cmap_obj)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(labelsize=8)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=240, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    if not PART_PATH.exists() or not GAP_POOL_PATH.exists():
        raise FileNotFoundError("Arquivos da fase 5 nao encontrados em data/processed.")

    part = pd.read_csv(PART_PATH)
    gap = pd.read_csv(GAP_POOL_PATH)

    geoms = load_ibge_uf_geoms()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Participacao por ano
    for ano in sorted(part["ANO"].unique()):
        sub = part[part["ANO"] == ano]
        values = {r.UF_SIGLA: float(r.TAXA_ACESSIVEL_PCT) for r in sub.itertuples(index=False)}
        draw_geo_map(
            values_by_sigla=values,
            geoms=geoms,
            title=f"Taxa de participacao em provas acessiveis por UF ({ano})",
            out_path=OUT_DIR / f"fase5_geo_participacao_uf_{ano}.png",
            cmap="YlGnBu",
            value_fmt="{:.3f}%",
        )

    # Gaps pooled por area
    for area in AREAS:
        sub = gap[gap["AREA"] == area]
        values = {r.UF_SIGLA: float(r.GAP_ACESSIVEL_MENOS_REGULAR) for r in sub.itertuples(index=False)}
        draw_geo_map(
            values_by_sigla=values,
            geoms=geoms,
            title=f"Gap acessivel - regular por UF (pooled 2023-2025) | {area}",
            out_path=OUT_DIR / f"fase5_geo_gap_uf_pooled_{area}.png",
            cmap="RdYlBu",
            value_fmt="{:.1f}",
        )

    print("Mapas geograficos gerados em:")
    for ano in sorted(part["ANO"].unique()):
        print(f"- {OUT_DIR / f'fase5_geo_participacao_uf_{ano}.png'}")
    for area in AREAS:
        print(f"- {OUT_DIR / f'fase5_geo_gap_uf_pooled_{area}.png'}")


if __name__ == "__main__":
    main()
