# 🕳️ Baches Madrid

Mapa colaborativo de baches y problemas en vías públicas de Madrid.

## Archivos

- `bot.py` — Bot de Telegram que recibe fotos con ubicación
- `requirements.txt` — Dependencias Python
- `index.html` — Página web con el mapa
- `Procfile` — Instrucciones para Railway

## Despliegue

### 1. Crear bucket de fotos en Supabase
- Ve a Supabase → Storage → New bucket
- Nombre: `fotos`
- Public bucket: ✅ activado

### 2. Subir código a GitHub
- Crea un repositorio nuevo en GitHub
- Sube todos estos archivos

### 3. Desplegar bot en Railway
- Ve a https://railway.app
- New Project → Deploy from GitHub repo
- Selecciona tu repositorio
- El bot arrancará automáticamente

### 4. Publicar página web en GitHub Pages
- En tu repositorio GitHub → Settings → Pages
- Source: main branch → / (root)
- Tu web estará en: https://tuusuario.github.io/baches-madrid
