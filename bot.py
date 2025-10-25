import logging
import sqlite3
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройки из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')

# Проверка токена
if not BOT_TOKEN:
    logging.error("❌ BOT_TOKEN не установлен!")
    exit(1)

# Состояния диалога
NAME, PHONE, AGE, EXPERIENCE = range(4)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('fencing_applications.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS applications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  first_name TEXT,
                  phone TEXT,
                  age INTEGER,
                  experience TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    logging.info("✅ База данных готова")

def save_application(user_id, username, first_name, phone, age, experience):
    conn = sqlite3.connect('fencing_applications.db')
    c = conn.cursor()
    c.execute('''INSERT INTO applications 
                 (user_id, username, first_name, phone, age, experience) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, username, first_name, phone, age, experience))
    conn.commit()
    conn.close()
    logging.info(f"✅ Заявка сохранена: {first_name}, {phone}")

def get_applications_count():
    conn = sqlite3.connect('fencing_applications.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM applications")
    count = c.fetchone()[0]
    conn.close()
    return count

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Пользователь {update.message.from_user.id} начал диалог")
    
    welcome_text = """
🤺 Добро пожаловать в Тольяттинскую федерацию фехтования!

Для записи на тренировку давайте соберем необходимую информацию.

📝 Как вас зовут?
"""
    
    await update.message.reply_text(welcome_text, reply_markup=ReplyKeyboardRemove())
    return NAME

# Обработка имени
async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    context.user_data['first_name'] = name
    context.user_data['username'] = update.message.from_user.username
    context.user_data['user_id'] = update.message.from_user.id
    
    logging.info(f"Пользователь ввел имя: {name}")
    
    phone_text = f"Приятно познакомиться, {name}! 📞"
    
    keyboard = [
        [KeyboardButton("📞 Поделиться номером", request_contact=True)],
        [KeyboardButton("📝 Ввести номер вручную")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(phone_text, reply_markup=reply_markup)
    return PHONE

# Обработка телефона через кнопку
async def process_contact_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone = contact.phone_number
    context.user_data['phone'] = phone
    
    logging.info(f"Получен контакт через кнопку: {phone}")
    
    await ask_age(update, context)
    return AGE

# Обработка выбора ручного ввода
async def process_manual_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "📝 Ввести номер вручную":
        await update.message.reply_text(
            "Введите ваш номер телефона:",
            reply_markup=ReplyKeyboardRemove()
        )
        return PHONE
    else:
        return await process_phone_text(update, context)

# Обработка ручного ввода телефона
async def process_phone_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    if not any(char.isdigit() for char in phone) or len(phone) < 10:
        await update.message.reply_text("❌ Пожалуйста, введите корректный номер телефона:")
        return PHONE
    
    context.user_data['phone'] = phone
    logging.info(f"Получен контакт вручную: {phone}")
    
    await ask_age(update, context)
    return AGE

# Запрос возраста
async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Сколько вам лет?")
    return AGE

# Обработка возраста
async def process_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 5 or age > 70:
            await update.message.reply_text("❌ Пожалуйста, укажите реальный возраст (5-70 лет):")
            return AGE
        
        context.user_data['age'] = age
        logging.info(f"Пользователь ввел возраст: {age}")
        
        keyboard = [
            [KeyboardButton("Новичок")],
            [KeyboardButton("Занимался(ась) ранее")],
            [KeyboardButton("Опытный спортсмен")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text("🏅 Есть ли у вас опыт в фехтовании?", reply_markup=reply_markup)
        return EXPERIENCE
        
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите возраст цифрами:")
        return AGE

# Обработка опыта и сохранение заявки
async def process_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    experience = update.message.text
    context.user_data['experience'] = experience
    
    save_application(
        user_id=context.user_data['user_id'],
        username=context.user_data['username'],
        first_name=context.user_data['first_name'],
        phone=context.user_data['phone'],
        age=context.user_data['age'],
        experience=experience
    )
    
    manager_message = f"""
🏆 НОВАЯ ЗАЯВКА В ФЕДЕРАЦИЮ ФЕХТОВАНИЯ!

👤 Имя: {context.user_data['first_name']}
📞 Телефон: {context.user_data['phone']}
🎯 Возраст: {context.user_data['age']} лет
📊 Опыт: {experience}
👤 Username: @{context.user_data['username']}
🆔 ID: {context.user_data['user_id']}

📈 Всего заявок: {get_applications_count()}
"""
    
    try:
        await context.bot.send_message(chat_id=MANAGER_CHAT_ID, text=manager_message)
        logging.info("✅ Уведомление отправлено менеджеру")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки менеджеру: {e}")
    
    success_text = f"""
✅ Спасибо, {context.user_data['first_name']}! Ваша заявка принята!

🏅 Тольяттинская федерация фехтования
📞 Наш менеджер свяжется с вами в течение 24 часов

Для новой заявки отправьте /start
"""
    
    await update.message.reply_text(success_text, reply_markup=ReplyKeyboardRemove())
    logging.info("✅ Диалог завершен успешно")
    return ConversationHandler.END

# Отмена диалога
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Диалог отменен. Для начала отправьте /start', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Основная функция
def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)],
            PHONE: [
                MessageHandler(filters.CONTACT, process_contact_button),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_manual_phone)
            ],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_age)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_experience)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    
    logging.info("🤺 Бот запущен на PythonAnywhere!")
    application.run_polling()

if __name__ == '__main__':
    main()