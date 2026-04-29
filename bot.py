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

# ── Estado temporal por usuario ─────────────────────────────────
# { user_id: { "foto_id": ..., "foto_bytes": ..., "descripcion": ... } }
fotos_temp = {}

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
    loc = update.message.location

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
        "latitud":          loc.latitude,
        "longitud":         loc.longitude,
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
    app.add_handler(MessageHandler(filters.LOCATION, recibir_ubicacion))
    app.run_polling()
