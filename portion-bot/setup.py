"""Interactive local configuration. Never prints or uploads secrets."""
from getpass import getpass
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile


def ask_valid(prompt, validator, hint, secret=False, clipboard=False):
    while True:
        if secret and clipboard:
            getpass(prompt + 'Скопируй ключ, затем нажми Enter здесь (не вставляй его): ')
            try:
                value = subprocess.run(['/usr/bin/pbpaste'], check=True,
                                       capture_output=True, text=True).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                print('Не удалось прочитать буфер обмена. Попробуй ещё раз.')
                continue
        else:
            value = (getpass(prompt) if secret else input(prompt)).strip()
        if validator(value):
            print('Формат принят. Работоспособность проверим при подключении.')
            return value
        print(hint + ' Повтори ввод этого поля. Для выхода: Control+C.')


def update_telegram(destination):
    if not destination.exists():
        raise SystemExit('Сначала выполни обычную настройку.')
    token = ask_valid('Новый Telegram Bot Token: ',
                      lambda s: re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', s),
                      'Нужен полный токен от BotFather.', True, '--clipboard' in sys.argv)
    lines = destination.read_text().splitlines()
    lines = [line for line in lines if not line.startswith('TELEGRAM_BOT_TOKEN=')]
    lines.append('TELEGRAM_BOT_TOKEN=' + token)
    fd, temporary = tempfile.mkstemp(prefix='.env-', dir=str(destination.parent))
    try:
        with os.fdopen(fd, 'w') as file:
            file.write('\n'.join(lines) + '\n')
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Токен Telegram обновлён. Остальные настройки сохранены. Запуск: python3 bot.py')


def main():
    destination = Path(__file__).resolve().parent / '.env'
    if '--update-telegram' in sys.argv:
        update_telegram(destination)
        return
    if destination.exists():
        raise SystemExit('.env уже существует. Для изменения открой его локально; файл не перезаписан.')
    print('Создай бота через https://t.me/BotFather → /newbot.\n'
          'Ключи вводятся здесь скрыто и сохраняются только в локальный .env.')
    clipboard = '--clipboard' in sys.argv
    if clipboard:
        print('Режим буфера обмена: ключи не вставляй. Копируй нужный ключ и нажимай Enter.\n'
              'Буфер читается только после Enter; ключи не выводятся на экран и не отправляются в сеть.')
    else:
        print('При вставке ключей символы не видны. Вставь один раз и нажми Enter.')
    token = ask_valid('Telegram Bot Token: ',
                      lambda s: re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', s),
                      'Нужен полный токен от BotFather: цифры, двоеточие и секретная часть.', True, clipboard)
    key = ask_valid('OpenAI API key: ',
                    lambda s: re.fullmatch(r'sk-[A-Za-z0-9_-]+', s),
                    'Нужен полный секретный ключ OpenAI, начинающийся с sk-, без пробелов.', True, clipboard)
    uid = ask_valid('Твой числовой Telegram user ID: ',
                    lambda s: bool(re.fullmatch(r'[0-9]+', s)) and int(s) > 0,
                    'ID должен содержать только цифры, без букв, подписи Id и знака @.')
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        file.write('TELEGRAM_BOT_TOKEN=' + token + '\nOPENAI_API_KEY=' + key
                   + '\nALLOWED_TELEGRAM_USER_IDS=' + uid + '\nOPENAI_MODEL=gpt-4.1-mini\n')
    print('Настройки сохранены. Запуск: python3 bot.py')


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nВвод отменён. Настройки не сохранены.')
