"""Transparent estimates; not a clinical nutrition engine."""
import math

MACROS = ('protein', 'fat', 'carbs')
FACTORS = {'low': 1.2, 'medium': 1.375, 'high': 1.55}


def number(value, low, high):
    if isinstance(value, bool):
        raise ValueError('Нужно число.')
    value = float(str(value).replace(',', '.'))
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Число должно быть от %s до %s.' % (low, high))
    return value


def target(profile, workout=None):
    """Mifflin–St Jeor; activity excludes exercise; gentle 10% deficit."""
    if profile['age'] < 18 or profile['special'] == 'yes':
        return None
    bmi = profile['weight'] / (profile['height'] / 100) ** 2
    if bmi < 18.5:
        return None
    resting = (10 * profile['weight'] + 6.25 * profile['height']
               - 5 * profile['age'] + (5 if profile['sex'] == 'm' else -161))
    maintenance = resting * FACTORS[profile['activity']]
    extra = 0
    if workout:
        # Net over resting expenditure; METs are coarse intensity categories.
        met = {'light': 3, 'moderate': 5, 'hard': 7}[workout['intensity']]
        extra = (met - 1) * profile['weight'] * workout['minutes'] / 60
    floor = 1500 if profile['sex'] == 'm' else 1200
    base = max(floor, maintenance * .9)
    kcal = round((base + extra * .9) / 10) * 10
    return {'kcal': kcal, 'base': round(base / 10) * 10,
            'extra': round(extra * .9 / 10) * 10,
            'protein': round(kcal * .20 / 4), 'fat': round(kcal * .30 / 9),
            'carbs': round(kcal * .50 / 4)}


def validate_estimate(data):
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('Некорректный ответ распознавания.')
    if len(data['items']) > 15:
        raise ValueError('Слишком много компонентов.')
    for item in data['items']:
        if not isinstance(item.get('name'), str) or not item['name'].strip():
            raise ValueError('Не указано название продукта.')
        item['name'] = item['name'][:100]
        for key in ('grams', 'grams_low', 'grams_high'):
            item[key] = number(item[key], 0, 5000)
        if not item['grams_low'] <= item['grams'] <= item['grams_high']:
            raise ValueError('Некорректный диапазон массы.')
        if item['grams'] <= 0:
            raise ValueError('Масса должна быть больше нуля.')
        for key in MACROS:
            item[key] = number(item[key], 0, item['grams'])
        if sum(item[key] for key in MACROS) > item['grams'] * 1.05:
            raise ValueError('Масса нутриентов больше массы продукта.')
    for key in ('title', 'uncertainty', 'question'):
        if not isinstance(data.get(key), str):
            raise ValueError('Неполный ответ распознавания.')
        data[key] = data[key][:500]
    return data


def totals(items):
    out = {key: sum(i[key] for i in items) for key in MACROS}
    out['kcal'] = 4 * out['protein'] + 9 * out['fat'] + 4 * out['carbs']
    out['grams'] = sum(i['grams'] for i in items)
    return out


def balance(values, daily=False):
    energy = values['kcal']
    if energy <= 0:
        return 'Пока недостаточно данных для оценки баланса.'
    shares = {k: values[k] * (9 if k == 'fat' else 4) / energy for k in MACROS}
    tips = []
    if shares['protein'] < .10:
        tips.append('Доля белка небольшая. Можно добавить рыбу, яйца, творог или бобовые.')
    elif shares['protein'] > .35:
        tips.append('Белок занимает большую долю. Следующий приём можно дополнить крупой и овощами.')
    if shares['fat'] > .35:
        tips.append('Доля жиров повышена. Уточни количество масла и соуса; дальше можно выбрать менее жирный источник белка.')
    elif shares['fat'] < .20:
        tips.append('Жиров пока немного. В течение дня можно добавить орехи или немного растительного масла.')
    if shares['carbs'] < .45:
        tips.append('Углеводов относительно мало. Крупа, картофель, фрукты или бобовые помогут дополнить рацион.')
    elif shares['carbs'] > .65:
        tips.append('Преобладают углеводы. Можно дополнить рацион источником белка и овощами.')
    context = ('Это баланс записанной части дня, а не диагноз дефицита.' if daily else
               'Один приём не обязан быть идеально сбалансирован: важен рацион за день.')
    return ('\n'.join(tips) if tips else 'По долям БЖУ заметного перекоса нет.') + '\n' + context
