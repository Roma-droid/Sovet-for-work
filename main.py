import sqlite3

import telebot
from ollama import Client as OllamaClient
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from env import OLLAMA_API_KEY, TELEGRAM_BOT_TOKEN

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError('Set TELEGRAM_BOT_TOKEN environment variable.')
if not OLLAMA_API_KEY:
    raise RuntimeError('Set OLLAMA_API_KEY environment variable.')

OLLAMA_MODEL = 'gpt-oss:120b'
ollama = OllamaClient(
    host='https://ollama.com',
    headers={'Authorization': f'Bearer {OLLAMA_API_KEY}'},
)
DB_PATH = 'my_database.db'
MAX_HISTORY = 10  # last N messages sent as context to AI

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ---------- States ----------
STATE_CHAT = 'chat'
STATE_ONBOARDING_ROLE = 'onboarding_role'
STATE_ONBOARDING_SKILLS = 'onboarding_skills'
STATE_ONBOARDING_GOALS = 'onboarding_goals'
STATE_EDIT_ROLE = 'edit_role'
STATE_EDIT_SKILLS = 'edit_skills'
STATE_EDIT_GOALS = 'edit_goals'

user_states: dict[int, str] = {}

# ---------- Database ----------

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id   INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            current_role  TEXT,
            skills        TEXT,
            goals         TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        );

        -- Карьерные пути (заполняется вручную)
        CREATE TABLE IF NOT EXISTS career_paths (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT NOT NULL,
            category         TEXT,
            description      TEXT,
            required_skills  TEXT,
            avg_salary_range TEXT,
            growth_potential TEXT
        );

        -- Ресурсы: курсы, книги, статьи, инструменты, сообщества
        CREATE TABLE IF NOT EXISTS resources (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT NOT NULL,
            title       TEXT NOT NULL,
            description TEXT,
            url         TEXT,
            tags        TEXT
        );
    ''')
    conn.commit()
    conn.close()


def get_user(telegram_id: int) -> dict | None:
    conn = _connect()
    row = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(telegram_id: int, username: str | None, first_name: str | None):
    conn = _connect()
    conn.execute(
        'INSERT OR IGNORE INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)',
        (telegram_id, username, first_name),
    )
    conn.commit()
    conn.close()


def update_user(telegram_id: int, **fields):
    if not fields:
        return
    sets = ', '.join(f'{k} = ?' for k in fields)
    vals = list(fields.values()) + [telegram_id]
    conn = _connect()
    conn.execute(
        f"UPDATE users SET {sets}, updated_at = datetime('now') WHERE telegram_id = ?",
        vals,
    )
    conn.commit()
    conn.close()


def save_message(telegram_id: int, role: str, content: str):
    conn = _connect()
    conn.execute(
        'INSERT INTO messages (telegram_id, role, content) VALUES (?, ?, ?)',
        (telegram_id, role, content),
    )
    conn.commit()
    conn.close()


def get_history(telegram_id: int) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        'SELECT role, content FROM messages WHERE telegram_id = ? ORDER BY id DESC LIMIT ?',
        (telegram_id, MAX_HISTORY),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def clear_history(telegram_id: int):
    conn = _connect()
    conn.execute('DELETE FROM messages WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()


def get_career_paths() -> list[dict]:
    conn = _connect()
    rows = conn.execute('SELECT * FROM career_paths ORDER BY id LIMIT 12').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_career_path(path_id: int) -> dict | None:
    conn = _connect()
    row = conn.execute('SELECT * FROM career_paths WHERE id = ?', (path_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_resources(category: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        'SELECT * FROM resources WHERE category = ? ORDER BY id LIMIT 15',
        (category,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Keyboards ----------

def main_menu_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton('💼 Карьерный совет'),
        KeyboardButton('📊 Анализ навыков'),
        KeyboardButton('🗺 Карьерные пути'),
        KeyboardButton('📚 Ресурсы'),
        KeyboardButton('👤 Мой профиль'),
        KeyboardButton('✏️ Изменить профиль'),
    )
    return kb


def resources_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton('📖 Курсы', callback_data='res_course'),
        InlineKeyboardButton('📕 Книги', callback_data='res_book'),
        InlineKeyboardButton('📰 Статьи', callback_data='res_article'),
        InlineKeyboardButton('🛠 Инструменты', callback_data='res_tool'),
        InlineKeyboardButton('👥 Сообщества', callback_data='res_community'),
    )
    return kb


def career_paths_kb() -> InlineKeyboardMarkup:
    paths = get_career_paths()
    kb = InlineKeyboardMarkup(row_width=2)
    if paths:
        kb.add(*[InlineKeyboardButton(p['title'], callback_data=f'path_{p["id"]}') for p in paths])
    else:
        kb.add(InlineKeyboardButton('База пока пуста', callback_data='noop'))
    return kb


def edit_profile_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton('💼 Должность', callback_data='edit_role'),
        InlineKeyboardButton('🧠 Навыки', callback_data='edit_skills'),
        InlineKeyboardButton('🎯 Карьерная цель', callback_data='edit_goals'),
    )
    return kb


# ---------- AI ----------

def build_system_prompt(user: dict | None) -> str:
    base = (
        'Ты — карьерный советник. Помогаешь людям развивать карьеру и находить '
        'свой путь. Отвечай по-русски, структурированно, конкретно и пиши кратко. '
        'Давай практические советы. Избегай общих фраз. '
        'Используй эмодзи умеренно — только там, где они добавляют ясность.'
    )
    if not user:
        return base

    profile_parts = []
    if user.get('first_name'):
        profile_parts.append(f'Пользователя зовут {user["first_name"]}.')
    if user.get('current_role'):
        profile_parts.append(f'Текущая должность: {user["current_role"]}.')
    if user.get('skills'):
        profile_parts.append(f'Навыки: {user["skills"]}.')
    if user.get('goals'):
        profile_parts.append(f'Карьерная цель: {user["goals"]}.')

    if profile_parts:
        return base + '\n\nПрофиль пользователя:\n' + ' '.join(profile_parts)
    return base


def call_ai(telegram_id: int, user_text: str, system_override: str | None = None) -> str:
    user = get_user(telegram_id)
    history = get_history(telegram_id)
    system = system_override or build_system_prompt(user)

    messages = [{'role': 'system', 'content': system}]
    for h in history:
        messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': user_text})

    response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
    answer = response.message.content or 'Не удалось сформировать ответ.'

    save_message(telegram_id, 'user', user_text)
    save_message(telegram_id, 'assistant', answer)
    return answer


def send_ai_reply(chat_id: int, telegram_id: int, user_text: str, system_override: str | None = None):
    bot.send_chat_action(chat_id, 'typing')
    try:
        answer = call_ai(telegram_id, user_text, system_override)
        # Try Markdown first; fall back to plain text if parsing fails
        try:
            bot.send_message(chat_id, answer, parse_mode='Markdown', reply_markup=main_menu_kb())
        except Exception:
            bot.send_message(chat_id, answer, reply_markup=main_menu_kb())
    except Exception as e:
        bot.send_message(chat_id, '❌ Ошибка при обращении к AI. Попробуйте позже.', reply_markup=main_menu_kb())
        print(f'AI error: {e}')


# ---------- Onboarding helpers ----------

def start_onboarding(message):
    uid = message.from_user.id
    user_states[uid] = STATE_ONBOARDING_ROLE

    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton('Ищу работу'),
        KeyboardButton('Студент / начинающий'),
        KeyboardButton('IT-специалист'),
        KeyboardButton('Менеджер / руководитель'),
        KeyboardButton('Предприниматель'),
        KeyboardButton('Другое'),
    )
    bot.send_message(
        message.chat.id,
        '👋 *Привет! Я карьерный советник.*\n\n'
        'Помогу разобраться с развитием карьеры, найти новые пути и прокачать нужные навыки.\n\n'
        'Сначала пара вопросов, чтобы давать персональные советы.\n\n'
        '❓ *Кем ты работаешь сейчас?*',
        parse_mode='Markdown',
        reply_markup=kb,
    )


def show_main_menu(chat_id: int, text: str = '✅ Готово! Чем могу помочь?'):
    bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=main_menu_kb())


def _safe(value: str | None) -> str:
    if not value:
        return '—'
    return value.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')


def show_profile(chat_id: int, telegram_id: int):
    user = get_user(telegram_id)
    if not user:
        bot.send_message(chat_id, '❌ Профиль не найден. Введи /start чтобы начать.', reply_markup=main_menu_kb())
        return
    text = (
        '👤 *Твой профиль*\n\n'
        f'Имя: {_safe(user["first_name"])}\n'
        f'💼 Должность: {_safe(user["current_role"])}\n'
        f'🧠 Навыки: {_safe(user["skills"])}\n'
        f'🎯 Цель: {_safe(user["goals"])}'
    )
    bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=main_menu_kb())


# ---------- Command handlers ----------

@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.from_user.id
    create_user(uid, message.from_user.username, message.from_user.first_name)
    user = get_user(uid)

    if user and user.get('current_role'):
        user_states[uid] = STATE_CHAT
        show_main_menu(message.chat.id, f'👋 С возвращением, {message.from_user.first_name}! Чем могу помочь?')
    else:
        start_onboarding(message)


@bot.message_handler(commands=['help'])
def handle_help(message):
    bot.reply_to(
        message,
        '🤖 *Карьерный советник*\n\n'
        'Используй кнопки меню или просто напиши вопрос.\n\n'
        '*Команды:*\n'
        '/start — перезапустить\n'
        '/profile — посмотреть профиль\n'
        '/reset — очистить историю чата',
        parse_mode='Markdown',
        reply_markup=main_menu_kb(),
    )


@bot.message_handler(commands=['profile'])
def handle_profile(message):
    show_profile(message.chat.id, message.from_user.id)


@bot.message_handler(commands=['reset'])
def handle_reset(message):
    clear_history(message.from_user.id)
    bot.reply_to(message, '🔄 История чата очищена.', reply_markup=main_menu_kb())


# ---------- Main message handler ----------

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    uid = message.from_user.id
    text = message.text.strip()
    state = user_states.get(uid, STATE_CHAT)

    # --- Onboarding flow ---
    if state == STATE_ONBOARDING_ROLE:
        update_user(uid, current_role=text)
        user_states[uid] = STATE_ONBOARDING_SKILLS
        bot.send_message(
            message.chat.id,
            '💡 Отлично!\n\n'
            '❓ *Перечисли свои ключевые навыки* через запятую.\n'
            '_Например: Python, Excel, управление проектами, переговоры_',
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if state == STATE_ONBOARDING_SKILLS:
        update_user(uid, skills=text)
        user_states[uid] = STATE_ONBOARDING_GOALS
        kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=1)
        kb.add(
            KeyboardButton('Вырасти в должности / получить повышение'),
            KeyboardButton('Сменить сферу деятельности'),
            KeyboardButton('Увеличить доход'),
            KeyboardButton('Открыть своё дело'),
            KeyboardButton('Найти первую работу'),
        )
        bot.send_message(
            message.chat.id,
            '🎯 *Какова твоя главная карьерная цель?*',
            parse_mode='Markdown',
            reply_markup=kb,
        )
        return

    if state == STATE_ONBOARDING_GOALS:
        update_user(uid, goals=text)
        user_states[uid] = STATE_CHAT
        show_main_menu(
            message.chat.id,
            '✅ *Профиль создан!* Теперь я могу давать тебе персональные советы.\n\nЧем могу помочь?',
        )
        return

    # --- Edit profile flow ---
    if state == STATE_EDIT_ROLE:
        update_user(uid, current_role=text)
        user_states[uid] = STATE_CHAT
        show_main_menu(message.chat.id, '✅ Должность обновлена!')
        return

    if state == STATE_EDIT_SKILLS:
        update_user(uid, skills=text)
        user_states[uid] = STATE_CHAT
        show_main_menu(message.chat.id, '✅ Навыки обновлены!')
        return

    if state == STATE_EDIT_GOALS:
        update_user(uid, goals=text)
        user_states[uid] = STATE_CHAT
        show_main_menu(message.chat.id, '✅ Цель обновлена!')
        return

    # --- Main menu buttons ---
    if text == '💼 Карьерный совет':
        bot.send_message(
            message.chat.id,
            '💼 *Карьерный совет*\n\nНапиши свой вопрос или опиши ситуацию — дам персональную рекомендацию.',
            parse_mode='Markdown',
            reply_markup=main_menu_kb(),
        )
        return

    if text == '📊 Анализ навыков':
        user = get_user(uid)
        if not user or not user.get('skills'):
            bot.send_message(message.chat.id, '⚠️ Сначала заполни профиль — нажми «✏️ Изменить профиль».', reply_markup=main_menu_kb())
            return
        bot.send_message(message.chat.id, '⏳ Анализирую навыки...', reply_markup=main_menu_kb())
        query = f'Мои навыки: {user["skills"]}. Цель: {user.get("goals", "не указана")}.'
        instruction = (
            'Проведи анализ навыков пользователя. Структурируй ответ строго по разделам:\n'
            '1. Сильные стороны — что уже есть и это ценно\n'
            '2. Пробелы — чего не хватает для достижения цели\n'
            '3. Топ-3 навыка для развития прямо сейчас с конкретными первыми шагами\n'
            'Будь конкретен. Никаких общих фраз.'
        )
        send_ai_reply(message.chat.id, uid, query, build_system_prompt(user) + '\n\n' + instruction)
        return

    if text == '🗺 Карьерные пути':
        paths = get_career_paths()
        if not paths:
            bot.send_message(
                message.chat.id,
                '📭 База карьерных путей пока пуста.\n\n'
                'Просто напиши, какое направление тебя интересует — подскажу что изучить!',
                reply_markup=main_menu_kb(),
            )
        else:
            bot.send_message(
                message.chat.id,
                '🗺 *Карьерные пути* — выбери направление:',
                parse_mode='Markdown',
                reply_markup=career_paths_kb(),
            )
        return

    if text == '📚 Ресурсы':
        bot.send_message(
            message.chat.id,
            '📚 *Ресурсы для развития* — выбери категорию:',
            parse_mode='Markdown',
            reply_markup=resources_kb(),
        )
        return

    if text == '👤 Мой профиль':
        show_profile(message.chat.id, uid)
        return

    if text == '✏️ Изменить профиль':
        bot.send_message(message.chat.id, '✏️ *Что обновить?*', parse_mode='Markdown', reply_markup=edit_profile_kb())
        return

    # --- Free chat ---
    send_ai_reply(message.chat.id, uid, text)


# ---------- Callback handlers ----------

RESOURCE_LABELS = {
    'course': '📖 Курсы',
    'book': '📕 Книги',
    'article': '📰 Статьи',
    'tool': '🛠 Инструменты',
    'community': '👥 Сообщества',
}


@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    uid = call.from_user.id
    data = call.data
    bot.answer_callback_query(call.id)

    if data == 'noop':
        return

    if data.startswith('edit_'):
        field = data[5:]
        config = {
            'role': (STATE_EDIT_ROLE, '💼 Напиши свою текущую должность:'),
            'skills': (STATE_EDIT_SKILLS, '🧠 Перечисли навыки через запятую:'),
            'goals': (STATE_EDIT_GOALS, '🎯 Опиши свою карьерную цель:'),
        }
        if field in config:
            state, prompt = config[field]
            user_states[uid] = state
            bot.send_message(call.message.chat.id, prompt, reply_markup=ReplyKeyboardRemove())
        return

    if data.startswith('res_'):
        category = data[4:]
        label = RESOURCE_LABELS.get(category, category)
        items = get_resources(category)
        if not items:
            bot.send_message(call.message.chat.id, f'📭 В разделе «{label}» пока ничего нет.', reply_markup=main_menu_kb())
            return
        lines = [f'*{label}*\n']
        for r in items:
            lines.append(f'• *{r["title"]}*')
            if r.get('description'):
                lines.append(f'  {r["description"]}')
            if r.get('url'):
                lines.append(f'  🔗 {r["url"]}')
            lines.append('')
        try:
            bot.send_message(call.message.chat.id, '\n'.join(lines), parse_mode='Markdown', reply_markup=main_menu_kb())
        except Exception:
            bot.send_message(call.message.chat.id, '\n'.join(lines), reply_markup=main_menu_kb())
        return

    if data.startswith('path_'):
        path_id = int(data[5:])
        path = get_career_path(path_id)
        if not path:
            bot.send_message(call.message.chat.id, '❌ Не найдено.', reply_markup=main_menu_kb())
            return
        lines = [f'🗺 *{path["title"]}*\n']
        if path.get('description'):
            lines.append(path['description'] + '\n')
        if path.get('required_skills'):
            lines.append(f'🧠 *Необходимые навыки:*\n{path["required_skills"]}\n')
        if path.get('avg_salary_range'):
            lines.append(f'💰 *Зарплата:* {path["avg_salary_range"]}\n')
        if path.get('growth_potential'):
            lines.append(f'📈 *Перспективы:*\n{path["growth_potential"]}')
        try:
            bot.send_message(call.message.chat.id, '\n'.join(lines), parse_mode='Markdown', reply_markup=main_menu_kb())
        except Exception:
            bot.send_message(call.message.chat.id, '\n'.join(lines), reply_markup=main_menu_kb())
        return


# ---------- Entry point ----------

if __name__ == '__main__':
    init_db()
    print('Запуск карьерного бота...')
    bot.polling(none_stop=True)
