import logging
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from datetime import datetime, date
import json

# === SOZLAMALAR ===
BOT_TOKEN = "8918026324:AAG4tFxXsClwj-tf4E62uCPgoakuZEYBC2w"
SPREADSHEET_ID = "1fV735qrjCq8gfagp-_AsMpi4l3LaKtXlUuE6ySr_NgA"
ADMIN_IDS = [6226188199]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

DAYS_UZ = {
    "Monday": "Dushanba", "Tuesday": "Seshanba", "Wednesday": "Chorshanba",
    "Thursday": "Payshanba", "Friday": "Juma", "Saturday": "Shanba", "Sunday": "Yakshanba"
}

# Conversation states
(STUDENT_NAME, STUDENT_PHONE, STUDENT_GROUP,
 GROUP_NAME, GROUP_DAYS, GROUP_TIME, GROUP_PRICE,
 BROADCAST_MSG, PAYMENT_CHECK,
 ATTENDANCE_GROUP, ATTENDANCE_DATE,
 ADD_ADMIN_STUDENT_NAME, ADD_ADMIN_STUDENT_PHONE, ADD_ADMIN_STUDENT_GROUP) = range(14)

logging.basicConfig(level=logging.INFO)

def get_client():
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds)

def get_or_create_sheet(name):
    client = get_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        return spreadsheet.worksheet(name)
    except:
        sheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
        return sheet

def ensure_headers():
    # Students sheet
    students = get_or_create_sheet("Talabalar")
    if not students.row_values(1):
        students.append_row(["ID", "Ism", "Telefon", "Guruh", "Qo'shilgan sana", "To'lov holati", "Telegram ID", "Status"])
    
    # Groups sheet
    groups = get_or_create_sheet("Guruhlar")
    if not groups.row_values(1):
        groups.append_row(["Guruh nomi", "Dars kunlari", "Vaqt", "Narx", "Yaratilgan sana", "Status"])
    
    # Payments sheet
    payments = get_or_create_sheet("To'lovlar")
    if not payments.row_values(1):
        payments.append_row(["ID", "Talaba", "Guruh", "Miqdor", "Sana", "Holat", "Telegram ID", "Chek fayl ID"])
    
    # Attendance sheet
    attendance = get_or_create_sheet("Davomat")
    if not attendance.row_values(1):
        attendance.append_row(["Sana", "Guruh", "Talaba", "Holat"])

def is_admin(user_id):
    return user_id in ADMIN_IDS

# === MENUS ===
def main_menu_student():
    keyboard = [
        [KeyboardButton("📅 Dars jadvali")],
        [KeyboardButton("💰 To'lov qilish"), KeyboardButton("📊 Mening ma'lumotlarim")],
        [KeyboardButton("📞 Bog'lanish")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def main_menu_admin():
    keyboard = [
        [KeyboardButton("👥 O'quvchilar"), KeyboardButton("📚 Guruhlar")],
        [KeyboardButton("✅ Davomat"), KeyboardButton("💰 To'lovlar")],
        [KeyboardButton("📊 Dashboard"), KeyboardButton("📢 Xabar yuborish")],
        [KeyboardButton("➕ O'quvchi qo'shish"), KeyboardButton("➕ Guruh qo'shish")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ensure_headers()
    except:
        pass
    
    user = update.effective_user
    if is_admin(user.id):
        text = (f"👋 Assalomu alaykum, {user.first_name}!\n\n"
                "🔧 Admin paneliga xush kelibsiz!")
        await update.message.reply_text(text, reply_markup=main_menu_admin())
    else:
        text = (f"👋 Assalomu alaykum, {user.first_name}!\n\n"
                "🎓 Kurs Boshqaruv Tizimiga xush kelibsiz!\n\n"
                "Ro'yxatdan o'tish uchun /register yuboring.")
        await update.message.reply_text(text, reply_markup=main_menu_student())

# === REGISTER ===
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Ismingiz va familiyangizni kiriting:\n(Masalan: Abdullayev Firdavs)")
    return STUDENT_NAME

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reg_name'] = update.message.text
    kb = [[KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True)]]
    await update.message.reply_text("📱 Telefon raqamingizni yuboring:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return STUDENT_PHONE

async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        context.user_data['reg_phone'] = update.message.contact.phone_number
    else:
        context.user_data['reg_phone'] = update.message.text
    
    # Guruhlarni olish
    try:
        groups_sheet = get_or_create_sheet("Guruhlar")
        rows = groups_sheet.get_all_values()[1:]
        active_groups = [r[0] for r in rows if len(r) > 5 and r[5] == "Faol"]
    except:
        active_groups = []
    
    if not active_groups:
        await update.message.reply_text("⚠️ Hozircha guruhlar yo'q. Administrator bilan bog'laning.")
        return ConversationHandler.END
    
    kb = [[KeyboardButton(g)] for g in active_groups]
    await update.message.reply_text("📚 Guruhni tanlang:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return STUDENT_GROUP

async def reg_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reg_group'] = update.message.text
    user = update.effective_user
    
    try:
        students = get_or_create_sheet("Talabalar")
        rows = students.get_all_values()
        next_id = len(rows)
        
        students.append_row([
            next_id,
            context.user_data['reg_name'],
            context.user_data['reg_phone'],
            context.user_data['reg_group'],
            datetime.now().strftime("%d.%m.%Y"),
            "To'lanmagan",
            str(user.id),
            "Faol"
        ])
        
        text = (f"✅ Ro'yxatdan muvaffaqiyatli o'tdingiz!\n\n"
                f"👤 Ism: {context.user_data['reg_name']}\n"
                f"📱 Telefon: {context.user_data['reg_phone']}\n"
                f"📚 Guruh: {context.user_data['reg_group']}\n\n"
                "Administrator tez orada bog'lanadi! 📞")
    except Exception as e:
        text = f"✅ Ma'lumotingiz qabul qilindi! Administrator bog'lanadi."
    
    await update.message.reply_text(text, reply_markup=main_menu_student())
    return ConversationHandler.END

# === DARS JADVALI ===
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        groups_sheet = get_or_create_sheet("Guruhlar")
        rows = groups_sheet.get_all_values()[1:]
        
        today = DAYS_UZ[date.today().strftime("%A")]
        
        text = "📅 Dars Jadvali:\n\n"
        text += f"📆 Bugun: {today}, {date.today().strftime('%d.%m.%Y')}\n\n"
        
        if not rows:
            text += "Hozircha guruhlar yo'q."
        else:
            text += "🔵 Bugungi darslar:\n"
            today_found = False
            for row in rows:
                if len(row) >= 4 and len(row) > 5 and row[5] == "Faol":
                    if today in row[1]:
                        text += f"  • {row[0]} — {row[2]}\n"
                        today_found = True
            if not today_found:
                text += "  Bugun dars yo'q\n"
            
            text += "\n📋 Barcha guruhlar:\n"
            for row in rows:
                if len(row) >= 4 and (len(row) <= 5 or row[5] == "Faol"):
                    text += f"\n🎓 {row[0]}\n"
                    text += f"   📅 Kunlar: {row[1]}\n"
                    text += f"   ⏰ Vaqt: {row[2]}\n"
                    if len(row) > 3 and row[3]:
                        text += f"   💰 Narx: {row[3]} so'm/oy\n"
    except Exception as e:
        text = f"⚠️ Ma'lumot olishda xatolik: {e}"
    
    await update.message.reply_text(text, reply_markup=main_menu_student() if not is_admin(update.effective_user.id) else main_menu_admin())

# === TO'LOV ===
async def payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ("💰 To'lov Ma'lumotlari:\n\n"
            "💳 Karta: [Karta raqamingizni bot.py da o'zgartiring]\n\n"
            "To'lov qilgandan keyin chekni yuboring 👇")
    await update.message.reply_text(text)
    return PAYMENT_CHECK

async def payment_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    try:
        # O'quvchini topish
        students = get_or_create_sheet("Talabalar")
        rows = students.get_all_values()[1:]
        student_row = None
        for i, row in enumerate(rows):
            if len(row) >= 7 and row[6] == str(user.id):
                student_row = (i+2, row)
                break
        
        # To'lovni saqlash
        payments = get_or_create_sheet("To'lovlar")
        pay_rows = payments.get_all_values()
        next_id = len(pay_rows)
        
        file_id = ""
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.document:
            file_id = update.message.document.file_id
        
        student_name = student_row[1][1] if student_row else str(user.id)
        student_group = student_row[1][3] if student_row else ""
        
        payments.append_row([
            next_id,
            student_name,
            student_group,
            "",
            datetime.now().strftime("%d.%m.%Y"),
            "Kutilmoqda",
            str(user.id),
            file_id
        ])
        
        # Adminlarga xabar
        for admin_id in ADMIN_IDS:
            try:
                msg = (f"💰 Yangi to'lov cheki!\n\n"
                       f"👤 O'quvchi: {student_name}\n"
                       f"📚 Guruh: {student_group}\n"
                       f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}\n\n"
                       f"Tasdiqlash uchun /payments buyrug'ini yuboring")
                await context.bot.send_message(admin_id, msg)
                if file_id:
                    if update.message.photo:
                        await context.bot.send_photo(admin_id, file_id)
                    else:
                        await context.bot.send_document(admin_id, file_id)
            except:
                pass
        
        await update.message.reply_text("✅ Chekingiz yuborildi! Administrator tez orada tasdiqlaydi.",
                                         reply_markup=main_menu_student())
    except Exception as e:
        await update.message.reply_text(f"✅ Chekingiz qabul qilindi!", reply_markup=main_menu_student())
    
    return ConversationHandler.END

# === MENING MA'LUMOTLARIM ===
async def my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        students = get_or_create_sheet("Talabalar")
        rows = students.get_all_values()[1:]
        found = None
        for row in rows:
            if len(row) >= 7 and row[6] == str(user.id):
                found = row
                break
        
        if found:
            text = (f"📊 Sizning ma'lumotlaringiz:\n\n"
                    f"👤 Ism: {found[1]}\n"
                    f"📱 Telefon: {found[2]}\n"
                    f"📚 Guruh: {found[3]}\n"
                    f"📆 Qo'shilgan: {found[4]}\n"
                    f"💰 To'lov: {found[5]}\n"
                    f"📌 Status: {found[7] if len(found)>7 else 'Faol'}")
        else:
            text = "❗ Siz hali ro'yxatdan o'tmagansiz.\n/register buyrug'ini yuboring."
    except:
        text = "⚠️ Ma'lumot olishda xatolik."
    
    await update.message.reply_text(text, reply_markup=main_menu_student())

# === ADMIN: GURUH QO'SHISH ===
async def add_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("📚 Yangi guruh nomi kiriting:\n(Masalan: Python-1, English-3)")
    return GROUP_NAME

async def group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['group_name'] = update.message.text
    await update.message.reply_text("📅 Dars kunlarini kiriting:\n(Masalan: Dushanba, Chorshanba, Juma)")
    return GROUP_DAYS

async def group_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['group_days'] = update.message.text
    await update.message.reply_text("⏰ Dars vaqtini kiriting:\n(Masalan: 14:00 - 16:00)")
    return GROUP_TIME

async def group_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['group_time'] = update.message.text
    await update.message.reply_text("💰 Oylik to'lov narxini kiriting (so'mda):\n(Masalan: 500000)")
    return GROUP_PRICE

async def group_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        groups = get_or_create_sheet("Guruhlar")
        groups.append_row([
            context.user_data['group_name'],
            context.user_data['group_days'],
            context.user_data['group_time'],
            update.message.text,
            datetime.now().strftime("%d.%m.%Y"),
            "Faol"
        ])
        text = (f"✅ Guruh qo'shildi!\n\n"
                f"📚 Nom: {context.user_data['group_name']}\n"
                f"📅 Kunlar: {context.user_data['group_days']}\n"
                f"⏰ Vaqt: {context.user_data['group_time']}\n"
                f"💰 Narx: {update.message.text} so'm/oy")
    except Exception as e:
        text = f"❌ Xatolik: {e}"
    
    await update.message.reply_text(text, reply_markup=main_menu_admin())
    return ConversationHandler.END

# === ADMIN: O'QUVCHI QO'SHISH ===
async def add_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("👤 O'quvchi ism-familiyasini kiriting:")
    return ADD_ADMIN_STUDENT_NAME

async def add_student_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_student_name'] = update.message.text
    await update.message.reply_text("📱 Telefon raqamini kiriting:")
    return ADD_ADMIN_STUDENT_PHONE

async def add_student_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_student_phone'] = update.message.text
    
    try:
        groups_sheet = get_or_create_sheet("Guruhlar")
        rows = groups_sheet.get_all_values()[1:]
        active_groups = [r[0] for r in rows if len(r) > 5 and r[5] == "Faol"]
    except:
        active_groups = []
    
    if not active_groups:
        await update.message.reply_text("⚠️ Guruhlar yo'q. Avval guruh qo'shing.")
        return ConversationHandler.END
    
    kb = [[KeyboardButton(g)] for g in active_groups]
    await update.message.reply_text("📚 Guruhni tanlang:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return ADD_ADMIN_STUDENT_GROUP

async def add_student_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        students = get_or_create_sheet("Talabalar")
        rows = students.get_all_values()
        next_id = len(rows)
        
        students.append_row([
            next_id,
            context.user_data['new_student_name'],
            context.user_data['new_student_phone'],
            update.message.text,
            datetime.now().strftime("%d.%m.%Y"),
            "To'lanmagan",
            "",
            "Faol"
        ])
        text = (f"✅ O'quvchi qo'shildi!\n\n"
                f"👤 {context.user_data['new_student_name']}\n"
                f"📱 {context.user_data['new_student_phone']}\n"
                f"📚 {update.message.text}")
    except Exception as e:
        text = f"❌ Xatolik: {e}"
    
    await update.message.reply_text(text, reply_markup=main_menu_admin())
    return ConversationHandler.END

# === ADMIN: O'QUVCHILAR RO'YXATI ===
async def students_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        students = get_or_create_sheet("Talabalar")
        rows = students.get_all_values()[1:]
        
        if not rows:
            await update.message.reply_text("📭 Hali o'quvchi yo'q.", reply_markup=main_menu_admin())
            return
        
        # Guruh bo'yicha guruhlash
        groups = {}
        for row in rows:
            if len(row) >= 4 and (len(row) <= 7 or row[7] == "Faol"):
                g = row[3] if row[3] else "Guruhsiz"
                if g not in groups:
                    groups[g] = []
                groups[g].append(row)
        
        text = f"👥 Jami o'quvchilar: {len(rows)}\n\n"
        for group, students_list in groups.items():
            text += f"📚 {group} ({len(students_list)} o'quvchi):\n"
            for i, s in enumerate(students_list, 1):
                pay_icon = "✅" if len(s) > 5 and s[5] == "To'langan" else "❌"
                text += f"  {i}. {s[1]} | {s[2]} | {pay_icon}\n"
            text += "\n"
            
            if len(text) > 3500:
                await update.message.reply_text(text)
                text = ""
        
        if text:
            await update.message.reply_text(text, reply_markup=main_menu_admin())
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}", reply_markup=main_menu_admin())

# === ADMIN: GURUHLAR ===
async def groups_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        groups_sheet = get_or_create_sheet("Guruhlar")
        rows = groups_sheet.get_all_values()[1:]
        
        if not rows:
            await update.message.reply_text("📭 Hali guruh yo'q.\n➕ Guruh qo'shish tugmasini bosing.", reply_markup=main_menu_admin())
            return
        
        text = "📚 Guruhlar ro'yxati:\n\n"
        for row in rows:
            if len(row) >= 3:
                status = row[5] if len(row) > 5 else "Faol"
                text += f"🎓 {row[0]} — {status}\n"
                text += f"   📅 {row[1]}\n"
                text += f"   ⏰ {row[2]}\n"
                if len(row) > 3 and row[3]:
                    text += f"   💰 {row[3]} so'm/oy\n"
                text += "\n"
        
        await update.message.reply_text(text, reply_markup=main_menu_admin())
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")

# === ADMIN: DASHBOARD ===
async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        students = get_or_create_sheet("Talabalar")
        s_rows = students.get_all_values()[1:]
        
        groups_sheet = get_or_create_sheet("Guruhlar")
        g_rows = groups_sheet.get_all_values()[1:]
        
        payments = get_or_create_sheet("To'lovlar")
        p_rows = payments.get_all_values()[1:]
        
        total_students = len([r for r in s_rows if len(r) > 7 and r[7] == "Faol"])
        total_groups = len([r for r in g_rows if len(r) > 5 and r[5] == "Faol"])
        paid = len([r for r in s_rows if len(r) > 5 and r[5] == "To'langan"])
        unpaid = total_students - paid
        pending_payments = len([r for r in p_rows if len(r) > 5 and r[5] == "Kutilmoqda"])
        
        today = DAYS_UZ[date.today().strftime("%A")]
        today_groups = [r[0] for r in g_rows if len(r) > 1 and today in r[1] and (len(r) <= 5 or r[5] == "Faol")]
        
        text = (f"📊 DASHBOARD\n"
                f"📅 {date.today().strftime('%d.%m.%Y')} — {today}\n\n"
                f"👥 Jami o'quvchilar: {total_students}\n"
                f"📚 Faol guruhlar: {total_groups}\n"
                f"✅ To'lagan: {paid}\n"
                f"❌ To'lamagan: {unpaid}\n"
                f"⏳ Kutilayotgan to'lovlar: {pending_payments}\n\n"
                f"📅 Bugungi darslar ({today}):\n")
        
        if today_groups:
            for g in today_groups:
                text += f"  • {g}\n"
        else:
            text += "  Bugun dars yo'q\n"
    except Exception as e:
        text = f"❌ Xatolik: {e}"
    
    await update.message.reply_text(text, reply_markup=main_menu_admin())

# === ADMIN: TO'LOVLAR ===
async def payments_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        payments = get_or_create_sheet("To'lovlar")
        rows = payments.get_all_values()[1:]
        
        pending = [r for r in rows if len(r) > 5 and r[5] == "Kutilmoqda"]
        
        if not pending:
            await update.message.reply_text("✅ Kutilayotgan to'lov yo'q.", reply_markup=main_menu_admin())
            return
        
        text = f"💰 Kutilayotgan to'lovlar: {len(pending)}\n\n"
        
        for i, row in enumerate(pending, 1):
            text += f"{i}. {row[1]} | {row[3]} | {row[4]}\n"
        
        text += "\nTasdiqlash uchun: /confirm_[raqam]\nMasalan: /confirm_1"
        
        await update.message.reply_text(text, reply_markup=main_menu_admin())
        
        # Chekli to'lovlar inline tugmalar bilan
        for row in pending:
            if len(row) > 7 and row[7]:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_confirm_{row[0]}_{row[6]}"),
                     InlineKeyboardButton("❌ Rad etish", callback_data=f"pay_reject_{row[0]}_{row[6]}")]
                ])
                caption = f"👤 {row[1]}\n📚 {row[2]}\n📅 {row[4]}"
                try:
                    await context.bot.send_photo(update.effective_chat.id, row[7], caption=caption, reply_markup=kb)
                except:
                    try:
                        await context.bot.send_document(update.effective_chat.id, row[7], caption=caption, reply_markup=kb)
                    except:
                        pass
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    action = data[1]  # confirm yoki reject
    pay_id = data[2]
    student_tg_id = data[3] if len(data) > 3 else ""
    
    try:
        payments = get_or_create_sheet("To'lovlar")
        rows = payments.get_all_values()
        
        for i, row in enumerate(rows[1:], 2):
            if str(row[0]) == pay_id:
                if action == "confirm":
                    payments.update_cell(i, 6, "To'langan")
                    
                    # Talabalar sheetida ham yangilash
                    if student_tg_id:
                        students = get_or_create_sheet("Talabalar")
                        s_rows = students.get_all_values()
                        for j, s_row in enumerate(s_rows[1:], 2):
                            if len(s_row) >= 7 and s_row[6] == student_tg_id:
                                students.update_cell(j, 6, "To'langan")
                                break
                    
                    # O'quvchiga xabar
                    if student_tg_id:
                        try:
                            await context.bot.send_message(int(student_tg_id), 
                                "✅ To'lovingiz tasdiqlandi! Rahmat! 🎉")
                        except:
                            pass
                    
                    await query.edit_message_caption("✅ TO'LOV TASDIQLANDI")
                else:
                    payments.update_cell(i, 6, "Rad etilgan")
                    if student_tg_id:
                        try:
                            await context.bot.send_message(int(student_tg_id),
                                "❌ To'lovingiz tasdiqlanmadi. Administrator bilan bog'laning.")
                        except:
                            pass
                    await query.edit_message_caption("❌ TO'LOV RAD ETILDI")
                break
    except Exception as e:
        await query.edit_message_caption(f"Xatolik: {e}")

# === ADMIN: DAVOMAT ===
async def attendance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    
    try:
        groups_sheet = get_or_create_sheet("Guruhlar")
        rows = groups_sheet.get_all_values()[1:]
        active_groups = [r[0] for r in rows if len(r) > 5 and r[5] == "Faol"]
    except:
        active_groups = []
    
    if not active_groups:
        await update.message.reply_text("Guruhlar yo'q.")
        return ConversationHandler.END
    
    kb = [[KeyboardButton(g)] for g in active_groups]
    await update.message.reply_text("📚 Davomat uchun guruhni tanlang:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return ATTENDANCE_GROUP

async def attendance_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['att_group'] = update.message.text
    
    try:
        students = get_or_create_sheet("Talabalar")
        rows = students.get_all_values()[1:]
        group_students = [r for r in rows if len(r) >= 4 and r[3] == context.user_data['att_group'] and (len(r) <= 7 or r[7] == "Faol")]
        
        if not group_students:
            await update.message.reply_text("Bu guruhda o'quvchi yo'q.", reply_markup=main_menu_admin())
            return ConversationHandler.END
        
        today = date.today().strftime("%d.%m.%Y")
        
        # Davomat inline tugmalar
        kb = []
        for s in group_students:
            kb.append([
                InlineKeyboardButton(f"✅ {s[1]}", callback_data=f"att_present_{s[1]}_{context.user_data['att_group']}_{today}"),
                InlineKeyboardButton(f"❌ {s[1]}", callback_data=f"att_absent_{s[1]}_{context.user_data['att_group']}_{today}")
            ])
        
        await update.message.reply_text(
            f"📋 {context.user_data['att_group']} guruh davomati\n📅 {today}\n\n✅ Keldi | ❌ Kelmadi",
            reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {e}", reply_markup=main_menu_admin())
    
    return ConversationHandler.END

async def attendance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Saqlandi!")
    
    data = query.data.split("_", 4)
    status = "Keldi" if data[1] == "present" else "Kelmadi"
    student = data[2]
    group = data[3]
    att_date = data[4]
    
    try:
        attendance = get_or_create_sheet("Davomat")
        attendance.append_row([att_date, group, student, status])
    except:
        pass

# === ADMIN: XABAR YUBORISH ===
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("📢 Yubormoqchi bo'lgan xabaringizni yozing:\n(Barcha o'quvchilarga yuboriladi)")
    return BROADCAST_MSG

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        students = get_or_create_sheet("Talabalar")
        rows = students.get_all_values()[1:]
        
        sent = 0
        failed = 0
        for row in rows:
            if len(row) >= 7 and row[6]:
                try:
                    await context.bot.send_message(int(row[6]), 
                        f"📢 Kurs xabari:\n\n{update.message.text}")
                    sent += 1
                except:
                    failed += 1
        
        await update.message.reply_text(
            f"✅ Xabar yuborildi!\n✅ Muvaffaqiyatli: {sent}\n❌ Xato: {failed}",
            reply_markup=main_menu_admin())
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}", reply_markup=main_menu_admin())
    
    return ConversationHandler.END

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📞 Bog'lanish:\n\n👤 Admin: @fayozbe_03\n⏰ Ish vaqti: 9:00-18:00",
        reply_markup=main_menu_student())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = main_menu_admin() if is_admin(update.effective_user.id) else main_menu_student()
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=menu)
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Register conversation
    register_conv = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            STUDENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            STUDENT_PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), reg_phone)],
            STUDENT_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_group)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Add group conversation
    add_group_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Guruh qo'shish$"), add_group_start)],
        states={
            GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_name)],
            GROUP_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_days)],
            GROUP_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_time)],
            GROUP_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Add student conversation
    add_student_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ O'quvchi qo'shish$"), add_student_start)],
        states={
            ADD_ADMIN_STUDENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_name)],
            ADD_ADMIN_STUDENT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_phone)],
            ADD_ADMIN_STUDENT_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_group)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Attendance conversation
    attendance_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✅ Davomat$"), attendance_start)],
        states={
            ATTENDANCE_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, attendance_group)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Payment conversation
    payment_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 To'lov qilish$"), payment_start)],
        states={
            PAYMENT_CHECK: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, payment_check),
                MessageHandler(filters.TEXT & ~filters.COMMAND, payment_check),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Broadcast conversation
    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Xabar yuborish$"), broadcast_start)],
        states={
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(register_conv)
    app.add_handler(add_group_conv)
    app.add_handler(add_student_conv)
    app.add_handler(attendance_conv)
    app.add_handler(payment_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(MessageHandler(filters.Regex("^📅 Dars jadvali$"), schedule))
    app.add_handler(MessageHandler(filters.Regex("^📊 Mening ma'lumotlarim$"), my_info))
    app.add_handler(MessageHandler(filters.Regex("^📞 Bog'lanish$"), contact))
    app.add_handler(MessageHandler(filters.Regex("^👥 O'quvchilar$"), students_list))
    app.add_handler(MessageHandler(filters.Regex("^📚 Guruhlar$"), groups_list))
    app.add_handler(MessageHandler(filters.Regex("^📊 Dashboard$"), dashboard))
    app.add_handler(MessageHandler(filters.Regex("^💰 To'lovlar$"), payments_list))
    app.add_handler(CallbackQueryHandler(payment_callback, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(attendance_callback, pattern="^att_"))
    
    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
