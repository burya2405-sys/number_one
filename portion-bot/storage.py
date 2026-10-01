import json
import sqlite3


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS meals(
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
            source_id INTEGER NOT NULL, at INTEGER NOT NULL, data TEXT NOT NULL,
            fullness TEXT, taste TEXT, hungry_at INTEGER,
            UNIQUE(user_id,source_id));
        CREATE INDEX IF NOT EXISTS meals_by_user_time ON meals(user_id,at);
        CREATE TABLE IF NOT EXISTS workouts(
            user_id INTEGER, day TEXT, data TEXT, PRIMARY KEY(user_id,day));
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
        ''')

    def user(self, uid):
        row = self.db.execute('SELECT data FROM users WHERE id=?', (uid,)).fetchone()
        return json.loads(row[0]) if row else {}

    def put_user(self, uid, data):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO users VALUES (?,?)',
                            (uid, json.dumps(data, ensure_ascii=False)))

    def save_meal(self, uid, draft):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO meals(user_id,source_id,at,data) VALUES (?,?,?,?)',
                            (uid, draft['source_id'], draft['at'], json.dumps(draft['estimate'], ensure_ascii=False)))
        return self.db.execute('SELECT id FROM meals WHERE user_id=? AND source_id=?',
                               (uid, draft['source_id'])).fetchone()[0]

    def meal(self, uid, mid):
        row = self.db.execute('SELECT * FROM meals WHERE user_id=? AND id=?', (uid, mid)).fetchone()
        return dict(row) if row else None

    def meals(self, uid, start, end):
        return [dict(r) for r in self.db.execute(
            'SELECT * FROM meals WHERE user_id=? AND at>=? AND at<? ORDER BY at,id', (uid, start, end))]

    def feedback(self, uid, mid, action, now):
        meal = self.meal(uid, mid)
        if not meal:
            return 'Запись не найдена.'
        if action == 'hungry':
            if meal['hungry_at'] is not None:
                now = meal['hungry_at']
            else:
                newer = self.db.execute('SELECT 1 FROM meals WHERE user_id=? AND (at>? OR (at=? AND id>?))',
                                        (uid, meal['at'], meal['at'], mid)).fetchone()
                if newer:
                    return 'После этого приёма уже была еда. Нажми «Проголодалась» у последнего приёма.'
                if now < meal['at']:
                    return 'Время приёма ещё не наступило.'
                with self.db:
                    self.db.execute('UPDATE meals SET hungry_at=? WHERE id=? AND user_id=?', (now, mid, uid))
            minutes = int((now - meal['at']) // 60)
            return 'Голод отмечен через %s ч %s мин после еды. Это время до отметки, а не точное измерение сытости.' % divmod(minutes, 60)
        fields = {'full': ('fullness', 'full'), 'notfull': ('fullness', 'notfull'),
                  'tasty': ('taste', 'tasty'), 'untasty': ('taste', 'untasty')}
        if action not in fields:
            return 'Неизвестная отметка.'
        field, value = fields[action]
        with self.db:
            self.db.execute('UPDATE meals SET ' + field + '=? WHERE user_id=? AND id=?', (value, uid, mid))
        return {'full': 'Записала: наелась.', 'notfull': 'Записала: не наелась. Можно добавить еды, ориентируясь на голод.',
                'tasty': 'Записала: вкусно.', 'untasty': 'Записала: не вкусно.'}[action]

    def workout(self, uid, day, value=None):
        if value is not None:
            with self.db:
                self.db.execute('INSERT OR REPLACE INTO workouts VALUES (?,?,?)', (uid, day, json.dumps(value)))
        row = self.db.execute('SELECT data FROM workouts WHERE user_id=? AND day=?', (uid, day)).fetchone()
        return json.loads(row[0]) if row else None

    def delete_meal(self, uid, mid):
        with self.db:
            self.db.execute('DELETE FROM meals WHERE user_id=? AND id=?', (uid, mid))

    def erase(self, uid):
        with self.db:
            for table in ('meals', 'workouts'):
                self.db.execute('DELETE FROM ' + table + ' WHERE user_id=?', (uid,))
            self.db.execute('DELETE FROM users WHERE id=?', (uid,))

    def offset(self, value=None):
        if value is not None:
            with self.db:
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('offset', str(value)))
        row = self.db.execute('SELECT value FROM meta WHERE key=?', ('offset',)).fetchone()
        return int(row[0]) if row else 0
