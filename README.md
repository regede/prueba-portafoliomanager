# Mi Portafolio de Inversión — Versión Vercel

Dashboard de portafolio personal con precios en vivo vía yfinance (sin CORS).

## Estructura del proyecto

```
portafolio-web/
├── api/
│   └── precios.py      ← Serverless function: obtiene precios con yfinance
├── index.html          ← Dashboard (edita solo el bloque CONFIG)
├── vercel.json         ← Configuración de rutas para Vercel
└── requirements.txt    ← Dependencias Python del backend
```

---

## Cómo hacer el deploy en Vercel (5 minutos)

### Requisitos previos
- Cuenta gratuita en [vercel.com](https://vercel.com) (puedes entrar con GitHub/GitLab/Bitbucket)
- Git instalado en tu computadora

### Paso 1 — Sube el proyecto a GitHub

1. Ve a [github.com/new](https://github.com/new) y crea un repositorio nuevo (puede ser privado)
2. En tu computadora, abre una terminal en la carpeta `portafolio-web/` y ejecuta:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

### Paso 2 — Conecta el repo a Vercel

1. Entra a [vercel.com/new](https://vercel.com/new)
2. Haz clic en **"Import Git Repository"** y selecciona tu repo
3. En la configuración del proyecto:
   - **Framework Preset**: `Other`
   - El resto déjalo en defaults
4. Haz clic en **"Deploy"**

Vercel detecta automáticamente `api/precios.py` y lo convierte en una serverless function.

### Paso 3 — Personaliza tu portafolio

Edita `index.html` — solo el bloque `CONFIG` al inicio del `<script>`:

- Cambia `titulo` con el nombre de tu dashboard
- Llena `posiciones_usd` y `posiciones_mxn` con tus posiciones reales
- Actualiza `fallback.precios` con precios recientes (se usan si el servidor falla)
- Haz commit y push — Vercel redespliega automáticamente en segundos

Tu URL será algo como `https://mi-portafolio.vercel.app`.

---

## Desarrollo local

Si quieres probar localmente antes de subir a Vercel:

```bash
npm install -g vercel      # instalar Vercel CLI (solo una vez)
pip install yfinance pandas # instalar dependencias Python
vercel dev                  # levanta servidor en http://localhost:3000
```

Con `vercel dev`, el endpoint `/api/precios` funciona igual que en producción.

---

## Notas

- **Precios**: usa Yahoo Finance vía yfinance (gratis, sin API key). Los precios se obtienen server-side, sin problemas de CORS.
- **Tipo de cambio**: también viene del backend (ticker `MXN=X` de Yahoo Finance).
- **Caché**: el dashboard cachea los precios en `localStorage` cuando el mercado está cerrado, para no hacer llamadas innecesarias.
- **SIC**: acciones marcadas con `sic_usd: true` se cotizan en USD y se convierten a MXN automáticamente con el T/C del servidor.
