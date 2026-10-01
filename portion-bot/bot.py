#!/usr/bin/env python3
"""Private Telegram portion diary. Python 3.9+, standard library only."""
import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen
from nutrition import number, totals, target, balance
from storage import Store
from vision import Vision, ServiceError, post_json

ROOT = Path(__file__).resolve().parent
QUESTIONS = [
    ('age', 'Сколько тебе лет?'),
    ('sex', 'Какой вариант формулы обмена использовать? Напиши «ж» или «м».'),
    ('height', 'Рост в сантиметрах?'),
    ('weight', 'Вес в килограммах?'),
    ('activity', 'Активность БЕЗ тренировок: 1 — преимущественно сижу; 2 — регулярно хожу; 3 — много двигаюсь или физическая работа.'),
    ('special', 'Нужен индивидуальный план питания (например, беременность, кормление или назначенная врачом диета)? Да / нет. При «да» оставлю дневник без автоматического дефицита.'),
    ('palm', 'Ширина ладони без большого пальца в сантиметрах? Можно написать «пропустить». Это поможет оценке масштаба.'),
    ('utc_offset', 'Часовой пояс: смещение от UTC, например 7 для Новокузнецка, 3 для Москвы.')]
HELP = ('🍽 Пришли фото тарелки с ладонью рядом и, по желанию, подписью. '
        'Ладонь и тарелку лучше держать в одной плоскости. Укажи масло, соусы и способ приготовления. '
        'Можно прислать только описание с массой. После оценки напиши уточнение или сохрани порцию.\n\n'
        '/today — баланс и дневник сегодня\n/workout — тренировка сегодня\n'
        '/profile — заполнить анкету заново\n/time ЧЧ:ММ — время еды до сохранения\n'
        '/cancel — отменить текущий ввод\n/privacy — хранение данных\n/delete — удалить мои данные')
PRIVACY = ('Анкета, состав еды, БЖУ и отметки хранятся в локальной базе владельца бота. '
           'Фото и описание отправляются в OpenAI для оценки; рост, вес и возраст туда не передаются. '
           'Ширина ладони передаётся, если указана. Исходные фото на диске бота не сохраняются, '
           'но остаются в Telegram. OpenAI может хранить данные по правилам API; store=false '
           'не означает отсутствие всех служебных журналов. /delete удаляет данные из активной базы бота, '
           'но не сообщения Telegram, резервные копии или данные у провайдера.')


def load_env():
    file = ROOT / '.env'
    if file.exists():
        for line in file.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


def keyboard(rows):
    return {'inline_keyboard': [[{'text': text, 'callback_data': data} for text, data in row] for row in rows]}


def meal_buttons(mid):
    return keyboard([[('Наелась', 'full:%s' % mid), ('Не наелась', 'notfull:%s' % mid)],
                     [('Проголодалась', 'hungry:%s' % mid)],
                     [('Вкусно', 'tasty:%s' % mid), ('Не вкусно', 'untasty:%s' % mid)],
                     [('Удалить запись', 'remove:%s' % mid)]])


class Telegram:
    def __init__(self, token):
        self.base = 'https://api.telegram.org/bot' + token + '/'
        self.file_base = 'https://api.telegram.org/file/bot' + token + '/'

    def call(self, method, **data):
        result = post_json(self.base + method, data)
        if not result.get('ok'):
            raise ServiceError('Telegram не выполнил запрос.')
        return result['result']

    def send(self, uid, text, buttons=None):
        data = {'chat_id': uid, 'text': text[:4000]}
        if buttons:
            data['reply_markup'] = buttons
        return self.call('sendMessage', **data)

    def photo(self, file_id):
        info = self.call('getFile', file_id=file_id)
        if info.get('file_size', 0) > 10 * 1024 * 1024:
            raise ServiceError('Фото слишком большое. Отправь его как обычное фото Telegram.')
        try:
            with urlopen(self.file_base + info['file_path'], timeout=30) as response:
                data = response.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                raise ValueError()
            return data
        except Exception:
            raise ServiceError('Не удалось загрузить фото. Отправь его ещё раз.') from None


class Bot:
    def __init__(self, store, telegram, vision, allowed, clock=time.time):
        self.store, self.tg, self.vision = store, telegram, vision
        self.allowed, self.clock = allowed, clock

    def local_now(self, user):
        return datetime.fromtimestamp(self.clock(), timezone(timedelta(hours=user.get('profile', {}).get('utc_offset', 7))))

    def estimate_text(self, draft):
        estimate = draft['estimate']
        if not estimate['items']:
            return 'Не удалось распознать еду. ' + estimate['question'] + '\nНапиши уточнение.'
        value = totals(estimate['items'])
        lines = ['🍽 ' + estimate['title'], 'Приблизительная оценка, не взвешивание:']
        for item in estimate['items']:
            lines.append('• %s: ≈%g г (ориентир %g–%g г)' % (item['name'], round(item['grams']), round(item['grams_low']), round(item['grams_high'])))
        lines += ['\nБ ≈%.0f г · Ж ≈%.0f г · У ≈%.0f г' % tuple(value[k] for k in ('protein', 'fat', 'carbs')),
                  'Энергия ≈%.0f ккал · всего ≈%.0f г' % (value['kcal'], value['grams']),
                  '\n' + balance(value), '\n' + estimate['uncertainty']]
        if estimate['question']:
            lines.append(estimate['question'])
        lines.append('\nМожно уточнить состав или граммы сообщением. Время еды: /time ЧЧ:ММ. В дневник попадёт только после сохранения.')
        return '\n'.join(lines)

    def analyze(self, uid, user):
        draft = user['draft']
        self.tg.send(uid, 'Рассматриваю порцию…')
        image = self.tg.photo(draft['file_id']) if draft.get('file_id') else None
        # Preserve draft on failures, but invalidate any previous estimate.
        draft.pop('estimate', None)
        self.store.put_user(uid, user)
        draft['estimate'] = self.vision.analyze(image, draft['description'], user['profile'].get('palm'))
        self.store.put_user(uid, user)
        buttons = [[('Сохранить порцию', 'save:%s' % draft['source_id'])]] if draft['estimate']['items'] else []
        buttons.append([('Отменить', 'cancel:%s' % draft['source_id'])])
        self.tg.send(uid, self.estimate_text(draft), keyboard(buttons))

    def summary(self, uid, user):
        now = self.local_now(user)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        meals = self.store.meals(uid, int(start.timestamp()), int((start + timedelta(days=1)).timestamp()))
        workout = self.store.workout(uid, now.date().isoformat())
        plan = target(user['profile'], workout)
        items = [i for m in meals for i in json.loads(m['data'])['items']]
        value = totals(items)
        lines = ['🌿 Сегодня · ' + now.strftime('%d.%m'),
                 'Б ≈%.0f г · Ж ≈%.0f г · У ≈%.0f г' % tuple(value[k] for k in ('protein', 'fat', 'carbs'))]
        if plan:
            lines += ['Ориентир Б/Ж/У: %s / %s / %s г' % tuple(plan[k] for k in ('protein', 'fat', 'carbs')),
                      'Энергия записанной еды ≈%.0f ккал; ориентир дня ≈%s ккал.' % (value['kcal'], plan['kcal']),
                      'Тренировка: прибавка ≈%s ккал. Это расчётный ориентир, не жёсткий лимит.' % plan['extra']]
        else:
            lines.append('Энергия записанной еды ≈%.0f ккал. Автоматическая цель снижения веса отключена: нужен индивидуальный ориентир.' % value['kcal'])
        lines.append('\n' + balance(value, daily=True))
        if not meals:
            lines.append('\nПока нет сохранённых приёмов пищи. Пришли фото или описание.')
        for m in meals:
            title = json.loads(m['data'])['title']
            stamp = datetime.fromtimestamp(m['at'], now.tzinfo).strftime('%H:%M')
            tags = []
            if m['fullness']:
                tags.append('наелась' if m['fullness'] == 'full' else 'не наелась')
            if m['taste']:
                tags.append('вкусно' if m['taste'] == 'tasty' else 'не вкусно')
            if m['hungry_at'] is not None:
                minutes = (m['hungry_at'] - m['at']) // 60
                tags.append('голод через %s ч %s мин' % divmod(minutes, 60))
            lines.append('\n%s · %s%s' % (stamp, title, ' — ' + ', '.join(tags) if tags else ''))
        self.tg.send(uid, '\n'.join(lines))
        if meals:
            self.tg.send(uid, 'Отметки для последнего приёма пищи:', meal_buttons(meals[-1]['id']))

    def profile_answer(self, uid, user, text):
        index = user['step']
        key = QUESTIONS[index][0]
        answer = text.strip().lower()
        try:
            bounds = {'age': (1, 110), 'height': (100, 230), 'weight': (25, 350), 'utc_offset': (-12, 14)}
            if key in bounds:
                value = number(answer, *bounds[key])
                if key == 'age' and not value.is_integer():
                    raise ValueError('Возраст укажи целым числом.')
            elif key == 'sex':
                value = {'ж': 'f', 'м': 'm'}[answer]
            elif key == 'activity':
                value = {'1': 'low', '2': 'medium', '3': 'high'}[answer]
            elif key == 'special':
                value = {'да': 'yes', 'нет': 'no'}[answer]
            else:
                value = None if answer == 'пропустить' else number(answer, 4, 15)
        except (ValueError, KeyError):
            self.tg.send(uid, 'Проверь ответ. ' + QUESTIONS[index][1])
            return
        user.setdefault('profile_edit', {})[key] = value
        user['step'] += 1
        if user['step'] == len(QUESTIONS):
            user['profile'] = user.pop('profile_edit')
            user.pop('step')
            self.store.put_user(uid, user)
            self.tg.send(uid, 'Анкета готова. Цель — постепенное снижение веса, основной фокус — баланс и сытость.\n\n' + HELP)
            self.summary(uid, user)
        else:
            self.store.put_user(uid, user)
            self.tg.send(uid, QUESTIONS[user['step']][1])

    def callback(self, uid, user, cb):
        self.tg.call('answerCallbackQuery', callback_query_id=cb['id'])
        parts = cb.get('data', '').split(':', 1)
        action, ident = parts[0], parts[1] if len(parts) > 1 else ''
        if action == 'agree':
            if user.get('consent'):
                self.tg.send(uid, 'Согласие уже сохранено. /profile — анкета, /help — действия.')
                return
            user['consent'] = True
            user['step'] = 0
            user.pop('profile_edit', None)
            self.store.put_user(uid, user)
            self.tg.send(uid, QUESTIONS[0][1])
            return
        if not user.get('consent'):
            return
        if action == 'erase':
            if ident != user.get('erase_nonce'):
                return
            self.store.erase(uid)
            self.tg.send(uid, 'Данные удалены из активной базы бота. Чтобы начать заново: /start.')
            return
        if action in ('save', 'cancel'):
            draft = user.get('draft')
            if not draft or str(draft['source_id']) != ident:
                self.tg.send(uid, 'Эта кнопка уже неактуальна. Открой /today.')
                return
            if action == 'save':
                if not draft.get('estimate', {}).get('items'):
                    self.tg.send(uid, 'Сначала нужно уточнить и оценить порцию.')
                    return
                mid = self.store.save_meal(uid, draft)
                user.pop('draft')
                self.store.put_user(uid, user)
                self.tg.send(uid, 'Порция сохранена. Как ощущения после еды?', meal_buttons(mid))
            else:
                user.pop('draft')
                self.store.put_user(uid, user)
                self.tg.send(uid, 'Порция отменена.')
            return
        if not ident.isdigit():
            return
        mid = int(ident)
        if action == 'remove':
            self.tg.send(uid, 'Удалить этот приём из дневника?', keyboard([[('Удалить', 'delete_meal:%s' % mid)]]))
        elif action == 'delete_meal':
            self.store.delete_meal(uid, mid)
            self.tg.send(uid, 'Запись удалена.')
        else:
            self.tg.send(uid, self.store.feedback(uid, mid, action, int(self.clock())))

    def handle(self, update):
        cb = update.get('callback_query')
        msg = cb.get('message', {}) if cb else update.get('message', {})
        sender = cb.get('from', {}) if cb else msg.get('from', {})
        uid = sender.get('id')
        if uid not in self.allowed or msg.get('chat', {}).get('type') != 'private' or msg['chat']['id'] != uid:
            return
        user = self.store.user(uid)
        if cb:
            self.callback(uid, user, cb)
            return
        text = msg.get('text', '').strip()
        command = text.split()[0].split('@')[0] if text.startswith('/') else ''
        if command == '/privacy':
            self.tg.send(uid, PRIVACY)
            return
        if command in ('/start', '/help') or not user.get('consent'):
            if user.get('consent') and user.get('profile'):
                self.tg.send(uid, HELP)
            else:
                self.tg.send(uid, 'Привет! Я помогу наблюдать баланс еды, порции и сытость.\n\n' + PRIVACY,
                             keyboard([[('Согласна, начать', 'agree')]]))
            return
        if command == '/delete':
            user['erase_nonce'] = str(msg['message_id'])
            self.store.put_user(uid, user)
            self.tg.send(uid, 'Удалить анкету, дневник и тренировки из базы бота?', keyboard([[('Удалить мои данные', 'erase:' + user['erase_nonce'])]]))
            return
        if command == '/cancel':
            for k in ('draft', 'step', 'profile_edit', 'await_workout', 'erase_nonce'):
                user.pop(k, None)
            self.store.put_user(uid, user)
            self.tg.send(uid, 'Текущий ввод отменён. /today — дневник, /profile — анкета.')
            return
        if command == '/profile':
            user['step'] = 0
            user.pop('profile_edit', None)
            self.store.put_user(uid, user)
            self.tg.send(uid, QUESTIONS[0][1])
            return
        if 'step' in user:
            self.profile_answer(uid, user, text)
            return
        if 'profile' not in user:
            self.tg.send(uid, 'Сначала заполни анкету: /profile.')
            return
        if command == '/today':
            self.summary(uid, user)
            return
        if command == '/workout':
            user['await_workout'] = True
            self.store.put_user(uid, user)
            self.tg.send(uid, 'Тренировка сегодня: напиши «лёгкая 30», «средняя 45» или «интенсивная 60» (минуты). '
                         '«нет» — день без тренировки. Запись заменяет тренировку за сегодня. '
                         'Не включай прогулки, уже учтённые в повседневной активности.')
            return
        if command == '/time':
            if 'draft' not in user:
                self.tg.send(uid, 'Сначала пришли фото или описание еды.')
                return
            try:
                hour, minute = map(int, text.split()[1].split(':'))
                now = self.local_now(user)
                at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if at > now:
                    raise ValueError()
            except (ValueError, IndexError):
                self.tg.send(uid, 'Укажи время сегодня, не в будущем: /time 13:30.')
                return
            user['draft']['at'] = int(at.timestamp())
            self.store.put_user(uid, user)
            self.tg.send(uid, 'Время еды изменено на ' + at.strftime('%H:%M') + '. Теперь можно сохранить порцию.')
            return
        if command:
            self.tg.send(uid, 'Не знаю эту команду. /help — список действий.')
            return
        if user.get('await_workout'):
            try:
                if text.lower() == 'нет':
                    workout = {'intensity': 'light', 'minutes': 0}
                else:
                    level, minutes = text.lower().split()
                    intensity = {'легкая': 'light', 'лёгкая': 'light', 'средняя': 'moderate', 'интенсивная': 'hard'}[level]
                    workout = {'intensity': intensity, 'minutes': number(minutes, 1, 180)}
            except (KeyError, ValueError):
                self.tg.send(uid, 'Например: средняя 45. Или «нет». /cancel — отменить.')
                return
            self.store.workout(uid, self.local_now(user).date().isoformat(), workout)
            user.pop('await_workout')
            self.store.put_user(uid, user)
            self.summary(uid, user)
            return
        photos = msg.get('photo')
        if photos and user.get('draft'):
            self.tg.send(uid, 'Есть несохранённая порция. Сохрани её или нажми /cancel, затем пришли новое фото.')
            return
        if photos:
            user['draft'] = {'file_id': photos[-1]['file_id'], 'description': msg.get('caption', ''),
                             'at': msg['date'], 'source_id': msg['message_id']}
        elif text:
            if user.get('draft'):
                user['draft']['description'] = (user['draft']['description'] + '\nУточнение: ' + text)[-6000:]
            else:
                user['draft'] = {'description': text, 'at': msg['date'], 'source_id': msg['message_id']}
        else:
            self.tg.send(uid, 'Пришли обычное фото Telegram или текстовое описание еды.')
            return
        self.store.put_user(uid, user)
        self.analyze(uid, user)


def main():
    load_env()
    required = ('TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY', 'ALLOWED_TELEGRAM_USER_IDS')
    if any(not os.getenv(k) for k in required):
        raise SystemExit('Сначала выполни python3 setup.py. Секреты не присылай в чат.')
    # Apply restrictive permissions to SQLite auxiliary files as well.
    os.umask(0o077)
    try:
        allowed = {int(s.strip()) for s in os.environ['ALLOWED_TELEGRAM_USER_IDS'].split(',')}
        if not allowed or any(x <= 0 for x in allowed):
            raise ValueError()
    except ValueError:
        raise SystemExit('ALLOWED_TELEGRAM_USER_IDS должен содержать числовые ID через запятую.')
    data_dir = ROOT / 'data'
    data_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(data_dir, 0o700)
    store = Store(str(data_dir / 'diary.sqlite3'))
    os.chmod(data_dir / 'diary.sqlite3', 0o600)
    tg = Telegram(os.environ['TELEGRAM_BOT_TOKEN'])
    bot = Bot(store, tg, Vision(os.environ['OPENAI_API_KEY'], os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')), allowed)
    tg.call('getMe')
    webhook = tg.call('getWebhookInfo')
    if webhook.get('url'):
        raise SystemExit('У этого бота уже подключён webhook. Используй отдельного бота или отключи webhook перед запуском.')
    print('Бот запущен. Для остановки: Ctrl+C. Данные и ключи не выводятся в журнал.')
    while True:
        try:
            updates = tg.call('getUpdates', offset=store.offset(), timeout=25,
                              allowed_updates=['message', 'callback_query'])
            for update in updates:
                try:
                    bot.handle(update)
                except ServiceError as exc:
                    msg = update.get('message') or update.get('callback_query', {}).get('message', {})
                    uid = msg.get('chat', {}).get('id')
                    if uid in allowed:
                        try:
                            tg.send(uid, str(exc) + ' Черновик сохранён. Напиши уточнение для повторного анализа.')
                        except ServiceError:
                            pass
                except Exception as exc:
                    # Do not print payload, traceback, HTTP URLs or secrets.
                    print('Ошибка обработки:', type(exc).__name__)
                store.offset(update['update_id'] + 1)
        except ServiceError:
            print('Связь недоступна; повтор через 5 секунд.')
            time.sleep(5)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nБот остановлен.')
