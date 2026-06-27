import os
import random
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

BOT_TOKEN = "8843700952:AAG-K1PFxwcHjE670TSn4dzAcqakgmx5M3U"
ADMIN_ID = 8908882066
FAMAPP_ID = "7082599978@fam"
MIN_DEPOSIT = 100

# AI Loss Control: lose 4 times, win 1 time (configurable from admin)
WIN_PATTERN = [False, False, False, False, True]  # 1 win per 5 flips

# Conversation states
WAITING_TXN_ID = 1
WAITING_AMOUNT = 2
WAITING_WITHDRAW_AMOUNT = 3

# ─── Database Setup ──────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect("coinflip.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        coins INTEGER DEFAULT 0,
        total_deposited REAL DEFAULT 0,
        flip_count INTEGER DEFAULT 0,
        win_count INTEGER DEFAULT 0,
        is_approved INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        joined_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        txn_id TEXT,
        status TEXT DEFAULT 'pending',
        submitted_at TEXT,
        confirmed_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS flip_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        result TEXT,
        coins_before INTEGER,
        coins_after INTEGER,
        flipped_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    # Default AI settings
    c.execute("INSERT OR IGNORE INTO settings VALUES ('win_every_n', '5')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('bot_active', '1')")
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect("coinflip.db")

# ─── DB Helpers ──────────────────────────────────────────────────────────────

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username, full_name):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users 
        (user_id, username, full_name, joined_at) VALUES (?,?,?,?)''',
        (user_id, username, full_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def should_win(user_id):
    """AI-controlled win/loss logic"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT flip_count, win_count FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    flip_count, win_count = row
    win_every_n = int(get_setting('win_every_n') or 5)
    # Win on every Nth flip
    return (flip_count + 1) % win_every_n == 0

# ─── Start / Access Request ───────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username or "", user.full_name)
    db_user = get_user(user.id)

    if db_user[8]:  # is_banned
        await update.message.reply_text("🚫 You are banned from this bot.")
        return

    if not db_user[7]:  # not approved
        # Notify admin
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")
        ]])
        await ctx.bot.send_message(
            ADMIN_ID,
            f"🔔 *New User Wants Access*\n\n"
            f"👤 Name: {user.full_name}\n"
            f"🆔 ID: `{user.id}`\n"
            f"📛 Username: @{user.username or 'N/A'}",
            parse_mode="Markdown",
            reply_markup=kb
        )
        await update.message.reply_text(
            "👋 Welcome!\n\n"
            "Your access request has been sent to the admin.\n"
            "⏳ Please wait for approval before you can use this bot."
        )
        return

    await show_main_menu(update, ctx)

async def show_main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id)
    coins = db_user[3]

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 Flip Coin", callback_data="flip")],
        [InlineKeyboardButton("💰 Add Money", callback_data="add_money"),
         InlineKeyboardButton("💼 My Balance", callback_data="balance")],
        [InlineKeyboardButton("📊 My Stats", callback_data="stats")]
    ])
    text = (
        f"🎰 *Coin Flip Bot*\n\n"
        f"👋 Hello, {user.first_name}!\n"
        f"🪙 Your Coins: *{coins}*\n\n"
        f"Each flip costs 1 coin.\n"
        f"Win = +1 coin | Lose = -1 coin"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

# ─── Approval Flow ────────────────────────────────────────────────────────────

async def handle_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    action, uid = data.split("_", 1)
    uid = int(uid)

    conn = get_db()
    c = conn.cursor()
    if action == "approve":
        c.execute("UPDATE users SET is_approved=1 WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ User `{uid}` has been approved.", parse_mode="Markdown")
        await ctx.bot.send_message(
            uid,
            "✅ *Your access has been approved!*\n\n"
            "You can now use the bot. Send /start to begin.",
            parse_mode="Markdown"
        )
    else:
        c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"❌ User `{uid}` has been rejected.", parse_mode="Markdown")
        await ctx.bot.send_message(uid, "❌ Your access request was rejected.")

# ─── Add Money Flow ───────────────────────────────────────────────────────────

async def add_money(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"💰 *Add Money*\n\n"
        f"Minimum deposit: ₹{MIN_DEPOSIT}\n\n"
        f"📲 Send money to Famapp ID:\n"
        f"`{FAMAPP_ID}`\n\n"
        f"After payment, click the button below and enter your amount.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ I've Paid – Enter Amount", callback_data="enter_amount")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu")]
        ])
    )

async def enter_amount_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"💵 Please enter the amount you paid (minimum ₹{MIN_DEPOSIT}):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="menu")
        ]])
    )
    return WAITING_AMOUNT

async def receive_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount < MIN_DEPOSIT:
            await update.message.reply_text(f"❌ Minimum deposit is ₹{MIN_DEPOSIT}. Please enter a valid amount:")
            return WAITING_AMOUNT
        ctx.user_data["deposit_amount"] = amount
        await update.message.reply_text(
            f"✅ Amount: ₹{amount}\n\n"
            f"Now please enter your *Famapp Transaction ID*:",
            parse_mode="Markdown"
        )
        return WAITING_TXN_ID
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number:")
        return WAITING_AMOUNT

async def receive_txn_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txn_id = update.message.text.strip()
    user_id = update.effective_user.id
    amount = ctx.user_data.get("deposit_amount", 0)

    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO payments (user_id, amount, txn_id, submitted_at)
                 VALUES (?,?,?,?)''', (user_id, amount, txn_id, datetime.now().isoformat()))
    payment_id = c.lastrowid
    conn.commit()
    conn.close()

    # Notify admin
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm_pay_{payment_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_pay_{payment_id}")
    ]])
    db_user = get_user(user_id)
    await ctx.bot.send_message(
        ADMIN_ID,
        f"💰 *New Payment Request*\n\n"
        f"👤 User: {update.effective_user.full_name}\n"
        f"🆔 ID: `{user_id}`\n"
        f"💵 Amount: ₹{amount}\n"
        f"🔖 Txn ID: `{txn_id}`",
        parse_mode="Markdown",
        reply_markup=kb
    )

    await update.message.reply_text(
        f"⏳ *Payment Submitted!*\n\n"
        f"Amount: ₹{amount}\n"
        f"Transaction ID: `{txn_id}`\n\n"
        f"Your payment will be verified within *24 hours*.\n"
        f"Coins will be added after confirmation. ✅",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu")
        ]])
    )
    return ConversationHandler.END

async def confirm_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    action, pay_id = data.rsplit("_", 1)
    pay_id = int(pay_id)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM payments WHERE id=?", (pay_id,))
    payment = c.fetchone()

    if not payment or payment[4] != "pending":
        await query.edit_message_text("⚠️ Payment already processed.")
        conn.close()
        return

    user_id, amount = payment[1], payment[2]
    coins_to_add = int(amount)  # ₹1 = 1 coin

    if "confirm_pay" in action:
        c.execute("UPDATE payments SET status='confirmed', confirmed_at=? WHERE id=?",
                  (datetime.now().isoformat(), pay_id))
        c.execute("UPDATE users SET coins=coins+?, total_deposited=total_deposited+? WHERE user_id=?",
                  (coins_to_add, amount, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ Payment #{pay_id} confirmed. Added {coins_to_add} coins to user `{user_id}`.", parse_mode="Markdown")
        await ctx.bot.send_message(
            user_id,
            f"🎉 *Payment Confirmed!*\n\n"
            f"₹{amount} → *{coins_to_add} coins* added to your account!\n\n"
            f"Send /start to start flipping! 🪙",
            parse_mode="Markdown"
        )
    else:
        c.execute("UPDATE payments SET status='rejected', confirmed_at=? WHERE id=?",
                  (datetime.now().isoformat(), pay_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"❌ Payment #{pay_id} rejected.", parse_mode="Markdown")
        await ctx.bot.send_message(user_id, "❌ Your payment was rejected. Please contact admin.")

# ─── Coin Flip ────────────────────────────────────────────────────────────────

async def flip_coin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    db_user = get_user(user_id)
    coins = db_user[3]

    if coins < 1:
        await query.edit_message_text(
            "❌ You don't have enough coins!\n\nAdd money first to get coins.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Add Money", callback_data="add_money")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu")]
            ])
        )
        return

    # AI-controlled result
    win = should_win(user_id)
    result = "heads" if win else "tails"
    coin_emoji = "🟡" if win else "⚫"
    result_text = "WIN" if win else "LOSE"
    coins_after = coins + 1 if win else coins - 1

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET coins=?, flip_count=flip_count+1, win_count=win_count+? WHERE user_id=?",
              (coins_after, 1 if win else 0, user_id))
    c.execute('''INSERT INTO flip_history (user_id, result, coins_before, coins_after, flipped_at)
                 VALUES (?,?,?,?,?)''',
              (user_id, result_text, coins, coins_after, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    status = "🎉 You WON! +1 coin" if win else "💔 You LOST! -1 coin"
    await query.edit_message_text(
        f"{coin_emoji} *{result.upper()}*\n\n"
        f"{status}\n\n"
        f"🪙 Coins: {coins} → *{coins_after}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🪙 Flip Again", callback_data="flip")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
        ])
    )

# ─── Balance & Stats ──────────────────────────────────────────────────────────

async def show_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    db_user = get_user(user_id)
    await query.edit_message_text(
        f"💼 *Your Balance*\n\n"
        f"🪙 Coins: *{db_user[3]}*\n"
        f"💵 Total Deposited: ₹{db_user[4]}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu")]])
    )

async def show_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    db_user = get_user(user_id)
    flips = db_user[5]
    wins = db_user[6]
    losses = flips - wins
    rate = round((wins / flips * 100), 1) if flips > 0 else 0
    await query.edit_message_text(
        f"📊 *Your Stats*\n\n"
        f"🎰 Total Flips: {flips}\n"
        f"✅ Wins: {wins}\n"
        f"❌ Losses: {losses}\n"
        f"📈 Win Rate: {rate}%\n\n"
        f"🪙 Current Coins: {db_user[3]}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu")]])
    )

# ─── Admin Commands ───────────────────────────────────────────────────────────

async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 All Users", callback_data="admin_users"),
         InlineKeyboardButton("💰 Payments", callback_data="admin_payments")],
        [InlineKeyboardButton("🎲 AI Settings", callback_data="admin_ai"),
         InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("➕ Add Coins", callback_data="admin_addcoins"),
         InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban")]
    ])
    await update.message.reply_text("🛠 *Admin Panel*", parse_mode="Markdown", reply_markup=kb)

async def admin_callbacks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
        await query.answer("Not authorized.")
        return
    await query.answer()
    data = query.data

    if data == "admin_users":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, full_name, coins, is_approved, is_banned FROM users LIMIT 20")
        users = c.fetchall()
        conn.close()
        text = "👥 *Users (last 20)*\n\n"
        for u in users:
            status = "✅" if u[3] else "⏳"
            banned = "🚫" if u[4] else ""
            text += f"{status}{banned} {u[1]} | 🪙{u[2]} | `{u[0]}`\n"
        await query.edit_message_text(text or "No users yet.", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_payments":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, amount, txn_id, status FROM payments ORDER BY id DESC LIMIT 10")
        pays = c.fetchall()
        conn.close()
        text = "💰 *Recent Payments*\n\n"
        for p in pays:
            text += f"#{p[0]} | User `{p[1]}` | ₹{p[2]} | {p[4]}\nTxn: `{p[3]}`\n\n"
        await query.edit_message_text(text or "No payments yet.", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_ai":
        win_n = get_setting("win_every_n")
        await query.edit_message_text(
            f"🎲 *AI Win Control*\n\n"
            f"Current: Win 1 out of every *{win_n}* flips\n\n"
            f"Use command:\n`/setwins <number>`\n\nExample: `/setwins 5` = win every 5th flip",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_stats":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_approved=1")
        approved = c.fetchone()[0]
        c.execute("SELECT SUM(amount) FROM payments WHERE status='confirmed'")
        total_money = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM flip_history")
        total_flips = c.fetchone()[0]
        conn.close()
        await query.edit_message_text(
            f"📊 *Bot Stats*\n\n"
            f"👥 Total Users: {total_users}\n"
            f"✅ Approved: {approved}\n"
            f"💵 Total Deposits: ₹{total_money}\n"
            f"🎰 Total Flips: {total_flips}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_back":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 All Users", callback_data="admin_users"),
             InlineKeyboardButton("💰 Payments", callback_data="admin_payments")],
            [InlineKeyboardButton("🎲 AI Settings", callback_data="admin_ai"),
             InlineKeyboardButton("📊 Stats", callback_data="admin_stats")]
        ])
        await query.edit_message_text("🛠 *Admin Panel*", parse_mode="Markdown", reply_markup=kb)

async def set_wins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        n = int(ctx.args[0])
        if n < 1:
            raise ValueError
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE settings SET value=? WHERE key='win_every_n'", (str(n),))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ AI set to win 1 out of every *{n}* flips.", parse_mode="Markdown")
    except:
        await update.message.reply_text("Usage: `/setwins 5`", parse_mode="Markdown")

async def add_coins_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: /addcoins <user_id> <amount>"""
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(ctx.args[0])
        amount = int(ctx.args[1])
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, uid))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Added {amount} coins to user `{uid}`.", parse_mode="Markdown")
        await ctx.bot.send_message(uid, f"🎁 Admin added *{amount} coins* to your account!", parse_mode="Markdown")
    except:
        await update.message.reply_text("Usage: `/addcoins <user_id> <amount>`", parse_mode="Markdown")

async def ban_user_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: /ban <user_id>"""
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(ctx.args[0])
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🚫 User `{uid}` has been banned.", parse_mode="Markdown")
    except:
        await update.message.reply_text("Usage: `/ban <user_id>`", parse_mode="Markdown")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation for deposit
    deposit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(enter_amount_prompt, pattern="^enter_amount$")],
        states={
            WAITING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)],
            WAITING_TXN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_txn_id)],
        },
        fallbacks=[CallbackQueryHandler(show_main_menu, pattern="^menu$")]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("setwins", set_wins))
    app.add_handler(CommandHandler("addcoins", add_coins_cmd))
    app.add_handler(CommandHandler("ban", ban_user_cmd))
    app.add_handler(deposit_conv)
    app.add_handler(CallbackQueryHandler(handle_approval, pattern="^(approve|reject)_\d+$"))
    app.add_handler(CallbackQueryHandler(confirm_payment, pattern="^(confirm_pay|reject_pay)_\d+$"))
    app.add_handler(CallbackQueryHandler(add_money, pattern="^add_money$"))
    app.add_handler(CallbackQueryHandler(flip_coin, pattern="^flip$"))
    app.add_handler(CallbackQueryHandler(show_balance, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(show_stats, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern="^admin_"))

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
