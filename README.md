# Карьерный советник — Telegram бот

Telegram бот для персональных карьерных рекомендаций на базе Ollama Cloud.

## Возможности

- **Онбординг** — при первом запуске бот собирает профиль пользователя (должность, навыки, цель) через кнопки и текст
- **Персональные советы** — все ответы AI учитывают профиль пользователя
- **Анализ навыков** — структурированный разбор сильных сторон, пробелов и плана развития
- **Карьерные пути** — база направлений с описанием, навыками и зарплатной вилкой
- **Ресурсы** — курсы, книги, статьи, инструменты, сообщества по категориям
- **История чата** — последние 10 сообщений передаются в AI как контекст
- **Редактирование профиля** — можно обновить любое поле в любой момент

## Установка

```bash
git clone <repo>
cd hod
python -m venv .venv
source .venv/bin/activate
pip install telebot ollama
```

## Конфигурация

Создайте файл `env.py`:

```python
TELEGRAM_BOT_TOKEN = 'ваш_токен'   # от @BotFather
OLLAMA_API_KEY = 'ваш_ключ'        # от ollama.com/settings/keys
```

## Запуск

```bash
python main.py
```

## Команды бота

| Команда | Действие |
|---|---|
| `/start` | Запустить бота / вернуться в главное меню |
| `/profile` | Посмотреть профиль |
| `/reset` | Очистить историю чата |
| `/help` | Справка |

## Структура базы данных

База `my_database.db` создаётся автоматически при первом запуске.

### `users` — профили пользователей

| Поле | Тип | Описание |
|---|---|---|
| `telegram_id` | INTEGER | ID пользователя в Telegram |
| `username` | TEXT | @username |
| `first_name` | TEXT | Имя |
| `current_role` | TEXT | Текущая должность |
| `skills` | TEXT | Навыки через запятую |
| `goals` | TEXT | Карьерная цель |

### `career_paths` — карьерные пути (заполняется вручную)

| Поле | Тип | Пример |
|---|---|---|
| `title` | TEXT | `Product Manager` |
| `category` | TEXT | `менеджмент` |
| `description` | TEXT | Краткое описание роли |
| `required_skills` | TEXT | `Jira, SQL, Figma` |
| `avg_salary_range` | TEXT | `150 000 — 350 000 руб/мес` |
| `growth_potential` | TEXT | `CPO, собственный продукт` |

### `resources` — материалы для развития (заполняется вручную)

| Поле | Тип | Значения |
|---|---|---|
| `category` | TEXT | `course` / `book` / `article` / `tool` / `community` |
| `title` | TEXT | Название |
| `description` | TEXT | Для кого и о чём |
| `url` | TEXT | Ссылка |
| `tags` | TEXT | `python, бесплатно, начинающим` |

## Стек

- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) — Telegram бот
- [Ollama Cloud](https://ollama.com) — языковая модель
- SQLite — база данных
