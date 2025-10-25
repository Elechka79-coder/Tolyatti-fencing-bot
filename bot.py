import os
import sys
import time
import logging
import sqlite3
import telebot
from telebot import types

# Проверка на множественный запуск
def check_running():
    import subprocess
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    processes = result.stdout
    
    bot_processes = [line for line in processes.split('\n') if 'python bot.py' in line and 'grep' not in line]
    
    if len(bot_processes) > 1:
        print("❌ Уже запущен другой экземпляр бота! Завершаем...")
        sys.exit(1)

check_running()

# Настройки из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')

if not BOT_TOKEN:
    print("❌ BOT_TOKEN не установлен!")
    exit(1)

# Создаем бота
bot = telebot.TeleBot(BOT_TOKEN)

# Состояния диалога (храним в памяти)
user_data = {}

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
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
    print("✅ База данных готова")

def save_application(user_id, username, first_name, phone, age, experience):
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
    conn = sqlite3.connect('fencing_applications.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM applications")
    count = c.fetchone()[0]
    conn.close()
    return count

# Команда /start
@bot.message_handler(commands=['start'])
def start_message(message):
    user_id = message.from_user.id
    user_data[user_id] = {'step': 'name'}
    
    welcome_text = """
🤺 Добро пожаловать в Тольяттинскую федерацию фехтования!

Для записи на тренировку давайте соберем необходимую информацию.

📝 Как вас зовут?
"""
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=types.ReplyKeyboardRemove())

# Обработка имени
@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('step') == 'name')
def process_name(message):
    user_id = message.from_user.id
    name = message.text
    
    user_data[user_id] = {
        'step': 'phone',
        'first_name': name,
        'username': message.from_user.username,
        'user_id': user_id
    }
    
    print(f"Пользователь ввел имя: {name}")
    
    phone_text = f"Приятно познакомиться, {name}! 📞"
    
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button_contact = types.KeyboardButton("📞 Поделиться номером", request_contact=True)
    button_manual = types.KeyboardButton("📝 Ввести номер вручную")
    keyboard.add(button_contact, button_manual)
    
    bot.send_message(message.chat.id, phone_text, reply_markup=keyboard)

# Обработка контакта через кнопку
@bot.message_handler(content_types=['contact'])
def process_contact(message):
    user_id = message.from_user.id
    if user_data.get(user_id, {}).get('step') != 'phone':
        return
    
    phone = message.contact.phone_number
    user_data[user_id]['phone'] = phone
    user_data[user_id]['step'] = 'age'
    
    print(f"Получен контакт через кнопку: {phone}")
    
    bot.send_message(message.chat.id, "🎯 Сколько вам лет?", reply_markup=types.ReplyKeyboardRemove())

# Обработка ручного ввода телефона
@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('step') == 'phone')
def process_phone_text(message):
    user_id = message.from_user.id
    
    if message.text == "📝 Ввести номер вручную":
        bot.send_message(message.chat.id, "Введите ваш номер телефона:", reply_markup=types.ReplyKeyboardRemove())
        return
    
    phone = message.text
    if not any(char.isdigit() for char in phone) or len(phone) < 10:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректный номер телефона:")
        return
    
    user_data[user_id]['phone'] = phone
    user_data[user_id]['step'] = 'age'
    
    print(f"Получен контакт вручную: {phone}")
    
    bot.send_message(message.chat.id, "🎯 Сколько вам лет?")

# Обработка возраста
@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('step') == 'age')
def process_age(message):
    user_id = message.from_user.id
    
    try:
        age = int(message.text)
        if age < 5 or age > 70:
            bot.send_message(message.chat.id, "❌ Пожалуйста, укажите реальный возраст (5-70 лет):")
            return
        
        user_data[user_id]['age'] = age
        user_data[user_id]['step'] = 'experience'
        
        print(f"Пользователь ввел возраст: {age}")
        
        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        keyboard.add(
            types.KeyboardButton("Новичок"),
            types.KeyboardButton("Занимался(ась) ранее"),
            types.KeyboardButton("Опытный спортсмен")
        )
        
        bot.send_message(message.chat.id, "🏅 Есть ли у вас опыт в фехтовании?", reply_markup=keyboard)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите возраст цифрами:")

# Обработка опыта и сохранение заявки
@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('step') == 'experience')
def process_experience(message):
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

Для новой заявки отправьте /start
"""
    
    bot.send_message(message.chat.id, success_text, reply_markup=types.ReplyKeyboardRemove())
    
    # Очищаем данные пользователя
    user_data.pop(user_id, None)
    print("✅ Диалог завершен успешно")

# Обработка неизвестных сообщений
@bot.message_handler(func=lambda message: True)
def unknown_message(message):
    if message.text.startswith('/'):
        bot.send_message(message.chat.id, "Для записи на тренировку отправьте /start")
    else:
        bot.send_message(message.chat.id, "Для начала диалога отправьте /start")

# Запуск бота
if __name__ == '__main__':
    init_db()
    print("🤺 Бот Тольяттинской федерации фехтования запущен!")
    bot.infinity_polling()

