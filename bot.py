import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client, Client

# ── Configuración ──────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.basicConfig(level=logging.INFO)

# ── /start ──────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy el bot de *Baches Madrid*.\n\n"
        "📸 Envíame una *foto* del bache o problema, con una descripción como pie de foto.\n\n"
        "Después te pediré la ubicación.",
        parse_mode="Markdown"
    )

# ── Recibir foto primero ────────────────────────────────────────
async def recibir_foto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    descripcion = update.message.caption or "Sin descripción"

    # Descargar y subir foto a Supabase Storage
    foto = update.message.photo[-1]
    file = await ctx.bot.get_file(foto.file_id)
    foto_bytes = await file.download_as_bytearray()

    filename = f"temp_{user_id}.jpg"
    try:
        # Borrar si ya existe una foto pendiente de este usuario
        supabase.storage.from_("fotos").remove([filename])
    except:
        pass

    try:
        supabase.storage.from_("fotos").upload(
            filename,
            bytes(foto_bytes),
            {"content-type": "image/jpeg"}
        )
        foto_url = f"{SUPABASE_URL}/storage/v1/object/public/fotos/{filename}"
    except Exception as e:
        logging.error(f"Error subiendo foto: {e}")
        await update.message.reply_text("❌ Error subiendo la foto, inténtalo de nuevo.")
        return

    # Guardar en tabla pendientes
    supabase.table("fotos_pendientes").upsert({
        "user_id":     user_id,
        "foto_url":    foto_url,
        "descripcion": descripcion,
    }).execute()

    # Pedir ubicación con botón nativo
    boton = KeyboardButton("📍 Enviar mi ubicación", request_location=True)
    teclado = ReplyKeyboardMarkup([[boton]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "✅ Foto recibida. Ahora pulsa el botón para enviar tu ubicación:",
        reply_markup=teclado
    )

# ── Recibir ubicación y guardar todo ───────────────────────────
async def recibir_ubicacion(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or str(user_id)

    # Recuperar foto pendiente de Supabase
    resultado = supabase.table("fotos_pendientes").select("*").eq("user_id", user_id).execute()

    if not resultado.data:
        await update.message.reply_text(
            "⚠️ Primero envíame una *foto* del problema.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    datos = resultado.data[0]

    # Borrar de pendientes
    supabase.table("fotos_pendientes").delete().eq("user_id", user_id).execute()

    # Obtener coordenadas
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
    elif update.message.venue:
        lat = update.message.venue.location.latitude
        lon = update.message.venue.location.longitude
    else:
        await update.message.reply_text("⚠️ No pude leer la ubicación, inténtalo de nuevo.")
        return

    # Renombrar foto de temp_ a definitiva
    foto_url_final = datos["foto_url"].replace(f"temp_{user_id}.jpg", f"bache_{user_id}_{int(lat*1000)}.jpg")
    try:
        supabase.storage.from_("fotos").move(
            f"temp_{user_id}.jpg",
            f"bache_{user_id}_{int(lat*1000)}.jpg"
        )
    except:
        foto_url_final = datos["foto_url"]  # usar la url temp si falla el rename

    # Guardar en base de datos
    supabase.table("baches").insert({
        "foto_url":         foto_url_final,
        "latitud":          lat,
        "longitud":         lon,
        "descripcion":      datos["descripcion"],
        "usuario_telegram": username,
        "confirmaciones":   0,
    }).execute()

    await update.message.reply_text(
        "✅ ¡Reporte añadido al mapa! Gracias por contribuir a mejorar Madrid 🗺️",
        reply_markup=ReplyKeyboardRemove()
    )

# ── Servidor keep-alive (evita que Render duerma el bot) ────────
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot activo")
    def log_message(self, *args):
        pass

def arrancar_servidor():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAlive)
    server.serve_forever()

# ── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    t = threading.Thread(target=arrancar_servidor, daemon=True)
    t.start()

    print("🤖 Bot arrancado...")

    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, recibir_foto))
    app.add_handler(MessageHandler(filters.LOCATION | filters.VENUE, recibir_ubicacion))
    app.run_polling()


# ── /start ──────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy el bot de *Baches Madrid*.\n\n"
        "📸 Envíame una *foto* del bache o problema, con una descripción como pie de foto.\n\n"
        "Después te pediré la ubicación.",
        parse_mode="Markdown"
    )

# ── Recibir foto primero ────────────────────────────────────────
async def recibir_foto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    descripcion = update.message.caption or "Sin descripción"

    # Guardar foto temporalmente
    foto = update.message.photo[-1]
    file = await ctx.bot.get_file(foto.file_id)
    foto_bytes = await file.download_as_bytearray()

    fotos_temp[user_id] = {
        "foto_id":    foto.file_id,
        "foto_bytes": foto_bytes,
        "descripcion": descripcion,
    }

    # Pedir ubicación con botón nativo
    boton = KeyboardButton("📍 Enviar mi ubicación", request_location=True)
    teclado = ReplyKeyboardMarkup([[boton]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "✅ Foto recibida. Ahora pulsa el botón para enviar tu ubicación:",
        reply_markup=teclado
    )

# ── Recibir ubicación y guardar todo ───────────────────────────
async def recibir_ubicacion(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or str(user_id)

    if user_id not in fotos_temp:
        await update.message.reply_text(
            "⚠️ Primero envíame una *foto* del problema.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    datos = fotos_temp.pop(user_id)

    # Soportar location normal y venue
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
    elif update.message.venue:
        lat = update.message.venue.location.latitude
        lon = update.message.venue.location.longitude
    else:
        await update.message.reply_text("⚠️ No pude leer la ubicación, inténtalo de nuevo.")
        return

    # Subir foto a Supabase Storage
    filename = f"{user_id}_{datos['foto_id']}.jpg"
    try:
        supabase.storage.from_("fotos").upload(
            filename,
            bytes(datos["foto_bytes"]),
            {"content-type": "image/jpeg"}
        )
        foto_url = f"{SUPABASE_URL}/storage/v1/object/public/fotos/{filename}"
    except Exception as e:
        logging.error(f"Error subiendo foto: {e}")
        foto_url = None

    # Guardar en base de datos
    supabase.table("baches").insert({
        "foto_url":         foto_url,
        "latitud":          lat,
        "longitud":         lon,
        "descripcion":      datos["descripcion"],
        "usuario_telegram": username,
        "confirmaciones":   0,
    }).execute()

    await update.message.reply_text(
        "✅ ¡Reporte añadido al mapa! Gracias por contribuir a mejorar Madrid 🗺️",
        reply_markup=ReplyKeyboardRemove()
    )

# ── Servidor keep-alive (evita que Render duerma el bot) ────────
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot activo")
    def log_message(self, *args):
        pass

def arrancar_servidor():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAlive)
    server.serve_forever()

# ── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    t = threading.Thread(target=arrancar_servidor, daemon=True)
    t.start()

    print("🤖 Bot arrancado...")

    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, recibir_foto))
    app.add_handler(MessageHandler(filters.LOCATION | filters.VENUE, recibir_ubicacion))
    app.run_polling()
