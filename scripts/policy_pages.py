"""Paginas de ayuda de Orkia y Nudo: cambios y devoluciones, envios, preguntas
frecuentes y terminos/privacidad.

Las usa scripts/generate_product_pages.py (se generan junto con las fichas de
producto, con los mismos colores y tipografias de cada marca). El texto vive
aqui; la tabla de costos de envio se lee en vivo de DIM_ZONAS_ENVIO (get_zonas),
asi que siempre coincide con lo que cobra el sistema.

No contiene costos, margenes ni datos internos: solo lo que se le dice a la clienta.
"""
import html as _html
import urllib.parse

# (slug, nombre en el pie de pagina, titulo de la pagina)
POLICY_PAGES = [
    ("cambios-y-devoluciones", "Cambios y devoluciones", "Cambios y devoluciones"),
    ("envios", "Envíos y entregas", "Envíos y entregas"),
    ("preguntas-frecuentes", "Preguntas frecuentes", "Preguntas frecuentes"),
    ("terminos-y-privacidad", "Términos y privacidad", "Términos y privacidad"),
]
POLICY_FECHA = "noviembre de 2026"

# Valores acordados (cambiarlos aqui actualiza las paginas de las dos marcas)
DIAS_CAMBIO = 7
DIAS_SALDO = 60
HORAS_REPORTE = 48
DIAS_REEMBOLSO = 5
DIAS_GARANTIA = 30
UMBRAL_ENVIO_GRATIS = 300


def esc(s):
    return _html.escape(str(s), quote=True)


def policy_links(marca):
    return [(f"/{marca}/{slug}/", nombre) for slug, nombre, _ in POLICY_PAGES]


def footer_links_html(marca):
    links = "".join(f'<a href="{href}">{esc(nombre)}</a>' for href, nombre in policy_links(marca))
    return f'<nav class="footer-links" aria-label="Ayuda">{links}</nav>'


def policy_urls(marca):
    return [f"https://casajrp.com/{marca}/{slug}/" for slug, _, _ in POLICY_PAGES]


def _wa(marca, wa_number, texto):
    return f"https://wa.me/{wa_number}?text={urllib.parse.quote(texto)}"


# ---------------------------------------------------------------- contenido

def _cambios(marca, wa):
    label = "Orkia" if marca == "orkia" else "Nudo"
    contacto = wa(f"Hola {label} 👋 Quiero consultar sobre un cambio o devolución de mi pedido.")
    if marca == "orkia":
        cambios = f"""
<h2>Cambios por talla o color</h2>
<ul>
  <li>Tienes <strong>{DIAS_CAMBIO} días</strong> desde que recibes tu pedido para pedir un cambio por talla o color.</li>
  <li>La prenda debe estar <strong>sin uso, sin lavar, con sus etiquetas y sin olores</strong> (perfume, humo, maquillaje).</li>
  <li>Un cambio por pedido.</li>
  <li>Pídelo por <a href="{contacto}" target="_blank" rel="noopener">WhatsApp</a> con tu número de pedido y una foto de la prenda.</li>
  <li><strong>Costos:</strong> tú envías la prenda de vuelta y nosotros te enviamos la nueva <strong>sin costo</strong>.</li>
  <li>Si no tenemos la talla o el color que quieres, te damos un <strong>saldo a favor</strong> para tu próxima compra, válido por {DIAS_SALDO} días.</li>
</ul>"""
    else:
        cambios = f"""
<h2>Ropa interior: por higiene, sin cambios ni devoluciones</h2>
<p>Por higiene, la ropa interior <strong>no tiene cambios ni devoluciones</strong>, salvo defecto de fábrica.</p>
<ul>
  <li><strong>Si tienes dudas con la talla, pregúntanos antes de comprar.</strong> Escríbenos por <a href="{contacto}" target="_blank" rel="noopener">WhatsApp</a> y te asesoramos.</li>
  <li>Si te equivocaste de talla y la prenda sigue <strong>cerrada, con etiqueta y sello, sin abrir</strong>, escríbenos dentro de los {DIAS_CAMBIO} días de recibirla y lo revisamos caso por caso. El envío de vuelta corre por tu cuenta.</li>
</ul>"""
    if marca == "orkia":
        devol = f"""
<h2>Devolución de dinero</h2>
<ul>
  <li>Solo si tu prenda llega con <strong>defecto de fábrica</strong>, <strong>dañada en el envío</strong> o si <strong>nos equivocamos</strong> de producto.</li>
  <li>Avísanos dentro de las <strong>{HORAS_REPORTE} horas</strong> de recibirla, con fotos.</li>
  <li>Te devolvemos el dinero por <strong>transferencia</strong> en hasta {DIAS_REEMBOLSO} días hábiles desde que recibimos la prenda.</li>
  <li>No hacemos devolución de dinero por "ya no me gustó".</li>
</ul>
<h2>Garantía</h2>
<p>Defectos de fábrica: {DIAS_GARANTIA} días desde la entrega.</p>
<h2>Ofertas finales</h2>
<p>Los productos marcados como <strong>oferta final</strong> (por ejemplo en Black Friday) no tienen cambio ni devolución, salvo defecto de fábrica.</p>"""
    else:
        devol = f"""
<h2>Defecto de fábrica, daño en el envío o error nuestro</h2>
<ul>
  <li>Avísanos dentro de las <strong>{HORAS_REPORTE} horas</strong> de recibir tu pedido.</li>
  <li>Envíanos una foto <strong>solo del defecto</strong>; la tratamos con total discreción.</li>
  <li>Te enviamos una prenda nueva o te devolvemos el dinero por <strong>transferencia</strong> en hasta {DIAS_REEMBOLSO} días hábiles desde que recibimos la prenda.</li>
</ul>
<h2>Garantía</h2>
<p>Defectos de fábrica: {DIAS_GARANTIA} días desde la entrega.</p>
<h2>Ofertas finales</h2>
<p>Los productos marcados como <strong>oferta final</strong> no tienen cambio ni devolución, salvo defecto de fábrica.</p>
<h2>Tu privacidad</h2>
<p>Tu pedido va en <strong>empaque discreto</strong>, sin logo ni descripción del producto.</p>"""
    cierre = f"""
<h2>Cancelaciones</h2>
<ul>
  <li>Antes del despacho: escríbenos por WhatsApp y cancelamos sin costo.</li>
  <li>Si tu pedido ya salió: espera a que llegue y sigue el proceso de cambio o devolución.</li>
</ul>
<h2>Importante</h2>
<p>La disponibilidad y los precios pueden cambiar sin previo aviso. Si hay un error de precio en tu pedido, te avisamos antes de despachar y puedes confirmarlo o cancelarlo con reembolso total.</p>"""
    desc = ("Cambios por talla o color, devoluciones y garantía de Orkia." if marca == "orkia"
            else "Política de cambios y devoluciones de Nudo: higiene, defectos de fábrica y cómo pedir ayuda.")
    return desc, cambios + devol + cierre


def _envios(marca, wa, zonas):
    label = "Orkia" if marca == "orkia" else "Nudo"
    contacto = wa(f"Hola {label} 👋 Quiero consultar el costo y el tiempo de envío a mi zona.")
    filas = "".join(
        f"<tr><td>{esc(z['nombre'])}</td><td>Q{int(z['costo_envio_gtq']) if float(z['costo_envio_gtq']).is_integer() else z['costo_envio_gtq']}</td></tr>"
        for z in zonas
    )
    tabla = (f'<table class="zonas"><thead><tr><th>Zona</th><th>Costo de envío</th></tr></thead><tbody>{filas}</tbody></table>'
             if filas else "<p>Escríbenos por WhatsApp y te confirmamos el costo de tu zona.</p>")
    discreto = ""
    if marca == "nudo":
        discreto = '<li>Tu pedido va en <strong>empaque discreto</strong>, sin logo ni descripción del producto.</li>'
    return (f"Costos y tiempos de envío de {label} en Guatemala. Tu primer envío va por nuestra cuenta.",
            f"""
<h2>Envío gratis</h2>
<ul>
  <li><strong>Tu primer envío va por nuestra cuenta.</strong> Aplica a tu primer pedido.</li>
  <li>Si ya compraste antes, el envío es gratis desde <strong>Q{UMBRAL_ENVIO_GRATIS}</strong> en prendas.</li>
</ul>
<h2>Cuánto cuesta el envío según tu zona</h2>
<p>Si tu compra no entra en el envío gratis, esto es lo que cuesta llevarla a tu zona. Te confirmamos el costo exacto por WhatsApp antes de que pagues.</p>
{tabla}
<p>¿Estás fuera de estas zonas o en otro municipio? <a href="{contacto}" target="_blank" rel="noopener">Escríbenos</a> y te confirmamos si llegamos y cuánto cuesta.</p>
<h2>Cuánto tarda</h2>
<ul>
  <li>Normalmente entre <strong>1 y 3 días hábiles</strong>; en casos especiales, hasta <strong>5 días hábiles</strong>.</li>
  <li>Te escribimos por WhatsApp para coordinar la entrega.</li>
  {discreto}
</ul>
<h2>Cómo pagas</h2>
<p>Aceptamos <strong>transferencia bancaria</strong> y <strong>link de pago</strong>. Nadia te explica cómo cuando confirmemos tu pedido.</p>
<h2>Si no hay nadie para recibir</h2>
<p>Te contactamos por WhatsApp para coordinar una nueva entrega.</p>""")


def _faq(marca, wa):
    label = "Orkia" if marca == "orkia" else "Nudo"
    contacto = wa(f"Hola {label} 👋 Tengo una duda sobre mi pedido.")
    if marca == "orkia":
        cambio = f"Sí, por talla o color, hasta {DIAS_CAMBIO} días después de recibirlo, con la prenda sin uso y con etiquetas. Mira los detalles en <a href=\"/orkia/cambios-y-devoluciones/\">Cambios y devoluciones</a>."
        talla = "Escríbenos por WhatsApp y te asesoramos con la talla antes de comprar."
        prod = "prendas"
    else:
        cambio = "Por higiene, la ropa interior no tiene cambios ni devoluciones, salvo defecto de fábrica. Si te equivocaste de talla y la prenda sigue cerrada, escríbenos y lo revisamos. Mira los detalles en <a href=\"/nudo/cambios-y-devoluciones/\">Cambios y devoluciones</a>."
        talla = "Escríbenos por WhatsApp y te asesoramos con la talla antes de comprar. Es lo más seguro, porque la ropa interior no se cambia."
        prod = "prendas"
    items = [
        ("¿Cómo hago un pedido?", f"Elige tus {prod} en el catálogo, agrégalas a tu selección y envíala por WhatsApp. Te confirmamos disponibilidad y el total, y coordinamos el pago y la entrega."),
        ("¿Cómo pago?", "Por transferencia bancaria o link de pago. Te explicamos cómo cuando confirmemos tu pedido."),
        ("¿Cuánto tarda mi pedido?", "Normalmente entre 1 y 3 días hábiles; en casos especiales, hasta 5 días hábiles."),
        ("¿Cuánto cuesta el envío?", f"Tu primer envío va por nuestra cuenta. Si ya compraste antes, es gratis desde Q{UMBRAL_ENVIO_GRATIS}; si no, depende de tu zona. Mira la tabla en <a href=\"/{marca}/envios/\">Envíos y entregas</a>."),
        ("¿Cómo sé qué talla pedir?", talla),
        ("¿Puedo cambiar mi pedido?", cambio),
        ("¿Puedo cancelar mi pedido?", "Sí, antes del despacho: escríbenos por WhatsApp y cancelamos sin costo."),
    ]
    cuerpo = "".join(f"<h2>{p}</h2><p>{r}</p>" for p, r in items)
    cuerpo += f'<p>¿Otra duda? <a href="{contacto}" target="_blank" rel="noopener">Escríbenos por WhatsApp</a>.</p>'
    return f"Preguntas frecuentes de {label}: pedidos, pagos, envíos, tallas y cambios.", cuerpo


def _terminos(marca, wa):
    label = "Orkia" if marca == "orkia" else "Nudo"
    contacto = wa(f"Hola {label} 👋 Tengo una consulta sobre mis datos o mi pedido.")
    privacidad_extra = ""
    satisfecho = "satisfecho" if marca == "nudo" else "satisfecha"
    if marca == "nudo":
        privacidad_extra = "<li>Tu pedido va en empaque discreto, y usamos tus datos solo para atenderlo.</li>"
    return (f"Términos de uso y política de privacidad de {label}.",
            f"""
<h2>Quiénes somos</h2>
<p>{label} es una marca de CASA JRP. Vendemos en línea y entregamos en Guatemala. Para cualquier consulta, escríbenos por <a href="{contacto}" target="_blank" rel="noopener">WhatsApp</a>.</p>
<h2>Cómo funciona tu compra</h2>
<ul>
  <li>Este sitio es un catálogo. El pedido se confirma por WhatsApp, donde acordamos disponibilidad, total, pago y entrega.</li>
  <li>Los precios están en quetzales (GTQ). La disponibilidad y los precios pueden cambiar sin previo aviso.</li>
  <li>Los cambios, devoluciones y envíos se rigen por las páginas de <a href="/{marca}/cambios-y-devoluciones/">Cambios y devoluciones</a> y <a href="/{marca}/envios/">Envíos y entregas</a>.</li>
</ul>
<h2>Qué datos guardamos y para qué</h2>
<ul>
  <li>Cuando haces un pedido guardamos tu nombre, teléfono, dirección de entrega y el detalle del pedido, para atenderte y entregarlo.</li>
  <li>Si usas "Avísame", guardamos el teléfono que dejes para escribirte cuando haya disponibilidad.</li>
  <li>Registramos de forma interna qué productos se ven en el sitio, para mejorar el catálogo.</li>
  <li>Usamos el píxel de Meta (Facebook e Instagram) para medir visitas y mostrar anuncios de {label} a quien visitó el sitio.</li>
  <li>No vendemos tu información.</li>
  {privacidad_extra}
</ul>
<h2>Tus datos, tu decisión</h2>
<p>Puedes pedirnos que corrijamos o borremos tus datos escribiéndonos por <a href="{contacto}" target="_blank" rel="noopener">WhatsApp</a>.</p>
<h2>Quejas y reclamos</h2>
<p>Si algo salió mal, escríbenos por WhatsApp y lo resolvemos. Queremos que quedes {satisfecho}.</p>""")


def build(marca, slug, wa_number, zonas):
    wa = lambda texto: _wa(marca, wa_number, texto)
    if slug == "cambios-y-devoluciones":
        return _cambios(marca, wa)
    if slug == "envios":
        return _envios(marca, wa, zonas)
    if slug == "preguntas-frecuentes":
        return _faq(marca, wa)
    if slug == "terminos-y-privacidad":
        return _terminos(marca, wa)
    raise ValueError(slug)


# ------------------------------------------------------------------ plantilla

_CSS = """
    :root{--bg:__bg__;--surface:__surface__;--dark:__dark__;--carbon:__carbon__;--text:__text__;--mid:__mid__;--border:__border__;--terracota:__terracota__}
    *{box-sizing:border-box}
    html{scroll-behavior:smooth}
    body{margin:0;min-height:100vh;display:flex;flex-direction:column;background:var(--bg);color:var(--text);font-family:'DM Sans',system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
    a{color:inherit}
    .serif{font-family:'__display__',Georgia,serif;font-weight:400}
    .icon{width:18px;height:18px;stroke:currentColor;stroke-width:1.55;fill:none;stroke-linecap:round;stroke-linejoin:round;flex:0 0 auto}
    .site-header{height:72px;background:linear-gradient(180deg,#161616,#111);color:#fff;display:flex;align-items:center;position:sticky;top:0;z-index:80;border-bottom:1px solid rgba(255,255,255,.07)}
    .header-inner{width:100%;margin:0 auto;padding:0 24px;display:flex;align-items:center;justify-content:space-between;gap:16px}
    .brand{line-height:1;display:flex;align-items:center;gap:10px;text-decoration:none}
    .brand .back{opacity:.75;font-size:13px}
    .brand-logo{font-family:'__display__',Georgia,serif;font-size:28px;letter-spacing:.09em;font-weight:400}
    .brand-dot{display:inline-block;width:6px;height:6px;background:var(--terracota);border-radius:50%;margin-left:2px}
    .icon-btn{color:#fff;padding:6px;line-height:0;display:inline-flex}
    .top-shipping{min-height:40px;padding:8px 16px;background:#EFE8E0;color:var(--text);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:500;text-align:center}
    main{flex:1;width:100%;max-width:760px;margin:0 auto;padding:36px 20px 56px}
    h1{font-family:'__display__',Georgia,serif;font-weight:400;font-size:40px;line-height:1.05;margin:0 0 6px}
    .updated{margin:0 0 26px;font-size:13px;color:var(--mid)}
    h2{font-size:18px;font-weight:600;margin:28px 0 8px}
    p,li{font-size:15.5px;line-height:1.6}
    p{margin:0 0 12px}
    ul{margin:0 0 12px;padding-left:20px}
    li{margin-bottom:6px}
    main a{color:var(--terracota);text-underline-offset:3px}
    table.zonas{width:100%;border-collapse:collapse;margin:8px 0 16px;font-size:14.5px;background:var(--surface)}
    table.zonas th,table.zonas td{padding:9px 12px;border-bottom:1px solid var(--border);text-align:left}
    table.zonas th{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--mid)}
    table.zonas td:last-child,table.zonas th:last-child{text-align:right;white-space:nowrap}
    .footer{background:var(--carbon);color:#fff;padding:22px 28px;text-align:center}
    .footer .brand-logo{font-size:20px}
    .footer p{margin:6px 0 0;color:rgba(255,255,255,.62);font-size:10px;letter-spacing:.14em;text-transform:uppercase}
    .footer-links{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 18px;margin:14px 0 0}
    .footer-links a{color:rgba(255,255,255,.78);font-size:12px;text-decoration:underline;text-underline-offset:3px}
    .wa-float{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;background:#25D366;display:flex;align-items:center;justify-content:center;box-shadow:0 6px 20px rgba(0,0,0,.28);z-index:60}
    .wa-float svg{width:28px;height:28px;color:#fff}
    @media (max-width:800px){h1{font-size:32px}.header-inner{padding:0 16px}.brand-logo{font-size:24px}.wa-float{right:14px;bottom:calc(14px + env(safe-area-inset-bottom));width:50px;height:50px}.wa-float svg{width:25px;height:25px}}
"""

_WA_ICON = ('<svg class="icon" viewBox="0 0 24 24"><path d="M12 21a9 9 0 0 0 7.7-13.7A9 9 0 0 0 5.2 18.6L4 22l3.5-1.1A9 9 0 0 0 12 21Z"/>'
            '<path d="M9.2 8.8c.2-.5.4-.5.7-.5h.5c.2 0 .4.1.5.4l.8 1.8c.1.3 0 .5-.1.7l-.4.5c.6 1 1.4 1.8 2.5 2.4l.6-.5c.2-.1.4-.2.7-.1l1.7.8"/></svg>')


def render(marca, brand, slug, wa_number, pixel_id, zonas):
    titulo = next(t for s, _, t in POLICY_PAGES if s == slug)
    desc, cuerpo = build(marca, slug, wa_number, zonas)
    canonical = f"https://casajrp.com/{marca}/{slug}/"
    page_title = f"{titulo} | {brand['label']}"
    css = _CSS
    for k, v in (("bg", brand["bg"]), ("surface", brand["surface"]), ("dark", brand["dark"]), ("carbon", brand["carbon"]),
                 ("text", brand["text"]), ("mid", brand["mid"]), ("border", brand["border"]),
                 ("terracota", brand["terracota"]), ("display", brand["font_display"])):
        css = css.replace(f"__{k}__", v)
    wa_generic = f"https://wa.me/{wa_number}?text={brand['wa_msg_generic']}"
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="{brand['dark']}" />
  <title>{esc(page_title)}</title>
  <meta name="description" content="{esc(desc)}" />
  <link rel="canonical" href="{canonical}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="{brand['label']}" />
  <meta property="og:title" content="{esc(page_title)}" />
  <meta property="og:description" content="{esc(desc)}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:locale" content="es_GT" />
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
  fbq('init', '{pixel_id}');
  fbq('track', 'PageView');
  </script>
  <noscript>
  <img height="1" width="1" style="display:none"
  src="https://www.facebook.com/tr?id={pixel_id}&ev=PageView&noscript=1"/>
  </noscript>
  <!-- End Facebook Pixel Code -->
  <style>{css}  </style>
</head>
<body>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="/{marca}/" aria-label="Volver al catálogo">
        <span class="icon back">&larr;</span>
        <div class="brand-logo">{brand['label']}<span class="brand-dot"></span></div>
      </a>
      <a class="icon-btn" href="{wa_generic}" target="_blank" rel="noopener" aria-label="WhatsApp">{_WA_ICON}</a>
    </div>
  </header>
  <div class="top-shipping"><span>{brand['ship_banner']}</span></div>
  <main>
    <h1>{esc(titulo)}</h1>
    <p class="updated">Actualizado en {POLICY_FECHA}</p>
{cuerpo}
  </main>
  <footer class="footer">
    <div class="brand-logo serif">{brand['label']}<span class="brand-dot"></span></div>
    {footer_links_html(marca)}
    <p>Guatemala &middot; &copy; 2026</p>
  </footer>
  <a class="wa-float" href="{wa_generic}" target="_blank" rel="noopener" aria-label="Escríbenos por WhatsApp">{_WA_ICON}</a>
</body>
</html>
"""
