import sqlite3
from datetime import datetime


def init_db():
    conn = sqlite3.connect("schedules.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            task TEXT,
            time TEXT,
            reminder_minutes INTEGER DEFAULT 5,
            notified INTEGER DEFAULT 0,        -- 通知済みかどうか
            confirmed INTEGER DEFAULT 0,       -- 既読・反応済みかどうか
            repeat INTEGER DEFAULT 0           -- 0:単発, 1:毎週繰り返し
        )
    """)
    conn.commit()
    conn.close()


def add_schedule(user_id, task, time, reminder_minutes, repeat=0):
    conn = sqlite3.connect("schedules.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO schedules (user_id, task, time, reminder_minutes, repeat)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, task, time, reminder_minutes, repeat))
    conn.commit()
    conn.close()


def get_upcoming_schedules():
    conn = sqlite3.connect("schedules.db")
    c = conn.cursor()

    # 現在時刻（比較用）
    now_str = datetime.now().strftime("%Y-%m-%d-%H:%M")

    # 🔥 過去の予定をすべて削除（自動クリーニング）
    c.execute("""
    DELETE FROM schedules
    WHERE time < ?
      AND notified = 1
      AND confirmed = 1
      AND repeat = 0
    """, (now_str,))

    conn.commit()

    # 🔥 未来の予定だけ取得（通知管理も安全）
    c.execute("""
        SELECT id, user_id, task, time, reminder_minutes, notified, confirmed, repeat
        FROM schedules
        WHERE time >= ?
        ORDER BY time ASC
    """, (now_str,))

    rows = c.fetchall()

    conn.close()
    return rows


def mark_notified(schedule_id):
    conn = sqlite3.connect("schedules.db")
    c = conn.cursor()
    c.execute("UPDATE schedules SET notified = 1 WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()


def mark_confirmed(schedule_id):
    conn = sqlite3.connect("schedules.db")
    c = conn.cursor()
    c.execute("UPDATE schedules SET confirmed = 1 WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()


def remove_schedule(schedule_id, user_id):
    conn = sqlite3.connect("schedules.db")
    c = conn.cursor()
    c.execute("DELETE FROM schedules WHERE id = ? AND user_id = ?", (schedule_id, user_id))
    changes = c.rowcount
    conn.commit()
    conn.close()
    return changes > 0
