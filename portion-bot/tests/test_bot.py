import json
import tempfile
import unittest
from pathlib import Path
from bot import Bot
from nutrition import number, target, totals, validate_estimate
from storage import Store
from vision import ServiceError, Vision
from unittest.mock import patch

PROFILE = {'age': 35, 'sex': 'f', 'height': 165, 'weight': 75,
           'activity': 'low', 'special': 'no', 'palm': 8, 'utc_offset': 7}


def estimate():
    return {'title': 'Обед', 'items': [{'name': 'Рис с рыбой', 'grams': 250,
            'grams_low': 200, 'grams_high': 300, 'protein': 30, 'fat': 10, 'carbs': 40}],
            'uncertainty': 'Количество масла неизвестно.', 'question': ''}


class FakeTelegram:
    def __init__(self):
        self.messages = []

    def send(self, uid, text, buttons=None):
        self.messages.append((uid, text, buttons))

    def call(self, *args, **kwargs):
        return True

    def photo(self, file_id):
        return b'jpeg'


class FakeVision:
    def analyze(self, *args):
        return estimate()


class BotTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = str(Path(self.folder.name) / 'db')
        self.store = Store(self.path)
        self.tg = FakeTelegram()
        self.now = 1790830800
        self.bot = Bot(self.store, self.tg, FakeVision(), {1}, clock=lambda: self.now)
        self.store.put_user(1, {'consent': True, 'profile': PROFILE.copy()})

    def tearDown(self):
        self.store.db.close()
        self.folder.cleanup()

    def message(self, text='', photos=None, mid=10, uid=1):
        msg = {'message_id': mid, 'date': self.now, 'chat': {'id': uid, 'type': 'private'},
               'from': {'id': uid}, 'text': text}
        if photos:
            msg['photo'] = [{'file_id': 'photo'}]
            msg['caption'] = text
        self.bot.handle({'message': msg})

    def click(self, data):
        self.bot.handle({'callback_query': {'id': 'cb', 'from': {'id': 1}, 'data': data,
                         'message': {'chat': {'id': 1, 'type': 'private'}}}})

    def test_photo_confirm_feedback_and_summary(self):
        self.message('Рыба с рисом', photos=True)
        self.assertEqual(self.store.meals(1, 0, self.now + 1), [])
        self.message('Рыба — треска, 150 г', mid=11)
        self.click('save:10')
        meals = self.store.meals(1, 0, self.now + 1)
        self.assertEqual(len(meals), 1)
        mid = meals[0]['id']
        self.click('save:10')
        self.assertEqual(len(self.store.meals(1, 0, self.now + 1)), 1)
        self.click('full:%s' % mid)
        self.click('tasty:%s' % mid)
        self.now += 10800
        self.click('hungry:%s' % mid)
        first = self.store.meal(1, mid)['hungry_at']
        self.now += 600
        self.click('hungry:%s' % mid)
        self.assertEqual(self.store.meal(1, mid)['hungry_at'], first)
        self.message('/today')
        summary = self.tg.messages[-2][1]
        self.assertIn('3 ч 0 мин', summary)
        self.assertIn('вкусно', summary)

    def test_new_meal_prevents_old_hunger(self):
        self.message('Завтрак')
        self.click('save:10')
        mid = self.store.meals(1, 0, self.now + 1)[0]['id']
        self.now += 3600
        self.message('Перекус', mid=12)
        self.click('save:12')
        self.click('hungry:%s' % mid)
        self.assertIsNone(self.store.meal(1, mid)['hungry_at'])
        self.assertIn('у последнего', self.tg.messages[-1][1])

    def test_access_control_and_ownership(self):
        self.message('Еда', uid=2)
        self.assertEqual(self.tg.messages, [])
        other = self.store.save_meal(2, {'at': self.now, 'source_id': 1, 'estimate': estimate()})
        self.click('full:%s' % other)
        self.assertIsNone(self.store.meal(2, other)['fullness'])
        self.click('delete_meal:%s' % other)
        self.assertIsNotNone(self.store.meal(2, other))

    def test_profile_and_restart(self):
        self.message('/profile')
        for value in ('35', 'ж', '165', '75', '1', 'нет', '8', '7'):
            self.message(value)
        self.assertEqual(self.store.user(1)['profile'], PROFILE)
        self.message('Обед')
        second = Store(self.path)
        self.assertIn('draft', second.user(1))
        second.db.close()

    def test_workout_replaces_instead_of_accumulating(self):
        self.message('/workout')
        self.message('средняя 45')
        day = self.bot.local_now(self.store.user(1)).date().isoformat()
        active = target(PROFILE, self.store.workout(1, day))
        self.assertGreater(active['kcal'], target(PROFILE)['kcal'])
        self.message('/workout')
        self.message('нет')
        self.assertEqual(target(PROFILE, self.store.workout(1, day)), target(PROFILE))

    def test_failure_invalidates_previous_estimate(self):
        self.message('Еда')
        def fail(*args):
            raise ServiceError('Временно недоступно')
        self.bot.vision.analyze = fail
        with self.assertRaises(ServiceError):
            self.message('Это другое блюдо')
        self.click('save:10')
        self.assertEqual(self.store.meals(1, 0, self.now + 1), [])
        self.assertIn('draft', self.store.user(1))

    def test_timezone_midnight(self):
        # 18:00 UTC is 01:00 next day at UTC+7; previous local day excluded.
        from datetime import datetime, timezone
        self.now = int(datetime(2026, 10, 1, 18, tzinfo=timezone.utc).timestamp())
        old = estimate()
        old['title'] = 'Вчерашний ужин'
        self.store.save_meal(1, {'at': self.now - 7200, 'source_id': 1, 'estimate': old})
        self.message('/today')
        self.assertIn('02.10', self.tg.messages[-1][1])
        self.assertNotIn('Вчерашний', self.tg.messages[-1][1])

    def test_delete_requires_current_confirmation(self):
        self.message('Еда')
        self.click('save:10')
        self.click('erase:12')
        self.assertTrue(self.store.user(1))
        self.message('/delete', mid=12)
        self.click('erase:12')
        self.assertEqual(self.store.user(1), {})
        self.assertEqual(self.store.meals(1, 0, self.now + 1), [])


class NutritionTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(totals(estimate()['items'])['kcal'], 370)
        self.assertEqual(target(PROFILE)['base'], 1560)

    def test_out_of_scope_profiles(self):
        for change in ({'age': 16}, {'special': 'yes'}, {'weight': 45}):
            self.assertIsNone(target({**PROFILE, **change}))

    def test_nonfinite_and_impossible_values(self):
        for value in ('nan', 'inf', '-1', True):
            with self.assertRaises(ValueError):
                number(value, 0, 100)
        data = estimate()
        data['items'][0]['protein'] = 500
        with self.assertRaises(ValueError):
            validate_estimate(data)

    def test_response_contract_and_no_profile_leak(self):
        captured = {}
        def post(url, payload, headers):
            captured.update(payload)
            return {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': json.dumps(estimate())}]}]}
        with patch('vision.post_json', post):
            result = Vision('test-key').analyze(b'jpeg', 'Треска', 8)
        self.assertEqual(result['title'], 'Обед')
        self.assertFalse(captured['store'])
        self.assertTrue(captured['text']['format']['strict'])
        content = captured['input'][0]['content']
        self.assertTrue(content[1]['image_url'].startswith('data:image/jpeg;base64,'))
        self.assertEqual(set(json.loads(content[0]['text'])), {'description', 'palm_width_cm'})


if __name__ == '__main__':
    unittest.main()
