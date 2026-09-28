#!/usr/bin/env python3
"""
Genera una pagina estatica por producto (SEO + destino limpio para anuncios),
una por cada SKU publicado de Orkia y Nudo, en {marca}/producto/{id}/index.html.

Cada pagina trae su propio <title>/meta description/Open Graph ya escritos en
el HTML (no dependen de JavaScript para ser indexables), dispara el mismo
evento ViewContent del Pixel que ya usa el catalogo, y ofrece un botón directo
a WhatsApp con el producto identificado, ademas de un link de vuelta al
catalogo completo interactivo para quien quiera armar un pedido de varias
prendas.

No sincroniza sola: hay que volver a correr este script (y hacer commit/push)
cada vez que cambien precios, stock o fotos publicadas.

Uso: python3 scripts/generate_product_pages.py
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

AS_URL = "https://script.google.com/macros/s/AKfycby4BrDKh66iyznFEFv7VH6H2adZaE-t-J_0kOHUQW_TY80-K5kb4Sw1eHv7eIaRBsQ/exec"
WA_NUMBER = "50248304736"
PIXEL_ID = "1778753106585555"
REPO_ROOT = Path(__file__).resolve().parent.parent

BRANDS = {
    "orkia": {
        "label": "ORKIA",
        "tagline": "Moda femenina colombiana",
        "bg": "#F5F0EA",
        "surface": "#FFFFFF",
        "dark": "#111111",
        "text": "#1E1E1E",
        "mid": "#716A63",
        "border": "#E5DDD4",
        "accent": "#C4714A",
    },
    "nudo": {
        "label": "NUDO",
        "tagline": "Ropa interior colombiana",
        "bg": "#FAF8F5",
        "surface": "#FFFFFF",
        "dark": "#111111",
        "text": "#1E1E1E",
        "mid": "#77736F",
        "border": "#E8E4DF",
        "accent": "#4A1F2C",
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


def esc(s):
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def slugify(s):
    s = str(s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")


def money(v):
    try:
        return f"Q{float(v):.0f}"
    except (TypeError, ValueError):
        return "Q0"


def build_whatsapp_message(marca_label, p):
    lines = [
        f"Hola {marca_label} \U0001F44B Me interesa este producto:",
        "",
        f"*{p['descripcion']}*",
        f"\U0001F3A8 Color: {p.get('color') or '-'}",
        f"\U0001F4B0 Precio: {money(p.get('precio_gtq'))}",
        f"\U0001F3F7️ Codigo: #{p['id_producto']}",
        "",
        "Me ayudas a confirmar disponibilidad?",
    ]
    return "\n".join(lines)


def page_html(marca, brand, p, canonical_url):
    pid = p["id_producto"]
    title_txt = f"{p.get('tipo_prenda') or 'Prenda'} {p.get('color') or ''}".strip()
    page_title = f"{esc(title_txt)} — {esc(p['descripcion'])} | {brand['label']}"
    description = f"{p['descripcion']} en color {p.get('color') or ''}. {money(p.get('precio_gtq'))}. Envio gratis desde Q300 en Guatemala. Pide por WhatsApp."
    image = p.get("url_imagen") or ""
    wa_msg = build_whatsapp_message(brand["label"], p)
    wa_msg_encoded = urllib.parse.quote(wa_msg)
    catalog_link = f"https://casajrp.com/{marca}/?sku={pid}"
    wa_link = f"https://wa.me/{WA_NUMBER}?text={wa_msg_encoded}"

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
  <link rel="preconnect" href="https://img.casajrp.com" crossorigin>
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
    *{{box-sizing:border-box}}
    body{{margin:0;background:{brand['bg']};color:{brand['text']};font-family:system-ui,-apple-system,'Segoe UI',sans-serif;-webkit-font-smoothing:antialiased}}
    a{{color:inherit;text-decoration:none}}
    header{{background:{brand['dark']};color:#fff;padding:16px 20px}}
    header a{{font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:14px}}
    main{{max-width:520px;margin:0 auto;padding:0 0 60px}}
    .photo{{width:100%;aspect-ratio:3/4;object-fit:cover;background:{brand['border']}}}
    .info{{padding:24px 20px}}
    .eyebrow{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:{brand['accent']};font-weight:700;margin:0 0 8px}}
    h1{{font-size:26px;line-height:1.15;margin:0 0 10px}}
    .price{{font-size:22px;font-weight:600;margin:0 0 16px}}
    .desc{{color:{brand['mid']};line-height:1.55;margin:0 0 24px;font-size:15px}}
    .btn{{display:flex;align-items:center;justify-content:center;gap:10px;height:52px;border-radius:999px;font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px}}
    .btn-wa{{background:#25D366;color:#fff}}
    .btn-catalog{{background:transparent;border:1px solid {brand['border']};color:{brand['text']}}}
    .meta{{font-size:12px;color:{brand['mid']};margin-top:20px}}
  </style>
</head>
<body>
  <header><a href="/{marca}/">&larr; {brand['label']}</a></header>
  <main>
    <img class="photo" src="{esc(image)}" alt="{esc(p['descripcion'])} - {esc(p.get('color') or '')}" width="1122" height="1402" loading="eager" fetchpriority="high">
    <div class="info">
      <p class="eyebrow">{esc(p.get('tipo_prenda') or brand['label'])}</p>
      <h1>{esc(p['descripcion'])}</h1>
      <p class="price">{money(p.get('precio_gtq'))} &middot; Color {esc(p.get('color') or '-')}</p>
      <p class="desc">{esc(p['descripcion'])} Envio gratis desde Q300 en Guatemala.</p>
      <a class="btn btn-wa" href="{wa_link}" target="_blank" rel="noopener">Pedir por WhatsApp</a>
      <a class="btn btn-catalog" href="{catalog_link}">Ver mas colores y prendas</a>
      <p class="meta">Codigo #{pid}</p>
    </div>
  </main>
</body>
</html>
"""


def main():
    for marca, brand in BRANDS.items():
        productos = fetch_catalogo(marca)
        out_dir = REPO_ROOT / marca / "producto"
        count = 0
        for p in productos:
            pid = p["id_producto"]
            page_dir = out_dir / str(pid)
            page_dir.mkdir(parents=True, exist_ok=True)
            canonical = f"https://casajrp.com/{marca}/producto/{pid}/"
            html = page_html(marca, brand, p, canonical)
            (page_dir / "index.html").write_text(html, encoding="utf-8")
            count += 1
        print(f"{marca}: {count} paginas generadas en {out_dir}")


if __name__ == "__main__":
    main()
