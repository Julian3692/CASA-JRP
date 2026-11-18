#!/usr/bin/env python3
"""
AUDITORIA COMPLETA de CASA JRP (Orkia + Nudo).

Revisa TODO lo que ya nos fallo alguna vez, para que no vuelva a pasar sin que nadie se entere:
  - feed de Meta contra el catalogo vivo del Sheet (ids, precios, stock, fotos)
  - formato del feed y de las ofertas (fechas, precio de oferta < precio regular, ofertas vencidas)
  - TODAS las fotos (principal rota = FALLO; secundaria rota = AVISO)
  - TODAS las fichas de producto (carga, precio, Pixel, ID del Pixel, WhatsApp, boton y confirmacion, anti doble clic,
    un solo AddToCart, datos estructurados, nada de datos internos)
  - paginas de ayuda y home de cada marca (Pixel, WhatsApp)
  - sitemap (completo y sin enlaces rotos), verificacion de dominio de Meta, robots
  - backend (Apps Script): catalogo vivo y cotizacion de solo lectura (el precio que se cobra = el del feed)

Uso:
  python3 scripts/auditoria.py            # revisa el sitio PUBLICADO (https://casajrp.com)
  python3 scripts/auditoria.py --local    # revisa los archivos del repo (antes de publicar); fotos y backend siempre en vivo

Sale con codigo 1 si hay algun FALLO. Los AVISOS no hacen fallar, pero se listan.
Lo que NO se puede automatizar (cuenta de Meta, prueba real con Nadia, etc.) esta en la lista manual del final.
"""
import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_product_pages as G   # noqa: E402  (constantes reales: AS_URL, WA_NUMBERS, PIXEL_ID)
import policy_pages                  # noqa: E402

BASE = "https://casajrp.com"
ROOT = HERE.parent
UA = {"User-Agent": "Mozilla/5.0 (auditoria-casajrp)"}
TOKEN_META = "8s589ilsd2u2yalo7nwgw7zapafbbx"          # verificacion de dominio de Meta (index.html raiz)
MARCAS = {"orkia": "Orkia", "nudo": "Nudo"}
CAMPOS_FEED = ["id", "title", "description", "availability", "condition", "price", "link", "image_link",
               "brand", "item_group_id", "google_product_category"]
PROHIBIDO_EN_PAGINAS = ["precio_cop", "Precio_COP", "id_proveedor", "nombre_foto"]   # costos / datos de proveedor: FALLO
# ref_proveedor viaja en el codigo de las fichas (agrupa colores y carrito). Decision pendiente del dueno: se lista como AVISO fijo.
TELEFONO_PRUEBA = "50255550000"   # numero inexistente: la cotizacion es de solo lectura y no guarda nada

LOCAL = False
RED = True   # False = modo compuerta (--solo-archivos): no pide nada a internet
R = {"FALLO": [], "AVISO": [], "OK": []}


def reg(nivel, area, msg):
    R[nivel].append((area, msg))


def agrupar(area, titulo, casos, nivel="FALLO", limite=6):
    """Un solo renglon por tipo de revision: OK si no hay casos; si los hay, lista los primeros."""
    if not casos:
        reg("OK", area, titulo)
        return
    ej = "; ".join(str(c) for c in casos[:limite]) + (f" ... (+{len(casos) - limite} mas)" if len(casos) > limite else "")
    reg(nivel, area, f"{titulo}: {len(casos)} caso(s) -> {ej}")


def http(url, method="GET", data=None, headers=None, timeout=30, tries=2):
    h = dict(UA)
    h.update(headers or {})
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, dict(r.headers), (r.read() if method != "HEAD" else b"")
        except urllib.error.HTTPError as e:
            if e.code == 404 or i == tries - 1:
                return e.code, {}, b""
        except Exception as e:  # tiempo agotado, DNS, etc.
            if i == tries - 1:
                return 0, {"error": str(e)}, b""
        time.sleep(1)
    return 0, {}, b""


def leer(path):
    """Lee un archivo del sitio: del repo (--local) o del sitio publicado. None si no existe."""
    if LOCAL:
        p = ROOT / path
        return p.read_text(encoding="utf-8") if p.exists() else None
    ruta = path[:-len("index.html")] if path.endswith("index.html") else path
    s, _, b = http(f"{BASE}/{ruta}?v={time.time_ns()}")
    return b.decode("utf-8", "ignore") if s == 200 else None


def estado_url(url):
    """200 si existe, 404 si no, otro/0 si no se pudo saber. Prueba HEAD y, si el servidor no lo permite, GET."""
    s, _, _ = http(url, "HEAD")
    if s in (403, 405, 0):
        s, _, _ = http(url, "GET")
    return s


def es_imagen(url):
    s, h, _ = http(url, "HEAD")
    if s in (403, 405, 0):
        return estado_url(url), None
    return s, (h.get("Content-Type") or h.get("content-type") or "")


# --------------------------------------------------------------------------------------------------
def auditar_marca(marca):
    A = MARCAS[marca]
    # ---- feed y catalogo vivo
    txt = leer(f"feeds/{marca}.csv")
    if txt is None:
        reg("FALLO", A, "no se pudo leer el feed feeds/%s.csv" % marca)
        return None
    filas = list(csv.DictReader(io.StringIO(txt)))
    F = {r["id"]: r for r in filas}
    agrupar(A, "Feed: ids unicos", [r["id"] for r in filas if [x["id"] for x in filas].count(r["id"]) > 1])
    faltan_cols = [c for c in CAMPOS_FEED + ["sale_price", "sale_price_effective_date", "additional_image_link"] if filas and c not in filas[0]]
    agrupar(A, "Feed: columnas requeridas presentes", faltan_cols)

    s, b = 0, b""
    if RED:
        s, _, b = http(f"{G.AS_URL}?accion=get_catalogo&marca={marca}&_ts={time.time_ns()}", timeout=60)
    try:
        d = json.loads(b.decode("utf-8"))
    except Exception:
        d = {}
    if not RED:
        vivo = {}
    elif not d.get("ok"):
        reg("FALLO", A, f"backend: get_catalogo no responde bien (HTTP {s})")
        vivo = {}
    else:
        vivo = {str(p["id_producto"]): p for p in d["productos"]}
        reg("OK", A, f"backend: get_catalogo responde ({d.get('total')} productos)")
        if d.get("total") != len(vivo):
            reg("FALLO", A, f"backend: total={d.get('total')} pero trae {len(vivo)} productos")
        agrupar(A, "Backend: catalogo vivo no expone datos internos de proveedor/stock",
                [k for k in ("ref_proveedor", "stock_total") if vivo and k in next(iter(vivo.values()))],
                nivel="AVISO")

    # ---- feed contra catalogo vivo
    if vivo:
        solo_feed = sorted(set(F) - set(vivo))
        solo_vivo = sorted(set(vivo) - set(F))
        agrupar(A, "Feed vs catalogo vivo: mismos productos", [f"solo en feed {solo_feed}"] * bool(solo_feed) + [f"solo en vivo {solo_vivo}"] * bool(solo_vivo))
        pr, dis, img = [], [], []
        for i, r in F.items():
            p = vivo.get(i)
            if not p:
                continue
            try:
                if abs(float(r["price"].split()[0]) - float(p["precio_gtq"])) > 0.001:
                    pr.append(f"{i}: feed {r['price']} vs vivo {p['precio_gtq']}")
            except Exception:
                pr.append(f"{i}: precio ilegible")
            en_stock = (not p.get("agotado")) and (p.get("stock_total") or 0) > 0
            if (r["availability"] == "in stock") != en_stock:
                dis.append(f"{i}: feed '{r['availability']}' vs vivo agotado={p.get('agotado')} stock={p.get('stock_total')}")
            if r["image_link"] != p.get("url_imagen"):
                img.append(i)
        agrupar(A, "Feed vs catalogo vivo: precio regular igual", pr)
        agrupar(A, "Feed vs catalogo vivo: disponibilidad igual", dis)
        agrupar(A, "Feed vs catalogo vivo: foto principal igual", img)

    # ---- formato del feed y ofertas
    malos, ofertas, vencidas, brand_mal, largos, links = [], [], [], [], [], []
    ahora = datetime.now(timezone.utc)
    pat_precio = re.compile(r"^\d+\.\d{2} GTQ$")
    pat_ven = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d[+-]\d{4})/(\d{4}-\d\d-\d\dT\d\d:\d\d[+-]\d{4})$")
    for i, r in F.items():
        if not pat_precio.match(r["price"]):
            malos.append(f"{i}: precio '{r['price']}'")
            continue
        p = float(r["price"].split()[0])
        if p <= 0:
            malos.append(f"{i}: precio <= 0")
        for c in CAMPOS_FEED:
            if not (r.get(c) or "").strip():
                malos.append(f"{i}: vacio {c}")
        if r["availability"] not in ("in stock", "out of stock"):
            malos.append(f"{i}: availability '{r['availability']}'")
        if len(r["title"]) > 150:
            largos.append(i)
        if r["brand"] != A:
            brand_mal.append(f"{i}: brand '{r['brand']}'")
        if r["link"] != f"{BASE}/{marca}/producto/{i}/":
            links.append(f"{i}: {r['link']}")
        sp, ef = r.get("sale_price", ""), r.get("sale_price_effective_date", "")
        if sp:
            if not pat_precio.match(sp):
                ofertas.append(f"{i}: sale_price mal formado")
                continue
            if float(sp.split()[0]) >= p:
                ofertas.append(f"{i}: oferta {sp} >= precio {r['price']}")
            m = pat_ven.match(ef)
            if not m:
                ofertas.append(f"{i}: fecha de oferta mal formada '{ef}'")
            else:
                a = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M%z")
                z = datetime.strptime(m.group(2), "%Y-%m-%dT%H:%M%z")
                if a >= z:
                    ofertas.append(f"{i}: inicio >= fin")
                if z < ahora:
                    vencidas.append(f"{i}: terminó {m.group(2)}")
        elif ef:
            ofertas.append(f"{i}: fecha de oferta sin precio de oferta")
    agrupar(A, "Feed: campos obligatorios, precios y disponibilidad bien formados", malos)
    agrupar(A, "Feed: brand correcto en todas las filas", brand_mal)
    agrupar(A, "Feed: enlaces a la ficha correctos", links)
    agrupar(A, "Feed: titulos <= 150 caracteres", largos, nivel="AVISO")
    agrupar(A, "Feed: ofertas bien formadas (precio < regular, fechas validas)", ofertas)
    agrupar(A, "Feed: sin ofertas ya vencidas", vencidas, nivel="AVISO")

    # ---- fotos
    if RED:
        principales = {r["image_link"]: i for i, r in F.items()}
        extras = {}
        for i, r in F.items():
            for u in (r.get("additional_image_link") or "").split(","):
                if u.strip():
                    extras[u.strip()] = i
        en_vivo_no_feed = {}
        for i, p in vivo.items():
            for k in ("url_imagen_2", "url_imagen_3"):
                u = p.get(k)
                if u and u not in extras:
                    en_vivo_no_feed[u] = i
        todas = {**principales, **extras, **en_vivo_no_feed}
        with ThreadPoolExecutor(12) as ex:
            res = dict(zip(todas, ex.map(es_imagen, list(todas))))
        f_princ = [f"{todas[u]} ({res[u][0]})" for u in principales if res[u][0] != 200 or (res[u][1] and "image" not in res[u][1])]
        f_extra = [f"{todas[u]} {u.rsplit('/', 1)[-1]} ({res[u][0]})" for u in extras if res[u][0] != 200 or (res[u][1] and "image" not in res[u][1])]
        f_vivo = [f"{todas[u]} {u.rsplit('/', 1)[-1]} ({res[u][0]})" for u in en_vivo_no_feed if res[u][0] != 200]
        agrupar(A, f"Fotos principales ({len(principales)}): todas existen y son imagen", f_princ)
        agrupar(A, f"Fotos extra del feed ({len(extras)}): todas existen", f_extra)
        agrupar(A, "Fotos que el catalogo vivo lista pero faltan en el almacenamiento (el generador ya las omite en feed y fichas)", f_vivo, nivel="AVISO")

    # ---- fichas de producto
    numero = G.WA_NUMBERS[marca]

    def ficha(i):
        r = F[i]
        h = leer(f"{marca}/producto/{i}/index.html")
        f = []
        if h is None:
            return i, ["no carga"]
        if f'<link rel="canonical" href="{BASE}/{marca}/producto/{i}/"' not in h:
            f.append("canonical incorrecto")
        t = re.search(r"<title>(.+?)</title>", h, re.S)
        if not t or not t.group(1).strip():
            f.append("sin <title>")
        if "noindex" in h.lower():
            f.append("noindex")
        if re.findall(r"fbq\('init', *'(\d+)'\)", h) != [G.PIXEL_ID]:
            f.append("Pixel: init distinto de 1 vez con el ID correcto")
        if h.count("fbq('track', 'PageView'") != 1:
            f.append("Pixel: PageView debe dispararse exactamente 1 vez")
        # ViewContent se dispara desde px() con el precio VIGENTE (oferta incluida); nunca con un valor escrito fijo en el <head>
        if "fbq('track', 'ViewContent'" in h:
            f.append("Pixel: ViewContent con valor fijo en el <head> (debe usar el precio vigente via px)")
        if h.count("px('ViewContent')") != 1:
            f.append(f"Pixel: ViewContent debe dispararse exactamente 1 vez desde px() (hay {h.count(chr(112) + 'x(' + chr(39) + 'ViewContent' + chr(39) + ')')})")
        if f'PID = "{i}"' not in h or "content_ids:[PID]" not in h:
            f.append("Pixel: content_ids no coincide con el id del producto")
        m = re.search(r"PRICE = ([\d.]+)", h)
        if not m or abs(float(m.group(1)) - float(r["price"].split()[0])) > 0.001:
            f.append(f"precio de la ficha {m.group(1) if m else '?'} != feed {r['price']}")
        if set(re.findall(r"wa\.me/(\d+)", h)) != {numero}:
            f.append("numero de WhatsApp distinto del configurado")
        ld = [x for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
        okld = False
        for x in ld:
            try:
                o = json.loads(x)
            except Exception:
                continue
            if o.get("@type") == "Product":
                okld = (str(o.get("sku")) == i and abs(float(o["offers"]["price"]) - float(r["price"].split()[0])) < 0.001
                        and (("InStock" in o["offers"]["availability"]) == (r["availability"] == "in stock")))
        if not okld:
            f.append("datos estructurados (JSON-LD) ausentes o inconsistentes")
        btn = re.search(r'<button[^>]*id="addBtn"[^>]*>', h)
        if not btn:
            f.append("sin boton de agregar")
        else:
            deshab = " disabled" in btn.group(0)
            if (r["availability"] == "in stock") == deshab:
                f.append("estado del boton no coincide con la disponibilidad")
        if r["availability"] == "in stock":
            if 'id="confirmMsg"' not in h or "Ver mi selecci" not in h or f"/{marca}/?abrirSeleccion=1" not in h:
                f.append("falta el cuadro de confirmacion con 'Ver mi seleccion'")
            if ("btn.dataset.lock === '1'" not in h or "btn.dataset.lock = '1'" not in h
                    or "btn.dataset.added = '1'" not in h or "dataset.added !== '1'" not in h):
                f.append("falta la proteccion anti doble clic")
            n_atc = h.count("px('AddToCart')")
            if n_atc != 1:
                f.append(f"AddToCart se dispara {n_atc} veces en el codigo (debe ser 1)")
        for pal in PROHIBIDO_EN_PAGINAS:
            if pal in h:
                f.append(f"dato interno visible: {pal}")
        if 'src="http://' in h or "href=\"http://casajrp" in h:
            f.append("enlace http (sin cifrar)")
        if "ref_proveedor" in h:
            f.append("@AVISO ref_proveedor visible en el codigo de la ficha (decision pendiente del dueno)")
        # --- UX (auditoria UX/UI 18-nov-2026, lote 1)
        if 'class="size-btn' in h:
            if "const NEEDS_SIZE = true" not in h or 'id="sizeError"' not in h:
                f.append("UX: hay tallas pero falta la obligacion de elegir talla / su aviso")
            if re.search(r'class="size-btn[^"]*\bactive\b', h):
                f.append("UX: una talla viene preseleccionada (debe elegirla la clienta)")
        if '<p class="desc">' in h:
            f.append("UX: descripcion repetida bajo el titulo")
        if 'class="color-code"' in h:
            f.append("UX: codigo interno visible dentro del chip de color")
        if "UX lote 1" not in h:
            f.append("UX: falta el bloque de estilos de legibilidad/contraste/areas tactiles")
        if r["availability"] == "in stock" and ('id="buyBar"' not in h or 'id="buyBarBtn"' not in h):
            f.append("UX: falta la barra de compra fija (precio y boton siempre visibles)")
        # Prendas de abajo: los recomendados deben incluir alternativas del mismo tipo (si existen)
        tipo = (r.get("product_type") or "").strip()
        if marca == "orkia" and tipo.lower() in ("jean", "pantalon", "falda"):
            rel = re.findall(r'class="related-card" href="/' + marca + r'/producto/(\d+)/"', h)
            alt = {x["item_group_id"] for x in filas if x["product_type"] == tipo and x["item_group_id"] != r["item_group_id"] and x["availability"] == "in stock"}
            mismos = [x for x in rel if x in F and F[x]["product_type"] == tipo]
            if len(mismos) < min(2, len(alt)):
                f.append(f"UX: los recomendados no incluyen alternativas del mismo tipo ({tipo}); hay {len(alt)} disponibles y salen {len(mismos)}")
        return i, f

    with ThreadPoolExecutor(10) as ex:
        resultados = list(ex.map(ficha, list(F)))
    por_tipo = {}
    for i, fs in resultados:
        for x in fs:
            por_tipo.setdefault(x, []).append(i)
    duros = {x: ids for x, ids in por_tipo.items() if not x.startswith("@AVISO ")}
    if not duros:
        reg("OK", A, f"Fichas de producto ({len(F)}): carga, canonical, Pixel, precio, WhatsApp, boton, confirmacion, anti doble clic, 1 solo AddToCart, JSON-LD, sin costos")
    for x, ids in por_tipo.items():
        nivel = "AVISO" if x.startswith("@AVISO ") else "FALLO"
        reg(nivel, A, f"Fichas: {x.replace('@AVISO ', '')} -> {len(ids)} ficha(s): {', '.join(ids[:5])}{' ...' if len(ids) > 5 else ''}")

    # ---- home y paginas de ayuda de la marca
    paginas = [f"{marca}/index.html"] + [f"{marca}/{slug}/index.html" for slug, _, _ in policy_pages.POLICY_PAGES]
    malas = []
    for pth in paginas:
        h = leer(pth)
        if h is None:
            malas.append(f"{pth}: no carga")
            continue
        if not re.search(r"<title>(.+?)</title>", h, re.S):
            malas.append(f"{pth}: sin title")
        if re.findall(r"fbq\('init', *'(\d+)'\)", h) != [G.PIXEL_ID]:
            malas.append(f"{pth}: Pixel init != 1 vez con el ID correcto")
        if pth == f"{marca}/index.html" and "UX lote 1" not in h:
            malas.append(f"{pth}: falta el bloque de estilos UX lote 1 (letra, contraste, areas tactiles)")
        if pth == f"{marca}/index.html":
            for marcador, que in (("data-qty", "botones de cantidad (- / +) en la seleccion"), ("bag-total", "total estimado en la seleccion"),
                                  ("unidadesPedido", "el mensaje de WhatsApp cuenta unidades"), ("num_items: unidadesPedido", "InitiateCheckout cuenta unidades"), ("function tallaTxt", "regla de talla unica/por confirmar")):
                if marcador not in h:
                    malas.append(f"{pth}: falta {que}")
    agrupar(A, f"Home y paginas de ayuda ({len(paginas)}): cargan, tienen titulo, el Pixel correcto y los estilos UX", malas)
    # contraste de los colores de marca para texto pequeno (WCAG AA: 4,5:1)
    br = G.BRANDS[marca]
    def _lum(hx):
        c = [int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    def _ratio(a, b):
        la, lb = _lum(a), _lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
    cmal = []
    texto = br.get("terracota_texto", br["terracota"]); fuerte = br.get("terracota_fuerte", br["terracota"])
    if _ratio(texto, "#FFFFFF") < 4.5: cmal.append(f"texto de acento {texto} sobre blanco {_ratio(texto, '#FFFFFF'):.2f}:1")
    if _ratio(texto, br["bg"]) < 4.5: cmal.append(f"texto de acento {texto} sobre fondo {br['bg']} {_ratio(texto, br['bg']):.2f}:1")
    if _ratio(fuerte, "#FFFFFF") < 4.5: cmal.append(f"blanco sobre {fuerte} {_ratio(fuerte, '#FFFFFF'):.2f}:1")
    agrupar(A, "Colores de marca: contraste >= 4,5:1 para texto pequeno de acento y texto blanco sobre acento", cmal)

    # ---- cotizacion de solo lectura: el precio que se cobra = el del feed
    if RED:
        cand = [r for r in filas if r["availability"] == "in stock"]
        con_of = [r for r in cand if r.get("sale_price")]
        sin_of = [r for r in cand if not r.get("sale_price")]
        muestra = (con_of[:1] + sin_of[:1]) or cand[:1]
        cot_mal = []
        for r in muestra:
            body = json.dumps({"accion": "cotizar_pedido", "marca": marca, "telefono": TELEFONO_PRUEBA,
                               "lineas": [{"id_producto": int(r["id"]), "cantidad": 1}]}).encode("utf-8")
            s, _, b = http(G.AS_URL, "POST", body, {"Content-Type": "text/plain;charset=utf-8"}, timeout=60)
            try:
                q = json.loads(b.decode("utf-8"))
            except Exception:
                q = {}
            if not q.get("ok"):
                cot_mal.append(f"{r['id']}: cotizacion fallo (HTTP {s}) {str(q)[:80]}")
                continue
            reg_p = float(r["price"].split()[0])
            if abs(float(q["subtotal_regular_gtq"]) - reg_p) > 0.001:
                cot_mal.append(f"{r['id']}: regular cotizado {q['subtotal_regular_gtq']} != feed {reg_p}")
            m = pat_ven.match(r.get("sale_price_effective_date", ""))
            if r.get("sale_price") and m:
                a = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M%z")
                z = datetime.strptime(m.group(2), "%Y-%m-%dT%H:%M%z")
                esperado = float(r["sale_price"].split()[0]) if a <= ahora < z else reg_p
                if abs(float(q["subtotal_gtq"]) - esperado) > 0.001:
                    cot_mal.append(f"{r['id']}: cobra {q['subtotal_gtq']} pero el feed implica {esperado}")
            elif abs(float(q["subtotal_gtq"]) - reg_p) > 0.001:
                cot_mal.append(f"{r['id']}: cobra {q['subtotal_gtq']} pero el precio es {reg_p}")
        agrupar(A, f"Backend: cotizacion de solo lectura coincide con el feed ({len(muestra)} producto(s) de muestra)", cot_mal)
    return set(F)


def auditar_global(ids_por_marca):
    # ---- sitemap
    sm = leer("sitemap.xml")
    if sm is None:
        reg("FALLO", "Sitio", "no carga sitemap.xml")
    else:
        locs = re.findall(r"<loc>([^<]+)</loc>", sm)
        faltan = [f"{m}/{i}" for m, ids in ids_por_marca.items() if ids for i in sorted(ids) if f"{BASE}/{m}/producto/{i}/" not in locs]
        agrupar("Sitio", f"Sitemap ({len(locs)} direcciones) incluye todas las fichas", faltan)
        if not LOCAL:
            with ThreadPoolExecutor(12) as ex:
                st = list(ex.map(estado_url, locs))
            rotos = [f"{u} ({s})" for u, s in zip(locs, st) if s != 200]
            agrupar("Sitio", "Sitemap: todas las direcciones responden 200", rotos)
    # ---- raiz, verificacion de Meta y robots
    raiz = leer("index.html")
    if raiz is None:
        reg("FALLO", "Sitio", "no carga la pagina principal")
    else:
        agrupar("Sitio", "Verificacion de dominio de Meta presente en la pagina principal",
                [] if f'name="facebook-domain-verification" content="{TOKEN_META}"' in raiz else ["falta o cambio el meta-tag"])
    s = estado_url(f"{BASE}/robots.txt") if not LOCAL else 200
    agrupar("Sitio", "robots.txt responde", [] if s == 200 else [f"HTTP {s}"])
    # ---- numero de WhatsApp de Nudo (recordatorio hasta que se active el nuevo)
    if G.WA_NUMBERS.get("nudo") == G.WA_NUMBERS.get("orkia"):
        reg("AVISO", "Nudo", "Nudo usa el MISMO WhatsApp que Orkia; falta activar WhatsApp Business de Nudo y cambiar WA_NUMBERS['nudo']")


LISTA_MANUAL = [
    "Meta: dominio casajrp.com 'Verified' (Settings > Brand safety > Domains).",
    "Meta: catalogos Orkia y Nudo sin errores en Diagnostics; cantidad de productos = feed; 'Last updated' reciente.",
    "Meta: Event match quality / Catalog match rate recalculados (revisar 24-48 h despues de cambios).",
    "Meta: la oferta se ve activa en el catalogo el dia que empieza (Q143 el 20-nov para la blusa 10022).",
    "Meta (Test events): PageView, ViewContent y AddToCart llegan una sola vez por clic en una ficha real.",
    "Meta: cuenta publicitaria con metodo de pago y moneda confirmados; conjuntos de anuncios existentes sin gasto no deseado.",
    "Operacion: prueba real de pedido con Nadia (app y WhatsApp); filas de prueba borradas del Sheet.",
    "Operacion: WhatsApp Business de Nudo activo y atendido antes de cambiar el numero.",
    "UX (medir en el navegador, en formato celular): CLS de la home < 0,1; LCP < 2,5 s; letra minima 11 px; areas tactiles >= 44 px; ninguna foto con texto/referencia del proveedor.",
    "UX: en celular, precio y boton de compra a la vista en la primera pantalla de una ficha (barra fija) y en escritorio (portatil 1366x768).",
]


def main():
    global LOCAL, RED
    ap = argparse.ArgumentParser(description="Auditoria completa de CASA JRP")
    ap.add_argument("--local", action="store_true", help="leer paginas/feeds/sitemap del repo en vez del sitio publicado")
    ap.add_argument("--solo-archivos", action="store_true",
                    help="modo COMPUERTA: revisa solo los archivos del repo, sin pedir nada a internet (fotos, catalogo vivo, cotizaciones)")
    args = ap.parse_args()
    LOCAL = args.local or args.solo_archivos
    RED = not args.solo_archivos
    t0 = time.time()
    print(f"AUDITORIA CASA JRP  |  fuente: {('archivos del repo (sin red)' if not RED else 'archivos del repo') if LOCAL else BASE}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    ids = {}
    for m in MARCAS:
        ids[m] = auditar_marca(m)
    auditar_global(ids)

    print()
    for nivel, marca_txt in (("FALLO", "FALLO "), ("AVISO", "AVISO "), ("OK", "ok    ")):
        for area, msg in R[nivel]:
            if nivel == "OK" and not VERBOSE_OK:
                continue
            print(f"[{marca_txt}] {area}: {msg}")
    print("\nRESUMEN:  FALLOS =", len(R["FALLO"]), " | AVISOS =", len(R["AVISO"]), " | revisiones OK =", len(R["OK"]),
          f" | {time.time() - t0:.0f} s")
    print("\nPENDIENTE DE REVISAR A MANO (no se puede automatizar):")
    for x in LISTA_MANUAL:
        print("  [ ]", x)
    sys.exit(1 if R["FALLO"] else 0)


VERBOSE_OK = True

if __name__ == "__main__":
    main()
