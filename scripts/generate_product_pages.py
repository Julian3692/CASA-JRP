#!/usr/bin/env python3
"""
Genera una pagina estatica REAL por producto (SEO + destino limpio para
anuncios + navegacion principal del catalogo), una por cada SKU publicado
de Orkia y Nudo, en {marca}/producto/{id}/index.html.

La presentacion reutiliza el mismo sistema visual del sitio (header oscuro
con logo serif + punto, banner de envio, tipografia Cormorant
Garamond/Playfair Display + DM Sans, botones y swatches con la misma
pinta que el modal) — esto NO es una pagina generica aparte, es la misma
identidad premium del catalogo.

Cada pagina:
- Trae su propio <title>/meta description/Open Graph ya escritos en el
  HTML (no dependen de JavaScript para ser indexables).
- Dispara el mismo evento ViewContent del Pixel que ya usa el catalogo.
- Muestra los colores hermanos del mismo modelo (mismo Ref_Proveedor) como
  links directos a la pagina de cada uno — igual que Zara/Amazon: cambiar
  de color es navegar a la URL de ese color, no un swap de JS.
- Tiene selector de talla (botones, como el modal) si el modelo tiene mas
  de una talla real.
- "Agregar a selección" escribe en el MISMO localStorage que usa el
  catalogo (orkia_seleccion_whatsapp_v1 / nudo_seleccion_whatsapp_v1), con
  el mismo formato de item — el carrito es compartido entre el catalogo y
  estas paginas, se revisa/envia desde el sheet de siempre
  (/{marca}/?abrirSeleccion=1 lo abre automatico).
- Incluye datos estructurados Product (JSON-LD) y marca "Agotado" +
  deshabilita agregar/tallas cuando el producto o la talla no tiene stock.

El catalogo (orkia/index.html, nudo/index.html) ya navega aca en vez de
abrir un modal — ver goToProductPage() en ambos archivos.

Tambien regenera sitemap.xml en la raiz del repo con las URLs de las
dos paginas de catalogo y cada producto.

No sincroniza sola: hay que volver a correr este script (y hacer
commit/push) cada vez que cambien precios, stock, tallas o fotos
publicadas.

Uso: python3 scripts/generate_product_pages.py
"""
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

AS_URL = "https://script.google.com/macros/s/AKfycby4BrDKh66iyznFEFv7VH6H2adZaE-t-J_0kOHUQW_TY80-K5kb4Sw1eHv7eIaRBsQ/exec"
WA_NUMBER = "50248304736"
PIXEL_ID = "1778753106585555"
REPO_ROOT = Path(__file__).resolve().parent.parent

COLOR_HEX = {
    "negro": "#111111", "blanco": "#FFFFFF", "hueso": "#F4F0E8", "beige": "#D8C7B4",
    "cafe": "#7A5236", "marron": "#7A5236", "camel": "#B98A5B", "rojo": "#A83A32",
    "vino": "#6D2430", "azul": "#2F4F73", "verde": "#556B4A", "gris": "#A3A09B",
    "rosa": "#D8A6A6", "rosado": "#D8A6A6", "morado": "#705A7A", "lila": "#B7A4C6",
    "amarillo": "#D6B45A", "naranja": "#C4714A", "terracota": "#C4714A",
}

BRANDS = {
    "orkia": {
        "label": "ORKIA",
        "tagline": "Moda femenina colombiana",
        "font_display": "Cormorant Garamond",
        "font_google": "Cormorant+Garamond:wght@400;500",
        "bg": "#F5F0EA", "surface": "#FFFFFF", "dark": "#111111", "carbon": "#1A1A1A",
        "text": "#1E1E1E", "mid": "#77736F", "border": "#E8E4DF", "terracota": "#C4714A",
        "wa_msg_generic": "Hola%20Orkia%20%F0%9F%91%8B%20Quisiera%20informaci%C3%B3n%20sobre%20sus%20prendas.",
        "low_stock_threshold": 2,
        "trust_items": [
            ("M8 3 5 5v4l-2 3 3 3v4l4 2 3-2 4 1 3-4-2-3 1-4-4-2-2-4z", "Diseño colombiano",
             "Prendas seleccionadas por su estilo, color y caída."),
            ("M4 21h16M7 21V7a5 5 0 0 1 10 0v14M9 8h6M9 12h6M9 16h6", "Confección con propósito",
             "Trabajamos con mujeres cabeza de hogar en Colombia para confeccionar nuestras prendas."),
            ("M12 21a9 9 0 0 0 7.7-13.7A9 9 0 0 0 5.2 18.6L4 22l3.5-1.1A9 9 0 0 0 12 21Z|"
             "M9.2 8.8c.2-.5.4-.5.7-.5h.5c.2 0 .4.1.5.4l.8 1.8c.1.3 0 .5-.1.7l-.4.5c.6 1 1.4 1.8 2.5 2.4l.6-.5c.2-.1.4-.2.7-.1l1.7.8",
             "Atención personalizada", "Te ayudamos por WhatsApp si tienes dudas o necesitas asesoría."),
        ],
    },
    "nudo": {
        "label": "NUDO",
        "tagline": "Ropa interior colombiana",
        "font_display": "Playfair Display",
        "font_google": "Playfair+Display:wght@500;600",
        "bg": "#FAF8F5", "surface": "#FFFFFF", "dark": "#111111", "carbon": "#1A1A1A",
        "text": "#1E1E1E", "mid": "#77736F", "border": "#E8E4DF", "terracota": "#4A1F2C",
        "wa_msg_generic": "Hola%20Nudo%20%F0%9F%91%8B%20Quisiera%20informaci%C3%B3n%20sobre%20su%20ropa%20interior.",
        "low_stock_threshold": 0,
        "trust_items": [
            ("M8 3 5 5v4l-2 3 3 3v4l4 2 3-2 4 1 3-4-2-3 1-4-4-2-2-4z", "Buen fit",
             "Ropa interior seleccionada por comodidad, materiales y durabilidad."),
            ("M4 21h16M7 21V7a5 5 0 0 1 10 0v14M9 8h6M9 12h6M9 16h6", "Fit cómodo",
             "Telas, elásticos y acabados pensados para acompañar tu cuerpo."),
            ("M12 21a9 9 0 0 0 7.7-13.7A9 9 0 0 0 5.2 18.6L4 22l3.5-1.1A9 9 0 0 0 12 21Z|"
             "M9.2 8.8c.2-.5.4-.5.7-.5h.5c.2 0 .4.1.5.4l.8 1.8c.1.3 0 .5-.1.7l-.4.5c.6 1 1.4 1.8 2.5 2.4l.6-.5c.2-.1.4-.2.7-.1l1.7.8",
             "Compra discreta", "Te atendemos por WhatsApp con color, talla, fit y disponibilidad."),
        ],
    },
}


def fetch_catalogo(marca):
    url = f"{AS_URL}?accion=get_catalogo&marca={marca}&_ts={time.time_ns()}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (generador-paginas-producto)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(f"get_catalogo respondio error para {marca}: {data}")
    return data["productos"]


def normalize(v):
    return str(v if v is not None else "").strip()


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def color_hex(color):
    raw = normalize(color)
    for part in re.split(r"[/,+]", raw):
        key = strip_accents(part).strip().lower()
        if key in COLOR_HEX:
            return COLOR_HEX[key]
    return "#D8D2CC"


def group_by_ref_proveedor(productos):
    groups = {}
    order = []
    for p in productos:
        key = normalize(p.get("ref_proveedor")) or f"producto-{p['id_producto']}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(p)
    return [groups[k] for k in order]


TOP_TYPES = {"blusa", "top", "body"}
BOTTOM_TYPES = {"falda", "pantalon"}
RELATED_COUNT = 4


def pick_related(marca, all_groups, current_group, count=RELATED_COUNT):
    current_ref = normalize(current_group[0].get("ref_proveedor"))
    current_tipo = strip_accents(normalize(current_group[0].get("tipo_prenda"))).lower()

    pool_primary = []
    pool_general = []
    for g in all_groups:
        if normalize(g[0].get("ref_proveedor")) == current_ref:
            continue
        available = [v for v in g if not v.get("agotado")]
        if not available:
            continue
        v = available[0]
        tipo = strip_accents(normalize(v.get("tipo_prenda"))).lower()
        if marca == "orkia" and current_tipo in TOP_TYPES and tipo in BOTTOM_TYPES:
            pool_primary.append(v)
        elif marca == "orkia" and current_tipo in BOTTOM_TYPES and tipo in TOP_TYPES:
            pool_primary.append(v)
        else:
            pool_general.append(v)

    chosen = pool_primary[:count]
    if len(chosen) < count:
        chosen += pool_general[: count - len(chosen)]
    return chosen[:count]


def esc(s):
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def money(v):
    try:
        return f"Q{float(v):.0f}"
    except (TypeError, ValueError):
        return "Q0"



def images_for(p):
    return [u for u in [p.get("url_imagen"), p.get("url_imagen_2"), p.get("url_imagen_3")] if u]


def page_html(marca, brand, group, p, canonical_url, all_groups):
    pid = p["id_producto"]
    title_txt = f"{p.get('tipo_prenda') or 'Prenda'} {p.get('color') or ''}".strip()
    page_title = f"{esc(title_txt)} — {esc(p['descripcion'])} | {brand['label']}"
    description = f"{p['descripcion']} en color {p.get('color') or ''}. {money(p.get('precio_gtq'))}. Envio gratis desde Q300 en Guatemala. Pide por WhatsApp."
    imgs = images_for(p)
    image = imgs[0] if imgs else ""
    tallas_disponibles = [t for t in (p.get("tallas") or [])] or ["Unica"]
    tallas_agotadas = {normalize(t).lower() for t in (p.get("tallas_agotadas") or [])}
    try:
        stock_total = float(p.get("stock_total"))
    except (TypeError, ValueError):
        stock_total = None
    is_agotado = bool(p.get("agotado")) or stock_total == 0
    low_stock_threshold = brand.get("low_stock_threshold") or 0
    is_low_stock = (
        not is_agotado
        and stock_total is not None
        and 0 < stock_total <= low_stock_threshold
    )

    manga_raw = normalize(p.get("material")).lower()
    manga_labels = {
        "larga": "Manga larga", "manga larga": "Manga larga",
        "corta": "Manga corta", "3/4": "Manga 3/4",
        "sin mangas": "Sin mangas", "sin manga": "Sin mangas",
        "sisa": "Tipo sisa", "strapless": "Strapless", "un hombro": "Un hombro",
    }
    manga_txt = manga_labels.get(manga_raw, "")
    patron_raw = normalize(p.get("patron")).lower()
    patron_skip = {"liso", "lisa", "n/a", "no especificado", ""}
    patron_txt = normalize(p.get("patron")) if patron_raw not in patron_skip else ""
    detail_bits = [b for b in [manga_txt, patron_txt] if b]
    detail_line = " · ".join(detail_bits)

    default_talla = next(
        (t for t in tallas_disponibles if normalize(t).lower() not in tallas_agotadas),
        tallas_disponibles[0],
    )
    catalog_url = f"https://casajrp.com/{marca}/"

    wa_contact_msg = urllib.parse.quote(
        f"Hola {brand['label']} 👋 Tengo una pregunta sobre: {p['descripcion']} (#{pid})"
    )
    wa_contact_link = f"https://wa.me/{WA_NUMBER}?text={wa_contact_msg}"
    wa_advice_msg = urllib.parse.quote(
        f"Hola {brand['label']} 👋 Quiero asesoría para saber cómo me quedaría: {p['descripcion']} (#{pid})"
    )
    wa_advice_link = f"https://wa.me/{WA_NUMBER}?text={wa_advice_msg}"

    color_swatches = "".join(
        f"""<a class="color-btn {'active' if v['id_producto']==pid else ''} {'disabled' if v.get('agotado') else ''}"
             href="/{marca}/producto/{v['id_producto']}/">
             <span class="color-dot" style="--dot:{color_hex(v.get('color'))}"></span>{esc(v.get('color') or 'Color')}
             <span class="color-code">#{v['id_producto']}</span></a>"""
        for v in group
    )

    if len(tallas_disponibles) <= 1:
        talla_block = ""
    else:
        size_buttons = "".join(
            f'<button type="button" class="size-btn {"active" if t==default_talla else ""} {"disabled" if normalize(t).lower() in tallas_agotadas else ""}" '
            f'data-talla="{esc(t)}" {"disabled" if normalize(t).lower() in tallas_agotadas else ""}>{esc(t)}</button>'
            for t in tallas_disponibles
        )
        talla_block = f'<div class="size-title">Selecciona tu talla</div><div class="sizes" id="sizes">{size_buttons}</div>'

    trust_bar = "".join(
        f'''<div class="trust-item"><svg class="icon" viewBox="0 0 24 24">{"".join(f'<path d="{d}"/>' for d in paths.split("|"))}</svg>
          <div><h3>{esc(title)}</h3><p>{esc(text)}</p></div></div>'''
        for paths, title, text in brand.get("trust_items", [])
    )

    related = pick_related(marca, all_groups, group)
    related_cards = "".join(
        f'''<a class="related-card" href="/{marca}/producto/{v['id_producto']}/">
          <div class="related-imgbox"><img src="{esc((images_for(v) or [''])[0])}" alt="{esc(v.get('descripcion') or '')}" loading="lazy"></div>
          <div class="related-name">{esc(v.get('descripcion') or '')}</div>
          <div class="related-price">{money(v.get('precio_gtq'))}</div>
        </a>'''
        for v in related
    )
    related_section = (
        f'''<section class="related" aria-label="También te puede gustar">
          <h2 class="serif">También te puede gustar</h2>
          <div class="related-grid">{related_cards}</div>
        </section>'''
        if related_cards else ""
    )

    gallery = "".join(
        f'<button type="button" class="thumb-btn {"active" if i==0 else ""}" data-idx="{i}"><img class="thumb" src="{esc(u)}" alt="{esc(p["descripcion"])}" loading="lazy"></button>'
        for i, u in enumerate(imgs)
    )
    images_json = json.dumps(imgs)

    ld_json = json.dumps({
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": p["descripcion"],
        "image": imgs,
        "description": description,
        "sku": str(pid),
        "brand": {"@type": "Brand", "name": brand["label"]},
        "offers": {
            "@type": "Offer",
            "url": canonical_url,
            "priceCurrency": "GTQ",
            "price": str(p.get("precio_gtq") or 0),
            "availability": (
                "https://schema.org/OutOfStock" if is_agotado else "https://schema.org/InStock"
            ),
        },
    }, ensure_ascii=False).replace("</", "<\\/")

    bag_key = f"{marca}_seleccion_whatsapp_v1"
    item_json = json.dumps({
        "id_producto": pid,
        "sku_key": normalize(group[0].get("ref_proveedor")) or f"producto-{pid}",
        "ref_proveedor": p.get("ref_proveedor") or "",
        "descripcion": p.get("descripcion") or "",
        "tipo_prenda": p.get("tipo_prenda") or "",
        "color": p.get("color") or "",
        "precio_gtq": p.get("precio_gtq") or 0,
        "codigo": str(pid),
        "imagen": image,
    })

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="{brand['dark']}" />
  <title>{page_title}</title>
  <meta name="description" content="{esc(description)}" />
  <link rel="canonical" href="{canonical_url}" />
  <meta property="og:type" content="product" />
  <meta property="og:site_name" content="{brand['label']}" />
  <meta property="og:title" content="{page_title}" />
  <meta property="og:description" content="{esc(description)}" />
  <meta property="og:image" content="{esc(image)}" />
  <meta property="og:url" content="{canonical_url}" />
  <meta property="og:locale" content="es_GT" />
  <meta property="product:price:amount" content="{p.get('precio_gtq') or ''}" />
  <meta property="product:price:currency" content="GTQ" />
  <script type="application/ld+json">{ld_json}</script>
  <link rel="preconnect" href="https://img.casajrp.com" crossorigin>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family={brand['font_google']}&display=swap" rel="stylesheet">
  <!-- Facebook Pixel Code -->
  <script>
  !function(f,b,e,v,n,t,s)
  {{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
  if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
  n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t,s)}}(window,document,'script',
  'https://connect.facebook.net/en_US/fbevents.js');
  fbq('init', '{PIXEL_ID}');
  fbq('track', 'PageView');
  fbq('track', 'ViewContent', {{
    content_ids: ['{pid}'],
    content_type: 'product',
    content_name: {json.dumps(p['descripcion'])},
    currency: 'GTQ',
    value: {p.get('precio_gtq') or 0}
  }});
  </script>
  <noscript>
  <img height="1" width="1" style="display:none"
  src="https://www.facebook.com/tr?id={PIXEL_ID}&ev=PageView&noscript=1"/>
  </noscript>
  <!-- End Facebook Pixel Code -->
  <style>
    :root{{
      --bg:{brand['bg']};--surface:{brand['surface']};--dark:{brand['dark']};--carbon:{brand['carbon']};
      --text:{brand['text']};--mid:{brand['mid']};--border:{brand['border']};--terracota:{brand['terracota']};
    }}
    *{{box-sizing:border-box}}
    html{{scroll-behavior:smooth}}
    html,body{{height:100%}}
    body{{margin:0;min-height:100vh;display:flex;flex-direction:column;background:var(--bg);color:var(--text);font-family:'DM Sans',system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}}
    a{{color:inherit;text-decoration:none}}
    img{{display:block;max-width:100%}}
    button{{font:inherit;cursor:pointer}}
    .serif{{font-family:'{brand['font_display']}',Georgia,serif;font-weight:400}}
    .icon{{width:18px;height:18px;stroke:currentColor;stroke-width:1.55;fill:none;stroke-linecap:round;stroke-linejoin:round;flex:0 0 auto}}
    .site-header{{height:72px;background:linear-gradient(180deg,#161616,#111);color:#fff;display:flex;align-items:center;position:sticky;top:0;z-index:80;border-bottom:1px solid rgba(255,255,255,.07)}}
    .header-inner{{width:100%;margin:0 auto;padding:0 24px;display:flex;align-items:center;justify-content:space-between;gap:16px}}
    .brand{{line-height:1;display:flex;align-items:center;gap:10px}}
    .brand .back{{opacity:.75;font-size:13px}}
    .brand-logo{{font-family:'{brand['font_display']}',Georgia,serif;font-size:28px;letter-spacing:.09em;font-weight:400}}
    .brand-dot{{display:inline-block;width:6px;height:6px;background:var(--terracota);border-radius:50%;margin-left:2px}}
    .header-actions{{display:flex;align-items:center;gap:18px}}
    .icon-btn{{border:0;background:transparent;color:inherit;padding:6px;line-height:0;position:relative;display:inline-flex}}
    .bag-count{{position:absolute;top:-2px;right:-2px;background:var(--terracota);color:#fff;font-size:9px;font-weight:700;width:15px;height:15px;border-radius:50%;display:flex;align-items:center;justify-content:center}}
    .top-shipping{{height:52px;background:#EFE8E0;color:var(--text);display:flex;align-items:center;justify-content:center;gap:10px;font-size:16px;font-weight:500}}
    .top-shipping .q{{color:var(--terracota);font-weight:700}}
    main{{max-width:1440px;margin:0 auto;padding:0;width:100%;flex:1 0 auto}}
    .layout{{display:flex;justify-content:center;align-items:stretch;gap:40px;max-width:1120px;margin:0 auto;flex-wrap:nowrap}}
    .gallery-col{{display:flex;flex-direction:column;min-width:0}}
    .gallery{{position:relative;background:var(--border);aspect-ratio:4/5;max-width:100%;flex:1 1 auto;min-height:600px}}
    .photo{{width:100%;height:100%;object-fit:cover;background:var(--border);display:block}}
    .gallery-nav{{position:absolute;top:50%;transform:translateY(-50%);width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.85);border:0;display:flex;align-items:center;justify-content:center;font-size:16px;color:#111}}
    .gallery-nav.prev{{left:10px}}
    .gallery-nav.next{{right:10px}}
    .gallery-nav.hidden{{display:none}}
    .zoom-hint{{position:absolute;bottom:10px;right:10px;background:rgba(0,0,0,.55);color:#fff;font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:6px 10px;border-radius:999px}}
    .thumbs{{display:flex;gap:8px;margin-top:8px;padding:0}}
    .thumb-btn{{border:1px solid transparent;background:none;padding:0;line-height:0}}
    .thumb-btn.active{{border-color:var(--terracota)}}
    .thumb{{width:72px;height:90px;object-fit:cover;background:var(--border);display:block}}
    .lightbox{{position:fixed;inset:0;background:rgba(17,17,17,.94);z-index:200;display:none;align-items:center;justify-content:center}}
    .lightbox.open{{display:flex}}
    .lightbox img{{max-width:92vw;max-height:82vh;object-fit:contain;transition:transform .2s ease;cursor:zoom-in}}
    .lightbox img.zoomed{{transform:scale(1.9);cursor:zoom-out}}
    .lightbox-close{{position:absolute;top:18px;right:18px;width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.14);color:#fff;border:0;font-size:18px}}
    .lightbox-zoom-hint{{position:absolute;left:50%;bottom:24px;transform:translateX(-50%);font-size:12px;color:rgba(255,255,255,.72);text-align:center}}
    .lightbox .gallery-nav{{background:rgba(255,255,255,.16);color:#fff}}
    .info-pad{{padding:48px 0 30px;flex:0 1 480px;max-width:480px}}
    .eyebrow{{font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--terracota);font-weight:600;margin:0 0 10px}}
    .badge-agotado{{display:inline-block;margin-left:8px;padding:2px 9px;border-radius:999px;background:#EFE3E0;color:#9A3B2E;font-size:9px;letter-spacing:.1em}}
    h1{{font-family:'{brand['font_display']}',Georgia,serif;font-size:38px;line-height:1.05;letter-spacing:-.02em;margin:6px 0 8px;color:var(--dark);max-width:520px}}
    .price{{font-size:24px;font-weight:600;margin:0 0 20px;color:var(--dark)}}
    .color-title,.size-title{{font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--text);margin-bottom:10px}}
    .color-options{{display:flex;flex-wrap:wrap;gap:9px;margin-bottom:24px}}
    .color-btn{{min-height:38px;border:1px solid #D9D2CC;background:#fff;color:#111;border-radius:999px;padding:0 13px;display:inline-flex;align-items:center;gap:8px;font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase}}
    .color-btn.active{{background:#111;color:#fff;border-color:#111}}
    .color-btn .color-code{{font-size:9px;opacity:.72;margin-left:2px}}
    .color-btn.disabled{{opacity:.45;text-decoration:line-through}}
    .color-dot{{width:13px;height:13px;border-radius:50%;border:1px solid rgba(0,0,0,.18);background:var(--dot,#D8D2CC)}}
    .sizes{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px}}
    .size-btn{{width:44px;height:44px;border:1px solid #D9D2CC;background:#fff;color:#111;font-size:12px}}
    .size-btn.active{{background:#111;color:#fff;border-color:#111}}
    .size-btn.disabled{{opacity:.4;text-decoration:line-through;cursor:not-allowed}}
    .detail-line{{font-size:11px;color:var(--terracota);letter-spacing:.1em;text-transform:uppercase;font-weight:600;margin:-4px 0 14px}}
    .low-stock{{font-size:12px;font-weight:600;color:#B3492E;margin:-6px 0 16px;display:flex;align-items:center;gap:6px}}
    .low-stock .dot{{width:7px;height:7px;border-radius:50%;background:#B3492E}}
    .desc{{color:var(--mid);line-height:1.6;margin:0 0 28px;font-size:14px;max-width:440px}}
    .actions{{display:flex;flex-direction:column;gap:12px;max-width:340px}}
    .wa-advice{{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text);margin-top:4px}}
    .wa-advice svg{{width:16px;height:16px;color:#25D366;flex:0 0 auto}}
    .wa-advice a{{color:var(--terracota);font-weight:600;text-decoration:underline}}
    .btn{{border:0;height:48px;padding:0 24px;font-size:11px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;display:inline-flex;align-items:center;justify-content:center;gap:8px;transition:.18s ease;width:100%}}
    .btn-primary{{background:var(--dark);color:#fff}}
    .btn-primary:hover{{background:#000}}
    .btn-primary:disabled{{background:#C9C2BB;color:#fff;cursor:not-allowed}}
    .btn-primary:disabled:hover{{background:#C9C2BB}}
    .btn-ghost{{background:transparent;color:var(--dark);border:1px solid #B8B2AC}}
    .btn-ghost:hover{{background:#fff}}
    .confirm{{font-size:12px;color:#2D6A4F;margin:-4px 0 0;display:none}}
    .confirm.show{{display:block}}
    .meta{{font-size:11px;color:var(--mid);letter-spacing:.06em;margin-top:22px}}
    .breadcrumb{{font-size:11px;color:var(--mid);margin:0 0 16px;display:flex;flex-wrap:wrap;gap:6px}}
    .breadcrumb a{{color:var(--mid)}}
    .breadcrumb a:hover{{color:var(--dark)}}
    .breadcrumb .sep{{opacity:.5}}
    .breadcrumb .current{{color:var(--text)}}
    .trust-bar{{display:flex;flex-direction:column;gap:16px;margin-top:32px;padding-top:24px;border-top:1px solid var(--border);max-width:440px}}
    .trust-item{{display:grid;grid-template-columns:24px 1fr;gap:12px;align-items:start}}
    .trust-item .icon{{width:21px;height:21px;color:var(--terracota)}}
    .trust-item h3{{margin:0 0 3px;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--dark)}}
    .trust-item p{{margin:0;color:var(--mid);font-size:12.5px;line-height:1.5}}
    .wa-float{{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;background:#25D366;display:flex;align-items:center;justify-content:center;box-shadow:0 6px 20px rgba(0,0,0,.28);z-index:60}}
    .wa-float svg{{width:28px;height:28px;color:#fff}}
    .related{{max-width:1120px;margin:56px auto 0;padding:0 34px 44px}}
    .related h2{{font-size:26px;font-weight:400;margin:0 0 20px;color:var(--dark)}}
    .related-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}}
    .related-card{{display:block}}
    .related-imgbox{{aspect-ratio:4/5;background:var(--border);overflow:hidden;margin-bottom:10px}}
    .related-imgbox img{{width:100%;height:100%;object-fit:cover;display:block}}
    .related-name{{font-size:13px;color:var(--dark);margin-bottom:4px;line-height:1.35}}
    .related-price{{font-size:13px;font-weight:600;color:var(--dark)}}
    .footer{{background:var(--carbon);color:#fff;margin-top:40px;padding:22px 28px;text-align:center}}
    .footer .brand-logo{{font-size:20px}}
    .footer p{{margin:6px 0 0;color:rgba(255,255,255,.62);font-size:10px;letter-spacing:.14em;text-transform:uppercase}}
    @media (max-width:800px){{
      .layout{{flex-direction:column;align-items:stretch;gap:0;max-width:none;margin:0}}
      main{{padding:0 0 50px}}
      .gallery{{height:58vh;min-height:0;max-height:480px;aspect-ratio:auto;width:100%;flex:0 0 auto}}
      .thumbs{{padding:8px 18px 0}}
      .info-pad{{padding:20px 18px 0;flex:0 0 auto;max-width:none}}
      .eyebrow{{font-size:9px}}
      h1{{font-size:31px;line-height:1.08;margin:5px 0 8px}}
      .price{{font-size:22px;margin:0 0 18px}}
      .site-header{{height:58px}}
      .header-inner{{padding:0 16px}}
      .brand-logo{{font-size:22px}}
      .wa-float{{right:14px;bottom:calc(14px + env(safe-area-inset-bottom));width:50px;height:50px}}
      .wa-float svg{{width:25px;height:25px}}
      .related{{padding:0 18px 34px;margin-top:36px}}
      .related h2{{font-size:22px}}
      .related-grid{{grid-template-columns:repeat(2,1fr);gap:14px}}
    }}
  </style>
</head>
<body>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="{catalog_url}" aria-label="Volver al catálogo">
        <span class="icon back">&larr;</span>
        <div class="brand-logo">{brand['label']}<span class="brand-dot"></span></div>
      </a>
      <div class="header-actions">
        <a class="icon-btn" href="/{marca}/?abrirSeleccion=1" aria-label="Selección">
          <svg class="icon" viewBox="0 0 24 24"><path d="M6 8h12l-1 13H7L6 8Z"/><path d="M9 8a3 3 0 0 1 6 0"/></svg>
          <span class="bag-count" id="bagCount">0</span>
        </a>
        <a class="icon-btn" href="https://wa.me/{WA_NUMBER}?text={brand['wa_msg_generic']}" target="_blank" rel="noopener" aria-label="WhatsApp">
          <svg class="icon" viewBox="0 0 24 24"><path d="M12 21a9 9 0 0 0 7.7-13.7A9 9 0 0 0 5.2 18.6L4 22l3.5-1.1A9 9 0 0 0 12 21Z"/><path d="M9.2 8.8c.2-.5.4-.5.7-.5h.5c.2 0 .4.1.5.4l.8 1.8c.1.3 0 .5-.1.7l-.4.5c.6 1 1.4 1.8 2.5 2.4l.6-.5c.2-.1.4-.2.7-.1l1.7.8c.3.1.4.3.4.6v.4c0 .4-.2.7-.6.9-.6.3-1.9.4-3.8-.6-2.6-1.3-4.3-4.1-4.4-5.5 0-.5.2-.9.4-1.3Z"/></svg>
        </a>
      </div>
    </div>
  </header>
  <div class="top-shipping"><span>Envío gratis desde <span class="q">Q300</span></span></div>
  <main>
    <div class="layout">
      <div class="gallery-col">
        <div class="gallery">
          <img id="mainPhoto" class="photo" src="{esc(image)}" alt="{esc(p['descripcion'])} - {esc(p.get('color') or '')}" loading="eager" fetchpriority="high">
          <button type="button" class="gallery-nav prev {'hidden' if len(imgs)<=1 else ''}" id="prevBtn" aria-label="Foto anterior">&lsaquo;</button>
          <button type="button" class="gallery-nav next {'hidden' if len(imgs)<=1 else ''}" id="nextBtn" aria-label="Foto siguiente">&rsaquo;</button>
          {f'<div class="zoom-hint">Toca para ampliar</div>' if imgs else ''}
        </div>
        {f'<div class="thumbs">{gallery}</div>' if len(imgs) > 1 else ''}
      </div>
      <div class="info-pad">
        <nav class="breadcrumb" aria-label="Ruta">
          <a href="{catalog_url}">Inicio</a><span class="sep">/</span><span class="current">{esc(p.get('tipo_prenda') or brand['label'])}</span>
        </nav>
        <p class="eyebrow">{esc(p.get('tipo_prenda') or brand['label'])}{' <span class="badge-agotado">Agotado</span>' if is_agotado else ''}</p>
        <h1 class="serif">{esc(p['descripcion'])}</h1>
        <p class="price">{money(p.get('precio_gtq'))}</p>
        {f'<p class="low-stock"><span class="dot"></span>¡Solo quedan {int(stock_total)} unidades!</p>' if is_low_stock else ''}
        {f'<p class="detail-line">{esc(detail_line)}</p>' if detail_line else ''}
        <div class="color-title">Selecciona color</div>
        <div class="color-options">{color_swatches}</div>
        {talla_block}
        <p class="desc">{esc(p['descripcion'])} Envío gratis desde Q300 en Guatemala.</p>
        <div class="actions">
          {f'<button class="btn btn-primary" id="addBtn" type="button" disabled>Agotado</button>' if is_agotado else '<button class="btn btn-primary" id="addBtn" type="button">Agregar a selección</button>'}
          <a class="btn btn-ghost" href="{catalog_url}">Ver catálogo completo</a>
        </div>
        <p class="confirm" id="confirmMsg">Agregado a tu selección. Ya está en tu carrito, revísalo cuando quieras.</p>
        <p class="wa-advice">
          <svg class="icon" viewBox="0 0 24 24"><path d="M12 21a9 9 0 0 0 7.7-13.7A9 9 0 0 0 5.2 18.6L4 22l3.5-1.1A9 9 0 0 0 12 21Z"/><path d="M9.2 8.8c.2-.5.4-.5.7-.5h.5c.2 0 .4.1.5.4l.8 1.8c.1.3 0 .5-.1.7l-.4.5c.6 1 1.4 1.8 2.5 2.4l.6-.5c.2-.1.4-.2.7-.1l1.7.8c.3.1.4.3.4.6v.4c0 .4-.2.7-.6.9-.6.3-1.9.4-3.8-.6-2.6-1.3-4.3-4.1-4.4-5.5 0-.5.2-.9.4-1.3Z"/></svg>
          <span>¿Quieres asesoría para saber cómo te quedaría? <a href="{wa_advice_link}" target="_blank" rel="noopener">Escríbenos por WhatsApp</a></span>
        </p>
        <p class="meta">Código #{pid}</p>
        <div class="trust-bar">{trust_bar}</div>
      </div>
    </div>
    {related_section}
  </main>
  <footer class="footer">
    <div class="brand-logo serif">{brand['label']}<span class="brand-dot"></span></div>
    <p>Guatemala &middot; Manufactura colombiana &middot; &copy; 2026</p>
  </footer>
  <a class="wa-float" href="{wa_contact_link}" target="_blank" rel="noopener" aria-label="Escríbenos por WhatsApp">
    <svg class="icon" viewBox="0 0 24 24"><path d="M12 21a9 9 0 0 0 7.7-13.7A9 9 0 0 0 5.2 18.6L4 22l3.5-1.1A9 9 0 0 0 12 21Z"/><path d="M9.2 8.8c.2-.5.4-.5.7-.5h.5c.2 0 .4.1.5.4l.8 1.8c.1.3 0 .5-.1.7l-.4.5c.6 1 1.4 1.8 2.5 2.4l.6-.5c.2-.1.4-.2.7-.1l1.7.8c.3.1.4.3.4.6v.4c0 .4-.2.7-.6.9-.6.3-1.9.4-3.8-.6-2.6-1.3-4.3-4.1-4.4-5.5 0-.5.2-.9.4-1.3Z"/></svg>
  </a>
  <div class="lightbox" id="lightbox">
    <button type="button" class="lightbox-close" id="lightboxClose" aria-label="Cerrar">&times;</button>
    <button type="button" class="gallery-nav prev {'hidden' if len(imgs)<=1 else ''}" id="lbPrev" aria-label="Foto anterior">&lsaquo;</button>
    <img id="lightboxImg" src="" alt="{esc(p['descripcion'])}">
    <button type="button" class="gallery-nav next {'hidden' if len(imgs)<=1 else ''}" id="lbNext" aria-label="Foto siguiente">&rsaquo;</button>
    <div class="lightbox-zoom-hint">Doble tap o pellizca para ampliar</div>
  </div>
  <script>
    const BAG_KEY = {json.dumps(bag_key)};
    const ITEM_BASE = {item_json};
    const IMAGES = {images_json};

    function readBag(){{ try{{ return JSON.parse(localStorage.getItem(BAG_KEY) || '[]') || []; }}catch(e){{ return []; }} }}
    function writeBag(items){{ try{{ localStorage.setItem(BAG_KEY, JSON.stringify(items)); }}catch(e){{}} updateBagCount(items); }}
    function bagKeyFor(item){{ return `${{item.id_producto || ''}}::${{item.talla || ''}}`; }}
    function updateBagCount(items){{
      const total = items.reduce((s,i)=>s+(Number(i.qty)||1),0);
      document.getElementById('bagCount').textContent = total;
    }}
    function isUnica(t){{ return /unica|confirmar/.test(String(t||'').toLowerCase()); }}
    let selectedTalla = {json.dumps(default_talla)};
    document.querySelectorAll('.size-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.size-btn').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        selectedTalla = btn.dataset.talla;
      }});
    }});

    document.getElementById('addBtn').addEventListener('click', () => {{
      const items = readBag();
      const item = Object.assign({{}}, ITEM_BASE, {{ talla: isUnica(selectedTalla) ? 'Por confirmar' : selectedTalla, ts: Date.now() }});
      const key = bagKeyFor(item);
      const existing = items.find(x => bagKeyFor(x) === key);
      if(existing){{ existing.qty = (existing.qty || 1) + 1; }}
      else {{ item.qty = 1; items.push(item); }}
      writeBag(items);
      document.getElementById('confirmMsg').classList.add('show');
    }});

    updateBagCount(readBag());

    // Galeria: miniaturas + flechas cambian la foto principal sin recargar.
    let currentIdx = 0;
    function showImage(idx){{
      if(!IMAGES.length) return;
      currentIdx = (idx + IMAGES.length) % IMAGES.length;
      document.getElementById('mainPhoto').src = IMAGES[currentIdx];
      document.querySelectorAll('.thumb-btn').forEach((btn,i)=>btn.classList.toggle('active', i===currentIdx));
    }}
    document.getElementById('prevBtn')?.addEventListener('click', ()=>showImage(currentIdx-1));
    document.getElementById('nextBtn')?.addEventListener('click', ()=>showImage(currentIdx+1));
    document.querySelectorAll('.thumb-btn').forEach(btn=>{{
      btn.addEventListener('click', ()=>showImage(Number(btn.dataset.idx)));
    }});

    // Lightbox: tocar la foto principal la abre a pantalla completa; tocar la
    // foto ampliada alterna zoom 1x/1.9x; las flechas tambien funcionan ahi.
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightboxImg');
    function openLightbox(){{
      if(!IMAGES.length) return;
      lightboxImg.src = IMAGES[currentIdx];
      resetZoom();
      lightbox.classList.add('open');
    }}
    function closeLightbox(){{ lightbox.classList.remove('open'); resetZoom(); }}
    document.getElementById('mainPhoto').addEventListener('click', openLightbox);
    document.getElementById('lightboxClose').addEventListener('click', closeLightbox);
    lightbox.addEventListener('click', (e)=>{{ if(e.target === lightbox) closeLightbox(); }});
    document.getElementById('lbPrev')?.addEventListener('click', (e)=>{{ e.stopPropagation(); showImage(currentIdx-1); lightboxImg.src = IMAGES[currentIdx]; resetZoom(); }});
    document.getElementById('lbNext')?.addEventListener('click', (e)=>{{ e.stopPropagation(); showImage(currentIdx+1); lightboxImg.src = IMAGES[currentIdx]; resetZoom(); }});

    // Zoom real: doble-tap/doble-clic o pellizco con dos dedos, igual que el
    // lightbox original (antes solo tenia un clic que alternaba una escala fija).
    let zs = {{scale:1, x:0, y:0, startDist:0, startScale:1, startX:0, startY:0, panX:0, panY:0, panning:false, lastTap:0}};
    function applyZoomTransform(){{
      lightboxImg.style.transform = `translate(${{zs.x}}px, ${{zs.y}}px) scale(${{zs.scale}})`;
      lightboxImg.classList.toggle('zoomed', zs.scale > 1);
    }}
    function resetZoom(){{ zs.scale=1; zs.x=0; zs.y=0; applyZoomTransform(); }}
    function toggleDoubleTapZoom(){{
      if(zs.scale > 1) resetZoom();
      else {{ zs.scale = 2.2; applyZoomTransform(); }}
    }}
    function dist(t1, t2){{ return Math.hypot(t1.clientX-t2.clientX, t1.clientY-t2.clientY); }}
    lightboxImg.addEventListener('click', (e)=>{{
      const now = Date.now();
      if(now - zs.lastTap < 320){{ toggleDoubleTapZoom(); }}
      zs.lastTap = now;
    }});
    lightboxImg.addEventListener('touchstart', (e)=>{{
      if(e.touches.length === 2){{
        zs.startDist = dist(e.touches[0], e.touches[1]);
        zs.startScale = zs.scale;
      }} else if(e.touches.length === 1 && zs.scale > 1){{
        zs.panning = true;
        zs.startX = e.touches[0].clientX - zs.x;
        zs.startY = e.touches[0].clientY - zs.y;
      }}
    }}, {{passive:true}});
    lightboxImg.addEventListener('touchmove', (e)=>{{
      if(e.touches.length === 2 && zs.startDist){{
        const scale = Math.min(4, Math.max(1, zs.startScale * (dist(e.touches[0], e.touches[1]) / zs.startDist)));
        zs.scale = scale;
        applyZoomTransform();
      }} else if(e.touches.length === 1 && zs.panning){{
        zs.x = e.touches[0].clientX - zs.startX;
        zs.y = e.touches[0].clientY - zs.startY;
        applyZoomTransform();
      }}
    }}, {{passive:true}});
    lightboxImg.addEventListener('touchend', (e)=>{{
      zs.startDist = 0; zs.panning = false;
      if(zs.scale <= 1) resetZoom();
      if(e.changedTouches.length === 1 && e.touches.length === 0){{
        const now = Date.now();
        if(now - zs.lastTap < 320) toggleDoubleTapZoom();
        zs.lastTap = now;
      }}
    }});
    document.addEventListener('keydown', (e)=>{{
      if(!lightbox.classList.contains('open')) return;
      if(e.key === 'Escape') closeLightbox();
      if(e.key === 'ArrowLeft') document.getElementById('lbPrev')?.click();
      if(e.key === 'ArrowRight') document.getElementById('lbNext')?.click();
    }});
  </script>
</body>
</html>
"""


def write_sitemap(product_urls):
    urls = ["https://casajrp.com/", "https://casajrp.com/orkia/", "https://casajrp.com/nudo/"] + product_urls
    body = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )
    (REPO_ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")
    print(f"sitemap.xml: {len(urls)} URLs")


def main():
    product_urls = []
    for marca, brand in BRANDS.items():
        productos = fetch_catalogo(marca)
        groups = group_by_ref_proveedor(productos)
        out_dir = REPO_ROOT / marca / "producto"
        count = 0
        for group in groups:
            for p in group:
                pid = p["id_producto"]
                page_dir = out_dir / str(pid)
                page_dir.mkdir(parents=True, exist_ok=True)
                canonical = f"https://casajrp.com/{marca}/producto/{pid}/"
                html = page_html(marca, brand, group, p, canonical, groups)
                (page_dir / "index.html").write_text(html, encoding="utf-8")
                product_urls.append(canonical)
                count += 1
        print(f"{marca}: {count} paginas generadas en {out_dir}")
    write_sitemap(product_urls)


if __name__ == "__main__":
    main()
