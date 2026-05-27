# Dashboard Electoral Colombia 2026 — Mercado Libre

Dashboard de monitoreo electoral con datos cargados desde JSON externo (editable sin tocar el HTML).

## 📁 Estructura de archivos

```
dashboard/
├── index.html      ← El dashboard (no se toca)
├── datos.json      ← Porcentajes, escenarios, departamentos
├── seguridad.json  ← MOE, riesgos, novedades
└── README.md       ← Este archivo
```

## ⚙️ Cómo funciona

1. Abres `index.html` en el navegador.
2. Automáticamente hace `fetch('datos.json')` y `fetch('seguridad.json')`.
3. Repinta porcentajes, podio, cambios vs ayer, mapa, sección de seguridad.
4. Cuando le das al botón **"Actualizar ahora"** vuelve a leer los JSON (con cache-busting `?t=timestamp`).

**Importante:** Si abres el HTML con doble clic (URL tipo `file://...`), tu navegador bloqueará el `fetch()` por seguridad. Hay dos opciones:

### Opción A — Servir local (1 minuto)

```bash
cd dashboard/
python3 -m http.server 8000
# Luego abre http://localhost:8000 en el navegador
```

### Opción B — Subir a servidor (recomendado)

Sube los 3 archivos (`index.html`, `datos.json`, `seguridad.json`) a cualquier servidor web.

---

## ✏️ Cómo actualizar los datos cada día

### Para actualizar porcentajes / podio / cambios vs ayer

Abre `datos.json` con cualquier editor (Notepad, VS Code, Sublime). Modifica los números y guarda. Recarga la página o presiona "Actualizar ahora".

**Campos clave a editar diariamente:**

```json
{
  "meta": {
    "fecha_actualizacion": "2026-05-28",   ← cambiar a la fecha de hoy
    "fuente_principal": "...",              ← describir la fuente
  },
  "primera_vuelta": {
    "candidatos": [
      {
        "id": "cep",
        "porcentaje": 38.5,                 ← actualizar
        "cambio_dia": -0.4,                 ← diferencia con ayer
        "departamentos_lidera": 18          ← cuántos depts gana
      },
      ...
    ]
  },
  "cambios_vs_ayer": [
    {
      "candidato": "Cepeda",
      "delta": -0.4,                        ← cambio numérico
      "direccion": "down",                  ← "up", "down" o "flat"
      "nota": "explicación breve"
    },
    ...
  ]
}
```

### Para actualizar seguridad / novedades

Abre `seguridad.json`. Lo más útil para mantener al día es la sección `novedades_recientes`:

```json
{
  "novedades_recientes": [
    {
      "fecha": "2026-05-28",
      "lugar": "Municipio, Departamento",
      "tipo": "homicidio",   ← homicidio, masacre, agresión, amenazas, vandalismo
      "descripcion": "Texto breve del hecho."
    },
    ...
  ]
}
```

Pon las novedades más recientes arriba. Recomiendo dejar máximo 6-8.

---

## 📡 Fuentes de información

### Intención de voto (datos.json)
- **Wikipedia** — Anexo:Sondeos_de_intención_de_voto_para_las_elecciones_presidenciales_de_Colombia_de_2026 (se actualiza diario por la comunidad)
- **La Silla Vacía Ponderador** — https://www.lasillavacia.com/silla-nacional/ponderador-de-encuestas-presidenciales-2026/
- **Última encuesta autorizada antes de veda:** 24 de mayo de 2026
- **Próximo dato real:** Resultados Registraduría desde la noche del 31 de mayo

### Seguridad (seguridad.json)
- **MOE** — https://moe.org.co/mapa-de-riesgo-por-factores-de-violencia-actualizacion-eleccion-presidencial-2026/
- **Defensoría del Pueblo** — Alertas Tempranas Electorales
- **Asocapitales** — https://www.asocapitales.co
- **Noticias diarias:** El Tiempo, Infobae Colombia, El Espectador

### Resultados oficiales (a partir del 31 may noche)
- **Registraduría Nacional** — https://resultados.registraduria.gov.co
  - Publica boletines cada 30 minutos
  - Datos por departamento y municipio
  - Para esta fase recomiendo cambiar el `fuente_principal` a "Registraduría · Boletín N°XX"

---

## 🔄 Flujo recomendado de actualización

### Hasta el 30 de mayo (veda de encuestas)
- **No hay datos nuevos legalmente publicables.** Solo actualizar `novedades_recientes` con incidentes reportados en prensa.

### 31 de mayo (jornada electoral)
- Desde las 5 PM, la Registraduría empieza a publicar boletines.
- Cada 1-2 horas, abre el boletín, transcribe los porcentajes a `datos.json` y cambia `fuente_principal` a "Registraduría · Boletín N° X · HH:MM".
- Cambia `fase` de `"veda_encuestas"` a `"resultados_oficiales"`.

### 1 al 20 de junio (entre vueltas)
- Vuelven a salir encuestas (la veda termina). Actualizar diario.

### 21 de junio (segunda vuelta)
- Mismo flujo que el 31 de mayo.

---

## 🛡️ Validación de JSON

Antes de guardar `datos.json` o `seguridad.json`, valida que el JSON sea correcto:
- En línea: https://jsonlint.com (pegas el contenido y le das "Validate JSON")
- En terminal: `python3 -c "import json; json.load(open('datos.json'))"` — si no imprime nada, está bien.

**Errores comunes:**
- Coma extra después del último elemento de un array u objeto → error.
- Comillas mal cerradas → error.
- Usar comillas tipográficas (" ") en vez de rectas (" ") → error.

---

## 📞 Soporte

Si el dashboard no carga los datos, abre la consola del navegador (F12 → pestaña "Console") y revisa si hay errores. Los más típicos:

- `Failed to fetch` → estás abriendo con `file://`. Usa `python3 -m http.server 8000`.
- `Unexpected token in JSON` → hay un error de sintaxis en el JSON. Usa JSONLint.
- `404 datos.json` → el archivo no está en la misma carpeta que `index.html`.
