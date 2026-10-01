"""Interactive local configuration. Never prints or uploads secrets."""
from getpass import getpass
from pathlib import Path
import os


def main():
    destination = Path(__file__).resolve().parent / '.env'
    if destination.exists():
        raise SystemExit('.env уже существует. Для изменения открой его локально; файл не перезаписан.')
    print('Создай бота через https://t.me/BotFather → /newbot.\n'
          'Ключи вводятся здесь скрыто и сохраняются только в локальный .env.')
    token = getpass('Telegram Bot Token: ').strip()
    key = getpass('OpenAI API key: ').strip()
    uid = input('Твой числовой Telegram user ID: ').strip()
    if ':' not in token or not key or not uid.isdigit() or int(uid) <= 0:
        raise SystemExit('Не все поля заполнены корректно. Файл не создан.')
    if any('\n' in s or '\r' in s for s in (token, key, uid)):
        raise SystemExit('Некорректный ввод.')
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        file.write('TELEGRAM_BOT_TOKEN=' + token + '\nOPENAI_API_KEY=' + key
                   + '\nALLOWED_TELEGRAM_USER_IDS=' + uid + '\nOPENAI_MODEL=gpt-4.1-mini\n')
    print('Настройки сохранены. Запуск: python3 bot.py')


if __name__ == '__main__':
    main()
