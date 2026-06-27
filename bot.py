    await query.edit_message_text(
        f"ðŸ“Š *Your Stats*\n\n"
        f"ðŸŽ° Total Flips: {flips}\n"
        f"âœ… Wins: {wins}\n"
        f"âŒ Losses: {losses}\n"
        f"ðŸ“ˆ Win Rate: {rate}%\n\n"
        f"ðŸª™ Current Coins: {db_user[3]}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="menu")]])
    )

# â”€â”€â”€ Admin Commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ðŸ‘¥ All Users", callback_data="admin_users"),
         InlineKeyboardButton("ðŸ’° Payments", callback_data="admin_payments")],
        [InlineKeyboardButton("ðŸŽ² AI Settings", callback_data="admin_ai"),
         InlineKeyboardButton("ðŸ“Š Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("âž• Add Coins", callback_data="admin_addcoins"),
         InlineKeyboardButton("ðŸš« Ban User", callback_data="admin_ban")]
    ])
    await update.message.reply_text("ðŸ›  *Admin Panel*", parse_mode="Markdown", reply_markup=kb)

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
        text = "ðŸ‘¥ *Users (last 20)*\n\n"
        for u in users:
            status = "âœ…" if u[3] else "â³"
            banned = "ðŸš«" if u[4] else ""
            text += f"{status}{banned} {u[1]} | ðŸª™{u[2]} | `{u[0]}`\n"
        await query.edit_message_text(text or "No users yet.", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="admin_back")]]))

    elif data == "admin_payments":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, amount, txn_id, status FROM payments ORDER BY id DESC LIMIT 10")
        pays = c.fetchall()
        conn.close()
        text = "ðŸ’° *Recent Payments*\n\n"
        for p in pays:
            text += f"#{p[0]} | User `{p[1]}` | â‚¹{p[2]} | {p[4]}\nTxn: `{p[3]}`\n\n"
        await query.edit_message_text(text or "No payments yet.", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="admin_back")]]))

    elif data == "admin_ai":
        win_n = get_setting("win_every_n")
        await query.edit_message_text(
            f"ðŸŽ² *AI Win Control*\n\n"
            f"Current: Win 1 out of every *{win_n}* flips\n\n"
            f"Use command:\n`/setwins <number>`\n\nExample: `/setwins 5` = win every 5th flip",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="admin_back")]]))

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
            f"ðŸ“Š *Bot Stats*\n\n"
            f"ðŸ‘¥ Total Users: {total_users}\n"
            f"âœ… Approved: {approved}\n"
            f"ðŸ’µ Total Deposits: â‚¹{total_money}\n"
            f"ðŸŽ° Total Flips: {total_flips}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="admin_back")]]))

    elif data == "admin_back":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("ðŸ‘¥ All Users", callback_data="admin_users"),
             InlineKeyboardButton("ðŸ’° Payments", callback_data="admin_payments")],
            [InlineKeyboardButton("ðŸŽ² AI Settings", callback_data="admin_ai"),
             InlineKeyboardButton("ðŸ“Š Stats", callback_data="admin_stats")]
        ])
        await query.edit_message_text("ðŸ›  *Admin Panel*", parse_mode="Markdown", reply_markup=kb)

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
        await update.message.reply_text(f"âœ… AI set to win 1 out of every *{n}* flips.", parse_mode="Markdown")
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
        await update.message.reply_text(f"âœ… Added {amount} coins to user `{uid}`.", parse_mode="Markdown")
        await ctx.bot.send_message(uid, f"ðŸŽ Admin added *{amount} coins* to your account!", parse_mode="Markdown")
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
        await update.message.reply_text(f"ðŸš« User `{uid}` has been banned.", parse_mode="Markdown")
    except:
        await update.message.reply_text("Usage: `/ban <user_id>`", parse_mode="Markdown")

# â”€â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    print("âœ… Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
