import logging
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# === SOZLAMALAR ===
BOT_TOKEN = "8918026324:AAG4tFxXsClwj-tf4E62uCPgoakuZEYBC2w"
SPREADSHEET_ID = "1fV735qrjCq8gfagp-_AsMpi4l3LaKtXlUuE6ySr_NgA"
ADMIN_IDS = []  # Admin Telegram ID larini shu yerga yozing: [123456789, 987654321]

# Google Sheets ulanish
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def get_sheet():
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1

# === HOLATLAR ===
ASK_NAME, ASK_PHONE, ASK_GROUP, ASK_TYPE = range(4)

logging.basicConfig(level=logging.INFO)

# === ASOSIY MENYU ===
def main_menu():
    keyboard = [
        [KeyboardButton("📝 Ro'yxatdan o'tish")],
        [KeyboardButton("📊 Mening ma'lumotlarim")],
        [KeyboardButton("📅 Dars jadvali")],
        [KeyboardButton("💰 To'lov holati")],
        [KeyboardButton("📞 Bog'lanish")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_menu():
    keyboard = [
        [KeyboardButton("👥 Barcha o'quvchilar")],
        [KeyboardButton("📈 Statistika")],
        [KeyboardButton("✅ To'lovni tasdiqlash")],
        [KeyboardButton("🔙 Orqaga")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        "🎓 Kurs Boshqaruv Tizimiga xush kelibsiz!\n\n"
        "Quyidagi tugmalardan birini tanlang:"
    )
    await update.message.reply_text(text, reply_markup=main_menu())

# === RO'YXATDAN O'TISH ===
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Ro'yxatdan o'tish\n\n"
        "Ism va familiyangizni kiriting:\n"
        "(Misol: Abdullayev Firdavs)"
    )
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    keyboard = [[KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True)]]
    await update.message.reply_text(
        "📱 Telefon raqamingizni yuboring:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return ASK_PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        context.user_data['phone'] = update.message.contact.phone_number
    else:
        context.user_data['phone'] = update.message.text

    keyboard = [
        [KeyboardButton("Guruh 1 (Dushanba/Chorshanba/Juma)")],
        [KeyboardButton("Guruh 2 (Seshanba/Payshanba/Shanba)")],
        [KeyboardButton("Guruh 3 (Individual)")],
    ]
    await update.message.reply_text(
        "📅 Guruhingizni tanlang:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return ASK_GROUP

async def ask_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['group'] = update.message.text
    keyboard = [
        [KeyboardButton("Online")],
        [KeyboardButton("Offline")],
    ]
    await update.message.reply_text(
        "💻 O'qish turini tanlang:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return ASK_TYPE

async def ask_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['type'] = update.message.text
    user = update.effective_user

    # Google Sheets ga yozish
    try:
        sheet = get_sheet()
        # Oxirgi ID ni olish
        all_rows = sheet.get_all_values()
        next_id = len(all_rows)  # 1-qator header

        from datetime import datetime
        row = [
            next_id,
            context.user_data['name'],
            context.user_data['phone'],
            context.user_data['group'],
            context.user_data['type'],
            datetime.now().strftime("%d.%m.%Y"),
            "",   # Narx
            "0",  # To'langan
            "Yangi",  # Status
            str(user.id)  # Telegram ID (izoh)
        ]
        sheet.append_row(row)
        success = True
    except Exception as e:
        logging.error(f"Sheets xatosi: {e}")
        success = False

    if success:
        text = (
            "✅ Muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
            f"👤 Ism: {context.user_data['name']}\n"
            f"📱 Telefon: {context.user_data['phone']}\n"
            f"📅 Guruh: {context.user_data['group']}\n"
            f"💻 Tur: {context.user_data['type']}\n\n"
            "Administrator tez orada siz bilan bog'lanadi! 📞"
        )
    else:
        text = (
            "✅ Ma'lumotlaringiz qabul qilindi!\n"
            "Administrator tez orada bog'lanadi. 📞"
        )

    await update.message.reply_text(text, reply_markup=main_menu())
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_menu())
    return ConversationHandler.END

# === MENING MA'LUMOTLARIM ===
async def my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        found = None
        for row in rows[1:]:
            if len(row) >= 10 and row[9] == user_id:
                found = row
                break

        if found:
            text = (
                "📊 Sizning ma'lumotlaringiz:\n\n"
                f"👤 Ism: {found[1]}\n"
                f"📱 Telefon: {found[2]}\n"
                f"📅 Guruh: {found[3]}\n"
                f"💻 Tur: {found[4]}\n"
                f"📆 Ro'yxat sanasi: {found[5]}\n"
                f"💰 To'lov: {found[7]} so'm\n"
                f"📌 Status: {found[8]}\n"
            )
        else:
            text = "❗ Siz hali ro'yxatdan o'tmagansiz.\n📝 Ro'yxatdan o'tish tugmasini bosing."
    except Exception as e:
        text = "⚠️ Ma'lumot olishda xatolik yuz berdi. Keyinroq urinib ko'ring."

    await update.message.reply_text(text, reply_markup=main_menu())

# === DARS JADVALI ===
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📅 Dars Jadvali:\n\n"
        "🔵 Guruh 1:\n"
        "   Dushanba, Chorshanba, Juma\n"
        "   🕐 14:00 - 16:00\n\n"
        "🟢 Guruh 2:\n"
        "   Seshanba, Payshanba, Shanba\n"
        "   🕐 14:00 - 16:00\n\n"
        "🟡 Individual:\n"
        "   Kelishuv asosida\n\n"
        "📍 Manzil: [Manzilingizni yozing]\n"
        "🌐 Online: Zoom/Google Meet"
    )
    await update.message.reply_text(text, reply_markup=main_menu())

# === TO'LOV HOLATI ===
async def payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💰 To'lov Ma'lumotlari:\n\n"
        "💳 Karta raqami: [Karta raqamingiz]\n"
        "👤 Karta egasi: [Ism]\n\n"
        "📌 To'lov qilgandan keyin:\n"
        "1. Chek skrinshotini yuboring\n"
        "2. Administrator tasdiqlagach statusingiz yangilanadi\n\n"
        "📞 Savollar uchun: @admin_username"
    )
    await update.message.reply_text(text, reply_markup=main_menu())

# === BOG'LANISH ===
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📞 Bog'lanish:\n\n"
        "👤 Administrator: @admin_username\n"
        "📱 Telefon: +998 XX XXX XX XX\n"
        "⏰ Ish vaqti: 9:00 - 18:00\n\n"
        "📍 Manzil: [Manzilingiz]"
    )
    await update.message.reply_text(text, reply_markup=main_menu())

# === ADMIN PANEL ===
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return

    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        count = len(rows) - 1  # header ni hisobga olmaslik

        text = (
            "🔧 Admin Panel\n\n"
            f"👥 Jami o'quvchilar: {count}\n\n"
            "Quyidagi buyruqlardan foydalaning:\n"
            "/students - Barcha o'quvchilar ro'yxati\n"
            "/stats - Statistika"
        )
    except:
        text = "🔧 Admin Panel\n\n/students - O'quvchilar\n/stats - Statistika"

    await update.message.reply_text(text, reply_markup=admin_menu())

async def all_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return

    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        if len(rows) <= 1:
            await update.message.reply_text("📭 Hali o'quvchi yo'q.")
            return

        text = "👥 O'quvchilar ro'yxati:\n\n"
        for i, row in enumerate(rows[1:], 1):
            if len(row) >= 5:
                text += f"{i}. {row[1]} | {row[3]} | {row[8] if len(row)>8 else 'Yangi'}\n"
            if i % 20 == 0:
                await update.message.reply_text(text)
                text = ""

        if text:
            await update.message.reply_text(text, reply_markup=admin_menu())
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {e}")

# === ASOSIY ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Ro'yxatdan o'tish conversation
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Ro'yxatdan o'tish$"), register_start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, ask_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)
            ],
            ASK_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_group)],
            ASK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_type)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("students", all_students))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("^📊 Mening ma'lumotlarim$"), my_info))
    app.add_handler(MessageHandler(filters.Regex("^📅 Dars jadvali$"), schedule))
    app.add_handler(MessageHandler(filters.Regex("^💰 To'lov holati$"), payment))
    app.add_handler(MessageHandler(filters.Regex("^📞 Bog'lanish$"), contact))
    app.add_handler(MessageHandler(filters.Regex("^👥 Barcha o'quvchilar$"), all_students))

    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
