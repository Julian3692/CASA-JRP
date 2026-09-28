#!/usr/bin/env python3
"""
Genera una pagina estatica REAL por producto (SEO + destino limpio para
anuncios + navegacion principal del catalogo), una por cada SKU publicado
de Orkia y Nudo, en {marca}/producto/{id}/index.html.

Cada pagina:
- Trae su propio <title>/meta description/Open Graph ya escritos en el
  HTML (no dependen de JavaScript para ser indexables).
- Dispara el mismo evento ViewContent del Pixel que ya usa el catalogo.
- Muestra los colores hermanos del mismo modelo (mismo Ref_Proveedor) como
  links directos a la pagina de cada uno — igual que Zara/Amazon: cambiar
  de color es navegar a la URL de ese color, no un swap de JS.
- Tiene selector de talla si el modelo tiene mas de una talla real.
- "Agregar a selección" escribe en el MISMO localStorage que usa el
  catalogo (orkia_seleccion_whatsapp_v1 / nudo_seleccion_whatsapp_v1), con
  el mismo formato de item — el carrito es compartido entre el catalogo y
  estas paginas, se revisa/envia desde el sheet de siempre
  (/{marca}/?abrirSeleccion=1 lo abre automatico).
- Tambien ofrece "Pedir ya por WhatsApp" para una consulta directa de un
  solo producto, sin pasar por el carrito.

El catalogo (orkia/index.html, nudo/index.html) ya navega aca en vez de
abrir un modal — ver goToProductPage() en ambos archivos.

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
        "bg": "#F5F0EA", "surface": "#FFFFFF", "dark": "#111111", "text": "#1E1E1E",
        "mid": "#716A63", "border": "#E5DDD4", "accent": "#C4714A",
    },
    "nudo": {
        "label": "NUDO",
        "bg": "#FAF8F5", "surface": "#FFFFFF", "dark": "#111111", "text": "#1E1E1E",
        "mid": "#77736F", "border": "#E8E4DF", "accent": "#4A1F2C",
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


def is_unica(talla):
    t = strip_accents(str(talla or "")).lower()
    return "unica" in t or "confirmar" in t


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


def build_whatsapp_message(marca_label, p, talla):
    talla_line = "" if is_unica(talla) else f"\n\U0001F4CF Talla: {talla}"
    lines = [
        f"Hola {marca_label} \U0001F44B Me interesa este producto:",
        "",
        f"*{p['descripcion']}*",
        f"\U0001F3A8 Color: {p.get('color') or '-'}{talla_line}",
        f"\U0001F4B0 Precio: {money(p.get('precio_gtq'))}",
        f"\U0001F3F7️ Codigo: #{p['id_producto']}",
        "",
        "Me ayudas a confirmar disponibilidad?",
    ]
    return "\n".join(lines)


def images_for(p):
    return [u for u in [p.get("url_imagen"), p.get("url_imagen_2"), p.get("url_imagen_3")] if u]


def page_html(marca, brand, group, p, canonical_url):
    pid = p["id_producto"]
    title_txt = f"{p.get('tipo_prenda') or 'Prenda'} {p.get('color') or ''}".strip()
    page_title = f"{esc(title_txt)} — {esc(p['descripcion'])} | {brand['label']}"
    description = f"{p['descripcion']} en color {p.get('color') or ''}. {money(p.get('precio_gtq'))}. Envio gratis desde Q300 en Guatemala. Pide por WhatsApp."
    imgs = images_for(p)
    image = imgs[0] if imgs else ""
    tallas_disponibles = [t for t in (p.get("tallas") or [])]
    if not tallas_disponibles:
        tallas_disponibles = ["Unica"]
    default_talla = tallas_disponibles[0]
    wa_msg_default = build_whatsapp_message(brand["label"], p, default_talla)
    wa_link_default = f"https://wa.me/{WA_NUMBER}?text={urllib.parse.quote(wa_msg_default)}"
    catalog_url = f"https://casajrp.com/{marca}/"

    color_swatches = "".join(
        f"""<a class="swatch {'active' if v['id_producto']==pid else ''} {'agotado' if v.get('agotado') else ''}"
             href="/{marca}/producto/{v['id_producto']}/"
             title="{esc(v.get('color') or '')}"
             style="--dot:{color_hex(v.get('color'))}"></a>"""
        for v in group
    )

    talla_options = "".join(
        f'<option value="{esc(t)}">{esc("Por confirmar" if is_unica(t) else t)}</option>'
        for t in tallas_disponibles
    )
    talla_block = "" if len(tallas_disponibles) <= 1 else f"""
      <div class="field">
        <label for="tallaSel">Talla</label>
        <select id="tallaSel">{talla_options}</select>
      </div>"""

    gallery = "".join(
        f'<img class="thumb" src="{esc(u)}" alt="{esc(p["descripcion"])}" loading="lazy">'
        for u in imgs[1:]
    )

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
    header{{background:{brand['dark']};color:#fff;padding:16px 20px;display:flex;align-items:center;justify-content:space-between}}
    header a.home{{font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:14px}}
    #bagPill{{font-size:12px;background:rgba(255,255,255,.14);border-radius:999px;padding:6px 12px;display:none}}
    #bagPill.show{{display:inline-flex;align-items:center;gap:6px}}
    main{{max-width:560px;margin:0 auto;padding:0 0 60px}}
    .photo{{width:100%;aspect-ratio:3/4;object-fit:cover;background:{brand['border']}}}
    .thumbs{{display:flex;gap:8px;padding:10px 20px 0}}
    .thumb{{width:64px;height:80px;object-fit:cover;background:{brand['border']}}}
    .info{{padding:24px 20px}}
    .eyebrow{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:{brand['accent']};font-weight:700;margin:0 0 8px}}
    h1{{font-size:26px;line-height:1.15;margin:0 0 10px}}
    .price{{font-size:22px;font-weight:600;margin:0 0 18px}}
    .swatches{{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 20px}}
    .swatch{{width:32px;height:32px;border-radius:50%;background:var(--dot);border:2px solid transparent;box-shadow:0 0 0 1px {brand['border']};display:inline-block}}
    .swatch.active{{border-color:{brand['accent']}}}
    .swatch.agotado{{opacity:.35}}
    .field{{margin:0 0 18px}}
    .field label{{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:{brand['mid']};margin-bottom:6px}}
    select{{width:100%;height:44px;border:1px solid {brand['border']};background:#fff;border-radius:8px;padding:0 12px;font-size:14px;color:{brand['text']}}}
    .desc{{color:{brand['mid']};line-height:1.55;margin:0 0 24px;font-size:15px}}
    .btn{{display:flex;align-items:center;justify-content:center;gap:10px;height:52px;border-radius:999px;font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;border:0;width:100%;cursor:pointer;font-family:inherit}}
    .btn-add{{background:{brand['dark']};color:#fff}}
    .btn-wa{{background:#25D366;color:#fff}}
    .btn-catalog{{background:transparent;border:1px solid {brand['border']} !important;color:{brand['text']};display:block;text-align:center;line-height:36px;height:auto;padding:8px 0}}
    .meta{{font-size:12px;color:{brand['mid']};margin-top:20px}}
    .confirm{{font-size:13px;color:#1f7a3d;margin:-4px 0 12px;display:none}}
    .confirm.show{{display:block}}
  </style>
</head>
<body>
  <header>
    <a class="home" href="{catalog_url}">&larr; {brand['label']}</a>
    <a id="bagPill" href="/{marca}/?abrirSeleccion=1">Selección: <span id="bagCount">0</span></a>
  </header>
  <main>
    <img id="mainPhoto" class="photo" src="{esc(image)}" alt="{esc(p['descripcion'])} - {esc(p.get('color') or '')}" width="1122" height="1402" loading="eager" fetchpriority="high">
    {f'<div class="thumbs">{gallery}</div>' if gallery else ''}
    <div class="info">
      <p class="eyebrow">{esc(p.get('tipo_prenda') or brand['label'])}</p>
      <h1>{esc(p['descripcion'])}</h1>
      <p class="price">{money(p.get('precio_gtq'))} &middot; Color {esc(p.get('color') or '-')}</p>
      <div class="swatches">{color_swatches}</div>
      {talla_block}
      <p class="desc">{esc(p['descripcion'])} Envio gratis desde Q300 en Guatemala.</p>
      <button class="btn btn-add" id="addBtn" type="button">Agregar a selección</button>
      <p class="confirm" id="confirmMsg">Agregado. Podés seguir viendo más prendas o revisar tu selección.</p>
      <a class="btn btn-wa" id="waBtn" href="{wa_link_default}" target="_blank" rel="noopener">Pedir ya por WhatsApp</a>
      <a class="btn btn-catalog" href="{catalog_url}?sku={pid}">Ver catálogo completo</a>
      <p class="meta">Codigo #{pid}</p>
    </div>
  </main>
  <script>
    const BAG_KEY = {json.dumps(bag_key)};
    const WA_NUMBER = {json.dumps(WA_NUMBER)};
    const MARCA_LABEL = {json.dumps(brand['label'])};
    const ITEM_BASE = {item_json};

    function readBag(){{ try{{ return JSON.parse(localStorage.getItem(BAG_KEY) || '[]') || []; }}catch(e){{ return []; }} }}
    function writeBag(items){{ try{{ localStorage.setItem(BAG_KEY, JSON.stringify(items)); }}catch(e){{}} updateBagPill(items); }}
    function bagKeyFor(item){{ return `${{item.id_producto || ''}}::${{item.talla || ''}}`; }}
    function updateBagPill(items){{
      const total = items.reduce((s,i)=>s+(Number(i.qty)||1),0);
      const pill = document.getElementById('bagPill');
      const count = document.getElementById('bagCount');
      count.textContent = total;
      pill.classList.toggle('show', total > 0);
    }}
    function currentTalla(){{
      const sel = document.getElementById('tallaSel');
      return sel ? sel.value : 'Unica';
    }}
    function isUnica(t){{
      return /unica|confirmar/.test(String(t||'').toLowerCase());
    }}
    function waLinkFor(talla){{
      const tallaLine = isUnica(talla) ? '' : `\\n\\uD83D\\uDCCF Talla: ${{talla}}`;
      const msg = `Hola ${{MARCA_LABEL}} \\uD83D\\uDC4B Me interesa este producto:\\n\\n*${{ITEM_BASE.descripcion}}*\\n\\uD83C\\uDFA8 Color: ${{ITEM_BASE.color}}${{tallaLine}}\\n\\uD83D\\uDCB0 Precio: Q${{Math.round(ITEM_BASE.precio_gtq)}}\\n\\uD83C\\uDFF7\\uFE0F Codigo: #${{ITEM_BASE.id_producto}}\\n\\n\\u00bfMe ayudas a confirmar disponibilidad?`;
      return `https://wa.me/${{WA_NUMBER}}?text=${{encodeURIComponent(msg)}}`;
    }}

    const tallaSel = document.getElementById('tallaSel');
    if(tallaSel){{
      tallaSel.addEventListener('change', () => {{
        document.getElementById('waBtn').href = waLinkFor(tallaSel.value);
      }});
    }}

    document.getElementById('addBtn').addEventListener('click', () => {{
      const talla = currentTalla();
      const items = readBag();
      const item = Object.assign({{}}, ITEM_BASE, {{ talla: isUnica(talla) ? 'Por confirmar' : talla, ts: Date.now() }});
      const key = bagKeyFor(item);
      const existing = items.find(x => bagKeyFor(x) === key);
      if(existing){{ existing.qty = (existing.qty || 1) + 1; }}
      else {{ item.qty = 1; items.push(item); }}
      writeBag(items);
      document.getElementById('confirmMsg').classList.add('show');
    }});

    updateBagPill(readBag());
  </script>
</body>
</html>
"""


def main():
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
                html = page_html(marca, brand, group, p, canonical)
                (page_dir / "index.html").write_text(html, encoding="utf-8")
                count += 1
        print(f"{marca}: {count} paginas generadas en {out_dir}")


if __name__ == "__main__":
    main()
