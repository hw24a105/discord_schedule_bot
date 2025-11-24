import discord
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, timedelta
import os
import asyncio
from dotenv import load_dotenv
import database  # database.py を別ファイルで用意
import re
from datetime import datetime, timedelta
import jaconv

# -----------------------------
# 📅 自然言語 → 日付パーサー
# -----------------------------
def parse_datetime(text: str) -> datetime:
    text = jaconv.z2h(text, digit=True, ascii=True)  # 全角→半角
    text = text.strip()

    now = datetime.now()

    # -----------------------------
    # ★ 日本語の時間表現（11時 / 11時30分 / 午後3時）
    # -----------------------------
    pm = False
    # 午前午後対応
    if "午後" in text or "PM" in text.upper():
        pm = True
        text = text.replace("午後", "").replace("PM", "")
    if "午前" in text or "AM" in text.upper():
        text = text.replace("午前", "").replace("AM", "")

    # 11時30分 / 11時30
    m = re.search(r"(\d{1,2})時(\d{1,2})分?", text)
    if m:
        h = int(m.group(1))
        mm = int(m.group(2))
        if pm and h < 12:
            h += 12
        return now.replace(hour=h, minute=mm, second=0, microsecond=0)

    # 11時
    m = re.search(r"(\d{1,2})時", text)
    if m:
        h = int(m.group(1))
        if pm and h < 12:
            h += 12
        return now.replace(hour=h, minute=0, second=0, microsecond=0)

    # -----------------------------
    # 今日
    # -----------------------------
    if text.startswith("今日"):
        m = re.search(r"(\d{1,2}):(\d{1,2})", text)
        if m:
            h, mm = map(int, m.groups())
            return now.replace(hour=h, minute=mm)

    # 明日
    if text.startswith("明日"):
        m = re.search(r"(\d{1,2}):(\d{1,2})", text)
        if m:
            h, mm = map(int, m.groups())
            return (now + timedelta(days=1)).replace(hour=h, minute=mm)

    # あさって
    if text.startswith("あさって"):
        m = re.search(r"(\d{1,2}):(\d{1,2})", text)
        if m:
            h, mm = map(int, m.groups())
            return (now + timedelta(days=2)).replace(hour=h, minute=mm)

    # -----------------------------
    # 来週の〇曜
    # -----------------------------
    youbi = ["月", "火", "水", "木", "金", "土", "日"]
    m = re.search(r"来週の([月火水木金土日])曜?", text)
    if m:
        target = youbi.index(m.group(1))
        today = now.weekday()  # 月0〜日6
        days_ahead = (7 + target - today) % 7 + 7

        t = re.search(r"(\d{1,2}):(\d{1,2})", text)
        if t:
            h, mm = map(int, t.groups())
            return (now + timedelta(days=days_ahead)).replace(hour=h, minute=mm)

    # -----------------------------
    # MM/DD HH:MM
    # -----------------------------
    m = re.match(r"(\d{1,2})/(\d{1,2}) (\d{1,2}):(\d{1,2})", text)
    if m:
        month, day, h, mm = map(int, m.groups())
        year = now.year
        return datetime(year, month, day, h, mm)

    # YYYY/MM/DD HH:MM
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2}) (\d{1,2}):(\d{1,2})", text)
    if m:
        year, month, day, h, mm = map(int, m.groups())
        return datetime(year, month, day, h, mm)

    # -----------------------------
    # 時刻だけ（今日扱い） → 11:00、23:59
    # -----------------------------
    m = re.match(r"(\d{1,2}):(\d{1,2})$", text)
    if m:
        h, mm = map(int, m.groups())
        return now.replace(hour=h, minute=mm)

    # -----------------------------
    # どれにも当てはまらない
    # -----------------------------
    return None


# -----------------------------
# ⚙️ 初期設定
# -----------------------------
load_dotenv()  # .env から BOTトークン読み込み
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # DMでの「OK」応答に必要
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

database.init_db()  # DB初期化

# -----------------------------
# 🔔 Bot起動時処理
# -----------------------------
@bot.event
async def on_ready():
    print(f"✅ ログイン完了：{bot.user}")
    
    # グローバル同期
    await tree.sync()
    
    # 定期タスク開始
    reminder_check.start()

# -----------------------------
# 📅 /add コマンド（自然言語対応版）
# -----------------------------
@tree.command(name="add", description="予定を追加します")
@discord.app_commands.describe(
    datetime_str="日時（例: 今日 12:00 / 明日 18:00 / 11/20 15:00 など）",
    task="予定内容",
    reminder="通知する何分前か",
    repeat="毎週繰り返すかどうか"
)
async def add_cmd(interaction: discord.Interaction, datetime_str: str, task: str, reminder: int = 5, repeat: bool = False):

    # 🔽 parse_datetime で自然言語→日時に変換
    dt = parse_datetime(datetime_str)
    if dt is None:
        await interaction.response.send_message("⛔ 日付の形式が読み取れませんでした。", ephemeral=True)
        return

    time_str = dt.strftime("%Y-%m-%d-%H:%M")

    # --- ここから下はそのまま ---
    database.add_schedule(interaction.user.id, task, time_str, reminder, int(repeat))

    await interaction.response.send_message(
        f"📅 予定を登録しました！\n"
        f"🕒 {time_str}\n"
        f"📝 {task}\n"
        f"🔔 通知：{reminder}分前\n"
        f"🔁 繰り返し：{'あり' if repeat else 'なし'}"
    )

# -----------------------------
# 📋 /list コマンド（最終美しい版）
# -----------------------------
@tree.command(name="list", description="登録済みの予定をカード形式で表示します")
async def list_cmd(interaction: discord.Interaction):
    schedules = [
        s for s in database.get_upcoming_schedules()
        if str(s[1]) == str(interaction.user.id)
    ]

    if not schedules:
        await interaction.response.send_message("🗓️ 予定はありません！")
        return

    embed = discord.Embed(
        title="📅 あなたの予定一覧",
        description="登録されている予定をカード形式で表示します。",
        color=0x00bfff
    )

    # 日付順に並べ替え
    schedules.sort(key=lambda s: datetime.strptime(s[3], "%Y-%m-%d-%H:%M"))

    for i, s in enumerate(schedules):
        _, _, task, time_str, reminder, _, _, repeat = s
        repeat_text = "毎週" if repeat == 1 else "なし"

        value = (
            f"🕒 **{time_str}**\n"
            f"🔔 **{reminder}分前**\n"
            f"🔁 **{repeat_text}**\n"
        )

        # 予定カード追加
        embed.add_field(
            name=f"📝 **{task}**",
            value=value,
            inline=False
        )

        # ─────────────── 区切り線（中央寄せ）
        if i < len(schedules) - 1:
            embed.add_field(
                name="​",  # ← 絶対に消さない（空白文字）
                value="`───────────────`",
                inline=False
            )

    await interaction.response.send_message(embed=embed)

# -----------------------------
# 🗑 /remove コマンド
# -----------------------------
@tree.command(name="remove", description="登録済みの予定を削除します（予定名を選択）")
@app_commands.describe(task_name="削除したい予定の名前を選んでください")
async def remove(interaction: discord.Interaction, task_name: str):
    schedules = [s for s in database.get_upcoming_schedules() if str(s[1]) == str(interaction.user.id)]
    target = next((s for s in schedules if s[2] == task_name), None)

    if not target:
        await interaction.response.send_message("❌ 指定した予定が見つかりません。", ephemeral=True)
        return

    success = database.remove_schedule(target[0], str(interaction.user.id))
    if success:
        await interaction.response.send_message(f"🗑 予定 **{task_name}** を削除しました。")
    else:
        await interaction.response.send_message("❌ 削除に失敗しました。", ephemeral=True)

# 🔍 自動補完
@remove.autocomplete("task_name")
async def task_name_autocomplete(interaction: discord.Interaction, current: str):
    schedules = [s for s in database.get_upcoming_schedules() if str(s[1]) == str(interaction.user.id)]
    choices = [app_commands.Choice(name=s[2], value=s[2]) for s in schedules if current.lower() in s[2].lower()]
    return choices[:25]

# -----------------------------
# ℹ️ /help コマンド
# -----------------------------
@tree.command(name="help", description="Botの操作説明を表示します")
async def help_cmd(interaction: discord.Interaction):
    help_text = (
        "📌 **予定管理Bot 操作説明** 📌\n\n"
        "1️⃣ **/add** - 予定を追加\n"
        "   例: `/add 2025-11-10-12:00 ミーティング 10 true`\n"
        "2️⃣ **/list** - 登録済みの予定一覧を表示\n"
        "3️⃣ **/remove** - 登録済みの予定を削除\n"
        "💬 DMで『OK』と返信すると通知確認済みにできます。\n"
        "⏰ 繰り返し予定は毎週自動で追加されます。"
    )
    await interaction.response.send_message(help_text, ephemeral=True)

# -----------------------------
# ⏰ 定期チェック
# -----------------------------
@tasks.loop(minutes=1)
async def reminder_check():
    now = datetime.now()
    schedules = database.get_upcoming_schedules()

    for s in schedules:
        id, user_id, task, time_str, reminder, notified, confirmed, repeat = s
        schedule_time = datetime.strptime(time_str, "%Y-%m-%d-%H:%M")

        if not notified and now >= schedule_time - timedelta(minutes=reminder):
            user = await bot.fetch_user(int(user_id))
            await user.send(
                f"⏰ {reminder}分前リマインダー！\n"
                f"📝 {task} ({time_str})\n返信で 'OK' と送ると確認済みにできます。"
            )
            database.mark_notified(id)

            if repeat == 1:
                next_time = schedule_time + timedelta(days=7)
                database.add_schedule(user_id, task, next_time.strftime("%Y-%m-%d-%H:%M"), reminder, 1)

            asyncio.create_task(resend_if_unconfirmed(user, task, time_str, id, delay_minutes=10))

# -----------------------------
# 🔁 再送処理
# -----------------------------
async def resend_if_unconfirmed(user, task, time_str, schedule_id, delay_minutes=10):
    await asyncio.sleep(delay_minutes * 60)
    schedules = database.get_upcoming_schedules()
    for s in schedules:
        if s[0] == schedule_id and s[6] == 0:
            await user.send(f"🔁 再通知：まだ確認がありません。\n📝 {task} ({time_str})")
            database.mark_confirmed(schedule_id)

# -----------------------------
# 💬 DMで「OK」返信
# -----------------------------
@bot.event
async def on_message(message):
    if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
        if message.content.lower().strip() == "ok":
            schedules = database.get_upcoming_schedules()
            for s in schedules:
                if str(s[1]) == str(message.author.id):
                    database.mark_confirmed(s[0])
                    await message.channel.send("✅ 通知を確認しました！")
                    break
    await bot.process_commands(message)

# -----------------------------
# ▶️ 実行
# -----------------------------
bot.run(TOKEN)
