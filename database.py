# database.py - Complete database functions for OSINT Pro Bot

import aiosqlite
import json
from datetime import datetime

DB_PATH = "osint_bot.db"

async def init_db():
    """Initialize all database tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            total_lookups INTEGER DEFAULT 0,
            username TEXT,
            first_name TEXT,
            last_name TEXT
        )''')
        # Admins table
        await db.execute('''CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # Banned table
        await db.execute('''CREATE TABLE IF NOT EXISTS banned (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            banned_by INTEGER,
            banned_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # Lookups table
        await db.execute('''CREATE TABLE IF NOT EXISTS lookups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            command TEXT,
            query TEXT,
            result TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # Daily stats table
        await db.execute('''CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT,
            command TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY(date, command)
        )''')
        await db.commit()

# ==================== USER FUNCTIONS ====================
async def update_user(user_id, username=None, first_name=None, last_name=None):
    """Insert or update user information."""
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        await db.execute('''
            INSERT INTO users (user_id, first_seen, last_seen, username, first_name, last_name)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_seen=excluded.last_seen,
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name
        ''', (user_id, now, now, username, first_name, last_name))
        await db.commit()

async def get_user(user_id):
    """Get user by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

# ==================== ADMIN FUNCTIONS ====================
async def is_admin(user_id):
    """Check if user is an admin."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def add_admin(user_id, added_by):
    """Add a new admin."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)', (user_id, added_by))
        await db.commit()

async def remove_admin(user_id):
    """Remove an admin."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_all_admins():
    """Get list of all admin user_ids."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id FROM admins') as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# ==================== BAN FUNCTIONS ====================
async def is_banned(user_id):
    """Check if user is banned."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM banned WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def ban_user(user_id, reason, banned_by):
    """Ban a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO banned (user_id, reason, banned_by) VALUES (?, ?, ?)',
                         (user_id, reason, banned_by))
        await db.commit()

async def unban_user(user_id):
    """Unban a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM banned WHERE user_id = ?', (user_id,))
        await db.commit()

# ==================== LOOKUP FUNCTIONS ====================
async def save_lookup(user_id, command, query, result):
    """Save a lookup record and update user stats."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO lookups (user_id, command, query, result) VALUES (?, ?, ?, ?)',
            (user_id, command, query, json.dumps(result))
        )
        await db.execute('UPDATE users SET total_lookups = total_lookups + 1 WHERE user_id = ?', (user_id,))
        # Update daily stats
        date = datetime.now().strftime('%Y-%m-%d')
        await db.execute('''
            INSERT INTO daily_stats (date, command, count) VALUES (?, ?, 1)
            ON CONFLICT(date, command) DO UPDATE SET count = count + 1
        ''', (date, command))
        await db.commit()

async def get_user_lookups(user_id, limit=10):
    """Get recent lookups of a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT command, query, timestamp FROM lookups WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?',
            (user_id, limit)
        ) as cursor:
            return await cursor.fetchall()

async def get_leaderboard(limit=10):
    """Get top users by total lookups."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT user_id, total_lookups FROM users ORDER BY total_lookups DESC LIMIT ?',
            (limit,)
        ) as cursor:
            return await cursor.fetchall()

async def get_all_users(limit=100, offset=0):
    """Get paginated list of users."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT user_id, username, first_name, total_lookups, last_seen FROM users ORDER BY last_seen DESC LIMIT ? OFFSET ?',
            (limit, offset)
        ) as cursor:
            return await cursor.fetchall()

async def get_recent_users(days=7):
    """Get users active in last N days."""
    async with aiosqlite.connect(DB_PATH) as db:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        async with db.execute(
            'SELECT user_id, username, last_seen FROM users WHERE last_seen >= ?',
            (cutoff,)
        ) as cursor:
            return await cursor.fetchall()

async def get_inactive_users(days=30):
    """Get users not active in last N days."""
    async with aiosqlite.connect(DB_PATH) as db:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        async with db.execute(
            'SELECT user_id, username, last_seen FROM users WHERE last_seen < ?',
            (cutoff,)
        ) as cursor:
            return await cursor.fetchall()

# ==================== STATISTICS FUNCTIONS ====================
async def get_stats():
    """Get overall bot statistics."""
    async with aiosqlite.connect(DB_PATH) as db:
        # total users
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            total_users = (await cursor.fetchone())[0]
        # total lookups
        async with db.execute('SELECT SUM(total_lookups) FROM users') as cursor:
            total_lookups = (await cursor.fetchone())[0] or 0
        # total admins
        async with db.execute('SELECT COUNT(*) FROM admins') as cursor:
            total_admins = (await cursor.fetchone())[0]
        # total banned
        async with db.execute('SELECT COUNT(*) FROM banned') as cursor:
            total_banned = (await cursor.fetchone())[0]
        return {
            "total_users": total_users,
            "total_lookups": total_lookups,
            "total_admins": total_admins,
            "total_banned": total_banned
        }

async def get_daily_stats(days=7):
    """Get daily stats for the last N days."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT date, command, count FROM daily_stats WHERE date >= date("now", "-? days") ORDER BY date DESC',
            (days,)
        ) as cursor:
            return await cursor.fetchall()

async def get_lookup_stats(limit=10):
    """Get command-wise lookup counts."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT command, COUNT(*) as cnt FROM lookups GROUP BY command ORDER BY cnt DESC LIMIT ?',
            (limit,)
        ) as cursor:
            return await cursor.fetchall()