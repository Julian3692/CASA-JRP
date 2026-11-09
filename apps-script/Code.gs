// ============================================================
// CASA JRP — Apps Script Multi-Marca
// Orkia + Nudo by CASA JRP
// Última actualización: Octubre 2026 (envío gratis en primera compra + umbral, Orkia y Nudo; códigos)
// ============================================================

const SHEETS = {
  orkia: "1g6HnyPLyNK1PI6ODiW-dMdbA4EFIXeavDnaaq8MAGac",
  nudo:  "1sG2fX6YzdcM63YNfbMRJa228ueVV3SJj"   // <-- actualizado (ID nuevo tras el reemplazo en Drive)
};

// Envío gratis a partir de este monto (subtotal de productos, ANTES de
// descuento/cupón), igual para ambas marcas. Definido Jul 2026.
const UMBRAL_ENVIO_GRATIS_GTQ = 300;

// ============================================================
// ROUTER PRINCIPAL
// ============================================================

function doGet(e) {
  const params = e.parameter;
  const accion = params.accion || "";

  if (!_origenValido(e)) {
    return _json({ error: "origen_no_permitido", accion: accion });
  }

  const marca  = _validarMarca(params.marca);

  try {
    switch (accion) {
      case "get_catalogo":
        return _json(getCatalogo(marca));
      case "get_zonas":
        return _json(getZonas(marca));
      case "registrar_clic":
        return _json(registrarClic(marca, params));
      case "registrar_demanda":
        return _json(registrarDemanda(marca, params));
      case "auditar_integridad":
        // FIX (Sep 2026): expuesta como accion HTTP ademas de funcion manual,
        // para poder consultarla via fetch sin depender de exportar el Sheet
        // a mano (esa exportacion perdia filas en archivos grandes). Lee
        // SpreadsheetApp directo, sin conversion con perdidas. Requiere
        // "marca" igual que las demas acciones, pero internamente audita
        // las dos marcas sin importar cual se mande.
        return _json(auditarIntegridadCatalogo());
      default:
        return _json({ error: "accion_no_reconocida", accion: accion });
    }
  } catch (err) {
    return _json({ error: err.message, accion: accion, marca: marca });
  }
}

function doPost(e) {
  const body  = JSON.parse(e.postData.contents);
  const accion = body.accion || "";

  if (!_origenValido(e)) {
    return _json({ error: "origen_no_permitido", accion: accion });
  }

  const marca  = _validarMarca(body.marca);

  try {
    switch (accion) {
      case "nuevo_pedido":
        return _json(registrarPedido(marca, body));
      case "cotizar_pedido":
        // Oct 2026: POST (no GET) para que el telefono no viaje en la URL.
        return _json(cotizarPedido(marca, body));
      case "nuevo_feedback":
        return _json(registrarFeedback(marca, body));
      default:
        return _json({ error: "accion_no_reconocida", accion: accion });
    }
  } catch (err) {
    return _json({ error: err.message, accion: accion, marca: marca });
  }
}

// ============================================================
// HELPERS INTERNOS
// ============================================================

function _validarMarca(marca) {
  const m = (marca || "").toLowerCase().trim();
  if (!SHEETS[m]) throw new Error("marca_invalida: " + m);
  return m;
}

// ============================================================
// Validacion de origen (Jul 2026)
// No depende de cuentas de Google ni de correo, es un chequeo
// tecnico del header HTTP. Solo bloquea si el request declara
// explicitamente venir de un dominio que NO es casajrp.com.
// Si no manda esa informacion (apps que no son navegador, como
// la de Nadia, pruebas desde Apps Script, etc.), se deja pasar.
// Diseñado a proposito de forma permisiva para no romper
// herramientas internas que todavia no estan mapeadas.
// ============================================================
const DOMINIOS_PERMITIDOS = ["casajrp.com"];

function _origenValido(e) {
  const origen = (e && e.headers && (e.headers.Origin || e.headers.Referer)) || "";
  if (!origen) return true; // sin info de origen -> se permite (apps/servidores)
  return DOMINIOS_PERMITIDOS.some(d => origen.indexOf(d) > -1);
}

// ============================================================
// Sanitizacion de texto libre (Jul 2026)
// Evita inyeccion de formulas en Sheets: si un campo de texto
// libre (nombre, direccion, notas, etc.) empieza con =, +, - o @,
// Google Sheets podria interpretarlo como formula al abrirlo.
// Se antepone un apostrofe para forzar que se guarde como texto.
// ============================================================
function _sanitizar(valor) {
  const v = (valor === undefined || valor === null) ? "" : String(valor);
  if (/^[=+\-@]/.test(v)) return "'" + v;
  return v;
}

function _ss(marca) {
  return SpreadsheetApp.openById(SHEETS[marca]);
}

function _hoja(marca, nombre) {
  const h = _ss(marca).getSheetByName(nombre);
  if (!h) throw new Error("hoja_no_encontrada: " + nombre + " en " + marca);
  return h;
}

function _json(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function _timestamp() {
  return new Date().toISOString();
}

function _fecha() {
  const d = new Date();
  return Utilities.formatDate(d, "America/Guatemala", "dd-MM-yyyy");
}

// ============================================================
// getCatalogo
// Devuelve solo productos publicables:
// Foto_Publicada = TRUE
//
// FIX (Jul 2026, version 2): confirmado contra el bucket real de R2
// que las fotos SIEMPRE se nombran por ID (nunca por Nombre_Foto,
// que es un dato viejo sin uso real en ninguna marca). Lo que SI
// cambia entre marcas es la cantidad de angulos:
//   - Orkia: siempre 3 fijos, confirmado en el bucket real
//     (_frente, _lado, _detalle), sin excepcion en ningun SKU revisado.
//   - Nudo: cantidad variable (1 a 3), por eso existen las columnas
//     Tiene_Foto_Atras / Tiene_Foto_Lado en su DIM_PRODUCTOS.
//
// Regla: si esas dos columnas NO existen en la hoja (caso Orkia),
// se usa el patron fijo de 3 que siempre funciono. Si SI existen
// (caso Nudo), se arma la cantidad real segun cada columna.
//
// FIX (Jul 2026, version 2): el orden final ahora agrupa primero
// por Tipo_Prenda (alfabetico) y dentro de cada grupo mantiene el
// criterio anterior (agotado al final, luego mayor stock primero).
// Antes solo ordenaba por agotado/stock, por eso en Nudo los SKU
// aparecian mezclados sin agrupar por tipo de prenda.
// ============================================================

// Sep 2026: cada get_catalogo leia DIM_PRODUCTOS + DIM_TALLAS_PRODUCTO +
// FACT_STOCK_ACTUAL enteros en cada visita (3 llamadas a Sheets sin cache),
// lo que media entre 2 y 4.5s de forma consistente en TODAS las cargas del
// catalogo. CacheService guarda el JSON ya calculado por CATALOGO_CACHE_SEG
// segundos: casi todas las visitas devuelven el resultado al instante, y el
// inventario nunca queda mas viejo que ese margen.
const CATALOGO_CACHE_SEG = 180;

function getCatalogo(marca) {
  const cache = CacheService.getScriptCache();
  const cacheKey = "catalogo_" + marca;
  const cacheado = cache.get(cacheKey);
  if (cacheado) return JSON.parse(cacheado);

  const resultado = _calcularCatalogo(marca);

  try {
    cache.put(cacheKey, JSON.stringify(resultado), CATALOGO_CACHE_SEG);
  } catch (err) {
    // Si el JSON supera el limite de tamano de CacheService (100KB por
    // clave), seguimos sirviendo la respuesta en vivo sin cache en vez
    // de fallar el request.
  }

  return resultado;
}

function _calcularCatalogo(marca) {
  const ss = _ss(marca);

  // --- DIM_PRODUCTOS ---
  const dimSheet = ss.getSheetByName("DIM_PRODUCTOS");
  if (!dimSheet) throw new Error("hoja_no_encontrada: DIM_PRODUCTOS");

  const dimData = dimSheet.getDataRange().getValues();
  if (!dimData || dimData.length < 2) {
    return { ok: true, marca: marca, total: 0, productos: [] };
  }

  const header = dimData[0];
  const idx = {};
  header.forEach((col, i) => {
    if (col) idx[String(col).trim()] = i;
  });

  if (idx["ID_Producto"] === undefined) {
    throw new Error("columna_no_encontrada: ID_Producto");
  }

  if (idx["Foto_Publicada"] === undefined) {
    throw new Error("columna_no_encontrada: Foto_Publicada");
  }

  const urlBaseCdn = "https://img.casajrp.com/" + marca + "/";

  const productos = {};

  for (let r = 1; r < dimData.length; r++) {
    const row = dimData[r];
    const id  = row[idx["ID_Producto"]];

    if (!id || typeof id !== "number") continue;

    const fotoPublicadaRaw = row[idx["Foto_Publicada"]];
    const fotoPublicada = (
      fotoPublicadaRaw === true ||
      fotoPublicadaRaw === 1 ||
      String(fotoPublicadaRaw).toUpperCase().trim() === "TRUE"
    );

    // Si Foto_Publicada no es TRUE, el producto no se devuelve al catalogo.
    if (!fotoPublicada) continue;

    const idStr = String(id);

    // --- Imagenes: siempre nombradas por ID en R2, nunca por Nombre_Foto ---
    const imagenes = [urlBaseCdn + idStr + "_frente.webp"];

    const tieneColumnasVariables = (idx["Tiene_Foto_Atras"] !== undefined || idx["Tiene_Foto_Lado"] !== undefined);

    if (tieneColumnasVariables) {
      // Caso Nudo: cantidad de angulos variable, confirmada por columna
      const tieneAtras = idx["Tiene_Foto_Atras"] !== undefined && (
        row[idx["Tiene_Foto_Atras"]] === true ||
        String(row[idx["Tiene_Foto_Atras"]]).toUpperCase().trim() === "TRUE"
      );
      const tieneLado = idx["Tiene_Foto_Lado"] !== undefined && (
        row[idx["Tiene_Foto_Lado"]] === true ||
        String(row[idx["Tiene_Foto_Lado"]]).toUpperCase().trim() === "TRUE"
      );
      if (tieneAtras) imagenes.push(urlBaseCdn + idStr + "_atras.webp");
      if (tieneLado)  imagenes.push(urlBaseCdn + idStr + "_lado.webp");
    } else {
      // Caso Orkia (y cualquier marca sin esas columnas): patron fijo de 3,
      // confirmado contra el bucket real, sin excepciones.
      imagenes.push(urlBaseCdn + idStr + "_lado.webp");
      imagenes.push(urlBaseCdn + idStr + "_detalle.webp");
    }

    productos[id] = {
      id_producto:   id,
      ref_proveedor: idx["Ref_Proveedor"] !== undefined ? row[idx["Ref_Proveedor"]] : "",
      tipo_prenda:   idx["Tipo_Prenda"] !== undefined ? row[idx["Tipo_Prenda"]] : "",
      patron:        idx["Patron"] !== undefined ? row[idx["Patron"]] || "" : "",
      material:      idx["Material"] !== undefined ? row[idx["Material"]] || "" : (idx["Manga"] !== undefined ? row[idx["Manga"]] || "" : ""),
      color:         idx["Color"] !== undefined ? row[idx["Color"]] : "",
      descripcion:   idx["Descripcion"] !== undefined ? row[idx["Descripcion"]] : "",
      // Oct 2026 (seguridad): precio_cop, id_proveedor y nombre_foto ya no se
      // publican en get_catalogo. Ningun frontend los usaba y exponian costos
      // y datos de proveedor a cualquiera con la URL.
      precio_gtq:    idx["Precio_GTQ"] !== undefined ? row[idx["Precio_GTQ"]] : "",
      foto_publicada: true,

      // FIX (Jul 2026 v3): se elimino el campo "imagenes" (array) de la
      // respuesta. Ningun frontend (orkia/nudo/operador) lo leia nunca -
      // los 3 se quedaron con el trio url_imagen/_2/_3, que ya refleja
      // exactamente lo mismo (imagenes[0/1/2], con "" cuando no aplica,
      // y el frontend filtra los "" al armar la galeria). Mandar el
      // array ademas de los 3 campos era peso muerto en cada respuesta
      // de get_catalogo, sin ningun consumidor.
      url_imagen:    imagenes[0] || "",
      url_imagen_2:  imagenes[1] || "",
      url_imagen_3:  imagenes[2] || "",

      tallas:        [],
      stock_total:   0,
      agotado:       false
    };
  }

  // --- DIM_TALLAS_PRODUCTO ---
  const tallasSheet = ss.getSheetByName("DIM_TALLAS_PRODUCTO");
  if (!tallasSheet) throw new Error("hoja_no_encontrada: DIM_TALLAS_PRODUCTO");

  const tallasData = tallasSheet.getDataRange().getValues();

  for (let r = 1; r < tallasData.length; r++) {
    const [id_prod, talla, activa] = tallasData[r];

    if (!id_prod || !productos[id_prod]) continue;

    if (activa === 1 || activa === true || activa === "1") {
      productos[id_prod].tallas.push(talla);
    }
  }

  // --- FACT_STOCK_ACTUAL ---
  const stockSheet = ss.getSheetByName("FACT_STOCK_ACTUAL");
  if (!stockSheet) throw new Error("hoja_no_encontrada: FACT_STOCK_ACTUAL");

  const stockData = stockSheet.getDataRange().getValues();

  if (stockData && stockData.length > 1) {
    const stockHeader = stockData[0];
    const sIdx = {};
    stockHeader.forEach((col, i) => {
      if (col) sIdx[String(col).trim()] = i;
    });

    if (sIdx["ID_Producto"] === undefined) {
      throw new Error("columna_no_encontrada: FACT_STOCK_ACTUAL.ID_Producto");
    }

    if (sIdx["Talla"] === undefined) {
      throw new Error("columna_no_encontrada: FACT_STOCK_ACTUAL.Talla");
    }

    if (sIdx["Stock_Actual"] === undefined) {
      throw new Error("columna_no_encontrada: FACT_STOCK_ACTUAL.Stock_Actual");
    }

    for (let r = 1; r < stockData.length; r++) {
      const row     = stockData[r];
      const id_prod = row[sIdx["ID_Producto"]];
      const talla   = row[sIdx["Talla"]];
      const stock   = Number(row[sIdx["Stock_Actual"]]) || 0;

      if (!id_prod || !productos[id_prod]) continue;

      productos[id_prod].stock_total += stock;

      if (stock <= 0) {
        const tallaIdx = productos[id_prod].tallas.indexOf(talla);

        if (tallaIdx > -1) {
          productos[id_prod].tallas.splice(tallaIdx, 1);

          if (!productos[id_prod].tallas_agotadas) {
            productos[id_prod].tallas_agotadas = [];
          }

          productos[id_prod].tallas_agotadas.push(talla);
        }
      }
    }
  }

  Object.values(productos).forEach(p => {
    p.agotado = p.stock_total <= 0;
    if (!p.tallas_agotadas) p.tallas_agotadas = [];
  });

  // FIX (Jul 2026 v2): agrupa primero por Tipo_Prenda (alfabetico),
  // y dentro de cada tipo mantiene el criterio original: agotado al
  // final, y entre los no agotados, mayor stock primero.
  const lista = Object.values(productos).sort((a, b) => {
    const tipoA = String(a.tipo_prenda || "");
    const tipoB = String(b.tipo_prenda || "");
    if (tipoA !== tipoB) return tipoA.localeCompare(tipoB, "es");
    if (a.agotado && !b.agotado) return 1;
    if (!a.agotado && b.agotado) return -1;
    return b.stock_total - a.stock_total;
  });

  return {
    ok: true,
    marca: marca,
    total: lista.length,
    productos: lista
  };
}

// ============================================================
// getZonas
// Lee DIM_ZONAS_ENVIO y devuelve lista de zonas con costo GTQ
// ============================================================

function getZonas(marca) {
  const ss        = _ss(marca);
  const zonasData = ss.getSheetByName("DIM_ZONAS_ENVIO").getDataRange().getValues();
  const header    = zonasData[0];
  const idx       = {};
  header.forEach((col, i) => { if (col) idx[String(col).trim()] = i; });

  const zonas = [];
  for (let r = 1; r < zonasData.length; r++) {
    const row = zonasData[r];
    if (!row[0]) continue;
    // Oct 2026: una zona con Activa = No/FALSE no se ofrece (si la hoja no
    // tiene la columna Activa, todas se ofrecen como siempre).
    if (idx["Activa"] !== undefined) {
      const act = String(row[idx["Activa"]]).toUpperCase().trim();
      if (act === "NO" || act === "FALSE" || act === "0") continue;
    }
    zonas.push({
      id_zona:        row[idx["ID_Zona"]]         || row[0],
      nombre:         row[idx["Nombre_Zona"]]      || row[1] || "",
      barrios:        row[idx["Barrios_Colonias"]] || row[2] || "",
      costo_envio_gtq: Number(row[idx["Costo_Envio_GTQ"]] || row[3]) || 0,
      tiempo_entrega: row[idx["Tiempo_Entrega"]]   || row[4] || "",
      nse_referencia: row[idx["NSE_Referencia"]]   || row[5] || ""
    });
  }

  return { ok: true, zonas: zonas };
}

// ============================================================
// registrarClic
// Mantiene compatibilidad con el front actual.
// Esta MISMA funcion ya sirve para ambas marcas via el parametro
// "marca" -> no hay que duplicarla para Nudo, solo asegurarse de
// que el HTML de Nudo la llame igual que el de Orkia (incluyendo
// el tracking de tiempo por foto, que vive en el frontend, no aqui).
// ============================================================

function registrarClic(marca, params) {
  const hoja = _hoja(marca, "FACT_CATALOGO_CLICS");
  const lastRow = hoja.getLastRow();
  const id = "CLK-" + String(lastRow).padStart(5, "0");

  const accionDetalle =
    params.accion_detalle ||
    params.evento ||
    params.accion ||
    "VER";

  hoja.appendRow([
    id,
    _timestamp(),
    params.id_producto     || "",
    params.nombre_producto || "",
    params.utm_origen      || "directo",
    accionDetalle
  ]);

  return { ok: true, id_clic: id, accion_detalle: accionDetalle };
}

// ============================================================
// registrarDemanda
// Mantiene compatibilidad con Avísame / demanda potencial
// ============================================================

function registrarDemanda(marca, params) {
  const hoja = _hoja(marca, "FACT_DEMANDA_POTENCIAL");
  const lastRow = hoja.getLastRow();
  const id = "DEM-" + String(lastRow).padStart(5, "0");

  hoja.appendRow([
    id,
    _timestamp(),
    params.id_producto     || "",
    params.nombre_producto || "",
    params.color           || "",
    params.talla           || "",
    params.canal_origen    || params.utm_origen || "directo"
  ]);

  return { ok: true, id_demanda: id };
}

// ============================================================
// registrarPedido
// FACT_LINEAS_PEDIDO escribe valores calculados desde Apps Script
//
// FIX (Jul 2026 v2): antes, precioMap solo leia Precio_COP, y el
// total_gtq final se recalculaba desde cero como
// total_cop * TASA_COP_GTQ (0.005), IGNORANDO por completo el
// Precio_GTQ que ya esta fijado manualmente por SKU en DIM_PRODUCTOS
// (con margenes distintos por tipo de prenda). Eso hacia que el total
// guardado en FACT_PEDIDOS fuera SIEMPRE mas bajo que el total que
// Nadia ve y cotiza en pantalla (calculado client-side con
// precio_gtq del catalogo).
//
// Ahora precioMapGTQ lee Precio_GTQ directamente, igual que
// precioMap lee Precio_COP, y subtotal_gtq/total_gtq se calculan
// sumando esos valores por linea.
//
// FIX (Jul 2026 v3): se elimino TASA_COP_GTQ. El descuento se lee
// directo de body.descuento_gtq (en Quetzales, la moneda que
// realmente se cobra) en vez de convertir un descuento_cop con una
// tasa fija que no reflejaba el tipo de cambio real y que ademas
// siempre multiplicaba por 0 (el front nunca mando un descuento_cop
// distinto de 0). descuento_cop se mantiene solo para el total_cop
// de referencia interna de costo/margen frente al proveedor.
// ============================================================

// ============================================================
// Reglas comerciales por marca (Oct 2026)
// Orkia y Nudo comparten el mismo esquema: envio gratis en la primera compra
// y, para quien ya compro, desde el umbral (UMBRAL_ENVIO_GRATIS_GTQ). Los
// codigos de influencer usan la hoja DIM_CODIGOS, que es opcional: mientras
// no exista, el codigo solo se registra como texto, como siempre.
// ============================================================

const REGLAS_MARCA = {
  orkia: { primeraCompra: true, codigos: true },
  nudo:  { primeraCompra: true, codigos: true }
};

function _reglas(marca) {
  return REGLAS_MARCA[marca] || { primeraCompra: false, codigos: false };
}

// Telefono comparable: solo digitos, ultimos 8 (numeros de Guatemala).
// Evita que "5555-1234", "+502 5555 1234" y "55551234" cuenten como
// clientes distintos (y regalen el envio de primera compra dos veces).
function _telNorm(t) {
  const d = String(t === undefined || t === null ? "" : t).replace(/\D/g, "");
  return d.length > 8 ? d.slice(-8) : d;
}

function _mismoTelefono(marca, a, b) {
  if (_reglas(marca).primeraCompra) {
    const na = _telNorm(a);
    return na !== "" && na === _telNorm(b);
  }
  return String(a) === String(b);   // Nudo: comparacion exacta, como siempre
}

function _esSi(v) {
  if (v === true || v === 1) return true;
  const s = String(v === undefined || v === null ? "" : v).toUpperCase().trim();
  return s === "TRUE" || s === "SI" || s === "SÍ" || s === "1";
}

// Zona de envio: acepta ID ("Z1"), nombre ("Centro") o un barrio/zona
// de la lista ("Zona 9"). Si nada coincide, costo 0 e id vacio.
function _resolverZona(zonasData, zona) {
  const z = String(zona || "").trim().toLowerCase();
  if (!z) return { id_zona: "", costo: 0 };

  for (let r = 1; r < zonasData.length; r++) {
    const row = zonasData[r];
    if (!row[0]) continue;
    if (String(row[0]).trim().toLowerCase() === z || String(row[1] || "").trim().toLowerCase() === z) {
      return { id_zona: row[0], costo: Number(row[3]) || 0 };
    }
  }
  for (let r = 1; r < zonasData.length; r++) {
    const row = zonasData[r];
    if (!row[0]) continue;
    const barrios = String(row[2] || "").toLowerCase().split(",").map(s => s.trim());
    if (barrios.indexOf(z) > -1) return { id_zona: row[0], costo: Number(row[3]) || 0 };
  }
  for (let r = 1; r < zonasData.length; r++) {
    const row = zonasData[r];
    if (!row[0]) continue;
    if (String(row[2] || "").toLowerCase().indexOf(z) > -1) return { id_zona: row[0], costo: Number(row[3]) || 0 };
  }
  return { id_zona: "", costo: 0 };
}

// Fecha de una celda (Date, "dd-MM-yyyy" o "yyyy-MM-dd") como "yyyy-MM-dd".
function _fechaISO(v) {
  if (v instanceof Date) return Utilities.formatDate(v, "America/Guatemala", "yyyy-MM-dd");
  const s = String(v || "").trim();
  let m = s.match(/^(\d{2})-(\d{2})-(\d{4})$/);
  if (m) return m[3] + "-" + m[2] + "-" + m[1];
  m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? m[1] + "-" + m[2] + "-" + m[3] : "";
}

// Valida un codigo de influencer contra DIM_CODIGOS. Lanza un error con
// mensaje claro (el operador lo ve tal cual) si no existe, esta inactivo
// o todavia no inicia. Se llama ANTES de escribir cualquier fila.
// Si la hoja DIM_CODIGOS todavia no existe, devuelve null (sin descuento: el
// codigo se guarda como texto, como antes). Una vez creada, se valida en serio.
function _validarCodigo(ss, codigoRaw) {
  const codigo = String(codigoRaw || "").trim().toUpperCase();
  const hoja = ss.getSheetByName("DIM_CODIGOS");
  if (!hoja) return null;
  const data = hoja.getDataRange().getValues();
  const idx = {};
  (data[0] || []).forEach((c, i) => { if (c) idx[String(c).trim()] = i; });
  ["Codigo", "Descuento_Pct", "Activo"].forEach(c => {
    if (idx[c] === undefined) throw new Error("columna_no_encontrada: DIM_CODIGOS." + c);
  });

  for (let r = 1; r < data.length; r++) {
    const row = data[r];
    if (String(row[idx["Codigo"]] || "").trim().toUpperCase() !== codigo) continue;

    if (!_esSi(row[idx["Activo"]])) {
      throw new Error("El código «" + codigo + "» está inactivo. Pedido no registrado.");
    }
    const inicio = idx["Fecha_Inicio"] !== undefined ? _fechaISO(row[idx["Fecha_Inicio"]]) : "";
    if (inicio && inicio > Utilities.formatDate(new Date(), "America/Guatemala", "yyyy-MM-dd")) {
      throw new Error("El código «" + codigo + "» todavía no está vigente (inicia el " + inicio + "). Pedido no registrado.");
    }
    const pct = Number(row[idx["Descuento_Pct"]]) || 0;
    if (pct <= 0 || pct > 100) {
      throw new Error("El código «" + codigo + "» no tiene un descuento válido. Pedido no registrado.");
    }
    return { codigo: codigo, pct: pct };
  }
  throw new Error("El código «" + codigo + "» no existe. Pedido no registrado.");
}

// Calculo puro (sin Sheets): mismos numeros para cotizar y para registrar.
//   o.unidades        [{precio}] una entrada por prenda (cantidad ya expandida)
//   o.descuentoManual Descuento extra que mande el front (heredado), en GTQ
//   o.costoEnvioZona  Costo de la zona, GTQ
//   o.esNuevo         true si el telefono no existia en DIM_CLIENTES
//   o.reglas          REGLAS_MARCA[marca]
//   o.codigoPct       % del codigo ya validado (0 si no hay)
function _calcularTotalesPedido(o) {
  const unidades = o.unidades.map(u => ({ precio: Number(u.precio) || 0 }));
  const subtotal = unidades.reduce((s, u) => s + u.precio, 0);

  // Codigo: % sobre el subtotal, redondeado al quetzal mas cercano.
  let descuento_codigo = 0;
  if (o.codigoPct > 0) {
    descuento_codigo = Math.round(subtotal * o.codigoPct / 100);
  }

  const descuento_manual = Math.round((Number(o.descuentoManual) || 0) * 100) / 100;
  const descuento_total  = Math.min(subtotal, descuento_codigo + descuento_manual);

  // Envio gratis: el umbral se compara contra el subtotal ANTES de descuentos.
  // Si no llega al umbral, la primera compra tambien lo regala.
  let envio_gratis = false;
  let motivo_envio_gratis = "";
  if (subtotal >= UMBRAL_ENVIO_GRATIS_GTQ) {
    envio_gratis = true;
    motivo_envio_gratis = "umbral";
  } else if (o.reglas.primeraCompra && o.esNuevo) {
    envio_gratis = true;
    motivo_envio_gratis = "primera_compra";
  }
  const costo_envio_cobrado = envio_gratis ? 0 : o.costoEnvioZona;
  // Zona sin tarifa cargada ("a validar"): el total NO incluye envio y el
  // operador debe cobrarlo aparte. Se avisa para que no pase desapercibido.
  const envio_por_validar = !envio_gratis && !(Number(o.costoEnvioZona) > 0);

  return {
    subtotal_gtq:         subtotal,
    descuento_codigo_gtq: descuento_codigo,
    descuento_gtq:        Math.round(descuento_total * 100) / 100,
    envio_gratis:         envio_gratis,
    motivo_envio_gratis:  motivo_envio_gratis,
    envio_por_validar:    envio_por_validar,
    costo_envio_cobrado:  costo_envio_cobrado,
    total_gtq:            Math.round((subtotal - descuento_total + costo_envio_cobrado) * 100) / 100
  };
}

// Lee Sheets y calcula el pedido SIN escribir nada. Si algo no es valido
// (codigo inexistente/inactivo), lanza el error antes de que registrarPedido
// toque DIM_CLIENTES, FACT_PEDIDOS o FACT_LINEAS_PEDIDO.
function _prepararPedido(marca, body) {
  const ss     = _ss(marca);
  const reglas = _reglas(marca);

  // --- Cliente (solo lectura) ---
  const clienteSheet = ss.getSheetByName("DIM_CLIENTES");
  const clienteData  = clienteSheet.getDataRange().getValues();
  let id_cliente = null, fila_cliente = 0, total_actual = 0;
  for (let r = 1; r < clienteData.length; r++) {
    if (_mismoTelefono(marca, clienteData[r][2], body.telefono)) {
      id_cliente   = clienteData[r][0];
      fila_cliente = r + 1;
      total_actual = Number(clienteData[r][8]) || 0;
      break;
    }
  }

  // --- DIM_PRODUCTOS: precios (GTQ es lo que se cobra) ---
  const dimData = ss.getSheetByName("DIM_PRODUCTOS").getDataRange().getValues();
  const dIdx    = {};
  dimData[0].forEach((col, i) => { if (col) dIdx[String(col).trim()] = i; });
  if (dIdx["Precio_GTQ"] === undefined) {
    throw new Error("columna_no_encontrada: Precio_GTQ en DIM_PRODUCTOS");
  }

  const precioMap    = {};   // Precio_COP: referencia interna
  const precioMapGTQ = {};   // Precio_GTQ: lo que se cobra
  const dim_dict     = {};
  for (let r = 1; r < dimData.length; r++) {
    const row = dimData[r];
    const id  = row[dIdx["ID_Producto"]];
    if (!id || typeof id !== "number") continue;
    precioMap[id]    = Number(row[dIdx["Precio_COP"]]) || 0;
    precioMapGTQ[id] = Number(row[dIdx["Precio_GTQ"]]) || 0;
    dim_dict[id]     = {
      color:         row[dIdx["Color"]]         || "",
      tipo_prenda:   row[dIdx["Tipo_Prenda"]]   || "",
      ref_proveedor: row[dIdx["Ref_Proveedor"]] || ""
    };
  }

  // --- Lineas -> unidades ---
  const lineas       = body.lineas || [];
  const unidades     = [];
  let   subtotal_cop = 0;   // referencia interna
  lineas.forEach(l => {
    const cantidad = Math.min(100, Math.max(1, Math.floor(Number(l.cantidad) || 1)));
    subtotal_cop  += (precioMap[l.id_producto] || 0) * cantidad;
    for (let i = 0; i < cantidad; i++) {
      unidades.push({ precio: precioMapGTQ[l.id_producto] || 0 });
    }
  });
  const descuento_cop = Number(body.descuento_cop) || 0;

  // --- Zona y costo de envio ---
  const zonasData = ss.getSheetByName("DIM_ZONAS_ENVIO").getDataRange().getValues();
  const zona      = _resolverZona(zonasData, body.zona_gt);

  // --- Codigo de influencer. Lanza si no es valido. ---
  const codigoRaw  = String(body.codigo_descuento || "").trim();
  const codigoInfo = (reglas.codigos && codigoRaw) ? _validarCodigo(ss, codigoRaw) : null;

  const totales = _calcularTotalesPedido({
    unidades:        unidades,
    descuentoManual: body.descuento_gtq,
    costoEnvioZona:  zona.costo,
    esNuevo:         !id_cliente,
    reglas:          reglas,
    codigoPct:       codigoInfo ? codigoInfo.pct : 0
  });

  return {
    ss: ss, reglas: reglas, clienteSheet: clienteSheet,
    id_cliente: id_cliente, fila_cliente: fila_cliente, total_actual: total_actual,
    es_nuevo: !id_cliente,
    lineas: lineas, dim_dict: dim_dict, precioMap: precioMap,
    subtotal_cop: subtotal_cop, descuento_cop: descuento_cop,
    id_zona: zona.id_zona, costo_envio: zona.costo,
    codigo: codigoInfo ? codigoInfo.codigo : codigoRaw,   // sin hoja de codigos: texto tal cual, como antes
    totales: totales
  };
}

// ============================================================
// cotizarPedido
// Misma cuenta que registrarPedido, sin escribir nada. La usa la app del
// operador para que el total en pantalla sea EXACTAMENTE el que se guarda.
// ============================================================

function cotizarPedido(marca, body) {
  const c = _prepararPedido(marca, body);
  const t = c.totales;
  return {
    ok:                   true,
    es_nuevo:             c.es_nuevo,
    subtotal_gtq:         t.subtotal_gtq,
    descuento_codigo_gtq: t.descuento_codigo_gtq,
    descuento_gtq:        t.descuento_gtq,
    costo_envio_gtq:      c.costo_envio,
    envio_gratis:         t.envio_gratis,
    motivo_envio_gratis:  t.motivo_envio_gratis,
    envio_por_validar:    t.envio_por_validar,
    total_gtq:            t.total_gtq
  };
}

function registrarPedido(marca, body) {
  // 1. Calcular y validar TODO antes de escribir (un codigo invalido corta aqui).
  const c = _prepararPedido(marca, body);
  const t = c.totales;
  const ss = c.ss;

  // --- 2. Cliente ---
  let id_cliente = c.id_cliente;
  if (id_cliente) {
    c.clienteSheet.getRange(c.fila_cliente, 9).setValue(c.total_actual + 1);
  } else {
    const nextRow = c.clienteSheet.getLastRow() + 1;
    id_cliente    = "CLI-" + String(nextRow - 1).padStart(5, "0");
    c.clienteSheet.appendRow([
      id_cliente,
      _sanitizar(body.nombre_cliente || ""),
      body.telefono       || "",
      _sanitizar(body.correo || ""),
      body.canal_origen   || "",
      _fecha(),
      false,
      "",
      1,
      "",
      "",
      "",
      "",
      ""
    ]);
  }

  // --- 3. Numero de pedido ---
  const pedidosSheet  = ss.getSheetByName("FACT_PEDIDOS");
  const nextPedidoRow = pedidosSheet.getLastRow() + 1;
  const id_pedido     = "PED-" + String(nextPedidoRow - 1).padStart(5, "0");
  const total_cop     = c.subtotal_cop - c.descuento_cop;

  // --- 4. FACT_PEDIDOS ---
  // costo_envio (el precio estandar de la zona) se guarda SIEMPRE, aunque el
  // envio sea gratis, para que quede registro de cuanto hubiera costado.
  const fila = [
    id_pedido,
    _fecha(),
    id_cliente,
    _sanitizar(body.nombre_cliente || ""),
    body.telefono       || "",
    body.ciudad         || "Guatemala City",
    body.zona_gt        || "",
    _sanitizar(body.colonia || ""),
    _sanitizar(body.direccion || ""),
    _sanitizar(body.referencias || ""),
    body.nse_inferido   || "",
    c.id_zona,
    c.costo_envio,
    body.banco          || "",
    body.metodo_pago    || "",
    "Pendiente pago",
    c.subtotal_cop,
    c.descuento_cop,
    total_cop,
    t.descuento_gtq,    // Descuento_GTQ: codigo (+ descuento manual heredado)
    t.total_gtq,
    c.codigo,           // Codigo_Descuento (el codigo validado, en mayusculas)
    body.comprobante === "Si",
    _sanitizar(body.notas || ""),
    body.motivo_compra  || "",
    body.perfil_decision || "",
    body.canal_origen   || "",
    body.edad_inferida  || "",
    body.mes_cumpleanos || "",
    t.envio_gratis      // Envio_Gratis: TRUE = costo_envio NO esta sumado en total_gtq
  ];
  // Columna nueva al final, "Motivo_Envio_Gratis" (umbral | primera_compra | vacio),
  // solo en pedidos nuevos. Agregar ese encabezado en FACT_PEDIDOS de la marca antes de desplegar.
  if (c.reglas.primeraCompra) fila.push(t.motivo_envio_gratis);
  pedidosSheet.appendRow(fila);

  // --- 5. FACT_LINEAS_PEDIDO ---
  const lineasSheet = ss.getSheetByName("FACT_LINEAS_PEDIDO");
  const rowsLineas = c.lineas.map((linea, i) => {
    const id_linea = id_pedido + "-L" + String(i + 1).padStart(2, "0");
    const d        = c.dim_dict[linea.id_producto] || {};
    const precio   = c.precioMap[linea.id_producto] || 0;
    const cant     = Number(linea.cantidad) || 1;
    return [
      id_pedido,
      id_linea,
      linea.id_producto,
      linea.talla || "",
      d.color || "",
      precio,
      cant,
      precio * cant,
      d.tipo_prenda || "",
      d.ref_proveedor || ""
    ];
  });

  if (rowsLineas.length > 0) {
    const lastRow = lineasSheet.getLastRow() + 1;
    lineasSheet.getRange(lastRow, 1, rowsLineas.length, 10).setValues(rowsLineas);
  }

  return {
    ok:                   true,
    id_pedido:            id_pedido,
    id_cliente:           id_cliente,
    es_nuevo:             c.es_nuevo,
    subtotal_cop:         c.subtotal_cop,
    descuento_cop:        c.descuento_cop,
    total_cop:            total_cop,
    subtotal_gtq:         t.subtotal_gtq,
    descuento_gtq:        t.descuento_gtq,
    descuento_codigo_gtq: t.descuento_codigo_gtq,
    costo_envio_gtq:      c.costo_envio,      // precio estandar de la zona (siempre, aunque sea gratis)
    envio_gratis:         t.envio_gratis,
    motivo_envio_gratis:  t.motivo_envio_gratis,
    envio_por_validar:    t.envio_por_validar,
    total_gtq:            t.total_gtq,        // ya incluye costo_envio si no aplico envio gratis
    lineas:               c.lineas.length
  };
}

// ============================================================
// Reporte mensual de codigos de influencer (Oct 2026)
// Se corre a mano desde el editor de Apps Script. Escribe la hoja
// REPORTE_CODIGOS en el Sheet de la marca (la reemplaza en cada corrida):
//   - reporteCodigosMesActual()   -> mes en curso
//   - reporteCodigosMesAnterior() -> mes anterior (el que se liquida)
// Ventas = lo que pago la clienta SIN envio (total_gtq menos el envio si se cobro).
// Comision = Comision_Pct de DIM_CODIGOS sobre esas ventas. No cuenta pedidos
// cuyo Estado contenga "cancel".
// ============================================================

function reporteCodigosMesActual()        { return _reporteCodigosMes("orkia", 0); }
function reporteCodigosMesAnterior()      { return _reporteCodigosMes("orkia", -1); }
function reporteCodigosNudoMesActual()    { return _reporteCodigosMes("nudo", 0); }
function reporteCodigosNudoMesAnterior()  { return _reporteCodigosMes("nudo", -1); }

function _reporteCodigosMes(marca, desfase) {
  const hoy = new Date();
  const d   = new Date(hoy.getFullYear(), hoy.getMonth() + desfase, 1);
  return _reporteCodigos(marca, d.getFullYear(), d.getMonth() + 1);
}

function _reporteCodigos(marca, anio, mes) {
  const ss  = _ss(marca);
  const mm  = String(mes).padStart(2, "0");
  const per = anio + "-" + mm;

  // Codigos y su comision
  const cod  = ss.getSheetByName("DIM_CODIGOS").getDataRange().getValues();
  const cIdx = {};
  cod[0].forEach((c, i) => { if (c) cIdx[String(c).trim()] = i; });
  const info = {};
  for (let r = 1; r < cod.length; r++) {
    const k = String(cod[r][cIdx["Codigo"]] || "").trim().toUpperCase();
    if (!k) continue;
    info[k] = {
      influencer: cod[r][cIdx["Influencer"]] || "",
      comision:   Number(cod[r][cIdx["Comision_Pct"]]) || 0
    };
  }

  // Pedidos del mes con codigo (posiciones = orden de columnas que escribe registrarPedido)
  const ped = ss.getSheetByName("FACT_PEDIDOS").getDataRange().getValues();
  const resumen = {};
  const detalle = [];
  for (let r = 1; r < ped.length; r++) {
    const row    = ped[r];
    const codigo = String(row[21] || "").trim().toUpperCase();
    if (!codigo || !info[codigo]) continue;
    if (_fechaISO(row[1]).slice(0, 7) !== per) continue;
    if (String(row[15] || "").toLowerCase().indexOf("cancel") > -1) continue;

    const total   = Number(row[20]) || 0;
    const envio   = _esSi(row[29]) ? 0 : (Number(row[12]) || 0);
    const ventas  = Math.round((total - envio) * 100) / 100;
    const comis   = Math.round(ventas * info[codigo].comision) / 100;
    const desc    = Number(row[19]) || 0;

    if (!resumen[codigo]) resumen[codigo] = { pedidos: 0, ventas: 0, descuentos: 0, comision: 0 };
    resumen[codigo].pedidos++;
    resumen[codigo].ventas     += ventas;
    resumen[codigo].descuentos += desc;
    resumen[codigo].comision   += comis;
    detalle.push([row[0], row[1], codigo, row[15], desc, ventas, comis]);
  }

  let hoja = ss.getSheetByName("REPORTE_CODIGOS");
  if (!hoja) hoja = ss.insertSheet("REPORTE_CODIGOS");
  hoja.clear();

  const filas = [["Periodo", per], [], ["Codigo", "Influencer", "Pedidos", "Ventas_GTQ", "Descuentos_GTQ", "Comision_Pct", "Comision_GTQ"]];
  Object.keys(info).forEach(k => {
    const x = resumen[k] || { pedidos: 0, ventas: 0, descuentos: 0, comision: 0 };
    filas.push([k, info[k].influencer, x.pedidos, x.ventas, x.descuentos, info[k].comision, Math.round(x.comision * 100) / 100]);
  });
  filas.push([], ["Detalle"], ["ID_Pedido", "Fecha", "Codigo", "Estado", "Descuento_GTQ", "Ventas_GTQ", "Comision_GTQ"]);
  detalle.forEach(d => filas.push(d));

  const ancho = 7;
  const norm  = filas.map(f => { const a = f.slice(); while (a.length < ancho) a.push(""); return a; });
  hoja.getRange(1, 1, norm.length, ancho).setValues(norm);
  return { ok: true, periodo: per, codigos: Object.keys(resumen).length, pedidos: detalle.length };
}

// ============================================================
// registrarFeedback
// ============================================================

function registrarFeedback(marca, body) {
  const hoja = _hoja(marca, "FACT_FEEDBACK");
  const lastRow = hoja.getLastRow();
  const id = "FBK-" + String(lastRow).padStart(5, "0");

  hoja.appendRow([
    id,
    body.id_pedido          || "",
    body.id_cliente         || "",
    _fecha(),
    "",
    body.talla_quedo_bien   || "",
    _sanitizar(body.comentario_talla || ""),
    body.nps                || "",
    _sanitizar(body.comentario_general || ""),
    _sanitizar(body.haria_cambio || ""),
    _sanitizar(body.producto_cambiado || ""),
    "Nadia"
  ]);

  return { ok: true, id_feedback: id };
}

// ============================================================
// auditarIntegridadCatalogo (Sep 2026)
//
// Control de integridad entre DIM_PRODUCTOS y FACT_STOCK_ACTUAL, para
// ambas marcas. Nace del hallazgo de que 10212/10228/10242 (Orkia)
// tenian stock real, fotos reales y hasta pedidos confirmados, pero
// su fila en DIM_PRODUCTOS habia desaparecido sin que nada lo avisara
// (Sheets no valida esto solo). Esta funcion NO se llama desde doGet/
// doPost -> se corre a mano desde el editor (seleccionar la funcion
// en el dropdown de arriba y darle "Ejecutar"), no requiere una
// nueva implementacion/deploy.
//
// Que revisa, por marca:
//   1. SIN_FICHA_DIM_PRODUCTOS: ID_Producto con stock en
//      FACT_STOCK_ACTUAL pero SIN fila en DIM_PRODUCTOS.
//   2. SIN_STOCK_REGISTRADO: fila en DIM_PRODUCTOS que nunca aparece
//      en FACT_STOCK_ACTUAL (puede ser normal si es un producto que
//      todavia no recibio su primera entrada).
//   3. STOCK_NEGATIVO: Stock_Actual < 0 (salida registrada sin su
//      entrada correspondiente).
//   4. FOTO_ROTA: productos con Foto_Publicada=TRUE cuya foto
//      "_frente" ya no responde 200 en el CDN.
//
// Escribe el resultado en una pestaña nueva "AUDITORIA_INTEGRIDAD"
// dentro del Sheet de cada marca (se recrea cada vez que se corre,
// para que siempre refleje el estado actual).
// ============================================================

function auditarIntegridadCatalogo() {
  const resumen = {};

  Object.keys(SHEETS).forEach(marca => {
    const ss = _ss(marca);
    const problemas = [];

    // --- Leer DIM_PRODUCTOS ---
    const dim = ss.getSheetByName("DIM_PRODUCTOS").getDataRange().getValues();
    const dimHeader = dim[0];
    const dimIdx = {};
    dimHeader.forEach((c, i) => { if (c) dimIdx[String(c).trim()] = i; });

    const dimIds = new Set();
    const fotoPublicadaById = {};
    for (let r = 1; r < dim.length; r++) {
      const id = dim[r][dimIdx["ID_Producto"]];
      if (!id) continue;
      const idStr = String(id);
      dimIds.add(idStr);
      const raw = dim[r][dimIdx["Foto_Publicada"]];
      fotoPublicadaById[idStr] = (raw === true || raw === 1 || String(raw).toUpperCase().trim() === "TRUE");
    }

    // --- Leer FACT_STOCK_ACTUAL ---
    const stock = ss.getSheetByName("FACT_STOCK_ACTUAL").getDataRange().getValues();
    const stockHeader = stock[0];
    const sIdx = {};
    stockHeader.forEach((c, i) => { if (c) sIdx[String(c).trim()] = i; });

    const stockByProduct = {};
    for (let r = 1; r < stock.length; r++) {
      const id = String(stock[r][sIdx["ID_Producto"]] || "");
      if (!id) continue;
      const cantidad = Number(stock[r][sIdx["Stock_Actual"]]) || 0;
      stockByProduct[id] = (stockByProduct[id] || 0) + cantidad;
    }

    // 1. SIN_FICHA_DIM_PRODUCTOS
    Object.keys(stockByProduct).forEach(id => {
      if (!dimIds.has(id)) {
        problemas.push([id, "SIN_FICHA_DIM_PRODUCTOS", stockByProduct[id], "Tiene stock pero no existe fila en DIM_PRODUCTOS"]);
      }
    });

    // 2. SIN_STOCK_REGISTRADO
    dimIds.forEach(id => {
      if (!(id in stockByProduct)) {
        problemas.push([id, "SIN_STOCK_REGISTRADO", "", "Existe en DIM_PRODUCTOS pero nunca aparece en FACT_STOCK_ACTUAL"]);
      }
    });

    // 3. STOCK_NEGATIVO
    Object.keys(stockByProduct).forEach(id => {
      if (stockByProduct[id] < 0) {
        problemas.push([id, "STOCK_NEGATIVO", stockByProduct[id], "Salida registrada sin entrada suficiente"]);
      }
    });

    // 4. FOTO_ROTA (solo productos marcados como publicados)
    Object.keys(fotoPublicadaById).forEach(id => {
      if (!fotoPublicadaById[id]) return;
      const url = "https://img.casajrp.com/" + marca + "/" + id + "_frente.webp";
      try {
        const resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
        if (resp.getResponseCode() !== 200) {
          problemas.push([id, "FOTO_ROTA", resp.getResponseCode(), "Foto_Publicada=TRUE pero " + url + " no responde 200"]);
        }
      } catch (err) {
        problemas.push([id, "FOTO_ROTA", "ERROR", "No se pudo verificar " + url + ": " + err.message]);
      }
    });

    // --- Escribir resultado en pestaña de auditoria propia del Sheet ---
    let outSheet = ss.getSheetByName("AUDITORIA_INTEGRIDAD");
    if (!outSheet) outSheet = ss.insertSheet("AUDITORIA_INTEGRIDAD");
    outSheet.clear();
    const fecha = _timestamp();
    outSheet.appendRow(["ID_Producto", "Tipo_Problema", "Valor", "Detalle", "Fecha_Auditoria"]);
    problemas.forEach(p => outSheet.appendRow([p[0], p[1], p[2], p[3], fecha]));
    if (problemas.length === 0) {
      outSheet.appendRow(["(ninguno)", "OK", "", "Sin problemas detectados en esta corrida", fecha]);
    }

    resumen[marca] = { total_problemas: problemas.length, problemas: problemas };
  });

  return resumen;
}
