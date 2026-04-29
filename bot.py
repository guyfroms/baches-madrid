import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client, Client
import httpx

# ── Configuración ──────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8664330814:AAF8Kkjf0zmI10pfXywfU_3KcHoHhcyD0sg")
SUPABASE_URL   = os.environ.get("SUPABASE_URL",   "https://poeobeskktdylyrnbaal.supabase.co")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY",   "sb_publishable_01_oeMFCtjqZErEoXWg-VA_U7xGymVW")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.basicConfig(level=logging.INFO)

# ── /start ──────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy el bot de *Baches Madrid*.\n\n"
        "📸 Envíame una foto de un bache u otro problema en la vía pública "
        "*adjuntando tu ubicación* y lo añadiré al mapa.\n\n"
        "¿Cómo adjuntar ubicación?\n"
        "1. Pulsa el clip 📎\n"
        "2. Elige 'Ubicación'\n"
        "3. Envía la ubicación\n"
        "4. Luego envía la foto con un mensaje describiendo el problema.",
        parse_mode="Markdown"
    )

# ── Guardar ubicación temporal por usuario ──────────────────────
ubicaciones_temp = {}

async def recibir_ubicacion(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    loc = update.message.location
    ubicaciones_temp[user_id] = {"lat": loc.latitude, "lon": loc.longitude}
    await update.message.reply_text(
        "📍 Ubicación recibida. Ahora envíame la foto del problema con una descripción."
    )

# ── Recibir foto ────────────────────────────────────────────────
async def recibir_foto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or str(user_id)

    if user_id not in ubicaciones_temp:
        await update.message.reply_text(
            "⚠️ Primero envíame tu *ubicación* y luego la foto.\n\n"
            "Pulsa el clip 📎 → Ubicación.",
            parse_mode="Markdown"
        )
        return

    loc = ubicaciones_temp.pop(user_id)
    descripcion = update.message.caption or "Sin descripción"

    # Descargar foto de Telegram
    foto = update.message.photo[-1]
    file = await ctx.bot.get_file(foto.file_id)
    foto_bytes = await file.download_as_bytearray()

    # Subir foto a Supabase Storage
    filename = f"{user_id}_{foto.file_id}.jpg"
    try:
        supabase.storage.from_("fotos").upload(
            filename,
            bytes(foto_bytes),
            {"content-type": "image/jpeg"}
        )
        foto_url = f"{SUPABASE_URL}/storage/v1/object/public/fotos/{filename}"
    except Exception as e:
        logging.error(f"Error subiendo foto: {e}")
        foto_url = None

    # Guardar en base de datos
    supabase.table("baches").insert({
        "foto_url":          foto_url,
        "latitud":           loc["lat"],
        "longitud":          loc["lon"],
        "descripcion":       descripcion,
        "usuario_telegram":  username,
        "confirmaciones":    0,
    }).execute()

    await update.message.reply_text(
        "✅ ¡Reporte añadido al mapa! Gracias por contribuir a mejorar Madrid 🗺️"
    )

# ── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, recibir_ubicacion))
    app.add_handler(MessageHandler(filters.PHOTO, recibir_foto))
    print("🤖 Bot arrancado...")
    app.run_polling()
