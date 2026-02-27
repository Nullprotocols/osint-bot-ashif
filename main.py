#!/usr/bin/env python3
# main.py - Complete OSINT Pro Bot with Flask for Render Web Service

import os
import sys
import re
import json
import uuid
import asyncio
import logging
import threading
import aiohttp
from datetime import datetime, timedelta
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

# Import config and database
from config import *
from database import *

# ==================== SETUP ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app for Render health checks
flask_app = Flask(__name__)

# ==================== UTILITY FUNCTIONS ====================
copy_cache = {}  # {uid: {"data": data, "time": timestamp}}

def clean_branding(text, extra_blacklist=None):
    """Remove all blacklisted strings from text (case-insensitive)."""
    if not text:
        return text
    blacklist = GLOBAL_BLACKLIST.copy()
    if extra_blacklist:
        blacklist.extend(extra_blacklist)
    for item in blacklist:
        text = re.sub(re.escape(item), '', text, flags=re.IGNORECASE)
    # Clean multiple newlines and spaces
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

async def call_api(url):
    """Async HTTP GET request with timeout."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json()
                    except:
                        return {"error": "Invalid JSON response"}
                else:
                    return {"error": f"HTTP {resp.status}"}
        except asyncio.TimeoutError:
            return {"error": "Request timeout"}
        except Exception as e:
            return {"error": str(e)}

def format_output(data):
    """Convert data to pretty JSON inside HTML <pre> tags, add footer."""
    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    # Escape HTML characters
    pretty = pretty.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return f"<pre>{pretty}</pre>{FOOTER}"

async def check_force_join(bot, user_id):
    """Check if user has joined all required channels."""
    missing = []
    for ch in FORCE_JOIN_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["id"], user_id=user_id)
            if member.status in ['left', 'kicked']:
                missing.append(ch)
        except Exception:
            missing.append(ch)  # if bot can't check, assume not joined
    return len(missing) == 0, missing

def get_force_join_keyboard(missing):
    """Create inline keyboard with join buttons and verify button."""
    keyboard = []
    for ch in missing:
        keyboard.append([InlineKeyboardButton(f"Join {ch['name']}", url=ch['link'])])
    keyboard.append([InlineKeyboardButton("✅ I've joined", callback_data="verify_join")])
    return InlineKeyboardMarkup(keyboard)

def store_copy_data(data):
    """Store data in cache and return unique ID."""
    uid = str(uuid.uuid4())
    copy_cache[uid] = {"data": data, "time": datetime.now().timestamp()}
    return uid

def get_copy_button(data):
    return InlineKeyboardButton("📋 Copy", callback_data=f"copy:{store_copy_data(data)}")

def get_search_button(cmd):
    return InlineKeyboardButton("🔍 Search", callback_data=f"search:{cmd}")

# ==================== FILTERS ====================
async def group_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Allow only groups; private messages redirected unless admin/owner."""
    if update.effective_chat.type == "private":
        user_id = update.effective_user.id
        if user_id == OWNER_ID or await is_admin(user_id):
            return True
        await update.message.reply_text(
            f"Ye bot sirf group me kaam karta hai.\nPersonal use ke liye use kare: {REDIRECT_BOT}"
        )
        return False
    return True

async def force_join_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check force join (admins/owner bypass)."""
    user = update.effective_user
    if not user:
        return True
    if user.id == OWNER_ID or await is_admin(user.id):
        return True
    if await is_banned(user.id):
        await update.message.reply_text("❌ Aap banned hain. Contact admin.")
        return False
    ok, missing = await check_force_join(context.bot, user.id)
    if not ok:
        await update.message.reply_text(
            "⚠️ Bot use karne ke liye ye channels join karo:",
            reply_markup=get_force_join_keyboard(missing)
        )
        return False
    return True

# ==================== COMMAND HANDLER ====================
async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE, cmd: str, query: str):
    """Execute a command by calling its API."""
    cmd_info = COMMANDS.get(cmd)
    if not cmd_info:
        await update.message.reply_text("❌ Command not found.")
        return

    url = cmd_info["url"].format(query)
    data = await call_api(url)

    # Clean branding
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    cleaned = clean_branding(json_str, cmd_info.get("extra_blacklist", []))

    # Prepare output
    output_html = f"<pre>{cleaned}</pre>{FOOTER}"
    keyboard = [[get_copy_button(data), get_search_button(cmd)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(output_html, parse_mode='HTML', reply_markup=reply_markup)

    # Save to DB
    await save_lookup(update.effective_user.id, cmd, query, data)

    # Log to channel
    log_text = f"User: {update.effective_user.id}\nQuery: {query}\nCmd: /{cmd}\n\n{json.dumps(data, indent=2)}"
    if len(log_text) > 4000:
        log_text = log_text[:4000] + "..."
    await context.bot.send_message(chat_id=cmd_info["log"], text=log_text)

# ==================== MAIN MESSAGE HANDLER ====================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for all messages."""
    # Apply filters
    if not await group_only(update, context):
        return
    if not await force_join_filter(update, context):
        return

    # Update user in DB
    u = update.effective_user
    await update_user(u.id, u.username, u.first_name, u.last_name)

    # Parse command
    text = update.message.text
    if not text or not text.startswith('/'):
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0][1:].lower()
    query = parts[1] if len(parts) > 1 else None

    if not query:
        param = COMMANDS.get(cmd, {}).get("param", "query")
        await update.message.reply_text(f"Usage: /{cmd} <{param}>")
        return

    await handle_command(update, context, cmd, query)

# ==================== CALLBACK HANDLER ====================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "verify_join":
        ok, missing = await check_force_join(context.bot, query.from_user.id)
        if ok:
            await query.edit_message_text("✅ Verification successful! Ab aap bot use kar sakte hain.")
        else:
            await query.edit_message_text(
                "⚠️ Aapne abhi bhi kuch channels join nahi kiye:",
                reply_markup=get_force_join_keyboard(missing)
            )
    elif data.startswith("copy:"):
        uid = data.split(":", 1)[1]
        if uid in copy_cache:
            await query.message.reply_text(
                f"```json\n{json.dumps(copy_cache[uid]['data'], indent=2)}\n```",
                parse_mode='Markdown'
            )
            del copy_cache[uid]  # one-time use
        else:
            await query.message.reply_text("❌ Copy data expired. Please run the command again.")
    elif data.startswith("search:"):
        cmd = data.split(":", 1)[1]
        await query.message.reply_text(f"Send /{cmd} with your query.")

# ==================== ADMIN COMMANDS ====================
async def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id == OWNER_ID or await is_admin(user.id):
            return await func(update, context)
        await update.message.reply_text("❌ This command is for admins only.")
    return wrapper

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast text message to all users."""
    if not context.args:
        return await update.message.reply_text("Usage: /broadcast <message>")
    msg = ' '.join(context.args)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id FROM users') as cursor:
            users = await cursor.fetchall()
    success, fail = 0, 0
    for (uid,) in users:
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
            success += 1
        except:
            fail += 1
    await update.message.reply_text(f"✅ Success: {success}\n❌ Fail: {fail}")

@admin_only
async def dm_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send direct message to a user."""
    try:
        uid = int(context.args[0])
        msg = ' '.join(context.args[1:])
        await context.bot.send_message(chat_id=uid, text=msg)
        await update.message.reply_text(f"✅ Message sent to {uid}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /dm <user_id> <message>")

@admin_only
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(context.args[0])
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason"
        await ban_user(uid, reason, update.effective_user.id)
        await update.message.reply_text(f"✅ Banned {uid}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /ban <user_id> [reason]")

@admin_only
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(context.args[0])
        await unban_user(uid)
        await update.message.reply_text(f"✅ Unbanned {uid}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /unban <user_id>")

@admin_only
async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete user from database."""
    try:
        uid = int(context.args[0])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('DELETE FROM users WHERE user_id = ?', (uid,))
            await db.commit()
        await update.message.reply_text(f"✅ User {uid} deleted from database.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /deleteuser <user_id>")

@admin_only
async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search user by ID, username, or name."""
    if not context.args:
        return await update.message.reply_text("Usage: /searchuser <query>")
    query = ' '.join(context.args)
    # Try exact user_id first
    try:
        uid = int(query)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT * FROM users WHERE user_id = ?', (uid,)) as cursor:
                user = await cursor.fetchone()
        if user:
            text = f"User found:\nID: {user[0]}\nUsername: @{user[4] or 'N/A'}\nName: {user[5] or ''} {user[6] or ''}\nLookups: {user[3]}\nLast seen: {user[2]}"
        else:
            text = "User not found."
        await update.message.reply_text(text)
        return
    except ValueError:
        pass
    # Search by username or name (partial, case-insensitive)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username, first_name, last_name FROM users WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ? LIMIT 10",
            (f'%{query}%', f'%{query}%', f'%{query}%')
        ) as cursor:
            results = await cursor.fetchall()
    if results:
        text = "Search results:\n"
        for r in results:
            text += f"• {r[0]} (@{r[1] or 'N/A'}) - {r[2] or ''} {r[3] or ''}\n"
    else:
        text = "No users found."
    await update.message.reply_text(text)

@admin_only
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List users with pagination."""
    page = int(context.args[0]) if context.args else 1
    per_page = 10
    offset = (page-1)*per_page
    users_list = await get_all_users(limit=per_page, offset=offset)
    if not users_list:
        await update.message.reply_text("No users found.")
        return
    text = f"👥 Users (Page {page}):\n"
    for u in users_list:
        text += f"• {u[0]} (@{u[1] or 'N/A'}) - {u[3]} lookups\n"
    await update.message.reply_text(text)

@admin_only
async def recent_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List users active in last N days."""
    days = int(context.args[0]) if context.args else 7
    users_list = await get_recent_users(days)
    text = f"📅 Users active in last {days} days:\n"
    for u in users_list:
        text += f"• {u[0]} (@{u[1] or 'N/A'}) - last seen {u[2]}\n"
    await update.message.reply_text(text)

@admin_only
async def inactive_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List users inactive for more than N days."""
    days = int(context.args[0]) if context.args else 30
    users_list = await get_inactive_users(days)
    text = f"💤 Users inactive for >{days} days:\n"
    for u in users_list:
        text += f"• {u[0]} (@{u[1] or 'N/A'}) - last seen {u[2]}\n"
    await update.message.reply_text(text)

@admin_only
async def user_lookups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(context.args[0])
        lookups = await get_user_lookups(uid, 10)
        text = f"📊 Last 10 lookups of {uid}:\n"
        for cmd, q, ts in lookups:
            text += f"{ts} - /{cmd} {q}\n"
        await update.message.reply_text(text)
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /userlookups <user_id>")

@admin_only
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board = await get_leaderboard(10)
    text = "🏆 Leaderboard (Top 10):\n"
    for i, (uid, count) in enumerate(board, 1):
        text += f"{i}. {uid} - {count} lookups\n"
    await update.message.reply_text(text)

@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_data = await get_stats()
    text = f"📈 Bot Statistics:\n"
    text += f"Total Users: {stats_data['total_users']}\n"
    text += f"Total Lookups: {stats_data['total_lookups']}\n"
    text += f"Total Admins: {stats_data['total_admins']}\n"
    text += f"Total Banned: {stats_data['total_banned']}\n"
    await update.message.reply_text(text)

@admin_only
async def daily_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = int(context.args[0]) if context.args else 7
    stats_list = await get_daily_stats(days)
    if not stats_list:
        await update.message.reply_text("No daily stats available.")
        return
    text = f"📅 Daily Stats (last {days} days):\n"
    for date, cmd, count in stats_list:
        text += f"{date} - /{cmd}: {count}\n"
    await update.message.reply_text(text)

@admin_only
async def lookup_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_list = await get_lookup_stats(10)
    text = "🔍 Lookup Stats (Top 10 commands):\n"
    for cmd, cnt in stats_list:
        text += f"/{cmd}: {cnt}\n"
    await update.message.reply_text(text)

# ==================== OWNER COMMANDS ====================
async def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id == OWNER_ID:
            return await func(update, context)
    return wrapper

@owner_only
async def add_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(context.args[0])
        await add_admin(uid, OWNER_ID)
        await update.message.reply_text(f"✅ Admin added: {uid}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /addadmin <user_id>")

@owner_only
async def remove_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(context.args[0])
        await remove_admin(uid)
        await update.message.reply_text(f"✅ Admin removed: {uid}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /removeadmin <user_id>")

@owner_only
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = await get_all_admins()
    text = "👑 Admins:\n" + "\n".join(str(a) for a in admins)
    await update.message.reply_text(text)

@owner_only
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Placeholder for settings command (can be extended)."""
    await update.message.reply_text("Settings command - under development.")

@owner_only
async def full_db_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open(DB_PATH, 'rb') as f:
        await update.message.reply_document(f, filename='osint_bot_backup.db')

# ==================== BOT INITIALIZATION ====================
async def post_init(app: Application):
    await init_db()
    for aid in INITIAL_ADMINS:
        await add_admin(aid, OWNER_ID)
    logger.info("✅ Bot initialized, database ready.")

def run_bot():
    """Run the Telegram bot in a separate thread."""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN not set! Please set it in Render environment variables.")
        return

    bot_app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Register all handlers
    bot_app.add_handler(CommandHandler("broadcast", broadcast))
    bot_app.add_handler(CommandHandler("dm", dm_user))
    bot_app.add_handler(CommandHandler("ban", ban))
    bot_app.add_handler(CommandHandler("unban", unban))
    bot_app.add_handler(CommandHandler("deleteuser", delete_user))
    bot_app.add_handler(CommandHandler("searchuser", search_user))
    bot_app.add_handler(CommandHandler("users", users))
    bot_app.add_handler(CommandHandler("recentusers", recent_users))
    bot_app.add_handler(CommandHandler("inactiveusers", inactive_users))
    bot_app.add_handler(CommandHandler("userlookups", user_lookups))
    bot_app.add_handler(CommandHandler("leaderboard", leaderboard))
    bot_app.add_handler(CommandHandler("stats", stats))
    bot_app.add_handler(CommandHandler("dailystats", daily_stats))
    bot_app.add_handler(CommandHandler("lookupstats", lookup_stats))

    # Owner-only
    bot_app.add_handler(CommandHandler("addadmin", add_admin_cmd))
    bot_app.add_handler(CommandHandler("removeadmin", remove_admin_cmd))
    bot_app.add_handler(CommandHandler("listadmins", list_admins))
    bot_app.add_handler(CommandHandler("settings", settings))
    bot_app.add_handler(CommandHandler("fulldbbackup", full_db_backup))

    # Main command handler (dynamic)
    bot_app.add_handler(MessageHandler(filters.COMMAND, message_handler))
    bot_app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("🚀 Bot polling started...")
    bot_app.run_polling()

# ==================== FLASK WEB SERVER ====================
@flask_app.route('/')
def home():
    return jsonify({
        "status": "running",
        "message": "OSINT Pro Bot is active",
        "time": datetime.now().isoformat()
    })

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

# ==================== MAIN ====================
def main():
    logger.info("🔧 Starting OSINT Pro Bot on Render Web Service...")
    
    # Check if token is set
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN not set! Please add it in Render environment variables.")
        logger.error("Bot will not start until token is configured.")
        # Still run Flask to show health check but bot won't work
    
    # Start bot in background thread (only if token is set)
    if BOT_TOKEN and BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        logger.info("✅ Bot thread started")
    else:
        logger.warning("⚠️ Bot not started due to missing token. Flask server only.")

    # Run Flask
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 Flask server starting on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()