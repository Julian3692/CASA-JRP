#!/usr/bin/env python3
"""Revision de seguridad ANTES de publicar paginas regeneradas automaticamente.

Si algo no cuadra, sale con error y el flujo automatico NO publica nada.
Uso: python3 scripts/check_generated.py [--root RUTA]
"""
import argparse
import csv
import re
import sys
from pathlib import Path

PROHIBIDO = re.compile(r"precio_cop|id_proveedor|nombre_foto|Precio_COP|costeo", re.I)
MINIMOS = {"orkia": 100, "nudo": 50}   # productos publicados hoy: 114 y 61


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    root = Path(ap.parse_args().root)
    errores = []

    for marca, minimo in MINIMOS.items():
        paginas = [d for d in (root / marca / "producto").glob("*") if (d / "index.html").exists()]
        feed = root / "feeds" / f"{marca}.csv"
        if len(paginas) < minimo:
            errores.append(f"{marca}: solo {len(paginas)} paginas de producto (minimo {minimo})")
        if not feed.exists():
            errores.append(f"falta feeds/{marca}.csv")
            continue
        filas = list(csv.DictReader(open(feed, encoding="utf-8")))
        if len(filas) < minimo:
            errores.append(f"{marca}: el catalogo de Meta tiene solo {len(filas)} filas (minimo {minimo})")
        ids = [f["id"] for f in filas]
        if len(ids) != len(set(ids)):
            errores.append(f"{marca}: ids repetidos en el catalogo de Meta")
        for f in filas:
            for c in ("id", "title", "price", "link", "image_link"):
                if not (f.get(c) or "").strip():
                    errores.append(f"{marca}: el producto {f.get('id')} no tiene '{c}'")
                    break
            if not re.fullmatch(r"\d+\.\d{2} GTQ", f.get("price", "")):
                errores.append(f"{marca}: el producto {f.get('id')} tiene precio raro: {f.get('price')}")
        sin_pagina = [i for i in ids if not (root / marca / "producto" / i / "index.html").exists()]
        if sin_pagina:
            errores.append(f"{marca}: {len(sin_pagina)} productos del catalogo no tienen pagina (ej. {sin_pagina[:3]})")

    sm = root / "sitemap.xml"
    n = len(re.findall(r"<loc>", sm.read_text(encoding="utf-8"))) if sm.exists() else 0
    if n < 150:
        errores.append(f"sitemap.xml tiene solo {n} direcciones (minimo 150)")

    for carpeta in ("orkia", "nudo", "feeds"):
        for p in (root / carpeta).rglob("*"):
            if p.suffix in (".html", ".csv") and p.is_file() and PROHIBIDO.search(p.read_text(encoding="utf-8", errors="ignore")):
                errores.append(f"datos internos en {p.relative_to(root)}")
                break

    if errores:
        print("NO SE PUBLICA. Problemas:")
        [print(" -", e) for e in errores]
        sys.exit(1)
    print(f"Revision OK: paginas, catalogos y sitemap ({n} direcciones) coherentes; sin datos internos.")


if __name__ == "__main__":
    main()
