import telebot
from telebot import types
import sqlite3
import os
import random
import string
import google.generativeai as genai

# ==========================================
# ⚠️ توکن‌ها از تنظیمات Render خوانده می‌شوند (امنیت بالا)
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)

# تنظیمات هوش مصنوعی
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

# ==========================================
# 🗄️ راه‌اندازی دیتابیس
# ==========================================
conn = sqlite3.connect('nexus_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    points INTEGER DEFAULT 0,
    state TEXT DEFAULT 'none',
    temp_data TEXT DEFAULT '' )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    is_done INTEGER DEFAULT 0)''')
conn.commit()

# ==========================================
# 🎛️ منوها
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🤖 دستیار هوشمند"),
        types.KeyboardButton("✅ مدیریت کارها"),
        types.KeyboardButton("📚 مرکز یادگیری"),
        types.KeyboardButton("🚀 فرصت‌ها"),
        types.KeyboardButton("🧰 جعبه ابزار"),
        types.KeyboardButton("👤 پروفایل من")
    )
    return markup

def back_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.from_user.id
    name = message.from_user.first_name
    
    cursor.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit()

    welcome_text = (
        f"سلام {name} عزیز! 👋\n"
        "به **NEXUS** خوش آمدید.\n"
        "دستیار دیجیتال همه‌کاره شما در تلگرام.\n\n"
        "لطفاً از منوی زیر یکی از بخش‌ها را انتخاب کنید:"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🤖 دستیار هوشمند")
def ai_assistant_start(message):
    bot.send_message(message.chat.id, "شما وارد دستیار هوشمند شدید. سوال خود را بپرسید یا برای خروج دکمه بازگشت را بزنید.", reply_markup=back_menu())
    cursor.execute("UPDATE users SET state = 'chatting_ai' WHERE user_id = ?", (message.from_user.id,))
    conn.commit()

@bot.message_handler(func=lambda message: message.text == "✅ مدیریت کارها")
def task_manager(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ افزودن کار جدید", callback_data="add_task"))
    markup.add(types.InlineKeyboardButton("📋 مشاهده لیست کارها", callback_data="list_tasks"))
    bot.send_message(message.chat.id, "📋 **مدیریت کارهای روزانه**\nیکی از گزینه‌ها را انتخاب کنید:", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "add_task")
def add_task_callback(call):
    msg = bot.send_message(call.message.chat.id, "عنوان کار جدید را تایپ کنید:")
    bot.register_next_step_handler(msg, save_task)

def save_task(message):
    uid = message.from_user.id
    title = message.text
    if title == "🔙 بازگشت به منوی اصلی":
        bot.send_message(message.chat.id, "منوی اصلی:", reply_markup=main_menu())
        return
    cursor.execute("INSERT INTO tasks (user_id, title) VALUES (?, ?)", (uid, title))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ کار '{title}' با موفقیت اضافه شد.", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "list_tasks")
def list_tasks(call):
    uid = call.from_user.id
    cursor.execute("SELECT id, title, is_done FROM tasks WHERE user_id = ?", (uid,))
    tasks = cursor.fetchall()
    
    if not tasks:
        bot.send_message(call.message.chat.id, "شما هیچ کاری ندارید.")
        return

    text = "📝 **لیست کارهای شما:**\n\n"
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for t in tasks:
        status = "✅" if t[2] == 1 else "⏳"
        text += f"{status} {t[1]}\n"
        if t[2] == 0:
            done_btn = types.InlineKeyboardButton(f"تکمیل {t[1][:10]}", callback_data=f"done_{t[0]}")
            del_btn = types.InlineKeyboardButton(f"حذف", callback_data=f"del_{t[0]}")
            markup.row(done_btn, del_btn)
    
    markup.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_tasks"))
    bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith("done_") or call.data.startswith("del_"))
def handle_task_action(call):
    action, task_id = call.data.split("_")
    uid = call.from_user.id
    
    if action == "done":
        cursor.execute("UPDATE tasks SET is_done = 1 WHERE id = ?", (task_id,))
        cursor.execute("UPDATE users SET points = points + 10 WHERE user_id = ?", (uid,))
        bot.answer_callback_query(call.id, "کار انجام شد! +۱۰ امتیاز")
    elif action == "del":
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        bot.answer_callback_query(call.id, "کار حذف شد.")
        
    conn.commit()
    list_tasks(call)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_tasks")
def back_to_tasks(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    task_manager(call.message)

@bot.message_handler(func=lambda message: message.text == "🧰 جعبه ابزار")
def tools_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🧮 ماشین‌حساب", callback_data="tool_calc"),
        types.InlineKeyboardButton("🔐 تولید رمز", callback_data="tool_pass"),
        types.InlineKeyboardButton("📝 شمارش کلمات", callback_data="tool_word"),
        types.InlineKeyboardButton("🎲 عدد تصادفی", callback_data="tool_rand")
    )
    bot.send_message(message.chat.id, "🧰 **جعبه ابزار NEXUS**\nیک ابزار را انتخاب کنید:", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith("tool_"))
def handle_tools(call):
    tool = call.data.split("_")[1]
    uid = call.from_user.id

    if tool == "calc":
        cursor.execute("UPDATE users SET state = 'calc' WHERE user_id = ?", (uid,))
        conn.commit()
        bot.send_message(call.message.chat.id, "🧮 عبارت ریاضی خود را وارد کنید (مثال: 5 * 8 + 10):")
    elif tool == "pass":
        password = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$%^&*", k=16))
        bot.send_message(call.message.chat.id, f"🔐 رمز عبور تصادفی شما:\n`{password}`", parse_mode='Markdown')
    elif tool == "word":
        cursor.execute("UPDATE users SET state = 'wordcount' WHERE user_id = ?", (uid,))
        conn.commit()
        bot.send_message(call.message.chat.id, "📝 متن خود را بفرستید تا تعداد کلماتش شمرده شود:")
    elif tool == "rand":
        num = random.randint(1, 100)
        bot.send_message(call.message.chat.id, f"🎲 عدد تصادفی شما بین ۱ تا ۱۰۰:\n**{num}**", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "📚 مرکز یادگیری")
def learn_menu(message):
    text = (
        "📚 **مرکز یادگیری NEXUS**\n\n"
        "🔗 [freeCodeCamp](https://www.freecodecamp.org) - دوره‌های رایگان برنامه‌نویسی\n\n"
        "🔗 [MDN Web Docs](https://developer.mozilla.org) - مرجع طراحی وب\n\n"
        "🔗 [CS50 هاروارد](https://cs50.harvard.edu) - دوره علوم کامپیوتر\n\n"
        "🔗 [Khan Academy](https://www.khanacademy.org) - ریاضی و علوم\n\n"
        "🔗 [Duolingo](https://www.duolingo.com) - یادگیری زبان"
    )
    bot.send_message(message.chat.id, text, disable_web_page_preview=True, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🚀 فرصت‌ها")
def opp_menu(message):
    text = (
        "🚀 **فرصت‌های پیش روی شما**\n\n"
        "🎓 [بورسیه ترکیه](https://turkiyeburslari.gov.tr) - بورسیه تحصیلی دولتی\n\n"
        "🏆 [جشنواره خوارزمی](https://khwarizmi.medu.ir) - جشنواره پژوهشی\n\n"
        "🥇 [المپیادهای علمی](https://olympiad.medu.ir) - المپیاد دانش‌آموزی\n\n"
        "⚠️ *تاریخ‌ها و شرایط را حتماً در سایت رسمی بررسی کنید.*"
    )
    bot.send_message(message.chat.id, text, disable_web_page_preview=True, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "👤 پروفایل من")
def profile(message):
    uid = message.from_user.id
    cursor.execute("SELECT name, points FROM users WHERE user_id = ?", (uid,))
    user = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND is_done = 1", (uid,))
    done_tasks = cursor.fetchone()[0]
    text = f"👤 **پروفایل شما**\n\n📛 نام: {user[0]}\n⭐️ امتیاز: {user[1]}\n✅ کارهای انجام شده: {done_tasks}\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🔙 بازگشت به منوی اصلی")
def back_to_main(message):
    uid = message.from_user.id
    cursor.execute("UPDATE users SET state = 'none' WHERE user_id = ?", (uid,))
    conn.commit()
    bot.send_message(message.chat.id, "به منوی اصلی بازگشتید.", reply_markup=main_menu())

@bot.message_handler(func=lambda message: True)
def handle_free_text(message):
    uid = message.from_user.id
    text = message.text
    cursor.execute("SELECT state FROM users WHERE user_id = ?", (uid,))
    state = cursor.fetchone()[0]

    if state == 'chatting_ai':
        if not ai_model:
            bot.send_message(message.chat.id, "⚠️ کلید API هوش مصنوعی تنظیم نشده است.")
            return
        msg = bot.send_message(message.chat.id, "⏳ در حال فکر کردن...")
        try:
            response = ai_model.generate_content(text)
            bot.edit_message_text(response.text, chat_id=message.chat.id, message_id=msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"خطا در ارتباط با هوش مصنوعی:\n{str(e)}", chat_id=message.chat.id, message_id=msg.message_id)
    elif state == 'calc':
        try:
            allowed = {"__builtins__": None}
            result = eval(text, allowed)
            bot.send_message(message.chat.id, f"🧮 نتیجه: `{result}`", parse_mode='Markdown')
        except:
            bot.send_message(message.chat.id, "⚠️ عبارت نامعتبر است. فقط از اعداد و علائم + - * / استفاده کنید.")
        cursor.execute("UPDATE users SET state = 'none' WHERE user_id = ?", (uid,))
        conn.commit()
    elif state == 'wordcount':
        words = len(text.split())
        chars = len(text)
        bot.send_message(message.chat.id, f"📝 تعداد کلمات: **{words}**\n🔠 تعداد کاراکترها: **{chars}**", parse_mode='Markdown')
        cursor.execute("UPDATE users SET state = 'none' WHERE user_id = ?", (uid,))
        conn.commit()
    else:
        bot.send_message(message.chat.id, "لطفاً از منوی زیر استفاده کنید:", reply_markup=main_menu())

if __name__ == '__main__':
    print("NEXUS Bot is running...")
    bot.infinity_polling()
