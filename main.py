import ollama
import telebot
import os
# Initialize the Ollama client
ollama_client = ollama.Client()
# Initialize the Telegram bot with your bot token
bot_token = 'YOUR_TELEGRAM_BOT_TOKEN'
bot = telebot.TeleBot(bot_token)

stream = ollama_client.chat(
  model='qwen3',
  messages=[{'role': 'user', 'content': 'What is 17 × 23?'}],
  stream=True,
)