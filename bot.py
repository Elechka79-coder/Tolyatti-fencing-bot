import logging
import sqlite3
import os
import telebot
from telebot import types
from flask import Flask
from threading import Thread
import datetime

# ==================== НАСТРОЙКИ ====================
# Эти переменные нужно установить в Secrets на Replit:
# BOT_TOKEN = ваш_токен_бота
# MANAGER_CHAT_ID = ваш_id_администратора

BOT_TOKEN = os.getenv('BOT_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')

# Проверка токена
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не установлен!")
    print("📝 На Replit зайдите в Secrets и установите BOT_TOKEN")
    exit(1)

if not MANAGER_CHAT_ID:
    print("❌ ОШИБКА: MANAGER_CHAT_ID не установлен!")
    print("📝 На Replit зайдите в Secrets и установите MANAGER_CHAT_ID")
    exit(1)

# ==================== FLASK ДЛЯ АКТИВНОСТИ ====================
# Это нужно чтобы Replit не "засыпал"
app = Flask('')

@app.route('/')
def home():
    return f"""
    <html>
        <head>
            <title>Тольяттинская федерация фехтования</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                h1 {{ color: #2c3e50; }}
                .status {{ color: #27ae60; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>🤺 Тольяттинская федерация фехтования</h1>
            <p class="status">✅ Телеграм-бот работает!</p>
            <p>Время: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Для записи на тренировки напишите боту в Telegram</p>
        </body>
    </html>
    """

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ==================== НАСТРОЙКА БОТА ====================
bot = telebot.TeleBot(BOT_TOKEN)

# Хранилище данных пользователей (в памяти)
user_data = {}

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    """Создаем базу данных для заявок"""
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
    print("✅ База данных готова")

def save_application(user_id, username, first_name, phone, age, experience):
    """Сохраняем заявку в базу данных"""
    conn = sqlite3.connect('fencing_applications.db')
    c = conn.cursor()
    c.execute('''INSERT INTO applications 
                 (user_id, username, first_name, phone, age, experience) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, username, first_name, phone, age, experience))
    conn.commit()
    conn.close()
    print(f"✅ Заявка сохранена: {first_name}, {phone}")

def get_applications_count():
    """Получаем количество заявок"""
    conn = sqlite3.connect('fencing_applications.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM applications")
    count = c.fetchone()[0]
    conn.close()
    return count

# ==================== КОМАНДЫ БОТА ====================
@bot.message_handler(commands=['start'])
def start_message(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user_data[user_id] = {'step': 'name'}
    
    welcome_text = """
🤺 Добро пожаловать в Тольяттинскую федерацию фехтования!

Для записи на тренировку давайте соберем необходимую информацию.

📝 Как вас зовут?
"""
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=types.ReplyKeyboardRemove())
    print(f"👤 Пользователь {user_id} начал диалог")

@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('step') == 'name')
def process_name(message):
    """Обработка имени пользователя"""
    user_id = message.from_user.id
    name = message.text.strip()
    
    if len(name) < 2:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите настоящее имя:")
        return
    
    user_data[user_id] = {
        'step': 'phone',
        'first_name': name,
        'username': message.from_user.username,
        'user_id': user_id
    }
    
    print(f"👤 Пользователь {user_id} ввел имя: {name}")
    
    phone_text = f"Приятно познакомиться, {name}! 📞"
    
    # Создаем клавиатуру с кнопками
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button_contact = types.KeyboardButton("📞 Поделиться номером", request_contact=True)
    button_manual = types.KeyboardButton("📝 Ввести номер вручную")
    keyboard.add(button_contact, button_manual)
    
    bot.send_message(message.chat.id, phone_text, reply_markup=keyboard)

@bot.message_handler(content_types=['contact'])
def process_contact(message):
    """Обработка контакта через кнопку"""
    user_id = message.from_user.id
    if user_data.get(user_id, {}).get('step') != 'phone':
        return
    
    phone = message.contact.phone_number
    user_data[user_id]['phone'] = phone
    user_data[user_id]['step'] = 'age'
    
    print(f"📞 Пользователь {user_id} поделился номером: {phone}")
    
    bot.send_message(message.chat.id, "🎯 Сколько вам лет?", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('step') == 'phone')
def process_phone_text(message):
    """Обработка ручного ввода телефона"""
    user_id = message.from_user.id
    
    if message.text == "📝 Ввести номер вручную":
        bot.send_message(message.chat.id, "Введите ваш номер телефона:", reply_markup=types.ReplyKeyboardRemove())
        return
    
    phone = message.text.strip()
    
    # Простая проверка номера
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) < 10:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректный номер телефона (например: 89991234567):")
        return
    
    user_data[user_id]['phone'] = phone
    user_data[user_id]['step'] = 'age'
    
    print(f"📞 Пользователь {user_id} ввел номер: {phone}")
    
    bot.send_message(message.chat.id, "🎯 Сколько вам лет?")

@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('step') == 'age')
def process_age(message):
    """Обработка возраста"""
    user_id = message.from_user.id
    
    try:
        age = int(message.text)
        if age < 5 or age > 70:
            bot.send_message(message.chat.id, "❌ Пожалуйста, укажите реальный возраст (5-70 лет):")
            return
        
        user_data[user_id]['age'] = age
        user_data[user_id]['step'] = 'experience'
        
        print(f"🎯 Пользователь {user_id} ввел возраст: {age}")
        
        # Клавиатура с вариантами опыта
        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        keyboard.add(
            types.KeyboardButton("Новичок"),
            types.KeyboardButton("Занимался(ась) ранее"),
            types.KeyboardButton("Опытный спортсмен")
        )
        
        bot.send_message(message.chat.id, "🏅 Есть ли у вас опыт в фехтовании?", reply_markup=keyboard)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите возраст цифрами:")

@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('step') == 'experience')
def process_experience(message):
    """Обработка опыта и сохранение заявки"""
    user_id = message.from_user.id
    experience = message.text
    user_data[user_id]['experience'] = experience
    
    # Сохраняем заявку
    save_application(
        user_id=user_data[user_id]['user_id'],
        username=user_data[user_id]['username'],
        first_name=user_data[user_id]['first_name'],
        phone=user_data[user_id]['phone'],
        age=user_data[user_id]['age'],
        experience=experience
    )
    
    # Сообщение для менеджера
    manager_message = f"""
🏆 НОВАЯ ЗАЯВКА В ФЕДЕРАЦИЮ ФЕХТОВАНИЯ!

👤 Имя: {user_data[user_id]['first_name']}
📞 Телефон: {user_data[user_id]['phone']}
🎯 Возраст: {user_data[user_id]['age']} лет
📊 Опыт: {experience}
👤 Username: @{user_data[user_id]['username']}
🆔 ID: {user_data[user_id]['user_id']}

📈 Всего заявок: {get_applications_count()}
"""
    
    try:
        bot.send_message(MANAGER_CHAT_ID, manager_message)
        print("✅ Уведомление отправлено менеджеру")
    except Exception as e:
        print(f"❌ Ошибка отправки менеджеру: {e}")
    
    # Ответ пользователю
    success_text = f"""
✅ Спасибо, {user_data[user_id]['first_name']}! Ваша заявка принята!

🏅 Тольяттинская федерация фехтования
📞 Наш менеджер свяжется с вами в течение 24 часов

📍 Адрес: г. Тольятти, ул. Спортивная, 15
📅 Расписание: Пн-Пт 18:00-21:00, Сб 10:00-14:00

Для новой заявки отправьте /start
"""
    
    bot.send_message(message.chat.id, success_text, reply_markup=types.ReplyKeyboardRemove())
    
    # Очищаем данные пользователя
    if user_id in user_data:
        del user_data[user_id]
    
    print(f"✅ Диалог с пользователем {user_id} завершен успешно")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    """Показывает статистику (только для администратора)"""
    if str(message.from_user.id) != MANAGER_CHAT_ID:
        bot.send_message(message.chat.id, "❌ Эта команда доступна только администратору")
        return
    
    count = get_applications_count()
    bot.send_message(message.chat.id, f"📊 Статистика заявок:\nВсего заявок: {count}")

@bot.message_handler(func=lambda message: True)
def unknown_message(message):
    """Обработка любых других сообщений"""
    if message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ Неизвестная команда\nДля записи на тренировку отправьте /start")
    else:
        bot.send_message(message.chat.id, "🤺 Для записи на тренировку отправьте /start")

# ==================== ЗАПУСК БОТА ====================
def main():
    """Основная функция запуска"""
    print("=" * 50)
    print("🤺 Запуск бота Тольяттинской федерации фехтования")
    print("=" * 50)
    
    # Запускаем Flask для поддержания активности
    keep_alive()
    print("✅ Flask сервер запущен")
    
    # Инициализируем базу данных
    init_db()
    
    print("✅ Бот готов к работе!")
    print("📝 Логи будут отображаться ниже...")
    
    # Запускаем бота
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Ошибка в работе бота: {e}")
        print("🔄 Перезапуск через 10 секунд...")
        import time
        time.sleep(10)
        main()  # Перезапуск

if __name__ == '__main__':
    main()
