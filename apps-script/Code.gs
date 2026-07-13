// ============================================================
// CASA JRP — Apps Script Multi-Marca
// Orkia + Nudo by CASA JRP
// Última actualización: Julio 2026 (v2 — fix Precio_GTQ + orden catálogo)
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

function getCatalogo(marca) {
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
    const nombreFoto = idx["Nombre_Foto"] !== undefined ? row[idx["Nombre_Foto"]] || "" : "";

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
      id_proveedor:  idx["ID_Proveedor"] !== undefined ? row[idx["ID_Proveedor"]] : "",
      ref_proveedor: idx["Ref_Proveedor"] !== undefined ? row[idx["Ref_Proveedor"]] : "",
      tipo_prenda:   idx["Tipo_Prenda"] !== undefined ? row[idx["Tipo_Prenda"]] : "",
      patron:        idx["Patron"] !== undefined ? row[idx["Patron"]] || "" : "",
      material:      idx["Material"] !== undefined ? row[idx["Material"]] || "" : (idx["Manga"] !== undefined ? row[idx["Manga"]] || "" : ""),
      color:         idx["Color"] !== undefined ? row[idx["Color"]] : "",
      precio_cop:    idx["Precio_COP"] !== undefined ? row[idx["Precio_COP"]] : "",
      descripcion:   idx["Descripcion"] !== undefined ? row[idx["Descripcion"]] : "",
      nombre_foto:   nombreFoto,  // se mantiene en la respuesta por compatibilidad, ya no define la URL
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

function registrarPedido(marca, body) {
  const ss = _ss(marca);

  // --- 1. Cliente ---
  const clienteSheet = ss.getSheetByName("DIM_CLIENTES");
  const clienteData  = clienteSheet.getDataRange().getValues();

  let id_cliente = null;
  let es_nuevo   = false;

  for (let r = 1; r < clienteData.length; r++) {
    if (String(clienteData[r][2]) === String(body.telefono)) {
      id_cliente = clienteData[r][0];
      const total_actual = Number(clienteData[r][8]) || 0;
      clienteSheet.getRange(r + 1, 9).setValue(total_actual + 1);
      break;
    }
  }

  if (!id_cliente) {
    es_nuevo       = true;
    const nextRow  = clienteSheet.getLastRow() + 1;
    const total_cl = nextRow - 1;
    id_cliente     = "CLI-" + String(total_cl).padStart(5, "0");

    clienteSheet.appendRow([
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

  // --- 2. Número de pedido ---
  const pedidosSheet  = ss.getSheetByName("FACT_PEDIDOS");
  const nextPedidoRow = pedidosSheet.getLastRow() + 1;
  const num_pedido    = nextPedidoRow - 1;
  const id_pedido     = "PED-" + String(num_pedido).padStart(5, "0");

  // --- 3. Leer DIM_PRODUCTOS en batch para precios y datos adicionales ---
  const dimData2  = ss.getSheetByName("DIM_PRODUCTOS").getDataRange().getValues();
  const dimHeader = dimData2[0];
  const dIdx      = {};
  dimHeader.forEach((col, i) => { if (col) dIdx[String(col).trim()] = i; });

  if (dIdx["Precio_GTQ"] === undefined) {
    throw new Error("columna_no_encontrada: Precio_GTQ en DIM_PRODUCTOS");
  }

  const precioMap    = {};   // Precio_COP por SKU (se mantiene para reportes internos)
  const precioMapGTQ = {};   // FIX: Precio_GTQ por SKU, fuente real del cobro al cliente
  const dim_dict     = {};

  for (let r = 1; r < dimData2.length; r++) {
    const row = dimData2[r];
    const id  = row[dIdx["ID_Producto"]];
    if (!id || typeof id !== "number") continue;

    precioMap[id]    = Number(row[dIdx["Precio_COP"]]) || 0;
    precioMapGTQ[id] = Number(row[dIdx["Precio_GTQ"]]) || 0;
    dim_dict[id]  = {
      color:         row[dIdx["Color"]]        || "",
      tipo_prenda:   row[dIdx["Tipo_Prenda"]]  || "",
      ref_proveedor: row[dIdx["Ref_Proveedor"]] || ""
    };
  }

  // --- 4. Calcular subtotales ---
  const lineas        = body.lineas || [];
  let   subtotal_cop  = 0;   // se mantiene solo como referencia interna de costo/margen
  let   subtotal_gtq  = 0;   // FIX: fuente real del total cobrado al cliente
  const descuento_cop = Number(body.descuento_cop) || 0;

  lineas.forEach(l => {
    const cantidad = Number(l.cantidad) || 1;
    subtotal_cop += (precioMap[l.id_producto] || 0) * cantidad;
    subtotal_gtq += (precioMapGTQ[l.id_producto] || 0) * cantidad;
  });

  const total_cop = subtotal_cop - descuento_cop;

  // Descuento real, en GTQ (la moneda que se cobra). Si el front no
  // manda nada, no hay descuento.
  const descuento_gtq = Math.round((Number(body.descuento_gtq) || 0) * 100) / 100;

  // --- 5. Lookup zona y costo de envío ---
  const zonasData = ss.getSheetByName("DIM_ZONAS_ENVIO").getDataRange().getValues();
  let id_zona     = "";
  let costo_envio = 0;
  const zona_gt   = body.zona_gt || "";

  for (let r = 1; r < zonasData.length; r++) {
    const barrios = String(zonasData[r][2]).toLowerCase();
    if (barrios.indexOf(zona_gt.toLowerCase()) > -1 || zona_gt === zonasData[r][0]) {
      id_zona     = zonasData[r][0];
      costo_envio = zonasData[r][3];
      break;
    }
  }

  // --- 5b. Envío gratis (Jul 2026) ---
  // Umbral se compara contra subtotal_gtq ANTES de descuento/cupón,
  // igual para Orkia y Nudo (UMBRAL_ENVIO_GRATIS_GTQ). costo_envio
  // (el precio estandar de la zona) se guarda SIEMPRE en su columna
  // propia de FACT_PEDIDOS, aunque sea gratis, para que quede registro
  // contable de cuanto hubiera costado. Lo que cambia es si ese monto
  // se suma o no a total_gtq.
  const envio_gratis        = subtotal_gtq >= UMBRAL_ENVIO_GRATIS_GTQ;
  const costo_envio_cobrado = envio_gratis ? 0 : costo_envio;

  const total_gtq = Math.round((subtotal_gtq - descuento_gtq + costo_envio_cobrado) * 100) / 100;

  // --- 6. Escribir FACT_PEDIDOS ---
  pedidosSheet.appendRow([
    id_pedido,
    _fecha(),
    id_cliente,
    _sanitizar(body.nombre_cliente || ""),
    body.telefono       || "",
    body.ciudad         || "Guatemala City",
    zona_gt,
    _sanitizar(body.colonia || ""),
    _sanitizar(body.direccion || ""),
    _sanitizar(body.referencias || ""),
    body.nse_inferido   || "",
    id_zona,
    costo_envio,
    body.banco          || "",
    body.metodo_pago    || "",
    "Pendiente pago",
    subtotal_cop,
    descuento_cop,
    total_cop,
    descuento_gtq,   // FIX (Jul 2026 v3): antes esta columna guardaba la constante
                     // TASA_COP_GTQ (igual en todas las filas, no aportaba nada por
                     // pedido). Ahora guarda el descuento real en GTQ de este pedido.
                     // Requiere renombrar el encabezado de esta columna en el Sheet
                     // (Orkia y Nudo) de "Tasa_Cop_Gtq" a "Descuento_GTQ" — es un
                     // cambio de nombre nada mas, no mueve ninguna columna.
    total_gtq,
    body.codigo_descuento || "",
    body.comprobante === "Si",   // FIX: antes escribia "false" fijo sin importar lo que mandaba el front
    _sanitizar(body.notas || ""),
    body.motivo_compra  || "",
    body.perfil_decision || "",
    body.canal_origen   || "",
    body.edad_inferida  || "",   // FIX: se capturaba en el front pero nunca se guardaba
    body.mes_cumpleanos || "",   // FIX: se capturaba en el front pero nunca se guardaba
    envio_gratis                 // NUEVO (Jul 2026): columna al final. TRUE = se aplico envio
                                  // gratis por umbral y costo_envio NO esta sumado en total_gtq;
                                  // FALSE = costo_envio SI esta sumado en total_gtq.
                                  // Requiere agregar el encabezado "Envio_Gratis" como ULTIMA
                                  // columna de FACT_PEDIDOS en ambos Sheets (Orkia y Nudo)
                                  // antes de desplegar este cambio.
  ]);

  // --- 7. Escribir FACT_LINEAS_PEDIDO ---
  const lineasSheet = ss.getSheetByName("FACT_LINEAS_PEDIDO");

  const rowsLineas = lineas.map((linea, i) => {
    const id_linea = id_pedido + "-L" + String(i + 1).padStart(2, "0");
    const d        = dim_dict[linea.id_producto] || {};
    const precio   = precioMap[linea.id_producto] || 0;
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
    ok:               true,
    id_pedido:        id_pedido,
    id_cliente:       id_cliente,
    es_nuevo:         es_nuevo,
    subtotal_cop:     subtotal_cop,
    descuento_cop:    descuento_cop,
    total_cop:        total_cop,
    subtotal_gtq:     subtotal_gtq,
    descuento_gtq:    descuento_gtq,
    costo_envio_gtq:  costo_envio,      // precio estandar de la zona (siempre, aunque sea gratis)
    envio_gratis:     envio_gratis,
    total_gtq:        total_gtq,        // ya incluye costo_envio si no aplico envio gratis
    lineas:           lineas.length
  };
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
