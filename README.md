#!/usr/bin/env python3
"""
Scraper de noticias de seguridad — Google News RSS
Elecciones Presidenciales Colombia 2026 · Mercado Libre

Estrategia: consulta Google News RSS con múltiples queries amplios, deduplica,
filtra por antigüedad (últimas 24 horas) y actualiza el campo "novedades_recientes"
de seguridad.json.

NO clasifica gravedad — solo trae las más recientes. La curación humana decide qué es
realmente importante. El script preserva las novedades pre-existentes si son recientes.
"""
import json
import re
import sys
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET
import hashlib

# ============================================================
# CONFIGURACIÓN
# ============================================================
ROOT_DIR      = Path(__file__).resolve().parent.parent
SEGURIDAD_PATH = ROOT_DIR / "seguridad.json"
LOG_DIR       = ROOT_DIR / "logs"
LOG_FILE      = LOG_DIR / "news_scrape.log"

# Queries amplios — cubren violencia electoral, orden público, logística, etc.
# Google News interpreta espacios como AND y comillas como frases exactas.
QUERIES = [
    'violencia electoral Colombia',
    'atentado candidato Colombia 2026',
    'amenaza candidato presidencial Colombia',
    'asesinato lider social Colombia',
    'paro armado Colombia',
    'orden publico Colombia elecciones',
    'bloqueo via Colombia',
    'disturbios Colombia 2026',
    'MOE alerta electoral Colombia',
    'masacre Colombia 2026',
    'ataque ELN disidencias Colombia',
    'seguridad elecciones Colombia',
    'Registraduria noticia Colombia',
    'Cepeda Espriella incidente',
    'Defensoria Pueblo alerta temprana Colombia',
    'protesta Colombia ultima hora',
]

# Filtro de gravedad — palabras clave que marcamos como "potencialmente graves"
# para destacarlas. NO descartamos las que no tienen estas palabras, solo las marcamos.
PALABRAS_GRAVES = [
    'muerto', 'muerte', 'asesinato', 'atentado', 'masacre',
    'homicidio', 'mata', 'asesinad', 'fallec',
    'herido', 'heridos', 'hospital', 'critico',
    'bomba', 'explosion', 'tiroteo', 'disparos', 'ataque',
    'secuestro', 'amenaza', 'extorsion',
    'paro armado', 'bloqueo', 'enfrentamiento',
    'quemado', 'incendio', 'destrucc',
]

# Tipos para clasificar visualmente en el dashboard
TIPO_MAPEO = [
    ('homicidio',  ['homicidio', 'asesinad', 'mata', 'muerto', 'muerte']),
    ('masacre',    ['masacre', 'multiple victimas']),
    ('atentado',   ['atentado', 'bomba', 'explosion', 'tiroteo']),
    ('amenazas',   ['amenaza', 'extorsion', 'secuestro']),
    ('agresión',   ['agresion', 'agredido', 'herido', 'golpiza', 'ataque']),
    ('vandalismo', ['vandalismo', 'vandalizad', 'destrozo', 'destruccion', 'quema']),
    ('protesta',   ['protesta', 'manifestacion', 'paro', 'bloqueo', 'marcha']),
    ('orden_publico', ['enfrentamiento', 'disturbio', 'choque', 'desorden']),
]

USER_AGENT  = "Mozilla/5.0 (compatible; MELI-NewsScraper/1.0)"
TIMEOUT_SEG = 15
HORAS_VENTANA = 24            # Considera noticias de las últimas N horas
MAX_NOVEDADES = 8             # Máximo de novedades a mostrar en el dashboard
MIN_PER_QUERY = 5             # Cuántos items por query

# ============================================================
# LOGGING
# ============================================================
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


# ============================================================
# GOOGLE NEWS RSS
# ============================================================
def build_url(query):
    """Construye URL de Google News RSS para Colombia, español."""
    q = quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=CO&ceid=CO:es-419"


def fetch_xml(url):
    """Descarga XML del feed RSS."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=TIMEOUT_SEG) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8", errors="replace")
    except (URLError, HTTPError, Exception) as e:
        log.warning(f"  Error fetch {url[:80]}...: {type(e).__name__}: {e}")
    return None


def parse_feed(xml_text):
    """Extrae items del feed RSS. Retorna lista de dicts."""
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.warning(f"  Error parseando XML: {e}")
        return []

    items = []
    for item in root.iter('item'):
        try:
            title       = item.findtext('title', '').strip()
            link        = item.findtext('link', '').strip()
            pub_date_s  = item.findtext('pubDate', '').strip()
            description = item.findtext('description', '').strip()
            source_el   = item.find('source')
            source_name = source_el.text.strip() if source_el is not None and source_el.text else ''

            # Parsear fecha
            try:
                from email.utils import parsedate_to_datetime
                pub_date = parsedate_to_datetime(pub_date_s)
            except Exception:
                pub_date = datetime.now(timezone.utc)

            items.append({
                'title':       title,
                'link':        link,
                'pub_date':    pub_date,
                'description': description,
                'source':      source_name,
            })
        except Exception as e:
            log.warning(f"  Error parseando item: {e}")
            continue
    return items


# ============================================================
# DEDUPLICACIÓN Y CLASIFICACIÓN
# ============================================================
def normalizar(texto):
    """Lowercase y sin tildes para comparar."""
    t = texto.lower()
    reemplazos = {'á':'a','é':'e','í':'i','ó':'o','ú':'u','ñ':'n'}
    for k, v in reemplazos.items():
        t = t.replace(k, v)
    return t


def hash_titulo(titulo):
    """Hash del título normalizado para deduplicar."""
    t = normalizar(titulo)
    t = re.sub(r'[^a-z0-9 ]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return hashlib.md5(t.encode()).hexdigest()[:12]


def detectar_tipo(titulo, descripcion):
    """Clasifica el tipo de novedad según palabras clave."""
    texto = normalizar(titulo + ' ' + descripcion)
    for tipo, palabras in TIPO_MAPEO:
        for p in palabras:
            if p in texto:
                return tipo
    return 'orden_publico'  # default genérico


def es_grave(titulo, descripcion):
    """¿La noticia tiene palabras de alta gravedad?"""
    texto = normalizar(titulo + ' ' + descripcion)
    return any(p in texto for p in PALABRAS_GRAVES)


def extraer_lugar(titulo, descripcion):
    """
    Intenta extraer un lugar (ciudad/depto) de la noticia.
    Heurística: busca nombres conocidos en el texto.
    """
    texto = titulo + ' ' + descripcion
    departamentos = [
        'Bogotá', 'Antioquia', 'Medellín', 'Cundinamarca', 'Valle', 'Cali',
        'Atlántico', 'Barranquilla', 'Bolívar', 'Cartagena', 'Magdalena',
        'Santa Marta', 'Córdoba', 'Montería', 'Sucre', 'Cesar', 'La Guajira',
        'Norte de Santander', 'Cúcuta', 'Catatumbo', 'Santander', 'Bucaramanga',
        'Boyacá', 'Tunja', 'Tolima', 'Ibagué', 'Huila', 'Neiva', 'Caldas',
        'Manizales', 'Risaralda', 'Pereira', 'Quindío', 'Armenia', 'Nariño',
        'Pasto', 'Tumaco', 'Cauca', 'Popayán', 'Chocó', 'Quibdó', 'Meta',
        'Villavicencio', 'Casanare', 'Yopal', 'Arauca', 'Putumayo', 'Caquetá',
        'Florencia', 'Amazonas', 'Vichada', 'Guaviare', 'Vaupés', 'Guainía',
        'San Andrés',
    ]
    encontrados = []
    for lugar in departamentos:
        if lugar in texto:
            encontrados.append(lugar)
    if encontrados:
        return ', '.join(encontrados[:2])
    return 'Colombia'


# ============================================================
# PROCESO PRINCIPAL
# ============================================================
def cargar_seguridad():
    try:
        with open(SEGURIDAD_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log.error(f"No se pudo cargar {SEGURIDAD_PATH}")
        return None


def guardar_seguridad(datos):
    with open(SEGURIDAD_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def main():
    log.info("=" * 60)
    log.info(f"INICIO scrape noticias — {datetime.now().isoformat()}")
    log.info("=" * 60)

    # 1) Recolectar de todos los queries
    todas_noticias = []
    vistos = set()  # hashes de títulos

    for query in QUERIES:
        log.info(f"Query: '{query}'")
        url = build_url(query)
        xml_text = fetch_xml(url)
        items = parse_feed(xml_text)
        log.info(f"  → {len(items)} items recibidos")

        for item in items[:MIN_PER_QUERY]:
            h = hash_titulo(item['title'])
            if h in vistos:
                continue
            vistos.add(h)
            todas_noticias.append(item)

    log.info(f"Total únicas después de dedup: {len(todas_noticias)}")

    # 2) Filtrar por ventana de tiempo
    ahora = datetime.now(timezone.utc)
    limite = ahora - timedelta(hours=HORAS_VENTANA)
    recientes = [n for n in todas_noticias if n['pub_date'] >= limite]
    log.info(f"Recientes (últimas {HORAS_VENTANA}h): {len(recientes)}")

    # 3) Ordenar: graves primero, luego más recientes
    recientes.sort(key=lambda n: (
        not es_grave(n['title'], n['description']),  # graves primero
        -(n['pub_date'].timestamp())                 # más recientes primero
    ))

    # 4) Formatear para el dashboard
    novedades_nuevas = []
    for n in recientes[:MAX_NOVEDADES]:
        tipo = detectar_tipo(n['title'], n['description'])
        lugar = extraer_lugar(n['title'], n['description'])

        # Limpiar descripción (a veces viene con HTML)
        desc_limpia = re.sub(r'<[^>]+>', '', n['description'])
        # Limpiar entities HTML
        import html
        desc_limpia = html.unescape(desc_limpia)
        desc_limpia = desc_limpia.replace('\xa0', ' ').replace('\u00a0', ' ')
        desc_limpia = re.sub(r'\s+', ' ', desc_limpia).strip()
        # Quitar "Por SOURCE" o " SOURCE" al final que mete Google News
        desc_limpia = re.sub(r'\s+' + re.escape(n.get('source','xxxxxxxxxxxx')) + r'$', '', desc_limpia)
        if len(desc_limpia) > 200:
            desc_limpia = desc_limpia[:197] + '...'

        # Limpiar también el título
        titulo_limpio = html.unescape(n['title'])
        titulo_limpio = titulo_limpio.replace('\xa0', ' ')
        titulo_limpio = re.sub(r'\s+', ' ', titulo_limpio).strip()
        # Quitar "- Fuente" al final
        if n.get('source'):
            titulo_limpio = re.sub(r'\s*-\s*' + re.escape(n['source']) + r'$', '', titulo_limpio)

        # Si no hay descripción útil, usar el título
        if not desc_limpia or len(desc_limpia) < 20:
            desc_limpia = titulo_limpio[:200]

        novedades_nuevas.append({
            'fecha':       n['pub_date'].strftime('%Y-%m-%d'),
            'hora':        n['pub_date'].strftime('%H:%M'),
            'titulo':      titulo_limpio,
            'lugar':       lugar,
            'tipo':        tipo,
            'descripcion': desc_limpia,
            'fuente':      n['source'],
            'url':         n['link'],
            'grave':       es_grave(n['title'], n['description']),
        })

    log.info(f"Novedades finales para dashboard: {len(novedades_nuevas)}")

    if not novedades_nuevas:
        log.warning("⚠ No se encontraron noticias en la ventana. Manteniendo las existentes.")
        return

    # 5) Actualizar seguridad.json
    datos = cargar_seguridad()
    if not datos:
        log.error("No se pudo cargar seguridad.json, abortando.")
        sys.exit(1)

    # Reemplazar novedades_recientes con las nuevas
    datos['novedades_recientes'] = novedades_nuevas

    # Actualizar metadata
    datos['meta']['fecha_actualizacion'] = datetime.now().strftime('%Y-%m-%d')
    datos['meta']['hora_actualizacion']  = datetime.now().strftime('%H:%M')
    datos['meta']['fuente_noticias']     = 'Google News RSS · auto-update cada hora'

    guardar_seguridad(datos)
    log.info(f"✓ {SEGURIDAD_PATH} actualizado")

    # Resumen en log
    log.info("--- Resumen de novedades ---")
    for i, n in enumerate(novedades_nuevas, 1):
        marker = "🔴" if n['grave'] else "  "
        log.info(f"  {marker} {i}. [{n['tipo']:12s}] {n['lugar']:30s} {n['hora']} · {n['descripcion'][:60]}")

    log.info("=" * 60)
    log.info("FIN — éxito")
    log.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception(f"ERROR no manejado: {e}")
        sys.exit(99)
