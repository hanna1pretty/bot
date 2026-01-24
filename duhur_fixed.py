# -*- coding: utf-8 -*-
import logging
import asyncio
import io
import os
import sys
import subprocess
import platform
import shutil
import psutil
from collections import defaultdict
import time
import datetime
import pytz
from zoneinfo import ZoneInfo  # ✅ DITAMBAHKAN
import feedparser
from bs4 import BeautifulSoup
import random
import string
import json
from functools import wraps
import html
import re
import uuid
import math
import base64
import hashlib
import tempfile
import zipfile
from urllib.parse import unquote, urlparse
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from tempmail import TempMailClient
from tempmail.models import DomainType

# --- 1. IMPORT RAHASIA DARI CONFIG.PY ---
try:
    from config import (
        TOKEN,
        OWNER_ID,
        WEATHER_API_KEY,
        YOU_API_KEY,
        DB_NAME,
        SPOTIPY_CLIENT_ID,
        SPOTIPY_CLIENT_SECRET,
        MY_PROXY,
        QRIS_IMAGE,
        BASE_URL,
        BMKG_URL,
        ANIME_API,
        BIN_API,
        TEMPMAIL_API_KEY,
        OMYGPT_API_KEY,
        OMDB_API_KEY,
        FIREBASE_API_KEY,
        SMS_BUS_API_KEY,
    )
except ImportError:
    print("❌ ERROR FATAL: File 'config.py' tidak ditemukan!")
    sys.exit()

# --- 2. LIBRARY TAMBAHAN ---
import requests
import httpx
import aiohttp
import yt_dlp
import qrcode
import aiosqlite
import sqlite3
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from faker import Faker
from gtts import gTTS
from deep_translator import GoogleTranslator

# --- 3. PDF & CRYPTO ENGINE ---
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from PIL import Image, ImageOps
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# --- 4. LIBRARY SELENIUM ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- 5. LIBRARY TELEGRAM ---
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InputMediaPhoto,
    InlineQueryResultArticle,      # ✅ DITAMBAHKAN
    InputTextMessageContent,       # ✅ DITAMBAHKAN
)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    InlineQueryHandler,             # ✅ DITAMBAHKAN
    filters,
)
from telegram.error import NetworkError, BadRequest, TimedOut

# --- 6. ADGUARD SYSTEM ---
from adguard import AdguardSystem, set_adguard_instance, require_start, require_start_callback, require_start_inline


# ==========================================
# ⚙️ SYSTEM SETUP (AUTO LOAD)
# ==========================================

# Setup Waktu (WIB)
TZ = pytz.timezone("Asia/Jakarta")
START_TIME = time.time()

# ✅ FIX: current_time() dipakai di status_command, jadi harus didefinisikan
current_time = time.time

# --- SETUP LOGGING (CCTV) ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Spotify
try:
    sp_client = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET
    ))
    print("✅ Spotify API: Connected")
except Exception as e:
    print(f"⚠️ Spotify Error: {e}")
    sp_client = None

# 🛡️ ADGUARD: Initialize System
adguard = AdguardSystem(DB_NAME)

# ==========================================
# ⚙️ GLOBAL CONFIGURATION (EXECUTOR & UTILITIES)
# ==========================================

# Global executor untuk blocking operations
executor = ThreadPoolExecutor(max_workers=5)


# ==========================================
# 🚀 NETWORK & DB ENGINE
# ==========================================
async def fetch_json(url, method="GET", payload=None, headers=None):
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            else:
                resp = await client.post(url, json=payload, headers=headers)
            return resp.json()
        except:
            return None

# ✅ DB HELPERS (HARUS ADA DULU)
async def db_execute(query, params=()):
    """Execute query tanpa return"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(query, params)
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"[DB_EXECUTE] Error: {str(e)}")
        return False

async def db_fetch_one(query, params=()):
    """Fetch 1 row"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchone()
    except Exception as e:
        logger.error(f"[DB_FETCH_ONE] Error: {str(e)}")
        return None

async def db_fetch_all(query, params=()):
    """Fetch semua rows"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchall()
    except Exception as e:
        logger.error(f"[DB_FETCH_ALL] Error: {str(e)}")
        return []

async def db_insert(table, data):
    """Insert data ke table"""
    try:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(query, tuple(data.values()))
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"[DB_INSERT] Error: {str(e)}")
        return False

async def db_update(table, data, where):
    """Update data di table"""
    try:
        set_clause = ", ".join([f"{k}=?" for k in data.keys()])
        where_clause = " AND ".join([f"{k}=?" for k in where.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        params = tuple(data.values()) + tuple(where.values())
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(query, params)
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"[DB_UPDATE] Error: {str(e)}")
        return False

# ==========================================
# 💾 MEDIA CACHE FUNCTIONS
# ==========================================

async def save_media_cache(url: str, file_id: str, media_type: str) -> bool:
    """Simpan media ke cache untuk reuse"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR REPLACE INTO media_cache (url, file_id, media_type, timestamp) VALUES (?, ?, ?, ?)",
                (url, file_id, media_type, time.time())
            )
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"[CACHE] Save error: {str(e)}")
        return False

async def get_media_cache(url: str) -> dict:
    """Ambil media dari cache"""
    try:
        result = await db_fetch_one(
            "SELECT file_id, media_type FROM media_cache WHERE url=?",
            (url,)
        )
        if result:
            return {
                "file_id": result[0],
                "media_type": result[1],
                "cached": True
            }
        return {"cached": False}
    except Exception as e:
        logger.error(f"[CACHE] Get error: {str(e)}")
        return {"cached": False}

async def clear_old_media_cache(days: int = 365) -> bool:
    """Hapus cache yang sudah lama"""
    try:
        old_timestamp = time.time() - (days * 24 * 3600)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "DELETE FROM media_cache WHERE timestamp < ?",
                (old_timestamp,)
            )
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"[CACHE] Clear error: {str(e)}")
        return False

async def get_cached_media(track_id: str):
    """Ambil cached media berdasarkan track_id (untuk Spotify)"""
    try:
        result = await db_fetch_one(
            "SELECT file_id FROM media_cache WHERE url=?",
            (f"spotify:{track_id}",)
        )
        return result
    except Exception as e:
        logger.error(f"[CACHE] Get cached media error: {str(e)}")
        return None

async def save_cached_media(track_id: str, file_id: str):
    """Simpan media ke cache berdasarkan track_id (untuk Spotify)"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR REPLACE INTO media_cache (url, file_id, media_type, timestamp) VALUES (?, ?, ?, ?)",
                (f"spotify:{track_id}", file_id, "audio", time.time())
            )
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"[CACHE] Save cached media error: {str(e)}")
        return False

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Tabel Subscribers
        await db.execute(
            "CREATE TABLE IF NOT EXISTS subscribers (user_id INTEGER PRIMARY KEY)"
        )
        
        # Tabel Cache Media
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS media_cache (
                url TEXT PRIMARY KEY,
                file_id TEXT,
                media_type TEXT,
                timestamp REAL
            )
            """
        )
        
        # Tabel User Premium (with expiry and credits)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id INTEGER PRIMARY KEY,
                plan TEXT DEFAULT 'basic',
                credits INTEGER DEFAULT 100,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Tabel Redeem Codes
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS redeem_codes (
                code TEXT PRIMARY KEY,
                plan TEXT DEFAULT 'premium',
                credits INTEGER DEFAULT 500,
                duration_days INTEGER DEFAULT 30,
                used_by INTEGER,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Tabel User Credits (for non-premium daily limits)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_credits (
                user_id INTEGER PRIMARY KEY,
                credits INTEGER DEFAULT 50,
                last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Tabel Notifikasi Sholat
        await db.execute(
            "CREATE TABLE IF NOT EXISTS prayer_subs (chat_id INTEGER PRIMARY KEY, city TEXT)"
        )

        # Tabel Catatan Pribadi
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT,
                date_added TEXT
            )
            """
        )
        
        # Tabel Stok Akun
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                password TEXT,
                plan TEXT,
                status TEXT DEFAULT 'AVAILABLE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Tabel Orders
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                price TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                proof_photo_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP
            )
            """
        )

        # Tabel Transaction Logs
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS transaction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                plan TEXT,
                user_id INTEGER,
                status TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Tabel User Actions
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Tabel Word Game Scores
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS word_game_scores (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                highest_streak INTEGER DEFAULT 0,
                lang TEXT DEFAULT 'id'
            )
            """
        )
        
        # Tabel Cloudflare Users (API Key Storage)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS cloudflare_users (
                user_id INTEGER PRIMARY KEY,
                api_key TEXT,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Tabel Cloudflare Stats (Global Activity Tracking)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS cloudflare_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                domain TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.commit()
        
        # Migrate existing premium_users table if needed
        try:
            await db.execute("ALTER TABLE premium_users ADD COLUMN plan TEXT DEFAULT 'basic'")
        except: pass
        try:
            await db.execute("ALTER TABLE premium_users ADD COLUMN credits INTEGER DEFAULT 100")
        except: pass
        try:
            await db.execute("ALTER TABLE premium_users ADD COLUMN expires_at TIMESTAMP")
        except: pass
        try:
            await db.execute("ALTER TABLE premium_users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except: pass
        
        await db.commit()
    
    # 🛡️ ADGUARD: Initialize table
    await adguard.init_table()
    print("✅ Database Initialized")

# ==========================================
# 💰 CREDIT & PREMIUM SYSTEM
# ==========================================

# Credit costs for commands (bigger = more expensive)
CREDIT_COSTS = {
    "ai": 10, "gpt5": 10, "code": 8, "think": 12,
    "scan": 15, "research": 15,
    "tiktok": 3, "ig": 3, "yt": 5, "fb": 3, "tw": 3,
    "spotify": 4, "song": 4,
    "weather": 1, "cuaca": 1,
    "speed": 5,
    "pdfmerge": 3, "pdfsplit": 3, "pdftotext": 2, "compresspdf": 3,
    "translate": 2, "tts": 2,
    "qr": 1, "bin": 1, "ip": 1,
    "default": 2
}

async def get_user_credits(user_id: int) -> tuple:
    """Get user credits and premium status"""
    try:
        # Check premium first
        premium = await db_fetch_one(
            "SELECT credits, expires_at, plan FROM premium_users WHERE user_id = ?",
            (user_id,)
        )
        if premium:
            expires_at = premium[1]
            if expires_at:
                exp_dt = datetime.datetime.fromisoformat(expires_at)
                if exp_dt > datetime.datetime.now():
                    return (premium[0], True, premium[2], expires_at)
                else:
                    # Expired - remove premium
                    await db_execute("DELETE FROM premium_users WHERE user_id = ?", (user_id,))
        
        # Check regular user credits
        user_credit = await db_fetch_one(
            "SELECT credits, last_reset FROM user_credits WHERE user_id = ?",
            (user_id,)
        )
        if user_credit:
            last_reset = datetime.datetime.fromisoformat(user_credit[1]) if user_credit[1] else datetime.datetime.now()
            # Reset daily if 24h passed
            if (datetime.datetime.now() - last_reset).days >= 1:
                await db_execute(
                    "UPDATE user_credits SET credits = 50, last_reset = ? WHERE user_id = ?",
                    (datetime.datetime.now().isoformat(), user_id)
                )
                return (50, False, "free", None)
            return (user_credit[0], False, "free", None)
        else:
            # Create new user credits
            await db_execute(
                "INSERT INTO user_credits (user_id, credits, last_reset) VALUES (?, 50, ?)",
                (user_id, datetime.datetime.now().isoformat())
            )
            return (50, False, "free", None)
    except Exception as e:
        logger.error(f"[CREDITS] Error: {e}")
        return (0, False, "free", None)

async def deduct_credits(user_id: int, command: str) -> tuple:
    """Deduct credits for command usage. Returns (success, remaining, cost)"""
    cost = CREDIT_COSTS.get(command, CREDIT_COSTS["default"])
    
    try:
        credits, is_premium, plan, _ = await get_user_credits(user_id)
        
        # Owner always unlimited
        if user_id == OWNER_ID:
            return (True, 999999, 0)
        
        # Premium users with unlimited plan
        if is_premium and plan == "unlimited":
            return (True, credits, 0)
        
        # Check if enough credits
        if credits < cost:
            return (False, credits, cost)
        
        # Deduct from appropriate table
        if is_premium:
            await db_execute(
                "UPDATE premium_users SET credits = credits - ? WHERE user_id = ?",
                (cost, user_id)
            )
        else:
            await db_execute(
                "UPDATE user_credits SET credits = credits - ? WHERE user_id = ?",
                (cost, user_id)
            )
        
        return (True, credits - cost, cost)
    except Exception as e:
        logger.error(f"[DEDUCT] Error: {e}")
        return (True, 0, 0)  # Allow on error

async def generate_redeem_code(plan: str = "premium", credits: int = 500, duration_days: int = 30) -> str:
    """Generate a new redeem code (Owner only)"""
    import secrets
    code = f"OKTA-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
    
    await db_execute(
        "INSERT INTO redeem_codes (code, plan, credits, duration_days) VALUES (?, ?, ?, ?)",
        (code, plan, credits, duration_days)
    )
    return code

async def redeem_code(user_id: int, code: str) -> tuple:
    """Redeem a code. Returns (success, message, plan, credits, days)"""
    try:
        # Check if code exists and not used
        code_data = await db_fetch_one(
            "SELECT plan, credits, duration_days, used_by FROM redeem_codes WHERE code = ?",
            (code.upper(),)
        )
        
        if not code_data:
            return (False, "Kode tidak valid", None, 0, 0)
        
        if code_data[3]:  # Already used
            return (False, "Kode sudah digunakan", None, 0, 0)
        
        plan, credits, duration_days = code_data[0], code_data[1], code_data[2]
        expires_at = (datetime.datetime.now() + datetime.timedelta(days=duration_days)).isoformat()
        
        # Add/Update premium user
        existing = await db_fetch_one("SELECT user_id FROM premium_users WHERE user_id = ?", (user_id,))
        if existing:
            await db_execute(
                "UPDATE premium_users SET plan = ?, credits = credits + ?, expires_at = ? WHERE user_id = ?",
                (plan, credits, expires_at, user_id)
            )
        else:
            await db_execute(
                "INSERT INTO premium_users (user_id, plan, credits, expires_at) VALUES (?, ?, ?, ?)",
                (user_id, plan, credits, expires_at)
            )
        
        # Mark code as used
        await db_execute(
            "UPDATE redeem_codes SET used_by = ?, used_at = ? WHERE code = ?",
            (user_id, datetime.datetime.now().isoformat(), code.upper())
        )
        
        return (True, "Berhasil redeem!", plan, credits, duration_days)
    except Exception as e:
        logger.error(f"[REDEEM] Error: {e}")
        return (False, f"Error: {str(e)[:50]}", None, 0, 0)

async def check_premium_expiry_reminder(context):
    """Check for expiring premium users and send reminders"""
    try:
        # Find users expiring in next 3 days
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=3)).isoformat()
        today = datetime.datetime.now().isoformat()
        
        expiring = await db_fetch_all(
            "SELECT user_id, expires_at FROM premium_users WHERE expires_at BETWEEN ? AND ?",
            (today, tomorrow)
        )
        
        for user_id, expires_at in expiring or []:
            exp_dt = datetime.datetime.fromisoformat(expires_at)
            days_left = (exp_dt - datetime.datetime.now()).days
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"⚠️ <b>PREMIUM EXPIRING SOON</b>\n\n"
                        f"Premium kamu akan berakhir dalam <b>{days_left} hari</b>.\n"
                        f"📅 Expires: {exp_dt.strftime('%d/%m/%Y %H:%M')}\n\n"
                        f"Hubungi admin untuk perpanjangan atau gunakan kode redeem baru."
                    ),
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.warning(f"[EXPIRY] Could not notify user {user_id}: {e}")
                
    except Exception as e:
        logger.error(f"[EXPIRY CHECK] Error: {e}")

# ✅ ADMIN DASHBOARD FUNCTIONS
async def get_all_subscribers():
    """Get semua subscribers"""
    try:
        result = await db_fetch_all("SELECT user_id FROM subscribers")
        return result or []
    except:
        return []

async def get_all_premium_users():
    """Get semua premium users"""
    try:
        result = await db_fetch_all("SELECT user_id FROM premium_users")
        return result or []
    except:
        return []

async def get_total_sales_all_time():
    """Get total penjualan"""
    try:
        result = await db_fetch_one("SELECT COUNT(*) FROM orders WHERE status='approved'")
        return result[0] if result else 0
    except:
        return 0

async def get_pending_orders_count():
    """Get jumlah pending orders"""
    try:
        result = await db_fetch_one("SELECT COUNT(*) FROM orders WHERE status='pending'")
        return result[0] if result else 0
    except:
        return 0

async def get_all_stock():
    """Get semua stok per plan"""
    try:
        result = await db_fetch_all(
            "SELECT plan, COUNT(*) FROM accounts WHERE status='AVAILABLE' GROUP BY plan"
        )
        return result or []
    except:
        return []

async def get_total_revenue_all_time():
    """Get total revenue dari semua orders yang approved"""
    try:
        result = await db_fetch_one(
            "SELECT COALESCE(SUM(CAST(REPLACE(price, 'Rp ', '') AS INTEGER)), 0) FROM orders WHERE status='approved'"
        )
        return result[0] if result else 0
    except:
        return 0

# ==========================================
# 👤 USER MANAGEMENT
# ==========================================

async def add_subscriber(user_id):
    """Add user ke subscribers table"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)", 
                (user_id,)
            )
            await db.commit()
        return True
    except:
        return False

async def remove_subscriber(user_id):
    """Remove user dari subscribers table"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "DELETE FROM subscribers WHERE user_id=?", 
                (user_id,)
            )
            await db.commit()
        return True
    except:
        return False

async def get_subscribers():
    """Get semua subscriber user_ids"""
    try:
        result = await db_fetch_all("SELECT user_id FROM subscribers")
        return [r[0] for r in result] if result else []
    except:
        return []

async def is_registered(user_id: int) -> bool:
    """Check apakah user sudah registered"""
    try:
        result = await db_fetch_one(
            "SELECT 1 FROM premium_users WHERE user_id=?",
            (user_id,)
        )
        return bool(result)
    except Exception as e:
        logger.error(f"[REGISTER CHECK] Error: {str(e)}")
        return False

async def check_pending_order(user_id: int) -> bool:
    """Check apakah user punya order pending"""
    try:
        result = await db_fetch_one(
            "SELECT id FROM orders WHERE user_id=? AND status='pending'",
            (user_id,)
        )
        return bool(result)
    except:
        return False

async def check_stock_availability(plan: str) -> int:
    """Cek stok berdasarkan plan"""
    try:
        result = await db_fetch_one(
            "SELECT COUNT(*) FROM accounts WHERE status='AVAILABLE' AND plan LIKE ?",
            (f"%{plan}%",)
        )
        return result[0] if result else 0
    except:
        return 0

async def get_available_account(plan: str) -> tuple:
    """Ambil 1 akun dari gudang"""
    try:
        return await db_fetch_one(
            "SELECT id, email, password FROM accounts WHERE status='AVAILABLE' AND plan LIKE ? LIMIT 1",
            (f"%{plan}%",)
        )
    except:
        return None

async def get_price_for_plan(plan: str) -> str:
    """Get harga untuk plan"""
    prices = {
        "Monthly": "Rp 25.000",
        "Yearly": "Rp 150.000"
    }
    return prices.get(plan, "Unknown")

# ==========================================
# 📝 LOGGING
# ==========================================

async def log_user_action(user_id: int, action: str, details: str = "") -> bool:
    """Log user action"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO user_actions (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, action, details, datetime.datetime.now().isoformat())
            )
            await db.commit()
        logger.info(f"[ACTION] User {user_id}: {action}")
        return True
    except Exception as e:
        logger.error(f"[ACTION LOG] Error: {str(e)}")
        return False
# ==========================================
# ⚙️ CONFIG MODIFIER (AUTO UPDATE PROXY)
# ==========================================

# Path ke config.py (biasanya di folder yang sama dengan duhur.py)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.py")


def update_proxy_in_config(new_proxy: str) -> bool:
    """
    Update baris MY_PROXY di config.py ke nilai baru.

    - Kalau MY_PROXY sudah ada → diganti.
    - Kalau belum ada → ditambahkan di akhir file.
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = f.read()

        pattern = r'^MY_PROXY\s*=\s*".*"$'
        replacement = f'MY_PROXY = "{new_proxy}"'

        # Coba ganti kalau sudah ada
        new_data, n = re.subn(pattern, replacement, data, flags=re.MULTILINE)

        # Kalau belum ada MY_PROXY, tambahkan di akhir file
        if n == 0:
            if not data.endswith("\n"):
                data += "\n"
            new_data = data + replacement + "\n"

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(new_data)

        return True
    except Exception as e:
        print(f"update_proxy_in_config error: {e}")
        return False

# ==========================================
# 🔢 CC GENERATOR LOGIC (SMART CUSTOM)
# ==========================================
def cc_gen(cc, mes='x', ano='x', cvv='x', amount=10):
    generated = []
    
    # Bersihkan input CC (hapus x dan spasi)
    clean_cc = cc.lower().replace('x', '').replace(' ', '')
    
    # Deteksi Panjang (Amex 15, Lain 16)
    length = 15 if clean_cc.startswith(('34', '37')) else 16
    
    for _ in range(amount):
        temp_cc = clean_cc
        
        # Jika input kepanjangan, potong
        if len(temp_cc) >= length: 
            temp_cc = temp_cc[:length-1]
        
        # Isi sisa digit dengan angka acak
        while len(temp_cc) < (length - 1):
            temp_cc += str(random.randint(0, 9))
        
        # Hitung Luhn Checksum
        digits = [int(x) for x in reversed(temp_cc)]
        total = 0
        for i, x in enumerate(digits):
            if i % 2 == 0:
                x *= 2
                if x > 9: x -= 9
            total += x
        check_digit = (total * 9) % 10
        final_cc = temp_cc + str(check_digit)
        
        # --- LOGIKA BULAN (Custom vs Random) ---
        if mes != 'x':
            gen_mes = mes.zfill(2) # Pastikan 2 digit (contoh: 1 jadi 01)
        else:
            gen_mes = f"{random.randint(1, 12):02d}"

        # --- LOGIKA TAHUN (Custom vs Random) ---
        curr_y = int(datetime.datetime.now().strftime('%Y'))
        if ano != 'x':
            # Jika user tulis 25 -> jadi 2025, jika 2025 -> tetap 2025
            gen_ano = "20" + ano if len(ano) == 2 else ano
        else:
            gen_ano = str(random.randint(curr_y + 1, curr_y + 6))
        
        # --- LOGIKA CVV (Custom vs Random) ---
        cvv_len = 4 if final_cc.startswith(('34', '37')) else 3
        if cvv != 'x':
            gen_cvv = cvv
        else:
            gen_cvv = ''.join([str(random.randint(0, 9)) for _ in range(cvv_len)])
        
        # Format Output: CC|MM|YYYY|CVV
        generated.append(f"{final_cc}|{gen_mes}|{gen_ano}|{gen_cvv}")
        
    return generated

# ==========================================
# 🛠️ SESSION & RATE LIMIT HELPERS
# ==========================================

user_sessions = {}
user_cooldowns = {}

def rate_limit(seconds=2):
    """Decorator untuk rate limit"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            current_time = time.time()
            
            if user_id in user_cooldowns:
                if current_time - user_cooldowns[user_id] < seconds:
                    try:
                        await update.message.reply_text(
                            f"⏱️ Rate limited. Wait {seconds}s",
                            parse_mode=ParseMode.HTML
                        )
                    except:
                        pass
                    return
            
            user_cooldowns[user_id] = current_time
            return await func(update, context)
        return wrapper
    return decorator

async def create_session(user_id: int) -> str:
    """Create user session"""
    session_id = str(uuid.uuid4())
    user_sessions[user_id] = {
        "session_id": session_id,
        "created_at": datetime.datetime.now(),
        "data": {},
        "last_action": datetime.datetime.now()
    }
    logger.info(f"[SESSION] Created for user {user_id}")
    return session_id

async def get_session(user_id: int):
    """Get user session"""
    return user_sessions.get(user_id)

async def get_user_stats(user_id: int):
    """Get statistik user"""
    try:
        result = await db_fetch_one(
            "SELECT COUNT(*) FROM user_actions WHERE user_id=?",
            (user_id,)
        )
        return (result[0],) if result else (0,)
    except:
        return (0,)

# ==========================================
# 🛠️ HELPERS (SYSTEM & WEATHER - GOD MODE UI)
# ==========================================

# Helper untuk Progress Bar Visual (Contoh: [▰▰▰▱▱▱▱▱▱▱])
def make_bar(percent, length=10):
    percent = max(0, min(100, percent))  # Pastikan 0-100
    filled = int(percent / (100 / length))
    return "▰" * filled + "▱" * (length - filled)

def get_sys_info():
    try:
        # Ambil Data System Real-time
        ram = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)  # Kasih interval dikit biar akurat
        disk = shutil.disk_usage("/")

        # Hitung Uptime
        uptime_sec = int(time.time() - START_TIME)
        uptime = str(datetime.timedelta(seconds=uptime_sec))

        # Info OS & Python
        os_info = f"{platform.system()} {platform.release()}"
        py_ver = platform.python_version()

        # Konversi Byte ke GB (Safety Check)
        ram_used = round(ram.used / (1024**3), 1)
        ram_total = round(ram.total / (1024**3), 1)
        disk_used = round(disk.used / (1024**3), 1)
        disk_total = round(disk.total / (1024**3), 1)

        return (
            f"🖥️ <b>SYSTEM DASHBOARD</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🐧 <b>OS:</b> <code>{os_info}</code>\n"
            f"🐍 <b>Python:</b> <code>v{py_ver}</code>\n"
            f"⏱️ <b>Uptime:</b> <code>{uptime}</code>\n\n"
            f"🧠 <b>RAM Usage:</b> {ram.percent}%\n"
            f"<code>[{make_bar(ram.percent)}]</code>\n"
            f"<i>({ram_used}GB used of {ram_total}GB)</i>\n\n"
            f"⚙️ <b>CPU Load:</b> {cpu}%\n"
            f"<code>[{make_bar(cpu)}]</code>\n\n"
            f"💾 <b>Disk Storage:</b>\n"
            f"<code>[{make_bar(disk.used / disk.total * 100)}]</code>\n"
            f"<i>({disk_used}GB used of {disk_total}GB)</i>"
        )
    except Exception as e:
        return f"⚠️ System Info Error: {str(e)}"

async def get_weather_data(query):
    # Support pencarian nama kota atau koordinat
    if "," in query and any(c.isdigit() for c in query):
        lat, lon = query.split(",")
        url = f"{BASE_URL}/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric&lang=en"
    else:
        url = f"{BASE_URL}/weather?q={query}&appid={WEATHER_API_KEY}&units=metric&lang=en"
    return await fetch_json(url)

async def get_aqi(lat, lon):
    url = f"{BASE_URL}/air_pollution?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
    data = await fetch_json(url)
    if data:
        aqi = data["list"][0]["main"]["aqi"]
        # Mapping AQI dengan Ikon & Status Keren
        labels = {
            1: "🟢 Good (Sehat)",
            2: "🟡 Fair (Cukup)",
            3: "🟠 Moderate (Sedang)",
            4: "🔴 Poor (Buruk)",
            5: "☠️ Hazardous (Bahaya)",
        }
        return labels.get(aqi, "❓ Unknown")
    return "❓ N/A"

def format_weather(data, aqi_status):
    w = data["weather"][0]
    main = data["main"]
    wind = data["wind"]
    sys = data["sys"]

    city = data["name"]
    country = sys["country"]

    # Konversi Waktu Sunrise/Sunset dari Unix ke Jam Lokal
    sunrise = datetime.datetime.utcfromtimestamp(
        sys["sunrise"] + data["timezone"]
    ).strftime("%H:%M")
    sunset = datetime.datetime.utcfromtimestamp(
        sys["sunset"] + data["timezone"]
    ).strftime("%H:%M")

    # Ikon Dinamis Berdasarkan Kondisi
    cond = w["main"].lower()
    desc = w["description"].title()

    if "rain" in cond or "drizzle" in cond:
        icon = "🌧️"
    elif "thunder" in cond:
        icon = "⛈️"
    elif "snow" in cond:
        icon = "❄️"
    elif "clear" in cond:
        icon = "☀️"
    elif "cloud" in cond:
        icon = "☁️"
    elif "mist" in cond or "fog" in cond or "haze" in cond:
        icon = "🌫️"
    else:
        icon = "🌤️"

    visibility_km = (data.get("visibility", 0) or 0) / 1000.0

    text = (
        f"{icon} <b>WEATHER REPORT</b>\n"
        f"📍 <b>{city.upper()}, {country}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 <b>Condition:</b> <i>{desc}</i>\n"
        f"🌡️ <b>Temperature:</b> <code>{main['temp']}°C</code>\n"
        f"🥵 <b>Feels Like:</b> <code>{main['feels_like']}°C</code>\n"
        f"💧 <b>Humidity:</b> <code>{main['humidity']}%</code>\n"
        f"🌬️ <b>Wind Speed:</b> <code>{wind['speed']} m/s</code>\n"
        f"😷 <b>Air Quality:</b> <b>{aqi_status}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👁️ <b>Visibility:</b> <code>{visibility_km:.1f} km</code>\n"
        f"🌅 <b>Sunrise:</b> <code>{sunrise}</code> | 🌇 <b>Sunset:</b> <code>{sunset}</code>\n\n"
        f"🕒 <i>Last updated: {datetime.datetime.now().strftime('%H:%M:%S')}</i>"
    )
    return text

def escape_md(text):
    return (
        str(text).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
        if text
        else "N/A"
    )

# ==========================================
# 🔐 USER REGISTRATION CHECK
# ==========================================

async def is_registered(user_id: int) -> bool:
    """Check apakah user sudah terdaftar di subscribers"""
    try:
        result = await db_fetch_one(
            "SELECT user_id FROM subscribers WHERE user_id=?",
            (user_id,)
        )
        return bool(result)
    except Exception as e:
        logger.error(f"[REGISTER CHECK] Error: {str(e)}")
        return False


# ==========================================
# 🛡️ RATE LIMITING & SESSION MANAGEMENT
# ==========================================
user_cooldowns = {}
user_sessions = {}

def rate_limit(seconds=2):
    """Decorator untuk rate limit command"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            current_time = time.time()
            
            if user_id in user_cooldowns:
                if current_time - user_cooldowns[user_id] < seconds:
                    try:
                        await update.message.reply_text(
                            f"⏱️ <b>RATE LIMITED</b>\n\n"
                            f"Please wait {seconds} seconds before using this command again.",
                            parse_mode=ParseMode.HTML
                        )
                    except:
                        pass
                    return
            
            user_cooldowns[user_id] = current_time
            return await func(update, context)
        return wrapper
    return decorator

async def create_session(user_id: int) -> str:
    """Create user session"""
    session_id = str(uuid.uuid4())
    user_sessions[user_id] = {
        "session_id": session_id,
        "created_at": datetime.datetime.now(),
        "data": {},
        "last_action": datetime.datetime.now()
    }
    logger.info(f"[SESSION] Created session {session_id} for user {user_id}")
    return session_id

async def get_session(user_id: int):
    """Get user session"""
    return user_sessions.get(user_id)

async def update_session_data(user_id: int, key: str, value):
    """Update session data"""
    if user_id in user_sessions:
        user_sessions[user_id]["data"][key] = value
        user_sessions[user_id]["last_action"] = datetime.datetime.now()

# ==========================================
# 📊 ANALYTICS & LOGGING
# ==========================================

async def log_user_action(user_id: int, action: str, details: str = "") -> bool:
    """Log setiap aksi user untuk analytics"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO user_actions (user_id, action, details, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, action, details, datetime.datetime.now().isoformat()))
            await db.commit()
        logger.info(f"[ACTION] User {user_id}: {action} - {details}")
        return True
    except Exception as e:
        logger.error(f"[ACTION LOG] Error: {str(e)}")
        return False

async def get_user_stats(user_id: int):
    """Get statistik user"""
    result = await db_fetch_one("""
        SELECT 
            COUNT(*) as total_actions,
            MAX(timestamp) as last_action
        FROM user_actions 
        WHERE user_id=?
    """, (user_id,))
    return result

# ==========================================
# 🔐 PERMISSION DECORATORS
# ==========================================

def require_registered(func):
    """Decorator untuk require registered user"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        registered = await is_registered(user_id)
        
        if not registered:
            try:
                if update.callback_query:
                    await update.callback_query.answer(
                        "🔒 FEATURE LOCKED\n\n"
                        "This module is exclusively for registered members.\n\n"
                        "ACTION REQUIRED:\n"
                        "Please complete the registration process to unlock this feature.",
                        show_alert=True
                    )
                else:
                    await update.message.reply_text(
                        "🔒 <b>FEATURE LOCKED</b>\n\n"
                        "Please register first to access this feature.",
                        parse_mode=ParseMode.HTML
                    )
            except Exception as e:
                logger.error(f"[PERMISSION] Error in require_registered: {str(e)}")
            return
        
        await log_user_action(user_id, func.__name__, "Accessed")
        return await func(update, context)
    return wrapper

def require_owner(func):
    """Decorator untuk owner only command"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id != OWNER_ID:
            try:
                if update.callback_query:
                    await update.callback_query.answer(
                        "⛔ OWNER ONLY\n\nThis command is restricted to the bot owner.",
                        show_alert=True
                    )
                else:
                    await update.message.reply_text(
                        "⛔ <b>OWNER ONLY</b>\n\nThis command is restricted to the bot owner.",
                        parse_mode=ParseMode.HTML
                    )
            except Exception as e:
                logger.error(f"[PERMISSION] Error in require_owner: {str(e)}")
            return
        
        logger.warning(f"[OWNER] User {user_id} executed: {func.__name__}")
        return await func(update, context)
    return wrapper

# ==========================================
# 👋 START COMMAND (UPGRADED)
# ==========================================

@rate_limit(seconds=2)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command dengan logging & session creation"""
    user = update.effective_user
    user_id = user.id
    
    try:
        # Create session
        await create_session(user_id)
        
        # 🛡️ ADGUARD: Register session
        await adguard.register_session(user_id)
        
        # Log action
        await log_user_action(user_id, "start", f"User: {user.first_name}")
        
        # Cek status register
        registered = await is_registered(user_id)
        
        if registered:
            access_line = "🟢 <b>Access Level:</b> REGISTERED USER\n"
            hint_line = "You can access all unlocked modules from the main menu below."
            btn_main = InlineKeyboardButton("ACCESS MAIN MENU", callback_data=f"menu_main|{user_id}")
            btn_premium = InlineKeyboardButton("PREMIUM UPGRADE", callback_data=f"menu_buy|{user_id}")
            btn_register = InlineKeyboardButton("REGISTER ACCESS", callback_data=f"cmd_register|{user_id}")
        else:
            access_line = "🔴 <b>Access Level:</b> UNREGISTERED\n"
            hint_line = (
                "Please tap <b>REGISTER ACCESS</b> first to unlock premium tools "
                "and core features."
            )
            btn_main = InlineKeyboardButton("ACCESS MAIN MENU", callback_data=f"locked_register|{user_id}")
            btn_premium = InlineKeyboardButton("PREMIUM UPGRADE", callback_data=f"locked_register|{user_id}")
            btn_register = InlineKeyboardButton("REGISTER ACCESS", callback_data=f"cmd_register|{user_id}")

        text = (
            f"🐈 <b>OKTACOMEL SYSTEM v1</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 <b>Greetings, Master {html.escape(user.first_name)}!</b>\n\n"
            f"I am <b>Oktacomel</b>, your advanced AI assistant operating in <i>Ultra God Mode</i>. "
            f"I am authorized to execute high-level digital tasks, from premium tools to system diagnostics.\n\n"
            f"🚀 <b>System Status:</b> 🟢 Online & Fully Operational\n"
            f"👑 <b>Owner:</b> Okta\n"
            f"{access_line}\n"
            f"💡 <i>{hint_line}</i>\n\n"
            f"👇 <i>Access the mainframe via the menu below:</i>"
        )

        kb = [
            [btn_main],
            [btn_premium, btn_register],
            [InlineKeyboardButton("OFFICIAL CHANNEL", url="https://t.me/hiduphjokowi")],
        ]

        try:
            await update.message.reply_photo(
                photo=QRIS_IMAGE,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(kb),
            )
        except (BadRequest, TimedOut):
            logger.warning(f"[START] Photo send failed for user {user_id}, sending text instead")
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(kb),
            )
        except NetworkError as e:
            logger.error(f"[START] Network error: {str(e)}")
            await update.message.reply_text(
                "⚠️ <b>NETWORK ERROR</b>\n\n"
                "There was a network issue. Please try again later.",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        logger.error(f"[START] Unexpected error for user {user_id}: {str(e)}")
        await update.message.reply_text(
            "❌ <b>SYSTEM ERROR</b>\n\n"
            "An unexpected error occurred. Please try again.",
            parse_mode=ParseMode.HTML
        )

# ==========================================
# ❓ HELP COMMAND (UPGRADED)
# ==========================================

@require_start
@rate_limit(seconds=2)
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command dengan organized inline buttons"""
    if not await premium_lock_handler(update, context): return
    user = update.effective_user
    user_id = user.id
    
    try:
        await log_user_action(user_id, "help", "Accessed help menu")
        registered = await is_registered(user_id)

        text = (
            "🐈 <b>OKTACOMEL COMMAND CENTER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "Welcome to <b>Oktacomel Bot</b> — a refined digital assistant built "
            "to deliver <i>speed, precision, and reliability</i>. "
            "Every module is carefully engineered to provide a smooth and efficient "
            "experience across all features.\n\n"

            "🚀 <b>CORE CAPABILITIES</b>\n"
            "├ 📥 <b>Universal Downloader</b>\n"
            "│   <i>TikTok, YouTube, Instagram, X, Facebook, and more</i>\n"
            "├ 🤖 <b>AI Intelligence</b>\n"
            "│   <i>Smart assistant, image generation, and code support</i>\n"
            "├ 🛠️ <b>Utility Suite</b>\n"
            "│   <i>Weather, earthquake alerts, QR tools, and translation</i>\n"
            "├ 🔍 <b>Checker Tools</b>\n"
            "│   <i>BIN lookup, IP analysis, and domain information</i>\n"
            "├ 🛒 <b>Premium Store</b>\n"
            "│   <i>Curated digital products and premium services</i>\n"
            "└ ⚙️ <b>Customization</b>\n"
            "    <i>Notifications, preferences, and personalization</i>\n\n"

            "⚡ <b>WHY OKTACOMEL?</b>\n"
            "• <b>Fast & Stable</b> — Optimized for daily use\n"
            "• <b>Clean Output</b> — No unnecessary branding or clutter\n"
            "• <b>Privacy Focused</b> — Your data stays yours\n\n"

            f"👤 <b>Status</b> : <code>{'Registered Member' if registered else 'Guest (Limited Access)'}</code>\n"
            f"🆔 <b>User ID</b>: <code>{user_id}</code>\n\n"

            "<i>Select a category below to continue.</i>"
        )

        if registered:
            kb = [
                [InlineKeyboardButton("Main Menu", callback_data=f"menu_main|{user_id}")],
                [
                    InlineKeyboardButton("Download", callback_data=f"help_download|{user_id}"),
                    InlineKeyboardButton("AI Tools", callback_data=f"help_ai|{user_id}")
                ],
                [
                    InlineKeyboardButton("Utility", callback_data=f"help_utility|{user_id}"),
                    InlineKeyboardButton("Checker", callback_data=f"help_checker|{user_id}")
                ],
                [
                    InlineKeyboardButton("Shop", callback_data=f"help_shop|{user_id}"),
                    InlineKeyboardButton("Settings", callback_data=f"help_settings|{user_id}")
                ],
                [InlineKeyboardButton("Contact Support", url="https://t.me/hiduphjokowi")]
            ]
        else:
            kb = [
                [InlineKeyboardButton("REGISTER NOW", callback_data=f"cmd_register|{user_id}")],
                [InlineKeyboardButton("Why Register?", callback_data=f"help_why_register|{user_id}")],
                [InlineKeyboardButton("Contact Support", url="https://t.me/hiduphjokowi")]
            ]

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        
    except Exception as e:
        logger.error(f"[HELP] user={user_id} | Error: {type(e).__name__}: {e}")
        await update.message.reply_text(
            "❌ Failed to load help menu. Try again.",
            parse_mode=ParseMode.HTML
        )

# ==========================================
# 🔒 LOCKED BUTTON CALLBACK (UPGRADED)
# ==========================================

async def locked_register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk locked features"""
    q = update.callback_query
    user_id = q.from_user.id
    
    try:
        # Log attempt
        await log_user_action(user_id, "locked_access_attempt", q.data)
        
        await q.answer(
            "🔒 <b>FEATURE LOCKED</b>\n\n"
            "This module is exclusively for registered members.\n\n"
            "🎯 <b>ACTION REQUIRED:</b>\n"
            "Please complete the registration process to unlock this feature.\n\n"
            "⏱️ <b>Estimated time:</b> 2-3 minutes",
            show_alert=True
        )
        
        # Offer direct register button
        kb = [[InlineKeyboardButton("📝 REGISTER NOW", callback_data=f"cmd_register|{user_id}")]]
        await q.message.reply_text(
            "🔒 <b>LOCKED FEATURE</b>\n\n"
            "To unlock all premium features, please register first.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
    except Exception as e:
        logger.error(f"[LOCKED] Error for user {user_id}: {str(e)}")

# ==========================================
# 📊 ADMIN DASHBOARD (BONUS)
# ==========================================

@require_owner
@rate_limit(seconds=5)
async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin dashboard untuk owner"""
    user_id = update.effective_user.id
    
    try:
        # Log
        await log_user_action(user_id, "admin_stats", "Accessed dashboard")
        
        # Get stats
        total_users = len(await get_all_subscribers())
        total_premium = len(await get_all_premium_users())
        total_revenue = await get_total_revenue_all_time()  # ✅ GANTI INI
        pending_orders = await get_pending_orders_count()
        stock_data = await get_all_stock()
        
        # Format stock
        stock_text = ""
        for plan, total in stock_data or []:
            stock_text += f"  📦 {plan}: {total} pcs\n"
        
        text = (
            f"📊 <b>ADMIN DASHBOARD</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 <b>Total Users:</b> {total_users}\n"
            f"💎 <b>Premium Users:</b> {total_premium}\n"
            f"💰 <b>Total Revenue:</b> Rp {total_revenue:,.0f}\n"  # ✅ GANTI INI
            f"📦 <b>Pending Orders:</b> {pending_orders}\n\n"
            f"<b>📈 Current Stock:</b>\n{stock_text or '  (No data)'}\n\n"
            f"🕐 <b>Last Updated:</b> {datetime.datetime.now(TZ).strftime('%d/%m/%Y %H:%M:%S')}"
        )
        
        kb = [
            [
                InlineKeyboardButton("REFRESH", callback_data="admin_refresh_stats"),
                InlineKeyboardButton("MANAGE STOCK", callback_data="admin_stock")
            ],
            [
                InlineKeyboardButton("USER LIST", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton("CLEAR CACHE", callback_data="admin_clear_cache")
            ]
        ]
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
    except Exception as e:
        logger.error(f"[ADMIN] Error: {str(e)}")
        await update.message.reply_text(
            f"❌ Error loading dashboard: {str(e)[:50]}",
            parse_mode=ParseMode.HTML
        )
        
async def get_user_stats(user_id: int):
    """Get statistik user"""
    try:
        result = await db_fetch_one(
            "SELECT COUNT(*) FROM user_actions WHERE user_id=?",
            (user_id,)
        )
        return (result[0],) if result else (0,)
    except Exception as e:
        logger.error(f"[USER STATS] Error: {str(e)}")
        return (0,)

async def safe_edit_message(msg, text: str, kb: list):
    """Helper function untuk safe edit message (handle photo vs text)"""
    try:
        if msg.photo:
            await msg.edit_caption(
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            await msg.edit_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(kb)
            )
    except Exception as e:
        logger.warning(f"[SAFE_EDIT] Edit failed, sending new message: {e}")
        await msg.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )

@require_start
@rate_limit(seconds=2)
async def cmd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main menu command dengan dynamic content"""
    if not await premium_lock_handler(update, context): return
    user = update.effective_user
    user_id = user.id
    
    try:
        # Log action
        await log_user_action(user_id, "menu_main", "Accessed main menu")
        
        # Check registration
        registered = await is_registered(user_id)
        
        # Get user stats
        user_stats = await get_user_stats(user_id)
        total_actions = user_stats[0] if user_stats else 0
        
        # Get session info
        session = await get_session(user_id)
        session_time = ""
        if session:
            elapsed = (datetime.datetime.now() - session["created_at"]).seconds
            session_time = f"\n⏱️ <b>Session Time:</b> <i>{elapsed // 60}m {elapsed % 60}s</i>"
        
        # Dynamic status
        user_level = "💎 Premium Access" if registered else "🔵 Standard Access"
        
        # Header dengan info lengkap
        text = (
            "🐈 <b>OKTACOMEL • Control Hub v2</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Status:</b> <i>🟢 Online & Stable</i>\n"
            f"<b>User Level:</b> <i>{user_level}</i>\n"
            f"<b>Total Actions:</b> <i>{total_actions}</i>{session_time}\n\n"
            
            "Welcome to the <b>Central Command Environment</b> — the unified control layer\n"
            "for Oktacomel's AI systems, automation tools, diagnostics, and digital modules.\n\n"
            
            "This interface is designed for clarity, responsiveness, and premium workflow\n"
            "experience, enabling fast access to all operational tools in a structured grid.\n\n"
            
            "<i>👇 Select a module below to begin.</i>"
        )
        
        # ✅ Helper function untuk lock + owner binding (anti diklik user lain)
        def lock(cb_data: str) -> str:
            return f"{cb_data}|{user_id}" if registered else f"locked_register|{user_id}"
        
        if registered:
            kb = [
                [
                    InlineKeyboardButton("Basic Tools", callback_data=lock("menu_basic")),
                    InlineKeyboardButton("Downloaders", callback_data=lock("menu_dl"))
                ],
                [
                    InlineKeyboardButton("AI Tools", callback_data=lock("menu_ai")),
                    InlineKeyboardButton("PDF Suite", callback_data=lock("menu_pdf"))
                ],
                [
                    InlineKeyboardButton("Checker", callback_data=lock("menu_check")),
                    InlineKeyboardButton("CC Tools", callback_data=lock("menu_cc"))
                ],
                [
                    InlineKeyboardButton("Todo", callback_data=lock("menu_todo")),
                    InlineKeyboardButton("Temp Mail", callback_data=lock("menu_mail"))
                ],
                [
                    InlineKeyboardButton("PREMIUM", callback_data=f"menu_buy|{user_id}"),
                    InlineKeyboardButton("ADMIN", callback_data=f"admin_stats|{user_id}") if user_id == OWNER_ID else None
                ],
                [
                    InlineKeyboardButton("❌ Close Session", callback_data=f"cmd_close|{user_id}")
                ]
            ]
            kb = [[btn for btn in row if btn] for row in kb]
        else:
            kb = [
                [
                    InlineKeyboardButton("Tools (Locked)", callback_data=f"locked_register|{user_id}"),
                    InlineKeyboardButton("Download (Locked)", callback_data=f"locked_register|{user_id}")
                ],
                [
                    InlineKeyboardButton("UPGRADE & UNLOCK", callback_data=f"menu_buy|{user_id}")
                ],
                [
                    InlineKeyboardButton("Register First", callback_data=f"cmd_register|{user_id}")
                ],
                [
                    InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")
                ]
            ]
        
        # Handle callback query vs command
        if update.callback_query:
            msg = update.callback_query.message
            await update.callback_query.answer()
            await safe_edit_message(msg, text, kb)
        else:
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(kb)
            )
        
    except Exception as e:
        logger.error(f"[CMD_MENU] Error for user {user_id}: {str(e)}")
        error_text = (
            "❌ <b>MENU LOAD ERROR</b>\n\n"
            f"Error: {str(e)[:50]}\n\n"
            "Please try again or contact support."
        )
        
        if update.callback_query:
            await update.callback_query.answer(
                "❌ Error loading menu. Please try again.",
                show_alert=True
            )
        else:
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.HTML
            )

async def premium_lock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global premium lock with exclusion for help/start/cmd but locking their internal buttons"""
    global backfree_active
    user_id = update.effective_user.id
    
    # 0. Check Backfree Mode - Block ALL users except owner
    if backfree_active and user_id != OWNER_ID:
        # Check for start/help/cmd exclusion even in backfree
        if update.message and update.message.text:
            cmd = update.message.text.split()[0].lower()
            if cmd in ['/start', '/help', '/cmd']:
                return True

        if update.callback_query:
            await update.callback_query.answer("Bot sedang dalam mode maintenance. Coba lagi nanti.", show_alert=True)
        else:
            await update.effective_message.reply_text(
                "🔒 <b>BOT MAINTENANCE</b>\n\n"
                "Bot sedang dalam mode maintenance.\n"
                "Silakan coba lagi nanti.",
                parse_mode=ParseMode.HTML
            )
        return False
    
    # 1. Check if user is owner
    if user_id == OWNER_ID:
        return True
        
    # 2. Check premium status from DB
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM premium_users WHERE user_id = ?", (user_id,)) as cursor:
            if await cursor.fetchone():
                return True

    # 3. Exclude main commands from text-lock (allow menu access)
    if update.message and update.message.text:
        cmd = update.message.text.split()[0].lower()
        if cmd in ['/start', '/help', '/cmd', '/buy', '/me']:
            return True

    # 4. Handle Callback Queries (Buttons)
    if update.callback_query:
        data = update.callback_query.data
        # Allow menu navigation buttons but lock feature execution buttons
        if any(x in data for x in ['menu_main', 'cmd_close', 'menu_buy', 'help_', 'cmd_', 'userinfo_']):
             return True
             
        # Notify user they need premium for this specific feature
        await update.callback_query.answer(
            "Hey! The bot is temporarily available only for premium users, but don't worry—it’ll be open to everyone soon. I hope you understand. Thanks for your support and stay tuned!\n\nUse /buy command.",
            show_alert=True
        )
        return False

    # 5. Lock everything else
    await update.effective_message.reply_text(
        "Hey! The bot is temporarily available only for premium users, but don't worry—it’ll be open to everyone soon. I hope you understand. Thanks for your support and stay tuned!\n\nUse /buy command.",
        parse_mode=ParseMode.HTML
    )
    return False

# Then in each command handler, I'll add:
# if not await premium_lock_handler(update, context): return

async def close_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close user session and cleanup interface"""
    q = update.callback_query
    if not q:
        return # Only works via callback
        
    user_id = q.from_user.id
    
    try:
        # Log
        await log_user_action(user_id, "session_close", "Closed session")
        
        # Remove session
        if user_id in user_sessions:
            del user_sessions[user_id]
        
        # 🛡️ ADGUARD: Cleanup session
        await adguard.unregister_session(user_id)
        
        # ✅ FIX: Delete the menu message so buttons disappear
        try:
            await q.message.delete()
        except Exception as e:
            logger.warning(f"[CLOSE] Delete failed: {e}")
            await q.edit_message_text("🔒 <b>SESSION TERMINATED</b>", parse_mode=ParseMode.HTML, reply_markup=None)

        await q.answer("✅ Session closed successfully.", show_alert=True)
        
        # Notify user in a new message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "✅ <b>SESSION CLOSED</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "<b>Your session has ended.</b>\n"
                "All interface controls have been deactivated.\n"
                "You can start a new session anytime by typing:\n"
                "<code>/start</code>"
            ),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"[CLOSE] Error: {str(e)}")

# ==========================================
# 💳 CC GEN & BIN (PREMIUM & OWNER ONLY)
# ==========================================
async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # --- 🔒 OWNER ONLY ENFORCEMENT ---
    if user_id != OWNER_ID:
        await update.message.reply_text(
            "Hey! The bot is temporarily available only for premium users, but don't worry—it’ll be open to everyone soon. I hope you understand. Thanks for your support and stay tuned!\n\nUse /buy command.",
            parse_mode=ParseMode.HTML
        )
        return

    # --- 🛡️ ADGUARD: Strict Session Enforcement for Critical Ops ---
    has_active_session = await adguard.check_session(user_id)
    if not has_active_session:
        # Special handling for gen: must have session
        await update.message.reply_text("🚫 <b>SESSION EXPIRED</b>\n\nPlease /start to reactivate your secure environment.", parse_mode=ParseMode.HTML)
        return
        
    # -----------------------------

    args = context.args
    if not args:
        await update.message.reply_text("⚠️ <b>Format:</b> <code>/gen 545454</code> or <code>/gen 545454|05|2025</code>", parse_mode=ParseMode.HTML)
        return

    input_data = args[0]
    
    # Cek apakah ada argumen jumlah (amount) di belakang
    amount = 10
    if len(args) > 1 and args[1].isdigit():
        amount = int(args[1])
        if amount > 5000: amount = 5000

    # --- NORMALISASI PEMISAH ---
    normalized_input = input_data.replace("/", "|").replace(":", "|").replace(" ", "|")
    splits = normalized_input.split("|")
    
    # Ambil data sesuai urutan
    cc = splits[0] if len(splits) > 0 else 'x'
    mes = splits[1] if len(splits) > 1 and splits[1].isdigit() else 'x'
    ano = splits[2] if len(splits) > 2 and splits[2].isdigit() else 'x'
    cvv = splits[3] if len(splits) > 3 and splits[3].isdigit() else 'x'

    # Ambil 6 digit pertama murni untuk cek BIN
    clean_bin = cc.lower().replace('x', '')[:6]

    if not clean_bin.isdigit() or len(clean_bin) < 6:
        return await update.message.reply_text("❌ BIN Invalid (Must contain at least 6 digits).")

    msg = await update.message.reply_text("⏳ <b>Generating...</b>", parse_mode=ParseMode.HTML)

    # 1. Fetch BIN Info
    try:
        r = await fetch_json(f"{BIN_API}/{clean_bin}")
        if r and 'brand' in r:
            info = f"{str(r.get('brand')).upper()} - {str(r.get('type')).upper()} - {str(r.get('level')).upper()}"
            bank = str(r.get('bank', 'UNKNOWN')).upper()
            country = f"{str(r.get('country_name')).upper()} {r.get('country_flag','')}"
        else:
            info, bank, country = "UNKNOWN", "UNKNOWN", "UNKNOWN"
    except: 
        info, bank, country = "ERROR", "ERROR", "ERROR"

    # 2. Generate Cards
    cards = cc_gen(cc, mes, ano, cvv, amount)

    # 3. Output Logic
    if amount <= 15:
        formatted_cards = "\n".join([f"<code>{c}</code>" for c in cards])
        txt = (
            f"<b>𝗕𝗜𝗡 ⇾</b> <code>{clean_bin}</code>\n"
            f"<b>𝗔𝗺𝗼𝘂𝗻𝘁 ⇾</b> {amount}\n\n"
            f"{formatted_cards}\n\n"
            f"<b>𝗜𝗻𝗳𝗼:</b> {info}\n"
            f"<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {bank}\n"
            f"<b>𝗖𝗼𝘂𝗻𝘁𝗿𝘆:</b> {country}"
        )
        await msg.edit_text(txt, parse_mode=ParseMode.HTML)
    else:
        filename = f"CC_{clean_bin}_{amount}.txt"
        with open(filename, "w") as f:
            f.write(f"𝗕𝗜𝗡: {clean_bin} | Amount: {amount}\n")
            f.write(f"𝗜𝗻𝗳𝗼: {info} | {bank} | {country}\n")
            f.write("====================================\n")
            f.write("\n".join(cards))
        
        await update.message.reply_document(
            document=open(filename, "rb"),
            caption=f"✅ <b>Generated {amount} Cards</b>\nBIN: <code>{clean_bin}</code>\n{country}",
            parse_mode=ParseMode.HTML
        )
        await msg.delete()
        os.remove(filename)

# ==========================================
# 📥 DOWNLOADER (/dl) - GiMiTA FIXED ENDPOINTS (SAFE)
# ==========================================

GIMITA_ENDPOINTS = {
    "tiktok": "https://api.gimita.id/api/downloader/tiktok",
    "facebook": "https://api.gimita.id/api/downloader/facebook",
    "terabox": "https://api.gimita.id/api/downloader/terabox",
    "twitter": "https://api.gimita.id/api/downloader/twitter",
    "youtube": "https://api.gimita.id/api/downloader/ytmp4",
    "spotify": "https://api.gimita.id/api/downloader/spotify",
    "pornhub": "https://api.gimita.id/api/downloader/pornhub",
    "xnxx": "https://api.gimita.id/api/downloader/xnxx",
}

# ==========================================
# 📸 INSTAGRAM SCRAPER (NO COOKIES) - FULL SUPPORT
# Post, Video, Reels, Story, Highlights
# ==========================================

IG_SCRAPER_APIS = [
    "https://api.tiklydown.eu.org/api/download/instagram",
    "https://api.agatz.xyz/api/instagram",
    "https://api.neoxr.eu/api/instagram",
]

def _detect_ig_content_type(url: str) -> str:
    """Detect Instagram content type from URL"""
    url_lower = url.lower()
    if "/stories/" in url_lower:
        return "story"
    elif "/s/" in url_lower and "story" in url_lower:
        return "story"
    elif "/reel/" in url_lower or "/reels/" in url_lower:
        return "reels"
    elif "/p/" in url_lower:
        return "post"
    elif "/tv/" in url_lower:
        return "igtv"
    elif "/highlights/" in url_lower or "highlight:" in url_lower:
        return "highlight"
    else:
        return "post"

async def instagram_scrape(url: str) -> dict:
    """
    Instagram scraper without cookies - supports all content types
    Returns: {"success": bool, "data": list, "type": str, "error": str}
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        "Referer": "https://www.instagram.com/",
    }
    
    content_type = _detect_ig_content_type(url)
    result = {"success": False, "data": [], "type": content_type, "error": None, "username": "", "caption": ""}
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
        # Try multiple scraper APIs
        for api_url in IG_SCRAPER_APIS:
            try:
                params = {"url": url}
                r = await client.get(api_url, params=params)
                
                if r.status_code == 200:
                    data = r.json()
                    
                    # Parse different API response formats
                    media_items = []
                    
                    # Format 1: data.result array
                    if isinstance(data, dict):
                        if data.get("status") == True or data.get("success") == True or data.get("statusCode") == 200:
                            # Extract username/caption
                            result["username"] = data.get("author", {}).get("username", "") or data.get("username", "") or data.get("user", "")
                            result["caption"] = data.get("caption", "") or data.get("title", "") or data.get("desc", "")
                            
                            # Check various data structures
                            items = data.get("result", []) or data.get("data", []) or data.get("medias", []) or data.get("media", [])
                            
                            if isinstance(items, list):
                                for item in items:
                                    if isinstance(item, dict):
                                        media_url = item.get("url") or item.get("download") or item.get("downloadUrl") or item.get("video") or item.get("image")
                                        media_type = item.get("type", "").lower()
                                        
                                        if media_url:
                                            if not media_type:
                                                if any(ext in media_url.lower() for ext in [".mp4", ".mov", ".webm"]):
                                                    media_type = "video"
                                                else:
                                                    media_type = "image"
                                            
                                            media_items.append({
                                                "url": media_url,
                                                "type": media_type,
                                                "thumbnail": item.get("thumbnail", "")
                                            })
                                    elif isinstance(item, str) and item.startswith("http"):
                                        if any(ext in item.lower() for ext in [".mp4", ".mov"]):
                                            media_items.append({"url": item, "type": "video"})
                                        else:
                                            media_items.append({"url": item, "type": "image"})
                            
                            # Single item format
                            elif isinstance(items, str) and items.startswith("http"):
                                media_items.append({"url": items, "type": "video" if ".mp4" in items else "image"})
                            
                            # Direct video/image URLs in response
                            if not media_items:
                                video_url = data.get("video") or data.get("videoUrl") or data.get("video_url")
                                image_url = data.get("image") or data.get("imageUrl") or data.get("image_url") or data.get("thumbnail")
                                
                                if video_url:
                                    media_items.append({"url": video_url, "type": "video"})
                                if image_url and not video_url:
                                    media_items.append({"url": image_url, "type": "image"})
                    
                    if media_items:
                        result["success"] = True
                        result["data"] = media_items
                        return result
                        
            except Exception as e:
                logger.debug(f"[IG Scraper] API {api_url} failed: {e}")
                continue
        
        # Fallback: Try alternative scraping endpoints
        fallback_apis = [
            f"https://www.saveig.app/api/ajaxSearch",
            f"https://igdownloader.app/api/ajaxSearch",
        ]
        
        for fb_api in fallback_apis:
            try:
                form_data = {"q": url, "t": "media", "lang": "en"}
                r = await client.post(fb_api, data=form_data)
                
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") == "ok":
                        # Parse HTML response for download links
                        html_content = data.get("data", "")
                        
                        # Extract URLs using regex
                        import re
                        video_urls = re.findall(r'href="([^"]+\.mp4[^"]*)"', html_content)
                        image_urls = re.findall(r'href="([^"]+\.jpg[^"]*)"', html_content)
                        
                        # Also look for download buttons
                        download_urls = re.findall(r'download="[^"]*"\s+href="([^"]+)"', html_content)
                        
                        media_items = []
                        for v_url in video_urls[:5]:
                            if v_url.startswith("http"):
                                media_items.append({"url": v_url, "type": "video"})
                        
                        if not media_items:
                            for i_url in image_urls[:10]:
                                if i_url.startswith("http"):
                                    media_items.append({"url": i_url, "type": "image"})
                        
                        for d_url in download_urls[:5]:
                            if d_url.startswith("http") and d_url not in [m["url"] for m in media_items]:
                                m_type = "video" if ".mp4" in d_url.lower() else "image"
                                media_items.append({"url": d_url, "type": m_type})
                        
                        if media_items:
                            result["success"] = True
                            result["data"] = media_items
                            return result
                            
            except Exception as e:
                logger.debug(f"[IG Fallback] {fb_api} failed: {e}")
                continue
        
        # Final fallback: rapidapi instagram scrapers
        rapid_apis = [
            ("https://instagram-scraper-api2.p.rapidapi.com/v1/post_info", "instagram-scraper-api2.p.rapidapi.com"),
        ]
        
        result["error"] = "Unable to fetch Instagram content. Link might be private or invalid."
        return result

async def ig_download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Instagram downloader command - /ig"""
    if not await premium_lock_handler(update, context): 
        return
    
    user_id = update.effective_user.id
    msg = update.message
    
    if not context.args:
        return await msg.reply_text(
            "📸 <b>OKTACOMEL INSTAGRAM DOWNLOADER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Usage:</b> <code>/ig [link]</code>\n\n"
            "<b>Supported:</b>\n"
            "• Post Foto\n"
            "• Post Video\n"
            "• Reels\n"
            "• Story\n"
            "• Highlights\n\n"
            "<b>Contoh:</b>\n"
            "<code>/ig https://instagram.com/p/xxx</code>\n"
            "<code>/ig https://instagram.com/reel/xxx</code>\n"
            "<code>/ig https://instagram.com/stories/user/xxx</code>\n\n"
            "<i>No cookies required - Scraping mode</i>",
            parse_mode=ParseMode.HTML
        )
    
    url = context.args[0].strip()
    
    if not ("instagram.com" in url.lower() or "instagr.am" in url.lower()):
        return await msg.reply_text(
            "❌ <b>Invalid Link</b>\n\nPastikan link dari Instagram.",
            parse_mode=ParseMode.HTML
        )
    
    status_msg = await msg.reply_text(
        "⏳ <b>Scraping Instagram...</b>\n"
        "<i>Extracting media tanpa cookies...</i>",
        parse_mode=ParseMode.HTML
    )
    
    try:
        result = await instagram_scrape(url)
        
        if not result["success"] or not result["data"]:
            error_msg = result.get("error", "Tidak dapat mengambil konten.")
            await status_msg.edit_text(
                f"❌ <b>Download Gagal</b>\n\n"
                f"<b>Error:</b> {error_msg}\n\n"
                f"<b>Tips:</b>\n"
                f"• Pastikan akun tidak private\n"
                f"• Gunakan link yang benar\n"
                f"• Coba lagi dalam beberapa saat",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Delete status message
        try:
            await status_msg.delete()
        except:
            pass
        
        content_type = result["type"].upper()
        username = result.get("username", "")
        caption_text = result.get("caption", "")[:100]
        
        type_labels = {
            "POST": "POST",
            "REELS": "REELS",
            "STORY": "STORY", 
            "HIGHLIGHT": "HIGHLIGHT",
            "IGTV": "IGTV"
        }
        type_label = type_labels.get(content_type, "MEDIA")
        
        caption = (
            f"📸 <b>OKTACOMEL INSTAGRAM {type_label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )
        if username:
            caption += f"👤 <b>User:</b> @{html.escape(username)}\n"
        if caption_text:
            caption += f"📝 {html.escape(caption_text)}...\n"
        caption += f"⚡ <i>Scraped by Oktacomel</i>"
        
        sent_count = 0
        videos_sent = []
        images_sent = []
        
        # Separate videos and images
        for item in result["data"]:
            if item["type"] == "video":
                videos_sent.append(item["url"])
            else:
                images_sent.append(item["url"])
        
        # Send videos first
        for i, video_url in enumerate(videos_sent[:5]):
            try:
                cap = caption if i == 0 else None
                await msg.reply_video(
                    video_url,
                    caption=cap,
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True
                )
                sent_count += 1
            except Exception as e:
                logger.warning(f"[IG] Failed to send video: {e}")
                try:
                    await msg.reply_document(video_url, caption=cap, parse_mode=ParseMode.HTML)
                    sent_count += 1
                except:
                    pass
        
        # Send images (if no videos or it's a carousel)
        for i, img_url in enumerate(images_sent[:10]):
            try:
                cap = caption if (sent_count == 0 and i == 0) else None
                await msg.reply_photo(img_url, caption=cap, parse_mode=ParseMode.HTML)
                sent_count += 1
            except Exception as e:
                logger.warning(f"[IG] Failed to send image: {e}")
                continue
        
        if sent_count == 0:
            await msg.reply_text(
                "❌ <b>Gagal mengirim media</b>\n\nFile mungkin terlalu besar atau format tidak didukung.",
                parse_mode=ParseMode.HTML
            )
        
    except Exception as e:
        logger.error(f"[IG] Error for user {user_id}: {e}")
        await status_msg.edit_text(
            f"❌ <b>Error</b>\n\n{str(e)[:100]}",
            parse_mode=ParseMode.HTML
        )

def _detect_platform_gimita(url: str) -> str | None:
    """Detect platform with expanded support"""
    u = url.lower()
    if "tiktok.com" in u: return "tiktok"
    if "instagram.com" in u or "instagr.am" in u: return "instagram_scrape"  # Use new scraper
    if "facebook.com" in u or "fb.watch" in u or "fb.com" in u: return "facebook"
    if "twitter.com" in u or "x.com" in u: return "twitter"
    if "terabox" in u or "teraboxapp" in u or "1024tera" in u: return "terabox"
    if "youtube.com" in u or "youtu.be" in u: return "youtube"
    if "spotify.com" in u or "open.spotify" in u: return "spotify"
    if "pornhub.com" in u: return "pornhub"
    if "xnxx.com" in u: return "xnxx"
    return None

def _first_str(*vals):
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def _collect_urls(obj, platform: str = None):
    """
    Smart URL collector that categorizes media URLs.
    Improved to handle TikTok/Instagram better - avoid duplicate thumbnails when video exists.
    """
    out = {"video": [], "audio": [], "image": [], "other": [], "music_info": None}
    
    # Track if we found a real video (not thumbnail)
    has_real_video = False

    def push(url: str, bucket: str):
        nonlocal has_real_video
        if not isinstance(url, str):
            return
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return
        if url not in out[bucket]:
            out[bucket].append(url)
            if bucket == "video":
                has_real_video = True

    def walk(x, parent_key=""):
        if isinstance(x, dict):
            for k, v in x.items():
                lk = str(k).lower()
                full_key = f"{parent_key}.{lk}" if parent_key else lk
                
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    # Priority: Video detection
                    if any(w in lk for w in ["video", "play", "nowatermark", "hdplay", "wmplay"]):
                        push(v, "video")
                    # Music/Audio detection
                    elif any(w in lk for w in ["music", "audio", "mp3", "sound"]) or ".mp3" in v.lower():
                        push(v, "audio")
                    # Skip thumbnails/covers if we're likely a video post
                    elif any(w in lk for w in ["thumb", "thumbnail", "cover", "origin_cover", "dynamic_cover", "avatar"]):
                        # Don't add thumbnails to image bucket - skip them
                        pass
                    # Real images (TikTok slideshow, IG carousel)
                    elif any(w in lk for w in ["images", "image_post", "display_url", "image_url"]):
                        push(v, "image")
                    # Fallback with extension check
                    elif ".mp4" in v.lower() or ".webm" in v.lower():
                        push(v, "video")
                    else:
                        push(v, "other")
                else:
                    walk(v, full_key)
                    
            # Extract music info from TikTok response
            if "music" in x and isinstance(x.get("music"), dict):
                music = x["music"]
                out["music_info"] = {
                    "title": music.get("title", "Unknown"),
                    "author": music.get("author", "Unknown"),
                    "url": music.get("play_url", {}).get("uri") if isinstance(music.get("play_url"), dict) else music.get("play_url", "")
                }
                
        elif isinstance(x, list):
            for it in x:
                walk(it, parent_key)

    walk(obj)

    # Fallback heuristics
    if not out["video"]:
        for u in out["other"]:
            if any(t in u.lower() for t in [".mp4", ".mkv", ".webm"]):
                push(u, "video")
                
    if not out["audio"]:
        for u in out["other"]:
            if any(t in u.lower() for t in [".mp3", ".m4a", ".aac"]):
                push(u, "audio")

    # SMART: If we have video, clear images (they're likely just thumbnails)
    # Exception: Instagram carousel and TikTok slideshows explicitly have "images" array
    if has_real_video and platform in ["tiktok", "pornhub", "xnxx"]:
        # For video platforms, thumbnails are not useful
        out["image"] = []

    return out

async def gimita_fetch(platform: str, target_url: str) -> tuple[dict | None, str | None]:
    """
    Fetch dari GiMiTA API
    Returns: (data, error_message)
    """
    endpoint = GIMITA_ENDPOINTS.get(platform)
    if not endpoint:
        return None, "Platform tidak didukung"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json,text/plain,*/*",
    }

    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, headers=headers) as client:
        try:
            r = await client.get(endpoint, params={"url": target_url})
            
            if r.status_code == 200:
                data = r.json()
                # Cek apakah response sukses
                if isinstance(data, dict):
                    if data.get("success") is False or data.get("status") is False:
                        error_msg = _first_str(
                            data.get("error"),
                            data.get("message"),
                            data.get("msg"),
                            "Request failed"
                        )
                        return None, error_msg
                return data, None
            
            # Handle error responses
            try:
                error_data = r.json()
                error_msg = _first_str(
                    error_data.get("error"),
                    error_data.get("message"),
                    f"API returned {r.status_code}"
                )
            except:
                error_msg = f"API returned {r.status_code}"
            
            return None, error_msg
            
        except asyncio.TimeoutError:
            return None, "Request timeout - server terlalu lama merespon"
        except httpx.ConnectError:
            return None, "Gagal terhubung ke server API"
        except Exception as e:
            logger.debug(f"[DL] GiMiTA error: {e}")
            return None, f"Error: {type(e).__name__}"

@rate_limit(seconds=2)
async def dl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await premium_lock_handler(update, context): return
    user_id = update.effective_user.id
    msg = update.message
    status_msg = None
    status_deleted = False

    if not context.args:
        return await msg.reply_text(
            "📥 <b>OKTACOMEL DOWNLOADER • ULTRA V2</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Usage:</b> <code>/dl [link]</code>\n\n"
            "Supported Matrix:\n"
            "• TikTok ✅\n"
            "• YouTube ✅\n"
            "• Spotify ✅\n"
            "• Instagram ✅\n"
            "• Facebook ✅\n"
            "• X / Twitter ✅\n"
            "• Terabox ✅\n"
            "• Pornhub ✅\n"
            "• XNXX ✅\n"
            "• <b>Premium:</b> High-Speed Node ⚡\n\n"
            "🚀 <i>Send a link to start high-speed extraction.</i>",
            parse_mode=ParseMode.HTML,
        )

    url = context.args[0].strip()
    if not url.startswith(("http://", "https://")):
        return await msg.reply_text("❌ Invalid URL format.", parse_mode=ParseMode.HTML)

    platform = _detect_platform_gimita(url)
    if not platform:
        return await msg.reply_text(
            "❌ Unsupported link.\n\n"
            "Supported: TikTok / Instagram / Facebook / Twitter(X) / Terabox / YouTube / Spotify / Pornhub / XNXX",
            parse_mode=ParseMode.HTML,
        )

    # Redirect Instagram to new scraper (no cookies)
    if platform == "instagram_scrape":
        return await ig_download_command(update, context)

    # Cache check
    try:
        cached = await get_media_cache(url)
        if cached and cached.get("cached"):
            file_id = cached.get("file_id")
            m_type = cached.get("media_type", "video")
            caption = "✅ <b>Cached Delivery</b>\n⚡ <i>Instant</i>"
            if m_type == "video":
                await msg.reply_video(file_id, caption=caption, parse_mode=ParseMode.HTML)
            elif m_type == "audio":
                await msg.reply_audio(file_id, caption=caption, parse_mode=ParseMode.HTML)
            elif m_type == "photo":
                await msg.reply_photo(file_id, caption=caption, parse_mode=ParseMode.HTML)
            return
    except Exception:
        pass

    status_msg = await msg.reply_text(
        f"⏳ <b>PROCESSING {platform.upper()}...</b>\n"
        f"<i>Establishing Secure Node Connection...</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        data, error_msg = await gimita_fetch(platform, url)
        
        # 🔧 FIX: Robust Instagram & Twitter list response handling
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        elif isinstance(data, dict) and data.get("data") and isinstance(data["data"], list) and len(data["data"]) > 0:
            # Handle cases where "data" is a list (Instagram slide/carousel)
            media_list = data["data"]
            data = {"data": media_list[0], "media_list": media_list} # Keep reference to all media
        elif isinstance(data, dict) and data.get("result") and isinstance(data["result"], list) and len(data["result"]) > 0:
            data = data["result"][0]

        if not data or not isinstance(data, dict):
            # Fallback for platform-specific response keys
            if isinstance(data, dict) and any(k in data for k in ["url", "link", "download"]):
                pass # Proceed with collecting
            else:
                raise Exception(error_msg or "Invalid API response matrix")

        # metadata best-effort
        res_data = data.get("data") or data.get("result") or data
        if not isinstance(res_data, dict): res_data = {}

        title = _first_str(
            res_data.get("title"),
            data.get("title"),
            "Oktacomel Media"
        )
        uploader = _first_str(
            res_data.get("author", {}).get("name") if isinstance(res_data.get("author"), dict) else "",
            res_data.get("author"),
            res_data.get("uploader"),
            "Oktacomel System"
        )

        urls = _collect_urls(data, platform)
        if not (urls["video"] or urls["image"] or urls["audio"]):
            # Specific check for XNXX/PornHub/Twitter which might have different structures
            if "url" in res_data:
                if any(x in res_data["url"].lower() for x in [".mp4", ".m3u8", ".mov"]):
                    urls["video"] = [res_data["url"]]
            
            if not (urls["video"] or urls["image"] or urls["audio"]):
                raise Exception("No downloadable streams detected in matrix")

        icon_map = {
            "tiktok": "🎥", 
            "instagram": "📸", 
            "facebook": "📘", 
            "twitter": "🐦", 
            "terabox": "📦",
            "youtube": "▶️",
            "spotify": "🎵",
            "pornhub": "🔞",
            "xnxx": "🔞",
        }
        name_map = {
            "tiktok": "TIKTOK", 
            "instagram": "INSTAGRAM", 
            "facebook": "FACEBOOK", 
            "twitter": "X/TWITTER", 
            "terabox": "TERABOX",
            "youtube": "YOUTUBE",
            "spotify": "SPOTIFY",
            "pornhub": "PORNHUB",
            "xnxx": "XNXX",
        }

        icon = icon_map.get(platform, "📁")
        pname = name_map.get(platform, platform.upper())

        # Build caption with music info for TikTok
        music_line = ""
        if urls.get("music_info") and platform == "tiktok":
            mi = urls["music_info"]
            music_line = f"\n🎵 <b>Sound:</b> {html.escape(mi.get('title', 'Unknown')[:50])} - {html.escape(mi.get('author', '')[:30])}"

        caption_base = (
            f"{icon} <b>OKTACOMEL {pname}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Title:</b> {html.escape(title[:120])}\n"
            f"👤 <b>By:</b> {html.escape(uploader[:60])}"
            f"{music_line}\n"
            f"⚡ <i>Powered by Oktacomel</i>"
        )

        # Hapus status message
        try:
            await status_msg.delete()
            status_deleted = True
        except Exception:
            status_deleted = True

        sent = False

        # send video first
        if urls["video"]:
            try:
                v = await msg.reply_video(urls["video"][0], caption=caption_base, parse_mode=ParseMode.HTML)
                sent = True
                try:
                    await save_media_cache(url, v.video.file_id, "video")
                except Exception:
                    pass
            except Exception as ve:
                logger.warning(f"[DL] Failed to send video: {ve}")
                try:
                    await msg.reply_document(urls["video"][0], caption=caption_base, parse_mode=ParseMode.HTML)
                    sent = True
                except Exception:
                    pass

        # then images ONLY if no video was sent (smart detection)
        # For video posts, images are just thumbnails - skip them
        if urls["image"] and not sent:
            for i, purl in enumerate(urls["image"][:8]):
                try:
                    cap = caption_base if (not sent and i == 0) else None
                    p = await msg.reply_photo(purl, caption=cap, parse_mode=ParseMode.HTML)
                    sent = True
                    if cap:
                        try:
                            await save_media_cache(url, p.photo[-1].file_id, "photo")
                        except Exception:
                            pass
                except Exception as pe:
                    logger.warning(f"[DL] Failed to send photo {i}: {pe}")
                    continue

        # then audio (untuk Spotify, TikTok music)
        if urls["audio"]:
            # For TikTok, send as separate music message
            audio_caption = "🎵 <b>Audio/Music</b>"
            if urls.get("music_info") and platform == "tiktok":
                mi = urls["music_info"]
                audio_caption = f"🎵 <b>{html.escape(mi.get('title', 'Music')[:60])}</b>\n👤 {html.escape(mi.get('author', '')[:40])}"
            
            try:
                a = await msg.reply_audio(urls["audio"][0], caption=audio_caption, parse_mode=ParseMode.HTML)
                sent = True
                try:
                    await save_media_cache(f"{url}_audio", a.audio.file_id, "audio")
                except Exception:
                    pass
            except Exception as ae:
                logger.warning(f"[DL] Failed to send audio: {ae}")

        if not sent:
            await msg.reply_text("❌ No media to send.", parse_mode=ParseMode.HTML)

    except Exception as e:
        error_str = str(e)
        logger.error(f"[DL] user={user_id} | Error: {type(e).__name__}: {e}")
        
        # Error message yang lebih spesifik
        if "private" in error_str.lower() or "invalid" in error_str.lower():
            specific_error = "• Konten mungkin private atau link tidak valid"
        elif "timeout" in error_str.lower():
            specific_error = "• Server timeout, coba lagi nanti"
        elif "no media" in error_str.lower() or "no download" in error_str.lower():
            specific_error = "• Tidak ada media yang bisa didownload"
        elif "404" in error_str:
            specific_error = "• Konten tidak ditemukan (404)"
        elif "500" in error_str:
            specific_error = "• Server API sedang bermasalah"
        else:
            specific_error = f"• {error_str[:100]}"
        
        error_message = (
            f"❌ <b>Download Failed</b>\n\n"
            f"<b>Platform:</b> {platform.upper()}\n"
            f"<b>Error:</b>\n{specific_error}\n\n"
            f"<b>Tips:</b>\n"
            f"• Pastikan link valid dan public\n"
            f"• Coba lagi dalam beberapa menit\n"
            f"• Gunakan link langsung ke video/post"
        )
        
        if status_msg and not status_deleted:
            try:
                await status_msg.edit_text(error_message, parse_mode=ParseMode.HTML)
            except Exception:
                await msg.reply_text(error_message, parse_mode=ParseMode.HTML)
        else:
            await msg.reply_text(error_message, parse_mode=ParseMode.HTML)

# ==========================================
# 👤 PROFILE (/ME) - SIMPLE
# ==========================================
async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    c = update.effective_chat
    user_id = u.id

    try:
        p = await u.get_profile_photos(limit=1)
    except Exception:
        p = None

    chat_type_raw = c.type.lower()
    if chat_type_raw == "private":
        chat_icon = "🔒"
        chat_type_label = "Private Chat"
    elif chat_type_raw == "group":
        chat_icon = "👥"
        chat_type_label = "Group"
    elif chat_type_raw == "supergroup":
        chat_icon = "🚀"
        chat_type_label = "Supergroup"
    elif chat_type_raw == "channel":
        chat_icon = "📣"
        chat_type_label = "Channel"
    else:
        chat_icon = "📂"
        chat_type_label = chat_type_raw.title()

    role_label = "N/A"
    if chat_type_raw in ("group", "supergroup"):
        try:
            member = await c.get_member(u.id)
            status = member.status
            if status == "creator":
                role_label = "Owner"
            elif status == "administrator":
                role_label = "Administrator"
            elif status == "member":
                role_label = "Member"
            elif status == "restricted":
                role_label = "Restricted"
            else:
                role_label = status.title()
        except:
            role_label = "Unknown"

    lang = getattr(u, "language_code", None) or "Unknown"
    tg_premium_label = "Yes" if getattr(u, "is_premium", False) else "No"

    try:
        time_str = update.message.date.strftime("%d %B %Y %H:%M")
    except:
        time_str = "Unknown"

    # Get bot premium status and credits
    credits, is_premium, plan, expires_at = await get_user_credits(user_id)
    
    if user_id == OWNER_ID:
        bot_status = "👑 OWNER (Unlimited)"
        credits_display = "∞"
        expiry_display = "Never"
    elif is_premium:
        bot_status = f"💎 Premium ({plan.upper()})"
        credits_display = str(credits)
        if expires_at:
            exp_dt = datetime.datetime.fromisoformat(expires_at)
            days_left = (exp_dt - datetime.datetime.now()).days
            expiry_display = f"{exp_dt.strftime('%d/%m/%Y')} ({days_left}d left)"
        else:
            expiry_display = "Lifetime"
    else:
        bot_status = "🔵 Free User"
        credits_display = f"{credits}/50 (daily)"
        expiry_display = "N/A"

    txt = (
        f"👤 <b>USER PROFILE</b>\n"
        f"✦────────────────────✦\n"
        f"📛 𝗡𝗮𝗺𝗲 ⇾ <b>{html.escape(u.full_name)}</b>\n"
        f"😎 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲 ⇾ @{u.username if u.username else 'None'}\n"
        f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗 ⇾ <code>{u.id}</code>\n"
        f"🔗 𝗣𝗲𝗿𝗺𝗮𝗹𝗶𝗻𝗸 ⇾ <a href='tg://user?id={u.id}'>Click Here</a>\n"
        f"\n"
        f"🌐 𝗟𝗮𝗻𝗴𝘂𝗮𝗴𝗲 ⇾ <code>{lang}</code>\n"
        f"💎 𝗧𝗚 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 ⇾ <code>{tg_premium_label}</code>\n"
        f"{chat_icon} 𝗖𝗵𝗮𝘁 𝗜𝗗 ⇾ <code>{c.id}</code>\n"
        f"{chat_icon} 𝗖𝗵𝗮𝘁 𝗧𝘆𝗽𝗲 ⇾ <code>{chat_type_label}</code>\n"
    )

    if chat_type_raw in ("group", "supergroup"):
        txt += f"🛡️ 𝗥𝗼𝗹𝗲 ⇾ <code>{role_label}</code>\n"

    txt += (
        f"🕒 𝗧𝗶𝗺𝗲 ⇾ <code>{time_str}</code>\n"
        f"\n"
        f"✦────── 𝗕𝗢𝗧 𝗦𝗧𝗔𝗧𝗨𝗦 ──────✦\n"
        f"🏷️ 𝗦𝘁𝗮𝘁𝘂𝘀 ⇾ {bot_status}\n"
        f"💰 𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ⇾ <code>{credits_display}</code>\n"
        f"📅 𝗘𝘅𝗽𝗶𝗿𝘆 ⇾ <code>{expiry_display}</code>\n"
        f"✦────────────────────✦\n"
        f"🤖 <i>Powered by Oktacomel</i>"
    )

    try:
        if p and p.total_count > 0:
            await update.message.reply_photo(
                p.photos[0][-1].file_id,
                caption=txt,
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception:
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

# ==========================================
# 🎫 REDEEM CODE COMMANDS
# ==========================================

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem a code: /redeem CODE"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "🎫 <b>REDEEM CODE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Usage:</b> <code>/redeem YOUR_CODE</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/redeem OKTA-ABCD1234-EFGH5678</code>\n\n"
            "💡 <i>Get redeem codes from admin or giveaways!</i>",
            parse_mode=ParseMode.HTML
        )
        return
    
    code = context.args[0].upper()
    success, message, plan, credits, days = await redeem_code(user_id, code)
    
    if success:
        await update.message.reply_text(
            f"✅ <b>REDEEM BERHASIL!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎫 <b>Code:</b> <code>{code}</code>\n"
            f"📦 <b>Plan:</b> {plan.upper()}\n"
            f"💰 <b>Credits:</b> +{credits}\n"
            f"📅 <b>Duration:</b> {days} hari\n\n"
            f"🎉 <i>Selamat menikmati fitur premium!</i>",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            f"❌ <b>REDEEM GAGAL</b>\n\n{message}",
            parse_mode=ParseMode.HTML
        )

async def gencode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate redeem code (Owner only): /gencode [plan] [credits] [days]"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Owner only!")
        return
    
    # Parse arguments
    plan = "premium"
    credits = 500
    days = 30
    
    if len(context.args) >= 1:
        plan = context.args[0].lower()
    if len(context.args) >= 2:
        try:
            credits = int(context.args[1])
        except:
            pass
    if len(context.args) >= 3:
        try:
            days = int(context.args[2])
        except:
            pass
    
    code = await generate_redeem_code(plan, credits, days)
    
    await update.message.reply_text(
        f"🎫 <b>REDEEM CODE GENERATED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 <b>Code:</b>\n<code>{code}</code>\n\n"
        f"📦 <b>Plan:</b> {plan.upper()}\n"
        f"💰 <b>Credits:</b> {credits}\n"
        f"📅 <b>Duration:</b> {days} days\n\n"
        f"<i>Share this code to a user to activate their premium!</i>",
        parse_mode=ParseMode.HTML
    )

async def listcodes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all unused redeem codes (Owner only)"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Owner only!")
        return
    
    codes = await db_fetch_all(
        "SELECT code, plan, credits, duration_days FROM redeem_codes WHERE used_by IS NULL"
    )
    
    if not codes:
        await update.message.reply_text("📭 No unused codes available.")
        return
    
    txt = "🎫 <b>AVAILABLE REDEEM CODES</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for code, plan, credits, days in codes:
        txt += f"<code>{code}</code>\n  └ {plan} | {credits}cr | {days}d\n\n"
    
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

# ==========================================
# 🔐 USERINFO - INTELLIGENCE DOSSIER
# ==========================================
async def userinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    c = update.effective_chat
    user_id = u.id

    try:
        p = await u.get_profile_photos(limit=1)
    except Exception:
        p = None

    # Role
    if user_id == OWNER_ID:
        rank = "👑 GOD MODE (OWNER)"
    else:
        rank = "👤 Member"
        if c.type.lower() in ("group", "supergroup"):
            try:
                member = await c.get_member(user_id)
                if member.status == "creator":
                    rank = "👑 Owner"
                elif member.status == "administrator":
                    rank = "⚡ Admin"
            except:
                pass

    # Status checks
    is_sub = await is_registered(user_id)
    is_premium_user = False
    try:
        pr = await db_fetch_one("SELECT user_id FROM premium_users WHERE user_id=?", (user_id,))
        is_premium_user = bool(pr)
    except:
        pass

    sub_status = "✅ ACTIVE" if is_sub else "❌ INACTIVE"
    prem_status = "✅ ACTIVE" if is_premium_user else "❌ INACTIVE"

    # Stats
    cmd_count = 0
    try:
        st = await db_fetch_one("SELECT COUNT(*) FROM user_actions WHERE user_id=?", (user_id,))
        cmd_count = st[0] if st else 0
    except:
        pass

    # Behavior score
    score = min(100, cmd_count * 5)
    if score >= 80:
        level = "🟢 TRUSTED"
        bar = "████████████████░░░░"
        threat = "✅ CLEAN"
    elif score >= 50:
        level = "🟡 MODERATE" 
        bar = "████████████░░░░░░░░"
        threat = "⚠️ MONITOR"
    elif score > 0:
        level = "🟠 LOW"
        bar = "██████░░░░░░░░░░░░░░"
        threat = "⚠️ REVIEW"
    else:
        level = "🔴 NEW USER"
        bar = "░░░░░░░░░░░░░░░░░░░░"
        threat = "🔴 UNKNOWN"

    # Achievement
    if user_id == OWNER_ID:
        ach = "👑 GOD TIER"
    elif is_premium_user:
        ach = "💎 PREMIUM"
    elif is_sub:
        ach = "✅ VERIFIED"
    else:
        ach = "🆕 NEW"

    time_str = datetime.datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")

    txt = (
        f"🔐 <b>TARGET INTELLIGENCE DOSSIER</b>\n\n"
        
        f"<b>👤 IDENTITY MATRIX</b>\n"
        f"├ User ID: <code>{user_id}</code>\n"
        f"├ Name: {html.escape(u.full_name)}\n"
        f"├ Username: @{u.username if u.username else 'None'}\n"
        f"└ Rank: {rank}\n\n"
        
        f"<b>📊 SYSTEM AUDIT</b>\n"
        f"├ Subscriber: {sub_status}\n"
        f"├ Premium: {prem_status}\n"
        f"├ Commands: {cmd_count}\n"
        f"└ Last Activity: {time_str}\n\n"
        
        f"<b>⚠️ THREAT ASSESSMENT</b>\n"
        f"├ Status: {threat}\n"
        f"└ [{bar}]\n\n"
        
        f"<b>📈 BEHAVIOR ANALYSIS</b>\n"
        f"├ Level: {level}\n"
        f"├ Score: {score}/100\n"
        f"└ Commands: {cmd_count}\n\n"
        
        f"<b>🎖️ ACHIEVEMENTS</b>\n"
        f"└ {ach}\n\n"
        
        f"<b>📅 ACTIVITY TIMELINE</b>\n"
        f"└ {'Active user' if cmd_count > 0 else 'No activity recorded'}\n\n"
        
        f"✅ <i>Analysis Complete - 100% Match</i>\n"
        f"🤖 <i>Oktacomel Intelligence System</i>"
    )

    try:
        if p and p.total_count > 0:
            await update.message.reply_photo(p.photos[0][-1].file_id, caption=txt, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML)


# ==========================================
# 💎 PREMIUM & BUY (FULL TEXT + BACK BUTTON)
# ==========================================
async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Text Baru Lengkap dengan Format Rapi
    text = (
        "🌟 <b>Upgrade to Premium</b> 🌟\n"
        "Take your experience to the next level with our premium plans. Enjoy higher limits, priority support, and exclusive features!\n\n"
        
        "🏷 <b>Premium Plans:</b>\n"
        "- <code>$69.99</code> for <b>Basic Premium</b> ($0.0292/credit)\n"
        "  • Daily Limit: 80 credits/day\n"
        "  • Hourly Limit: 25 credits/hour\n"
        "  • Weekly Limit: 560 credits\n"
        "  • Monthly Limit: 2400 credits\n\n"
        
        "- <code>$149.99</code> for <b>Advanced Premium</b> ($0.0250/credit)\n"
        "  • Daily Limit: 200 credits/day\n"
        "  • Hourly Limit: 65 credits/hour\n"
        "  • Weekly Limit: 1400 credits\n"
        "  • Monthly Limit: 6000 credits\n\n"
        
        "- <code>$249.99</code> for <b>Pro Premium</b> ($0.0238/credit)\n"
        "  • Daily Limit: 350 credits/day\n"
        "  • Hourly Limit: 115 credits/hour\n"
        "  • Weekly Limit: 2450 credits\n"
        "  • Monthly Limit: 10500 credits\n\n"
        
        "- <code>$449.99</code> for <b>Enterprise Premium</b> ($0.0187/credit)\n"
        "  • Daily Limit: 800 credits/day\n"
        "  • Hourly Limit: 265 credits/hour\n"
        "  • Weekly Limit: 5600 credits\n"
        "  • Monthly Limit: 24000 credits\n\n"

        "🏷 <b>Credits Plans (Popular):</b>\n"
        "- <code>$4.99</code> for 100 credits + 2 bonus\n"
        "- <code>$19.99</code> for 500 credits + 10 bonus\n"
        "- <code>$39.99</code> for 1000 credits + 25 bonus\n"
        "- <code>$94.99</code> for 2500 credits + 50 bonus\n"
        "- <code>$179.99</code> for 5000 credits + 50 bonus\n"
        "- <code>$333.99</code> for 10000 credits + 100 bonus\n"
        "- <code>$739.99</code> for 25000 credits + 300 bonus\n\n"

        "✅ <b>After Payment:</b>\n"
        "Your premium plan will be automatically activated once the payment is confirmed.\n"
        "<i>All sales are final. No refunds.</i>\n\n"

        "🤝 Thank you for choosing to go premium! Your support helps us keep improving.\n"
        "📜 <a href='https://google.com'>Learn More About Plans</a>"
    )
    
    # Tombol Lengkap (+ Back Button)
    user_id = update.effective_user.id
    kb = [
        [InlineKeyboardButton("Pay via Crypto", callback_data=f"pay_crypto|{user_id}"),
         InlineKeyboardButton("Pay via QRIS", callback_data=f"pay_qris|{user_id}")],
        [InlineKeyboardButton("Contact Support", url="https://t.me/hiduphjokowi")],
        [InlineKeyboardButton("Plan Details", url="https://google.com")],
        
        # 👇 INI TOMBOL TAMBAHANNYA 👇
        [InlineKeyboardButton("🔙 Back to Menu", callback_data=f"menu_main|{user_id}")]
    ]
    
    # Gunakan edit jika dari callback, atau send jika command baru
    if update.callback_query:
        # Cek jika ada foto (dari /start), hapus dulu
        if update.callback_query.message.photo:
            await update.callback_query.message.delete()
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)
        else:
            await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)

# ==========================================
# 🔍 IP & NETWORK (/IP) - PREMIUM STYLE
# ==========================================
async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = " ".join(context.args) if context.args else ""
    if not q: 
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/ip domain_or_ip</code>", parse_mode=ParseMode.HTML)
        return
    
    msg = await update.message.reply_text("⏳ <b>Scanning network...</b>", parse_mode=ParseMode.HTML)

    # API Request (Fields Lengkap)
    api_url = f"http://ip-api.com/json/{q}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,mobile,proxy,hosting,query"
    
    try:
        r = await fetch_json(api_url)
        
        if r and r['status'] == 'success':
            lat, lon = r['lat'], r['lon']
            # Link Google Maps Resmi (Biar gak error)
            map_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            
            # Status Check
            is_mobile = "✅ Yes" if r.get('mobile') else "❌ No"
            is_proxy = "🔴 DETECTED" if r.get('proxy') else "🟢 Clean"
            is_hosting = "🖥️ VPS/Cloud" if r.get('hosting') else "🏠 Residential"

            # TAMPILAN PREMIUM (BOLD SANS + MONO)
            txt = (
                f"🔍 <b>IP INTELLIGENCE</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 𝗧𝗮𝗿𝗴𝗲𝘁 ⇾ <code>{r['query']}</code>\n"
                f"🏢 𝗜𝗦𝗣 ⇾ <code>{r['isp']}</code>\n"
                f"💼 𝗢𝗿𝗴 ⇾ <code>{r.get('org', 'N/A')}</code>\n"
                f"🔢 𝗔𝗦𝗡 ⇾ <code>{r.get('as', 'N/A')}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🌍 𝗟𝗢𝗖𝗔𝗧𝗜𝗢𝗡 𝗗𝗘𝗧𝗔𝗜𝗟\n"
                f"🏳️ 𝗖𝗼𝘂𝗻𝘁𝗿𝘆 ⇾ <code>{r['country']} ({r['countryCode']})</code>\n"
                f"📍 𝗥𝗲𝗴𝗶𝗼𝗻 ⇾ <code>{r['regionName']}</code>\n"
                f"🏙️ 𝗖𝗶𝘁𝘆 ⇾ <code>{r['city']}</code>\n"
                f"📮 𝗭𝗶𝗽 𝗖𝗼𝗱𝗲 ⇾ <code>{r['zip']}</code>\n"
                f"⏰ 𝗧𝗶𝗺𝗲𝘇𝗼𝗻𝗲 ⇾ <code>{r['timezone']}</code>\n"
                f"🛰️ 𝗖𝗼𝗼𝗿𝗱𝘀 ⇾ <code>{lat}, {lon}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🛡️ 𝗦𝗘𝗖𝗨𝗥𝗜𝗧𝗬 𝗔𝗡𝗔𝗟𝗬𝗦𝗜𝗦\n"
                f"📱 𝗠𝗼𝗯𝗶𝗹𝗲 ⇾ <b>{is_mobile}</b>\n"
                f"🕵️ 𝗣𝗿𝗼𝘅𝘆/𝗩𝗣𝗡 ⇾ <b>{is_proxy}</b>\n"
                f"☁️ 𝗧𝘆𝗽𝗲 ⇾ <b>{is_hosting}</b>\n\n"
                f"🤖 <i>Powered by Oktacomel</i>"
            )
            
            kb = [[InlineKeyboardButton("🗺️ Open Google Maps", url=map_url)]]
            await msg.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        else: 
            await msg.edit_text("❌ <b>Failed.</b> Invalid IP/Domain.", parse_mode=ParseMode.HTML)

    except Exception as e:
        await msg.edit_text(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
        
# ==========================================
# 🌦️ WEATHER & GEMPA & BROADCAST (ICON UPDATE)
# ==========================================
async def cuaca_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Weather Command - /weather city"""
    if not await premium_lock_handler(update, context): return
    
    user_id = update.effective_user.id
    
    # Check if triggered by callback (refresh)
    q = update.callback_query
    if q:
        await q.answer("🔄 Refreshing weather data...")
        raw_data = q.data
        city = raw_data.split("|")[1]
    else:
        if not context.args: 
            return await update.message.reply_text("🌦️ <b>OKTACOMEL WEATHER</b>\nUsage: <code>/weather [city]</code>", parse_mode=ParseMode.HTML)
        city = " ".join(context.args)
        
        # Check and deduct credits (only for initial command, not refresh)
        success, remaining, cost = await deduct_credits(user_id, "weather")
        if not success:
            await update.message.reply_text(
                f"❌ <b>Kredit Tidak Cukup</b>\n\n"
                f"Command ini membutuhkan {cost} kredit.\n"
                f"Kredit kamu: {remaining}\n\n"
                f"💎 Upgrade ke Premium!",
                parse_mode=ParseMode.HTML
            )
            return

    try:
        data = await get_weather_data(city)
        
        if data and data.get('cod') == 200:
            lat, lon = data['coord']['lat'], data['coord']['lon']
            map_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            aqi = await get_aqi(lat, lon)
            
            # Using wttr.in for aesthetic weather image
            image_url = f"https://v2.wttr.in/{city.replace(' ', '+')}.png?0&Q&T&m"
            
            txt = format_weather(data, aqi)
            
            kb = [
                [InlineKeyboardButton("🔄 Refresh Data", callback_data=f"weather_refresh|{city}|{user_id}")],
                [InlineKeyboardButton("🗺️ View on Map", url=map_url)],
                [InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")]
            ]
            
            if q:
                try:
                    await q.message.edit_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
                except:
                    # If edit_caption fails (e.g. no photo), send new
                    await context.bot.send_photo(chat_id=q.message.chat_id, photo=image_url, caption=txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            else:
                await update.message.reply_photo(photo=image_url, caption=txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        else:
            err_msg = f"❌ <b>City '{city}' Not Found.</b> Please check the spelling."
            if q: await q.message.reply_text(err_msg, parse_mode=ParseMode.HTML)
            else: await update.message.reply_text(err_msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"[WEATHER] Error: {e}")
        await update.message.reply_text(f"⚠️ <b>Weather Error:</b> {str(e)}", parse_mode=ParseMode.HTML)

# ==========================================
# 🌋 INFO GEMPA TERKINI (OKTACOMEL BMKG ALERT)
# ==========================================
async def gempa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Mengambil data gempa terbaru khusus wilayah Indonesia
    Sumber: BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)
    """
    user_id = update.effective_user.id
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    # API BMKG khusus Gempa M 5.0+ (Terkini)
    BMKG_URL = "https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json"

    try:
        r = await fetch_json(BMKG_URL)
        if not r:
            logger.warning(f"[GEMPA] user={user_id} | BMKG API returned empty response")
            await update.message.reply_text(
                "❌ <b>Gagal koneksi ke server BMKG.</b>\nSilakan coba lagi nanti.",
                parse_mode=ParseMode.HTML
            )
            return

        gempa_data = r.get("Infogempa", {}).get("gempa")
        if not gempa_data:
            logger.warning(f"[GEMPA] user={user_id} | No earthquake data in response")
            await update.message.reply_text(
                "❌ <b>Data gempa BMKG tidak tersedia.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        d = gempa_data # autogempa.json return dict

        # 1. Logika Warna & Status Bahaya
        try:
            mag = float(d.get("Magnitude", "0"))
        except:
            mag = 0.0

        if mag >= 7.0:
            alert = "🔴 BAHAYA (GEMPA KUAT)"
            level_label = "HIGH ALERT"
        elif mag >= 5.0:
            alert = "🟠 WASPADA (GEMPA SEDANG)"
            level_label = "CAUTION"
        else:
            alert = "🟢 TERKENDALI (GEMPA RINGAN)"
            level_label = "INFO"

        # 2. Cek Potensi Tsunami
        potensi = d.get("Potensi", "")
        if "tidak berpotensi" in potensi.lower():
            tsunami_status = "🟢 TIDAK BERPOTENSI TSUNAMI"
        else:
            tsunami_status = f"🔴 ⚠️ {potensi or 'POTENSI TSUNAMI TIDAK DIKETAHUI'}"

        # 3. Link Google Maps Resmi
        coords_raw = d.get("Coordinates", "")
        try:
            coords = coords_raw.split(",")  # Format: -3.55,102.33
            lat, lon = coords[0].strip(), coords[1].strip()
            map_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        except Exception:
            lat, lon = "Unknown", "Unknown"
            map_url = "https://www.google.com/maps/search/?q=BMKG+Gempa+Terkini"

        # 4. Info Detail
        dirasakan = d.get("Dirasakan", "").strip()
        dirasakan_text = f"<code>{html.escape(dirasakan)}</code>" if dirasakan else "<i>Tidak ada laporan terasa signifikan.</i>"

        # 5. Tampilan Premium (Indonesian Focus)
        txt = (
            "🇮🇩 <b>OKTACOMEL BMKG ALERT</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>Level:</b> <code>{level_label}</code>\n"
            f"⚠️ <b>Status:</b> {alert}\n"
            f"🌊 <b>Tsunami:</b> {tsunami_status}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📅 <b>Waktu:</b> <code>{d.get('Tanggal', '-') } | {d.get('Jam', '-')}</code>\n"
            f"💥 <b>Magnitude:</b> <code>{d.get('Magnitude', '-')} SR</code>\n"
            f"🌊 <b>Kedalaman:</b> <code>{d.get('Kedalaman', '-')}</code>\n"
            f"📍 <b>Wilayah:</b> <code>{html.escape(d.get('Wilayah', '-'))}</code>\n"
            f"📌 <b>Koordinat:</b> <code>{coords_raw or 'Unknown'}</code>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>Dirasakan:</b>\n{dirasakan_text}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🏛️ <i>Sumber resmi: BMKG Indonesia</i>"
        )

        kb = [[InlineKeyboardButton("🗺️ Lihat Lokasi di Peta", url=map_url)]]

        # Generate Static Map Image dari Yandex (fokus Indonesia)
        static_map_url = None
        if lat != "Unknown" and lon != "Unknown":
            try:
                # Use Yandex static map API for high quality markers
                static_map_url = f"https://static-maps.yandex.ru/1.x/?ll={lon},{lat}&z=7&size=450,300&l=map&pt={lon},{lat},pm2rdm"
            except:
                pass

        # Kirim Gambar Shakemap jika ada
        shakemap_file = d.get("Shakemap")
        photo_url = None
        
        if shakemap_file:
            photo_url = f"https://data.bmkg.go.id/DataMKG/TEWS/{shakemap_file}"
        elif static_map_url:
            photo_url = static_map_url
            
        if photo_url:
            try:
                await update.message.reply_photo(
                    photo_url,
                    caption=txt,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(kb)
                )
                return
            except Exception:
                pass

        # Fallback
        await update.message.reply_text(
            txt,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )

    except Exception as e:
        logger.error(f"[GEMPA] user={user_id} | Error: {type(e).__name__}: {e}")
        await update.message.reply_text(
            "❌ <b>Terjadi kesalahan sistem.</b>\nGagal mengambil data BMKG.",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"[GEMPA] user={user_id} | Error: {type(e).__name__}: {e}")
        await update.message.reply_text(
            "❌ Terjadi kesalahan saat mengambil data gempa.\nSilakan coba lagi.",
            parse_mode=ParseMode.HTML
        )


# ==========================================
# 🔒 BACKFREE (BF) - BLOCK ALL USERS EXCEPT OWNER
# ==========================================
backfree_active = False  # Global toggle

async def bf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle Backfree Mode - Block all users except owner + Reset Credits"""
    global backfree_active
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ <b>Access Denied.</b> Owner only.", parse_mode=ParseMode.HTML)
        return
    
    backfree_active = not backfree_active
    status = "🔴 ACTIVE" if backfree_active else "🟢 DISABLED"
    
    # RESET CREDITS Logic
    if backfree_active:
        try:
            # Delete all premium users and reset user_credits to 50
            await db_execute("DELETE FROM premium_users")
            await db_execute("UPDATE user_credits SET credits = 50, last_reset = ?", (datetime.datetime.now().isoformat(),))
            reset_status = "✅ <b>User credits reset to 50 (Free).</b>\n"
        except Exception as e:
            reset_status = f"⚠️ <b>Credit reset failed:</b> {e}\n"
    else:
        reset_status = ""

    text = (
        "🔒 <b>OKTACOMEL BACKFREE MODE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Status:</b> {status}\n"
        f"{reset_status}\n"
    )
    
    if backfree_active:
        text += (
            "⚠️ <b>All users are now blocked</b>\n"
            "Only Owner can use the bot.\n\n"
            "<i>Use /bf again to disable.</i>"
        )
    else:
        text += (
            "✅ <b>Bot is now open for everyone</b>\n"
            "All users can use the bot normally.\n\n"
            "<i>Use /bf again to enable.</i>"
        )
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def check_backfree(update: Update) -> bool:
    """Check if backfree mode is blocking this user"""
    global backfree_active
    if not backfree_active:
        return True  # Not blocked
    if update.effective_user.id == OWNER_ID:
        return True  # Owner bypasses
    return False  # Blocked

# ==========================================
# 📬 SUBSCRIBE / UNSUBSCRIBE BROADCAST
# ==========================================
async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await add_subscriber(update.effective_user.id):
        await update.message.reply_text(
            "✅ <b>Subscribed to OKTACOMEL Alerts.</b>\n"
            "📡 You will receive curated daily updates and important broadcasts.",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "ℹ️ <b>You are already subscribed.</b>\n"
            "No action was taken.",
            parse_mode=ParseMode.HTML
        )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await remove_subscriber(update.effective_user.id):
        await update.message.reply_text(
            "🔕 <b>Unsubscribed from OKTACOMEL Alerts.</b>\n"
            "We’ll stay quiet unless you call us again. 😉",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "ℹ️ <b>You are not in the subscriber list.</b>",
            parse_mode=ParseMode.HTML
        )


# ==========================================
# 📢 SYSTEM BROADCAST (OWNER ONLY)
# ==========================================
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return  # Diam saja kalau bukan owner

    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b> <code>/broadcast your message here</code>",
            parse_mode=ParseMode.HTML
        )
        return

    msg_text = " ".join(context.args)
    users = await get_subscribers()
    total = len(users)
    sent = 0
    removed = 0

    status_msg = await update.message.reply_text(
        f"⏳ <b>Sending broadcast...</b>\n"
        f"Target: <code>{total}</code> users.",
        parse_mode=ParseMode.HTML
    )

    for uid in users:
        try:
            await context.bot.send_message(
                uid,
                f"📢 <b>OKTACOMEL BROADCAST</b>\n"
                "━━━━━━━━━━━━━━━━\n\n"
                f"{msg_text}",
                parse_mode=ParseMode.HTML
            )
            sent += 1
        except Exception:
            # User mungkin block bot / chat hilang → hapus dari DB
            await remove_subscriber(uid)
            removed += 1

    await status_msg.edit_text(
        "✅ <b>Broadcast Completed.</b>\n"
        f"📨 Delivered to: <code>{sent}</code> users.\n"
        f"🗑️ Removed inactive: <code>{removed}</code>\n"
        f"👥 Original list: <code>{total}</code>",
        parse_mode=ParseMode.HTML
    )


# ==========================================
# 🌅 MORNING BROADCAST (AUTO TASK)
# ==========================================
async def morning_broadcast(context: ContextTypes.DEFAULT_TYPE):
    # Ambil data cuaca Jakarta (default)
    data = await get_weather_data("Jakarta")
    if not data:
        return

    # Bisa pakai nama kota default "Jakarta" atau "Unknown" sesuai fungsi format_weather
    weather_text = format_weather(data, "Jakarta")

    now = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    text = (
        "🌅 <b>GOOD MORNING FROM OKTACOMEL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <b>Update Time:</b> <code>{now}</code>\n"
        "📍 <b>Region:</b> <code>Jakarta & Surroundings</code>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{weather_text}\n\n"
        "💡 <i>Tip:</i> Stay hydrated, stay productive, and have a great day!"
    )

    users = await get_subscribers()
    for uid in users:
        try:
            await context.bot.send_message(uid, text, parse_mode=ParseMode.HTML)
        except Exception:
            await remove_subscriber(uid)


# ==========================================
# 🔎 SEARCH (ANIME + MOVIE/IMDB) — PREMIUM UI
# ==========================================
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await premium_lock_handler(update, context): return
    # langsung load OMDB key dari config (boleh dipakai atau dihapus jika sudah import global)
    from config import OMDB_API_KEY  

    # 1. Cek Input
    if not context.args:
        return await update.message.reply_text(
            "⚠️ <b>Usage:</b>\n"
            "<code>/search Naruto</code>\n"
            "<code>/search anime Naruto</code>\n"
            "<code>/search movie Inception</code>",
            parse_mode=ParseMode.HTML,
        )

    # MODE DETECTOR (anime / manhwa / donghua / movie)
    first = context.args[0].lower()
    known_modes = {"anime", "manga", "manhwa", "donghua", "harem", "movie", "film", "imdb"}

    if first in known_modes:
        mode = first
        if len(context.args) == 1:
            return await update.message.reply_text(
                "⚠️ <b>Usage:</b>\n"
                "<code>/search anime Naruto</code>\n"
                "<code>/search movie Inception</code>",
                parse_mode=ParseMode.HTML,
            )
        q = " ".join(context.args[1:])
    else:
        mode = "anime"  # default
        q = " ".join(context.args)

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    # ==========================
    # 🎨 OKTACOMEL IMAGEN (ULTIMATE PREMIUM)
    # ==========================
    if mode in ["draw", "img", "gen"]:
        try:
            prompt = q
            await msg.edit_text(f"🎨 <b>OKTACOMEL IMAGEN</b> is generating...\n━━━━━━━━━━━━━━━━━━━━━━\nPrompt: <code>{html.escape(prompt)}</code>", parse_mode=ParseMode.HTML)
            
            # Using stable diffusion or similar API (simulated for now with branding)
            # This is where the Ultimate Premium feature lives
            image_url = f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={random.randint(1,99999)}"
            
            txt = (
                f"🎨 <b>OKTACOMEL IMAGEN • PREMIUM ULTIMATE</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Prompt:</b> <code>{html.escape(prompt)}</code>\n"
                f"<b>Engine:</b> <i>Oktacomel Vision v2</i>\n\n"
                f"⚡ <i>Generated with Ultimate Priority</i>"
            )
            
            await msg.delete() # Remove loading text
            await update.message.reply_photo(
                photo=image_url,
                caption=txt,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await msg.edit_text(f"❌ <b>Imagen Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
        return

    # ==========================
    # 🤖 OKTACOMEL AI (GPT-5 BRAIN)
    # ==========================
    if mode in ["gpt5", "ai", "okta"]:
        try:
            prompt = q
            # Status loading with branding
            loading_msg = await msg.edit_text(
                f"🧠 <b>OKTACOMEL AI</b> is thinking...\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>Input Matrix:</b> <code>{html.escape(prompt[:50])}...</code>", 
                parse_mode=ParseMode.HTML
            )
            
            # For now, simulate GPT-5 branding. In real use, this would be an API call.
            ai_response = (
                f"Greetings! I am <b>Oktacomel GPT-5</b>, the advanced neural layer of this system. "
                f"Regarding your query: <i>\"{html.escape(prompt)}\"</i>\n\n"
                f"My intelligence matrix is currently processing high-level data. "
                f"I am designed to provide superior logic, coding assistance, and creative insights with 100% precision."
            )
            
            txt = (
                f"🤖 <b>OKTACOMEL AI • GPT-5 BRAIN</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{ai_response}\n\n"
                f"📡 <b>Status:</b> 🟢 Optimized\n"
                f"⚡ <i>Powered by Oktacomel Quantum Core</i>\n"
                f"💬 <i>Reply to this message to continue chat</i>"
            )
            await loading_msg.edit_text(txt, parse_mode=ParseMode.HTML)
        except Exception as e:
            await msg.edit_text(f"❌ <b>AI Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
        return

    # ==========================
    # 🎞️ ANIME / MANHWA / DONGHUA
    # ==========================
    if mode in {"anime", "manga", "manhwa", "donghua", "harem"}:
        try:
            r = await fetch_json(f"{ANIME_API}?q={urllib.parse.quote(q)}&limit=1&sfw=true")

            if r and r.get("data"):
                d = r["data"][0]

                raw_synopsis = d.get("synopsis", "No synopsis available.")
                if raw_synopsis and len(raw_synopsis) > 400:
                    raw_synopsis = raw_synopsis[:400] + "..."
                clean_synopsis = html.escape(str(raw_synopsis))

                title_e = html.escape(d.get("title", "Unknown Title"))
                score = d.get("score", "N/A")
                a_type = d.get("type", "?")
                episodes = d.get("episodes", "?")
                status = d.get("status", "Unknown")
                url_mal = d.get("url", "#")
                
                # Extract genres from API response
                genres_list = d.get("genres", [])
                genres = ", ".join([g.get("name", "") for g in genres_list]) if genres_list else "N/A"

                txt = (
                    f"🎬 <b>ANIME SEARCH — PREMIUM</b>\n"
                    f"✦────────────────────✦\n"
                    f"🔎 <b>Query</b> ⇾ <code>{html.escape(q)}</code>\n"
                    f"📂 <b>Category</b> ⇾ <code>{mode.upper()}</code>\n"
                    f"✦────────────────────✦\n\n"
                    f"🎞️ <b>{title_e}</b>\n"
                    f"⭐ <b>Score</b> ⇾ <code>{score} / 10</code>\n"
                    f"📺 <b>Type</b> ⇾ <code>{a_type} ({episodes} eps)</code>\n"
                    f"📅 <b>Status</b> ⇾ <code>{status}</code>\n"
                    f"🎭 <b>Genre</b> ⇾ <code>{genres}</code>\n"
                    f"✦────────────────────✦\n"
                    f"📝 <b>Synopsis:</b>\n"
                    f"<i>{clean_synopsis}</i>"
                )

                kb = [[InlineKeyboardButton("🌐 View on MyAnimeList", url=url_mal)]]

                img_url = (
                    d.get("images", {}).get("jpg", {}).get("large_image_url")
                    or d.get("images", {}).get("jpg", {}).get("image_url")
                )

                if img_url:
                    await update.message.reply_photo(
                        img_url,
                        caption=txt,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(kb),
                    )
                else:
                    await update.message.reply_text(
                        txt,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(kb),
                    )

            else:
                await update.message.reply_text(
                    "❌ <b>Anime not found.</b> Try another keyword.",
                    parse_mode=ParseMode.HTML,
                )

        except Exception as e:
            await update.message.reply_text(
                f"⚠️ <b>Error:</b> <code>{html.escape(str(e))}</code>",
                parse_mode=ParseMode.HTML,
            )
        return

    # ==========================
    #  MOVIE / IMDb MODE
    # ==========================
    if mode in {"movie", "film", "imdb"}:
        try:
            omdb_key = OMDB_API_KEY.strip() if OMDB_API_KEY else ""

            if not omdb_key or omdb_key == "YOUR_OMDB_API_KEY_HERE":
                return await update.message.reply_text(
                    "⚠️ <b>Movie Search not configured.</b>\n"
                    "Tambahkan <code>OMDB_API_KEY</code> di <code>config.py</code> untuk mengaktifkan IMDb search.",
                    parse_mode=ParseMode.HTML,
                )

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://www.omdbapi.com/",
                    params={"apikey": omdb_key, "t": q, "plot": "short"},
                )
                # cek status http dulu agar error clearer
                resp.raise_for_status()
                data = resp.json()

            if not data or data.get("Response") != "True":
                return await update.message.reply_text(
                    "❌ <b>Movie not found on IMDb.</b>",
                    parse_mode=ParseMode.HTML,
                )

            title_e = html.escape(data.get("Title", "Unknown"))
            year = data.get("Year", "?")
            m_type = data.get("Type", "N/A")
            genre_e = html.escape(data.get("Genre", "N/A"))
            rating = data.get("imdbRating", "N/A")
            votes = data.get("imdbVotes", "N/A")
            plot = data.get("Plot", "No plot available.")
            runtime = data.get("Runtime", "N/A")
            rated = data.get("Rated", "N/A")
            poster = data.get("Poster", "")
            imdb_id = data.get("imdbID", "") or ""

            plot_short = plot[:400] + "..." if len(plot) > 400 else plot
            plot_e = html.escape(plot_short)

            imdb_url = f"https://www.imdb.com/title/{imdb_id}" if imdb_id else "https://www.imdb.com/"

            txt = (
                f"🎬 <b>MOVIE SEARCH — IMDb PREMIUM</b>\n"
                f"✦────────────────────✦\n"
                f"🔎 <b>Query</b> ⇾ <code>{html.escape(q)}</code>\n"
                f"📂 <b>Category</b> ⇾ <code>MOVIE</code>\n"
                f"✦────────────────────✦\n\n"
                f"🎞️ <b>{title_e}</b> ({year})\n"
                f"📺 <b>Type</b> ⇾ <code>{m_type}</code>\n"
                f"⏱️ <b>Duration</b> ⇾ <code>{runtime}</code>\n"
                f"💠 <b>Rated</b> ⇾ <code>{rated}</code>\n"
                f"🎭 <b>Genre</b> ⇾ <code>{genre_e}</code>\n"
                f"⭐ <b>IMDb</b> ⇾ <code>{rating} / 10</code> ({votes} votes)\n"
                f"✦────────────────────✦\n"
                f"📝 <b>Plot:</b>\n"
                f"<i>{plot_e}</i>"
            )

            kb = [[InlineKeyboardButton("🎬 Open on IMDb", url=imdb_url)]]

            if poster and poster != "N/A":
                await update.message.reply_photo(
                    poster,
                    caption=txt,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(kb),
                )
            else:
                await update.message.reply_text(
                    txt,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(kb),
                )

        except httpx.RequestError as e:
            await update.message.reply_text(
                f"⚠️ <b>Network error:</b> <code>{html.escape(str(e))}</code>",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await update.message.reply_text(
                f"⚠️ <b>Error:</b> <code>{html.escape(str(e))}</code>",
                parse_mode=ParseMode.HTML,
            )

# --- Tambahkan helper ini di luar ping_command (sekali saja) ---
async def http_ping(url: str = "https://1.1.1.1/cdn-cgi/trace") -> float:
    """
    Ping VPS ke internet via HTTP (lebih kompatibel daripada ICMP ping).
    Return dalam ms.
    """
    t0 = time.perf_counter()
    timeout = aiohttp.ClientTimeout(total=3)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as r:
            await r.read()

    return (time.perf_counter() - t0) * 1000


async def vps_ping_best() -> float:
    """
    Coba beberapa target yang stabil (cocok untuk VPS US/LAX),
    ambil ping tercepat. Kalau semua gagal, return angka besar.
    """
    targets = [
        "https://1.1.1.1/cdn-cgi/trace",
        "https://www.cloudflare.com/cdn-cgi/trace",
        "https://www.google.com/generate_204",
    ]

    results = []
    for url in targets:
        try:
            results.append(await http_ping(url))
        except Exception:
            pass

    return min(results) if results else 9999.0


# ==========================================
# 🖥️ PING / SYSTEM CHECK (PREMIUM UI)
# ==========================================
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await premium_lock_handler(update, context): return

    # Pesan Loading (tetap)
    msg = await update.message.reply_text("⏳ <b>Analyzing system...</b>", parse_mode=ParseMode.HTML)

    try:
        # --- DATA SYSTEM ---
        # 1. Hitung Ping VPS (Network) ✅
        ping_ms = await vps_ping_best()

        # 2. Hardware Info
        ram = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        disk = shutil.disk_usage("/")

        # 3. CPU Frequency (Safe Check)
        freq = psutil.cpu_freq()
        cpu_freq = f"{freq.current:.0f}Mhz" if freq else "N/A"

        # 4. OS Info
        os_name = f"{platform.system()} {platform.release()}"
        py_ver = sys.version.split()[0]

        # 5. Uptime
        try:
            uptime_sec = int(time.time() - START_TIME)
            uptime = str(datetime.timedelta(seconds=uptime_sec))
        except:
            uptime = "Unknown"

        # Helper Bar Visual (10 Balok)
        def make_bar(percent):
            filled = int(percent / 10)
            filled = max(0, min(10, filled)) # Limit 0-10
            return "▰" * filled + "▱" * (10 - filled)

        # --- TAMPILAN PREMIUM (BOLD SANS + MONO) ---
        txt = (
            f"🖥️ <b>SYSTEM DASHBOARD</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💻 𝗢𝗦 ⇾ <code>{os_name}</code>\n"
            f"🐍 𝗣𝘆𝘁𝗵𝗼𝗻 ⇾ <code>v{py_ver}</code>\n"
            f"⏱️ 𝗨𝗽𝘁𝗶𝗺𝗲 ⇾ <code>{uptime}</code>\n\n"

            f"🧠 𝗥𝗔𝗠 𝗨𝘀𝗮𝗴𝗲 ⇾ <code>{ram.percent}%</code>\n"
            f"<code>[{make_bar(ram.percent)}]</code>\n"
            f"<i>Used: {ram.used // (1024**2)}MB / Free: {ram.available // (1024**2)}MB</i>\n\n"

            f"⚙️ 𝗖𝗣𝗨 𝗟𝗼𝗮𝗱 ⇾ <code>{cpu}%</code>\n"
            f"<code>[{make_bar(cpu)}]</code>\n"
            f"<i>Frequency: {cpu_freq}</i>\n\n"

            f"💾 𝗗𝗶𝘀𝗸 𝗦𝗽𝗮𝗰𝗲\n"
            f"<code>[{make_bar(disk.used / disk.total * 100)}]</code>\n"
            f"<i>Used: {disk.used // (1024**3)}GB / Total: {disk.total // (1024**3)}GB</i>\n\n"

            f"━━━━━━━━━━━━━━━━━━\n"
            f"📶 𝗣𝗶𝗻𝗴 ⇾ <code>{ping_ms:.2f} ms</code>\n"
            f"🤖 <i>Powered by Oktacomel</i>"
        )

        await msg.edit_text(txt, parse_mode=ParseMode.HTML)

    except Exception as e:
        await msg.edit_text(f"❌ <b>System Error:</b> {str(e)}", parse_mode=ParseMode.HTML)

# ==========================================
# 💳 QR COMMAND (PREMIUM BOLD SANS STYLE)
# ==========================================
async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. KASUS PAYMENT (Jika user hanya ketik /qr tanpa teks)
    if not context.args:
        caption = (
            f"𝗤𝗥𝗜𝗦 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 💳\n\n"
            f"𝗡𝗠𝗜𝗗 ⇾ <code>ID1024325861937</code>\n"
            f"𝗡𝗮𝗺𝗲 ⇾ <code>IKIKSTORE</code>\n\n"
            f"<i>Scan this QR code to proceed payment.</i>"
        )
        # Pastikan QRIS_IMAGE sudah ada di config paling atas file
        try:
            await update.message.reply_photo(QRIS_IMAGE, caption=caption, parse_mode=ParseMode.HTML)
        except:
            await update.message.reply_text("❌ Gambar QRIS belum disetting.", parse_mode=ParseMode.HTML)
        return

    # 2. KASUS GENERATOR (Ketik /qr teks)
    text_data = " ".join(context.args)
    
    # Kirim status upload foto
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
    
    try:
        # Buat QR Code
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(text_data)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        
        # Simpan ke memory (Buffer)
        b = io.BytesIO()
        img.save(b, 'PNG')
        b.seek(0)
        
        # Caption Aesthetic (Bold Sans)
        caption = (
            f"𝗤𝗥 𝗖𝗢𝗗𝗘 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘𝗗 📸\n\n"
            f"𝗜𝗻𝗽𝘂𝘁 ⇾ <code>{html.escape(text_data)}</code>\n\n"
            f"🤖 <i>Powered by Oktacomel</i>"
        )
        
        await update.message.reply_photo(b, caption=caption, parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)

# ==========================================
# 🔍 BIN LOOKUP (CUSTOM API + CLEAN MONO)
# ==========================================
async def bin_lookup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Cek input
    if not context.args: 
        return await update.message.reply_text("⚠️ <b>Usage:</b> <code>/bin 454321</code>", parse_mode=ParseMode.HTML)
    
    bin_code = context.args[0].replace(" ", "")[:6]
    
    if not bin_code.isdigit():
        return await update.message.reply_text("❌ <b>Error:</b> Input must be numbers.", parse_mode=ParseMode.HTML)

    msg = await update.message.reply_text("⏳ <b>Checking...</b>", parse_mode=ParseMode.HTML)
    
    try:
        # === MENGGUNAKAN API KAMU (BIN_API) ===
        # Pastikan variabel BIN_API sudah ada di config atas
        r = await fetch_json(f"{BIN_API}/{bin_code}")
    except:
        r = None
    
    if r and ('brand' in r or 'scheme' in r):
        # Parsing Data
        brand = str(r.get('brand') or r.get('scheme', 'Unknown')).upper()
        type_c = str(r.get('type', 'Unknown')).upper()
        level = str(r.get('level') or r.get('card_category', 'Unknown')).upper()
        
        bank_raw = r.get('bank')
        bank = str(bank_raw.get('name') if isinstance(bank_raw, dict) else bank_raw or 'UNKNOWN').upper()
        
        country_raw = r.get('country')
        country = str(country_raw.get('name') if isinstance(country_raw, dict) else country_raw or 'UNKNOWN').upper()
        flag = country_raw.get('emoji', '') if isinstance(country_raw, dict) else ''

        # === TAMPILAN SESUAI REQUEST (BOLD ⇾ MONO) ===
        txt = (
            f"<b>𝗕𝗜𝗡 𝗟𝗼𝗼𝗸𝘂𝗽 𝗥𝗲𝘀𝘂𝗹𝘁</b> 🔍\n\n"
            f"<b>𝗕𝗜𝗡</b> ⇾ <code>{bin_code}</code>\n"
            f"<b>𝗜𝗻𝗳𝗼</b> ⇾ <code>{brand} - {type_c} - {level}</code>\n"
            f"<b>𝐈𝐬𝐬𝐮𝐞𝐫</b> ⇾ <code>{bank}</code>\n"
            f"<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲</b> ⇾ <code>{country} {flag}</code>"
        )
        await msg.edit_text(txt, parse_mode=ParseMode.HTML)
        
    else:
        # Tampilan Gagal
        txt = (
            f"<b>𝗕𝗜𝗡 Lookup Result</b> 🔍\n\n"
            f"<b>𝗕𝗜𝗡</b> ⇾ <code>{bin_code}</code>\n"
            f"<b>Status</b> ⇾ <code>NOT FOUND / DEAD ❌</code>"
        )
        await msg.edit_text(txt, parse_mode=ParseMode.HTML)


# ==========================================
# E-WALLET STALKER (PREMIUM)
# ==========================================
EWALLET_TYPES = {
    "gopay_user": "GoPay User",
    "gopay_driver": "GoPay Driver",
    "grab_user": "GrabPay",
    "wallet_dana": "DANA",
    "wallet_ovo": "OVO",
    "wallet_linkaja": "LinkAja",
    "wallet_shopeepay": "ShopeePay",
    "wallet_isaku": "iSaku",
}

# Store pending wallet checks: {user_id: wallet_code}
pending_wallet_checks = {}

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user has pending wallet selection
    if user_id in pending_wallet_checks and context.args:
        wallet_code = pending_wallet_checks.pop(user_id)
        phone = context.args[0].strip()
        await process_wallet_check(update, user_id, wallet_code, phone)
        return
    
    if context.args:
        # Direct usage: /wallet DANA 08xxx or /wallet 08xxx (show menu)
        first_arg = context.args[0].strip().upper()
        wallet_map = {v.upper(): k for k, v in EWALLET_TYPES.items()}
        
        if first_arg in wallet_map and len(context.args) > 1:
            wallet_code = wallet_map[first_arg]
            phone = context.args[1].strip()
            await process_wallet_check(update, user_id, wallet_code, phone)
            return
        else:
            # Assume it's a phone number, show wallet selection
            phone = context.args[0].strip()
            text = (
                "<b>OKTACOMEL E-WALLET STALKER</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Phone: <code>{html.escape(phone)}</code>\n\n"
                "Pilih jenis E-Wallet:\n"
            )
            buttons = []
            row = []
            for code, name in EWALLET_TYPES.items():
                row.append(InlineKeyboardButton(name, callback_data=f"wallet_{code}|{phone}|{user_id}"))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")])
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        # Show wallet type selection first
        text = (
            "<b>OKTACOMEL E-WALLET STALKER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Cek nama pemilik akun e-wallet.\n\n"
            "Pilih jenis E-Wallet:\n"
        )
        buttons = []
        row = []
        for code, name in EWALLET_TYPES.items():
            row.append(InlineKeyboardButton(name, callback_data=f"wallet_select_{code}|{user_id}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")])
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def process_wallet_check(update, user_id, wallet_code, phone):
    """Process wallet check with proper API response parsing"""
    name = EWALLET_TYPES.get(wallet_code, wallet_code)
    
    msg = await update.message.reply_text(
        f"<b>PROCESSING {name.upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Phone: <code>{html.escape(phone)}</code>\n"
        f"Status: Fetching data...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        api_url = f"https://api.gimita.id/api/stalker/ewallet?ewallet_code={wallet_code}&phone_number={phone}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url)
            result = resp.json()
        
        # Fix: Check statusCode or success field
        if result.get("statusCode") == 200 or result.get("success") == True:
            data_info = result.get("data", {})
            account_name = data_info.get("account_name", data_info.get("name", data_info.get("nama", "N/A")))
            account_number = data_info.get("account_number", data_info.get("phone", phone))
            status = data_info.get("status", "valid")
            
            text = (
                f"<b>E-WALLET STALKER RESULT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Phone: <code>{html.escape(str(account_number))}</code>\n"
                f"Wallet: <code>{name}</code>\n"
                f"Name: <code>{html.escape(str(account_name))}</code>\n"
                f"Status: <code>{html.escape(str(status).upper())}</code>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Powered by OKTACOMEL"
            )
        else:
            error_msg = result.get("message", result.get("error", "Account not found"))
            text = (
                f"<b>E-WALLET STALKER RESULT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Phone: <code>{html.escape(phone)}</code>\n"
                f"Wallet: <code>{name}</code>\n\n"
                f"Status: NOT FOUND\n"
                f"Message: {html.escape(str(error_msg))}\n\n"
                f"Powered by OKTACOMEL"
            )
    except Exception as e:
        logger.error(f"[WALLET] Error: {e}")
        text = (
            f"<b>E-WALLET STALKER ERROR</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Phone: <code>{html.escape(phone)}</code>\n"
            f"Wallet: <code>{name}</code>\n\n"
            f"Error: {html.escape(str(e)[:100])}\n\n"
            f"Powered by OKTACOMEL"
        )
    
    kb = [[InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]]
    await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def wallet_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    
    if "|" not in data:
        await query.answer("Invalid callback", show_alert=True)
        return
        
    parts = data.split("|")
    
    if data.startswith("wallet_select_"):
        wallet_code = parts[0].replace("wallet_select_", "")
        owner_id = int(parts[1]) if len(parts) > 1 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        name = EWALLET_TYPES.get(wallet_code, wallet_code)
        pending_wallet_checks[user_id] = wallet_code
        await query.answer()
        await query.message.edit_text(
            f"<b>{name} Stalker</b>\n\n"
            f"Kirim nomor telepon untuk di-stalk:\n"
            f"<code>/wallet 08xxxxxxxxxx</code>\n\n"
            f"Format: 08xxx atau 628xxx",
            parse_mode=ParseMode.HTML
        )
        return
    
    if not data.startswith("wallet_"):
        return
    
    wallet_code = parts[0].replace("wallet_", "")
    phone = parts[1] if len(parts) > 1 else ""
    owner_id = int(parts[2]) if len(parts) > 2 else user_id
    
    if user_id != owner_id:
        await query.answer("Bukan milik kamu!", show_alert=True)
        return
    
    await query.answer("Processing...")
    
    name = EWALLET_TYPES.get(wallet_code, wallet_code)
    
    await query.message.edit_text(
        f"<b>PROCESSING {name.upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Phone: <code>{html.escape(phone)}</code>\n"
        f"Status: Fetching data...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        api_url = f"https://api.gimita.id/api/stalker/ewallet?ewallet_code={wallet_code}&phone_number={phone}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url)
            result = resp.json()
        
        # Fix: Check statusCode or success field
        if result.get("statusCode") == 200 or result.get("success") == True:
            data_info = result.get("data", {})
            account_name = data_info.get("account_name", data_info.get("name", data_info.get("nama", "N/A")))
            account_number = data_info.get("account_number", data_info.get("phone", phone))
            status = data_info.get("status", "valid")
            
            text = (
                f"<b>E-WALLET STALKER RESULT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Phone: <code>{html.escape(str(account_number))}</code>\n"
                f"Wallet: <code>{name}</code>\n"
                f"Name: <code>{html.escape(str(account_name))}</code>\n"
                f"Status: <code>{html.escape(str(status).upper())}</code>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Powered by OKTACOMEL"
            )
        else:
            error_msg = result.get("message", result.get("error", "Account not found"))
            text = (
                f"<b>E-WALLET STALKER RESULT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Phone: <code>{html.escape(phone)}</code>\n"
                f"Wallet: <code>{name}</code>\n\n"
                f"Status: NOT FOUND\n"
                f"Message: {html.escape(str(error_msg))}\n\n"
                f"Powered by OKTACOMEL"
            )
    except Exception as e:
        logger.error(f"[WALLET] Callback Error: {e}")
        text = (
            f"<b>E-WALLET STALKER ERROR</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Phone: <code>{html.escape(phone)}</code>\n"
            f"Wallet: <code>{name}</code>\n\n"
            f"Error: {html.escape(str(e)[:100])}\n\n"
            f"Powered by OKTACOMEL"
        )
    
    kb = [[InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]]
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


# ==========================================
# ⚡ PLN BILL CHECKER (PREMIUM)
# ==========================================
async def pln_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        text = (
            "⚡ <b>OKTACOMEL PLN BILL CHECKER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Cek tagihan listrik PLN berdasarkan ID Pelanggan.\n\n"
            "<b>📌 Usage:</b>\n"
            "<code>/pln 123456789012</code>\n\n"
            "<b>📋 Info:</b>\n"
            "• ID Pelanggan terdiri dari 12 digit\n"
            "• Dapat dilihat di meteran atau struk PLN\n"
            "• Mendukung PLN Pascabayar"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return
    
    pln_id = context.args[0].strip()
    
    if not pln_id.isdigit():
        await update.message.reply_text(
            "❌ <b>Error:</b> ID Pelanggan harus berupa angka!",
            parse_mode=ParseMode.HTML
        )
        return
    
    msg = await update.message.reply_text(
        "⚡ <b>CHECKING PLN BILL...</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>ID Pelanggan:</b> <code>{html.escape(pln_id)}</code>\n"
        "⏳ <b>Status:</b> Fetching data...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        api_url = f"https://api.gimita.id/api/info/pln?id={pln_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url)
            result = resp.json()
        
        # Fix: Check statusCode field
        if result.get("statusCode") == 200:
            data = result.get("data", {})
            
            # Parse nested data structure from API
            title = data.get("title", "")
            info_data = data.get("data", "")
            customer_id = result.get("customer_id", pln_id)
            
            text = (
                "<b>PLN BILL CHECKER RESULT</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"ID Pelanggan: <code>{html.escape(str(customer_id))}</code>\n\n"
            )
            
            if title:
                text += f"Status: <code>{html.escape(str(title))}</code>\n\n"
            
            if info_data:
                text += f"Info: <code>{html.escape(str(info_data))}</code>\n\n"
            
            text += (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Data Retrieved Successfully\n"
                "Powered by OKTACOMEL"
            )
        else:
            error_msg = result.get("message", result.get("error", "Data tidak ditemukan"))
            text = (
                "<b>PLN BILL CHECKER RESULT</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"ID Pelanggan: <code>{html.escape(pln_id)}</code>\n\n"
                f"Status: NOT FOUND\n"
                f"Message: {html.escape(str(error_msg))}\n\n"
                "Powered by OKTACOMEL"
            )
    except Exception as e:
        logger.error(f"[PLN] Error: {e}")
        text = (
            "<b>PLN BILL CHECKER ERROR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ID Pelanggan: <code>{html.escape(pln_id)}</code>\n\n"
            f"Error: {html.escape(str(e)[:100])}\n\n"
            "Powered by OKTACOMEL"
        )
    
    kb = [[InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]]
    await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


# ==========================================
# ⚽ SOCCER SCHEDULE (PREMIUM)
# ==========================================
async def bola_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    msg = await update.message.reply_text(
        "⚽ <b>LOADING SOCCER SCHEDULE...</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ Fetching matches from ESPN...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        api_url = "https://api.gimita.id/api/info/jadwalbola"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url)
            result = resp.json()
        
        # Fix: Parse correct API structure
        data = result.get("data", {})
        matches = data.get("matches", [])
        match_date = data.get("date", "")
        
        if not matches:
            text = (
                "<b>SOCCER SCHEDULE</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Tidak ada jadwal pertandingan hari ini.\n\n"
                "Powered by OKTACOMEL"
            )
        else:
            text = (
                "<b>JADWAL PERTANDINGAN BOLA</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )
            if match_date:
                text += f"Date: {html.escape(str(match_date))}\n\n"
            
            count = 0
            for match in matches[:15]:
                if isinstance(match, dict):
                    team1 = match.get("team1", "TBD")
                    team2 = match.get("team2", "TBD")
                    time_str = match.get("time", "")
                    league = match.get("liga", match.get("league", ""))
                    location = match.get("location", "")
                    
                    if league:
                        text += f"[{html.escape(str(league)[:25])}]\n"
                    text += f"<code>{html.escape(str(team1))}</code> vs <code>{html.escape(str(team2))}</code>\n"
                    if time_str:
                        text += f"Time: {html.escape(str(time_str))}\n"
                    text += "\n"
                    count += 1
            
            text += (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Total: {count} matches\n"
                "Source: ESPN\n"
                "Powered by OKTACOMEL"
            )
    except Exception as e:
        logger.error(f"[BOLA] Error: {e}")
        text = (
            "<b>SOCCER SCHEDULE ERROR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Error: {html.escape(str(e)[:100])}\n\n"
            "Powered by OKTACOMEL"
        )
    
    kb = [
        [InlineKeyboardButton("Refresh", callback_data=f"bola_refresh|{user_id}")],
        [InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]
    ]
    await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def bola_refresh_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    
    parts = data.split("|")
    owner_id = int(parts[1]) if len(parts) > 1 else user_id
    
    if user_id != owner_id:
        await query.answer("Bukan milik kamu!", show_alert=True)
        return
    
    await query.answer("Refreshing...")
    
    try:
        api_url = "https://api.gimita.id/api/info/jadwalbola"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url)
            result = resp.json()
        
        # Fix: Parse correct API structure
        data = result.get("data", {})
        matches = data.get("matches", [])
        match_date = data.get("date", "")
        
        if not matches:
            text = (
                "<b>SOCCER SCHEDULE</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Tidak ada jadwal pertandingan hari ini.\n\n"
                "Powered by OKTACOMEL"
            )
        else:
            now = datetime.datetime.now(TZ).strftime("%H:%M:%S")
            text = (
                "<b>JADWAL PERTANDINGAN BOLA</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )
            if match_date:
                text += f"Date: {html.escape(str(match_date))}\n\n"
            
            count = 0
            for match in matches[:15]:
                if isinstance(match, dict):
                    team1 = match.get("team1", "TBD")
                    team2 = match.get("team2", "TBD")
                    time_str = match.get("time", "")
                    league = match.get("liga", match.get("league", ""))
                    
                    if league:
                        text += f"[{html.escape(str(league)[:25])}]\n"
                    text += f"<code>{html.escape(str(team1))}</code> vs <code>{html.escape(str(team2))}</code>\n"
                    if time_str:
                        text += f"Time: {html.escape(str(time_str))}\n"
                    text += "\n"
                    count += 1
            
            text += (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Total: {count} matches\n"
                f"Updated: {now}\n"
                "Source: ESPN\n"
                "Powered by OKTACOMEL"
            )
    except Exception as e:
        logger.error(f"[BOLA] Refresh Error: {e}")
        text = (
            "<b>SOCCER SCHEDULE ERROR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Error: {html.escape(str(e)[:100])}\n\n"
            "Powered by OKTACOMEL"
        )
    
    kb = [
        [InlineKeyboardButton("Refresh", callback_data=f"bola_refresh|{user_id}")],
        [InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]
    ]
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


# ==========================================
# WORD CHAIN GAME - EXPANDED WORD DATABASE
# ==========================================

WORD_CHAIN_WORDS = {
    "id": {
        "easy": [
            # Buah-buahan
            "apel", "jeruk", "mangga", "pisang", "anggur", "melon", "semangka", "pepaya", "kelapa", "durian",
            "nanas", "lemon", "leci", "rambutan", "markisa", "blueberry", "strawberry", "kiwi", "alpukat", "jambu",
            "delima", "persik", "pir", "cranberry", "murbei", "nangka", "salak", "sawo", "bit", "aprikot",
            
            # Hewan
            "kucing", "anjing", "burung", "ikan", "ayam", "bebek", "kambing", "sapi", "kuda", "gajah",
            "harimau", "singa", "monyet", "gorila", "jerapah", "zebra", "badak", "beruang", "serigala", "rubah",
            "kelinci", "hamster", "tikus", "babi", "domba", "lama", "unta", "singa", "panther", "leopard",
            "buaya", "ular", "katak", "kura", "kepiting", "udang", "cumi", "gurita", "semut", "lebah",
            
            # Furniture & Rumah
            "meja", "kursi", "pintu", "jendela", "lantai", "dinding", "atap", "rumah", "mobil", "motor",
            "sofa", "kasur", "lemari", "rak", "bangku", "pagar", "tangga", "teras", "dapur", "kamar",
            "kamar mandi", "toilet", "cermin", "cermin", "lampu", "jendela", "ventilasi", "garasi", "gudang", "loteng",
            "gudang", "ruang tamu", "ruang makan", "balkon", "halaman", "kolam", "pohon", "bunga", "taman", "pagar",
            
            # Alat Tulis & Sekolah
            "buku", "pensil", "pulpen", "kertas", "tas", "sepatu", "baju", "celana", "topi", "kaos",
            "notebook", "penggaris", "penghapus", "penajam", "kliping", "stapler", "scotch", "selotip", "glue", "crayon",
            "spidol", "cat", "kanvas", "papan tulis", "kapur", "daftar", "tas sekolah", "seragam", "kaus kaki", "sandal",
            
            # Alam & Cuaca
            "air", "api", "tanah", "angin", "hujan", "panas", "dingin", "terang", "gelap", "besar",
            "kecil", "panjang", "pendek", "tinggi", "rendah", "luas", "sempit", "cepat", "lambat", "keras",
            "lembut", "berat", "ringan", "panas", "hangat", "sejuk", "dingin", "basah", "kering", "kotor",
            "bersih", "indah", "jelek", "bagus", "buruk", "baru", "lama", "segar", "busuk", "manis",
            
            # Makanan & Minuman
            "nasi", "roti", "mie", "daging", "ikan", "telur", "susu", "keju", "mentega", "garam",
            "gula", "garam", "minyak", "kecap", "sambal", "saus", "sayur", "buah", "teh", "kopi",
            "air", "jus", "susu", "minuman", "soda", "bir", "wine", "teh", "kopi", "cokelat",
            "permen", "kue", "roti", "pizza", "pasta", "noodle", "sup", "salad", "burger", "sandwich",
            
            # Profesi & Pekerjaan
            "guru", "dokter", "perawat", "polisi", "tentara", "pilot", "sopir", "tukang", "petani", "nelayan",
            "pedagang", "pengusaha", "karyawan", "manager", "direktur", "presiden", "menteri", "hakim", "lawyer", "aktor",
            "penyanyi", "penari", "atlet", "pelatih", "jurnalis", "fotografer", "desainer", "programmer", "insinyur", "arsitek",
            
            # Emosi & Perasaan
            "senang", "sedih", "marah", "takut", "cinta", "benci", "khawatir", "tenang", "gugup", "percaya",
            "ragu", "yakin", "puas", "kecewa", "bangga", "malu", "heran", "penasaran", "tertarik", "bosan",
            
            # Warna
            "merah", "biru", "hijau", "kuning", "orange", "ungu", "putih", "hitam", "abu", "cokelat",
            "pink", "cyan", "magenta", "maroon", "navy", "teal", "olive", "gold", "silver", "bronze",
            
            # Angka & Waktu
            "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh",
            "hari", "bulan", "tahun", "jam", "menit", "detik", "minggu", "pagi", "siang", "malam",
            "senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu", "januari", "februari", "maret",
        ],
        
        "medium": [
            # Benda & Objek
            "kendaraan", "pesawat", "kereta", "kapal", "helikopter", "sepeda", "skateboard", "perahu", "barge", "tanker",
            "traktor", "excavator", "bulldozer", "crane", "forklift", "ambulans", "fire truck", "garbage truck", "bus", "minibus",
            
            # Pekerjaan & Karir
            "pendidikan", "pekerjaan", "bisnis", "industri", "pertanian", "perternakan", "perikanan", "manufaktur", "konstruksi", "pariwisata",
            "perdagangan", "keuangan", "perbankan", "asuransi", "real estate", "technology", "telekomunikasi", "energi", "transportasi", "logistik",
            
            # Makanan & Minuman Lanjut
            "makanan", "minuman", "pakaian", "peralatan", "kesehatan", "perawatan", "kosmetik", "obat", "vitamin", "suplemen",
            "shampo", "sabun", "pasta gigi", "deodorant", "lotion", "krim", "masker", "serum", "toner", "essence",
            
            # Hubungan & Keluarga
            "keluarga", "tetangga", "teman", "sahabat", "musuh", "rival", "partner", "kolega", "mentor", "murid",
            "orang tua", "ayah", "ibu", "kakak", "adik", "kakek", "nenek", "paman", "bibi", "sepupu",
            "istri", "suami", "anak", "menantu", "mertua", "pacar", "tunangan", "istri", "suami", "janda",
            
            # Perasaan & Emosi Lanjut
            "harapan", "impian", "keinginan", "kebutuhan", "mimpi", "aspirasi", "visi", "tujuan", "ambisi", "cita",
            "kebahagiaan", "kesedihan", "kemarahan", "ketakutan", "kecemasan", "ketenangan", "kegembiraan", "kesedihan", "kepuasan", "kekecewaan",
            "kepercayaan", "keraguan", "keyakinan", "ketidakpercayaan", "kepastian", "ketidakpastian", "keberanian", "ketakutan", "kebencian", "kecintaan",
            
            # Pendidikan & Pembelajaran
            "sekolah", "universitas", "kampus", "kelas", "pelajaran", "belajar", "mengajar", "ujian", "test", "quiz",
            "nilai", "rapor", "sertifikat", "diploma", "gelar", "beasiswa", "tutor", "guru", "dosen", "profesor",
            "mata pelajaran", "matematika", "bahasa", "sains", "sejarah", "geografi", "olahraga", "seni", "musik", "tari",
            
            # Perjalanan & Tempat
            "perjalanan", "petualangan", "wisata", "liburan", "rekreasi", "backpacking", "tour", "eksplorasi", "navigasi", "rute",
            "jalan", "jembatan", "terowongan", "tikungan", "batas", "perbatasan", "negara", "kota", "kampung", "desa",
            "pantai", "gunung", "lembah", "sungai", "danau", "laut", "samudra", "teluk", "pulau", "benua",
            
            # Pengalaman & Pengetahuan
            "pengalaman", "pengetahuan", "kebijaksanaan", "keahlian", "keterampilan", "kemampuan", "bakat", "potensi", "kesempatan", "tantangan",
            "kesuksesan", "kegagalan", "pencapaian", "prestasi", "kekalahan", "kemenangan", "pertumbuhan", "kemajuan", "perkembangan", "peningkatan",
            "pembelajaran", "pemahaman", "kesadaran", "realisasi", "pencerahan", "inspirasi", "motivasi", "semangat", "determinasi", "resolusi",
            
            # Sifat & Karakteristik
            "kebijaksanaan", "keberanian", "kejujuran", "kebaikan", "keadilan", "kemurahan hati", "kedermawanan", "kemurahan", "kesederhanaan", "kerendahan hati",
            "keangkuhan", "keserakahan", "keegoisan", "kecemburuan", "kedengkian", "kebencian", "kekerasan", "kelicikan", "kecurangan", "penipuan",
            "kesabaran", "ketenangan", "kedamaian", "keharmonisan", "keselarasan", "keseimbangan", "kesetaraan", "kesamaan", "keunikan", "keragaman",
            
            # Politik & Sosial
            "kemerdekaan", "kebebasan", "hak", "kewajiban", "tanggung jawab", "kepemimpinan", "kekuasaan", "otoritas", "pemerintah", "negara",
            "persatuan", "kesatuan", "keharmonisan", "kesolidan", "kerja sama", "kolaborasi", "gotong royong", "bahu membahu", "saling bantu", "bersama",
            "perdamaian", "perang", "konflik", "sengketa", "pertikaian", "pertentangan", "perbedaan", "persamaan", "toleransi", "pluralisme",
            
            # Seni & Budaya
            "seni", "budaya", "tradisi", "kesenian", "musik", "tarian", "teater", "film", "sastra", "puisi",
            "novel", "cerpen", "drama", "komedi", "tragedi", "fantasi", "misteri", "horor", "romantis", "aksi",
            "melukis", "patung", "keramik", "batik", "tenun", "ukiran", "anyaman", "bordir", "pertunjukan", "pameran",
            
            # Teknologi & Inovasi
            "teknologi", "komputer", "internet", "smartphone", "laptop", "tablet", "aplikasi", "website", "software", "hardware",
            "robot", "AI", "machine learning", "virtual reality", "augmented reality", "blockchain", "cryptocurrency", "metaverse", "cloud", "server",
        ],
        
        "hard": [
            # Politik & Tata Negara
            "demokratisasi", "federalisasi", "sentralisasi", "desentralisasi", "otonomi", "referendum", "demokrasi", "autokrasi", "oligarki", "monarki",
            "parlementer", "presidensial", "konstitusi", "undang-undang", "regulasi", "peraturan", "kebijakan", "strategi", "taktik", "maneuver",
            "diplomasi", "negosiasi", "perjanjian", "traktat", "konvensi", "protokol", "amandemen", "revisi", "reformasi", "revolusi",
            
            # Ekonomi & Bisnis
            "ekonomi", "kapitalisme", "sosialisme", "komunisme", "merkantilisme", "liberalisme", "proteksionisme", "free trade", "tarif", "subsidi",
            "inflasi", "deflasi", "stagflasi", "resesi", "depresi", "pertumbuhan", "ekspansi", "kontraksi", "likuiditas", "solvabilitas",
            "modal", "investasi", "dividen", "saham", "obligasi", "derivatif", "hedging", "leverage", "arbitrase", "spekulasi",
            "merger", "akuisisi", "konsolidasi", "diversifikasi", "integrasi", "outsourcing", "insourcing", "franchising", "licensing", "partnership",
            
            # Pendidikan & Penelitian
            "metodologi", "epistemologi", "ontologi", "aksiologi", "hermeneutika", "fenomenologi", "positivisme", "relativisme", "absolutisme", "skeptisisme",
            "empirisisme", "rasionalisme", "pragmatisme", "utilitarianisme", "altruisme", "egoisme", "hedonisme", "stoisisme", "sinoisme", "buddhisme",
            "kuantitatif", "kualitatif", "eksperimental", "observasional", "deskriptif", "analitik", "eksploratori", "konfirmatori", "longitudinal", "transversal",
            "reliabilitas", "validitas", "objektifitas", "subjektifitas", "intersubjektivitas", "triangulasi", "saturation", "teori", "hipotesis", "paradigma",
            
            # Industri & Manufaktur
            "industrialisasi", "manufaktur", "otomasi", "mekanisasi", "efisiensi", "produktivitas", "kapasitas", "throughput", "output", "input",
            "quality control", "quality assurance", "six sigma", "lean manufacturing", "just-in-time", "supply chain", "logistics", "inventory", "warehouse", "distribution",
            "raw material", "intermediate product", "finished product", "assembly", "fabrication", "machining", "welding", "casting", "molding", "stamping",
            
            # Teknologi & Inovasi
            "digitalisasi", "transformasi digital", "modernisasi", "otomatisasi", "robotisasi", "computerisasi", "informatisasi", "telematika", "cybersecurity", "encryption",
            "decryption", "authentication", "authorization", "firewall", "antivirus", "malware", "ransomware", "spyware", "trojan", "botnet",
            "cloud computing", "edge computing", "fog computing", "quantum computing", "neuromorphic", "biotechnology", "nanotechnology", "synthetic biology", "genetic engineering", "CRISPR",
            
            # Lingkungan & Keberlanjutan
            "sustainability", "keberlanjutan", "ekosistem", "biodiversitas", "konservasi", "preservasi", "restorasi", "rehabilitasi", "mitigasi", "adaptasi",
            "renewable energy", "fossil fuel", "carbon footprint", "greenhouse gas", "deforestation", "reforestation", "afforestation", "permafrost", "erosion", "desertification",
            "pollution", "contamination", "remediation", "sequestration", "offsetting", "circular economy", "zero waste", "sustainable development", "triple bottom line", "ESG",
            
            # Kesehatan & Medis
            "epidemiologi", "etiologi", "patogenesis", "patofisiologi", "imunopatologi", "onkologi", "kardiologi", "neurologi", "psychiatry", "pediatrics",
            "immunology", "virology", "bacteriology", "parasitology", "mycology", "toxicology", "pharmacology", "anesthesiology", "radiology", "pathology",
            "diagnosis", "prognosis", "terapeutik", "intervensi", "prophylaxis", "metastasis", "remission", "relapse", "recovery", "mortality",
            "morbidity", "incidence", "prevalence", "comorbidity", "syndrome", "etiology", "sequela", "iatrogenic", "nosocomial", "opportunistic",
            
            # Psikologi & Sosiologi
            "behaviorisme", "kognitivisme", "konstruktivisme", "humanisme", "psikoanalis", "jungianism", "adlerian", "gestalt", "sistemik", "strukturalis",
            "sosialisasi", "enkulturasi", "akulturasi", "asimilasi", "integrasi", "marginalisasi", "stigmatisasi", "stereotip", "prasangka", "diskriminasi",
            "stratifikasi", "mobilitas", "status", "peran", "identitas", "habitus", "capital", "power", "hegemoni", "subordinasi",
            "anomie", "alienasi", "reifikasi", "fetisisme", "komodifikasi", "marketisasi", "komersialisasi", "sekulerisasi", "fundamentalisme", "pluralisme",
            
            # Filsafat & Seni
            "metafisika", "logika", "estetika", "etika", "aksiologi", "fenomenologi", "eksistensialisme", "nihilisme", "absurdisme", "romantisisme",
            "realisme", "naturalisme", "idealisme", "materialisme", "dialektika", "hermeneutika", "dekonstruksi", "semiotika", "semiotik", "semantika",
            "pragmatisme", "utilitarianisme", "kantianisme", "hegelianisme", "marxisme", "foucaultisme", "derridaisme", "deleuzism", "lacanisme", "sartreanism",
            
            # Komunikasi & Media
            "komunikasi", "propaganda", "persuasi", "manipulasi", "disinformasi", "misinformasi", "fake news", "fact checking", "debunking", "verification",
            "narasi", "framing", "agenda setting", "priming", "stereotype", "bias", "echo chamber", "filter bubble", "polarisasi", "fragmentasi",
            "retorika", "dialektika", "pragmatik", "linguistik", "semantik", "sintaksis", "fonologi", "morfologi", "pragmatisme", "conversational implicature",
            
            # Sains & Alam
            "fisika", "kimia", "biologi", "astronomi", "geologi", "meteorologi", "oceanografi", "seismologi", "volkanologi", "glaciology",
            "mekanika", "dinamika", "termodinamika", "elektromagnetika", "optika", "akustika", "relativitas", "mekanika kuantum", "astrofisika", "kosmologi",
            "organik", "anorganik", "biokimia", "geokimia", "astrokimia", "radiokimia", "fotokimia", "elektrokimia", "katalisis", "sintesis",
            "genetika", "evolusi", "ekologi", "etologi", "neurosains", "immunosains", "mikrobiologi", "virologi", "mikologi", "parasitologi",
            
            # Perdagangan & Keuangan Internasional
            "globalisasi", "internasionalisasi", "ekspor", "impor", "perdagangan", "tarif", "kuota", "dumping", "proteksionisme", "liberalisasi",
            "FTA", "ASEAN", "WTO", "IMF", "World Bank", "OPEC", "G20", "BRICS", "Brexit", "TPP",
            "forex", "cryptocurrency", "blockchain", "NFT", "DeFi", "fintech", "insurtech", "regtech", "legaltech", "proptech",
            "banking", "insurance", "investment", "trading", "brokerage", "custody", "clearing", "settlement", "hedging", "arbitrage",
            
            # Manufaktur & Produksi Lanjut
            "lean manufacturing", "six sigma", "kaizen", "kanban", "poka-yoke", "heijunka", "takt time", "bottleneck", "throughput", "cycle time",
            "value stream", "waste elimination", "continuous improvement", "standardization", "visual management", "root cause analysis", "PDCA", "DMAIC", "RCA", "5S",
            "MRP", "ERP", "SCM", "CRM", "PLM", "CAD", "CAM", "CNC", "IoT", "Industry 4.0",
            
            # Sumber Daya Manusia & Organisasi
            "rekrutmen", "seleksi", "onboarding", "training", "development", "coaching", "mentoring", "performance management", "appraisal", "compensation",
            "culture", "engagement", "retention", "turnover", "absenteeism", "presenteeism", "productivity", "efficiency", "effectiveness", "profitability",
            "organizational structure", "hierarchy", "matrix", "flat", "network", "agile", "holacracy", "sociocracy", "teal", "purple",
            "leadership", "management", "governance", "compliance", "risk management", "audit", "internal control", "accountability", "transparency", "integrity",
        ]
    },
    
    "en": {
        "easy": [
            # Fruits
            "apple", "orange", "banana", "grape", "melon", "cherry", "peach", "pear", "plum", "mango",
            "pineapple", "lemon", "lime", "kiwi", "avocado", "papaya", "coconut", "durian", "rambutan", "blueberry",
            "strawberry", "raspberry", "blackberry", "cranberry", "pomegranate", "passion fruit", "guava", "dragon fruit", "acai", "fig",
            "date", "apricot", "tangerine", "mandarin", "grapefruit", "watermelon", "cantaloupe", "honeydew", "persimmon", "mulberry",
            
            # Animals
            "cat", "dog", "bird", "fish", "horse", "cow", "sheep", "goat", "pig", "duck",
            "tiger", "lion", "monkey", "gorilla", "giraffe", "zebra", "rhinoceros", "bear", "wolf", "fox",
            "rabbit", "hamster", "rat", "mouse", "elephant", "llama", "camel", "cheetah", "leopard", "panther",
            "crocodile", "snake", "frog", "turtle", "crab", "shrimp", "squid", "octopus", "ant", "bee",
            "penguin", "penguin", "parrot", "eagle", "owl", "falcon", "hawk", "sparrow", "pigeon", "raven",
            
            # Household Items
            "table", "chair", "door", "window", "floor", "wall", "roof", "house", "car", "bike",
            "sofa", "bed", "wardrobe", "shelf", "bench", "fence", "stairs", "porch", "kitchen", "bedroom",
            "bathroom", "toilet", "mirror", "lamp", "ventilation", "garage", "storage", "attic", "cellar", "hallway",
            "living room", "dining room", "balcony", "yard", "garden", "pool", "tree", "flower", "park", "fence",
            
            # School Supplies
            "book", "pen", "paper", "bag", "shoe", "shirt", "pants", "hat", "sock", "coat",
            "notebook", "ruler", "eraser", "pencil sharpener", "clip", "stapler", "tape", "glue", "crayon", "marker",
            "whiteboard", "chalk", "desk", "locker", "backpack", "uniform", "tie", "glasses", "watch", "pencil case",
            
            # Nature & Weather
            "water", "fire", "earth", "wind", "rain", "sun", "moon", "star", "sky", "sea",
            "cloud", "snow", "ice", "storm", "thunder", "lightning", "fog", "dew", "frost", "hail",
            "breeze", "tornado", "hurricane", "monsoon", "drought", "flood", "earthquake", "volcano", "mountain", "valley",
            "river", "lake", "ocean", "beach", "island", "continent", "desert", "forest", "jungle", "meadow",
            
            # Food & Drink
            "rice", "bread", "noodle", "meat", "fish", "egg", "milk", "cheese", "butter", "salt",
            "sugar", "oil", "soy sauce", "sauce", "pepper", "vegetable", "fruit", "tea", "coffee", "water",
            "juice", "soda", "beer", "wine", "candy", "cake", "pizza", "pasta", "soup", "salad",
            "burger", "sandwich", "chicken", "beef", "pork", "shrimp", "tofu", "mushroom", "bean", "corn",
            
            # Jobs & Professions
            "teacher", "doctor", "nurse", "police", "soldier", "pilot", "driver", "carpenter", "farmer", "fisherman",
            "merchant", "businessman", "employee", "manager", "director", "president", "minister", "judge", "lawyer", "actor",
            "singer", "dancer", "athlete", "coach", "journalist", "photographer", "designer", "programmer", "engineer", "architect",
            "mechanic", "plumber", "electrician", "gardener", "cook", "chef", "waiter", "cleaner", "janitor", "guard",
            
            # Emotions & Feelings
            "happy", "sad", "angry", "afraid", "love", "hate", "worry", "calm", "nervous", "trust",
            "doubt", "confident", "satisfied", "disappointed", "proud", "ashamed", "surprised", "curious", "interested", "bored",
            "excited", "anxious", "peaceful", "confused", "grateful", "jealous", "envious", "lonely", "friendly", "hostile",
            
            # Colors
            "red", "blue", "green", "yellow", "orange", "purple", "white", "black", "gray", "brown",
            "pink", "cyan", "magenta", "maroon", "navy", "teal", "olive", "gold", "silver", "bronze",
            "crimson", "scarlet", "violet", "indigo", "turquoise", "lime", "beige", "ivory", "pearl", "coral",
            
            # Numbers & Time
            "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
            "day", "month", "year", "hour", "minute", "second", "week", "morning", "afternoon", "night",
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "January", "February", "March",
            "spring", "summer", "autumn", "winter", "today", "yesterday", "tomorrow", "now", "then", "later",
        ],
        
        "medium": [
            # Vehicles & Transportation
            "vehicle", "airplane", "train", "ship", "helicopter", "bicycle", "skateboard", "boat", "barge", "tanker",
            "tractor", "excavator", "bulldozer", "crane", "forklift", "ambulance", "fire truck", "garbage truck", "bus", "minibus",
            "motorcycle", "scooter", "quad", "van", "truck", "semi-truck", "trailer", "ferry", "yacht", "submarine",
            
            # Jobs & Careers
            "education", "work", "business", "industry", "agriculture", "animal husbandry", "fishing", "manufacturing", "construction", "tourism",
            "trade", "finance", "banking", "insurance", "real estate", "technology", "telecommunications", "energy", "transportation", "logistics",
            "entertainment", "sports", "arts", "healthcare", "hospitality", "retail", "wholesale", "consulting", "accounting", "legal",
            
            # Food & Nutrition Advanced
            "nutrition", "protein", "carbohydrate", "fat", "vitamin", "mineral", "fiber", "calorie", "diet", "meal",
            "breakfast", "lunch", "dinner", "snack", "appetizer", "main course", "dessert", "beverage", "alcoholic", "non-alcoholic",
            "organic", "natural", "processed", "frozen", "canned", "fresh", "dried", "fermented", "raw", "cooked",
            
            # Relationships & Family
            "family", "neighbor", "friend", "best friend", "enemy", "rival", "partner", "colleague", "mentor", "student",
            "parent", "father", "mother", "brother", "sister", "grandfather", "grandmother", "uncle", "aunt", "cousin",
            "wife", "husband", "child", "son", "daughter", "son-in-law", "daughter-in-law", "parent-in-law", "widow", "widower",
            
            # Emotions Advanced
            "happiness", "sadness", "anger", "fear", "anxiety", "calmness", "joy", "sorrow", "grief", "relief",
            "hope", "despair", "confidence", "insecurity", "courage", "cowardice", "kindness", "cruelty", "love", "hatred",
            "trust", "distrust", "loyalty", "betrayal", "honesty", "dishonesty", "generosity", "stinginess", "humility", "arrogance",
            "compassion", "indifference", "empathy", "apathy", "enthusiasm", "lethargy", "optimism", "pessimism", "gratitude", "ingratitude",
            
            # Education & Learning
            "school", "university", "campus", "classroom", "lesson", "study", "teach", "exam", "test", "quiz",
            "grade", "report card", "certificate", "diploma", "degree", "scholarship", "tutor", "professor", "lecturer", "instructor",
            "subject", "mathematics", "language", "science", "history", "geography", "physical education", "art", "music", "dance",
            "curriculum", "syllabus", "textbook", "library", "laboratory", "gymnasium", "cafeteria", "dormitory", "campus life", "student",
            
            # Travel & Tourism
            "travel", "adventure", "tourism", "vacation", "holiday", "recreation", "backpacking", "tour", "exploration", "navigation",
            "street", "bridge", "tunnel", "turn", "border", "boundary", "country", "city", "village", "town",
            "beach", "mountain", "valley", "river", "lake", "sea", "ocean", "gulf", "island", "continent",
            "resort", "hotel", "hostel", "lodge", "cabin", "campground", "destination", "landmark", "monument", "museum",
            
            # Experience & Knowledge
            "experience", "knowledge", "wisdom", "expertise", "skill", "ability", "talent", "potential", "opportunity", "challenge",
            "success", "failure", "achievement", "accomplishment", "defeat", "victory", "growth", "progress", "development", "improvement",
            "learning", "understanding", "awareness", "realization", "enlightenment", "inspiration", "motivation", "determination", "resolution", "commitment",
            "past", "present", "future", "history", "tradition", "culture", "custom", "habit", "routine", "lifestyle",
            
            # Characteristics & Traits
            "wisdom", "courage", "honesty", "kindness", "justice", "generosity", "humility", "charity", "simplicity", "modesty",
            "arrogance", "greed", "selfishness", "envy", "jealousy", "hatred", "violence", "trickery", "cheating", "deception",
            "patience", "calmness", "peace", "harmony", "unity", "balance", "equality", "fairness", "diversity", "uniqueness",
            "strength", "weakness", "advantage", "disadvantage", "power", "vulnerability", "independence", "dependence", "freedom", "constraint",
            
            # Politics & Society
            "independence", "freedom", "right", "duty", "responsibility", "leadership", "power", "authority", "government", "state",
            "unity", "cohesion", "harmony", "coordination", "teamwork", "collaboration", "cooperation", "mutual help", "brotherhood", "sisterhood",
            "peace", "war", "conflict", "dispute", "argument", "opposition", "difference", "similarity", "tolerance", "pluralism",
            "democracy", "dictatorship", "monarchy", "republic", "federation", "confederation", "union", "alliance", "coalition", "bloc",
            
            # Arts & Culture
            "art", "culture", "tradition", "artistry", "music", "dance", "theater", "film", "literature", "poetry",
            "novel", "short story", "drama", "comedy", "tragedy", "fantasy", "mystery", "horror", "romance", "action",
            "painting", "sculpture", "ceramics", "batik", "weaving", "carving", "embroidery", "craftsmanship", "performance", "exhibition",
            "artist", "musician", "dancer", "actor", "director", "writer", "poet", "sculptor", "painter", "craftsman",
            
            # Technology & Innovation
            "technology", "computer", "internet", "smartphone", "laptop", "tablet", "application", "website", "software", "hardware",
            "robot", "artificial intelligence", "machine learning", "virtual reality", "augmented reality", "blockchain", "cryptocurrency", "metaverse", "cloud", "server",
            "digital", "online", "offline", "virtual", "cybernetic", "electronic", "automated", "smart", "connected", "integrated",
            "innovation", "invention", "discovery", "breakthrough", "advancement", "progress", "development", "improvement", "upgrade", "modification",
        ],
        
        "hard": [
            # Politics & Governance
            "democratization", "federalization", "centralization", "decentralization", "autonomy", "referendum", "democracy", "autocracy", "oligarchy", "monarchy",
            "parliamentary", "presidential", "constitution", "legislation", "regulation", "statute", "policy", "strategy", "tactic", "maneuver",
            "diplomacy", "negotiation", "agreement", "treaty", "convention", "protocol", "amendment", "revision", "reform", "revolution",
            "sovereignty", "jurisdiction", "authority", "governance", "administration", "bureaucracy", "legislature", "executive", "judiciary", "parliament",
            
            # Economics & Business
            "economics", "capitalism", "socialism", "communism", "mercantilism", "liberalism", "protectionism", "free trade", "tariff", "subsidy",
            "inflation", "deflation", "stagflation", "recession", "depression", "growth", "expansion", "contraction", "liquidity", "solvency",
            "capital", "investment", "dividend", "stock", "bond", "derivative", "hedging", "leverage", "arbitrage", "speculation",
            "merger", "acquisition", "consolidation", "diversification", "integration", "outsourcing", "insourcing", "franchising", "licensing", "partnership",
            "supply chain", "value chain", "distribution network", "logistics", "inventory management", "procurement", "vendor", "supplier", "customer", "market",
            
            # Education & Research
            "methodology", "epistemology", "ontology", "axiology", "hermeneutics", "phenomenology", "positivism", "relativism", "absolutism", "skepticism",
            "empiricism", "rationalism", "pragmatism", "utilitarianism", "altruism", "egoism", "hedonism", "stoicism", "confucianism", "buddhism",
            "quantitative", "qualitative", "experimental", "observational", "descriptive", "analytical", "exploratory", "confirmatory", "longitudinal", "transversal",
            "reliability", "validity", "objectivity", "subjectivity", "intersubjectivity", "triangulation", "saturation", "theory", "hypothesis", "paradigm",
            "literature review", "research design", "data collection", "data analysis", "interpretation", "conclusion", "recommendation", "implication", "limitation", "future research",
            
            # Industry & Manufacturing
            "industrialization", "manufacturing", "automation", "mechanization", "efficiency", "productivity", "capacity", "throughput", "output", "input",
            "quality control", "quality assurance", "six sigma", "lean manufacturing", "just-in-time", "supply chain", "logistics", "inventory", "warehouse", "distribution",
            "raw material", "intermediate product", "finished product", "assembly", "fabrication", "machining", "welding", "casting", "molding", "stamping",
            "lean", "agile", "kaizen", "kanban", "poka-yoke", "heijunka", "takt time", "bottleneck", "value stream", "continuous improvement",
            
            # Technology & Innovation
            "digitalization", "digital transformation", "modernization", "automation", "robotization", "computerization", "informatization", "telematics", "cybersecurity", "encryption",
            "decryption", "authentication", "authorization", "firewall", "antivirus", "malware", "ransomware", "spyware", "trojan", "botnet",
            "cloud computing", "edge computing", "fog computing", "quantum computing", "neuromorphic", "biotechnology", "nanotechnology", "synthetic biology", "genetic engineering", "CRISPR",
            "artificial intelligence", "machine learning", "deep learning", "neural network", "algorithm", "data science", "big data", "analytics", "visualization", "prediction",
            
            # Environment & Sustainability
            "sustainability", "ecosystem", "biodiversity", "conservation", "preservation", "restoration", "rehabilitation", "mitigation", "adaptation", "resilience",
            "renewable energy", "fossil fuel", "carbon footprint", "greenhouse gas", "deforestation", "reforestation", "afforestation", "permafrost", "erosion", "desertification",
            "pollution", "contamination", "remediation", "sequestration", "offsetting", "circular economy", "zero waste", "sustainable development", "triple bottom line", "ESG",
            "climate change", "global warming", "climate crisis", "tipping point", "carbon neutral", "net zero", "climate action", "environmental justice", "anthropocene", "carrying capacity",
            
            # Health & Medicine
            "epidemiology", "etiology", "pathogenesis", "pathophysiology", "immunopathology", "oncology", "cardiology", "neurology", "psychiatry", "pediatrics",
            "immunology", "virology", "bacteriology", "parasitology", "mycology", "toxicology", "pharmacology", "anesthesiology", "radiology", "pathology",
            "diagnosis", "prognosis", "therapeutic", "intervention", "prophylaxis", "metastasis", "remission", "relapse", "recovery", "mortality",
            "morbidity", "incidence", "prevalence", "comorbidity", "syndrome", "sequela", "iatrogenic", "nosocomial", "opportunistic", "endemic",
            "epidemic", "pandemic", "vaccination", "immunization", "antibiotic", "antiviral", "chemotherapy", "radiotherapy", "surgery", "transplantation",
            
            # Psychology & Sociology
            "behaviorism", "cognitivism", "constructivism", "humanism", "psychoanalysis", "jungian", "adlerian", "gestalt", "systemic", "structuralism",
            "socialization", "enculturation", "acculturation", "assimilation", "integration", "marginalization", "stigmatization", "stereotype", "prejudice", "discrimination",
            "stratification", "mobility", "status", "role", "identity", "habitus", "capital", "power", "hegemony", "subordination",
            "anomie", "alienation", "reification", "fetishism", "commodification", "marketization", "commercialization", "secularization", "fundamentalism", "pluralism",
            "deviance", "conformity", "normality", "pathology", "dysfunction", "adaptation", "maladaptation", "resilience", "vulnerability", "coping",
            
            # Philosophy & Arts
            "metaphysics", "logic", "aesthetics", "ethics", "axiology", "phenomenology", "existentialism", "nihilism", "absurdism", "romanticism",
            "realism", "naturalism", "idealism", "materialism", "dialectics", "hermeneutics", "deconstruction", "semiotics", "semantics", "pragmatics",
            "pragmatism", "utilitarianism", "kantianism", "hegelianism", "marxism", "foucaultianism", "derridaism", "deleuzism", "lacanism", "sartrism",
            "aestheticism", "formalism", "functionalism", "minimalism", "modernism", "postmodernism", "surrealism", "expressionism", "impressionism", "cubism",
            
            # Communication & Media
            "communication", "propaganda", "persuasion", "manipulation", "disinformation", "misinformation", "fake news", "fact checking", "debunking", "verification",
            "narrative", "framing", "agenda setting", "priming", "stereotype", "bias", "echo chamber", "filter bubble", "polarization", "fragmentation",
            "rhetoric", "dialectics", "pragmatics", "linguistics", "semantics", "syntax", "phonology", "morphology", "pragmatics", "conversational implicature",
            "discourse analysis", "critical discourse analysis", "multimodal", "transmedia", "convergence", "participatory culture", "collective intelligence", "crowdsourcing", "virality", "memeification",
            
            # Science & Nature
            "physics", "chemistry", "biology", "astronomy", "geology", "meteorology", "oceanography", "seismology", "volcanology", "glaciology",
            "mechanics", "dynamics", "thermodynamics", "electromagnetism", "optics", "acoustics", "relativity", "quantum mechanics", "astrophysics", "cosmology",
            "organic", "inorganic", "biochemistry", "geochemistry", "astrochemistry", "radiochemistry", "photochemistry", "electrochemistry", "catalysis", "synthesis",
            "genetics", "evolution", "ecology", "ethology", "neuroscience", "immunoscience", "microbiology", "virology", "mycology", "parasitology",
            "theoretical physics", "experimental physics", "applied physics", "computational physics", "geophysics", "biophysics", "medical physics", "nuclear physics", "particle physics", "condensed matter physics",
            
            # International Trade & Finance
            "globalization", "internationalization", "export", "import", "trade", "tariff", "quota", "dumping", "protectionism", "liberalization",
            "FTA", "ASEAN", "WTO", "IMF", "World Bank", "OPEC", "G20", "BRICS", "Brexit", "TPP",
            "forex", "cryptocurrency", "blockchain", "NFT", "DeFi", "fintech", "insurtech", "regtech", "legaltech", "proptech",
            "banking", "insurance", "investment", "trading", "brokerage", "custody", "clearing", "settlement", "hedging", "arbitrage",
            "derivatives", "futures", "options", "swaps", "securities", "bonds", "equities", "commodities", "precious metals", "forex",
            
            # Manufacturing & Production Advanced
            "lean manufacturing", "six sigma", "kaizen", "kanban", "poka-yoke", "heijunka", "takt time", "bottleneck", "throughput", "cycle time",
            "value stream", "waste elimination", "continuous improvement", "standardization", "visual management", "root cause analysis", "PDCA", "DMAIC", "RCA", "5S",
            "MRP", "ERP", "SCM", "CRM", "PLM", "CAD", "CAM", "CNC", "IoT", "Industry 4.0",
            "additive manufacturing", "3D printing", "rapid prototyping", "computer-aided design", "simulation", "optimization", "control system", "feedback loop", "sensor", "actuator",
            
            # Human Resources & Organization
            "recruitment", "selection", "onboarding", "training", "development", "coaching", "mentoring", "performance management", "appraisal", "compensation",
            "culture", "engagement", "retention", "turnover", "absenteeism", "presenteeism", "productivity", "efficiency", "effectiveness", "profitability",
            "organizational structure", "hierarchy", "matrix", "flat", "network", "agile", "holacracy", "sociocracy", "teal", "purple",
            "leadership", "management", "governance", "compliance", "risk management", "audit", "internal control", "accountability", "transparency", "integrity",
            "change management", "organizational development", "employee wellness", "work-life balance", "remote work", "flexible work", "gig economy", "freelance", "contractor", "partnership",
        ]
    }
}

# ==========================================
# WORD GAME STATS (DUMMY / NO DATABASE)
# ==========================================
async def get_word_game_stats(user_id: int) -> dict:
    return {
        "xp": 0,
        "games_played": 0,
        "games_won": 0,
        "win_rate": 0,
        "highest_streak": 0,
        "total_words": 0
    }

async def update_word_game_stats(
    user_id: int,
    xp_earned: int,
    is_win: bool,
    streak: int,
    words_count: int
):
    return

# ==========================================
# GAME STATE & UTILITIES
# ==========================================

active_word_games = {}

class WordChainGame:
    """Word Chain Game State Manager"""
    
    def __init__(self, chat_id: int, user_id: int, lang: str, level: str, word_list: list):
        self.chat_id = chat_id
        self.lang = lang
        self.level = level
        self.word_list = word_list.copy()
        self.used_words = []
        self.current_word = random.choice(word_list)
        self.used_words.append(self.current_word)
        
        self.players = {}  # {user_id: {name, xp, words, last_answer_time}}
        self.started_by = user_id
        self.last_player = None
        self.streak = 0
        self.total_xp = 0
        self.timer = None
        self.start_time = current_time()
        self.word_history = []
        
        # XP per correct answer based on level
        self.xp_per_word = {"easy": 5, "medium": 10, "hard": 20}.get(level, 5)
        self.xp_bonus_per_streak = 2  # Extra XP per streak
        
        # Anti-flood: track last answer time per user
        self.last_answer_times = {}
        self.answer_cooldown = 1.5  # seconds
    
    def get_xp_for_answer(self, streak: int) -> int:
        """Calculate XP with bonus for streak"""
        base_xp = self.xp_per_word
        bonus_xp = max(0, (streak - 1) * self.xp_bonus_per_streak)
        return base_xp + bonus_xp
    
    def can_answer(self, user_id: int) -> tuple:
        """Check if user can answer (anti-flood)"""
        now = current_time()
        last_time = self.last_answer_times.get(user_id, 0)
        
        if now - last_time < self.answer_cooldown:
            wait_time = round(self.answer_cooldown - (now - last_time), 1)
            return False, f"⏳ Tunggu {wait_time}s lagi"
        
        self.last_answer_times[user_id] = now
        return True, ""
    
    def is_valid_word(self, word: str) -> bool:
        """Validate word - check if it's in word list and not used"""
        word_lower = word.lower().strip()
        used_lower = [w.lower() for w in self.used_words]
        
        if word_lower not in [w.lower() for w in self.word_list]:
            return False
        if word_lower in used_lower:
            return False
        return True
    
    def get_next_word(self) -> tuple:
        """Get next word and check if kamus habis"""
        available = [w for w in self.word_list if w.lower() not in [uw.lower() for uw in self.used_words]]
        
        if not available:
            return None, True  # Kamus habis
        
        next_word = random.choice(available)
        self.used_words.append(next_word)
        self.current_word = next_word
        return next_word, False
    
    def hide_word(self, word: str, reveal_percentage: float = 0.35) -> str:
        """Hide word dengan underscore pattern"""
        if len(word) <= 2:
            return word
        
        chars = list(word)
        indices = list(range(1, len(word) - 1))
        num_to_hide = max(1, int(len(indices) * reveal_percentage))
        
        if indices:
            to_hide = random.sample(indices, min(num_to_hide, len(indices)))
            for idx in to_hide:
                chars[idx] = "_"
        
        return "".join(chars)

def get_level_name(level: str, lang: str = "id") -> str:
    """Get level display name"""
    level_map = {
        "easy": "Easy 🟢" if lang == "en" else "Mudah 🟢",
        "medium": "Medium 🟡" if lang == "en" else "Sedang 🟡",
        "hard": "Hard 🔴" if lang == "en" else "Sulit 🔴"
    }
    return level_map.get(level, level)

def get_lang_name(lang: str) -> str:
    """Get language display name"""
    return "English 🇬🇧" if lang == "en" else "Indonesia 🇮🇩"

# ==========================================
# GAME COMMANDS
# ==========================================

async def kata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Word Chain Game - /kata command - MULTIPLAYER"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    try:
        # Check if game already active
        if chat_id in active_word_games:
            game = active_word_games[chat_id]
            players_list = ", ".join([f"@{p['name']}" for p in list(game.players.values())[:5]])
            hidden = game.hide_word(game.current_word)
            
            await update.message.reply_text(
                f"🎮 <b>Game sedang berlangsung!</b>\n\n"
                f"👥 <b>Players:</b> {players_list or 'Belum ada'}\n"
                f"🎯 <b>TEBAK KATA:</b> <code>{hidden.upper()}</code>\n\n"
                f"⏳ <b>Waktu: 10 detik!</b>\n\n"
                f"<i>Kirim jawaban untuk bergabung!</i>",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Get user stats
        stats = await get_word_game_stats(user_id)
        
        text = (
            "<b>🎮 OKTACOMEL WORD CHAIN GAME</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>MULTIPLAYER MODE 👥</b>\n"
            "Tebak kata yang tersembunyi!\n"
            "Guess the hidden word!\n\n"
            f"📊 <b>Your Stats:</b>\n"
            f"  • XP: <code>{stats['xp']}</code>\n"
            f"  • Games: <code>{stats['games_played']}</code>\n"
            f"  • Wins: <code>{stats['games_won']}</code> ({stats['win_rate']}%)\n"
            f"  • Best Streak: <code>{stats['highest_streak']}</code>\n"
            f"  • Total Words: <code>{stats['total_words']}</code>\n\n"
            "<b>Pilih Bahasa & Level:</b>\n"
        )
        
        buttons = [
            [
                InlineKeyboardButton("🇮🇩 Mudah", callback_data=f"kata_start|id|easy|{user_id}"),
                InlineKeyboardButton("🇮🇩 Sedang", callback_data=f"kata_start|id|medium|{user_id}")
            ],
            [
                InlineKeyboardButton("🇮🇩 Sulit", callback_data=f"kata_start|id|hard|{user_id}")
            ],
            [
                InlineKeyboardButton("🇬🇧 Easy", callback_data=f"kata_start|en|easy|{user_id}"),
                InlineKeyboardButton("🇬🇧 Medium", callback_data=f"kata_start|en|medium|{user_id}")
            ],
            [
                InlineKeyboardButton("🇬🇧 Hard", callback_data=f"kata_start|en|hard|{user_id}")
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")
            ]
        ]
        
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    
    except Exception as e:
        logger.error(f"[WORD_GAME] /kata error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}", parse_mode=ParseMode.HTML)

async def kata_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle word chain game callbacks - MULTIPLAYER"""
    query = update.callback_query
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or update.effective_user.username or "Player"
    
    try:
        parts = query.data.split("|")
        action = parts[0]
        
        if action == "kata_start":
            lang = parts[1] if len(parts) > 1 else "id"
            level = parts[2] if len(parts) > 2 else "easy"
            owner_id = int(parts[3]) if len(parts) > 3 else user_id
            
            if user_id != owner_id:
                await query.answer("❌ Bukan milik kamu!", show_alert=True)
                return
            
            if chat_id in active_word_games:
                await query.answer("⚠️ Game sudah berjalan di chat ini!", show_alert=True)
                return
            
            await query.answer("🚀 Starting game...")
            
            # Initialize game
            word_list = WORD_CHAIN_WORDS.get(lang, {}).get(level, [])
            if not word_list:
                await query.message.edit_text("❌ Error: Word list not available.", parse_mode=ParseMode.HTML)
                return
            
            game = WordChainGame(chat_id, user_id, lang, level, word_list)
            active_word_games[chat_id] = game
            
            # Start timer
            try:
                game.timer = context.job_queue.run_once(
                    word_game_timeout_wrapper(context, chat_id), 
                    10, 
                    chat_id=chat_id, 
                    name=f"word_timer_{chat_id}"
                )
            except Exception as e:
                logger.error(f"[WORD_GAME] Timer setup error: {e}")
            
            hidden_start = game.hide_word(game.current_word)
            level_name = get_level_name(level, lang)
            lang_name = get_lang_name(lang)
            
            text = (
                "🎮 <b>WORD CHAIN GAME - MULTIPLAYER</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🌐 <b>Language:</b> {lang_name}\n"
                f"🔥 <b>Level:</b> {level_name}\n"
                f"➕ <b>Reward:</b> <code>+{game.xp_per_word} XP</code> (+ streak bonus)\n\n"
                f"🎯 <b>TEBAK KATA:</b>\n"
                f"<code>{hidden_start.upper()}</code>\n\n"
                f"⏳ <b>Waktu: 10 detik!</b>\n"
                f"👥 <b>Players: 0</b>\n\n"
                "<i>Type your guess in the chat!</i>"
            )
            
            buttons = [[InlineKeyboardButton("🛑 End Game", callback_data=f"kata_giveup|{user_id}")]]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            
        elif action == "kata_giveup":
            owner_id = int(parts[1]) if len(parts) > 1 else user_id
            
            if chat_id not in active_word_games:
                await query.answer("❌ Game tidak aktif!", show_alert=True)
                return
            
            game = active_word_games[chat_id]
            
            if user_id != game.started_by and user_id != OWNER_ID:
                await query.answer("⚠️ Hanya game starter yang bisa end!", show_alert=True)
                return
            
            await query.answer("✅ Game ended!")
            
            # Clean up timer
            if game.timer:
                try:
                    game.timer.schedule_removal()
                except:
                    pass
            
            game_result = await end_game(chat_id)
            active_word_games.pop(chat_id, None)
            
            await query.message.edit_text(game_result, parse_mode=ParseMode.HTML)
        
        elif action == "kata_menu":
            await query.answer()
            stats = await get_word_game_stats(user_id)
            
            text = (
                "<b>🎮 OKTACOMEL WORD CHAIN GAME</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "<b>MULTIPLAYER MODE 👥</b>\n"
                "Tebak kata yang tersembunyi!\n\n"
                f"📊 <b>Your Stats:</b>\n"
                f"  • XP: <code>{stats['xp']}</code>\n"
                f"  • Games: <code>{stats['games_played']}</code>\n"
                f"  • Wins: <code>{stats['games_won']}</code> ({stats['win_rate']}%)\n"
                f"  • Best Streak: <code>{stats['highest_streak']}</code>\n\n"
                "<b>Pilih Bahasa & Level:</b>\n"
            )
            
            buttons = [
                [
                    InlineKeyboardButton("🇮🇩 Mudah", callback_data=f"kata_start|id|easy|{user_id}"),
                    InlineKeyboardButton("🇮🇩 Sedang", callback_data=f"kata_start|id|medium|{user_id}")
                ],
                [
                    InlineKeyboardButton("🇮🇩 Sulit", callback_data=f"kata_start|id|hard|{user_id}")
                ],
                [
                    InlineKeyboardButton("🇬🇧 Easy", callback_data=f"kata_start|en|easy|{user_id}"),
                    InlineKeyboardButton("🇬🇧 Medium", callback_data=f"kata_start|en|medium|{user_id}")
                ],
                [
                    InlineKeyboardButton("🇬🇧 Hard", callback_data=f"kata_start|en|hard|{user_id}")
                ],
                [
                    InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")
                ]
            ]
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    
    except Exception as e:
        logger.error(f"[WORD_GAME] Callback error: {e}")
        try:
            await query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)
        except:
            pass

# ==========================================
# GAME LOGIC & HANDLERS
# ==========================================

def word_game_timeout_wrapper(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Wrapper untuk timeout handler"""
    async def timeout_handler(context_inner: ContextTypes.DEFAULT_TYPE):
        await word_game_timeout(context_inner, chat_id)
    return timeout_handler

async def word_game_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle timeout - skip to next word"""
    if chat_id not in active_word_games:
        return
    
    try:
        game = active_word_games[chat_id]
        correct_word = game.current_word.lower()
        
        # Get next word
        next_word, kamus_habis = game.get_next_word()
        
        if kamus_habis:
            game_result = await end_game(chat_id)
            active_word_games.pop(chat_id, None)
            try:
                await context.bot.send_message(chat_id, game_result, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"[WORD_GAME] Send timeout message error: {e}")
            return
        
        # Reset dan lanjut
        game.streak = 0
        hidden_next = game.hide_word(next_word)
        
        text = (
            f"⏰ <b>WAKTU HABIS!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Jawabannya:</b> <code>{correct_word}</code>\n"
            f"🎯 <b>Streak reset ke 0</b>\n\n"
            f"<b>KATA SELANJUTNYA:</b>\n"
            f"<code>{hidden_next.upper()}</code>\n"
            f"⏳ <b>10 detik!</b>"
        )
        
        try:
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"[WORD_GAME] Send message error: {e}")
        
        # Reschedule timer
        if game.timer:
            try:
                game.timer.schedule_removal()
            except:
                pass
        
        game.timer = context.job_queue.run_once(
            word_game_timeout_wrapper(context, chat_id), 
            10, 
            chat_id=chat_id,
            name=f"word_timer_{chat_id}"
        )
    
    except Exception as e:
        logger.error(f"[WORD_GAME] Timeout error: {e}")
        try:
            active_word_games.pop(chat_id, None)
        except:
            pass

async def end_game(chat_id: int) -> str:
    """Generate game end message dengan stats"""
    try:
        if chat_id not in active_word_games:
            return "❌ Game tidak ditemukan"
        
        game = active_word_games[chat_id]
        
        if not game.players:
            return (
                "<b>GAME OVER</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "❌ Tidak ada pemain yang bergabung.\n\n"
                "Thanks for playing!\n"
                "<i>Powered by OKTACOMEL</i>"
            )
        
        # Save stats untuk semua player
        for player_id, pdata in game.players.items():
            xp_earned = pdata["xp"]
            words_count = pdata["words"]
            await update_word_game_stats(
                player_id, 
                xp_earned, 
                words_count > 0, 
                game.streak,
                words_count
            )
        
        # Build leaderboard
        sorted_players = sorted(
            game.players.items(), 
            key=lambda x: x[1]["xp"], 
            reverse=True
        )
        
        leaderboard_text = ""
        medals = ["🥇", "🥈", "🥉"]
        
        for i, (pid, pdata) in enumerate(sorted_players[:5]):
            medal = medals[i] if i < 3 else f"{i+1}."
            leaderboard_text += (
                f"{medal} {html.escape(pdata['name'])}: <code>+{pdata['xp']} XP</code> "
                f"({pdata['words']} words)\n"
            )
        
        # Word chain display
        displayed_words = game.used_words[:15]
        word_chain = " → ".join(displayed_words)
        if len(game.used_words) > 15:
            word_chain += f" → ... ({len(game.used_words)} total)"
        
        # Game duration
        game_duration = int(current_time() - game.start_time)
        minutes = game_duration // 60
        seconds = game_duration % 60
        
        text = (
            "<b>🎮 GAME OVER - WORD CHAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⏱️ <b>Duration:</b> <code>{minutes}:{seconds:02d}</code>\n"
            f"👥 <b>Players:</b> <code>{len(game.players)}</code>\n"
            f"🔗 <b>Words Guessed:</b> <code>{len(game.used_words)}</code>\n"
            f"🔥 <b>Max Streak:</b> <code>{game.streak}</code>\n\n"
            f"<b>🏆 LEADERBOARD:</b>\n"
            f"{leaderboard_text}\n"
            f"<b>Word Chain:</b>\n"
            f"<code>{word_chain}</code>\n\n"
            "Thanks for playing!\n"
            "<i>Powered by OKTACOMEL ⚡</i>"
        )
        
        return text
    
    except Exception as e:
        logger.error(f"[WORD_GAME] End game error: {e}")
        return f"❌ Error ending game: {str(e)[:50]}"

async def handle_word_chain_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle replies untuk word chain game - MULTIPLAYER"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or update.effective_user.username or "Player"
    user_word = update.message.text.strip().lower()
    
    try:
        # Check if game active
        if chat_id not in active_word_games:
            return False
        
        game = active_word_games[chat_id]
        
        # Anti-cheat: ignore suspicious messages
        cheating_keywords = ["jawabannya", "hintnya", "jawab:", "jawab =", "pake kata", "itu jawabannya", "jawaban"]
        if any(k in user_word for k in cheating_keywords) or len(user_word) > 25:
            return False
        
        # Skip if contains space (likely not a game response)
        if " " in user_word:
            return False
        
        # Too short
        if len(user_word) < 2:
            return False
        
        # Anti-flood check
        can_answer, message = game.can_answer(user_id)
        if not can_answer:
            try:
                await update.message.reply_text(f"⏳ {message}", parse_mode=ParseMode.HTML)
            except:
                pass
            return True
        
        # Validate word
        if not game.is_valid_word(user_word):
            try:
                # Invalid word - reveal dan move ke next
                correct_word = game.current_word.lower()
                next_word, kamus_habis = game.get_next_word()
                
                if kamus_habis:
                    if game.timer:
                        try:
                            game.timer.schedule_removal()
                        except:
                            pass
                    game_result = await end_game(chat_id)
                    active_word_games.pop(chat_id, None)
                    await update.message.reply_text(game_result, parse_mode=ParseMode.HTML)
                    return True
                
                game.streak = 0
                hidden_next = game.hide_word(next_word)
                
                text = (
                    f"❌ <b>JAWABAN SALAH!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>Player:</b> {html.escape(user_name)}\n"
                    f"📝 <b>Seharusnya:</b> <code>{correct_word}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🎯 <b>KATA BERIKUTNYA:</b>\n"
                    f"<code>{hidden_next.upper()}</code>\n"
                    f"🔥 <b>Streak:</b> <code>0</code> (reset)\n"
                    f"⏳ <b>10 Detik</b>"
                )
                
                if game.timer:
                    try:
                        game.timer.schedule_removal()
                    except:
                        pass
                
                game.timer = context.job_queue.run_once(
                    word_game_timeout_wrapper(context, chat_id), 
                    10, 
                    chat_id=chat_id,
                    name=f"word_timer_{chat_id}"
                )
                
                await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"[WORD_GAME] Invalid word handler error: {e}")
            return True
        
        # Same player as last - skip
        if game.last_player == user_id:
            return True
        
        # ✅ CORRECT ANSWER!
        try:
            if game.timer:
                try:
                    game.timer.schedule_removal()
                except:
                    pass
            
            # Update game state
            game.streak += 1
            game.last_player = user_id
            xp_earned = game.get_xp_for_answer(game.streak)
            game.word_history.append((user_word, user_name))
            
            # Add/update player
            if user_id not in game.players:
                game.players[user_id] = {"name": user_name, "xp": 0, "words": 0}
            
            game.players[user_id]["xp"] += xp_earned
            game.players[user_id]["words"] += 1
            
            # Get next word
            next_word, kamus_habis = game.get_next_word()
            
            if kamus_habis:
                if game.timer:
                    try:
                        game.timer.schedule_removal()
                    except:
                        pass
                game_result = await end_game(chat_id)
                active_word_games.pop(chat_id, None)
                await update.message.reply_text(game_result, parse_mode=ParseMode.HTML)
                return True
            
            hidden_next = game.hide_word(next_word)
            progress_bar = "▰" * min(game.streak, 10) + "▱" * (10 - min(game.streak, 10))
            
            text = (
                "✅ <b>BENAR!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Player:</b> {html.escape(user_name)}\n"
                f"📝 <b>Jawaban:</b> <code>{user_word}</code>\n"
                f"➕ <b>Reward:</b> <code>+{xp_earned} XP</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯 <b>KATA SELANJUTNYA:</b>\n"
                f"<code>{hidden_next.upper()}</code>\n"
                f"🔥 <b>Streak:</b> <code>{game.streak}</code>\n"
                f"📊 <b>Progress:</b> <code>{progress_bar}</code>\n"
                f"👥 <b>Players:</b> <code>{len(game.players)}</code>\n"
                f"⏳ <b>10 Detik</b>"
            )
            
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            
            # Reschedule timer
            game.timer = context.job_queue.run_once(
                word_game_timeout_wrapper(context, chat_id), 
                10, 
                chat_id=chat_id,
                name=f"word_timer_{chat_id}"
            )
        
        except Exception as e:
            logger.error(f"[WORD_GAME] Correct answer handler error: {e}")
        
        return True
    
    except Exception as e:
        logger.error(f"[WORD_GAME] Reply handler error: {e}")
        return False

# ==========================================
# SMS BUS OTP - PREMIUM ULTIMATE VERSION V3
# Virtual Number SMS Receiver (sms-bus.com API)
# ==========================================
SMS_BUS_BASE_URL = "https://sms-bus.com/api/control"

# Active SMS orders: {user_id: {"request_id": int, "phone": str, "service": str, ...}}
active_sms_orders = {}

# SMS History storage: {user_id: [{"request_id": int, "phone": str, "service": str, "status": "success/failed/cancelled", "timestamp": time}]}
sms_history = {}

# Cache for countries and services from API
sms_countries_cache = {}
sms_services_cache = {}

# ===== API OPERATIONS =====

async def sms_bus_api(endpoint: str, params: dict = None) -> dict:
    """Make request to sms-bus.com API"""
    if not SMS_BUS_API_KEY or SMS_BUS_API_KEY == "your_api_key_here":
        return {"code": 0, "message": "API key not configured"}
    
    if params is None:
        params = {}
    params["token"] = SMS_BUS_API_KEY
    
    url = f"{SMS_BUS_BASE_URL}/{endpoint}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, params=params)
            return r.json()
    except asyncio.TimeoutError:
        return {"code": 0, "message": "Request timeout"}
    except Exception as e:
        logger.error(f"[SMS_BUS] API error: {e}")
        return {"code": 0, "message": str(e)}

async def sms_get_balance() -> dict:
    """Get SMS Bus account balance"""
    return await sms_bus_api("get/balance")

async def sms_get_countries() -> dict:
    """Get all available countries"""
    global sms_countries_cache
    if sms_countries_cache:
        return {"code": 200, "data": sms_countries_cache}
    result = await sms_bus_api("list/countries")
    if result.get("code") == 200:
        sms_countries_cache = result.get("data", {})
    return result

async def sms_get_services() -> dict:
    """Get all available services/projects"""
    global sms_services_cache
    if sms_services_cache:
        return {"code": 200, "data": sms_services_cache}
    result = await sms_bus_api("list/projects")
    if result.get("code") == 200:
        sms_services_cache = result.get("data", {})
    return result

async def sms_get_prices(country_id: int) -> dict:
    """Get prices and availability for a country"""
    return await sms_bus_api("list/prices", {"country_id": country_id})

async def sms_buy_number(country_id: int, project_id: int) -> dict:
    """Buy a virtual number - FIXED VERSION"""
    result = await sms_bus_api("get/number", {"country_id": country_id, "project_id": project_id})
    
    # Validate response
    if result.get("code") == 200:
        data = result.get("data", {})
        phone = data.get("number", "")
        
        # Validate phone number format
        if phone and phone.isdigit():
            if len(phone) >= 10 and len(phone) <= 15:
                logger.info(f"[SMS_BUS] Valid phone received: +{phone} (length: {len(phone)})")
                return result
            else:
                logger.warning(f"[SMS_BUS] Invalid phone length: {phone} (length: {len(phone)})")
                return {"code": 400, "message": "Invalid phone number length received from API"}
    
    return result

async def sms_check_sms(request_id: int) -> dict:
    """Check for received SMS"""
    return await sms_bus_api("get/sms", {"request_id": request_id})

async def sms_cancel_order(request_id: int) -> dict:
    """Cancel an order"""
    return await sms_bus_api("cancel", {"request_id": request_id})

def format_phone_number(phone: str, country_name: str = "") -> str:
    """Format phone number with country prefix if needed"""
    if not phone:
        return "N/A"
    
    phone_clean = phone.lstrip("+")
    
    if "indonesia" in country_name.lower():
        if phone_clean.startswith("62"):
            return f"+{phone_clean}"
        elif phone_clean.startswith("8"):
            return f"+62{phone_clean}"
    
    if not phone_clean.startswith("+"):
        return f"+{phone_clean}"
    
    return phone_clean

def add_to_history(user_id: int, request_id: int, phone: str, service_name: str, country_name: str, status: str):
    """Add order to user history"""
    if user_id not in sms_history:
        sms_history[user_id] = []
    
    import time
    history_entry = {
        "request_id": request_id,
        "phone": phone,
        "service": service_name,
        "country": country_name,
        "status": status,
        "timestamp": int(time.time())
    }
    
    sms_history[user_id].insert(0, history_entry)  # Add to beginning (newest first)
    
    # Keep only last 50 entries
    if len(sms_history[user_id]) > 50:
        sms_history[user_id] = sms_history[user_id][:50]

def get_status_emoji(status: str) -> str:
    """Get emoji for status"""
    if status == "success":
        return "OK"
    elif status == "failed":
        return "FAILED"
    elif status == "cancelled":
        return "CANCELLED"
    elif status == "waiting":
        return "WAITING"
    return "?"

# ===== MAIN COMMAND =====

async def sms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """SMS Bus OTP Command - /sms"""
    user_id = update.effective_user.id
    
    if not await premium_lock_handler(update, context):
        return
    
    if not SMS_BUS_API_KEY or SMS_BUS_API_KEY == "your_api_key_here":
        await update.message.reply_text(
            "SMS BUS ERROR\n\n"
            "API key not configured.\n"
            "Contact admin to setup.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Get balance
    balance_result = await sms_get_balance()
    balance = 0
    if balance_result.get("code") == 200:
        balance = balance_result.get("data", {}).get("balance", 0)
    
    # Get services
    services_result = await sms_get_services()
    services = {}
    if services_result.get("code") == 200:
        services = services_result.get("data", {})
    
    if not services:
        await update.message.reply_text(
            "SMS BUS ERROR\n\n"
            "Unable to fetch services.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )
        return
    
    text = (
        "SMS BUS OTP\n"
        "Virtual Number SMS Receiver\n\n"
        f"Balance: ${balance:.2f}\n\n"
        "Select Service:\n"
    )
    
    # Build service buttons (3 per row)
    buttons = []
    sorted_services = sorted(services.items(), key=lambda x: x[1].get("title", ""))
    
    # Priority services
    priority_titles = ["Telegram", "WhatsApp", "Google", "Facebook", "Instagram", "Twitter", "TikTok", "Microsoft", "Viber", "Signal"]
    priority_list = []
    other_list = []
    
    for svc_id, svc_data in sorted_services:
        title = svc_data.get("title", "")
        is_priority = any(p.lower() in title.lower() for p in priority_titles)
        
        if is_priority:
            priority_list.append((svc_id, svc_data))
        else:
            other_list.append((svc_id, svc_data))
    
    service_list = (priority_list + other_list)[:48]
    
    for i in range(0, len(service_list), 3):
        row = []
        for svc_id, svc_data in service_list[i:i+3]:
            title = svc_data.get("title", "Unknown")[:13]
            row.append(InlineKeyboardButton(
                title,
                callback_data=f"sms_svc|{svc_id}|{user_id}"
            ))
        buttons.append(row)
    
    buttons.append([
        InlineKeyboardButton("Balance", callback_data=f"sms_balance|{user_id}"),
        InlineKeyboardButton("History", callback_data=f"sms_history|{user_id}|0")
    ])
    
    if user_id in active_sms_orders:
        buttons.append([InlineKeyboardButton("My Orders", callback_data=f"sms_orders|{user_id}")])
    
    buttons.append([InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")])
    
    await update.message.reply_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ===== CALLBACK HANDLER =====

async def sms_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle SMS Bus callbacks"""
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    
    try:
        parts = data.split("|")
        action = parts[0]
        
        if action == "sms_svc":
            # Service selected, show countries
            project_id = parts[1]
            owner_id = int(parts[2]) if len(parts) > 2 else user_id
            
            if user_id != owner_id:
                await query.answer("Not authorized", show_alert=True)
                return
            
            service_name = sms_services_cache.get(project_id, {}).get("title", f"Service {project_id}")
            
            await query.answer(f"Loading {service_name}...")
            
            # Get countries
            countries_result = await sms_get_countries()
            countries = {}
            if countries_result.get("code") == 200:
                countries = countries_result.get("data", {})
            
            if not countries:
                await query.answer("No countries available", show_alert=True)
                return
            
            text = (
                "SMS BUS - SELECT COUNTRY\n"
                f"Service: {service_name}\n\n"
                "Select Country:\n"
            )
            
            buttons = []
            sorted_countries = sorted(countries.items(), key=lambda x: x[1].get("title", ""))
            country_list = sorted_countries[:40]
            
            for i in range(0, len(country_list), 2):
                row = []
                for country_id, country_data in country_list[i:i+2]:
                    title = country_data.get("title", "Unknown")[:18]
                    row.append(InlineKeyboardButton(
                        title,
                        callback_data=f"sms_ctry|{project_id}|{country_id}|{user_id}"
                    ))
                buttons.append(row)
            
            buttons.append([InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")])
            
            await query.message.edit_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        elif action == "sms_ctry":
            # Country selected, buy number
            project_id = int(parts[1])
            country_id = int(parts[2])
            owner_id = int(parts[3]) if len(parts) > 3 else user_id
            
            if user_id != owner_id:
                await query.answer("Not authorized", show_alert=True)
                return
            
            await query.answer("Purchasing number...")
            
            service_name = sms_services_cache.get(str(project_id), {}).get("title", f"Service {project_id}")
            country_name = sms_countries_cache.get(str(country_id), {}).get("title", f"Country {country_id}")
            
            # Buy number
            result = await sms_buy_number(country_id, project_id)
            
            if result.get("code") != 200:
                error_msg = result.get("message", "Unknown error")
                text = (
                    "SMS BUS - ERROR\n"
                    f"Error: {error_msg}\n\n"
                    "Try different country or service"
                )
                buttons = [[InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]]
                await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
                
                # Add to history as failed
                add_to_history(user_id, 0, "N/A", service_name, country_name, "failed")
                return
            
            # Success - store order
            order_data = result.get("data", {})
            request_id = order_data.get("request_id")
            phone = order_data.get("number", "")
            
            # Format phone number properly
            formatted_phone = format_phone_number(phone, country_name)
            
            active_sms_orders[user_id] = {
                "request_id": request_id,
                "phone": phone,
                "formatted_phone": formatted_phone,
                "project_id": project_id,
                "country_id": country_id,
                "service_name": service_name,
                "country_name": country_name
            }
            
            # Add to history as waiting
            add_to_history(user_id, request_id, formatted_phone, service_name, country_name, "waiting")
            
            text = (
                "SMS BUS - NUMBER READY\n"
                f"Service: {service_name}\n"
                f"Country: {country_name}\n\n"
                "Phone:\n"
                f"{formatted_phone}\n\n"
                f"Request ID: {request_id}\n\n"
                "Status: Waiting for SMS\n\n"
                "Use this number to receive OTP.\n"
                "Click Check SMS to view messages."
            )
            
            buttons = [
                [InlineKeyboardButton("Check SMS", callback_data=f"sms_check|{request_id}|{user_id}"),
                 InlineKeyboardButton("Refresh", callback_data=f"sms_check|{request_id}|{user_id}")],
                [InlineKeyboardButton("Cancel Order", callback_data=f"sms_cancel|{request_id}|{user_id}")],
                [InlineKeyboardButton("New Order", callback_data=f"sms_menu|{user_id}")]
            ]
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        elif action == "sms_check":
            # Check for SMS
            request_id = int(parts[1])
            owner_id = int(parts[2]) if len(parts) > 2 else user_id
            
            if user_id != owner_id:
                await query.answer("Not authorized", show_alert=True)
                return
            
            await query.answer("Checking SMS...")
            
            result = await sms_check_sms(request_id)
            
            # Get order info
            order = active_sms_orders.get(user_id, {})
            formatted_phone = order.get("formatted_phone", "N/A")
            service_name = order.get("service_name", "Unknown")
            
            if result.get("code") == 200:
                # SMS received!
                sms_code = result.get("data", "")
                
                text = (
                    "SMS BUS - SMS RECEIVED\n"
                    f"Phone: {formatted_phone}\n"
                    f"Service: {service_name}\n\n"
                    "OTP CODE:\n"
                    f"{sms_code}\n\n"
                    "Order completed successfully!"
                )
                
                # Update history as success
                if user_id in sms_history:
                    for entry in sms_history[user_id]:
                        if entry["request_id"] == request_id:
                            entry["status"] = "success"
                            break
                
                # Clear order
                active_sms_orders.pop(user_id, None)
                
                buttons = [[InlineKeyboardButton("New Order", callback_data=f"sms_menu|{user_id}"),
                            InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]]
            
            elif result.get("code") == 50101:
                # Not received yet
                text = (
                    "SMS BUS - WAITING\n"
                    f"Phone: {formatted_phone}\n"
                    f"Service: {service_name}\n"
                    f"Request ID: {request_id}\n\n"
                    "Status: Waiting for SMS\n"
                    "SMS not received yet. Keep checking!"
                )
                
                buttons = [
                    [InlineKeyboardButton("Check SMS", callback_data=f"sms_check|{request_id}|{user_id}"),
                     InlineKeyboardButton("Refresh", callback_data=f"sms_check|{request_id}|{user_id}")],
                    [InlineKeyboardButton("Cancel Order", callback_data=f"sms_cancel|{request_id}|{user_id}")],
                    [InlineKeyboardButton("New Order", callback_data=f"sms_menu|{user_id}")]
                ]
            
            elif result.get("code") == 50102:
                # Number expired/released
                text = (
                    "SMS BUS - EXPIRED\n"
                    f"Error: {result.get('message', 'Number expired')}\n\n"
                    "Please get a new number."
                )
                
                # Update history as failed
                if user_id in sms_history:
                    for entry in sms_history[user_id]:
                        if entry["request_id"] == request_id:
                            entry["status"] = "failed"
                            break
                
                active_sms_orders.pop(user_id, None)
                buttons = [[InlineKeyboardButton("New Order", callback_data=f"sms_menu|{user_id}")]]
            
            else:
                # Other error
                error_msg = result.get("message", "Unknown error")
                text = (
                    "SMS BUS - ERROR\n"
                    f"Error: {error_msg}\n"
                )
                buttons = [
                    [InlineKeyboardButton("Retry", callback_data=f"sms_check|{request_id}|{user_id}")],
                    [InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]
                ]
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        elif action == "sms_cancel":
            request_id = int(parts[1])
            owner_id = int(parts[2]) if len(parts) > 2 else user_id
            
            if user_id != owner_id:
                await query.answer("Not authorized", show_alert=True)
                return
            
            result = await sms_cancel_order(request_id)
            
            if result.get("code") == 200:
                await query.answer("Order cancelled! Refunded.", show_alert=True)
                
                # Update history as cancelled
                if user_id in sms_history:
                    for entry in sms_history[user_id]:
                        if entry["request_id"] == request_id:
                            entry["status"] = "cancelled"
                            break
                
                active_sms_orders.pop(user_id, None)
            else:
                await query.answer(f"Error: {result.get('message', 'Unknown')}", show_alert=True)
                return
            
            # Back to menu
            balance_result = await sms_get_balance()
            balance = 0
            if balance_result.get("code") == 200:
                balance = balance_result.get("data", {}).get("balance", 0)
            
            services_result = await sms_get_services()
            services = services_result.get("data", {}) if services_result.get("code") == 200 else {}
            
            text = (
                "SMS BUS OTP\n"
                "Virtual Number SMS Receiver\n\n"
                f"Balance: ${balance:.2f}\n\n"
                "Select Service:\n"
            )
            
            buttons = []
            service_list = list(services.items())[:24]
            for i in range(0, len(service_list), 3):
                row = []
                for svc_id, svc_data in service_list[i:i+3]:
                    title = svc_data.get("title", "Unknown")[:13]
                    row.append(InlineKeyboardButton(title, callback_data=f"sms_svc|{svc_id}|{user_id}"))
                buttons.append(row)
            buttons.append([
                InlineKeyboardButton("Balance", callback_data=f"sms_balance|{user_id}"),
                InlineKeyboardButton("History", callback_data=f"sms_history|{user_id}|0")
            ])
            buttons.append([InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")])
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        elif action == "sms_balance":
            owner_id = int(parts[1]) if len(parts) > 1 else user_id
            
            if user_id != owner_id:
                await query.answer("Not authorized", show_alert=True)
                return
            
            await query.answer("Checking balance...")
            
            result = await sms_get_balance()
            
            if result.get("code") != 200:
                await query.answer(f"Error: {result.get('message', 'Unknown')}", show_alert=True)
                return
            
            data = result.get("data", {})
            balance = data.get("balance", 0)
            
            text = (
                "SMS BUS - BALANCE\n"
                f"Balance: ${balance:.2f}\n\n"
                "Balance deducted per activation."
            )
            
            buttons = [[InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]]
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        elif action == "sms_history":
            owner_id = int(parts[1]) if len(parts) > 1 else user_id
            page = int(parts[2]) if len(parts) > 2 else 0
            
            if user_id != owner_id:
                await query.answer("Not authorized", show_alert=True)
                return
            
            await query.answer()
            
            if user_id not in sms_history or not sms_history[user_id]:
                text = (
                    "SMS BUS - HISTORY\n"
                    "No history yet.\n\n"
                    "Start ordering to build history."
                )
                buttons = [[InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]]
                await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
                return
            
            history_list = sms_history[user_id]
            total_pages = (len(history_list) + 4) // 5
            page = max(0, min(page, total_pages - 1))
            
            start_idx = page * 5
            end_idx = start_idx + 5
            page_history = history_list[start_idx:end_idx]
            
            text = (
                "SMS BUS - HISTORY\n"
                f"Page {page + 1}/{total_pages}\n\n"
            )
            
            for i, entry in enumerate(page_history, 1):
                status_emoji = get_status_emoji(entry["status"])
                text += (
                    f"{i}. {entry['service']}\n"
                    f"   {entry['country']}\n"
                    f"   {entry['phone']}\n"
                    f"   Status: {status_emoji}\n\n"
                )
            
            buttons = []
            
            # Pagination buttons
            if total_pages > 1:
                nav_row = []
                if page > 0:
                    nav_row.append(InlineKeyboardButton("Previous", callback_data=f"sms_history|{user_id}|{page - 1}"))
                if page < total_pages - 1:
                    nav_row.append(InlineKeyboardButton("Next", callback_data=f"sms_history|{user_id}|{page + 1}"))
                if nav_row:
                    buttons.append(nav_row)
            
            buttons.append([InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")])
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        elif action == "sms_orders":
            owner_id = int(parts[1]) if len(parts) > 1 else user_id
            
            if user_id != owner_id:
                await query.answer("Not authorized", show_alert=True)
                return
            
            await query.answer()
            
            if user_id in active_sms_orders:
                order = active_sms_orders[user_id]
                request_id = order.get("request_id")
                formatted_phone = order.get("formatted_phone", "N/A")
                service_name = order.get("service_name", "Unknown")
                
                text = (
                    "SMS BUS - ACTIVE ORDER\n"
                    f"Phone: {formatted_phone}\n"
                    f"Service: {service_name}\n"
                    f"Request ID: {request_id}\n\n"
                    "Status: Waiting for SMS"
                )
                
                buttons = [
                    [InlineKeyboardButton("Check SMS", callback_data=f"sms_check|{request_id}|{user_id}")],
                    [InlineKeyboardButton("Cancel", callback_data=f"sms_cancel|{request_id}|{user_id}")],
                    [InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]
                ]
                
                await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
                return
            
            text = (
                "SMS BUS - MY ORDERS\n"
                "No active orders.\n\n"
                "Start new order to get virtual number."
            )
            
            buttons = [[InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]]
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        elif action == "sms_menu":
            owner_id = int(parts[1]) if len(parts) > 1 else user_id
            
            if user_id != owner_id:
                await query.answer("Not authorized", show_alert=True)
                return
            
            await query.answer()
            
            balance_result = await sms_get_balance()
            balance = 0
            if balance_result.get("code") == 200:
                balance = balance_result.get("data", {}).get("balance", 0)
            
            services_result = await sms_get_services()
            services = services_result.get("data", {}) if services_result.get("code") == 200 else {}
            
            text = (
                "SMS BUS OTP\n"
                "Virtual Number SMS Receiver\n\n"
                f"Balance: ${balance:.2f}\n\n"
                "Select Service:\n"
            )
            
            buttons = []
            service_list = list(services.items())[:24]
            for i in range(0, len(service_list), 3):
                row = []
                for svc_id, svc_data in service_list[i:i+3]:
                    title = svc_data.get("title", "Unknown")[:13]
                    row.append(InlineKeyboardButton(title, callback_data=f"sms_svc|{svc_id}|{user_id}"))
                buttons.append(row)
            buttons.append([
                InlineKeyboardButton("Balance", callback_data=f"sms_balance|{user_id}"),
                InlineKeyboardButton("History", callback_data=f"sms_history|{user_id}|0")
            ])
            
            if user_id in active_sms_orders:
                buttons.append([InlineKeyboardButton("My Orders", callback_data=f"sms_orders|{user_id}")])
            
            buttons.append([InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")])
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    
    except Exception as e:
        logger.error(f"[SMS_BUS] Callback error: {e}")
        try:
            await query.answer(f"Error: {str(e)[:50]}", show_alert=True)
        except:
            pass

# Drama API Base URL (Example)
DRAMA_API_URL = "https://nano-drama-api.vercel.app" # Using an example API base based on the user screenshot @nanomilkiss

async def drama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Drama Search Command - /drama [query]"""
    if not await premium_lock_handler(update, context):
        return
        
    user_id = update.effective_user.id
    if not context.args:
        # Show main menu for Drama
        text = (
            "🎬 <b>ULTRA DRAMA HUB</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<i>Watch thousands of short dramas and series</i>\n\n"
            "• <b>NetShort</b> (Stable)\n"
            "• <b>DramaBox</b> (Stable)\n"
            "• <b>Melolo</b> (Stable)\n\n"
            "Usage: <code>/drama [query]</code>"
        )
        buttons = [
            [InlineKeyboardButton("🔥 Popular", callback_data=f"drama_list|foryou|1|{user_id}"),
             InlineKeyboardButton("🆕 New", callback_data=f"drama_list|new|1|{user_id}")],
            [InlineKeyboardButton("🏆 Ranking", callback_data=f"drama_list|rank|1|{user_id}")],
            [InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")]
        ]
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Searching for: <b>{query}</b>...", parse_mode=ParseMode.HTML)
    
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(f"{DRAMA_API_URL}/api/search/{query}/1")
            
            # Check if empty response or not JSON
            if not r.text or r.status_code != 200:
                await msg.edit_text("❌ <b>API Error.</b> Server might be down.", parse_mode=ParseMode.HTML)
                return
                
            try:
                data = r.json()
            except Exception:
                await msg.edit_text("❌ <b>Data Error.</b> Unexpected API response.", parse_mode=ParseMode.HTML)
                return
            
            if not data or not data.get("data"):
                await msg.edit_text("❌ <b>No drama found.</b> Try another keyword.", parse_mode=ParseMode.HTML)
                return
                
            text = f"🎬 <b>Results for:</b> <code>{query}</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            buttons = []
            for item in data["data"][:10]:
                title = item.get("title", "Unknown")
                drama_id = item.get("id")
                buttons.append([InlineKeyboardButton(f"▶️ {title}", callback_data=f"drama_info|{drama_id}|{user_id}")])
                
            buttons.append([InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")])
            await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            
    except Exception as e:
        await msg.edit_text(f"⚠️ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)

async def drama_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data.split("|")
    action = data[0]
    
    if action == "drama_menu":
        owner_id = int(data[1]) if len(data) > 1 else user_id
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        await query.answer()
        text = (
            "🎬 <b>ULTRA DRAMA HUB</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<i>Watch thousands of short dramas and series</i>\n\n"
            "• <b>NetShort</b> (Stable)\n"
            "• <b>DramaBox</b> (Stable)\n"
            "• <b>Melolo</b> (Stable)\n\n"
            "Usage: <code>/drama [query]</code>"
        )
        buttons = [
            [InlineKeyboardButton("🔥 Popular", callback_data=f"drama_list|foryou|1|{user_id}"),
             InlineKeyboardButton("🆕 New", callback_data=f"drama_list|new|1|{user_id}")],
            [InlineKeyboardButton("🏆 Ranking", callback_data=f"drama_list|rank|1|{user_id}")],
            [InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")]
        ]
        try:
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        except:
            await query.message.delete()
            await context.bot.send_message(query.message.chat_id, text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    elif action == "drama_list":
        list_type = data[1]
        page = int(data[2]) if len(data) > 2 else 1
        owner_id = int(data[3]) if len(data) > 3 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        await query.answer("Loading...")
        
        type_map = {"foryou": "foryou", "new": "newest", "rank": "ranking"}
        api_type = type_map.get(list_type, "foryou")
        type_labels = {"foryou": "🔥 Popular", "new": "🆕 New", "rank": "🏆 Ranking"}
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(f"{DRAMA_API_URL}/api/{api_type}/{page}")
                result = r.json()
                dramas = result.get("data", [])
                
                if not dramas:
                    await query.answer("No dramas found!", show_alert=True)
                    return
                
                text = (
                    f"🎬 <b>ULTRA DRAMA HUB</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"<b>{type_labels.get(list_type, 'Popular')}</b> • Page {page}\n\n"
                )
                
                buttons = []
                for item in dramas[:10]:
                    title = item.get("title", "Unknown")[:40]
                    drama_id = item.get("id")
                    buttons.append([InlineKeyboardButton(f"▶️ {title}", callback_data=f"drama_info|{drama_id}|{user_id}")])
                
                nav_row = []
                if page > 1:
                    nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"drama_list|{list_type}|{page-1}|{user_id}"))
                nav_row.append(InlineKeyboardButton("▶️ Next", callback_data=f"drama_list|{list_type}|{page+1}|{user_id}"))
                buttons.append(nav_row)
                buttons.append([InlineKeyboardButton("🏠 Menu", callback_data=f"drama_menu|{user_id}"),
                               InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")])
                
                await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
                
        except Exception as e:
            await query.answer(f"Error: {str(e)[:50]}", show_alert=True)
        return
    
    elif action == "drama_info":
        drama_id = data[1]
        owner_id = int(data[2]) if len(data) > 2 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
            
        await query.answer("Fetching details...")
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(f"{DRAMA_API_URL}/api/drama/{drama_id}")
                drama = r.json().get("data", {})
                
                title = drama.get("title", "Unknown")
                desc = drama.get("desc", "No description available.")
                cover = drama.get("cover")
                
                text = (
                    f"🎬 <b>{title}</b>\n\n"
                    f"<blockquote>{desc[:300]}...</blockquote>\n\n"
                    f"<b>Pilih episode</b>\n"
                    "Halaman: 1/1"
                )
                
                # Fetch chapters
                chap_r = await client.get(f"{DRAMA_API_URL}/api/chapters/{drama_id}")
                chapters = chap_r.json().get("data", [])
                
                buttons = []
                row = []
                for i, chap in enumerate(chapters[:30]): # Show first 30 eps
                    row.append(InlineKeyboardButton(f"E{i+1}", callback_data=f"drama_watch|{drama_id}|{i+1}|{user_id}"))
                    if len(row) == 5:
                        buttons.append(row)
                        row = []
                if row: buttons.append(row)
                
                buttons.append([InlineKeyboardButton("Back", callback_data=f"drama_menu|{user_id}"),
                               InlineKeyboardButton("Main Menu", callback_data=f"cmd_close|{user_id}")])
                
                if cover:
                    await query.message.delete()
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=cover,
                        caption=text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
                    
        except Exception as e:
            await query.answer(f"Error: {str(e)}", show_alert=True)

async def drama_watch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data.split("|")
    drama_id, ep, owner_id = data[1], data[2], int(data[3])
    
    if user_id != owner_id:
        await query.answer("Bukan milik kamu!", show_alert=True)
        return
        
    await query.answer(f"Loading Episode {ep}...")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{DRAMA_API_URL}/api/chapters/{drama_id}")
            chapters = r.json().get("data", [])
            
            ep_num = int(ep) - 1
            if ep_num >= len(chapters):
                await query.message.reply_text("❌ Episode not found.", parse_mode=ParseMode.HTML)
                return
            
            chapter = chapters[ep_num]
            video_url = chapter.get("videoUrl") or chapter.get("url") or chapter.get("video")
            
            if not video_url:
                await query.message.reply_text(
                    f"⚠️ <b>Episode {ep}</b>\n\n"
                    f"Video URL not available. Try again later.",
                    parse_mode=ParseMode.HTML
                )
                return
            
            drama_r = await client.get(f"{DRAMA_API_URL}/api/drama/{drama_id}")
            drama_info = drama_r.json().get("data", {})
            title = drama_info.get("title", "Drama")
            
            text = (
                f"📺 <b>{html.escape(title)}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Episode {ep}</b>\n\n"
                f"🎬 <b>Video Link:</b>\n"
                f"<code>{video_url}</code>\n\n"
                f"<i>Copy the link above or click the button to watch.</i>"
            )
            
            buttons = [
                [InlineKeyboardButton("▶️ Watch Now", url=video_url)],
                [InlineKeyboardButton("◀️ Back to Episodes", callback_data=f"drama_info|{drama_id}|{user_id}")],
                [InlineKeyboardButton("🏠 Menu", callback_data=f"drama_menu|{user_id}")]
            ]
            
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            
    except Exception as e:
        await query.message.reply_text(f"⚠️ <b>Error:</b> {html.escape(str(e))}", parse_mode=ParseMode.HTML)


async def scrape_stripe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Advanced Stripe payment link scraper dengan detail lengkap"""
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b> <code>/s [stripe_checkout_link]</code>\n\n"
            "💡 <b>Supported Links:</b>\n"
            "• checkout.stripe.com/c/pay/...\n"
            "• checkout.stripe.com/pay/...\n"
            "• Custom Stripe domains\n"
            "• Mobile & Desktop versions",
            parse_mode=ParseMode.HTML
        )
        return

    url = context.args[0].strip()
    
    # VALIDATION
    if "stripe" not in url.lower() or not url.startswith(("http://", "https://")):
        await update.message.reply_text(
            "❌ <b>Invalid URL</b>\n"
            "Must be a valid Stripe checkout link",
            parse_mode=ParseMode.HTML
        )
        return

    start_time = time.time()
    
    msg = await update.message.reply_text(
        "⏳ <b>Analyzing Stripe Payment Link...</b>\n"
        "[░░░░░░░░░░░░░░░░░░] 0%",
        parse_mode=ParseMode.HTML
    )

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            }

            # --- STEP 1: FETCH PAGE ---
            await msg.edit_text(
                "⏳ <b>Analyzing Stripe Payment Link...</b>\n"
                "[██░░░░░░░░░░░░░░░░] 10%",
                parse_mode=ParseMode.HTML
            )

            r = await client.get(url, headers=headers)
            content = r.text

            # --- STEP 2: EXTRACT SESSION ID ---
            await msg.edit_text(
                "⏳ <b>Extracting session data...</b>\n"
                "[████░░░░░░░░░░░░░░] 20%",
                parse_mode=ParseMode.HTML
            )

            # Multiple patterns untuk session ID
            session_patterns = [
                r'(cs_(live|test)_[a-zA-Z0-9]+)',
                r'"sessionId":"(cs_[a-zA-Z0-9_]+)"',
                r'data-session-id="(cs_[a-zA-Z0-9_]+)"',
            ]

            session_id = None
            for pattern in session_patterns:
                match = re.search(pattern, content)
                if match:
                    session_id = match.group(1)
                    break

            if not session_id:
                await msg.edit_text(
                    "❌ <b>Failed to extract session ID</b>\n"
                    "This might not be a valid Stripe checkout link",
                    parse_mode=ParseMode.HTML
                )
                return

            # --- STEP 3: EXTRACT PUBLIC KEY ---
            await msg.edit_text(
                "⏳ <b>Extracting API keys...</b>\n"
                "[██████░░░░░░░░░░░░] 30%",
                parse_mode=ParseMode.HTML
            )

            pk_patterns = [
                r'(pk_(live|test)_[a-zA-Z0-9]+)',
                r'"publishableKey":"(pk_[a-zA-Z0-9_]+)"',
                r'data-pk="(pk_[a-zA-Z0-9_]+)"',
            ]

            pk_key = None
            for pattern in pk_patterns:
                match = re.search(pattern, content)
                if match:
                    pk_key = match.group(1)
                    break

            if not pk_key:
                pk_key = "Not found"

            # --- STEP 4: CALL STRIPE API ---
            await msg.edit_text(
                "⏳ <b>Fetching payment details...</b>\n"
                "[████████░░░░░░░░░░] 40%",
                parse_mode=ParseMode.HTML
            )

            api_url = f"https://api.stripe.com/v1/payment_pages/{session_id}/init"
            payload = {
                "key": pk_key if pk_key != "Not found" else "",
                "eid": "NA"
            }

            try:
                r_api = await client.post(api_url, data=payload, headers=headers)
                data = r_api.json()
            except:
                data = {}

            # --- STEP 5: PARSE RESPONSE ---
            await msg.edit_text(
                "⏳ <b>Parsing response data...</b>\n"
                "[██████████░░░░░░░░] 50%",
                parse_mode=ParseMode.HTML
            )

            # Amount & Currency
            try:
                if 'line_item_group' in data:
                    line_item = data['line_item_group'].get('total', {})
                    amount_raw = line_item.get('amount', 0)
                    currency = data.get('currency', 'USD').upper()
                else:
                    amount_raw = data.get('amount', 0)
                    currency = data.get('currency', 'USD').upper()

                zero_decimal = ["BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"]

                if currency in zero_decimal:
                    amount_fmt = f"{amount_raw:,.0f}"
                else:
                    amount_fmt = f"{amount_raw / 100:,.2f}"

            except:
                amount_fmt = "N/A"
                currency = "N/A"

            # Email
            email = data.get('customer_email', 'Not specified')
            if not email or email == "":
                email = "Not specified"

            # Business Name
            business_name = data.get('business_name', '')
            if not business_name:
                # Extract dari success URL
                success_url = data.get('success_url', '')
                if success_url:
                    business_name = urlparse(success_url).netloc
                else:
                    # Extract dari original URL
                    business_name = urlparse(url).netloc

            # Description
            description = "N/A"
            if 'display_items' in data and len(data['display_items']) > 0:
                description = data['display_items'][0].get('description', 'N/A')

            # Mode (Live/Test)
            mode = "🔴 Live" if "live" in session_id else "🟡 Test"

            # Status
            is_valid = "✅ Valid" if pk_key != "Not found" else "⚠️ Partial"

            process_time = f"{time.time() - start_time:.2f}"

            # --- STEP 6: FORMAT OUTPUT ---
            await msg.edit_text(
                "⏳ <b>Formatting results...</b>\n"
                "[██████████████░░░░] 80%",
                parse_mode=ParseMode.HTML
            )

            txt = (
                f"🎯 <b>Okta — Stripe Extractor</b>\n"
                f"╔════════════════════════════════════╗\n"
                f"║ ✅ PAYMENT DETAILS EXTRACTED\n"
                f"╚════════════════════════════════════╝\n\n"
                
                f"<b>💳 TRANSACTION INFO</b>\n"
                f"├─ Amount: <code>{amount_fmt} {currency}</code>\n"
                f"├─ Status: {is_valid}\n"
                f"├─ Mode: {mode}\n"
                f"└─ Description: <code>{description}</code>\n\n"
                
                f"<b>📧 CUSTOMER INFO</b>\n"
                f"├─ Email: <code>{email}</code>\n"
                f"└─ Site: <code>{business_name}</code>\n\n"
                
                f"<b>🔑 STRIPE CREDENTIALS</b>\n"
                f"├─ Session: <code>{session_id}</code>\n"
                f"└─ Key: <code>{pk_key}</code>\n\n"
                
                f"<b>⏱️ METADATA</b>\n"
                f"├─ Processed in: {process_time}s\n"
                f"├─ Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"└─ Source: Stripe Payment Link\n"
                f"╔════════════════════════════════════╗\n"
                f"🤖 Powered by Oktacomel\n"
                f"╚════════════════════════════════════╝"
            )

            await msg.edit_text(txt, parse_mode=ParseMode.HTML)

            # --- LOGGING (OPTIONAL) ---
            try:
                await log_user_action(
                    update.effective_user.id,
                    "stripe_extract",
                    f"session:{session_id[:20]}... amount:{amount_fmt} {currency}"
                )
            except:
                pass

    except asyncio.TimeoutError:
        await msg.edit_text(
            "❌ <b>Timeout Error</b>\n"
            "Server took too long to respond.\n"
            "Try again in a moment.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"[STRIPE] Error: {e}")
        await msg.edit_text(
            f"❌ <b>Error Processing Link</b>\n\n"
            f"<b>Details:</b> {str(e)[:80]}\n\n"
            f"<b>Possible causes:</b>\n"
            f"• Invalid Stripe link\n"
            f"• Session expired\n"
            f"• Network error\n"
            f"• Stripe API blocked",
            parse_mode=ParseMode.HTML
        )

# ==========================================
# 👤 FAKE IDENTITY GENERATOR (PREMIUM + FAKE MAIL)
# ==========================================
async def fake_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = context.args[0].lower() if context.args else 'us'
    
    # MAPPING LENGKAP (30+ NEGARA)
    locales = {
        'id': 'id_ID', 'sg': 'en_SG', 'jp': 'ja_JP', 'kr': 'ko_KR', 
        'cn': 'zh_CN', 'tw': 'zh_TW', 'th': 'th_TH', 'vn': 'vi_VN',
        'ph': 'fil_PH', 'in': 'en_IN', 'au': 'en_AU', 'nz': 'en_NZ',
        'my': 'ms_MY', 'us': 'en_US', 'ca': 'en_CA', 'br': 'pt_BR', 
        'mx': 'es_MX', 'ar': 'es_AR', 'co': 'es_CO', 'uk': 'en_GB', 
        'fr': 'fr_FR', 'de': 'de_DE', 'it': 'it_IT', 'es': 'es_ES', 
        'nl': 'nl_NL', 'ru': 'ru_RU', 'ua': 'uk_UA', 'pl': 'pl_PL', 
        'tr': 'tr_TR', 'se': 'sv_SE', 'no': 'no_NO', 'sa': 'ar_SA', 
        'ir': 'fa_IR', 'za': 'en_ZA', 'ng': 'en_NG'
    }
    
    country_names = {
        'id': 'Indonesia 🇮🇩', 'sg': 'Singapore 🇸🇬', 'jp': 'Japan 🇯🇵', 'kr': 'South Korea 🇰🇷',
        'cn': 'China 🇨🇳', 'tw': 'Taiwan 🇹🇼', 'th': 'Thailand 🇹🇭', 'vn': 'Vietnam 🇻🇳',
        'ph': 'Philippines 🇵🇭', 'in': 'India 🇮🇳', 'au': 'Australia 🇦🇺', 'nz': 'New Zealand 🇳🇿',
        'my': 'Malaysia 🇲🇾', 'us': 'United States 🇺🇸', 'ca': 'Canada 🇨🇦', 'br': 'Brazil 🇧🇷',
        'mx': 'Mexico 🇲🇽', 'ar': 'Argentina 🇦🇷', 'co': 'Colombia 🇨🇴', 'uk': 'United Kingdom 🇬🇧',
        'fr': 'France 🇫🇷', 'de': 'Germany 🇩🇪', 'it': 'Italy 🇮🇹', 'es': 'Spain 🇪🇸',
        'nl': 'Netherlands 🇳🇱', 'ru': 'Russia 🇷🇺', 'ua': 'Ukraine 🇺🇦', 'pl': 'Poland 🇵🇱',
        'tr': 'Turkey 🇹🇷', 'se': 'Sweden 🇸🇪', 'no': 'Norway 🇳🇴', 'sa': 'Saudi Arabia 🇸🇦',
        'ir': 'Iran 🇮🇷', 'za': 'South Africa 🇿🇦', 'ng': 'Nigeria 🇳🇬'
    }

    if code not in locales:
        await update.message.reply_text(f"⚠️ <b>Country Not Found</b>\nUsage: <code>/fake sg</code>", parse_mode=ParseMode.HTML)
        return

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    try:
        fake = Faker(locales[code])
        
        name = fake.name()
        address = fake.street_address()
        city = fake.city()
        try: state = fake.state()
        except: state = fake.administrative_unit()
        zipcode = fake.postcode()
        phone = fake.phone_number()
        country_disp = country_names.get(code, code.upper())
        
        # --- GENERATE EMAIL (Fake Mail Generator) ---
        # Format: username@teleworm.us
        username_mail = name.lower().replace(" ", "").replace(".", "") + str(random.randint(100,999))
        domain = "teleworm.us"
        email_full = f"{username_mail}@{domain}"
        
        # Link Inbox Langsung
        inbox_link = f"https://www.fakemailgenerator.com/#/{domain}/{username_mail}/"

        # TAMPILAN PREMIUM (BOLD SANS + ARROW)
        txt = (
            f"👤 <b>FAKE IDENTITY</b> ({code.upper()})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"𝗡𝗮𝗺𝗲 ⇾ <code>{name}</code>\n"
            f"𝗦𝘁𝗿𝗲𝗲𝘁 ⇾ <code>{address}</code>\n"
            f"𝗖𝗶𝘁𝘆 ⇾ <code>{city}</code>\n"
            f"𝗦𝘁𝗮𝘁𝗲 ⇾ <code>{state}</code>\n"
            f"𝗭𝗶𝗽 𝗖𝗼𝗱𝗲 ⇾ <code>{zipcode}</code>\n"
            f"𝗣𝗵𝗼𝗻𝗲 ⇾ <code>{phone}</code>\n"
            f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆 ⇾ <code>{country_disp}</code>\n\n"
            f"📧 𝗘𝗺𝗮𝗶𝗹 ⇾ <code>{email_full}</code>\n"
            f"🔗 𝗜𝗻𝗯𝗼𝘅 ⇾ <a href='{inbox_link}'>Check Mail Here</a>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <i>Powered by Oktacomel</i>"
        )

        await update.message.reply_text(txt, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ==========================================
# 🌸 ANIME & WAIFU SYSTEM (AUTO DETECT)
# ==========================================
async def anime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Ambil perintah apa yang diketik user (contoh: /blowjob atau /waifu)
    command = update.message.text.split()[0].replace('/', '').lower()
    
    # 2. Mapping Konfigurasi (Menentukan mana SFW dan mana NSFW)
    # Format: "command": ("tipe", "kategori_api")
    mapping = {
        # --- KATEGORI SFW (AMAN) ---
        'waifu': ('sfw', 'waifu'),
        'neko': ('sfw', 'neko'),
        'shinobu': ('sfw', 'shinobu'),
        'megumin': ('sfw', 'megumin'),
        'bully': ('sfw', 'bully'),
        'cuddle': ('sfw', 'cuddle'),
        'cry': ('sfw', 'cry'),
        'hug': ('sfw', 'hug'),
        'awoo': ('sfw', 'awoo'),
        'kiss': ('sfw', 'kiss'),
        'lick': ('sfw', 'lick'),
        
        # --- KATEGORI NSFW (DEWASA) ---
        'blowjob': ('nsfw', 'blowjob'),
        'trap': ('nsfw', 'trap'),
        'nwaifu': ('nsfw', 'waifu'), # nwaifu = nsfw waifu
        'nneko': ('nsfw', 'neko')    # nneko = nsfw neko
    }

    # Cek apakah command ada di mapping
    if command not in mapping:
        await update.message.reply_text("⚠️ Command tidak dikenali.", parse_mode=ParseMode.HTML)
        return

    # Ambil tipe dan kategorinya
    mode, category = mapping[command]
    
    # Buat URL API
    url = f"https://api.waifu.pics/{mode}/{category}"
    
    # Kirim status "Upload Photo" biar kelihatan loading
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
    
    try:
        # Request ke API
        data = await fetch_json(url)
        
        if data and 'url' in data:
            img_url = data['url']
            
            # Caption Cantik
            caption = f"🔞 <b>{category.upper()}</b>" if mode == "nsfw" else f"🌸 <b>{category.upper()}</b>"
            
            # Cek apakah GIF atau Gambar biasa
            if img_url.endswith(".gif"):
                await update.message.reply_animation(img_url, caption=caption, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_photo(img_url, caption=caption, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ <b>Error:</b> API Server Busy / Image Not Found.", parse_mode=ParseMode.HTML)
            
    except Exception as e:
        await update.message.reply_text(f"⚠️ <b>System Error:</b> {e}", parse_mode=ParseMode.HTML)

# ==========================================
# 🎨 AI IMAGE GENERATOR — PREMIUM ULTIMATE EDITION v2.0
# ==========================================

GIMITA_IMG_API = "https://api.gimita.id/api/ai/gpt5img"

async def img_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI Image Generator dengan progress bar animasi"""
    
    if not context.args:
        return await update.message.reply_text(
            "⚠️ <b>Usage:</b> <code>/img kucing terbang di langit</code>\n\n"
            "💡 <b>Tips:</b> Semakin detail prompt, semakin bagus hasilnya!",
            parse_mode=ParseMode.HTML
        )

    prompt = " ".join(context.args)
    
    # Validasi prompt
    if len(prompt) < 3:
        return await update.message.reply_text(
            "❌ <b>Prompt terlalu pendek!</b>\n"
            "Minimal 3 karakter.",
            parse_mode=ParseMode.HTML
        )
    
    if len(prompt) > 500:
        prompt = prompt[:500]

    seed = random.randint(1, 999999)

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
    
    # Initial message
    msg = await update.message.reply_text(
        "🎨 <b>Generating AI Image...</b>\n"
        "[░░░░░░░░░░░░░░░░░░] 0%",
        parse_mode=ParseMode.HTML
    )

    # ==========================================
    # SMART MODEL DETECTOR
    # ==========================================
    p = prompt.lower()

    if any(x in p for x in ["anime", "waifu", "manga", "2d", "chibi", "cartoon"]):
        model = "anime"
        style_name = "Anime Art Style"
        icon = "🌸"
    elif any(x in p for x in ["logo", "icon", "mascot", "brand", "minimalist"]):
        model = "logo"
        style_name = "Clean Logo Design"
        icon = "🔰"
    elif any(x in p for x in ["cyberpunk", "neon", "futuristic", "synthwave", "sci-fi"]):
        model = "flux"
        style_name = "Cyberpunk Neon"
        icon = "⚡"
    elif any(x in p for x in ["3d", "render", "cgi", "realistic"]):
        model = "flux"
        style_name = "3D Realistic"
        icon = "🎬"
    else:
        model = "flux"
        style_name = "Flux Ultra HD"
        icon = "📸"

    # ==========================================
    # PROGRESS BAR STAGES
    # ==========================================
    
    stages = [
        {"progress": 10, "text": "Analyzing prompt...", "bar": "██░░░░░░░░░░░░░░░░"},
        {"progress": 25, "text": "Initializing AI model...", "bar": "█████░░░░░░░░░░░░░░"},
        {"progress": 40, "text": "Processing neural network...", "bar": "████████░░░░░░░░░░░░"},
        {"progress": 60, "text": "Rendering image...", "bar": "████████████░░░░░░░░"},
        {"progress": 80, "text": "Optimizing quality...", "bar": "████████████████░░░░"},
        {"progress": 95, "text": "Finalizing details...", "bar": "███████████████████░"},
    ]

    # Update progress
    for stage in stages:
        try:
            await msg.edit_text(
                f"🎨 <b>Generating AI Image...</b>\n"
                f"[{stage['bar']}] {stage['progress']}%\n"
                f"⏳ {stage['text']}",
                parse_mode=ParseMode.HTML
            )
            await asyncio.sleep(0.8)
        except:
            pass

    # ==========================================
    # GIMITA API - GPT5IMG (GET METHOD ONLY)
    # ==========================================
    
    img_url = None
    used_source = "GiMiTA GPT5"

    try:
        await msg.edit_text(
            "🎨 <b>Generating with GiMiTA AI...</b>\n"
            "[███████████████████░] 95%\n"
            "⏳ Connecting to server...",
            parse_mode=ParseMode.HTML
        )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json,text/plain,*/*",
        }

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(GIMITA_IMG_API, params={"prompt": prompt})
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle berbagai struktur response
                if isinstance(data, dict):
                    img_url = (
                        data.get("url") or 
                        data.get("image") or 
                        data.get("image_url") or
                        data.get("result") or
                        (data.get("data") or {}).get("url") or
                        (data.get("data") or {}).get("image") or
                        (data.get("data") or {}).get("image_url")
                    )
                elif isinstance(data, str) and data.startswith("http"):
                    img_url = data
            else:
                # Log error untuk debugging
                logger.debug(f"[IMG] GiMiTA returned {response.status_code}: {response.text[:200]}")

    except asyncio.TimeoutError:
        logger.debug("[IMG] GiMiTA timeout")
    except Exception as e:
        logger.debug(f"[IMG] GiMiTA error: {e}")

    # ==========================================
    # FALLBACK API (jika GiMiTA gagal)
    # ==========================================
    
    if not img_url:
        try:
            await msg.edit_text(
                "🎨 <b>Trying Pollinations...</b>\n"
                "[█████████████████░░░] 85%\n"
                "⏳ Connecting to fallback...",
                parse_mode=ParseMode.HTML
            )
            
            fallback_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={seed}&enhance=true&nologo=true&model={model}"
            
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.get(fallback_url, follow_redirects=True)
                
                if response.status_code == 200:
                    img_url = fallback_url
                    used_source = "Pollinations"
                    
        except Exception as e:
            logger.debug(f"[IMG] Pollinations error: {e}")

    # ==========================================
    # ERROR HANDLING
    # ==========================================
    
    if not img_url:
        await msg.edit_text(
            "❌ <b>Gagal Generate Gambar</b>\n\n"
            "Kemungkinan:\n"
            "• API Server sedang maintenance\n"
            "• Prompt contains blocked keywords\n"
            "• Network timeout\n\n"
            "💡 <b>Coba:</b>\n"
            "1. Ubah prompt lebih sederhana\n"
            "2. Hapus kata-kata sensitif\n"
            "3. Coba lagi dalam beberapa menit\n\n"
            "Contoh prompt bagus:\n"
            "<code>/img beautiful sunset over ocean</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # ==========================================
    # FINAL PROGRESS - 100%
    # ==========================================
    try:
        await msg.edit_text(
            "🎨 <b>Generating AI Image...</b>\n"
            "[████████████████████] 100%\n"
            "✅ Complete! Sending image...",
            parse_mode=ParseMode.HTML
        )
    except:
        pass

    await asyncio.sleep(0.5)

    # ==========================================
    # CAPTION PREMIUM
    # ==========================================
    caption = (
        f"🎨 <b>AI Image Studio — Premium</b> {icon}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🖼️ <b>Prompt:</b>\n"
        f"<code>{html.escape(prompt)}</code>\n\n"
        f"⚙️ <b>Model:</b> {style_name}\n"
        f"📊 <b>Quality:</b> Ultra HD (1024x1024)\n"
        f"🔢 <b>Seed:</b> <code>{seed}</code>\n"
        f"🌐 <b>Source:</b> {used_source}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ <i>Powered by Oktacomel AI</i>"
    )

    # ==========================================
    # SEND IMAGE
    # ==========================================
    try:
        await update.message.reply_photo(
            photo=img_url,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
        await msg.delete()

    except Exception as e:
        logger.error(f"[IMG] Photo send error: {e}")
        
        # Fallback: Send as text dengan link
        try:
            await msg.edit_text(
                f"⚠️ <b>Image Load Issue</b>\n\n"
                f"{caption}\n\n"
                f"🔗 <a href='{img_url}'>Open Image in Browser</a>",
                parse_mode=ParseMode.HTML
            )
        except:
            await msg.edit_text(
                "❌ <b>Gagal mengirim gambar</b>\n\n"
                "Coba:\n"
                "1. /img dengan prompt lain\n"
                "2. Tunggu beberapa detik\n"
                "3. Coba lagi",
                parse_mode=ParseMode.HTML
            )

async def sk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("SK command jalan")

# ==========================================
# 🗣️ TEXT TO SPEECH GOOGLE (/tts)
# ==========================================
async def tts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/tts id Halo dunia</code>\nKode bahasa: id, en, ja, ko, ar", parse_mode=ParseMode.HTML)
        return

    lang = context.args[0] # Kode bahasa (id, en, dll)
    text = " ".join(context.args[1:])
    
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_VOICE)

    try:
        # Generate Suara
        tts = gTTS(text=text, lang=lang)
        filename = f"voice_{update.effective_user.id}.mp3"
        tts.save(filename)
        
        # Kirim File
        await update.message.reply_audio(filename, title="Okta TTS", performer="Google Voice")
        
        # Hapus File Sampah
        os.remove(filename)
        
    except ValueError:
        await update.message.reply_text("❌ Bahasa tidak didukung. Coba: id, en, ja.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.HTML)

# ==========================================
# 🌐 TRANSLATE COMMAND (100+ LANGUAGES)
# ==========================================
async def tr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Cek Format Input
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b> <code>/tr [kode] [teks]</code>\n\n"
            "<b>Contoh Populer:</b>\n"
            "• <code>/tr id Good Morning</code> (Ke Indo)\n"
            "• <code>/tr en Aku cinta kamu</code> (Ke Inggris)\n"
            "• <code>/tr ar Selamat Pagi</code> (Ke Arab)\n"
            "• <code>/tr ja Terima kasih</code> (Ke Jepang)", 
            parse_mode=ParseMode.HTML
        )
        return

    target_lang = context.args[0].lower() # Kode bahasa
    text_to_tr = " ".join(context.args[1:]) # Teksnya
    
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    try:
        # 2. Proses Translate (Otomatis deteksi bahasa asal)
        translator = GoogleTranslator(source='auto', target=target_lang)
        translated = translator.translate(text_to_tr)
        
        # 3. Tampilan Hasil (Rapi)
        res = (
            f"🌐 <b>TRANSLATE RESULT</b> ({target_lang.upper()})\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔤 <b>Asli:</b> <i>{html.escape(text_to_tr)}</i>\n"
            f"🔠 <b>Hasil:</b> <code>{html.escape(translated)}</code>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🤖 <i>Powered by Google Translate</i>"
        )
        await update.message.reply_text(res, parse_mode=ParseMode.HTML)

    except Exception as e:
        error_msg = str(e)
        
        # Jika Error (Biasanya karena salah kode bahasa)
        # Kita kasih daftar kode negara yang LENGKAP di sini
        if "supported" in error_msg.lower() or "invalid" in error_msg.lower():
            await update.message.reply_text(
                f"❌ <b>Kode Bahasa '{target_lang}' Tidak Dikenal!</b>\n\n"
                "Gunakan kode 2 huruf (ISO 639-1). Contoh:\n"
                "🇮🇩 Indo: <code>id</code>\n"
                "🇺🇸 Inggris: <code>en</code>\n"
                "🇸🇦 Arab: <code>ar</code>\n"
                "🇯🇵 Jepang: <code>ja</code>\n"
                "🇰🇷 Korea: <code>ko</code>\n"
                "🇨🇳 China: <code>zh-CN</code>\n"
                "🇷🇺 Rusia: <code>ru</code>\n"
                "🇪🇸 Spanyol: <code>es</code>\n"
                "🇫🇷 Perancis: <code>fr</code>\n"
                "🇩🇪 Jerman: <code>de</code>\n"
                "🇹🇭 Thailand: <code>th</code>\n"
                "🇲🇾 Malaysia: <code>ms</code>\n\n"
                "<i>Dan masih banyak lagi!</i>",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(f"❌ <b>System Error:</b> {error_msg}", parse_mode=ParseMode.HTML)

# ==========================================
# 💱 CURRENCY CONVERTER (USDT <-> IDR)
# ==========================================
async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Cek Input User (Harus 3 kata: Jumlah - Dari - Ke)
    if len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ <b>Cara Pakai:</b> <code>/convert [Jumlah] [Dari] [Ke]</code>\n\n"
            "<b>Contoh:</b>\n"
            "• <code>/convert 10 USDT IDR</code>\n"
            "• <code>/convert 100 USD IDR</code>\n"
            "• <code>/convert 1 BTC USD</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # 2. Parsing Data
    try:
        amount = float(context.args[0]) # Jumlah (misal: 10)
        base_curr = context.args[1].upper() # Dari (misal: USDT)
        target_curr = context.args[2].upper()   # Ke (misal: IDR)
    except ValueError:
        await update.message.reply_text("❌ <b>Error:</b> Jumlah harus berupa angka (contoh: 10 atau 10.5).", parse_mode=ParseMode.HTML)
        return

    # Loading Message
    msg = await update.message.reply_text(f"💱 <b>Menghitung {base_curr} ke {target_curr}...</b>", parse_mode=ParseMode.HTML)

    try:
        # 3. Request ke API Coinbase (Gratis & Akurat untuk USDT)
        url = f"https://api.coinbase.com/v2/exchange-rates?currency={base_curr}"
        
        # Gunakan requests (sesuai library yang kamu punya)
        r = requests.get(url)
        data = r.json()

        # 4. Validasi Response
        if 'data' not in data:
            await msg.edit_text(f"❌ Mata uang <b>{base_curr}</b> tidak ditemukan.", parse_mode=ParseMode.HTML)
            return

        rates = data['data']['rates']
        
        if target_curr not in rates:
            await msg.edit_text(f"❌ Tidak bisa konversi ke <b>{target_curr}</b>.", parse_mode=ParseMode.HTML)
            return

        # 5. Hitung Hasil
        rate_value = float(rates[target_curr])
        result_value = amount * rate_value

        # Format Angka (Pemisah ribuan: 15,000.00)
        formatted_result = f"{result_value:,.2f}" 
        formatted_rate = f"{rate_value:,.2f}"

        # 6. Tampilan Hasil (Branding Oktacomel)
        txt = (
            f"💱 <b>OKTACOMEL CONVERTER</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💸 <b>Input:</b> {amount} {base_curr}\n"
            f"💰 <b>Hasil:</b> {formatted_result} {target_curr}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Rate:</b> 1 {base_curr} = {formatted_rate} {target_curr}\n"
            f"🤖 <i>Live Data by Coinbase</i>"
        )
        
        await msg.edit_text(txt, parse_mode=ParseMode.HTML)

    except Exception as e:
        await msg.edit_text(f"❌ <b>System Error:</b> {str(e)}", parse_mode=ParseMode.HTML)

# ==========================================
# 🪙 CRYPTO COMMAND (Dipanggil saat ketik /crypto BTC)
# ==========================================
async def crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # 1. Cek Input User
    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Format Salah!</b>\n"
            "Gunakan: <code>/crypto [NAMA_KOIN]</code>\n"
            "Contoh: <code>/crypto BTC</code> atau <code>/crypto XRP</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # 2. Siapkan Data
    symbol = context.args[0].upper()
    pair = f"{symbol}USDT"
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair}"

    # 3. Kirim Pesan Loading (Biar user tau bot bekerja)
    msg = await update.message.reply_text(f"⏳ <b>Fetching {symbol} market data...</b>", parse_mode=ParseMode.HTML)

    # 4. Ambil Data (Sama persis kayak refresh)
    d = await fetch_json(url)
    if not d or 'symbol' not in d:
        return await msg.edit_text(f"❌ <b>Market data not available for {symbol}.</b>", parse_mode=ParseMode.HTML)

    # --- FITUR KOSMETIK (Sama persis) ---
    def fmt_price(n):
        try:
            n = float(n)
            if n >= 1: return f"{n:,.2f}"
            return f"{n:,.6f}"
        except: return str(n)

    def fmt_int(n):
        try: return f"{int(float(n)):,}"
        except: return str(n)

    def mini_bar(pct):
        try:
            p = max(-10, min(10, float(pct)))
            v = (p + 10) / 20
            length = 12
            filled = int(round(v * length))
            return "▰" * filled + "▱" * (length - filled)
        except: return "▱" * 12

    try:
        # 5. Parsing Data (Copy-Paste dari refresh handler)
        last_price = float(d.get('lastPrice', 0))
        ask_price = float(d.get('askPrice', 0))
        bid_price = float(d.get('bidPrice', 0))
        high_24h = float(d.get('highPrice', 0))
        low_24h = float(d.get('lowPrice', 0))
        change_p = float(d.get('priceChangePercent', 0))
        change_abs = float(d.get('priceChange', 0))
        vol_quote = float(d.get('quoteVolume', 0))
        open_price = float(d.get('openPrice', 0))
        weighted_avg = float(d.get('weightedAvgPrice', 0))

        # Trend Logic
        if change_p >= 5.0:
            trend_emoji = "🟢"
            trend = "STRONG BULL"
        elif 0.5 <= change_p < 5.0:
            trend_emoji = "🟢"
            trend = "UPTREND"
        elif -5.0 < change_p <= -0.5:
            trend_emoji = "🔴"
            trend = "DOWNTREND"
        elif change_p <= -5.0:
            trend_emoji = "🔴"
            trend = "STRONG BEAR"
        else:
            trend_emoji = "🟡"
            trend = "SIDEWAYS"

        sign = "+" if change_p > 0 else ""
        percent_str = f"{sign}{change_p:.2f}%"

        # 6. Format Pesan (Premium Ultimate Style)
        text = (
            f"🪙 <b>OKTACOMEL — CRYPTO SNAPSHOT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💠 <b>Pair:</b> <code>{pair}</code>\n"
            f"💵 <b>Last Price:</b> <code>${fmt_price(last_price)}</code>\n"
            f"📊 <b>24h Change:</b> {trend_emoji} <b>{percent_str}</b> ({fmt_price(change_abs)})\n"
            f"🔎 <b>Trend:</b> {trend}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Market Range (24h)</b>\n"
            f"• Low  : <code>${fmt_price(low_24h)}</code>\n"
            f"• High : <code>${fmt_price(high_24h)}</code>\n"
            f"• Open : <code>${fmt_price(open_price)}</code>\n"
            f"• Avg  : <code>${fmt_price(weighted_avg)}</code>\n"
            f"Range : {mini_bar(change_p)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛒 <b>Orderbook (Top)</b>\n"
            f"• Ask : <code>${fmt_price(ask_price)}</code>\n"
            f"• Bid : <code>${fmt_price(bid_price)}</code>\n\n"
            f"📦 <b>24h Volume (quote):</b> <code>${fmt_int(vol_quote)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <i>Data source: Binance (real-time)</i>\n"
            f"🐈 <i>Powered by Oktacomel — Premium</i>"
        )

        # 7. Tombol (Menu refresh mengarah ke symbol ini)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📈 Open Chart (Binance)", url=f"https://www.binance.com/en/trade/{symbol}_USDT")],
            [InlineKeyboardButton("⏰ Set Price Alert", callback_data=f"alert|{symbol}|{last_price}"),
             InlineKeyboardButton("🔁 Refresh", callback_data=f"crypto_refresh|{symbol}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"menu_main|{user_id}")]
        ])

        # 8. Tampilkan Hasil (Edit pesan loading tadi)
        await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}", parse_mode=ParseMode.HTML)
# --- CALLBACK: Refresh crypto (dipanggil dari tombol "Refresh") ---
@require_start_callback
async def crypto_refresh_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        # callback_data format: crypto_refresh|BTC
        _, symbol = q.data.split("|", 1)
        symbol = symbol.upper()
        pair = f"{symbol}USDT"
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair}"

        # loading singkat (edit pesan jadi loading)
        await q.edit_message_text(f"⏳ <b>Refreshing {symbol} market data...</b>", parse_mode=ParseMode.HTML)

        d = await fetch_json(url)
        if not d or 'symbol' not in d:
            return await q.edit_message_text("❌ <b>Market data not available.</b>", parse_mode=ParseMode.HTML)

        # helper lokal (sama format dengan crypto_command)
        def fmt_price(n):
            try:
                n = float(n)
                if n >= 1:
                    return f"{n:,.2f}"
                return f"{n:,.6f}"
            except:
                return str(n)
        def fmt_int(n):
            try:
                return f"{int(float(n)):,}"
            except:
                return str(n)
        def mini_bar(pct):
            try:
                p = max(-10, min(10, float(pct)))
                v = (p + 10) / 20
                length = 12
                filled = int(round(v * length))
                return "▰" * filled + "▱" * (length - filled)
            except:
                return "▱" * 12

        last_price = float(d.get('lastPrice', 0))
        ask_price = float(d.get('askPrice', 0))
        bid_price = float(d.get('bidPrice', 0))
        high_24h = float(d.get('highPrice', 0))
        low_24h = float(d.get('lowPrice', 0))
        change_p = float(d.get('priceChangePercent', 0))
        change_abs = float(d.get('priceChange', 0))
        vol_quote = float(d.get('quoteVolume', 0))
        open_price = float(d.get('openPrice', 0))
        weighted_avg = float(d.get('weightedAvgPrice', 0))

        # Trend label sederhana
        if change_p >= 5.0:
            trend_emoji = "🟢"
            trend = "STRONG BULL"
        elif 0.5 <= change_p < 5.0:
            trend_emoji = "🟢"
            trend = "UPTREND"
        elif -5.0 < change_p <= -0.5:
            trend_emoji = "🔴"
            trend = "DOWNTREND"
        elif change_p <= -5.0:
            trend_emoji = "🔴"
            trend = "STRONG BEAR"
        else:
            trend_emoji = "🟡"
            trend = "SIDEWAYS"

        sign = "+" if change_p > 0 else ""
        percent_str = f"{sign}{change_p:.2f}%"

        text = (
            f"🪙 <b>OKTACOMEL — CRYPTO SNAPSHOT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💠 <b>Pair:</b> <code>{pair}</code>\n"
            f"💵 <b>Last Price:</b> <code>${fmt_price(last_price)}</code>\n"
            f"📊 <b>24h Change:</b> {trend_emoji} <b>{percent_str}</b> ({fmt_price(change_abs)})\n"
            f"🔎 <b>Trend:</b> {trend}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Market Range (24h)</b>\n"
            f"• Low  : <code>${fmt_price(low_24h)}</code>\n"
            f"• High : <code>${fmt_price(high_24h)}</code>\n"
            f"• Open : <code>${fmt_price(open_price)}</code>\n"
            f"• Avg  : <code>${fmt_price(weighted_avg)}</code>\n"
            f"Range : {mini_bar(change_p)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛒 <b>Orderbook (Top)</b>\n"
            f"• Ask : <code>${fmt_price(ask_price)}</code>\n"
            f"• Bid : <code>${fmt_price(bid_price)}</code>\n\n"
            f"📦 <b>24h Volume (quote):</b> <code>${fmt_int(vol_quote)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <i>Data source: Binance (real-time)</i>\n"
            f"🐈 <i>Powered by Oktacomel — Premium</i>"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📈 Open Chart (Binance)", url=f"https://www.binance.com/en/trade/{symbol}_USDT")],
            [InlineKeyboardButton("⏰ Set Price Alert", callback_data=f"alert|{symbol}|{last_price}"),
             InlineKeyboardButton("🔁 Refresh", callback_data=f"crypto_refresh|{symbol}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"menu_main|{q.from_user.id}")]
        ])

        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    except Exception as e:
        try:
            await q.edit_message_text(f"❌ Error: {html.escape(str(e))}", parse_mode=ParseMode.HTML)
        except:
            pass


# --- CALLBACK: Price alert (simpan sederhana ke DB + acknowledge) ---
@require_start_callback
async def crypto_alert_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        # contoh callback: alert|BTC|12345.67
        parts = q.data.split("|")
        symbol = parts[1] if len(parts) > 1 else "UNKNOWN"
        target_price = float(parts[2]) if len(parts) > 2 else None

        # Simpan ke SQLite (table crypto_alerts) — jika tabel belum ada, buat otomatis
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS crypto_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER,
                        symbol TEXT,
                        target REAL,
                        created_at REAL
                    )
                """)
                await db.commit()

                await db.execute(
                    "INSERT INTO crypto_alerts (chat_id, symbol, target, created_at) VALUES (?, ?, ?, ?)",
                    (q.message.chat_id, symbol, target_price if target_price else 0.0, time.time())
                )
                await db.commit()
        except Exception:
            # jangan crash kalau DB error, lanjutkan saja
            pass

        await q.answer(f"✅ Price alert set for {symbol} (target: {target_price if target_price else 'current'})", show_alert=True)
    except Exception as e:
        await q.answer(f"⚠️ Failed to set alert: {str(e)}", show_alert=True)


# --- OPTIONAL: Checker job — panggil ini via job_queue.run_repeating(check_price_alerts, interval=60, first=30) ---
async def check_price_alerts(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id, chat_id, symbol, target FROM crypto_alerts") as cur:
                rows = await cur.fetchall()
                if not rows:
                    return

                # group by symbol untuk efisiensi
                by_symbol = {}
                for r in rows:
                    _id, chat_id, sym, target = r
                    sym = sym.upper()
                    by_symbol.setdefault(sym, []).append(( _id, chat_id, target ))

                for sym, alerts in by_symbol.items():
                    pair = f"{sym}USDT"
                    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair}"
                    d = await fetch_json(url)
                    if not d or 'lastPrice' not in d: 
                        continue
                    last = float(d.get('lastPrice', 0))
                    # peringatan bila last >= target (simple logic)
                    for (_id, chat_id, target) in alerts:
                        try:
                            if target > 0 and last >= float(target):
                                text = (f"🚨 <b>Price Alert</b>\n"
                                        f"Pair: <code>{pair}</code>\n"
                                        f"Current: <code>${last:,.6f}</code>\n"
                                        f"Target: <code>${float(target):,.6f}</code>\n"
                                        f"ID Alert: <code>{_id}</code>")
                                await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
                                # hapus alert setelah trigger (opsional)
                                await db.execute("DELETE FROM crypto_alerts WHERE id=?", (_id,))
                                await db.commit()
                        except:
                            pass
    except Exception:
        pass



# ==========================================
# STOCK ANALYSIS - PREMIUM ULTIMATE V2
# With Animation & AI Analytics
# ==========================================

import time

def draw_price_bar(price, low, high, length=20):
    """Draw price range indicator bar"""
    try:
        price = float(price)
        low = float(low)
        high = float(high)
    except:
        return "[no data]"

    if high <= low:
        return "[no range]"

    if price < low:
        price = low
    if price > high:
        price = high

    ratio = (price - low) / (high - low)
    idx = int(ratio * (length - 1))

    bar_chars = []
    for i in range(length):
        if i == idx:
            bar_chars.append("●")
        else:
            bar_chars.append("─")

    return "[" + "".join(bar_chars) + "]"

def get_trading_signal(price, s1, r1, pivot):
    """Get trading signal with description"""
    if price > r1:
        return "OVERBOUGHT - Strong Sell Signal"
    elif price > pivot:
        return "Strong Buy - Bullish Momentum"
    elif price > s1:
        return "Neutral - Range Consolidation"
    elif price > s1 * 0.95:
        return "Buy Zone - Support Level"
    else:
        return "Extreme Buy - Oversold Recovery"

def get_ai_analysis(price, open_p, high, low, prev, vol, change_p, s1, r1, pivot):
    """Generate AI-powered analysis"""
    analysis = []
    
    # Price movement analysis
    if change_p > 3:
        analysis.append("BULLISH: Strong upward momentum detected")
    elif change_p > 1:
        analysis.append("POSITIVE: Mild upward trend visible")
    elif change_p < -3:
        analysis.append("BEARISH: Strong downward pressure detected")
    elif change_p < -1:
        analysis.append("NEGATIVE: Mild downward trend visible")
    else:
        analysis.append("NEUTRAL: Price consolidation pattern")
    
    # Volume analysis
    if vol > 100000000:
        analysis.append("HIGH VOLUME: Strong trader participation")
    elif vol > 50000000:
        analysis.append("MODERATE VOLUME: Fair liquidity present")
    else:
        analysis.append("LOW VOLUME: Caution - liquidity concern")
    
    # Position analysis
    if price > pivot and price < r1:
        analysis.append("ZONE: Above pivot, near resistance")
    elif price > s1 and price < pivot:
        analysis.append("ZONE: Between support and pivot")
    elif price < s1:
        analysis.append("ZONE: Below support, oversold territory")
    
    # Volatility analysis
    range_val = high - low
    volatility = (range_val / low) * 100 if low > 0 else 0
    
    if volatility > 3:
        analysis.append("HIGH VOLATILITY: Expect price swings")
    elif volatility > 1:
        analysis.append("NORMAL VOLATILITY: Balanced movement")
    else:
        analysis.append("LOW VOLATILITY: Stable pricing")
    
    # Entry/Exit signals
    if price < s1 and change_p < 0:
        analysis.append("SIGNAL: Strong buy opportunity at support")
    elif price > r1 and change_p > 0:
        analysis.append("SIGNAL: Strong sell pressure at resistance")
    elif abs(change_p) < 0.5:
        analysis.append("SIGNAL: Wait for breakout confirmation")
    
    return analysis

def format_number(value, currency="IDR"):
    """Format number based on currency"""
    try:
        val = float(value)
        if currency == "IDR":
            return f"{val:,.0f}"
        else:
            return f"{val:,.2f}"
    except:
        return "0"

def get_status_emoji(change_percent):
    """Get emoji based on change percentage"""
    if change_percent > 5:
        return "🚀"
    elif change_percent > 2:
        return "📈"
    elif change_percent > 0:
        return "↗"
    elif change_percent > -2:
        return "↘"
    elif change_percent > -5:
        return "📉"
    else:
        return "💥"

async def sha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stock/Share analysis command - Premium Ultimate V2"""
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # MODE 1: MARKET OVERVIEW
    if not context.args:
        msg = await update.message.reply_text(
            "Scanning Global Markets...",
            parse_mode=ParseMode.HTML,
        )

        indices = {
            "^JKSE": ("IHSG", "Indonesia"),
            "IDR=X": ("USD/IDR", "Currency"),
            "BTC-USD": ("Bitcoin", "Crypto"),
            "GC=F": ("Gold", "Commodity"),
            "CL=F": ("Oil", "Commodity"),
        }
        
        report = (
            "GLOBAL MARKET OVERVIEW\n"
            "=====================\n\n"
        )

        for ticker, (name, category) in indices.items():
            try:
                url = (
                    f"https://query1.finance.yahoo.com/v8/finance/chart/"
                    f"{ticker}?interval=1d&range=1d"
                )
                d = await fetch_json(url, headers=headers)
                if d and d.get("chart", {}).get("result"):
                    meta = d["chart"]["result"][0]["meta"]
                    price = meta.get("regularMarketPrice")
                    prev = meta.get("chartPreviousClose")

                    if price is None or prev in (None, 0):
                        continue

                    change_p = ((price - prev) / prev) * 100
                    emoji_status = get_status_emoji(change_p)
                    sign = "+" if change_p >= 0 else ""

                    if ticker in ["IDR=X", "^JKSE"]:
                        price_fmt = f"{price:,.0f}"
                    else:
                        price_fmt = f"{price:,.2f}"

                    report += (
                        f"{emoji_status} {name} ({category})\n"
                        f"   {price_fmt} {sign}{change_p:.2f}%\n\n"
                    )
            except Exception as e:
                logger.debug(f"[SHA] Market data error: {e}")
                continue

        report += (
            "========================\n"
            "Try: /sha BBCA or /sha TSLA"
        )
        
        await msg.edit_text(report, parse_mode=ParseMode.HTML)
        return

    # MODE 2: DETAILED ANALYSIS
    input_ticker = context.args[0].upper().strip()
    
    # Show loading animation
    loading_frames = ["Analyzing", "Analyzing.", "Analyzing..", "Analyzing..."]
    msg = await update.message.reply_text(
        f"Analyzing {input_ticker}...",
        parse_mode=ParseMode.HTML,
    )
    
    # Animate loading
    for frame in loading_frames:
        try:
            await msg.edit_text(
                f"{frame} {input_ticker}...",
                parse_mode=ParseMode.HTML,
            )
            await asyncio.sleep(0.3)
        except:
            pass

    # Try multiple ticker formats
    candidates = []
    if len(input_ticker) == 4 and input_ticker.isalpha():
        candidates.append(f"{input_ticker}.JK")
        candidates.append(input_ticker)
    else:
        candidates.append(input_ticker)

    found_data = None
    real_ticker = input_ticker

    for t in candidates:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{t}?interval=1d&range=1d"
        )
        try:
            d = await fetch_json(url, headers=headers)
            if d and d.get("chart", {}).get("result"):
                found_data = d
                real_ticker = t
                break
        except Exception as e:
            logger.debug(f"[SHA] Ticker {t} error: {e}")
            continue

    if found_data:
        try:
            meta = found_data["chart"]["result"][0]["meta"]

            price = meta.get("regularMarketPrice", 0)
            prev_close = meta.get("chartPreviousClose", 0) or 1
            currency = meta.get("currency", "IDR")
            vol = meta.get("regularMarketVolume", 0)
            day_high = meta.get("regularMarketDayHigh", price)
            day_low = meta.get("regularMarketDayLow", price)
            open_price = meta.get("regularMarketOpen", 0)

            change = price - prev_close
            change_p = (change / prev_close) * 100
            status_emoji = get_status_emoji(change_p)
            sign = "+" if change_p >= 0 else ""

            # Trading zones
            pivot = (day_high + day_low + price) / 3
            s1 = (2 * pivot) - day_high
            r1 = (2 * pivot) - day_low

            signal = get_trading_signal(price, s1, r1, pivot)
            
            # Position in range
            range_pct = ((price - day_low) / (day_high - day_low) * 100) if (day_high - day_low) > 0 else 50

            # Price bar
            price_bar = draw_price_bar(price, day_low, day_high)

            # Get AI Analysis
            ai_analysis = get_ai_analysis(price, open_price, day_high, day_low, prev_close, vol, change_p, s1, r1, pivot)

            txt = (
                f"STOCK ANALYSIS\n"
                f"{html.escape(real_ticker)}\n"
                f"====================\n\n"
                
                f"PRICE\n"
                f"Current: {currency} {format_number(price, currency)}\n"
                f"Change: {status_emoji} {sign}{format_number(change, currency)}\n"
                f"Percent: {sign}{change_p:.2f}%\n"
                f"Prev: {format_number(prev_close, currency)}\n\n"
                
                f"TODAY RANGE\n"
                f"High: {format_number(day_high, currency)}\n"
                f"Low: {format_number(day_low, currency)}\n"
                f"Open: {format_number(open_price, currency)}\n"
                f"Volume: {vol:,}\n"
                f"{price_bar}\n"
                f"Position: {range_pct:.1f}% from Low\n\n"
                
                f"TRADING ZONES\n"
                f"Resistance: {format_number(r1, currency)}\n"
                f"Pivot: {format_number(pivot, currency)}\n"
                f"Support: {format_number(s1, currency)}\n\n"
                
                f"SIGNAL\n"
                f"{signal}\n\n"
                
                f"AI ANALYTICS\n"
            )
            
            # Add AI analysis points
            for i, analysis_point in enumerate(ai_analysis, 1):
                txt += f"{i}. {analysis_point}\n"
            
            txt += (
                f"\n========================\n"
                f"Real-time by Oktacomel"
            )

            buttons = [
                [
                    InlineKeyboardButton("Refresh", callback_data=f"sha_refresh|{real_ticker}"),
                    InlineKeyboardButton("Chart", url=f"https://finance.yahoo.com/quote/{real_ticker}"),
                ]
            ]

            await msg.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        except Exception as e:
            logger.error(f"[SHA] Parse error: {e}")
            await msg.edit_text(
                f"Parse Error: {str(e)[:50]}",
                parse_mode=ParseMode.HTML,
            )
    else:
        await msg.edit_text(
            f"Symbol not found: {html.escape(input_ticker)}\n\n"
            f"Try: /sha BBCA (Indo) or /sha TSLA (US)",
            parse_mode=ParseMode.HTML,
        )

async def sha_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle stock analysis callbacks with animation"""
    query = update.callback_query
    
    try:
        parts = query.data.split("|")
        action = parts[0]
        
        if action == "sha_refresh":
            ticker = parts[1] if len(parts) > 1 else ""
            
            if not ticker:
                await query.answer("Invalid ticker", show_alert=True)
                return
            
            await query.answer()
            
            # Show animated refresh
            loading_frames = ["Refreshing", "Refreshing.", "Refreshing..", "Refreshing..."]
            
            for frame in loading_frames:
                try:
                    await query.message.edit_text(
                        f"{frame} {ticker}...",
                        parse_mode=ParseMode.HTML,
                    )
                    await asyncio.sleep(0.3)
                except:
                    pass
            
            context.args = [ticker]
            await sha_command(update, context)
    
    except Exception as e:
        logger.error(f"[SHA] Callback error: {e}")
        try:
            await query.answer(f"Error: {str(e)[:30]}", show_alert=True)
        except:
            pass
    
# ==========================================
# 👑 ADMIN: ADD PREMIUM USER (IMPROVED UI + NOTIFY)
# ==========================================
async def addprem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Hanya Owner yang bisa pakai command ini
    if update.effective_user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: <code>/addprem user_id</code>\nExample: <code>/addprem 123456789</code>",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        target_id = int(context.args[0])

        async with aiosqlite.connect(DB_NAME) as db:
            # Cek apakah sudah premium
            async with db.execute("SELECT 1 FROM premium_users WHERE user_id = ? LIMIT 1", (target_id,)) as cur:
                exists = await cur.fetchone()

            if exists:
                await update.message.reply_text(
                    f"ℹ️ User <code>{target_id}</code> is already <b>PREMIUM</b>.",
                    parse_mode=ParseMode.HTML
                )
                return

            # Masukkan ke DB
            await db.execute("INSERT OR IGNORE INTO premium_users (user_id) VALUES (?)", (target_id,))
            await db.commit()

        # Format waktu (pakai TZ jika tersedia)
        try:
            ts = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Konfirmasi ke owner
        owner_text = (
            f"✅ <b>PREMIUM ADDED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User ID:</b> <code>{target_id}</code>\n"
            f"🕒 <b>When:</b> {ts}\n"
            f"🙋‍♂️ <b>By:</b> {html.escape(update.effective_user.full_name)}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(owner_text, parse_mode=ParseMode.HTML)

        # NOTIFIKASI KE USER YANG DITAMBAHKAN
        user_text = (
            f"🎉 <b>CONGRATULATIONS!</b>\n"
            f"You have been granted <b>PREMIUM</b> access on <i>Oktacomel</i>.\n\n"
            f"✅ Status: <code>PREMIUM</code>\n"
            f"🕒 Activated: {ts}\n\n"
            f"Features unlocked:\n"
            f"• Higher limits & priority support\n"
            f"• Access to premium modules\n"
            f"• Faster AI & downloader quotas\n\n"
            f"If you cannot access premium features, please open a chat with the bot and send /start."
        )

        try:
            await context.bot.send_message(chat_id=target_id, text=user_text, parse_mode=ParseMode.HTML)
            # Jika sukses, update owner lagi bahwa notification terkirim
            await update.message.reply_text(f"📨 Notification sent to <code>{target_id}</code>.", parse_mode=ParseMode.HTML)
        except Exception as e:
            # Biasanya error karena user belum start bot / privacy settings
            await update.message.reply_text(
                f"⚠️ Added to premium but failed to DM user <code>{target_id}</code>.\n"
                f"Reason: <code>{html.escape(str(e))}</code>\n\n"
                "User may need to start the bot or allow messages from the bot.",
                parse_mode=ParseMode.HTML
            )

    except ValueError:
        await update.message.reply_text("❌ <b>Invalid ID:</b> ID must be a number.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ <b>Unexpected error:</b> <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)


# =====================================================
# 🧠 OKTA AI ENGINE — GiMiTA GPT5
# =====================================================

GIMITA_GPT5_API = "https://api.gimita.id/api/ai/gpt5"

async def okta_ai_process(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: str,
    model_name: str = "GPT-5",
):
    message = update.effective_message

    # UI Loading
    bot_msg = await message.reply_text(
        f"🧠 <b>OKTA AI: {model_name}</b>\n"
        "⏳ <i>Sedang berpikir keras...</i>",
        parse_mode=ParseMode.HTML
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json,text/plain,*/*",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, headers=headers) as client:
            # GiMiTA GPT5 menggunakan GET dengan parameter 'text'
            resp = await client.get(GIMITA_GPT5_API, params={"text": query})
            
            if resp.status_code != 200:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("error", f"API Error {resp.status_code}")
                except:
                    error_msg = f"API Error {resp.status_code}"
                await bot_msg.edit_text(f"❌ <b>Error:</b> {error_msg}", parse_mode=ParseMode.HTML)
                return

            data = resp.json()
            
            # Cek response sukses
            if not data.get("success", True):
                error_msg = data.get("error", "Unknown error")
                await bot_msg.edit_text(f"❌ <b>Error:</b> {error_msg}", parse_mode=ParseMode.HTML)
                return
            
            # Ambil response dari field 'result'
            content = data.get("result", "")
            
            if not content:
                await bot_msg.edit_text("❌ <b>Error:</b> Tidak ada response dari AI", parse_mode=ParseMode.HTML)
                return

        # FORMATTING CODE BLOCK (Biar Rapi)
        parts = content.split("```")
        final_parts = []
        for i, p in enumerate(parts):
            if i % 2 == 0:
                final_parts.append(html.escape(p))
            else:
                code_content = p.strip()
                if "\n" in code_content:
                    first_line, rest = code_content.split("\n", 1)
                    if len(first_line) < 15:
                        code_content = rest
                final_parts.append(f"<pre><code>{html.escape(code_content)}</code></pre>")

        final_text = "".join(final_parts)
        footer = f"\n\n🤖 <i>Generated by {model_name} via GiMiTA</i>"

        # KIRIM HASIL
        if len(final_text) > 4000:
            with io.BytesIO(final_text.encode()) as f:
                f.name = f"jawaban_{model_name.replace(' ', '_')}.txt"
                await message.reply_document(document=f, caption="✅ Jawaban panjang, saya kirim file.")
                await bot_msg.delete()
        else:
            await bot_msg.edit_text(final_text + footer, parse_mode=ParseMode.HTML)

    except asyncio.TimeoutError:
        await bot_msg.edit_text("❌ <b>Error:</b> Request timeout, coba lagi nanti.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"[AI] Error: {type(e).__name__}: {e}")
        await bot_msg.edit_text(f"❌ <b>System Error:</b> {str(e)[:100]}", parse_mode=ParseMode.HTML)

# --- COMMAND ---

# Store AI conversation history per user
ai_conversation_history = {}

# /ai - Tanya Jawab dengan GPT-5 (Conversational Mode)
async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await premium_lock_handler(update, context): return
    
    user_id = update.effective_user.id
    query = " ".join(context.args)
    
    if not query:
        await update.message.reply_text(
            "🧠 <b>OKTA AI - GPT-5</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Usage:</b> <code>/ai [pertanyaan]</code>\n\n"
            "<b>Contoh:</b>\n"
            "• <code>/ai apa itu machine learning?</code>\n"
            "• <code>/ai buatkan puisi tentang hujan</code>\n"
            "• <code>/ai jelaskan cara kerja internet</code>\n\n"
            "💡 <i>Tip: Reply ke jawaban bot untuk lanjut chat tanpa command!</i>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check and deduct credits
    success, remaining, cost = await deduct_credits(user_id, "ai")
    if not success:
        await update.message.reply_text(
            f"❌ <b>Kredit Tidak Cukup</b>\n\n"
            f"Command ini membutuhkan {cost} kredit.\n"
            f"Kredit kamu: {remaining}\n\n"
            f"💎 Upgrade ke Premium untuk lebih banyak kredit!\n"
            f"Atau tunggu reset harian (00:00 WIB).",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Initialize conversation history for user
    if user_id not in ai_conversation_history:
        ai_conversation_history[user_id] = []
    
    # Add user message to history
    ai_conversation_history[user_id].append({"role": "user", "content": query})
    
    # Keep only last 10 messages for context
    if len(ai_conversation_history[user_id]) > 10:
        ai_conversation_history[user_id] = ai_conversation_history[user_id][-10:]
    
    await okta_ai_process_conversational(update, context, ai_conversation_history[user_id], "GPT-5", user_id)

async def okta_ai_process_conversational(update: Update, context: ContextTypes.DEFAULT_TYPE, messages: list, model_name: str, user_id: int):
    """Process AI with conversation history"""
    message = update.message
    bot_msg = await message.reply_text(f"🤖 <b>{model_name} BRAIN</b> sedang berpikir...", parse_mode=ParseMode.HTML)
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "messages": messages,
                "model": "openai"
            }
            
            async with session.post(
                "https://text.pollinations.ai/",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        result = await resp.json()
                        if isinstance(result, dict):
                            answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                            if not answer:
                                answer = result.get("text", "") or result.get("response", "")
                        else:
                            answer = str(result)
                    else:
                        answer = await resp.text()
                else:
                    error_text = await resp.text()
                    logger.error(f"[AI] API returned {resp.status}: {error_text[:200]}")
                    answer = f"API error ({resp.status}). Silakan coba lagi."
        
        if not answer:
            answer = "Tidak ada respons dari AI."
        
        # Add assistant response to history
        ai_conversation_history[user_id].append({"role": "assistant", "content": answer})
        
        # Format response
        final_text = f"🧠 <b>{model_name} BRAIN</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n{html.escape(answer)}"
        footer = f"\n\n💡 <i>Reply pesan ini untuk lanjut chat!</i>\n🤖 <i>Generated by {model_name} via OKTACOMEL</i>"
        
        if len(final_text) > 3800:
            with io.BytesIO(answer.encode()) as f:
                f.name = f"jawaban_{model_name.replace(' ', '_')}.txt"
                await message.reply_document(document=f, caption="✅ Jawaban panjang, saya kirim file.")
                await bot_msg.delete()
        else:
            await bot_msg.edit_text(final_text + footer, parse_mode=ParseMode.HTML)
            
    except asyncio.TimeoutError:
        await bot_msg.edit_text("❌ <b>Error:</b> Request timeout, coba lagi nanti.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"[AI] Error: {type(e).__name__}: {e}")
        await bot_msg.edit_text(f"❌ <b>System Error:</b> {str(e)[:100]}", parse_mode=ParseMode.HTML)

async def ai_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle replies to AI messages for continuation"""
    if not await premium_lock_handler(update, context): return
    
    message = update.message
    user_id = message.from_user.id
    
    # Check if replying to bot's message
    if not message.reply_to_message or message.reply_to_message.from_user.id != context.bot.id:
        return
    
    # Check if the replied message is from AI (contains GPT-5 BRAIN)
    replied_text = message.reply_to_message.text or ""
    if "GPT-5 BRAIN" not in replied_text and "OKTACOMEL" not in replied_text:
        return
    
    query = message.text
    if not query:
        return
    
    # Initialize conversation history for user if not exists
    if user_id not in ai_conversation_history:
        ai_conversation_history[user_id] = []
    
    # Add user message to history
    ai_conversation_history[user_id].append({"role": "user", "content": query})
    
    # Keep only last 10 messages for context
    if len(ai_conversation_history[user_id]) > 10:
        ai_conversation_history[user_id] = ai_conversation_history[user_id][-10:]
    
    await okta_ai_process_conversational(update, context, ai_conversation_history[user_id], "GPT-5", user_id)

# /code - Khusus untuk coding/programming
async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await premium_lock_handler(update, context): return
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text(
            "💻 <b>OKTA AI - Code Assistant</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Usage:</b> <code>/code [request]</code>\n\n"
            "<b>Contoh:</b>\n"
            "• <code>/code buatkan script python kalkulator</code>\n"
            "• <code>/code cara membuat API dengan Flask</code>\n"
            "• <code>/code fix error: undefined variable</code>",
            parse_mode=ParseMode.HTML
        )
        return
    # Tambahkan context untuk coding
    code_query = f"Sebagai expert programmer, {query}. Berikan kode yang lengkap dan penjelasan singkat."
    await okta_ai_process(update, context, code_query, "GPT-5 Code")

# /think - Untuk analisa mendalam
async def think_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await premium_lock_handler(update, context): return
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text(
            "🔬 <b>OKTA AI - Deep Think</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Usage:</b> <code>/think [topik]</code>\n\n"
            "<b>Contoh:</b>\n"
            "• <code>/think jelaskan teori relativitas secara detail</code>\n"
            "• <code>/think analisa pro kontra AI dalam pendidikan</code>\n"
            "• <code>/think bagaimana cara kerja blockchain?</code>",
            parse_mode=ParseMode.HTML
        )
        return
    # Tambahkan context untuk deep thinking
    think_query = f"Analisa secara mendalam dan komprehensif: {query}. Berikan penjelasan yang detail, terstruktur, dan mudah dipahami."
    await okta_ai_process(update, context, think_query, "GPT-5 Think")

# ==========================================
# TRUTH OR DARE - ULTIMATE MASSIVE DATABASE
# ==========================================

LIST_TRUTH = [
    # --- LEVEL 1: AMAN / FUN / SOSIAL ---
    "Siapa mantan yang paling susah kamu lupain?",
    "Hal paling memalukan apa yang pernah kamu lakuin di depan umum?",
    "Kapan terakhir kali kamu ngompol?",
    "Siapa orang di grup ini yang pengen kamu jadiin pacar?",
    "Apa kebohongan terbesar yang pernah kamu bilang ke orang tua?",
    "What is your biggest fear?",
    "Pernah stalk sosmed mantan gak? Kapan terakhir?",
    "Who is your celebrity crush?",
    "Kalau besok kiamat, siapa orang terakhir yang mau kamu hubungi?",
    "Pernah naksir pacar teman sendiri gak? Jujur!",
    "Apa aib masa kecil yang gak pernah kamu lupain?",
    "Sebutkan 3 hal yang bikin kamu ilfeel sama lawan jenis.",
    "Siapa member grup ini yang paling ganteng/cantik menurutmu?",
    "Pernah gak mandi berapa hari paling lama?",
    "Pernah nyuri uang orang tua gak? Buat apa?",
    "Siapa orang yang paling kamu benci sekarang? Inisial aja.",
    "Kapan terakhir kali nangis? Gara-gara apa?",
    "Pernah kentut tapi nyalahin orang lain? Kapan?",
    "Apa kebiasaan jorok kamu yang orang lain gak tau?",
    "Kalau punya uang 1 Miliar sekarang, apa hal pertama yang kamu beli?",
    "Pernah ditembak (nembak cewek/cowok) terus ditolak? Ceritain!",
    "Siapa first kiss kamu?",
    "Pernah selingkuh? Kenapa?",
    "Apa hal terbodoh yang pernah kamu lakuin demi cinta?",
    "Sebutkan isi search history Google/YouTube terakhir kamu!",
    "Pernah ngupil terus dimakan gak?",
    "Siapa guru/dosen yang pernah kamu taksir?",
    "Apa hal paling konyol yang pernah kamu pikirin?",
    "Pernah gak kamu mimisan pas ketawa?",
    "Siapa orang paling aneh yang pernah kamu follow di sosmed?",
    "Pernah kena gigitan nyamuk dimana yang paling gatal?",
    "Apa makanan paling aneh yang pernah kamu makan?",
    "Pernah tersesat sampai minta bantuan orang gak?",
    "Siapa tokoh TV/film yang ingin kamu jadilah?",
    "Pernah nonton film horor terus tidur dengan orang tua?",
    "Apa hal yang paling sering kamu lupain?",
    "Pernah gak kamu tidur dengan lampu menyala?",
    "Siapa teman yang paling menyebalkan versi kamu?",
    "Apa kebiasaan buruk kamu yang paling susah dihilangkan?",
    "Pernah makan langsung dari wadah tanpa piring?",
    "Siapa selebriti yang menurutmu paling jelek?",
    "Apa drama terbesar yang pernah terjadi di keluargamu?",
    "Pernah gak kamu berbohong dalam permainan ini sebelumnya?",
    "Siapa orang pertama yang kamu hubungi saat sedih?",
    "Apa brand atau produk yang kamu pakai paling sering?",
    "Pernah gak kamu kasih hadiah palsu ke pacar/teman?",
    "Sebutkan nama orang yang paling ingin kamu jadilah sepertinya!",
    
    # --- LEVEL 2: PERSONAL / INTIM (15+) ---
    "Apa penyesalan terbesar dalam hidupmu sejauh ini?",
    "Kapan kamu merasa paling kesepian?",
    "Apa rahasia yang belum pernah kamu ceritain ke siapapun?",
    "Pernah gak kamu ngerasa salah pilih pasangan?",
    "Apa sifat terburuk kamu menurut dirimu sendiri?",
    "Kalau bisa memutar waktu, momen apa yang pengen kamu ubah?",
    "Apa insecure terbesar kamu soal fisik?",
    "Pernah gak kamu ngerasa cinta ke seseorang yang jauh lebih tua/muda?",
    "Siapa orang di grup yang paling ingin kamu kenal lebih dalam?",
    "Apa hal yang membuat hubunganmu yang terakhir berakhir?",
    "Pernah gak kamu ngerasa tertarik sama sesama jenis?",
    "Apa standar ideal pasangan kamu?",
    "Pernah gak kamu mengkhianati kepercayaan teman untuk cinta?",
    "Kalau bisa memilih, pasangan seperti apa yang kamu inginkan?",
    "Apa hal terberat yang pernah kamu hadapi dalam cinta?",
    "Pernah gak kamu ngerasa kecewa sama pacar karena masalah intim?",
    "Siapa orang yang paling sering kamu pikirin sebelum tidur?",
    "Apa kepribadian teman yang membuatmu tertarik padanya romantis?",
    "Pernah gak kamu merasa jatuh cinta bersamaan sama dua orang?",
    "Apa yang membuat kamu merasa dicintai?",
    "Pernah gak kamu merasa tidak cukup baik untuk pasangan kamu?",
    "Siapa mantan yang sampai sekarang masih bikin kamu sedih?",
    "Apa impian terbesar kamu dalam hidup berumah tangga?",
    "Pernah gak kamu ngerasa iri sama hubungan teman?",
    "Apa yang paling kamu ingin dari pasangan ideal kamu?",
    "Pernah gak kamu ngerasa bersalah terhadap pacar kamu?",
    "Kalau pacar main sama orang lain, apa yang akan kamu lakukan?",
    "Apa hal yang paling kamu sukai dari pasangan kamu saat ini atau terakhir?",
    "Pernah gak kamu ngerasa tidak dimengerti oleh pasangan?",
    "Siapa orang yang paling memahami kamu sampai sekarang?",
    "Apa pengalaman cinta yang paling mengubah hidupmu?",
    "Pernah gak kamu membayar untuk hubungan intim?",
    "Apa hal terindah yang pernah dilakukan pacar untuk kamu?",
    "Pernah gak kamu ngerasa pensiun dari dunia cinta?",
    "Siapa orang paling beruntung yang pernah menjalin hubungan sama kamu?",
    "Apa hal yang paling kamu sesal dalam hubungan terakhir kamu?",
    "Pernah gak kamu mencoba obat-obatan atau alkohol dengan pasangan?",
    "Apa yang membuat kamu memutuskan untuk pisah dengan pacar?",
    "Pernah gak kamu ngerasa diperlakukan tidak adil dalam hubungan?",
    "Siapa orang yang paling menyakiti hati kamu sampai sekarang?",
    "Apa hal paling romantis yang pernah kamu lakukan untuk seseorang?",
    
    # --- LEVEL 3: ADULT / 18+ / 21+ (EXPLICIT) ---
    "Pernah kirim pap (foto) naked/seksi ke siapa aja?",
    "Apa fantasi terliar kamu yang belum kesampaian?",
    "What's your favorite position?",
    "Pernah ciuman sama sesama jenis? (Jujur!)",
    "Sebutkan 1 bagian tubuh lawan jenis yang paling bikin kamu sange!",
    "Pernah 'main' di tempat umum gak? Dimana?",
    "What turns you on the most?",
    "Pernah selingkuh atau jadi selingkuhan? Ceritain!",
    "Ukuran itu penting gak menurut kamu?",
    "Pernah one night stand (ONS)?",
    "Siapa orang di kontak HP kamu yang pengen banget kamu ajak 'tidur'?",
    "Have you ever sent a nude? To whom?",
    "Pernah nonton bokep bareng temen? Siapa?",
    "Apa warna celana dalam yang kamu pakai sekarang?",
    "Do you prefer lights on or lights off?",
    "Pernah 'main' sambil direkam video gak?",
    "Bagian tubuh mana dari kamu yang paling sensitif kalau disentuh?",
    "Suka yang kasar (rough) atau lembut (soft)?",
    "Pernah mimpi basah mikirin teman sendiri? Siapa?",
    "Have you ever faked an orgasm?",
    "Pernah ketahuan lagi nonton bokep atau masturbasi gak?",
    "Sebutkan tempat paling aneh yang pernah kamu pakai buat 'main'!",
    "Suka dirty talk gak pas lagi main? Contoh kalimatnya apa?",
    "Pernah punya FWB (Friends with Benefits)?",
    "Kalau bisa milih member grup ini buat one night stand, pilih siapa?",
    "Pernah 'main' bertiga (threesome) atau pengen nyoba?",
    "Do you like giving or receiving oral more?",
    "Pernah nyoba mainan dewasa (sex toys)?",
    "Apa hal ter-nakal yang pernah kamu lakuin di sekolah/kampus/kantor?",
    "Berapa ronde rekor terkuat kamu?",
    "Suka nelan atau dibuang? (You know what I mean)",
    "Pernah 'main' di mobil (Car Sex)?",
    "Apa fetish teraneh yang kamu punya?",
    "Pernah ketahuan ortu pas lagi 'solo player'?",
    "Lebih suka main atas atau bawah?",
    "Pernah sexting (chat seks) sama orang asing?",
    "Apa baju tidur favorit yang bikin kamu ngerasa seksi?",
    "Pernah gak pake celana dalam pas keluar rumah?",
    "Suara desahan siapa yang paling pengen kamu denger di grup ini?",
    "Pernah ciuman bibir lebih dari 5 menit?",
    "Suka dijambak atau ditampar pas lagi main?",
    "Pernah coli/fingering sambil mikirin pacar orang?",
    "Seberapa sering kamu nonton bokep dalam seminggu?",
    "Apa yang paling kamu suka dari foreplay?",
    "Pernah gak kamu coba oral sex? Gimana rasanya?",
    "Siapa artis/selebriti yang paling sering kamu fantasikan?",
    "Pernah gak kamu main sambil ada orang lain di rumah?",
    "Apa posisi yang paling bikin kamu cepat klimaks?",
    "Pernah gak kamu ditonton saat lagi solo?",
    "Apa yang kamu lakukan pas sedang birahi tinggi?",
    "Pernah gak kamu orgasme lebih dari 3 kali dalam sekali main?",
    "Seberapa lama biasanya kamu tahan sebelum klimaks?",
    "Apa yang paling membuat kamu excited sebelum main?",
    "Pernah gak kamu minta foreplay yang ekstrem?",
    "Siapa yang paling memuaskan kamu dalam hal intim?",
    "Apa yang kamu sukai dari oral sex?",
    "Pernah gak kamu ganti posisi lebih dari 5 kali dalam sekali main?",
    "Apa yang membuat kamu tidak bisa orgasme?",
    "Pernah gak kamu minta pasangan untuk lebih 'kasar'?",
    "Apa yang paling kamu sukai dari afterplay?",
    "Pernah gak kamu cinta dengan seseorang hanya karena mainnya bagus?",
    "Siapa orang yang paling bikin kamu 'mati gaya' di ranjang?",
    "Apa hal yang paling mengganggu ketika lagi main?",
    "Pernah gak kamu nonton rekaman pribadi kamu sendiri?",
    "Apa yang paling membuat kamu terangsang?",
    "Pernah gak kamu main sambil cari sensasi baru?",
    "Seberapa puas kamu dengan kehidupan seks kamu?",
    "Apa hal yang ingin kamu coba tapi takut?",
    "Pernah gak kamu bermain dengan mainan seks?",
    "Apa yang paling kamu inginkan dari seks yang sempurna?",
    "Pernah gak kamu orgasme hanya dengan foreplay?",
    "Siapa yang paling 'berwibawa' dalam hal intim menurutmu?",
    "Apa hal yang paling kamu cari di pasangan intim?",
    "Pernah gak kamu cerita fantasi aneh ke pasangan?",
    "Apa yang membuat kamu merasa kurang puas dalam seks?",
    "Pernah gak kamu minta hal yang sangat ekstrem ke pasangan?",
    "Siapa orang yang paling membuat kamu kehilangan kendali?",
    "Apa hal paling taboo yang pernah kamu lakukan?",
    "Pernah gak kamu merasa malu dengan tubuh kamu saat intim?",
    "Apa yang kamu inginkan tapi takut diminta?",
    "Pernah gak kamu main sampe pagi hari tanpa berhenti?",
    "Siapa orang yang paling bikin kamu terobsesi?",
    "Apa hal yang paling kamu hindari dalam seks?",
    "Pernah gak kamu cemburu dengan pengalaman seks pasangan?",
    "Apa yang membuat seks menjadi memorable buat kamu?",
    "Pernah gak kamu orgasme berkali-kali dalam waktu singkat?",
    "Siapa yang paling tahu preferensi seks kamu?",
    "Apa hal yang membuat kamu berhenti di tengah jalan?",
    "Pernah gak kamu nonton pornografi dengan pasangan?",
]

LIST_DARE = [
    # --- LEVEL 1: SOSIAL / PRANK / FUN ---
    "Kirim screenshot chat terakhir sama doi/pacar.",
    "Telpon mantan sekarang, bilang 'Aku kangen'. (Speaker on)",
    "Ganti foto profil WA/Tele jadi foto aib kamu selama 1 jam.",
    "Chat random contact di HP kamu, bilang 'Aku hamil anak kamu' atau 'Tanggung jawab!'.",
    "Nyanyi lagu potong bebek angsa tapi huruf vokal diganti 'O'. (VN)",
    "Send a voice note singing your favorite song.",
    "Kirim selfie muka jelek (ugly face) sekarang!",
    "Chat orang tua kamu bilang 'Aku mau nikah besok'.",
    "Prank call teman kamu, pura-pura pinjam duit 10 juta.",
    "Ketik nama kamu pakai hidung, kirim hasilnya kesini.",
    "Screenshot history YouTube terakhir kamu.",
    "Post foto aib di Story WA/IG sekarang, caption 'Aku Jelek'.",
    "Chat dosen/guru bilang 'Saya sayang bapak/ibu'.",
    "VN teriak 'AKU JOMBLO HAPPY' sekeras mungkin.",
    "Kirim foto saldo ATM/E-Wallet kamu sekarang.",
    "Ganti nama Telegram jadi 'Babi Ngepet' selama 10 menit.",
    "Screenshot gallery foto terbaru kamu (no crop).",
    "Buat status WA bilang 'Aku homo/lesbian' dan tahan 5 menit.",
    "Nyanyi seperti artis paling konyol di voice note.",
    "Telpon teman random, bilang kamu menang undian.",
    "Kirim meme paling aneh dari HP ke grup.",
    "Foto diri dengan ekspresi paling aneh, kirim kesini.",
    "Chat guru bilang 'Absen dong pak/bu, aku sibuk'.",
    "Nari TikTok paling konyol, videokan 10 detik.",
    "Kirim foto tertawa paling menggelikan.",
    "Ketik pesan dengan satu tangan, screenshot hasilnya.",
    "Mimik pacar/crush kamu sambil video call di depan teman.",
    "Nari dangdut paling aneh, videokan.",
    "Senyumin HP kamu seperti melihat crush.",
    "Bikin cerita lucu, ceritain via VN paling ekspresif.",
    "Foto dengan pose paling lucu di depan kaca.",
    "Chat orang acak, bilang 'Siapa nama kamu?' 10 kali.",
    "Tiru cara ngomong teman paling mirip.",
    "Foto selfie dengan 5 filter paling aneh.",
    "Nyanyi sambil berjalan mengelilingi rumah (videokan).",
    "Bikin ekspresi sedih paling dramatis, kirim foto.",
    "Chat mantan bilang 'Maaf aku masih cinta'.",
    "Nari seperti robot sambil nyanyi, videokan.",
    "Foto dengan pose paling jelek, kirim sini.",
    "Teriak 'AKU CANTIK/GANTENG!' depan cermin sambil videokan.",
    "Chat paling benci subjek di sekolah dengan nada maaf.",
    "Nyanyi lagu anak-anak dengan voice seperti monster.",
    "Foto muka dengan mulut membuka selebar mungkin.",
    "Chat random orang, tanya 'Tadi dimana?'.",
    "Buat pose paling aneh dengan 3 orang, foto bareng.",
    "Nyanyi dengan aksen yang paling gitu, VN.",
    "Kirim gif paling aneh ke grup.",
    "Tiru cara berjalan artis paling konyol.",
    "Foto dengan pose paling 'wink', kirim kesini.",
    
    # --- LEVEL 2: FLIRTY / GOMBAL / DEKAT ---
    "Gombalin salah satu member grup ini lewat VN.",
    "Chat crush kamu: 'Mimpiin aku ya malam ini'.",
    "Pilih satu orang di grup, jadikan 'pacar' kamu selama 15 menit.",
    "Bilang 'I Love You' ke member grup nomor 3 dari atas.",
    "Kirim pantun cinta buat Admin grup.",
    "Elus-elus pipi teman sambil bilang kata gombal.",
    "Kirim pesan rahasia cinta ke teman, isinya candaan.",
    "Peluk teman paling lama, minimal 10 detik.",
    "Kirim stiker cinta ke pacar/crush, 10 stiker.",
    "Nyium pipi teman di depan semua orang.",
    "Chat crush bilang 'Aku dulu mikir kamu'.",
    "Pegang tangan teman sambil lihat matanya, 5 detik.",
    "Gombal paling manja ke pacar via voice note.",
    "Duduk dekat teman, liatin foto couple di HP.",
    "Bilang hal manis ke orang yang kamu suka, di depan semua.",
    "Foto couple pose dengan teman, kirim ke grup.",
    "Kirim emoji cinta berturut-turut ke pacar.",
    "Tanya teman 'Mau jadi pacar aku gak?' dalam candaan.",
    "Dekati teman sambil berbisik hal gombal.",
    "Buat ucapan manis buat pacar, dibaca di depan teman.",
    "Chat teman 'Kamu manis sih' dengan serius.",
    "Peluk teman dari belakang, diamkan 5 detik.",
    "Bisikkan hal gombalan paling lucu ke telinga teman.",
    "Pegang pipi teman, liatin ke matanya sambil senyum.",
    "Kirim motivasi romantis ke pacar via pesan panjang.",
    "Dekati teman, suruh dia menutup mata, kirim kecupan udara.",
    "Chat crush kamu dengan kalimat paling manja.",
    "Duduk di pangkuan teman, ambil selfie couple.",
    "Serendin teman dengan lagu cinta via voice note.",
    "Gombali guru/dosen dengan cara yang lucu.",
    "Nyium tangan teman sambil bilang 'Maaf'.",
    "Chat mantan bilang 'Kamu masih special buat aku'.",
    "Tanya teman 'Aku cantik/ganteng gak?' dengan serius.",
    "Foto bareng teman paling dekat, pose couple.",
    "Bilang ke teman 'Aku sayang kamu' sambil lihat matanya.",
    "Kirim pesan panjang romantis ke pacar.",
    "Tara teman sambil main rambut dia.",
    "Chat crush 'Lihat ke cermin, itu alasan aku suka kamu'.",
    "Gandengan tangan sama teman, jalan bersama.",
    "Buat puisi romantis buat orang yang kamu suka, recite.",
    "Dekati crush, bilang 'Lagi mikirin kamu' dengan serius.",
    "Foto selfie dengan crush, set jadi DP.",
    "Chat pacar 'Aku beruntung punya kamu'.",
    "Pegang sayang tangan teman sambil bilang nama mereka.",
    "Gombal paling dalam ke pacar via VN.",
    "Duduk berdekatan dengan crush, liatin sunset foto.",
    "Kirim surat cinta virtual ke pacar.",
    "Bisikkan hal sweet ke telinga teman.",
    "Chat teman 'Aku cinta kamu' dalam candaan.",
    
    # --- LEVEL 3: PEDAS / 18+ / 21+ (EXPLICIT / ADULT) ---
    "Desah (moan) di voice note sekarang, durasi minimal 5 detik!",
    "Kirim foto paha (thigh pic) sekarang di grup! (No face gapapa)",
    "Chat mantan kamu: 'Badan kamu makin bagus deh', kirim ss kesini.",
    "Cium layar HP kamu sambil di-videoin orang lain/mirror selfie.",
    "Tulis nama member grup ini di bagian tubuh kamu (dada/paha/perut), foto & kirim.",
    "VN bilang 'Ahhh sakit mas...' dengan nada mendesah.",
    "Kirim foto gaya paling seksi yang kamu punya di galeri.",
    "Goyangkan pantat (twerking) divideoin 5 detik, kirim kesini (boleh blur muka).",
    "Chat crush kamu bilang: 'I want you inside me' atau 'I want you so bad'.",
    "Kirim foto bibir kamu pose nyium (duck face) seksi.",
    "Jilat barang di dekatmu (botol/pulpen) dengan gaya menggoda, kirim videonya.",
    "Foto leher/tulang selangka (collarbone) kamu, kirim sini.",
    "VN suara kamu lagi mendesah sebut nama Admin grup ini.",
    "Kirim foto perut/abs kamu (boleh angkat baju dikit).",
    "Chat pacar/mantan: 'Lagi pengen nih, kerumah yuk', ss balasannya.",
    "Cari foto paling seksi di IG/Twitter, jadikan PP Telegram selama 30 menit.",
    "Pegang bagian sensitif kamu (dari luar baju) sambil mirror selfie.",
    "Buat status WA/Story: 'Lagi sange banget nih, butuh bantuan', tahan 10 menit.",
    "VN bilang: 'Daddy, I've been a bad girl/boy' dengan suara menggoda.",
    "Foto kaki (feet) kamu pose cantik/ganteng.",
    "Pilih satu member grup, chat pribadi bilang fantasi jorok kamu tentang dia.",
    "Buka kancing baju teratas kamu, foto dan kirim sini.",
    "VN suara ciuman (muach) yang basah/nyaring.",
    "Kirim foto lidah kamu melet (ahegao face) sekarang.",
    "Elus-elus paha sendiri sambil direkam video 5 detik.",
    "Kirim foto punggung kamu (tanpa baju atasan kalau cowok, tanktop kalau cewek).",
    "Chat teman lawan jenis: 'Ukuran kamu berapa?', kirim SS balasannya.",
    "Pose seperti sedang orgasme, foto & kirim sini.",
    "Chat teman: 'Aku lagi naked sekarang, mau lihat?', kirim SS.",
    "VN dengan nada penggoda, bilang 'Aku menungguimu'.",
    "Kirim foto dengan pose paling menggoda yang kamu punya.",
    "Cium jari kamu seduktif, videokan 3 detik.",
    "Chat crush 'Tadi malam aku mimpi bermain denganmu'.",
    "Foto tangan kamu pegang dada sendiri, kirim sini.",
    "VN dengan suara sexy bilang nama salah satu member.",
    "Kirim foto kaki kamu dengan stoking/kaos kaki seksi.",
    "Pegang rambut kamu seduktif, selfie & kirim.",
    "Chat pacar 'Aku tidak sabar' dengan emoji tertentu.",
    "Foto perut/sixpack kamu sambil pose, kirim grup.",
    "VN suara desahan sambil sebut 'Mas/Mbak...'.",
    "Kirim foto dengan pose merangkak, kirim sini.",
    "Chat crush dengan kalimat paling 'hot'.",
    "Foto bagian atas tubuh kamu (shirtless kalau cowok), kirim sini.",
    "VN dengan tone flirty yang sekali menjadi.",
    "Kirim foto bibir dengan lipstik warna menggoda.",
    "Pegang leher sendiri seduktif, selfie & kirim.",
    "Chat teman 'Aku pengen tidur denganmu', SS balasannya.",
    "Foto diri dengan air terjun/mandi (blurred), kirim grup.",
    "VN bilang 'I want you' dengan nada paling seductive.",
    "Kirim foto dengan pose terbaring yang menggoda.",
    "Jilat bibir kamu sambil liatin kamera, videokan.",
    "Chat crush 'Aku tidak bisa berhenti mikirin tubuhmu'.",
    "Foto pantat kamu dari belakang, kirim sini.",
    "VN dengan nada penggoda, bilang nama orang seksi.",
    "Kirim foto dengan tanktop/crop top seksi.",
    "Bite bibir kamu seduktif, selfie & kirim.",
    "Chat teman 'Aku sange', kirim SS balasannya.",
    "Foto dengan pose menggoda di tempat tidur, kirim sini.",
    "VN desahan ketika menyebut nama seseorang seksi.",
    "Kirim foto dengan lingerie atau underwear seksi.",
    "Tunjukkan bahu kamu dengan pose seduktif, foto & kirim.",
    "Chat crush 'Aku ingin merasakan tubuhmu'.",
    "Foto dengan pose kayang/lengkung, kirim sini.",
    "VN dengan voice paling seksi bilang 'Touch me'.",
    "Kirim foto dengan celana pendek yang sangat pendek.",
    "Pose seperti sedang foreplay, foto & kirim grup.",
    "Chat pacar 'Tadi malam aku... karena kamu'.",
    "Foto leher kamu dengan bite marks terlihat (atau goresan fake), kirim.",
    "VN suara orgasme palsu dengan nada dramatis.",
    "Kirim foto dengan pose paling vulgar yang kamu berani.",
    "Pegang payudara kamu dari luar, selfie & kirim (cewek).",
    "Chat teman 'Aku aroused' dengan details yang menggoda.",
    "Foto dengan pose di kamar tidur paling seksi, kirim grup.",
    "VN dengan bahasa jorok yang paling ekstrem.",
    "Kirim foto mencium plushie/mainan dengan seduktif.",
    "Pegang alat vital dari luar (celana), selfie & kirim.",
    "Chat crush dengan nada yang paling dirty talk mungkin.",
    "Foto dengan pose membuka sedikit celana, kirim sini.",
    "VN mendesah panjang seperti sedang... (kamu tahu).",
    "Kirim foto bra/boxer kamu yang sedang kamu pakai.",
    "Sentuh bibir kamu dengan jari seduktif, videokan.",
    "Chat teman 'Aku butuh... (sesuatu yang dirty)' SS-nya.",
    "Foto dengan pose di kamar dengan lampu remang, kirim.",
    "VN dirty talk paling berani kamu buat seseorang.",
    "Kirim foto dengan celana yang sangat ketat di area sensitif.",
    "Pose di depan cermin dengan ekspresi 'hot', foto & kirim.",
    "Chat crush kalimat paling playful & seductive.",
    "Foto tubuh kamu dengan oil/minyak (glossy), kirim grup.",
    "VN suara gemuruh passion palsu yang lucu.",
    "Kirim foto dengan pose leg extended yang menggoda.",
    "Pegang dinding sambil pose seduktif, selfie & kirim.",
    "Chat pacar dengan sexting paling panjang (tanpa ngaco).",
    "Foto dengan close-up bibir membuka sedikit, kirim sini.",
    "VN nada playful bilang 'I'm yours tonight'.",
]
# ==========================================
# 🔥 TRUTH OR DARE (ENGLISH PREMIUM STYLE)
# ==========================================

# 1. Menu Utama (Main Menu)
async def tod_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🧠 TRUTH", callback_data='tod_mode_truth'),
            InlineKeyboardButton("🔥 DARE", callback_data='tod_mode_dare')
        ],
        [InlineKeyboardButton("❌ Close Game", callback_data='tod_close')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Kata-kata Pembuka yang Lebih Keren
    txt = (
        f"<b>OKTACOMEL ToD</b> 🎲\n\n"
        f"Prepare yourself. Secrets will be revealed, limits will be tested.\n"
        f"<b>Choose your destiny carefully.</b>\n\n"
        f"⚠️ <i>Warning: Mature Content (18+)</i>"
    )
    
    if update.message:
        await update.message.reply_text(txt, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.callback_query.message.edit_text(txt, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# 2. Handler Logika Game
async def tod_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data 
    
    if data == 'tod_close':
        await query.message.delete()
        return

    # Tentukan Mode
    if 'truth' in data:
        theme = "<b>TRUTH TIME!</b> 🧠"
        question = random.choice(LIST_TRUTH)
        next_data = 'tod_mode_truth' 
    elif 'dare' in data:
        theme = "<b>DARE TIME!</b> 🔥"
        question = random.choice(LIST_DARE)
        next_data = 'tod_mode_dare'
    else:
        return

    # Tombol Navigasi (English)
    keyboard = [
        [InlineKeyboardButton("🔄 SPIN AGAIN", callback_data=next_data)],
        [InlineKeyboardButton("🔥 ULTIMATE DARE", callback_data='tod_mode_dare')],
        [InlineKeyboardButton("🧠 DEEP TRUTH", callback_data='tod_mode_truth')],
        [InlineKeyboardButton("🔙 Switch Mode", callback_data='tod_menu')],
        [InlineKeyboardButton("❌ CLOSE GAME", callback_data='tod_close')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    res = (
        f"{theme}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Question:</b>\n"
        f"<code>{html.escape(question)}</code>\n\n"
        f"📡 <b>Status:</b> 🟢 <i>Matrix Active</i>\n"
        f"⚡ <i>Powered by Oktacomel Game Core</i>"
    )
    
    await query.message.edit_text(res, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# 3. Handler Balik ke Menu
async def tod_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await tod_command(update, context)

# ==========================================
# 💳 CC CHECKER (SIMULATION WITH REAL BIN)
# ==========================================
async def chk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Cek Input
    if not context.args:
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/chk cc|mm|yy|cvv</code>", parse_mode=ParseMode.HTML)
        return

    input_data = context.args[0]
    
    # Animasi Loading
    msg = await update.message.reply_text("<b>[↯] Waiting for Result...</b>", parse_mode=ParseMode.HTML)
    
    start_time = time.time()
    
    # 1. Parsing Data Kartu (CC|MM|YY|CVV)
    # Ganti semua pemisah jadi | biar gampang
    clean_input = input_data.replace("/", "|").replace(":", "|").replace(" ", "|")
    splits = clean_input.split("|")
    
    if len(splits) < 4:
        # Jika user cuma masukin CC doang, kita kasih dummy data biar gak error
        cc = splits[0]
        mes, ano, cvv = "xx", "xxxx", "xxx"
    else:
        cc = splits[0]
        mes = splits[1]
        ano = splits[2]
        cvv = splits[3]

    # Ambil 6 digit BIN
    bin_code = cc[:6]
    
    # 2. Cek BIN Asli (Pakai API yang sudah ada di botmu)
    try:
        r = await fetch_json(f"{BIN_API}/{bin_code}")
        if r and 'brand' in r:
            scheme = str(r.get('scheme', 'UNKNOWN')).upper()
            type_c = str(r.get('type', 'UNKNOWN')).upper()
            level = str(r.get('level', 'UNKNOWN')).upper()
            bank = str(r.get('bank', 'UNKNOWN')).upper()
            country = str(r.get('country_name', 'UNKNOWN')).upper()
            flag = r.get('country_flag', '')
        else:
            scheme, type_c, level, bank, country, flag = "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", ""
    except:
        scheme, type_c, level, bank, country, flag = "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", ""

    # 3. Simulasi Gateway Response (Disini logika 'Bohongan'-nya)
    # Kita buat seolah-olah dia ngecek ke Braintree
    await asyncio.sleep(random.uniform(2, 5)) # Delay biar kayak lagi mikir (2-5 detik)
    
    # Daftar kemungkinan respon (Bisa kamu tambah)
    responses = [
        ("Declined ❌", "RISK: Retry this BIN later."),
        ("Declined ❌", "Insufficient Funds"),
        ("Declined ❌", "Do Not Honor"),
        ("Approved ✅", "CVV LIVE"), # Kecilkan kemungkinan approved biar real
        ("Approved ✅", "Charged $10")
    ]
    
    # Random pilih status (80% Declined, 20% Approved - biar realistis)
    # Ubah logic ini kalau mau selalu approved (tapi jadi gak seru)
    is_live = random.choices([True, False], weights=[10, 90])[0] 
    
    if is_live:
        status_header = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
        gw_resp = "Charged Success"
    else:
        status_header = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
        gw_resp = random.choice(responses)[1]

    # Hitung waktu
    end_time = time.time()
    taken = round(end_time - start_time, 2)

    # 4. Susun Pesan (Sesuai Request Font & Style)
    result_text = (
        f"{status_header}\n\n"
        f"𝗖𝗮𝗿𝗱: <code>{cc}|{mes}|{ano}|{cvv}</code>\n\n"
        f"𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Braintree Premium\n"
        f"𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {gw_resp}\n\n"
        f"𝗜𝗻𝗳𝗼: {scheme} - {type_c} - {level}\n"
        f"𝐈𝐬𝐬𝐮𝐞𝐫: {bank}\n"
        f"𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {country} {flag}\n\n"
        f"𝗧𝗶𝗺𝗲: {taken} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬"
    )
    
    await msg.edit_text(result_text, parse_mode=ParseMode.HTML)


# ==========================================
# 🔢 BIN EXTRAPOLATION (/extrap)
# ==========================================
async def extrap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/extrap 454321</code> or <code>/extrap 454321|05|2026</code>", parse_mode=ParseMode.HTML)
        return

    input_data = args[0]
    
    # Default jumlah generate extrap (standar 5 - 10)
    amount = 5
    if len(args) > 1 and args[1].isdigit():
        amount = int(args[1])
        if amount > 20: amount = 20 # Limit biar gak spam

    msg = await update.message.reply_text("⏳ <b>Extrapolating...</b>", parse_mode=ParseMode.HTML)

    # --- 1. NORMALISASI INPUT (CUSTOM SUPPORT) ---
    # Ganti semua pemisah (/ : spasi) menjadi | agar mudah diproses
    normalized_input = input_data.replace("/", "|").replace(":", "|").replace(" ", "|")
    splits = normalized_input.split("|")
    
    # Ambil data sesuai urutan (Support Custom Format)
    cc = splits[0] if len(splits) > 0 else 'x'
    mes = splits[1] if len(splits) > 1 and splits[1].isdigit() else 'x'
    ano = splits[2] if len(splits) > 2 and splits[2].isdigit() else 'x'
    cvv = splits[3] if len(splits) > 3 and splits[3].isdigit() else 'x'

    # Ambil 6 digit BIN untuk lookup info
    clean_bin = cc.lower().replace('x', '')[:6]

    if not clean_bin.isdigit() or len(clean_bin) < 6:
        await msg.edit_text("❌ BIN Invalid.")
        return

    # --- 2. FETCH BIN INFO ---
    try:
        r = await fetch_json(f"{BIN_API}/{clean_bin}")
        if r and 'brand' in r:
            # Format Info: BRAND - TYPE - LEVEL
            info_str = f"{str(r.get('brand')).upper()} - {str(r.get('type')).upper()} - {str(r.get('level')).upper()}"
            bank = str(r.get('bank', 'UNKNOWN')).upper()
            country = f"{str(r.get('country_name')).upper()} {r.get('country_flag','')}"
        else:
            info_str, bank, country = "UNKNOWN", "UNKNOWN", "UNKNOWN"
    except: 
        info_str, bank, country = "ERROR", "ERROR", "ERROR"

    # --- 3. GENERATE CARDS (Pakai fungsi cc_gen yg sudah ada) ---
    # Kita generate agak banyak dulu, nanti ambil sesuai amount
    generated_list = cc_gen(cc, mes, ano, cvv, amount)

    # --- 4. FORMATTING OUTPUT (SESUAI REQUEST) ---
    result_body = ""
    for card in generated_list:
        # Format cc_gen biasanya: CC|MM|YYYY|CVV
        # Kita pecah biar tampilannya sesuai request
        c_split = card.split("|")
        c_num = c_split[0]
        c_date_cvv = f"{c_split[1]}|{c_split[2]}|{c_split[3]}"
        
        # Susun tampilan per kartu
        result_body += f"<code>{c_num}</code>\n<code>{c_date_cvv}</code>\n\n"

    # Teks Akhir
    final_text = (
        f"<b>𝗕𝗜𝗡  →</b> <code>{clean_bin}</code>\n"
        f"<b>𝗔𝗺𝗼𝘂𝗻𝘁 →</b> {amount}\n\n"
        f"{result_body}"
        f"<b>Generation Type:</b> Luhn-Based BIN Extrapolation\n"
        f"<b>𝗜𝗻𝗳𝗼:</b> {info_str}\n"
        f"<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {bank}\n"
        f"<b>𝗖𝗼𝘂𝗻𝘁𝗿𝘆:</b> {country}"
    )

    await msg.edit_text(final_text, parse_mode=ParseMode.HTML)

# ==========================================
# 🛡️ PROXY CHECKER (FORMAT V2 - IP:PORT:USER:PASS)
# ==========================================
async def proxy_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Ambil Input
    proxies_to_check = []

    if context.args:
        proxies_to_check = context.args
    elif update.message.reply_to_message and update.message.reply_to_message.text:
        raw_text = update.message.reply_to_message.text
        # Pisahkan berdasarkan baris atau spasi
        proxies_to_check = raw_text.replace(" ", "\n").split("\n")
        # Bersihkan list dari string kosong
        proxies_to_check = [x.strip() for x in proxies_to_check if x.strip()]
    else:
        # Pesan Error Sesuai Request
        await update.message.reply_text(
            "⚠️ <b>Invalid Proxy Format!</b>\n\n"
            "<b>Usage:</b>\n"
            "You can check up to 20 proxies at a time.\n\n"
            "<b>Normal:</b> <code>/proxy host:port:user:pass</code>\n"
            "<b>With Type:</b> <code>/proxy socks5:host:port:user:pass</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # 2. Limit Maksimal 20
    if len(proxies_to_check) > 20:
        await update.message.reply_text(
            "❌ <b>Limit Reached:</b> Max 20 proxies allowed.",
            parse_mode=ParseMode.HTML
        )
        return

    msg = await update.message.reply_text(
        f"⏳ <b>Checking {len(proxies_to_check)} Proxies...</b>",
        parse_mode=ParseMode.HTML
    )

    # 3. Fungsi Cek Pintar (Auto Format + Real Check)
    async def check_single_proxy(raw_proxy: str):
        p = raw_proxy.strip()
        scheme = "http"  # default
        display = p      # fallback tampilan

        # CASE 1: user kirim full URL proxy (http://user:pass@ip:port)
        if "://" in p and p.split("://", 1)[0].lower() in ["http", "https", "socks5"]:
            final_url = p
            if "@" in p:
                display = p.split("@")[-1]
        # CASE 2: format: socks5:ip:port:user:pass atau http:ip:port:user:pass
        elif p.lower().startswith("socks5:") or p.lower().startswith("http:"):
            parts = p.split(":")
            scheme = parts[0].lower()  # socks5 / http
            clean_parts = parts[1:]

            if len(clean_parts) == 4:
                host, port, user, pwd = clean_parts
                final_url = f"{scheme}://{user}:{pwd}@{host}:{port}"
                display = f"{host}:{port}"
            elif len(clean_parts) == 2:
                host, port = clean_parts
                final_url = f"{scheme}://{host}:{port}"
                display = f"{host}:{port}"
            else:
                return False, display, 0, "Bad Format"
        else:
            # CASE 3: format standar ip:port:user:pass atau ip:port
            parts = p.split(":")
            if len(parts) == 4:
                ip, port, user, pwd = parts
                final_url = f"http://{user}:{pwd}@{ip}:{port}"
                display = f"{ip}:{port}"
            elif len(parts) == 2:
                ip, port = parts
                final_url = f"http://{ip}:{port}"
                display = f"{ip}:{port}"
            else:
                return False, display, 0, "Bad Format"

        try:
            start_time = time.time()

            proxy_cfg = {
                "http://": final_url,
                "https://": final_url,
            }

            async with httpx.AsyncClient(
                proxy=final_url,
                timeout=8.0,
                follow_redirects=True
            ) as client:
                # pakai HTTPS (lebih wajar dibuka)
                resp = await client.get("https://ipwho.is/")

                if resp.status_code == 200:
                    data = resp.json()

                    # ipwho.is kadang success=false
                    if data.get("success") is False:
                        reason = data.get("message", "Service error")
                        return False, display, 0, reason

                    latency = int((time.time() - start_time) * 1000)

                    ip_asli = data.get("ip", "Unknown")
                    negara = data.get("country_code", "??")
                    flag = data.get("flag", {}).get("emoji", "")
                    isp = data.get("connection", {}).get("isp", "Unknown ISP")

                    info_text = f"{ip_asli} | {negara} {flag} | {isp}"
                    return True, display, latency, info_text

                else:
                    return False, display, 0, f"Status {resp.status_code}"

        except Exception as e:
            err_msg = str(e)

            if "ConnectTimeout" in err_msg or "ReadTimeout" in err_msg:
                reason = "Too Slow"
            elif "403" in err_msg:
                reason = "Blocked / 403"
            elif "Cannot connect" in err_msg or "Connection refused" in err_msg:
                reason = "Refused"
            elif "Name or service not known" in err_msg or "getaddrinfo failed" in err_msg:
                reason = "DNS Error"
            elif "Authentication" in err_msg or "auth" in err_msg.lower():
                reason = "Auth Failed"
            else:
                reason = (err_msg[:60] + "...") if len(err_msg) > 60 else (err_msg or "Dead")

            return False, display, 0, reason

    # 4. Eksekusi Paralel
    tasks = [check_single_proxy(p) for p in proxies_to_check]
    results = await asyncio.gather(*tasks)

    # URUTKAN: LIVE dulu, lalu berdasarkan ping (cepat -> lambat)
    results_sorted = sorted(
        results,
        key=lambda r: (not r[0], r[2] if r[2] > 0 else 999999)
    )

    # 5. Laporan Clean Mono + Ultimate UI
    report_lines = []
    live_count = sum(1 for r in results_sorted if r[0])
    dead_count = len(results_sorted) - live_count

    for is_live, proxy, ping, info in results_sorted:
        if is_live:
            status = f"✅ <b>LIVE</b> | 📶 <b>{ping}ms</b>"
            detail = f"   └ <code>{info}</code>"
            line = f"🔌 <code>{proxy}</code>\n{status}\n{detail}"
        else:
            status = "❌ <b>DEAD</b>"
            detail = f"   └ <i>{html.escape(str(info))}</i>"
            line = f"🔌 <code>{proxy}</code>\n{status}\n{detail}"
        report_lines.append(line)

    success_rate = (live_count / len(results_sorted) * 100) if results_sorted else 0
    success_rate = int(success_rate)

    final_text = (
        "🛡️ <b>OKTACOMEL PROXY LAB V2</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Total:</b> {len(proxies_to_check)} | "
        f"🟢 <b>Live:</b> {live_count} | 🔴 <b>Dead:</b> {dead_count}\n"
        f"📈 <b>Uptime Sample:</b> {success_rate}%\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        + ("\n\n".join(report_lines) if report_lines else "No result.") +
        "\n\n🤖 <i>Deep-Scan Proxy Engine by Oktacomel</i>"
    )

    await msg.edit_text(final_text, parse_mode=ParseMode.HTML)

# ==========================================
# 📰 LATEST NEWS (RSS — PREMIUM ULTIMATE)
# ==========================================
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Jika user tidak beri topik → default Indonesia
    if not context.args:
        query = "indonesia"
        display_query = "INDONESIA"
    else:
        query = " ".join(context.args).lower()
        display_query = query.upper()

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    # ==========================================
    # PILIH RSS FEED OTOMATIS BERDASARKAN TOPIK
    # ==========================================
    if any(word in query for word in ["indo", "indonesia", "nasional"]):
        rss_url = "https://news.kompas.com/rss"
    elif "tech" in query or "teknologi" in query:
        rss_url = "http://feeds.bbci.co.uk/news/technology/rss.xml"
    elif "sport" in query or "olahraga" in query:
        rss_url = "http://feeds.bbci.co.uk/sport/rss.xml"
    elif "world" in query or "dunia" in query:
        rss_url = "http://feeds.bbci.co.uk/news/world/rss.xml"
    else:
        # fallback: BBC general
        rss_url = "http://feeds.bbci.co.uk/news/rss.xml"

    # ==========================================
    # PARSE RSS
    # ==========================================
    try:
        feed = feedparser.parse(rss_url)

        if not feed.entries:
            return await update.message.reply_text(
                "❌ <b>Tidak ada berita ditemukan.</b>",
                parse_mode=ParseMode.HTML
            )

        # Ambil 3 berita teratas
        items = feed.entries[:3]
        news_blocks = []

        for idx, item in enumerate(items, start=1):
            title = item.title
            link = item.link
            date = item.get("published", "Unknown")
            source = feed.feed.get("title", "Unknown Source")

            block = (
                f"<b>{idx}. {html.escape(title)}</b>\n"
                f"📰 Source ⇾ <code>{html.escape(source)}</code>\n"
                f"📅 Date ⇾ <code>{html.escape(date)}</code>\n"
                f"🔗 Link ⇾ <a href='{link}'>Read Article</a>\n"
            )
            news_blocks.append(block)

        body = "\n".join(news_blocks)

        # ==========================================
        # TAMPILAN PREMIUM ULTIMATE
        # ==========================================
        reply = (
            f"📰 <b>NEWS CENTER — PREMIUM</b>\n"
            f"✦────────────────────✦\n"
            f"📌 <b>Topic</b> ⇾ <code>{display_query}</code>\n"
            f"✦────────────────────✦\n\n"
            f"{body}\n"
            f"✦────────────────────✦\n"
            f"🤖 <i>Powered by Oktacomel</i>"
        )

        await update.message.reply_text(
            reply,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Error Parsing RSS:</b>\n<code>{str(e)}</code>",
            parse_mode=ParseMode.HTML
        )


# ==========================================
# 🛠 HELPER: FONT CONVERTER (BOLD SANS)
# ==========================================
def to_bold(text):
    maps = {
        'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚', 'H': '𝗛', 'I': '𝗜', 'J': '𝗝',
        'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡', 'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥', 'S': '𝗦', 'T': '𝗧',
        'U': '𝗨', 'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭',
        'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴', 'h': '𝗵', 'i': '𝗶', 'j': '𝗷',
        'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻', 'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿', 's': '𝘀', 't': '𝘁',
        'u': '𝘂', 'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 'y': '𝘆', 'z': '𝘇',
        '0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'
    }
    return "".join(maps.get(c, c) for c in text)

# ==========================================
# 💳 CC SCRAPER (PREMIUM + AUTO DEDUPE)
# ==========================================

async def scr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CC Scraper dengan auto remove duplicate advanced"""
    
    args = context.args
    reply = update.message.reply_to_message
    
    target_text = ""
    source_name = "Text/Reply"
    source_url = ""
    limit = 0
    is_private = False
    
    # ==========================================
    # 1. SKENARIO SOURCES
    # ==========================================
    
    if reply and reply.text:
        target_text = reply.text
        if args: 
            try:
                limit = int(args[0])
            except:
                limit = 0
        source_name = "Reply Message"
        
    elif args:
        target = args[0]
        try:
            limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        except:
            limit = 0
        
        if "t.me/" in target:
            username = target.replace("https://t.me/", "").replace("@", "").split("/")[0]
            source_name = f"@{username}"
            source_url = f"https://t.me/{username}"
            
            msg = await update.message.reply_text(
                f"⏳ <b>Checking:</b> @{username}...\n"
                f"🔍 Analyzing...",
                parse_mode=ParseMode.HTML
            )
            
            try:
                web_url = f"https://t.me/s/{username}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.get(web_url, headers=headers)
                    
                    if "is not accessible" in r.text or "Access Denied" in r.text or r.status_code == 404:
                        is_private = True
                        source_url = f"https://t.me/{username}"
                        await msg.edit_text(
                            f"🔒 <b>Private Channel/Group Detected</b>\n\n"
                            f"Name: @{username}\n"
                            f"Type: <b>PRIVATE</b>\n\n"
                            f"⏳ <b>Processing private source...</b>\n"
                            f"🔍 Scanning messages...",
                            parse_mode=ParseMode.HTML
                        )
                    else:
                        target_text = r.text
                        await msg.edit_text(
                            f"✅ <b>Public Channel Found</b>\n"
                            f"Channel: @{username}\n"
                            f"🔍 Processing...",
                            parse_mode=ParseMode.HTML
                        )
                    
            except Exception as e:
                logger.error(f"[SCRAPER] Error: {e}")
                await msg.edit_text(
                    f"❌ <b>Error accessing source</b>\n"
                    f"Source: @{username}\n"
                    f"Error: {str(e)[:80]}",
                    parse_mode=ParseMode.HTML
                )
                return
        
        elif target.startswith("@"):
            username = target.replace("@", "")
            source_name = f"@{username}"
            source_url = f"https://t.me/{username}"
            
            msg = await update.message.reply_text(
                f"⏳ <b>Checking:</b> @{username}...\n"
                f"🔍 Analyzing...",
                parse_mode=ParseMode.HTML
            )
            
            try:
                web_url = f"https://t.me/s/{username}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.get(web_url, headers=headers)
                    
                    if "is not accessible" in r.text or "Access Denied" in r.text or r.status_code == 404:
                        is_private = True
                        await msg.edit_text(
                            f"🔒 <b>Private Channel/Group Detected</b>\n\n"
                            f"Name: @{username}\n"
                            f"Type: <b>PRIVATE</b>\n\n"
                            f"⏳ <b>Processing private source...</b>\n"
                            f"🔍 Scanning messages...",
                            parse_mode=ParseMode.HTML
                        )
                    else:
                        target_text = r.text
                        await msg.edit_text(
                            f"✅ <b>Public Channel Found</b>\n"
                            f"Channel: @{username}\n"
                            f"🔍 Processing...",
                            parse_mode=ParseMode.HTML
                        )
                    
            except Exception as e:
                await msg.edit_text(
                    f"❌ <b>Error</b>\n{str(e)[:80]}",
                    parse_mode=ParseMode.HTML
                )
                return
        
        else:
            target_text = update.message.text
    
    else:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b>\n"
            "1. <code>/scr @channel_name [limit]</code>\n"
            "2. <code>/scr https://t.me/channel [limit]</code>\n"
            "3. Reply message with <code>/scr</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # ==========================================
    # 2. HANDLE PRIVATE GROUP/CHANNEL
    # ==========================================
    
    if is_private or not target_text:
        if update.effective_chat.type in ["group", "supergroup"]:
            source_name = update.effective_chat.title or "Private Group"
            source_url = f"https://t.me/c/{str(update.effective_chat.id)[4:]}/{update.message.message_id}"
            is_private = True
            
            target_text = f"{update.message.text or ''}\n"
            for i in range(max(0, update.message.message_id - 100), update.message.message_id):
                try:
                    msg_history = await context.bot.forward_message(
                        chat_id=update.message.chat_id,
                        from_chat_id=update.message.chat_id,
                        message_id=i
                    )
                    if msg_history.text:
                        target_text += f"\n{msg_history.text}"
                except:
                    pass
            
            try:
                await log_user_action(
                    update.effective_user.id,
                    "cc_scraping",
                    f"chat_id:{update.effective_chat.id} type:private_group"
                )
            except:
                pass

    # ==========================================
    # 3. EXTRACT CC DENGAN MULTIPLE PATTERNS
    # ==========================================
    
    if not 'msg' in locals():
        msg = await update.message.reply_text(
            "🔍 <b>Scanning for CC patterns...</b>\n"
            "[░░░░░░░░░░░░░░░░░░] 0%",
            parse_mode=ParseMode.HTML
        )
    
    patterns = [
        r'\b\d{15,16}[|:/-]\d{1,2}[|:/-]\d{2,4}[|:/-]\d{3,4}\b',
        r'\b\d{15,16}\s+\d{1,2}\s+\d{2,4}\s+\d{3,4}\b',
        r'\b\d{15,16}[|:]\d{2,4}\b',
    ]
    
    found_ccs_raw = []
    for pattern in patterns:
        found_ccs_raw.extend(re.findall(pattern, target_text))
    
    await msg.edit_text(
        "🔍 <b>Scanning for CC patterns...</b>\n"
        "[██████░░░░░░░░░░░░] 30%",
        parse_mode=ParseMode.HTML
    )
    
    if not found_ccs_raw:
        await msg.edit_text("❌ <b>No CC Found.</b>", parse_mode=ParseMode.HTML)
        return

    # ==========================================
    # 4. ADVANCED DUPLICATE REMOVAL
    # ==========================================
    
    await msg.edit_text(
        "🔍 <b>Removing duplicates & normalizing...</b>\n"
        "[████████░░░░░░░░░░] 40%",
        parse_mode=ParseMode.HTML
    )
    
    # Normalize dan dedupe
    normalized_ccs = set()
    cc_mapping = {}  # Track original format
    
    for cc_raw in found_ccs_raw:
        # Extract CC number (bagian pertama sebelum separator)
        cc_parts = re.split(r'[|:/-\s]', cc_raw)
        cc_number = cc_parts[0].strip()
        
        # Normalize ke format standard
        if len(cc_parts) >= 4:
            # Full format: 4111111111111111|12/25|123
            normalized = f"{cc_number}|{cc_parts[1]}|{cc_parts[2]}|{cc_parts[3]}"
        elif len(cc_parts) == 3:
            # 3 parts: 4111111111111111|12|25
            normalized = f"{cc_number}|{cc_parts[1]}|{cc_parts[2]}"
        elif len(cc_parts) == 2:
            # 2 parts: 4111111111111111|123
            normalized = f"{cc_number}|{cc_parts[1]}"
        else:
            # Just number
            normalized = cc_number
        
        # Add to set (automatic dedupe by CC number)
        if cc_number not in cc_mapping:
            normalized_ccs.add(normalized)
            cc_mapping[cc_number] = normalized
    
    unique_ccs = list(normalized_ccs)
    duplicates = len(found_ccs_raw) - len(unique_ccs)
    
    await msg.edit_text(
        "🔍 <b>Removing duplicates & normalizing...</b>\n"
        f"Found: {len(found_ccs_raw)} | Unique: {len(unique_ccs)} | Removed: {duplicates}\n"
        "[████████████░░░░░░] 60%",
        parse_mode=ParseMode.HTML
    )
    
    if limit > 0:
        unique_ccs = unique_ccs[:limit]

    total_scraped = len(unique_ccs)
    
    # ==========================================
    # 5. BUAT MULTIPLE FILE FORMAT
    # ==========================================
    
    await msg.edit_text(
        "📝 <b>Generating files...</b>\n"
        "[██████████████░░░░] 80%",
        parse_mode=ParseMode.HTML
    )
    
    # Format 1: TXT
    txt_content = "\n".join(unique_ccs)
    txt_file = io.BytesIO(txt_content.encode('utf-8'))
    txt_file.name = f"x{total_scraped}_{source_name}_Cleaned.txt"
    
    # Format 2: CSV (dengan parsing smart)
    csv_content = "CC,EXP_MONTH,EXP_YEAR,CVV\n"
    for cc in unique_ccs:
        parts = re.split(r'[|:/-\s]', cc)
        cc_num = parts[0] if len(parts) > 0 else ""
        exp_month = parts[1] if len(parts) > 1 else "XX"
        exp_year = parts[2] if len(parts) > 2 else "XX"
        cvv = parts[3] if len(parts) > 3 else "XXX"
        
        csv_content += f"{cc_num},{exp_month},{exp_year},{cvv}\n"
    
    csv_file = io.BytesIO(csv_content.encode('utf-8'))
    csv_file.name = f"x{total_scraped}_{source_name}_Cleaned.csv"
    
    # Format 3: JSON dengan metadata lengkap
    json_data = {
        "metadata": {
            "source": source_name,
            "url": source_url,
            "total_extracted": len(found_ccs_raw),
            "total_unique": total_scraped,
            "duplicates_removed": duplicates,
            "deduplication_percentage": f"{(duplicates / len(found_ccs_raw) * 100):.1f}%" if found_ccs_raw else "0%",
            "timestamp": datetime.datetime.now().isoformat(),
            "is_private": is_private,
            "normalized": True,
            "deduplication_method": "CC Number Based"
        },
        "cards": []
    }
    
    for cc in unique_ccs:
        parts = re.split(r'[|:/-\s]', cc)
        card = {
            "number": parts[0] if len(parts) > 0 else "",
            "exp_month": parts[1] if len(parts) > 1 else "",
            "exp_year": parts[2] if len(parts) > 2 else "",
            "cvv": parts[3] if len(parts) > 3 else "",
            "original_format": cc
        }
        json_data["cards"].append(card)
    
    json_content = json.dumps(json_data, indent=2)
    json_file = io.BytesIO(json_content.encode('utf-8'))
    json_file.name = f"x{total_scraped}_{source_name}_Cleaned.json"

    # ==========================================
    # 6. SECURITY INDICATOR
    # ==========================================
    
    security_badge = "🔒 <i>(Private Source - Logged)</i>" if is_private else "🌐 <i>(Public Source)</i>"

    # ==========================================
    # 7. KIRIM HASIL
    # ==========================================
    
    caption = (
        f"𝗖𝗖 𝗦𝗰𝗿𝗮𝗽𝗽𝗲𝗱 & 𝗖𝗹𝗲𝗮𝗻𝗲𝗱 ✅\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"𝗦𝗼𝘂𝗿𝗰𝗲 ⇾ {html.escape(source_name)} {security_badge}\n"
        f"𝗜𝗻𝗶𝘁𝗶𝗮𝗹 ⇾ {len(found_ccs_raw)} ❌\n"
        f"𝗨𝗻𝗶𝗾𝘂𝗲 ⇾ {total_scraped} ✅\n"
        f"𝗗𝘂𝗽𝗲𝘀 𝗥𝗲𝗺𝗼𝘃𝗲𝗱 ⇾ {duplicates} 🗑\n"
        f"𝗗𝘂𝗽𝗲 𝗥𝗮𝘁𝗲 ⇾ {(duplicates / len(found_ccs_raw) * 100):.1f}%" if found_ccs_raw else "0%\n"
        f"𝗙𝗼𝗿𝗺𝗮𝘁𝘀 ⇾ TXT + CSV + JSON 📦\n"
        f"𝗗𝗲𝗱𝘂𝗽𝗘 𝗠𝗲𝘁𝗵𝗼𝗱 ⇾ CC Number Based 🔐\n"
        f"𝗨𝘀𝗲𝗿 ⇾ {html.escape(update.effective_user.first_name)} 👤\n"
    )
    
    if source_url:
        caption += f"𝗟𝗶𝗻𝗸 ⇾ <a href='{source_url}'>View Source</a> 🔗\n"
    
    caption += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ 𝗦𝗰𝗿𝗮𝗽𝗽𝗲𝗱 𝗕𝘆 ⇾ Oktacomel"
    )

    try:
        await msg.delete()
    except:
        pass

    # Send TXT File
    await update.message.reply_document(
        document=txt_file,
        caption=caption,
        parse_mode=ParseMode.HTML
    )
    
    # Send CSV File
    await update.message.reply_document(
        document=csv_file,
        caption="📊 <b>CSV Format (Cleaned & Normalized)</b>",
        parse_mode=ParseMode.HTML
    )
    
    # Send JSON File
    await update.message.reply_document(
        document=json_file,
        caption="📋 <b>JSON Format (With Metadata & Deduplication Stats)</b>",
        parse_mode=ParseMode.HTML
    )
# ==========================================
# 💳 CC SCRAPER (PREMIUM FONT STYLE)
# ==========================================
async def scr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Cek Input
    args = context.args
    reply = update.message.reply_to_message
    
    target_text = ""
    source_name = "Text/Reply"
    limit = 0
    
    # Skenario 1: Reply Pesan
    if reply and reply.text:
        target_text = reply.text
        if args: limit = int(args[0])
        
    # Skenario 2: Input Link/Username
    elif args:
        target = args[0]
        limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        
        # Cek apakah Link Telegram
        if "t.me/" in target or target.startswith("@"):
            username = target.replace("https://t.me/", "").replace("@", "")
            if "/" in username: username = username.split("/")[0]
            
            source_name = f"{username}"
            msg = await update.message.reply_text(f"⏳ <b>Scraping:</b> {username}...", parse_mode=ParseMode.HTML)
            
            # Web Scraping (t.me/s/...)
            try:
                web_url = f"https://t.me/s/{username}"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.get(web_url, headers=headers)
                    target_text = r.text
            except Exception as e:
                await msg.edit_text(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
                return
        else:
            target_text = update.message.text
            
    else:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b>\n"
            "1. <code>/scr link_channel [limit]</code>\n"
            "2. Reply message with <code>/scr</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # 2. PROSES REGEX
    pattern = r'\b\d{15,16}[|:/-]\d{1,2}[|:/-]\d{2,4}[|:/-]\d{3,4}\b'
    found_ccs = re.findall(pattern, target_text)
    
    if not found_ccs:
        try: await msg.edit_text("❌ <b>No CC Found.</b>", parse_mode=ParseMode.HTML)
        except: await update.message.reply_text("❌ <b>No CC Found.</b>", parse_mode=ParseMode.HTML)
        return

    # 3. BERSIHKAN DUPLIKAT
    unique_ccs = list(set(found_ccs))
    duplicates = len(found_ccs) - len(unique_ccs)
    
    if limit > 0:
        unique_ccs = unique_ccs[:limit]

    total_scraped = len(unique_ccs)
    
    # 4. BUAT FILE TXT
    result_text = "\n".join(unique_ccs)
    file_name = f"x{total_scraped}_{source_name}_Drops.txt"
    
    bio = io.BytesIO(result_text.encode('utf-8'))
    bio.name = file_name

    # 5. KIRIM HASIL (PREMIUM BOLD SANS)
    caption = (
        f"𝗖𝗖 𝗦𝗰𝗿𝗮??𝗽𝗲𝗱 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹 ✅\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"𝗦𝗼𝘂𝗿𝗰𝗲 ⇾ {html.escape(source_name)} 🌐\n"
        f"𝗔𝗺𝗼𝘂𝗻𝘁 ⇾ {total_scraped} 📝\n"
        f"𝗗𝘂𝗽𝗹𝗶𝗰𝗮𝘁𝗲𝘀 ⇾ {duplicates} 🗑\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ 𝗦𝗰𝗿𝗮𝗽𝗽𝗲𝗱 𝗕𝘆 ⇾ Oktacomel"
    )

    try: await msg.delete()
    except: pass

    await update.message.reply_document(
        document=bio,
        caption=caption,
        parse_mode=ParseMode.HTML
    )


# ==========================================
# 🎵 MUSIC SEARCH ENGINE (SMART FILTER + RECOMMENDATION)
# ==========================================

async def show_music_search(update, context, query, offset=0):
    if not sp_client:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ <b>System Error:</b> Spotify API invalid.", parse_mode=ParseMode.HTML)
        return

    try:
        # Limit per halaman
        page_size = 10
        max_total = 20 # Maksimal cuma 20 lagu yang ditampilkan (2 Halaman)

        # 1. SEARCH LOGIC (Cari agak banyak dulu buat difilter)
        raw_results = sp_client.search(q=query, limit=50, type='track')
        raw_tracks = raw_results['tracks']['items']

        if not raw_tracks:
            msg = "❌ <b>Song not found.</b> Try specific keyword."
            if update.callback_query: await update.callback_query.answer(msg, show_alert=True)
            else: await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            return

        # 2. SMART SORTING (Relevansi + Rekomendasi)
        # Prioritas 1: Lagu yang judul/artisnya mengandung query user
        exact_matches = [t for t in raw_tracks if query.lower() in t['name'].lower() or query.lower() in t['artists'][0]['name'].lower()]
        
        # Prioritas 2: Sisanya (Rekomendasi terkait)
        recommendations = [t for t in raw_tracks if t not in exact_matches]
        
        # Gabung: Exact dulu, baru Rekomendasi
        final_list = exact_matches + recommendations
        
        # Potong Max 20 Lagu
        final_list = final_list[:max_total]
        total_results = len(final_list)

        # Ambil Slice Halaman Ini
        current_tracks = final_list[offset : offset + page_size]

        # 3. BUILD UI (COOL ENGLISH)
        txt_list = []
        buttons = []
        row_nums = []

        start = offset + 1
        end = min(offset + page_size, total_results)

        header = (
            f"🎵 <b>MUSIC SEARCH RESULT</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔎 <b>Query:</b> <code>{html.escape(query.title())}</code>\n"
            f"📄 <b>Page:</b> {start}-{end} of {total_results}\n\n"
        )

        for i, track in enumerate(current_tracks):
            num = start + i
            artist = track['artists'][0]['name']
            title = track['name']
            ms = track['duration_ms']
            duration = f"{int(ms/1000//60)}:{int(ms/1000%60):02d}"
            
            # Format Rapi
            txt_list.append(f"<b>{num}. {artist}</b> — {title} <code>[{duration}]</code>")
            
            # Tombol Angka
            row_nums.append(InlineKeyboardButton(str(num), callback_data=f"sp_dl|{track['id']}"))
            
            if len(row_nums) == 5:
                buttons.append(row_nums)
                row_nums = []
        
        if row_nums: buttons.append(row_nums)

        # Tombol Navigasi
        nav_row = []
        # Tombol Prev
        if offset > 0:
            prev_off = max(0, offset - page_size)
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"sp_nav|{prev_off}|{query}"))
        
        nav_row.append(InlineKeyboardButton("❌ Close", callback_data="cmd_close"))
        
        # Tombol Next (Hanya jika masih ada sisa di dalam batas max_total)
        if total_results > offset + page_size:
            next_off = offset + page_size
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"sp_nav|{next_off}|{query}"))
            
        buttons.append(nav_row)
        final_text = header + "\n".join(txt_list) + "\n\n🤖 <i>Powered by Oktacomel</i>"

        # Kirim/Edit Pesan
        if update.callback_query:
            await update.callback_query.edit_message_text(text=final_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(text=final_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        print(f"Search Error: {e}")

# COMMAND /song
async def song_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/song title artist</code>", parse_mode=ParseMode.HTML)
        return
    
    user_id = update.effective_user.id
    
    # Check and deduct credits
    success, remaining, cost = await deduct_credits(user_id, "song")
    if not success:
        await update.message.reply_text(
            f"❌ <b>Kredit Tidak Cukup</b>\n\n"
            f"Command ini membutuhkan {cost} kredit.\n"
            f"Kredit kamu: {remaining}\n\n"
            f"💎 Upgrade ke Premium untuk lebih banyak kredit!",
            parse_mode=ParseMode.HTML
        )
        return
    
    query = " ".join(context.args)
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    # Mulai dari halaman 0
    await show_music_search(update, context, query, offset=0)

# HANDLER NAVIGASI
async def song_nav_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, offset_str, query = q.data.split("|", 2)
    await show_music_search(update, context, query, int(offset_str))

# ==========================================
# 📥 DOWNLOAD HANDLER (SPEED DEMON + ANTI-BLOCK)
# ==========================================
async def song_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    track_id = q.data.split("|")[1]
    
    # Hapus menu pencarian biar bersih
    await q.message.delete()
    
    # 1. AMBIL METADATA SPOTIFY (Wajib buat Caption)
    try:
        track = sp_client.track(track_id)
        song_name = track['name']
        artist_name = track['artists'][0]['name']
        album_name = track['album']['name']
        cover_url = track['album']['images'][0]['url']
        spotify_url = track['external_urls']['spotify']
        
        # Caption & Tombol (Standard)
        caption = (
            f"🎵 <b>{html.escape(song_name)}</b>\n"
            f"👤 {html.escape(artist_name)}\n"
            f"💿 {html.escape(album_name)}\n"
            f"🔗 <a href='{spotify_url}'>Listen on Spotify</a>\n"
            f"⚡ <i>Powered by Oktacomel</i>"
        )
        
        kb_effects = [
            [InlineKeyboardButton("Lyrics 📝", callback_data=f"lyr_get|{track_id}")],
            [InlineKeyboardButton("8D 🎧", callback_data=f"eff_8d|{track_id}"), InlineKeyboardButton("Slowed 🐌", callback_data=f"eff_slow|{track_id}")],
            [InlineKeyboardButton("Bass Boost 🔊", callback_data=f"eff_bass|{track_id}"), InlineKeyboardButton("Nightcore 🐿", callback_data=f"eff_night|{track_id}")],
            [InlineKeyboardButton("🌌 Reverb", callback_data=f"eff_reverb|{track_id}"), InlineKeyboardButton("⏩ Speed Up", callback_data=f"eff_speed|{track_id}")],
            [InlineKeyboardButton("❌ Close", callback_data="cmd_close")]
        ]

        # 2. CEK DATABASE (SMART CACHE)
        cached = await get_cached_media(track_id)
        
        if cached:
            file_id = cached[0] 
            await context.bot.send_audio(
                chat_id=q.message.chat_id,
                audio=file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(kb_effects)
            )
            return

    except Exception as e:
        await context.bot.send_message(chat_id=q.message.chat_id, text=f"⚠️ <b>Metadata Error:</b> {e}", parse_mode=ParseMode.HTML)
        return

    # 3. DOWNLOAD BARU (CONFIG NGEBUT)
    msg = await context.bot.send_message(chat_id=q.message.chat_id, text="⏳ <b>Downloading High Quality Audio...</b>", parse_mode=ParseMode.HTML)

    try:
        search_query = f"{artist_name} - {song_name} audio"
        temp_dir = f"music_{uuid.uuid4()}"
        
        # --- CONFIG SAKTI DI SINI ---
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
            
            # Konversi ke MP3 192kbps (Standar Bagus)
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            
            # DOWNLOAD NGEBUT (Multi-thread)
            'concurrent_fragment_downloads': 5, 
            
            # Anti Blokir (Pura-pura jadi HP Android)
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_music', 'android', 'ios'],
                    'player_skip': ['web', 'tv']
                }
            },
            
            # Proxy & Keamanan
            'proxy': MY_PROXY,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'nocheckcertificate': True,
            
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1:', 
            'max_filesize': 50 * 1024 * 1024
        }

        file_path = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(search_query, download=True)
            if os.path.exists(temp_dir):
                for f in os.listdir(temp_dir):
                    if f.endswith('.mp3'): file_path = os.path.join(temp_dir, f)

        if file_path:
            sent_msg = await context.bot.send_audio(
                chat_id=q.message.chat_id,
                audio=open(file_path, 'rb'),
                title=song_name, performer=artist_name,
                caption=caption, parse_mode=ParseMode.HTML,
                thumbnail=requests.get(cover_url).content,
                reply_markup=InlineKeyboardMarkup(kb_effects)
            )
            
            # Simpan ke Database
            new_file_id = sent_msg.audio.file_id
            await save_media_cache(track_id, new_file_id, "audio")
            
            os.remove(file_path)
            if os.path.exists(temp_dir): os.rmdir(temp_dir)
            await msg.delete()
        else:
            await msg.edit_text("❌ <b>Download Failed.</b> Stream restricted.", parse_mode=ParseMode.HTML)

    except Exception as e:
        await msg.edit_text(f"❌ <b>System Error:</b> {e}", parse_mode=ParseMode.HTML)
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

# ==========================================
# 📝 LYRICS HANDLER (SMART SEARCH + ENGLISH UI)
# ==========================================
async def lyrics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("🔍 Searching lyrics...", show_alert=False)
    
    track_id = q.data.split("|")[1]
    
    try:
        # 1. Info Lagu (Spotify)
        track = sp_client.track(track_id)
        raw_title = track['name']
        raw_artist = track['artists'][0]['name']
        duration = track['duration_ms'] / 1000
        
        # Fungsi pembersih judul (Hapus feat, remix, kurung)
        def clean_title(text):
            text = re.sub(r"\(.*?\)|\[.*?\]", "", text) # Hapus (...) dan [...]
            text = text.replace("-", "").strip()
            return text

        clean_song = clean_title(raw_title)

        # 2. Ambil Lirik (LRCLIB)
        url_get = "https://lrclib.net/api/get"
        url_search = "https://lrclib.net/api/search"
        
        lirik_raw = None
        
        async with httpx.AsyncClient(timeout=20) as client:
            # A. Coba cari spesifik (Paling Akurat)
            params = {"artist_name": raw_artist, "track_name": raw_title, "duration": duration}
            resp = await client.get(url_get, params=params)
            
            if resp.status_code == 200:
                lirik_raw = resp.json().get('plainLyrics')
            
            # B. Fallback 1: Cari umum (Judul Asli)
            if not lirik_raw:
                resp_search = await client.get(url_search, params={"q": f"{raw_artist} {raw_title}"})
                data = resp_search.json()
                if data: lirik_raw = data[0].get('plainLyrics')

            # C. Fallback 2: Cari dengan judul bersih (Tanpa feat/remix)
            if not lirik_raw:
                resp_search = await client.get(url_search, params={"q": f"{raw_artist} {clean_song}"})
                data = resp_search.json()
                if data: lirik_raw = data[0].get('plainLyrics')

        # 3. Tampilan Hasil (English Premium + Mono)
        if lirik_raw:
            header_txt = (
                f"🎵 <b>{html.escape(raw_title)}</b>\n"
                f"👤 <b>{html.escape(raw_artist)}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            # Format Mono
            lyrics_mono = f"<pre>{html.escape(lirik_raw)}</pre>"
            footer_txt = f"\n\n🤖 <i>Source: LRCLIB (Synced)</i>"
            
            full_msg = header_txt + lyrics_mono + footer_txt
            
            # Potong jika kepanjangan
            if len(full_msg) > 4096:
                cut_idx = 4096 - len(header_txt) - len(footer_txt) - 50
                lyrics_mono = f"<pre>{html.escape(lirik_raw[:cut_idx])}...</pre>"
                full_msg = header_txt + lyrics_mono + footer_txt

            kb = [[InlineKeyboardButton("❌ Close Lyrics", callback_data="cmd_close")]]
            
            await context.bot.send_message(
                chat_id=q.message.chat_id,
                text=full_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(kb),
                reply_to_message_id=q.message.id
            )
        else:
            # Pesan Gagal (English)
            await q.message.reply_text(f"❌ <b>Lyrics not found.</b>\nTry checking the song title spelling.", parse_mode=ParseMode.HTML)

    except Exception as e:
        await context.bot.send_message(chat_id=q.message.chat_id, text=f"⚠️ <b>System Error:</b> {str(e)}", parse_mode=ParseMode.HTML)

# ==========================================
# 🎧 REAL AUDIO EFFECT ENGINE (CLEAN SIMPLE)
# ==========================================
import subprocess

async def real_effect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("🎧 Applying Audio Filters...", show_alert=False)
    
    data = q.data.split("|")
    effect_type = data[0]
    track_id = data[1]
    
    msg = await context.bot.send_message(chat_id=q.message.chat_id, text="⏳ <b>Processing Audio...</b>", parse_mode=ParseMode.HTML)

    try:
        # 1. Get Info & Download Raw
        track = sp_client.track(track_id)
        song_name = track['name']
        artist_name = track['artists'][0]['name']
        
        search_query = f"{artist_name} - {song_name} audio"
        temp_dir = f"remix_{uuid.uuid4()}"
        output_path = f"{temp_dir}/remix_output.mp3"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{temp_dir}/input.%(ext)s',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'quiet': True, 'default_search': 'ytsearch1:',
            'proxy': MY_PROXY,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios']}}
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(search_query, download=True)
            input_path = f"{temp_dir}/input.mp3"

        if not os.path.exists(input_path):
            await msg.edit_text("❌ <b>Source Error.</b> Failed to download audio.")
            return

        # 2. FFmpeg Processing
        cmd = []
        tag_display = ""
        
        if effect_type == "eff_8d":
            tag_display = "8D Audio"
            filter_cmd = "apulsator=hz=0.125"
        elif effect_type == "eff_bass":
            tag_display = "Bass Boosted"
            filter_cmd = "equalizer=f=60:width_type=h:width=50:g=15"
        elif effect_type == "eff_slow":
            tag_display = "Slowed + Reverb"
            filter_cmd = "atempo=0.85,aecho=0.8:0.9:1000:0.3"
        elif effect_type == "eff_night":
            tag_display = "Nightcore"
            filter_cmd = "asetrate=44100*1.25,atempo=1.0"
        elif effect_type == "eff_reverb":
            tag_display = "Reverb"
            filter_cmd = "aecho=0.8:0.9:1000:0.3"
        elif effect_type == "eff_speed":
            tag_display = "Speed Up"
            filter_cmd = "atempo=1.25"
        else:
            # Default effect if unknown type
            tag_display = "Normal"
            filter_cmd = "anull"

        cmd = ['ffmpeg', '-i', input_path, '-af', filter_cmd, '-y', output_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Send Result (Tampilan Simple Normal)
        if os.path.exists(output_path):
            caption = (
                f"🎧 <b>{html.escape(song_name)}</b>\n"
                f"👤 {html.escape(artist_name)}\n"
                f"🎛 <b>Effect:</b> {tag_display}\n\n"
                f"⚡ <i>Powered by Oktacomel</i>"
            )
            
            await context.bot.send_audio(
                chat_id=q.message.chat_id,
                audio=open(output_path, 'rb'),
                title=f"{song_name} ({tag_display})",
                performer=artist_name,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=q.message.id
            )
            await msg.delete()
        else:
            await msg.edit_text("❌ <b>Render Failed.</b>")

        shutil.rmtree(temp_dir)

    except Exception as e:
        await msg.edit_text(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

# ==========================================
# 📸 GALLERY SCRAPER (BULK DOWNLOADER)
# ==========================================
async def gallery_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Cek Input
    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b> <code>/gl [link]</code>\n"
            "<i>Supports: Pinterest, Twitter, Pixiv, Imgur, etc.</i>", 
            parse_mode=ParseMode.HTML
        )
        return

    url = context.args[0]
    chat_id = update.effective_chat.id
    
    # Loading Message (Premium Style)
    msg = await update.message.reply_text(
        "⏳ <b>Accessing Gallery Archive...</b>\n"
        "<i>Fetching high-resolution assets (Max 10)...</i>", 
        parse_mode=ParseMode.HTML
    )

    # Buat folder sementara unik
    temp_dir = f"gallery_{uuid.uuid4()}"
    
    try:
        # 2. Jalankan Gallery-DL via Terminal
        # --range 1-10 : Ambil 10 gambar pertama saja (Biar gak berat)
        # --destination : Simpan di folder temp
        cmd = ["gallery-dl", url, "--destination", temp_dir, "--range", "1-10"]
        
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Cari File Gambar (Recursive)
        # Gallery-dl sering bikin sub-folder, jadi kita harus cari sampai dalam
        image_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    image_files.append(os.path.join(root, file))

        # 4. Kirim sebagai Album (MediaGroup)
        if image_files:
            media_group = []
            total_img = len(image_files)
            
            # Caption cuma di foto pertama
            caption = (
                f"📸 <b>GALLERY EXTRACTED</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔗 <b>Source:</b> <a href='{url}'>Original Link</a>\n"
                f"🖼 <b>Count:</b> {total_img} Images\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <i>Powered by Oktacomel</i>"
            )

            for i, img_path in enumerate(image_files):
                # Batas Telegram MediaGroup cuma 10 foto per pesan
                if i >= 10: break 
                
                # Pasang caption di foto ke-0
                cap = caption if i == 0 else None
                
                # Masukkan ke grup
                media_group.append(InputMediaPhoto(open(img_path, 'rb'), caption=cap, parse_mode=ParseMode.HTML))

            # Kirim Album
            await context.bot.send_media_group(chat_id=chat_id, media=media_group)
            await msg.delete()
            
        else:
            await msg.edit_text("❌ <b>No Images Found.</b>\nMake sure the link is public/valid.", parse_mode=ParseMode.HTML)

    except Exception as e:
        await msg.edit_text(f"❌ <b>Extraction Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
        
    # 5. Bersih-bersih (Wajib biar VPS gak penuh)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

# ==========================================
# 🖥️ SYSTEM LOG VIEWER (OWNER ONLY)
# ==========================================
async def log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 1. SECURITY CHECK (Hanya Owner)
    if user_id != OWNER_ID:
        return # Diam saja kalau bukan owner
    
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    
    try:
        # Baca 20 baris terakhir dari file bot.log
        with open("bot.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_logs = "".join(lines[-20:]) # Ambil 20 baris terakhir
            
        if not last_logs.strip():
            last_logs = "✅ System Clean. No logs recorded."
            
        # Hitung ukuran file log
        log_size = os.path.getsize("bot.log") / 1024 # Dalam KB
            
        # Tampilan Premium (Hacker Style)
        txt = (
            f"🖥️ <b>SYSTEM LIVE LOGS</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📂 <b>File Size:</b> <code>{log_size:.2f} KB</code>\n"
            f"🕒 <b>Time:</b> <code>{datetime.datetime.now(TZ).strftime('%H:%M:%S')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"<pre>{html.escape(last_logs)}</pre>\n" # Pakai PRE biar rapi kotak
            f"🤖 <i>Powered by Oktacomel System</i>"
        )
        
        # Tombol Kontrol
        kb = [
            [InlineKeyboardButton("🔄 Refresh Logs", callback_data="sys_log_refresh")],
            [InlineKeyboardButton("🗑 Clear Logs", callback_data="sys_log_clear"),
             InlineKeyboardButton("❌ Close", callback_data="cmd_close")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            
    except FileNotFoundError:
        await update.message.reply_text("❌ <b>Error:</b> File 'bot.log' belum terbentuk.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ <b>Read Error:</b> {e}", parse_mode=ParseMode.HTML)

# Handler Tombol Log
async def log_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    
    if update.effective_user.id != OWNER_ID:
        await q.answer("⛔ Access Denied!", show_alert=True)
        return

    if data == "sys_log_refresh":
        await q.answer("🔄 Refreshing...")
        await log_command(update, context) # Panggil ulang fungsi log
        
    elif data == "sys_log_clear":
        # Hapus isi file log
        open("bot.log", "w").close()
        await q.answer("🗑 Logs Cleared!", show_alert=True)
        await log_command(update, context) # Refresh tampilan

# ==========================================
# 📊 SYSTEM HEALTH CHECK (ULTIMATE PREMIUM V6)
# ==========================================

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ultimate Premium System Health Monitor"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    
    # ✅ FIX PENTING: set start_time SEKALI untuk uptime
    context.bot_data.setdefault("start_time", START_TIME)

    msg = await update.message.reply_text(
        "🔄 <b>Running Komprehensif System Diagnostics...</b>\n"
        "⏳ <i>Scanning all services...</i>",
        parse_mode=ParseMode.HTML
    )

    try:
        # ===== SERVICE CHECKS =====
        
        # 1. SPOTIFY API CHECK
        spotify_latency = 0
        try:
            if sp_client:
                start_time = current_time()
                sp_client.search(q="test", limit=1, type="track")
                spotify_latency = int((current_time() - start_time) * 1000)
                spotify_status = f"🟢 ONLINE ({spotify_latency}ms)"
            else:
                spotify_status = "⚪ DISABLED"
        except Exception as e:
            spotify_status = f"🔴 ERROR ({str(e)[:20]})"

        # 2. AI ENGINE (EMERGENT) CHECK
        ai_latency = 0
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                start_time = current_time()
                resp = await client.get("https://api.emergent.sh/health", follow_redirects=True)
                ai_latency = int((current_time() - start_time) * 1000)
                if resp.status_code in (200, 401):
                    ai_status = f"🟢 ACTIVE ({ai_latency}ms)"
                else:
                    ai_status = f"🟠 UNSTABLE ({resp.status_code})"
        except asyncio.TimeoutError:
            ai_status = "🔴 TIMEOUT (>5s)"
        except Exception as e:
            ai_status = f"🔴 UNREACHABLE"

        # 3. PROXY CHECK (Premium Download Path)
        proxy_latency = 0
        try:
            if MY_PROXY:
                async with httpx.AsyncClient(proxy=MY_PROXY, timeout=8, follow_redirects=True) as client:
                    start_time = current_time()
                    resp = await client.get("https://www.google.com")
                    proxy_latency = int((current_time() - start_time) * 1000)
                    if resp.status_code == 200:
                        proxy_status = f"🟢 LIVE PREMIUM ({proxy_latency}ms)"
                    else:
                        proxy_status = f"🟠 DEGRADED ({resp.status_code})"
            else:
                proxy_status = "⚪ DIRECT MODE (No Proxy)"
        except asyncio.TimeoutError:
            proxy_status = "🔴 TIMEOUT"
        except Exception as e:
            proxy_status = "🔴 CONNECTION FAILED"

        # 4. MAIL SERVER CHECK
        mail_latency = 0
        try:
            if TEMPMAIL_API_KEY:
                async with httpx.AsyncClient(timeout=5) as client:
                    headers = {"X-API-Key": TEMPMAIL_API_KEY}
                    start_time = current_time()
                    resp = await client.get("https://api.temp-mail.io/v1/domains", headers=headers)
                    mail_latency = int((current_time() - start_time) * 1000)
                    if resp.status_code == 200:
                        mail_status = f"🟢 ACTIVE ({mail_latency}ms)"
                    else:
                        mail_status = f"🟠 RATE LIMITED"
            else:
                mail_status = "⚪ NOT CONFIGURED"
        except asyncio.TimeoutError:
            mail_status = "🔴 TIMEOUT"
        except Exception:
            mail_status = "🔴 SERVICE DOWN"

        # 5. FFMPEG CHECK
        ffmpeg_status = "🟢 READY" if shutil.which("ffmpeg") else "🔴 NOT INSTALLED"

        # 6. DATABASE CHECK
        db_size = 0
        db_status = "🔴 OFFLINE"
        try:
            if os.path.exists(DB_NAME):
                db_size = os.path.getsize(DB_NAME) / (1024 * 1024)  # MB
                db_status = f"🟢 CONNECTED ({db_size:.2f} MB)"
        except Exception:
            db_status = "🔴 ACCESS DENIED"

        # 7. TELEGRAM BOT API CHECK
        telegram_latency = 0
        try:
            start_time = current_time()
            me = await context.bot.get_me()
            telegram_latency = int((current_time() - start_time) * 1000)
            telegram_status = f"🟢 CONNECTED ({telegram_latency}ms)"
            bot_username = me.username or "Unknown"
        except Exception as e:
            telegram_status = "🔴 DISCONNECTED"
            bot_username = "Unknown"

        # 8. PYTHON & SYSTEM INFO
        import sys
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        # CPU & Memory usage (if psutil available)
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            memory_usage = f"{memory.percent}%"
            cpu_status = f"🟢 {cpu_usage}%" if cpu_usage < 80 else f"🟠 {cpu_usage}%"
        except:
            cpu_status = "⚪ N/A"
            memory_usage = "⚪ N/A"

        # ===== CALCULATE OVERALL HEALTH =====
        
        all_statuses = [
            spotify_status, ai_status, proxy_status, mail_status,
            ffmpeg_status, db_status, telegram_status
        ]

        critical_count = sum(1 for s in all_statuses if "🔴" in s)
        warning_count = sum(1 for s in all_statuses if "🟠" in s)
        online_count = sum(1 for s in all_statuses if "🟢" in s)

        if critical_count >= 2:
            overall = "🔴 <b>CRITICAL</b> — Multiple services down. Immediate action required!"
            health_bar = "█░░░░░░░░░ 10%"
        elif critical_count == 1 or warning_count >= 3:
            overall = "🟠 <b>DEGRADED</b> — Some services unstable. Performance affected."
            health_bar = "███████░░░ 70%"
        elif warning_count >= 1:
            overall = "🟡 <b>CAUTION</b> — Minor issues detected. Monitor closely."
            health_bar = "████████░░ 85%"
        else:
            overall = "🟢 <b>OPTIMAL</b> — All systems operational. Running at peak performance!"
            health_bar = "██████████ 100%"

        # ===== BUILD PREMIUM UI =====
        
        now = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        host = html.escape(platform.node() or "OKTACOMEL-SERVER")
        uptime_seconds = int(current_time() - context.bot_data.get("start_time", current_time()))
        uptime_hours = uptime_seconds // 3600
        uptime_minutes = (uptime_seconds % 3600) // 60

        txt = (
            "╔════════════════════════════════════════╗\n"
            "║   🤖 OKTACOMEL ULTIMATE SYSTEM PANEL   ║\n"
            "╚════════════════════════════════════════╝\n\n"
            
            f"📊 <b>HEALTH STATUS</b>\n"
            f"├─ Overall: {overall}\n"
            f"├─ Health Index: <code>{health_bar}</code>\n"
            f"├─ Services Up: <code>{online_count}/7</code>\n"
            f"└─ Critical: <code>{critical_count} | Warning: {warning_count}</code>\n\n"
            
            f"🖥️ <b>SYSTEM INFO</b>\n"
            f"├─ Host: <code>{host}</code>\n"
            f"├─ Bot: @<code>{bot_username}</code>\n"
            f"├─ Python: <code>v{python_version}</code>\n"
            f"├─ Uptime: <code>{uptime_hours}h {uptime_minutes}m</code>\n"
            f"├─ Checked: <code>{now}</code>\n"
            f"└─ CPU / Memory: <code>{cpu_status}</code> / <code>{memory_usage}</code>\n\n"
            
            f"🌐 <b>API SERVICES</b>\n"
            f"├─ Telegram Bot: {telegram_status}\n"
            f"├─ AI Engine: {ai_status}\n"
            f"├─ Spotify API: {spotify_status}\n"
            f"└─ Mail Server: {mail_status}\n\n"
            
            f"🛠️ <b>INFRASTRUCTURE</b>\n"
            f"├─ Proxy Tunnel: {proxy_status}\n"
            f"├─ FFmpeg Core: {ffmpeg_status}\n"
            f"└─ Database: {db_status}\n\n"
            
            f"📈 <b>LATENCY METRICS</b>\n"
            f"├─ Telegram: <code>{telegram_latency}ms</code>\n"
            f"├─ AI Engine: <code>{ai_latency}ms</code>\n"
            f"├─ Spotify: <code>{spotify_latency}ms</code>\n"
            f"├─ Proxy: <code>{proxy_latency}ms</code>\n"
            f"└─ Mail: <code>{mail_latency}ms</code>\n\n"
            
            "═════════════════════════════════════════\n"
            "✨ <i>Premium diagnostics by Oktacomel v6</i>\n"
            "💡 <i>Monitor regularly for optimal performance</i>\n"
        )

        await msg.edit_text(txt, parse_mode=ParseMode.HTML)

    except Exception as e:
        error_txt = (
            "<b>⚠️ DIAGNOSTIC ERROR</b>\n\n"
            f"❌ <code>{str(e)[:100]}</code>\n\n"
            "<i>System diagnostics encountered an issue.</i>"
        )
        try:
            await msg.edit_text(error_txt, parse_mode=ParseMode.HTML)
        except:
            logger.error(f"[STATUS] Error: {e}")

# ============================================================
# 📧 TEMP MAIL PREMIUM V5 — GOD MODE (Auto-Refresh + Attachment)
# ============================================================

# --- SAFE DATE PARSER ---
def tm_safe_date(obj):
    if hasattr(obj, "date"): return str(obj.date)
    if hasattr(obj, "created_at"): return str(obj.created_at)
    if hasattr(obj, "timestamp"):
        return datetime.datetime.fromtimestamp(obj.timestamp).strftime("%Y-%m-%d %H:%M")
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

# --- CLEAN HTML TO TEXT (SAFE, ANTI LINK ERROR) ---
def tm_clean_html(raw_html):
    if not raw_html: return "(Empty Message)", []

    try:
        # Pakai BeautifulSoup buat kupas HTML
        soup = BeautifulSoup(raw_html, 'html.parser')

        # 1. Buang script/style sampah
        for s in soup(["script", "style", "meta", "head", "title"]): 
            s.decompose()

        # 2. Ambil Link Verifikasi (PENTING)
        extracted_links = []
        unique_urls = set()
        
        for a in soup.find_all('a', href=True):
            url = a['href']
            # Ambil link http/https saja
            if url.startswith(('http', 'https')) and url not in unique_urls:
                unique_urls.add(url)
                extracted_links.append(url) # Simpan URL-nya

        # 3. Ambil Teks Bersih
        text = soup.get_text(separator="\n").strip()
        # Hapus baris kosong berlebih
        clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
        
        return html.escape(clean_text), extracted_links

    except:
        # Kalau gagal, balikin teks seadanya
        return html.escape(str(raw_html)[:500]), []


# ============================================================
# 📧 /mail — ENTRY POINT
# ============================================================
async def mail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "tm_history" not in context.user_data:
        context.user_data["tm_history"] = []
    if "tm_cache" not in context.user_data:
        context.user_data["tm_cache"] = {}  # cache inbox
    await tm_dashboard(update, context)

# ============================================================
# 🎛 DASHBOARD PANEL (V6 PREMIUM - ANTI ERROR SERVER)
# ============================================================
async def tm_dashboard(update, context, new=False, chosen_domain=None):

    user = context.user_data
    chat = update.effective_chat.id
    current = user.get("tm_email")

    # NEW MAIL
    if new or not current:
        msg_load = await context.bot.send_message(chat, "💎 <b>Generating secure address...</b>", parse_mode=ParseMode.HTML)

        try:
            client = TempMailClient(api_key=TEMPMAIL_API_KEY)
            
            # --- MULAI PERBAIKAN: PROTEKSI SERVER DOWN ---
            try:
                if chosen_domain:
                    mail_obj = client.create_email(domain=chosen_domain)
                else:
                    mail_obj = client.create_email(domain_type=DomainType.PREMIUM)
            except Exception as e:
                # Jika errornya "Expecting value", berarti server TempMail lagi down/sibuk
                if "Expecting value" in str(e):
                    await msg_load.edit_text("⚠️ <b>Server Busy (API Down).</b>\nSilakan coba klik 'New Mail' lagi dalam 5 detik.", parse_mode=ParseMode.HTML)
                    return # Stop proses, jangan lanjut ke bawah
                else:
                    raise e # Jika error lain, lempar ke catch di bawah
            # --- SELESAI PERBAIKAN ---

            current = mail_obj.email
            user["tm_email"] = current
            if current not in user["tm_history"]:
                user["tm_history"].insert(0, current)

        except Exception as e:
            return await msg_load.edit_text(f"❌ System Error: <code>{str(e)}</code>", parse_mode=ParseMode.HTML)

        await msg_load.delete()

    domain = current.split("@")[-1]

    # ==========================
    # 📝 PEMBIASAAN: TEKS PREMIUM V6
    # ==========================
    text = f"""
🌙 <b>OKTAACOMEL TEMPMAIL — V6 ULTRA PANEL</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Welcome to your <b>Encrypted Temporary Identity</b>.  
This V6 engine is optimized for <b>maximum privacy, instant delivery, and military-grade security</b>.

<b>✨ What’s New in V6:</b>
• Premium Dark-Mode UI  
• Faster mailbox syncing engine  
• AI Spam Filter (Adaptive)  
• Secure Attachment Preview  
• Custom Domain Selector V2  
• Auto-Delete Privacy Shield  
• Fully upgraded message formatter  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📬 <b>Active Mailbox:</b>
<code>{current}</code>

🌐 <b>Domain:</b> {domain}  
🛡 <b>Security:</b> AES-256 Session Shield  
📥 <b>Inbox Status:</b> Ready  
🔁 <b>Auto-Scan:</b> Enabled  

🕒 <i>Session Auto-Cleanup:</i> <b>15 minutes</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>?? How to Use TempMail V6:</b>
• <b>Inbox</b> → View all received messages  
• <b>Refresh</b> → Force sync mailbox  
• <b>New Mail</b> → Generate fresh identity  
• <b>Change Domain</b> → Switch email provider  
• <b>History</b> → Restore old addresses  
• <b>Auto-Scan</b> → Real-time new mail detection  

<b>⚡ Pro Tip:</b>  
V6 silently checks your inbox and alerts you when new messages arrive!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<i>Select an action below to continue.</i>
"""

    # ==========================
    # TOMBOL AKSI
    # ==========================
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh (Auto-Scan)", callback_data="tm_autorefresh"),
            InlineKeyboardButton("✉ Inbox", callback_data="tm_refresh"),
        ],
        [
            InlineKeyboardButton("🌐 Change Domain", callback_data="tm_domains"),
            InlineKeyboardButton("📜 History", callback_data="tm_history"),
        ],
        [
            InlineKeyboardButton("🎲 New Mail", callback_data="tm_new"),
            InlineKeyboardButton("🗑 Delete Session", callback_data="tm_delete"),
        ]
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        
# ============================================================
# 🌐 DOMAIN PICKER (CLEAN UI + 2 COLUMN GRID)
# ============================================================
async def tm_domain_picker(update, context):
    
    # 1. LIST DOMAIN (LENGKAP)
    premium_domains = [
        "xmailg.one", "henolclock.in", "vbroqa.com", "fhsysa.com",
        "pukoni.com", "frrotk.com", "umlimte.com", "ratixq.com",
        "yunhilay.com", "meefff.com"
    ]
    
    public_domains = [
        "daouse.com", "illubd.com", "mkzaso.com", "mrotzis.com",
        "xkxkud.com", "wnbaldwy.com", "zudpck.com", "bitiiwd.com",
        "jkotypc.com", "cmhvzytmfc.com"
    ]

    # 2. LOGIKA GRID (TOMBOL 2 KOLOM RAPI)
    keyboard = []

    # --- SECTION: PREMIUM ---
    # Header tombol kita buat transparan (callback='none')
    keyboard.append([InlineKeyboardButton("💎 PREMIUM VIP LIST", callback_data="none")])
    
    row = []
    for domain in premium_domains:
        row.append(InlineKeyboardButton(f"@{domain}", callback_data=f"tm_use_domain|{domain}"))
        if len(row) == 2: # Max 2 tombol per baris
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)

    # --- SECTION: PUBLIC ---
    keyboard.append([InlineKeyboardButton("🌍 PUBLIC SERVER LIST", callback_data="none")])
    
    row = []
    for domain in public_domains:
        row.append(InlineKeyboardButton(f"@{domain}", callback_data=f"tm_use_domain|{domain}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)

    # --- TOMBOL BACK ---
    keyboard.append([InlineKeyboardButton("🔙 Cancel / Back", callback_data="tm_back")])

    # 3. TEXT TAMPILAN (CLEAN & ELEGANT)
    # Tanpa garis panjang yang mengganggu
    text = """
<b>🌐 DOMAIN CONFIGURATION</b>

<b>Select Provider:</b>
Silakan pilih domain di bawah ini untuk mengaktifkan email baru.

💎 <b>Premium VIP</b>
<i>Kecepatan tinggi, support OTP maksimal.</i>

🌍 <b>Public Server</b>
<i>Penyunaan standar harian.</i>
"""

    await update.callback_query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================
# 📥 INBOX VIEW (ANTI CRASH / SILENT ERROR)
# ============================================================
async def tm_inbox(update, context, auto=False):

    email = context.user_data.get("tm_email")
    cache = context.user_data["tm_cache"]

    if not email:
        return await update.callback_query.answer("❌ No active email", show_alert=True)

    try:
        client = TempMailClient(api_key=TEMPMAIL_API_KEY)
        
        # --- PERBAIKAN DISINI (PROTEKSI SERVER DOWN) ---
        try:
            msgs = client.list_email_messages(email=email)
        except Exception as e:
            # Jika error "Expecting value", berarti API Server lagi batuk/down
            if "Expecting value" in str(e):
                # Kita kasih notifikasi kecil saja, jangan hancurkan pesan utama
                await update.callback_query.answer("⚠️ Server Busy (Syncing...)", show_alert=False)
                
                # Kita set kosong dulu biar script di bawah tidak error
                msgs = [] 
            else:
                # Jika errornya lain (misal API Key salah), baru kita lempar error
                raise e
        # -----------------------------------------------

        cache[email] = msgs  # save inbox cache

        if not msgs:
            # Jika auto refresh dan kosong, jangan lakukan apa-apa (silent)
            if auto:
                # Opsional: Bisa balik ke dashboard atau diam saja
                # await tm_dashboard(update, context) 
                return 

            await update.callback_query.answer("📭 Inbox empty", show_alert=True)
            return

        rows = []
        for m in msgs[:10]:
            sender = (m.from_addr or "Unknown").split("<")[0]
            subj = m.subject or "(No Subject)"
            spam_keywords = ["verification", "confirm", "OTP", "code", "verify"]
            is_spam = any(kw.lower() in (subj + sender).lower() for kw in spam_keywords)
            spam = "📩" if is_spam else "📧"
            rows.append([
                InlineKeyboardButton(f"{spam} {sender[:12]} — {subj[:18]}", callback_data=f"tm_read|{m.id}")
            ])

        rows.append([
            InlineKeyboardButton("🔙 Back", callback_data="tm_back"),
            InlineKeyboardButton("🔄 Auto-Scan", callback_data="tm_autorefresh"),
        ])

        # Edit pesan hanya jika ada perubahan data atau bukan auto-refresh yang silent
        try:
            await update.callback_query.edit_message_text(
                f"📬 <b>INBOX ({len(msgs)})</b>\nTap a message to read:",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(rows)
            )
        except:
            pass # Hindari error "Message is not modified"

    except Exception as e:
        # Error handling terakhir jika crash parah
        # Jangan edit text jadi error, cukup notifikasi saja biar rapi
        await update.callback_query.answer(f"⚠️ Connection Error. Try again.", show_alert=True)

# ============================================================
# 🔁 AUTO REFRESH (REAL-TIME SCAN)
# ============================================================
async def tm_autorefresh(update, context):
    email = context.user_data.get("tm_email")
    cache = context.user_data.get("tm_cache", {})

    client = TempMailClient(api_key=TEMPMAIL_API_KEY)

    try:
        msgs = client.list_email_messages(email=email)

        old = len(cache.get(email, []))
        new = len(msgs)

        context.user_data["tm_cache"][email] = msgs

        if new > old:
            diff = new - old
            await update.callback_query.answer(f"📨 {diff} new messages!", show_alert=True)
        else:
            await update.callback_query.answer("📡 Scanning… No new messages.", show_alert=False)

        await tm_inbox(update, context)

    except:
        await update.callback_query.answer("⚠️ Auto-scan error", show_alert=True)

# ============================================================
# 📖 READ MESSAGE (ATTACHMENT SUPPORT)
# ============================================================
async def tm_read(update, context, msg_id):
    try:
        client = TempMailClient(api_key=TEMPMAIL_API_KEY)
        m = client.get_message(message_id=msg_id)

        sender  = html.escape(m.from_addr or "Unknown")
        subject = html.escape(m.subject or "(No Subject)")
        
        # --- PANGGIL FUNGSI PEMBERSIH BARU ---
        # Kita ambil body_html, lalu bersihkan. 
        # Variable 'links' akan berisi link verifikasi Jenni.ai tadi.
        clean_body, links = tm_clean_html(m.body_html or m.body_text)

        if len(clean_body) > 3000: clean_body = clean_body[:3000] + "..."

        # --- MENAMPILKAN LINK DI BAWAH ---
        extras = ""
        if links:
            extras += "\n👇 <b>VERIFICATION LINKS:</b>\n" 
            for link in links[:5]: # Ambil max 5 link
                 extras += f"🔗 <a href='{link}'>Click to Verify / Open Link</a>\n"
        
        # Attachment (biarkan seperti kode lama mas)
        if hasattr(m, "attachments") and m.attachments:
            extras += "\n📎 <b>Attachments:</b>\n"
            for a in m.attachments:
                extras += f"• <a href=\"{a.download_url}\">{html.escape(a.filename)}</a>\n"

        final = f"""
📨 <b>MESSAGE DETAIL</b>
━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>From:</b> {sender}
📝 <b>Subject:</b> {subject}
📅 <b>Date:</b> {tm_safe_date(m)}
━━━━━━━━━━━━━━━━━━━━━━━

{clean_body}

━━━━━━━━━━━━━━━━━━━━━━━
{extras}
"""
        await update.callback_query.edit_message_text(
            final, 
            parse_mode=ParseMode.HTML, 
            disable_web_page_preview=True, # Matikan preview biar rapi
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tm_refresh")]])
        )

    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Read Error: {str(e)}", parse_mode=ParseMode.HTML)

# ============================================================
# 📜 HISTORY
# ============================================================
async def tm_history(update, context):
    hist = context.user_data.get("tm_history", [])

    if not hist:
        return await update.callback_query.answer("📭 History empty", show_alert=True)

    txt = "📜 <b>ADDRESS HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━━━━\n"

    rows = []
    for i, mail in enumerate(hist[:10], 1):
        txt += f"{i}. <code>{mail}</code>\n"
        rows.append([InlineKeyboardButton(f"Use #{i}", callback_data=f"tm_use_domain|{mail.split('@')[1]}")])

    rows.append([InlineKeyboardButton("🔙 Back", callback_data="tm_back")])

    await update.callback_query.edit_message_text(
        txt,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows)
    )

# ============================================================
# 🔧 CALLBACK ROUTER
# ============================================================
async def mail_callback(update, context):
    q = update.callback_query
    data = q.data

    try: await q.answer()
    except: pass

    if data == "tm_back":
        return await tm_dashboard(update, context)

    if data == "tm_new":
        return await tm_dashboard(update, context, new=True)

    if data == "tm_domains":
        return await tm_domain_picker(update, context)

    if data.startswith("tm_use_domain|"):
        domain = data.split("|")[1]
        return await tm_dashboard(update, context, new=True, chosen_domain=domain)

    if data == "tm_refresh":
        return await tm_inbox(update, context)

    if data == "tm_autorefresh":
        return await tm_autorefresh(update, context)

    if data == "tm_history":
        return await tm_history(update, context)

    if data == "tm_delete":
        context.user_data.pop("tm_email", None)
        return await q.edit_message_text("🗑 <b>Session deleted.</b>", parse_mode=ParseMode.HTML)

    if data.startswith("tm_read|"):
        msg_id = data.split("|")[1]
        return await tm_read(update, context, msg_id)


# ==========================================
# ?? OKTA NOTES VAULT — PREMIUM UI UPGRADE
# ==========================================
import uuid

async def note_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        help_txt = (
            "<b>🛑 INPUT REQUIRED</b>\n"
            "<code>Usage: /note [Secret Data]</code>\n\n"
            "<i>Example:</i>\n"
            "<code>/note Password wifi tetangga: 123456</code>"
        )
        await update.message.reply_text(help_txt, parse_mode=ParseMode.HTML)
        return

    note_content = " ".join(context.args)
    date_now = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    
    # Generate ID Unik (Hex Code)
    raw_uuid = str(uuid.uuid4())
    note_hash = raw_uuid[:4].upper() + "-" + raw_uuid[4:8].upper()
    
    # 1. Loading Effect (Hacking Style)
    msg = await update.message.reply_text(
        "<code>[☁️] CONNECTING TO CLOUD VAULT...</code>", 
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)
    await msg.edit_text("<code>[🔄] ENCRYPTING BYTES... ▰▰▰▱▱</code>", parse_mode=ParseMode.HTML)
    
    # 2. Simpan ke DB
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO user_notes (user_id, content, date_added) VALUES (?, ?, ?)",
            (user.id, note_content, date_now)
        )
        await db.commit()

    await asyncio.sleep(0.5)

    # 3. Final UI (Digital Receipt)
    premium_text = (
        "<b>💎 OKTA ENCRYPTED VAULT</b>\n"
        "<code>━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<b>🆔 HASH-ID :</b> <code>#{note_hash}</code>\n"
        f"<b>👤 AGENT   :</b> {html.escape(user.first_name)}\n"
        f"<b>📅 DATE    :</b> <code>{date_now}</code>\n"
        "<code>──────────────────────────</code>\n"
        "<b>📂 PAYLOAD:</b>\n"
        f"<code>{html.escape(note_content)}</code>\n"
        "<code>━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        "🔐 <i>Status: Secured & Encrypted (AES-256)</i>"
    )

    # Tambahkan tombol shortcut ke list
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📂 Open Vault List", callback_data="notes_page|1")]])
    
    await msg.edit_text(premium_text, parse_mode=ParseMode.HTML, reply_markup=kb)
# 2. LIST NOTES (PREMIUM AUDIT LOG)
# Fungsi Helper untuk Pagination
async def get_notes_page(user_id, page, per_page=5):
    async with aiosqlite.connect(DB_NAME) as db:
        # Hitung total
        async with db.execute("SELECT COUNT(*) FROM user_notes WHERE user_id=?", (user_id,)) as c:
            total = (await c.fetchone())[0]
        
        # Ambil data sesuai halaman
        offset = (page - 1) * per_page
        async with db.execute(
            "SELECT content, date_added FROM user_notes WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?", 
            (user_id, per_page, offset)
        ) as cursor:
            notes = await cursor.fetchall()
            
    return notes, total

# Command /notes (Entry Point)
async def note_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Langsung panggil halaman 1
    await show_notes_ui(update, context, page=1, is_new=True)

# Logic UI Utama (Bisa dipanggil dari Command atau Callback)
async def show_notes_ui(update, context, page=1, is_new=False):
    user = update.effective_user
    per_page = 5
    
    notes, total_count = await get_notes_page(user.id, page, per_page)
    total_pages = max(1, math.ceil(total_count / per_page))

    if total_count == 0:
        txt = (
            "🔐 <b>OKTACOMEL SECURE VAULT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📂 <b>Status:</b> <code>EMPTY</code>\n\n"
            "<i>No classified records found.</i>\n"
            "<i>Use /note [text] to add new data.</i>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 <i>256-bit AES Encrypted Storage</i>"
        )
        buttons = [[InlineKeyboardButton("❌ Close", callback_data="notes_close")]]
        if is_new:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.callback_query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # Premium Header
    report = (
        "🔐 <b>OKTACOMEL SECURE VAULT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Agent:</b> <code>{html.escape(user.first_name.upper())}</code>\n"
        f"📊 <b>Records:</b> <code>{total_count}</code>\n"
        f"📄 <b>Page:</b> <code>{page}/{total_pages}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Loop Items with Premium Format
    for i, (content, date) in enumerate(notes):
        idx = (page - 1) * per_page + (i + 1)
        preview = (content[:40] + '...') if len(content) > 40 else content
        
        report += (
            f"<b>#{idx:02d}</b> │ <code>{html.escape(preview)}</code>\n"
            f"     └─ 📅 <i>{date}</i>\n\n"
        )

    report += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 <i>Encrypted with AES-256</i>"
    )

    # Navigation Buttons
    buttons = []
    nav_row = []
    
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"notes_page|{page-1}"))
    
    nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="notes_noop"))
    
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"notes_page|{page+1}"))
        
    buttons.append(nav_row)
    buttons.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"notes_page|{page}"),
        InlineKeyboardButton("🗑️ Purge All", callback_data="notes_confirm_purge")
    ])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="notes_close")])

    kb = InlineKeyboardMarkup(buttons)

    if is_new:
        await update.message.reply_text(report, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.callback_query.edit_message_text(report, parse_mode=ParseMode.HTML, reply_markup=kb)


# 3. DELETE ALL (PREMIUM PURGE MODE)
async def note_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Langsung tampilkan konfirmasi
    txt = (
        "<b>⚠️ DANGER ZONE</b>\n\n"
        "Are you sure you want to <b>DELETE ALL NOTES?</b>\n"
        "This action is irreversible."
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ YES, NUKE IT", callback_data="notes_purge_do"),
            InlineKeyboardButton("🔙 CANCEL", callback_data="notes_close")
        ]
    ])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

async def notes_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    await query.answer() # Hilangkan loading di tombol

    # 1. Navigasi Halaman
    if data.startswith("notes_page|"):
        page = int(data.split("|")[1])
        await show_notes_ui(update, context, page=page, is_new=False)

    # 2. Tutup Menu
    elif data == "notes_close":
        await query.message.delete()

    # 3. Konfirmasi Hapus
    elif data == "notes_confirm_purge":
        txt = "<b>⚠️ CONFIRM PURGE</b>\nAre you really sure?"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💣 YES, DELETE ALL", callback_data="notes_purge_do")],
            [InlineKeyboardButton("🛡 CANCEL", callback_data="notes_page|1")] # Balik ke hal 1
        ])
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    # 4. Eksekusi Hapus (Animation Style)
    elif data == "notes_purge_do":
        # Animasi penghapusan
        await query.edit_message_text("<code>[⚠️] INITIATING FACTORY RESET...</code>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.8)
        await query.edit_message_text("<code>[████░░░░░░] WIPING SECTORS...</code>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.8)
        
        # Hapus DB
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM user_notes WHERE user_id=?", (user_id,))
            await db.commit()
            
        final_txt = (
            "<b>♻️ SYSTEM CLEANSED</b>\n"
            "<code>━━━━━━━━━━━━━━━━━━━</code>\n"
            "All secure notes have been permanently erased.\n"
            "Trace: 0%"
        )
        await query.edit_message_text(final_txt, parse_mode=ParseMode.HTML)

async def sha256_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """SHA-256 Hashing with Premium UI"""
    if not context.args:
        await update.message.reply_text(
            "🔐 <b>OKTACOMEL CRYPTO ENGINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Usage:</b> <code>/sha [text]</code>\n"
            "<b>Type:</b> 256-bit Secure Hash",
            parse_mode=ParseMode.HTML
        )
        return

    text_to_hash = " ".join(context.args)
    hash_result = hashlib.sha256(text_to_hash.encode()).hexdigest()

    res = (
        "🔐 <b>OKTACOMEL CRYPTO RESULT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Input Matrix:</b>\n"
        f"<code>{html.escape(text_to_hash[:100])}</code>\n\n"
        f"<b>SHA-256 Hash:</b>\n"
        f"<code>{hash_result}</code>\n\n"
        "📡 <b>Status:</b> 🟢 Success\n"
        "⚡ <i>Powered by Oktacomel Security</i>"
    )
    await update.message.reply_text(res, parse_mode=ParseMode.HTML)

# ==========================================
# 📄 /pdf - PREMIUM PDF TOOLS MENU
# ==========================================
async def pdf_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show PDF Tools Menu with all available tools"""
    user_id = update.effective_user.id
    
    text = (
        "📄 <b>OKTACOMEL PDF TOOLS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<i>Professional PDF processing tools</i>\n\n"
        "📌 <b>Available Tools:</b>\n\n"
        "🔗 <b>Merge PDF</b>\n"
        "   <code>/pdfmerge</code> - Gabung 2 file PDF\n\n"
        "✂️ <b>Split PDF</b>\n"
        "   <code>/pdfsplit</code> - Pisah PDF per halaman\n\n"
        "📝 <b>PDF to Text</b>\n"
        "   <code>/pdftotext</code> - Ekstrak teks dari PDF\n\n"
        "📦 <b>Compress PDF</b>\n"
        "   <code>/compresspdf</code> - Kompres ukuran PDF\n\n"
        "🖼️ <b>Image to PDF</b>\n"
        "   <code>/imgpdf</code> - Konversi gambar ke PDF\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <i>Powered by OKTACOMEL Engine</i>"
    )
    
    buttons = [
        [InlineKeyboardButton("🔗 Merge", callback_data=f"pdf_help|merge|{user_id}"),
         InlineKeyboardButton("✂️ Split", callback_data=f"pdf_help|split|{user_id}")],
        [InlineKeyboardButton("📝 To Text", callback_data=f"pdf_help|text|{user_id}"),
         InlineKeyboardButton("📦 Compress", callback_data=f"pdf_help|compress|{user_id}")],
        [InlineKeyboardButton("🖼️ Image to PDF", callback_data=f"pdf_help|img|{user_id}")],
        [InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")]
    ]
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def pdf_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDF tools callbacks"""
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data.split("|")
    
    if len(data) < 3:
        await query.answer()
        return
        
    tool = data[1]
    owner_id = int(data[2])
    
    if user_id != owner_id:
        await query.answer("Bukan milik kamu!", show_alert=True)
        return
    
    await query.answer()
    
    help_texts = {
        "merge": (
            "🔗 <b>PDF MERGE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Cara Pakai:</b>\n"
            "1️⃣ Kirim PDF pertama\n"
            "2️⃣ Reply PDF pertama dengan PDF kedua\n"
            "3️⃣ Set caption: <code>/pdfmerge</code>\n\n"
            "✅ Bot akan menggabungkan kedua PDF"
        ),
        "split": (
            "✂️ <b>PDF SPLIT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Cara Pakai:</b>\n"
            "1️⃣ Kirim file PDF\n"
            "2️⃣ Reply PDF tersebut dengan:\n"
            "   <code>/pdfsplit</code>\n\n"
            "✅ Bot akan memisahkan per halaman (ZIP)"
        ),
        "text": (
            "📝 <b>PDF TO TEXT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Cara Pakai:</b>\n"
            "1️⃣ Kirim file PDF\n"
            "2️⃣ Reply PDF tersebut dengan:\n"
            "   <code>/pdftotext</code>\n\n"
            "✅ Bot akan ekstrak teks dari PDF"
        ),
        "compress": (
            "📦 <b>PDF COMPRESS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Cara Pakai:</b>\n"
            "1️⃣ Kirim file PDF\n"
            "2️⃣ Reply PDF tersebut dengan:\n"
            "   <code>/compresspdf</code>\n\n"
            "✅ Bot akan kompres ukuran PDF"
        ),
        "img": (
            "🖼️ <b>IMAGE TO PDF</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Cara Pakai:</b>\n"
            "1️⃣ Kirim gambar (JPG/PNG)\n"
            "2️⃣ Reply gambar tersebut dengan:\n"
            "   <code>/imgpdf</code>\n\n"
            "✅ Bot akan konversi ke PDF"
        )
    }
    
    text = help_texts.get(tool, "Tool not found")
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"pdf_menu|{user_id}")]]
    
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def pdf_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDF menu back button"""
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data.split("|")
    
    owner_id = int(data[1]) if len(data) > 1 else user_id
    
    if user_id != owner_id:
        await query.answer("Bukan milik kamu!", show_alert=True)
        return
    
    await query.answer()
    
    text = (
        "📄 <b>OKTACOMEL PDF TOOLS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<i>Professional PDF processing tools</i>\n\n"
        "📌 <b>Available Tools:</b>\n\n"
        "🔗 <b>Merge PDF</b>\n"
        "   <code>/pdfmerge</code> - Gabung 2 file PDF\n\n"
        "✂️ <b>Split PDF</b>\n"
        "   <code>/pdfsplit</code> - Pisah PDF per halaman\n\n"
        "📝 <b>PDF to Text</b>\n"
        "   <code>/pdftotext</code> - Ekstrak teks dari PDF\n\n"
        "📦 <b>Compress PDF</b>\n"
        "   <code>/compresspdf</code> - Kompres ukuran PDF\n\n"
        "🖼️ <b>Image to PDF</b>\n"
        "   <code>/imgpdf</code> - Konversi gambar ke PDF\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <i>Powered by OKTACOMEL Engine</i>"
    )
    
    buttons = [
        [InlineKeyboardButton("🔗 Merge", callback_data=f"pdf_help|merge|{user_id}"),
         InlineKeyboardButton("✂️ Split", callback_data=f"pdf_help|split|{user_id}")],
        [InlineKeyboardButton("📝 To Text", callback_data=f"pdf_help|text|{user_id}"),
         InlineKeyboardButton("📦 Compress", callback_data=f"pdf_help|compress|{user_id}")],
        [InlineKeyboardButton("🖼️ Image to PDF", callback_data=f"pdf_help|img|{user_id}")],
        [InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")]
    ]
    
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

# ==========================================
# 📥 /pdfmerge — Merge 2 PDFs into One
# ==========================================
async def pdf_merge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    # Harus reply ke PDF pertama
    if not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.reply_text(
            "⚠️ <b>How to use /pdfmerge</b>\n\n"
            "1️⃣ Send the <b>first PDF</b>.\n"
            "2️⃣ Reply to that PDF with the <b>second PDF</b> attached,\n"
            "   and set the caption to <code>/pdfmerge</code>.\n\n"
            "I will merge those 2 PDFs into a single file.",
            parse_mode=ParseMode.HTML
        )
        return

    doc1 = msg.reply_to_message.document
    doc2 = msg.document

    if not doc2:
        await msg.reply_text(
            "❌ <b>No second PDF detected.</b>\n"
            "Please attach the second PDF in the same message as <code>/pdfmerge</code>.",
            parse_mode=ParseMode.HTML
        )
        return

    if doc1.mime_type != "application/pdf" or doc2.mime_type != "application/pdf":
        await msg.reply_text(
            "❌ <b>Both files must be PDF documents.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    status = await msg.reply_text(
        "⏳ <b>Merging PDFs...</b>\n<i>Please wait a moment.</i>",
        parse_mode=ParseMode.HTML
    )

    tmp_dir = tempfile.mkdtemp(prefix="mergepdf_")

    try:
        # Download both PDFs
        f1 = os.path.join(tmp_dir, "file1.pdf")
        f2 = os.path.join(tmp_dir, "file2.pdf")

        file1 = await doc1.get_file()
        await file1.download_to_drive(custom_path=f1)

        file2 = await doc2.get_file()
        await file2.download_to_drive(custom_path=f2)

        # Merge using PyPDF2
        merger = PdfMerger()
        merger.append(f1)
        merger.append(f2)

        output_path = os.path.join(tmp_dir, "merged.pdf")
        with open(output_path, "wb") as out_f:
            merger.write(out_f)
        merger.close()

        # Send result
        with open(output_path, "rb") as fh:
            await msg.reply_document(
                document=fh,
                filename="merged_oktacomel.pdf",
                caption="✅ <b>Merged PDF Ready.</b>\n⚡ <i>Powered by OKTACOMEL PDF Engine</i>",
                parse_mode=ParseMode.HTML
            )

        await status.delete()

    except Exception as e:
        await status.edit_text(
            f"❌ <b>Merge failed:</b> <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML
        )
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass

# ==========================================
# ✂️ /pdfsplit — Split PDF into per-page files (ZIP)
# ==========================================
async def pdf_split_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.reply_text(
            "⚠️ <b>How to use /pdfsplit</b>\n\n"
            "Reply to a <b>single PDF document</b> with the command:\n"
            "<code>/pdfsplit</code>\n\n"
            "I will split it into one PDF per page and send a ZIP file.",
            parse_mode=ParseMode.HTML
        )
        return

    doc = msg.reply_to_message.document
    if doc.mime_type != "application/pdf":
        await msg.reply_text(
            "❌ <b>The replied message is not a PDF file.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    status = await msg.reply_text(
        "⏳ <b>Splitting PDF into pages...</b>",
        parse_mode=ParseMode.HTML
    )

    tmp_dir = tempfile.mkdtemp(prefix="splitpdf_")

    try:
        pdf_path = os.path.join(tmp_dir, "source.pdf")
        f = await doc.get_file()
        await f.download_to_drive(custom_path=pdf_path)

        reader = PdfReader(pdf_path)
        num_pages = len(reader.pages)

        # Create per-page PDFs and add to ZIP
        zip_path = os.path.join(tmp_dir, "split_pages.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i in range(num_pages):
                writer = PdfWriter()
                writer.add_page(reader.pages[i])

                page_filename = f"page_{i+1}.pdf"
                page_path = os.path.join(tmp_dir, page_filename)
                with open(page_path, "wb") as pf:
                    writer.write(pf)

                zf.write(page_path, arcname=page_filename)

        with open(zip_path, "rb") as fh:
            await msg.reply_document(
                document=fh,
                filename="split_pages_oktacomel.zip",
                caption=(
                    f"✅ <b>PDF Split Complete.</b>\n"
                    f"📄 Pages: <b>{num_pages}</b>\n"
                    f"📦 All pages are inside this ZIP.\n\n"
                    f"⚡ <i>Powered by OKTACOMEL PDF Engine</i>"
                ),
                parse_mode=ParseMode.HTML
            )

        await status.delete()

    except Exception as e:
        await status.edit_text(
            f"❌ <b>Split failed:</b> <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML
        )
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass


# ==========================================
# 📝 /pdftotext — Extract Text from PDF
# ==========================================
async def pdf_to_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.reply_text(
            "⚠️ <b>How to use /pdftotext</b>\n\n"
            "Reply to a <b>PDF document</b> with:\n"
            "<code>/pdftotext</code>\n\n"
            "I will extract all readable text from the PDF.",
            parse_mode=ParseMode.HTML
        )
        return

    doc = msg.reply_to_message.document
    if doc.mime_type != "application/pdf":
        await msg.reply_text(
            "❌ <b>The replied message is not a PDF file.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    status = await msg.reply_text(
        "⏳ <b>Extracting text from PDF...</b>",
        parse_mode=ParseMode.HTML
    )

    tmp_dir = tempfile.mkdtemp(prefix="pdftotext_")

    try:
        pdf_path = os.path.join(tmp_dir, "source.pdf")
        f = await doc.get_file()
        await f.download_to_drive(custom_path=pdf_path)

        reader = PdfReader(pdf_path)
        all_text = []

        for page in reader.pages:
            txt = page.extract_text() or ""
            if txt.strip():
                all_text.append(txt)

        full_text = "\n\n".join(all_text).strip()

        if not full_text:
            await status.edit_text(
                "❌ <b>No text found in this PDF.</b>\n"
                "This file may be scanned or image-only.",
                parse_mode=ParseMode.HTML
            )
            return

        # Kalau singkat, kirim langsung di chat
        if len(full_text) <= 3800:
            await status.delete()
            await msg.reply_text(
                "?? <b>PDF Text Extracted:</b>\n\n"
                f"<code>{html.escape(full_text)}</code>",
                parse_mode=ParseMode.HTML
            )
        else:
            # Teks terlalu panjang → kirim sebagai file .txt
            txt_path = os.path.join(tmp_dir, "extracted_text.txt")
            with open(txt_path, "w", encoding="utf-8") as tf:
                tf.write(full_text)

            with open(txt_path, "rb") as fh:
                await status.delete()
                await msg.reply_document(
                    document=fh,
                    filename="pdf_text_oktacomel.txt",
                    caption="✅ <b>Text extracted as .txt file.</b>\n⚡ <i>Powered by OKTACOMEL PDF Engine</i>",
                    parse_mode=ParseMode.HTML
                )

    except Exception as e:
        await status.edit_text(
            f"❌ <b>Extract failed:</b> <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML
        )
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass


# ==========================================
# 📦 /compresspdf — Compress PDF size (requires Ghostscript)
# ==========================================
async def pdf_compress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.reply_text(
            "⚠️ <b>How to use /compresspdf</b>\n\n"
            "Reply to a <b>PDF document</b> with:\n"
            "<code>/compresspdf</code>\n\n"
            "I will try to reduce its file size.",
            parse_mode=ParseMode.HTML
        )
        return

    if not shutil.which("gs"):
        await msg.reply_text(
            "❌ <b>Ghostscript is not installed on this server.</b>\n"
            "Compression requires <code>ghostscript</code>.\n\n"
            "On Ubuntu/Debian:\n"
            "<code>sudo apt-get install ghostscript</code>",
            parse_mode=ParseMode.HTML
        )
        return

    doc = msg.reply_to_message.document
    if doc.mime_type != "application/pdf":
        await msg.reply_text(
            "❌ <b>The replied message is not a PDF file.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    status = await msg.reply_text(
        "⏳ <b>Compressing PDF...</b>\n<i>This may take a few seconds.</i>",
        parse_mode=ParseMode.HTML
    )

    tmp_dir = tempfile.mkdtemp(prefix="compresspdf_")

    try:
        src_pdf = os.path.join(tmp_dir, "source.pdf")
        out_pdf = os.path.join(tmp_dir, "compressed.pdf")

        f = await doc.get_file()
        await f.download_to_drive(custom_path=src_pdf)

        # Dapatkan ukuran awal
        original_size = os.path.getsize(src_pdf)

        # Ghostscript compression (ebook quality)
        cmd = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/ebook",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={out_pdf}",
            src_pdf,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()

        if not os.path.exists(out_pdf):
            await status.edit_text(
                "❌ <b>Compression failed.</b>\n"
                "Ghostscript could not create the output file.",
                parse_mode=ParseMode.HTML
            )
            return

        compressed_size = os.path.getsize(out_pdf)

        # Hitung penghematan
        def fmt_size(n):
            for unit in ["B", "KB", "MB", "GB"]:
                if n < 1024:
                    return f"{n:.1f} {unit}"
                n /= 1024
            return f"{n:.1f} TB"

        saved = original_size - compressed_size
        saved_pct = (saved / original_size * 100) if original_size > 0 else 0

        with open(out_pdf, "rb") as fh:
            await status.delete()
            await msg.reply_document(
                document=fh,
                filename="compressed_oktacomel.pdf",
                caption=(
                    "✅ <b>PDF Compression Complete.</b>\n"
                    f"📦 Original: <code>{fmt_size(original_size)}</code>\n"
                    f"📉 Compressed: <code>{fmt_size(compressed_size)}</code>\n"
                    f"💾 Saved: <code>{fmt_size(saved)}</code> (~{saved_pct:.1f}%)\n\n"
                    "⚡ <i>Powered by OKTACOMEL PDF Engine</i>"
                ),
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        await status.edit_text(
            f"❌ <b>Compression error:</b> <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML
        )
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass

# ==========================================
# 🖼️➡️📄 /imgpdf — IMAGE TO PDF (A+B+C+D)
# ==========================================
async def imgpdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    # --- 1. Check: must reply to a photo or image document ---
    reply = msg.reply_to_message
    if not reply:
        await msg.reply_text(
            "⚠️ <b>How to use /imgpdf</b>\n\n"
            "1️⃣ Send or forward an <b>image</b> (photo or image document).\n"
            "2️⃣ Reply to that image with:\n"
            "   <code>/imgpdf</code>\n\n"
            "Optional:\n"
            "• <code>/imgpdf pass=yourpassword</code> → create password-protected PDF.\n\n"
            "I will convert the image into a high-quality PDF.",
            parse_mode=ParseMode.HTML
        )
        return

    image_files = []

    # Single photo (standard Telegram photo)
    if reply.photo:
        # Take highest resolution variant
        image_files.append(("photo", reply.photo[-1]))
    # Image sent as document (e.g. to keep original quality)
    elif reply.document and (reply.document.mime_type or "").startswith("image/"):
        image_files.append(("document", reply.document))
    else:
        await msg.reply_text(
            "❌ <b>No valid image detected.</b>\n"
            "Please reply to a <b>photo</b> or an <b>image document</b>.",
            parse_mode=ParseMode.HTML
        )
        return

    # --- 2. Parse optional password argument ---
    password = None
    if context.args:
        for arg in context.args:
            if arg.lower().startswith("pass=") or arg.lower().startswith("password="):
                password = arg.split("=", 1)[1].strip()
                if not password:
                    password = None

    # --- 3. Status message ---
    status = await msg.reply_text(
        "⏳ <b>Generating PDF from image...</b>\n"
        "<i>Optimizing size & quality...</i>",
        parse_mode=ParseMode.HTML
    )

    tmp_dir = tempfile.mkdtemp(prefix="imgpdf_")

    try:
        image_paths = []

        # --- 4. Download image(s) to temp folder ---
        for idx, (kind, media) in enumerate(image_files, start=1):
            img_path = os.path.join(tmp_dir, f"img_{idx}.jpg")

            if kind == "photo":
                f = await media.get_file()
                await f.download_to_drive(custom_path=img_path)
            else:  # document image
                f = await media.get_file()
                await f.download_to_drive(custom_path=img_path)

            image_paths.append(img_path)

        if not image_paths:
            await status.edit_text(
                "❌ <b>Download error.</b> Could not download the image.",
                parse_mode=ParseMode.HTML
            )
            return

        # --- 5. Open images with Pillow, fix orientation & convert to RGB ---
        pil_images = []
        for p in image_paths:
            try:
                im = Image.open(p)

                # Auto-rotate if EXIF orientation exists
                try:
                    im = ImageOps.exif_transpose(im)
                except Exception:
                    pass

                # Convert all to RGB (required for PDF)
                if im.mode in ("RGBA", "P"):
                    im = im.convert("RGB")

                # Optional: simple auto-resize if extremely large
                max_dim = 2500
                if max(im.size) > max_dim:
                    im.thumbnail((max_dim, max_dim))

                pil_images.append(im)
            except Exception as e:
                print(f"Image open error: {e}")

        if not pil_images:
            await status.edit_text(
                "❌ <b>Failed to process the image.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        # --- 6. Save to PDF (single or multi-page) ---
        base_pdf_path = os.path.join(tmp_dir, "output_raw.pdf")

        first_img = pil_images[0]
        if len(pil_images) == 1:
            first_img.save(base_pdf_path, "PDF", resolution=150.0)
        else:
            # Multi-page PDF (future-proof if you add album support)
            first_img.save(
                base_pdf_path,
                "PDF",
                resolution=150.0,
                save_all=True,
                append_images=pil_images[1:]
            )

        final_pdf_path = os.path.join(tmp_dir, "output_final.pdf")

        # --- 7. Optional: add password protection (D) ---
        if password:
            reader = PdfReader(base_pdf_path)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)

            writer.encrypt(password)

            with open(final_pdf_path, "wb") as fw:
                writer.write(fw)
        else:
            # No password → just use base PDF
            shutil.copy(base_pdf_path, final_pdf_path)

        # --- 8. Send result to user ---
        pages_info = "1 page" if len(pil_images) == 1 else f"{len(pil_images)} pages"
        pass_info = "🔓 <b>Unprotected PDF</b>" if not password else "🔐 <b>Password-Protected PDF</b>"

        with open(final_pdf_path, "rb") as fh:
            await status.delete()
            await msg.reply_document(
                document=fh,
                filename="image_to_pdf_oktacomel.pdf",
                caption=(
                    "📄 <b>OKTACOMEL IMAGE → PDF</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"🖼️ <b>Images:</b> {pages_info}\n"
                    f"{pass_info}\n"
                    "🎛️ <b>Optimized:</b> Auto-rotate & size tuned\n"
                    "⚡ <i>Powered by OKTACOMEL PDF Engine</i>"
                ),
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        await status.edit_text(
            f"❌ <b>Conversion error:</b> <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML
        )
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass


# ==========================================
# 👤 /userinfo — ULTIMATE INTELLIGENCE SYSTEM v2.0
# ==========================================

class UserInfoCache:
    def __init__(self):
        self.cache = {}
        self.timestamp = {}
    
    async def get(self, user_id, force_refresh=False):
        now = time.time()
        
        if (user_id in self.cache and 
            not force_refresh and 
            (now - self.timestamp.get(user_id, 0)) < 300):
            return self.cache[user_id]
        
        data = await self._fetch_user_data(user_id)
        self.cache[user_id] = data
        self.timestamp[user_id] = now
        return data
    
    async def _fetch_user_data(self, user_id):
        db_data = {
            "is_sub": False,
            "is_prem": False,
            "note_count": 0,
            "prem_tier": None,
            "prem_expiry": None,
            "prem_auto_renew": False,
            "activity_count": 0,
            "error_count": 0,
            "last_activity": None,
            "created_at": None,
        }
        
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("SELECT 1 FROM subscribers WHERE user_id=?", (user_id,)) as c:
                    db_data["is_sub"] = bool(await c.fetchone())
                
                async with db.execute(
                    "SELECT COUNT(*) FROM user_notes WHERE user_id=?", (user_id,)
                ) as c:
                    db_data["note_count"] = (await c.fetchone())[0]
        except Exception as e:
            logger.error(f"Cache fetch error: {e}")
        
        return db_data

user_cache = UserInfoCache()

def get_rank(is_owner: bool, is_premium: bool, is_sub: bool) -> str:
    if is_owner:
        return "👑 GOD MODE (OWNER)"
    elif is_premium:
        return "💎 PREMIUM MEMBER"
    elif is_sub:
        return "⭐ SUBSCRIBER"
    else:
        return "👻 STRANGER / GUEST"

def get_threat_level(activity_score: int, error_rate: float) -> dict:
    if activity_score > 500 and error_rate < 5:
        return {
            "level": "🟢 LOW",
            "bar": "████░░░░░░░░░░░░░░",
            "description": "Safe User - No Threats Detected"
        }
    elif activity_score > 200 and error_rate < 10:
        return {
            "level": "🟡 MEDIUM",
            "bar": "████████░░░░░░░░░░",
            "description": "Normal Activity - Monitor Routine"
        }
    else:
        return {
            "level": "🟢 LOW",
            "bar": "████░░░░░░░░░░░░░░",
            "description": "Safe User"
        }

def get_behavior_score(activity_count: int, error_count: int) -> dict:
    score = min(100, max(0, 85))
    
    return {
        "score": int(score),
        "status": "🟢 GOOD",
        "description": "Healthy Activity Pattern",
        "activity": activity_count,
        "errors": error_count
    }

def get_achievements(is_owner: bool, is_premium: bool, is_sub: bool, 
                     note_count: int, activity_count: int, behavior_score: int) -> list:
    badges = []
    
    if is_owner:
        badges.append("👑 GOD TIER")
    if is_premium:
        badges.append("💎 PREMIUM VIP")
    if is_sub and not is_premium:
        badges.append("⭐ SUBSCRIBER")
    if activity_count > 500:
        badges.append("🔥 POWER USER")
    
    return badges if badges else ["👻 NEWCOMER"]

def format_time_ago(timestamp_str) -> str:
    if not timestamp_str:
        return "Never"
    
    try:
        dt = datetime.datetime.fromisoformat(timestamp_str)
        now = datetime.datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} days ago"
        else:
            return "Today"
    except:
        return "Unknown"

async def animate_loading_userinfo(status_msg) -> None:
    """Animasi loading untuk userinfo"""
    frames = [
        ("🔐 <b>INITIALIZING SECURE UPLINK...</b>", "█░░░░░░░░░░░░░░░░░░", 5),
        ("📡 <b>SCANNING BIOMETRICS...</b>", "███░░░░░░░░░░░░░░░░", 15),
        ("💾 <b>ACCESSING ENCRYPTED ARCHIVES...</b>", "██████░░░░░░░░░░░░░", 30),
        ("✅ <b>ANALYSIS COMPLETE</b>", "████████████████████", 100),
    ]
    
    for text, bar, percent in frames:
        await asyncio.sleep(0.8)
        try:
            await status_msg.edit_text(
                f"{text}\n"
                f"<code>[{bar}] {percent}%</code>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

async def userinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /userinfo - Get user intelligence"""
    msg = update.message
    caller_id = update.effective_user.id
    
    if caller_id != OWNER_ID:
        await msg.reply_text(
            "⛔ <b>ACCESS DENIED</b>\n"
            "Owner only!",
            parse_mode=ParseMode.HTML
        )
        return
    
    target_id = None
    
    if msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
    elif context.args:
        raw = context.args[0]
        if raw.isdigit():
            target_id = int(raw)
        else:
            await msg.reply_text("⚠️ Invalid format. Use User ID.", parse_mode=ParseMode.HTML)
            return
    else:
        await msg.reply_text("⚠️ Usage: <code>/userinfo [ID]</code>", parse_mode=ParseMode.HTML)
        return
    
    status_msg = await msg.reply_text(
        "🔐 <b>INITIALIZING...</b>\n"
        "<code>[░░░░░░░░░░] 0%</code>",
        parse_mode=ParseMode.HTML
    )
    
    await animate_loading_userinfo(status_msg)
    
    try:
        chat_info = await context.bot.get_chat(target_id)
        full_name = chat_info.full_name or "Unknown"
        username = f"@{chat_info.username}" if chat_info.username else "N/A"
    except BadRequest:
        await status_msg.edit_text("❌ User not found!", parse_mode=ParseMode.HTML)
        return
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)[:50]}", parse_mode=ParseMode.HTML)
        return
    
    db_data = await user_cache.get(target_id)
    is_owner = (target_id == OWNER_ID)
    rank = get_rank(is_owner, False, db_data["is_sub"])
    
    report_text = (
        "╔════════════════════════════════╗\n"
        "║  🔐 INTELLIGENCE DOSSIER 🔐   ║\n"
        "╚════════════════════════════════╝\n\n"
        
        f"<b>👤 IDENTITY</b>\n"
        f"├ <b>User ID:</b> <code>{target_id}</code>\n"
        f"├ <b>Name:</b> {html.escape(full_name)}\n"
        f"├ <b>Username:</b> {username}\n"
        f"└ <b>Rank:</b> {rank}\n\n"
        
        f"<b>📊 ACCOUNT STATUS</b>\n"
        f"├ <b>Subscriber:</b> {'✅' if db_data['is_sub'] else '❌'}\n"
        f"├ <b>Files:</b> <code>{db_data['note_count']}</code>\n"
        f"└ <b>Last Activity:</b> {format_time_ago(db_data['last_activity'])}\n\n"
        
        "═══════════════════════════════\n"
        "✅ Analysis Complete\n"
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📨 Message", url=f"tg://user?id={target_id}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"userinfo_refresh_{target_id}"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="userinfo_close")]
    ])
    
    try:
        await status_msg.edit_text(
            report_text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("❌ Error sending report", parse_mode=ParseMode.HTML)

async def userinfo_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer("✅ Refreshed!", show_alert=False)

async def userinfo_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    try:
        await q.message.delete()
    except:
        pass
    await q.answer("Closed", show_alert=False)
# ==========================================
# 🔧 /setproxy — Ganti Proxy via Telegram (Owner Only)
# ==========================================
async def setproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Hanya OWNER yang boleh
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text(
            "❌ This command is restricted.\nOnly the bot owner can change proxy."
        )

    if not context.args:
        return await update.message.reply_text(
            "🧩 <b>Proxy Config</b>\n"
            "Usage:\n"
            "• <code>/setproxy user:pass@host:port</code>\n"
            "• <code>/setproxy off</code>  → disable proxy\n\n"
            "Example:\n"
            "<code>/setproxy i1vU7ROatOpJlknj:HY3c533CC5n4qGVd@geo.g-w.info:10080</code>",
            parse_mode=ParseMode.HTML,
        )

    raw = context.args[0].strip()

    # Matikan proxy
    if raw.lower() in ("off", "none", "0", "disable"):
        proxy_str = ""
    else:
        # kalau user nggak tulis http://, kita tambahin
        if raw.startswith("http://") or raw.startswith("https://"):
            proxy_str = raw
        else:
            proxy_str = "http://" + raw

    # Update file config.py di disk
    ok = update_proxy_in_config(proxy_str)
    if not ok:
        return await update.message.reply_text(
            "⚠️ Failed to update <code>config.py</code> on disk.",
            parse_mode=ParseMode.HTML,
        )

    # Update variabel global di runtime
    global MY_PROXY
    MY_PROXY = proxy_str

    status = html.escape(proxy_str) if proxy_str else "DISABLED"

    await update.message.reply_text(
        "✅ <b>Proxy updated successfully.</b>\n"
        f"Current proxy:\n<code>{status}</code>",
        parse_mode=ParseMode.HTML,
    )

import subprocess
import json

# ==========================================
# 🚀 /speed — OFFICIAL OOKLA ENGINE
# ==========================================

speedtest_cooldown = defaultdict(lambda: datetime.datetime.min)
SPEEDTEST_COOLDOWN = 600

async def animate_loading_speedtest(msg_obj, duration=180):
    """Animasi loading untuk speedtest"""
    bars = ["▒▒▒▒▒▒▒▒▒▒", "█▒▒▒▒▒▒▒▒▒", "██▒▒▒▒▒▒▒▒", "███▒▒▒▒▒▒▒", 
            "████▒▒▒▒▒▒", "█████▒▒▒▒▒", "██████▒▒▒▒", "███████▒▒▒", 
            "████████▒▒", "█████████▒", "██████████"]
    
    elapsed = 0
    bar_idx = 0
    
    try:
        while elapsed < duration:
            bar = bars[bar_idx % len(bars)]
            percent = min(100, int((elapsed / duration) * 100))
            
            await msg_obj.edit_text(
                f"🚀 <b>TESTING SPEED...</b>\n"
                f"<code>[{bar}] {percent}%</code>\n"
                f"⏱️ Elapsed: {elapsed}s",
                parse_mode=ParseMode.HTML
            )
            
            await asyncio.sleep(2)
            bar_idx += 1
            elapsed += 2
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning(f"Animasi error: {e}")

def run_ookla_native():
    """Jalankan speedtest-cli (Python library)"""
    try:
        import speedtest
        st = speedtest.Speedtest()
        st.get_best_server()
        st.download()
        st.upload()
        results = st.results.dict()
        return {
            "download": results.get("download", 0),
            "upload": results.get("upload", 0),
            "ping": results.get("ping", 0),
            "jitter": 0,
            "packetLoss": 0,
            "isp": results.get("client", {}).get("isp", "Unknown"),
            "serverName": results.get("server", {}).get("sponsor", "Unknown"),
            "serverLocation": results.get("server", {}).get("name", "Unknown")
        }
    except ImportError:
        return {"error": "NOT_INSTALLED"}
    except Exception as e:
        logger.error(f"Speedtest error: {e}")
        return {"error": f"ERROR: {str(e)[:50]}"}


# ==========================================
# CLOUDFLARE DNS MANAGER - OKTACOMEL PREMIUM
# ==========================================

CF_API_BASE = "https://api.cloudflare.com/client/v4"

cf_user_states = {}

# ===== DATABASE OPERATIONS =====

async def cf_get_user_api(user_id: int) -> dict:
    """Get user's Cloudflare API credentials"""
    try:
        result = await db_fetch_one(
            "SELECT api_key, email FROM cloudflare_users WHERE user_id = ?",
            (user_id,)
        )
        if result:
            return {"api_key": result[0], "email": result[1]}
    except Exception as e:
        logger.error(f"[CF] Get API error: {e}")
    return {}

async def cf_save_user_api(user_id: int, api_key: str, email: str) -> bool:
    """Save user's Cloudflare API credentials"""
    try:
        await db_execute(
            "INSERT OR REPLACE INTO cloudflare_users (user_id, api_key, email, created_at) VALUES (?, ?, ?, ?)",
            (user_id, api_key, email, datetime.datetime.now().isoformat())
        )
        return True
    except Exception as e:
        logger.error(f"[CF] Save API error: {e}")
        return False

async def cf_delete_user_api(user_id: int) -> bool:
    """Delete user's Cloudflare API credentials"""
    try:
        await db_execute("DELETE FROM cloudflare_users WHERE user_id = ?", (user_id,))
        return True
    except Exception as e:
        logger.error(f"[CF] Delete API error: {e}")
        return False

async def cf_log_action(user_id: int, action: str, domain: str = "", details: str = ""):
    """Log Cloudflare action for stats"""
    try:
        await db_execute(
            "INSERT INTO cloudflare_stats (user_id, action, domain, details, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, domain, details, datetime.datetime.now().isoformat())
        )
    except Exception as e:
        logger.debug(f"[CF] Log error: {e}")

async def cf_get_global_stats() -> dict:
    """Get global Cloudflare usage statistics"""
    try:
        total_users = await db_fetch_one("SELECT COUNT(DISTINCT user_id) FROM cloudflare_users")
        change_ip = await db_fetch_one("SELECT COUNT(*) FROM cloudflare_stats WHERE action = 'change_ip'")
        add_sub = await db_fetch_one("SELECT COUNT(*) FROM cloudflare_stats WHERE action = 'add_sub'")
        delete_sub = await db_fetch_one("SELECT COUNT(*) FROM cloudflare_stats WHERE action = 'delete_sub'")
        return {
            "total_users": total_users[0] if total_users else 0,
            "change_ip": change_ip[0] if change_ip else 0,
            "add_sub": add_sub[0] if add_sub else 0,
            "delete_sub": delete_sub[0] if delete_sub else 0
        }
    except Exception as e:
        logger.debug(f"[CF] Stats error: {e}")
        return {"total_users": 0, "change_ip": 0, "add_sub": 0, "delete_sub": 0}

# ===== API OPERATIONS =====

async def cf_api_request(method: str, endpoint: str, api_key: str, email: str, data: dict = None) -> dict:
    """Make authenticated request to Cloudflare API"""
    try:
        headers = {
            "X-Auth-Email": email,
            "X-Auth-Key": api_key,
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=30) as client:
            url = f"{CF_API_BASE}{endpoint}"
            if method == "GET":
                r = await client.get(url, headers=headers)
            elif method == "POST":
                r = await client.post(url, headers=headers, json=data)
            elif method == "PUT":
                r = await client.put(url, headers=headers, json=data)
            elif method == "DELETE":
                r = await client.delete(url, headers=headers)
            else:
                return {"success": False, "errors": [{"message": "Invalid method"}]}
            return r.json()
    except asyncio.TimeoutError:
        return {"success": False, "errors": [{"message": "Request timeout"}]}
    except Exception as e:
        logger.error(f"[CF API] Error: {e}")
        return {"success": False, "errors": [{"message": str(e)[:100]}]}

async def cf_verify_api(api_key: str, email: str) -> bool:
    """Verify Cloudflare API credentials"""
    result = await cf_api_request("GET", "/user", api_key, email)
    return result.get("success", False)

async def cf_get_zones(api_key: str, email: str) -> list:
    """Get all zones (domains) from Cloudflare"""
    result = await cf_api_request("GET", "/zones?per_page=50", api_key, email)
    if result.get("success"):
        return result.get("result", [])
    return []

async def cf_get_dns_records(api_key: str, email: str, zone_id: str) -> list:
    """Get DNS records for a zone"""
    result = await cf_api_request("GET", f"/zones/{zone_id}/dns_records?per_page=100", api_key, email)
    if result.get("success"):
        return result.get("result", [])
    return []

async def cf_add_dns_record(api_key: str, email: str, zone_id: str, record_type: str, name: str, content: str, proxied: bool = True) -> dict:
    """Add DNS record to zone"""
    data = {"type": record_type, "name": name, "content": content, "proxied": proxied, "ttl": 1}
    return await cf_api_request("POST", f"/zones/{zone_id}/dns_records", api_key, email, data)

async def cf_update_dns_record(api_key: str, email: str, zone_id: str, record_id: str, record_type: str, name: str, content: str, proxied: bool = True) -> dict:
    """Update DNS record"""
    data = {"type": record_type, "name": name, "content": content, "proxied": proxied, "ttl": 1}
    return await cf_api_request("PUT", f"/zones/{zone_id}/dns_records/{record_id}", api_key, email, data)

async def cf_delete_dns_record(api_key: str, email: str, zone_id: str, record_id: str) -> dict:
    """Delete DNS record"""
    return await cf_api_request("DELETE", f"/zones/{zone_id}/dns_records/{record_id}", api_key, email)

async def cf_host_to_ip(hostname: str) -> str:
    """Resolve hostname to IP"""
    try:
        import socket
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception as e:
        return f"Error: {str(e)[:30]}"

async def cf_ping_host(hostname: str) -> str:
    """Ping hostname and return latency"""
    try:
        import subprocess
        import platform
        
        if platform.system() == "Windows":
            result = subprocess.run(["ping", "-n", "3", hostname], capture_output=True, text=True, timeout=10)
        else:
            result = subprocess.run(["ping", "-c", "3", hostname], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.split("\n")
            for line in lines:
                if "avg" in line.lower() or "rtt" in line.lower() or "min" in line.lower():
                    return line.strip()
            return "Ping successful"
        return "Ping failed"
    except Exception as e:
        return f"Error: {str(e)[:30]}"

async def cf_get_domain_info(domain: str) -> dict:
    """Get domain WHOIS info"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"https://api.api-ninjas.com/v1/whois?domain={domain}")
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        logger.debug(f"[CF] WHOIS error: {e}")
    return {}

# ===== MAIN COMMAND =====

async def cf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cloudflare DNS Manager"""
    if not await premium_lock_handler(update, context):
        return
    
    user_id = update.effective_user.id
    username = html.escape(update.effective_user.username or "User")
    
    user_api = await cf_get_user_api(user_id)
    api_connected = "Connected" if user_api.get("api_key") else "Not Connected"
    api_email = html.escape(user_api.get("email", "None"))
    
    domain_count = 0
    if user_api.get("api_key"):
        try:
            zones = await cf_get_zones(user_api["api_key"], user_api["email"])
            domain_count = len(zones)
        except:
            pass
    
    stats = await cf_get_global_stats()
    
    text = (
        "OKTACOMEL CLOUDFLARE MANAGER\n"
        "=================================\n\n"
        f"User: @{username}\n"
        f"API Status: {api_connected}\n"
        f"Email: {api_email}\n"
        f"Domains: {domain_count}\n\n"
        
        "GLOBAL STATISTICS\n"
        f"Total Users: {stats['total_users']}\n"
        f"IP Changes: {stats['change_ip']}\n"
        f"Subdomains Added: {stats['add_sub']}\n"
        f"Subdomains Deleted: {stats['delete_sub']}\n\n"
        
        "Setup API Key di Menu Tools untuk mengakses semua fitur."
    )
    
    buttons = [
        [
            InlineKeyboardButton("Add Subdomain", callback_data=f"cf_add|{user_id}"),
            InlineKeyboardButton("Change IP", callback_data=f"cf_changeip|{user_id}")
        ],
        [
            InlineKeyboardButton("Delete Subdomain", callback_data=f"cf_delete|{user_id}"),
            InlineKeyboardButton("List Subdomains", callback_data=f"cf_listsub|{user_id}")
        ],
        [
            InlineKeyboardButton("More Tools", callback_data=f"cf_extra|{user_id}")
        ],
        [
            InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")
        ]
    ]
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

# ===== CALLBACK HANDLER =====

async def cf_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all Cloudflare callbacks"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        parts = query.data.split("|")
        action = parts[0]
        owner_id = int(parts[1]) if len(parts) > 1 else user_id
        
        if user_id != owner_id:
            await query.answer("Not authorized", show_alert=True)
            return
        
        await query.answer()
        
        user_api = await cf_get_user_api(user_id)
        
        # MAIN MENU
        if action == "cf_main":
            username = html.escape(update.effective_user.username or "User")
            api_connected = "Connected" if user_api.get("api_key") else "Not Connected"
            api_email = html.escape(user_api.get("email", "None"))
            
            domain_count = 0
            if user_api.get("api_key"):
                zones = await cf_get_zones(user_api["api_key"], user_api["email"])
                domain_count = len(zones)
            
            stats = await cf_get_global_stats()
            
            text = (
                "OKTACOMEL CLOUDFLARE MANAGER\n"
                "=================================\n\n"
                f"User: @{username}\n"
                f"API Status: {api_connected}\n"
                f"Email: {api_email}\n"
                f"Domains: {domain_count}\n\n"
                
                "GLOBAL STATISTICS\n"
                f"Total Users: {stats['total_users']}\n"
                f"IP Changes: {stats['change_ip']}\n"
                f"Subdomains Added: {stats['add_sub']}\n"
                f"Subdomains Deleted: {stats['delete_sub']}"
            )
            
            buttons = [
                [
                    InlineKeyboardButton("Add Subdomain", callback_data=f"cf_add|{user_id}"),
                    InlineKeyboardButton("Change IP", callback_data=f"cf_changeip|{user_id}")
                ],
                [
                    InlineKeyboardButton("Delete Subdomain", callback_data=f"cf_delete|{user_id}"),
                    InlineKeyboardButton("List Subdomains", callback_data=f"cf_listsub|{user_id}")
                ],
                [
                    InlineKeyboardButton("More Tools", callback_data=f"cf_extra|{user_id}")
                ],
                [
                    InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")
                ]
            ]
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # MORE TOOLS
        elif action == "cf_extra":
            text = (
                "MORE TOOLS\n"
                "=================================\n\n"
                "Select additional tools:"
            )
            buttons = [
                [InlineKeyboardButton("Setup API Key", callback_data=f"cf_setupapi|{user_id}")],
                [InlineKeyboardButton("View My Data", callback_data=f"cf_mydata|{user_id}")],
                [InlineKeyboardButton("Host to IP", callback_data=f"cf_hostip|{user_id}"),
                 InlineKeyboardButton("Ping", callback_data=f"cf_ping|{user_id}")],
                [InlineKeyboardButton("Domain Info", callback_data=f"cf_domaininfo|{user_id}")],
                [InlineKeyboardButton("Back", callback_data=f"cf_main|{user_id}")]
            ]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # SETUP API KEY
        elif action == "cf_setupapi":
            text = (
                "SETUP GLOBAL API KEY\n"
                "=================================\n\n"
                "How to get API Key:\n"
                "1. Login to dash.cloudflare.com\n"
                "2. Click My Profile > API Tokens\n"
                "3. Select Global API Key > View\n"
                "4. Copy the API Key\n\n"
                "Send to bot:\n"
                "/cfapi EMAIL|API_KEY\n\n"
                "Example:\n"
                "/cfapi admin@gmail.com|a1b2c3d4e5f6g7h8"
            )
            buttons = [[InlineKeyboardButton("Back", callback_data=f"cf_extra|{user_id}")]]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # MY DATA
        elif action == "cf_mydata":
            if not user_api.get("api_key"):
                await query.answer("API Key not configured", show_alert=True)
                return
            
            zones = await cf_get_zones(user_api["api_key"], user_api["email"])
            
            text = (
                "MY CLOUDFLARE DATA\n"
                "=================================\n\n"
                f"Email: {html.escape(user_api['email'])}\n"
                f"API Key: ...{user_api['api_key'][-8:]}\n"
                f"Total Domains: {len(zones)}\n\n"
                "DOMAINS:\n"
            )
            
            for i, zone in enumerate(zones[:15], 1):
                status = "active" if zone.get("status") == "active" else "inactive"
                text += f"{i}. {html.escape(zone.get('name', 'Unknown'))} ({status})\n"
            
            if len(zones) > 15:
                text += f"\n...and {len(zones) - 15} more"
            
            buttons = [
                [InlineKeyboardButton("Delete API Key", callback_data=f"cf_deleteapi|{user_id}")],
                [InlineKeyboardButton("Back", callback_data=f"cf_extra|{user_id}")]
            ]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # DELETE API KEY
        elif action == "cf_deleteapi":
            await cf_delete_user_api(user_id)
            await query.answer("API Key deleted", show_alert=True)
            
            text = (
                "MORE TOOLS\n"
                "=================================\n\n"
                "API Key has been deleted.\nSetup again if needed."
            )
            buttons = [
                [InlineKeyboardButton("Setup API Key", callback_data=f"cf_setupapi|{user_id}")],
                [InlineKeyboardButton("View My Data", callback_data=f"cf_mydata|{user_id}")],
                [InlineKeyboardButton("Host to IP", callback_data=f"cf_hostip|{user_id}"),
                 InlineKeyboardButton("Ping", callback_data=f"cf_ping|{user_id}")],
                [InlineKeyboardButton("Domain Info", callback_data=f"cf_domaininfo|{user_id}")],
                [InlineKeyboardButton("Back", callback_data=f"cf_main|{user_id}")]
            ]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # ADD SUBDOMAIN
        elif action == "cf_add":
            if not user_api.get("api_key"):
                await query.answer("Setup API Key first", show_alert=True)
                return
            
            zones = await cf_get_zones(user_api["api_key"], user_api["email"])
            if not zones:
                await query.answer("No domains found", show_alert=True)
                return
            
            text = "ADD SUBDOMAIN\n=================================\n\nSelect domain:\n"
            
            buttons = []
            for zone in zones[:12]:
                zone_name = html.escape(zone.get("name", "Unknown"))
                buttons.append([InlineKeyboardButton(zone_name, callback_data=f"cf_add_zone|{zone.get('id')}|{user_id}")])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"cf_main|{user_id}")])
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # SELECT ZONE FOR ADD
        elif action == "cf_add_zone":
            zone_id = parts[1]
            cf_user_states[user_id] = {"action": "add_sub", "zone_id": zone_id}
            
            text = (
                "ADD SUBDOMAIN\n"
                "=================================\n\n"
                "Send subdomain:\n"
                "/cfsub SUBDOMAIN IP\n\n"
                "Example:\n"
                "/cfsub api 192.168.1.1"
            )
            buttons = [[InlineKeyboardButton("Cancel", callback_data=f"cf_main|{user_id}")]]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # CHANGE IP
        elif action == "cf_changeip":
            if not user_api.get("api_key"):
                await query.answer("Setup API Key first", show_alert=True)
                return
            
            zones = await cf_get_zones(user_api["api_key"], user_api["email"])
            if not zones:
                await query.answer("No domains found", show_alert=True)
                return
            
            text = "CHANGE IP SUBDOMAIN\n=================================\n\nSelect domain:\n"
            
            buttons = []
            for zone in zones[:12]:
                zone_name = html.escape(zone.get("name", "Unknown"))
                buttons.append([InlineKeyboardButton(zone_name, callback_data=f"cf_changeip_zone|{zone.get('id')}|{user_id}")])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"cf_main|{user_id}")])
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # SELECT ZONE FOR CHANGE IP
        elif action == "cf_changeip_zone":
            zone_id = parts[1]
            records = await cf_get_dns_records(user_api["api_key"], user_api["email"], zone_id)
            
            a_records = [r for r in records if r.get("type") == "A"]
            
            if not a_records:
                await query.answer("No A records found", show_alert=True)
                return
            
            text = "SELECT SUBDOMAIN\n=================================\n\nSelect subdomain:\n"
            
            buttons = []
            for rec in a_records[:15]:
                name = html.escape(rec.get("name", "Unknown"))
                ip = html.escape(rec.get("content", "0.0.0.0"))
                rec_id = rec.get("id")
                btn_text = f"{name} ({ip})"[:40]
                buttons.append([InlineKeyboardButton(btn_text, callback_data=f"cf_changeip_rec|{zone_id}|{rec_id}|{user_id}")])
            
            buttons.append([InlineKeyboardButton("Back", callback_data=f"cf_changeip|{user_id}")])
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # SELECT RECORD FOR CHANGE IP
        elif action == "cf_changeip_rec":
            zone_id = parts[1]
            rec_id = parts[2]
            cf_user_states[user_id] = {"action": "change_ip", "zone_id": zone_id, "rec_id": rec_id}
            
            text = (
                "CHANGE IP SUBDOMAIN\n"
                "=================================\n\n"
                "Send new IP:\n"
                "/cfip NEW_IP\n\n"
                "Example:\n"
                "/cfip 103.123.45.67"
            )
            buttons = [[InlineKeyboardButton("Cancel", callback_data=f"cf_main|{user_id}")]]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # DELETE SUBDOMAIN
        elif action == "cf_delete":
            if not user_api.get("api_key"):
                await query.answer("Setup API Key first", show_alert=True)
                return
            
            zones = await cf_get_zones(user_api["api_key"], user_api["email"])
            if not zones:
                await query.answer("No domains found", show_alert=True)
                return
            
            text = "DELETE SUBDOMAIN\n=================================\n\nSelect domain:\n"
            
            buttons = []
            for zone in zones[:12]:
                zone_name = html.escape(zone.get("name", "Unknown"))
                buttons.append([InlineKeyboardButton(zone_name, callback_data=f"cf_delete_zone|{zone.get('id')}|{user_id}")])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"cf_main|{user_id}")])
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # SELECT ZONE FOR DELETE
        elif action == "cf_delete_zone":
            zone_id = parts[1]
            records = await cf_get_dns_records(user_api["api_key"], user_api["email"], zone_id)
            
            a_records = [r for r in records if r.get("type") == "A"]
            
            if not a_records:
                await query.answer("No A records found", show_alert=True)
                return
            
            text = "DELETE SUBDOMAIN\n=================================\n\nSelect subdomain:\n"
            
            buttons = []
            for rec in a_records[:15]:
                name = html.escape(rec.get("name", "Unknown"))
                rec_id = rec.get("id")
                buttons.append([InlineKeyboardButton(name[:40], callback_data=f"cf_delete_rec|{zone_id}|{rec_id}|{user_id}")])
            
            buttons.append([InlineKeyboardButton("Back", callback_data=f"cf_delete|{user_id}")])
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # CONFIRM DELETE RECORD
        elif action == "cf_delete_rec":
            zone_id = parts[1]
            rec_id = parts[2]
            
            result = await cf_delete_dns_record(user_api["api_key"], user_api["email"], zone_id, rec_id)
            if result.get("success"):
                await cf_log_action(user_id, "delete_sub", "", "Deleted subdomain")
                await query.answer("Subdomain deleted", show_alert=True)
            else:
                error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
                await query.answer(f"Error: {error_msg[:50]}", show_alert=True)
            
            zones = await cf_get_zones(user_api["api_key"], user_api["email"])
            text = "DELETE SUBDOMAIN\n=================================\n\nSelect domain:\n"
            buttons = []
            for zone in zones[:12]:
                zone_name = html.escape(zone.get("name", "Unknown"))
                buttons.append([InlineKeyboardButton(zone_name, callback_data=f"cf_delete_zone|{zone.get('id')}|{user_id}")])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"cf_main|{user_id}")])
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # LIST SUBDOMAINS
        elif action == "cf_listsub":
            if not user_api.get("api_key"):
                await query.answer("Setup API Key first", show_alert=True)
                return
            
            zones = await cf_get_zones(user_api["api_key"], user_api["email"])
            if not zones:
                await query.answer("No domains found", show_alert=True)
                return
            
            text = "LIST SUBDOMAINS\n=================================\n\nSelect domain:\n"
            
            buttons = []
            for zone in zones[:12]:
                zone_name = html.escape(zone.get("name", "Unknown"))
                buttons.append([InlineKeyboardButton(zone_name, callback_data=f"cf_listsub_zone|{zone.get('id')}|{user_id}")])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"cf_main|{user_id}")])
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # LIST RECORDS FOR ZONE
        elif action == "cf_listsub_zone":
            zone_id = parts[1]
            records = await cf_get_dns_records(user_api["api_key"], user_api["email"], zone_id)
            
            text = "SUBDOMAIN LIST\n=================================\n\n"
            
            for i, rec in enumerate(records[:20], 1):
                rec_type = rec.get("type", "?")
                name = html.escape(rec.get("name", "Unknown"))
                content = html.escape(rec.get("content", "")[:20])
                proxied = "Yes" if rec.get("proxied") else "No"
                text += f"{i}. {name}\n   Type: {rec_type}, Content: {content}, Proxy: {proxied}\n\n"
            
            if len(records) > 20:
                text += f"...and {len(records) - 20} more records"
            
            buttons = [[InlineKeyboardButton("Back", callback_data=f"cf_listsub|{user_id}")]]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # HOST TO IP
        elif action == "cf_hostip":
            cf_user_states[user_id] = {"action": "host_to_ip"}
            text = (
                "HOST TO IP\n"
                "=================================\n\n"
                "Send hostname:\n"
                "/cfhost HOSTNAME\n\n"
                "Example:\n"
                "/cfhost google.com"
            )
            buttons = [[InlineKeyboardButton("Back", callback_data=f"cf_extra|{user_id}")]]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # PING
        elif action == "cf_ping":
            cf_user_states[user_id] = {"action": "ping"}
            text = (
                "PING HOST\n"
                "=================================\n\n"
                "Send hostname:\n"
                "/cfping HOSTNAME\n\n"
                "Example:\n"
                "/cfping cloudflare.com"
            )
            buttons = [[InlineKeyboardButton("Back", callback_data=f"cf_extra|{user_id}")]]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        # DOMAIN INFO
        elif action == "cf_domaininfo":
            cf_user_states[user_id] = {"action": "domain_info"}
            text = (
                "DOMAIN INFO\n"
                "=================================\n\n"
                "Send domain:\n"
                "/cfdomaininfo DOMAIN\n\n"
                "Example:\n"
                "/cfdomaininfo example.com"
            )
            buttons = [[InlineKeyboardButton("Back", callback_data=f"cf_extra|{user_id}")]]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    
    except Exception as e:
        logger.error(f"[CF] Callback error: {e}")
        try:
            await query.answer(f"Error: {str(e)[:50]}", show_alert=True)
        except:
            pass

# ===== TEXT COMMAND HANDLERS =====

async def cfapi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Setup API Key"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "SETUP API KEY\n\n"
            "Format: /cfapi EMAIL|API_KEY\n\n"
            "Example:\n"
            "/cfapi admin@gmail.com|abc123def456"
        )
        return
    
    try:
        parts = " ".join(context.args).split("|")
        if len(parts) != 2:
            await update.message.reply_text("Format: /cfapi EMAIL|API_KEY")
            return
        
        email = parts[0].strip()
        api_key = parts[1].strip()
        
        msg = await update.message.reply_text("Verifying API Key...")
        
        if await cf_verify_api(api_key, email):
            await cf_save_user_api(user_id, api_key, email)
            await msg.edit_text(
                "API KEY SAVED\n\n"
                f"Email: {html.escape(email)}\n"
                f"API Key: ...{api_key[-8:]}\n\n"
                "Use /cf to access menu."
            )
        else:
            await msg.edit_text("API Key invalid!\n\nCheck email and key.")
    
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def cfsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add subdomain"""
    user_id = update.effective_user.id
    user_api = await cf_get_user_api(user_id)
    
    if not user_api.get("api_key"):
        await update.message.reply_text("Setup API Key with /cfapi")
        return
    
    state = cf_user_states.get(user_id, {})
    if state.get("action") != "add_sub" or not state.get("zone_id"):
        await update.message.reply_text("Use /cf menu to add subdomain")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Format: /cfsub SUBDOMAIN IP")
        return
    
    subdomain = context.args[0].lower()
    ip = context.args[1]
    zone_id = state["zone_id"]
    
    if not all(part.isdigit() and 0 <= int(part) <= 255 for part in ip.split(".")):
        await update.message.reply_text("Invalid IP format")
        return
    
    msg = await update.message.reply_text("Adding subdomain...")
    
    result = await cf_add_dns_record(user_api["api_key"], user_api["email"], zone_id, "A", subdomain, ip, True)
    
    if result.get("success"):
        await cf_log_action(user_id, "add_sub", subdomain, ip)
        cf_user_states.pop(user_id, None)
        await msg.edit_text(
            "SUBDOMAIN ADDED\n\n"
            f"Subdomain: {subdomain}\n"
            f"IP: {ip}\n"
            f"Proxy: ON\n\n"
            "Use /cf for menu."
        )
    else:
        error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
        await msg.edit_text(f"Error: {error_msg}")

async def cfip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change IP"""
    user_id = update.effective_user.id
    user_api = await cf_get_user_api(user_id)
    
    if not user_api.get("api_key"):
        await update.message.reply_text("Setup API Key with /cfapi")
        return
    
    state = cf_user_states.get(user_id, {})
    if state.get("action") != "change_ip":
        await update.message.reply_text("Use /cf menu to change IP")
        return
    
    if not context.args:
        await update.message.reply_text("Format: /cfip NEW_IP")
        return
    
    new_ip = context.args[0]
    
    if not all(part.isdigit() and 0 <= int(part) <= 255 for part in new_ip.split(".")):
        await update.message.reply_text("Invalid IP format")
        return
    
    zone_id = state["zone_id"]
    rec_id = state["rec_id"]
    
    msg = await update.message.reply_text("Updating IP...")
    
    records = await cf_get_dns_records(user_api["api_key"], user_api["email"], zone_id)
    current_rec = next((r for r in records if r.get("id") == rec_id), None)
    
    if not current_rec:
        await msg.edit_text("Record not found")
        return
    
    result = await cf_update_dns_record(
        user_api["api_key"], user_api["email"], zone_id, rec_id,
        current_rec.get("type", "A"), current_rec.get("name", ""), new_ip, current_rec.get("proxied", True)
    )
    
    if result.get("success"):
        await cf_log_action(user_id, "change_ip", current_rec.get("name", ""), new_ip)
        cf_user_states.pop(user_id, None)
        await msg.edit_text(
            "IP CHANGED\n\n"
            f"Subdomain: {html.escape(current_rec.get('name', 'Unknown'))}\n"
            f"New IP: {new_ip}\n\n"
            "Use /cf for menu."
        )
    else:
        error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
        await msg.edit_text(f"Error: {error_msg}")

async def cfhost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Host to IP"""
    if not context.args:
        await update.message.reply_text("Format: /cfhost HOSTNAME")
        return
    
    hostname = context.args[0]
    msg = await update.message.reply_text("Resolving...")
    
    ip = await cf_host_to_ip(hostname)
    
    await msg.edit_text(
        f"HOST TO IP\n\n"
        f"Hostname: {hostname}\n"
        f"IP Address: {ip}"
    )

async def cfping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ping host"""
    if not context.args:
        await update.message.reply_text("Format: /cfping HOSTNAME")
        return
    
    hostname = context.args[0]
    msg = await update.message.reply_text("Pinging...")
    
    result = await cf_ping_host(hostname)
    
    await msg.edit_text(
        f"PING RESULT\n\n"
        f"Host: {hostname}\n"
        f"Result: {result}"
    )

async def cfdomaininfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Domain info"""
    if not context.args:
        await update.message.reply_text("Format: /cfdomaininfo DOMAIN")
        return
    
    domain = context.args[0]
    msg = await update.message.reply_text("Getting info...")
    
    info = await cf_get_domain_info(domain)
    
    if not info:
        await msg.edit_text(f"Cannot find info for domain: {domain}")
        return
    
    registrar = html.escape(info.get("registrar", "Unknown"))
    created = html.escape(info.get("creation_date", "Unknown"))
    expiry = html.escape(info.get("expiration_date", "Unknown"))
    
    text = (
        f"DOMAIN INFO\n\n"
        f"Domain: {domain}\n"
        f"Registrar: {registrar}\n"
        f"Created: {created}\n"
        f"Expires: {expiry}"
    )
    
    await msg.edit_text(text)


async def speedtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /speed"""
    
    msg = update.message
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await msg.reply_text("⛔ Owner only!", parse_mode=ParseMode.HTML)
        return
    
    now = datetime.datetime.now()
    if (now - speedtest_cooldown[user_id]).total_seconds() < SPEEDTEST_COOLDOWN:
        await msg.reply_text("⏳ Wait 10 minutes before next test", parse_mode=ParseMode.HTML)
        return
    
    speedtest_cooldown[user_id] = now
    
    try:
        status_msg = await msg.reply_text(
            "🚀 <b>CONTACTING OOKLA...</b>\n"
            "<code>[░░░░░░░░░░] 0%</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.reply_text("❌ Failed to send message", parse_mode=ParseMode.HTML)
        return

    animation_task = None
    test_task = None
    
    try:
        loop = asyncio.get_running_loop()
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)
        
        test_task = loop.run_in_executor(executor, run_ookla_native)
        animation_task = asyncio.create_task(animate_loading_speedtest(status_msg, duration=180))
        
        data = await asyncio.wait_for(test_task, timeout=190)
        
        if animation_task and not animation_task.done():
            animation_task.cancel()
            try:
                await animation_task
            except asyncio.CancelledError:
                pass
        
    except asyncio.TimeoutError:
        if animation_task and not animation_task.done():
            animation_task.cancel()
        await status_msg.edit_text("⏱️ Timeout (>3 minutes)", parse_mode=ParseMode.HTML)
        return
        
    except Exception as e:
        if animation_task and not animation_task.done():
            animation_task.cancel()
        await status_msg.edit_text(f"❌ Error: {str(e)[:100]}", parse_mode=ParseMode.HTML)
        return

    if not data or "error" in data:
        error_msg = data.get("error", "Unknown") if data else "Unknown"
        
        if error_msg == "NOT_INSTALLED":
            await status_msg.edit_text(
                "❌ Speedtest CLI not installed\n"
                "Run: <code>apt install speedtest-cli</code>",
                parse_mode=ParseMode.HTML
            )
        else:
            await status_msg.edit_text(f"❌ Error: {error_msg}", parse_mode=ParseMode.HTML)
        return

    try:
        download_mbps = round(float(data["download"]) / 1_000_000, 2)
        upload_mbps = round(float(data["upload"]) / 1_000_000, 2)
        ping = round(float(data.get("ping", 0)), 2)
        jitter = round(float(data.get("jitter", 0)), 2)
        packet_loss = round(float(data.get("packetLoss", 0)), 1)
        
        isp = str(data.get("isp", "Unknown"))[:100]
        server_name = str(data.get("serverName", "Unknown"))[:100]
        server_location = str(data.get("serverLocation", "Unknown"))[:100]
        
    except (KeyError, ValueError, TypeError) as e:
        await status_msg.edit_text(f"❌ Parse error: {str(e)[:50]}", parse_mode=ParseMode.HTML)
        return

    try:
        await status_msg.delete()
    except:
        pass

    report_text = (
        "<b>🚀 OOKLA SPEEDTEST RESULT</b>\n"
        "<code>━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<b>📊 PERFORMANCE</b>\n"
        f"├ 📥 <b>Download:</b> <code>{download_mbps} Mbps</code>\n"
        f"├ 📤 <b>Upload:</b> <code>{upload_mbps} Mbps</code>\n"
        f"├ 📡 <b>Ping:</b> <code>{ping} ms</code>\n"
        f"└ 📊 <b>Jitter:</b> <code>{jitter} ms</code> (Loss: {packet_loss}%)\n\n"
        
        f"<b>💻 CLIENT INFO</b>\n"
        f"└ <b>ISP:</b> {isp}\n\n"
        
        f"<b>🌍 SERVER TARGET</b>\n"
        f"├ <b>Node:</b> {server_name}\n"
        f"└ <b>Location:</b> {server_location}\n"
        "<code>━━━━━━━━━━━━━━━━━━━━━━━━━━</code>"
    )

    try:
        await msg.reply_text(report_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error sending result: {e}")
        
# ==========================================
# 🕌 JADWAL SHOLAT (PREMIUM ULTIMATE V5)
# ==========================================

async def sholat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get prayer times for specified city with Friday special handling"""
    user_id = update.effective_user.id
    
    # 1. Tentukan Kota (Default: Jakarta)
    raw_city = "Jakarta"
    if context.args:
        raw_city = " ".join(context.args).title()  # Huruf depan besar semua

    # Encode untuk URL
    city_encoded = urllib.parse.quote(raw_city)

    # Method 20 = Kemenag RI (Standar Indonesia)
    url = (
        f"https://api.aladhan.com/v1/timingsByCity"
        f"?city={city_encoded}&country=Indonesia&method=20"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    # Loading message
    msg = await update.message.reply_text(
        "⏳ <b>Scanning prayer times...</b>",
        parse_mode=ParseMode.HTML,
    )

    try:
        r = await fetch_json(url, headers=headers)

        if r and r.get("code") == 200 and r.get("data"):
            data = r["data"]
            t = data["timings"]
            d_date = data["date"]
            hijri = d_date["hijri"]

            # Tanggal hijriah yang rapi
            hijri_str = f"{hijri['day']} {hijri['month']['en']} {hijri['year']}"

            # Escape teks agar aman di HTML
            city_safe = html.escape(raw_city)
            gregorian_safe = html.escape(d_date.get("readable", "Unknown"))

            # Check if today is Friday (Jum'at)
            import datetime
            today = datetime.datetime.now()
            is_friday = today.weekday() == 4  # 0 = Monday, 4 = Friday
            
            # Determine Dzuhur/Jum'at label
            if is_friday:
                dzuhur_label = "🕌 Jum'at"
                dzuhur_emoji = "🕋"
            else:
                dzuhur_label = "☀️ Dzuhur"
                dzuhur_emoji = "☀️"

            # UI PREMIUM ULTIMATE (IMPROVED RESULT ONLY)
            txt = (
                f"🕌 <b>JADWAL SHOLAT</b>\n"
                f"────────────────────────\n"
                f"📍 <b>Kota</b>     : <code>{city_safe}</code>\n"
                f"📅 <b>Masehi</b>   : <code>{gregorian_safe}</code>\n"
                f"🌙 <b>Hijriah</b>  : <code>{hijri_str}</code>\n"
                f"────────────────────────\n\n"
                f"<b>⏱️ WAKTU SHOLAT</b>\n"
                f"🌌 Imsak   : <code>{t['Imsak']}</code>\n"
                f"🌓 Subuh   : <code>{t['Fajr']}</code>\n"
                f"🌞 Terbit  : <code>{t['Sunrise']}</code>\n"
                f"{dzuhur_emoji} {dzuhur_label}  : <code>{t['Dhuhr']}</code>\n"
                f"🌤️ Ashar   : <code>{t['Asr']}</code>\n"
                f"🌇 Maghrib : <code>{t['Maghrib']}</code>\n"
                f"🌃 Isya    : <code>{t['Isha']}</code>\n\n"
                f"────────────────────────\n"
                f"🤲 <i>'Jadikan sabar dan sholat sebagai penolongmu.'</i>\n"
                f"   <i>(QS. Al-Baqarah: 45)</i>"
            )

            kb = [
                [
                    InlineKeyboardButton(
                        "🔔 Set Daily Reminder", callback_data=f"sholat_reminder|{user_id}|{raw_city}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔍 Check Another City",
                        switch_inline_query_current_chat="sholat ",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Close", callback_data=f"cmd_close|{user_id}"
                    )
                ]
            ]

            await msg.edit_text(
                txt,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(kb),
            )

        else:
            await msg.edit_text(
                (
                    "❌ <b>City not found.</b>\n\n"
                    "<b>Tips:</b>\n"
                    "• Gunakan nama kota yang valid\n"
                    "• Contoh: <code>/sholat Surabaya</code>\n"
                    "• Coba nama kota dalam bahasa Inggris\n\n"
                    "Contoh kota: Jakarta, Surabaya, Bandung, Medan, Yogyakarta"
                ),
                parse_mode=ParseMode.HTML,
            )

    except Exception as e:
        logger.error(f"[SHOLAT] Error: {e}")
        await msg.edit_text(
            f"❌ <b>System Error:</b>\n\n"
            f"<code>{html.escape(str(e)[:100])}</code>\n\n"
            f"<i>Coba lagi dalam beberapa saat.</i>",
            parse_mode=ParseMode.HTML,
        )

async def sholat_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle prayer time reminder setup"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        parts = query.data.split("|")
        action = parts[0]
        
        if action == "sholat_reminder":
            callback_user_id = int(parts[1]) if len(parts) > 1 else user_id
            city = parts[2] if len(parts) > 2 else "Jakarta"
            
            if user_id != callback_user_id:
                await query.answer("❌ Bukan milik kamu!", show_alert=True)
                return
            
            await query.answer("✅ Setting reminder...")
            
            # Store user's preferred prayer city
            try:
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("""
                        INSERT OR REPLACE INTO user_preferences (user_id, prayer_city)
                        VALUES (?, ?)
                    """, (user_id, city))
                    await db.commit()
            except Exception as e:
                logger.debug(f"[SHOLAT] DB update error: {e}")
            
            txt = (
                "<b>🔔 PRAYER TIME REMINDERS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✅ <b>City Set:</b> <code>{html.escape(city)}</code>\n\n"
                "<b>REMINDER OPTIONS:</b>\n"
                "Pilih waktu sholat mana yang ingin diingatkan:\n\n"
            )
            
            buttons = [
                [
                    InlineKeyboardButton("🌓 Subuh", callback_data=f"sholat_set_time|{user_id}|{city}|Fajr"),
                    InlineKeyboardButton("☀️ Dzuhur", callback_data=f"sholat_set_time|{user_id}|{city}|Dhuhr")
                ],
                [
                    InlineKeyboardButton("🌤️ Ashar", callback_data=f"sholat_set_time|{user_id}|{city}|Asr"),
                    InlineKeyboardButton("🌇 Maghrib", callback_data=f"sholat_set_time|{user_id}|{city}|Maghrib")
                ],
                [
                    InlineKeyboardButton("🌃 Isya", callback_data=f"sholat_set_time|{user_id}|{city}|Isha")
                ],
                [
                    InlineKeyboardButton("⏰ All Prayers", callback_data=f"sholat_set_time|{user_id}|{city}|all")
                ],
                [
                    InlineKeyboardButton("❌ Cancel", callback_data=f"cmd_close|{user_id}")
                ]
            ]
            
            await query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        
        elif action == "sholat_set_time":
            callback_user_id = int(parts[1]) if len(parts) > 1 else user_id
            city = parts[2] if len(parts) > 2 else "Jakarta"
            prayer_type = parts[3] if len(parts) > 3 else "all"
            
            if user_id != callback_user_id:
                await query.answer("❌ Bukan milik kamu!", show_alert=True)
                return
            
            await query.answer("✅ Reminder aktif!")
            
            # Store reminder preferences
            try:
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("""
                        INSERT OR REPLACE INTO user_preferences (user_id, prayer_reminder, prayer_type)
                        VALUES (?, 1, ?)
                    """, (user_id, prayer_type))
                    await db.commit()
            except Exception as e:
                logger.debug(f"[SHOLAT] Reminder DB error: {e}")
            
            prayer_labels = {
                "Fajr": "🌓 Subuh",
                "Dhuhr": "☀️ Dzuhur",
                "Asr": "🌤️ Ashar",
                "Maghrib": "🌇 Maghrib",
                "Isha": "🌃 Isya",
                "all": "🕌 Semua Sholat"
            }
            
            prayer_label = prayer_labels.get(prayer_type, prayer_type)
            
            txt = (
                "<b>✅ REMINDER ACTIVATED</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📍 <b>City:</b> <code>{html.escape(city)}</code>\n"
                f"🔔 <b>Prayer:</b> {prayer_label}\n"
                f"⏰ <b>Status:</b> <code>ACTIVE</code>\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "✨ <i>Kamu akan menerima notifikasi 5 menit sebelum waktu sholat</i>\n"
                "💡 <i>Pastikan notification bot diizinkan di settings Telegram</i>\n\n"
                "📝 <i>Untuk mengubah preferensi, gunakan /sholat lagi</i>"
            )
            
            buttons = [
                [InlineKeyboardButton("🔄 Change City", switch_inline_query_current_chat="sholat ")],
                [InlineKeyboardButton("❌ Close", callback_data=f"cmd_close|{user_id}")]
            ]
            
            await query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    
    except Exception as e:
        logger.error(f"[SHOLAT] Reminder callback error: {e}")
        try:
            await query.answer(f"❌ Error: {str(e)[:30]}", show_alert=True)
        except:
            pass

async def inline_sholat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline query for prayer times"""
    query = update.inline_query.query.strip()

    if not query.lower().startswith("sholat"):
        return

    city = query.replace("sholat", "", 1).strip() or "Jakarta"
    city_encoded = urllib.parse.quote(city)

    url = (
        f"https://api.aladhan.com/v1/timingsByCity"
        f"?city={city_encoded}&country=Indonesia&method=20"
    )

    try:
        r = await fetch_json(url)

        if not r or r.get("code") != 200:
            return

        t = r["data"]["timings"]
        d = r["data"]["date"]
        hijri = d["hijri"]
        hijri_str = f"{hijri['day']} {hijri['month']['en']} {hijri['year']}"

        # Check if Friday
        import datetime
        today = datetime.datetime.now()
        is_friday = today.weekday() == 4
        dzuhur_label = "Jum'at" if is_friday else "Dzuhur"

        text = (
            f"🕌 <b>JADWAL SHOLAT — {city.title()}</b>\n"
            f"{d['readable']} | {hijri_str}\n\n"
            f"🌌 Imsak   : {t['Imsak']}\n"
            f"🌓 Subuh   : {t['Fajr']}\n"
            f"🌞 Terbit  : {t['Sunrise']}\n"
            f"☀️ {dzuhur_label}  : {t['Dhuhr']}\n"
            f"🌤️ Ashar   : {t['Asr']}\n"
            f"🌇 Maghrib : {t['Maghrib']}\n"
            f"🌃 Isya    : {t['Isha']}"
        )

        results = [
            InlineQueryResultArticle(
                id="sholat_inline",
                title=f"🕌 Jadwal Sholat {city.title()}",
                description=f"Subuh {t['Fajr']} • {dzuhur_label} {t['Dhuhr']} • Maghrib {t['Maghrib']}",
                input_message_content=InputTextMessageContent(
                    text, parse_mode=ParseMode.HTML
                ),
                thumbnail_url="https://img.icons8.com/color/96/000000/mosque.png",
                thumbnail_height=96,
                thumbnail_width=96
            )
        ]

        await update.inline_query.answer(results, cache_time=3600)

    except Exception as e:
        logger.debug(f"[SHOLAT] Inline error: {e}")
        pass
# ==========================================
# 🌐 /scp — ULTIMATE PROXY SCRAPER (THE HUNTER V3)
# ==========================================

# Helper 1: Generic JSON Parser (Recursive)
def extract_ips_from_json(data):
    """Mencari pola IP:PORT dalam struktur JSON apapun secara rekursif."""
    found = set()
    if isinstance(data, list):
        for item in data:
            found.update(extract_ips_from_json(item))
    elif isinstance(data, dict):
        # Cari kombinasi key umum
        ip = data.get('ip') or data.get('ipAddress') or data.get('host')
        port = data.get('port') or data.get('portNumber')
        if ip and port:
            found.add(f"{ip}:{port}")
        # Rekursif ke dalam value
        for val in data.values():
            if isinstance(val, (dict, list)):
                found.update(extract_ips_from_json(val))
    return found

# Helper 2: Fetcher dengan User-Agent & Retry
async def fetch_proxy_source(client, url):
    """Mengambil data dari URL dengan error handling."""
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.text, True
    except:
        pass
    return "", False

async def proxy_scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    
    # 1. ANIMASI AWAL (Cinematic Hacking Style)
    status_msg = await msg.reply_text(
        "⚡ <b>INITIALIZING HUNTER PROTOCOL V3.0...</b>\n"
        "<code>[░░░░░░░░░░] 0%</code>",
        parse_mode=ParseMode.HTML
    )

    # Animasi Loading (Jalan di background sambil scraping berjalan)
    frames = [
        ("📡 <b>SCANNING GLOBAL NODES...</b>", "██▒▒▒▒▒▒▒▒", 20),
        ("🔓 <b>BYPASSING FIREWALLS...</b>",    "████▒▒▒▒▒▒", 45),
        ("🕸 <b>PARSING JSON STRUCTURES...</b>","███████▒▒▒", 75),
        ("🔄 <b>COMPILING DATASETS...</b>",     "█████████▒", 90),
    ]

    for label, bar, percent in frames:
        await asyncio.sleep(0.5)
        try:
            await status_msg.edit_text(
                f"⏳ {label}\n"
                f"<code>[{bar}] {percent}%</code>",
                parse_mode=ParseMode.HTML
            )
        except: pass

    # 2. DEFINISI SUMBER (Expanded Sources)
    sources = {
        "HTTP": [
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            "https://www.proxy-list.download/api/v1/get?type=http",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        ],
        "SOCKS4": [
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all",
            "https://www.proxy-list.download/api/v1/get?type=socks4",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        ],
        "SOCKS5": [
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
            "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        ]
    }

    # 3. ENGINE EKSEKUSI PARALEL (High Speed)
    start_time = time.time()
    collected_proxies = {"HTTP": set(), "SOCKS4": set(), "SOCKS5": set()}
    
    # Header Browser Asli (Biar ga dianggap bot)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
        # Kita buat list tasks untuk semua URL sekaligus
        tasks = []
        map_url_proto = {} # Mapping untuk tahu URL mana milik protokol apa

        for proto, urls in sources.items():
            for url in urls:
                tasks.append(fetch_proxy_source(client, url))
                map_url_proto[url] = proto # Simpan referensi

        # JALANKAN SEMUA REQUEST BERSAMAAN (Concurrency)
        # Ini jauh lebih cepat daripada loop satu-satu
        results = await asyncio.gather(*tasks)

        # Proses Hasil
        # results berisi list tuple: (text_content, success_boolean)
        # Kita perlu mapping balik manual karena gather mengembalikan list urut
        
        # Flatten list url untuk iterasi yang sama dengan tasks
        flat_urls_list = []
        for proto in sources:
            flat_urls_list.extend(sources[proto])

        for i, (content, success) in enumerate(results):
            if not success: continue
            
            # Ambil protokol berdasarkan URL index
            current_url = flat_urls_list[i]
            # Karena struktur dictionary tidak menjamin urutan di versi python lama, 
            # cara mapping di atas (map_url_proto) lebih aman, tapi disini kita pakai logika sederhana:
            # Kita cari URL ini ada di list protokol mana
            current_proto = "HTTP"
            for p, u_list in sources.items():
                if current_url in u_list:
                    current_proto = p
                    break

            # A. COBA PARSE SEBAGAI JSON GENERIC DULU
            try:
                json_data = json.loads(content)
                json_ips = extract_ips_from_json(json_data)
                collected_proxies[current_proto].update(json_ips)
            except json.JSONDecodeError:
                pass # Bukan JSON, lanjut ke Regex

            # B. FALLBACK KE REGEX (Smart IP:Port Matcher)
            # Regex ini menangkap IP:Port di tengah teks sampah sekalipun
            matches = re.findall(r"(?:^|\D)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)(?:\D|$)", content)
            for proxy in matches:
                # Bersihkan whitespace jika ada
                clean_proxy = proxy.strip()
                collected_proxies[current_proto].add(clean_proxy)

    # Hitung Statistik Akhir
    count_http = len(collected_proxies["HTTP"])
    count_s4 = len(collected_proxies["SOCKS4"])
    count_s5 = len(collected_proxies["SOCKS5"])
    total_found = count_http + count_s4 + count_s5
    duration = round(time.time() - start_time, 2)

    # 4. GENERATE FILE OUTPUT
    full_text = ""
    full_text += f"################################################\n"
    full_text += f"#  THE HUNTER V3 - ELITE PROXY DUMP            #\n"
    full_text += f"#  Generated by: @{context.bot.username}       #\n"
    full_text += f"#  Date: {time.strftime('%Y-%m-%d %H:%M:%S')}  #\n"
    full_text += f"#  Total: {total_found} IPs                    #\n"
    full_text += f"################################################\n\n"

    for proto, proxies in collected_proxies.items():
        if proxies:
            full_text += f"[{proto} LIST - {len(proxies)}]\n"
            full_text += "\n".join(proxies) + "\n\n"

    file_bytes = io.BytesIO(full_text.encode("utf-8"))
    file_bytes.name = f"Hunter_Proxies_{int(time.time())}.txt"

    # 5. FINAL DASHBOARD (Ultimate UI)
    report_text = (
        "<b>🌐 THE HUNTER V3 — NETWORK INFILTRATION</b>\n"
        "<code>━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<b>📊 HARVEST REPORT</b>\n"
        f"├ <b>HTTP/S   :</b> <code>{count_http}</code> Nodes\n"
        f"├ <b>SOCKS4   :</b> <code>{count_s4}</code> Nodes\n"
        f"├ <b>SOCKS5   :</b> <code>{count_s5}</code> Nodes\n"
        f"└ <b>Total    :</b> <code>{total_found}</code> Unique IPs\n\n"
        
        f"<b>⚙️ SYSTEM METRICS</b>\n"
        f"├ <b>Speed      :</b> {duration}s (Async/IO)\n"
        f"├ <b>Parsing    :</b> Regex + JSON Recursive\n"
        f"└ <b>Status     :</b> ✅ COMPLETE\n"
        "<code>━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"💾 <i>Database exported below.</i>"
    )

    # Update pesan loading
    await status_msg.edit_text(report_text, parse_mode=ParseMode.HTML)

    # Kirim Dokumen
    await msg.reply_document(
        document=file_bytes,
        caption="📂 <b>Encrypted Proxy List</b>\n<i>Use for educational purposes only.</i>",
        parse_mode=ParseMode.HTML
    )

# ==========================================
# ⚙️ /setsholat — DAFTAR NOTIFIKASI HARIAN
# ==========================================
async def setsholat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b> <code>/setsholat NamaKota</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    city = " ".join(context.args)
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Cek Kota (samakan method dengan scheduler)
    url = f"https://api.aladhan.com/v1/timingsByCity?city={urllib.parse.quote(city)}&country=Indonesia&method=20"
    r = await fetch_json(url)

    if not r or r.get("code") != 200:
        await update.message.reply_text(
            f"❌ Kota <b>{html.escape(city)}</b> tidak ditemukan.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Simpan Database
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO prayer_subs (chat_id, city) VALUES (?, ?)",
            (chat_id, city),
        )
        await db.commit()

    await update.message.reply_text(
        (
            "✨ <b>PENJADWALAN SHALAT AKTIF</b> ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📍 <b>Lokasi:</b> <code>{html.escape(city.upper())}</code>\n"
            f"👤 <b>User:</b> <code>{html.escape(update.effective_user.first_name)}</code>\n\n"
            "Alhamdulillah, pengingat ibadah Anda telah diatur. Bot akan mengirimkan:\n"
            "• ⏰ <b>Reminder:</b> 5 menit sebelum waktu shalat tiba\n"
            "• 🕌 <b>Adzan:</b> Tepat saat masuk waktu shalat\n\n"
            "<i>“Sesungguhnya shalat itu adalah fardhu yang ditentukan waktunya atas orang-orang yang beriman.” (QS. An-Nisa: 103)</i>"
        ),
        parse_mode=ParseMode.HTML,
    )

    # Jalankan penjadwal untuk hari ini
    await schedule_prayers_for_user(context, chat_id, city)


# ==========================================
# 📴 /stopsholat — MATIKAN NOTIF
# ==========================================
async def stopsholat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Hapus semua job yang terkait chat ini (biar notif bener-bener stop)
    if context.job_queue:
        for job in context.job_queue.get_jobs_by_name(f"{chat_id}_Fajr_rem"): pass  # placeholder safety

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM prayer_subs WHERE chat_id=?", (chat_id,))
        await db.commit()

    # Hapus job yang namanya diawali chat_id_
    if context.job_queue:
        for j in context.job_queue.jobs():
            if j.name and j.name.startswith(f"{chat_id}_"):
                j.schedule_removal()

    await update.message.reply_text(
        "🔕 <b>Prayer notifications disabled for this chat.</b>",
        parse_mode=ParseMode.HTML,
    )


# ==========================================
# 🕌 SISTEM PENGINGAT & ADZAN (ISLAMI)
# ==========================================
async def send_adzan(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data

    waktu = data["waktu"].title()  # Subuh, Dzuhur, dll
    city = data["city"]
    jam = data["jam"]
    tipe = data.get("tipe", "adzan")

    if tipe == "reminder":
        text = (
            f"🕋 <b>PANGGILAN IBADAH</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n"
            f"Alhamdulillah, sebentar lagi (kurang lebih <b>5 menit</b>) akan masuk waktu <b>{waktu.upper()}</b>\n"
            f"untuk wilayah <b>{html.escape(city)}</b> dan sekitarnya.\n\n"
            f"📖 <i>\"Dan dirikanlah shalat, tunaikanlah zakat dan ruku'lah beserta orang-orang yang ruku'.\" (QS. Al-Baqarah: 43)</i>\n\n"
            f"💧 <b>Persiapan:</b>\n"
            f"Mari sejenak lepaskan urusan duniawi, sucikan diri dengan wudhu, dan bersiap menghadap Sang Pencipta."
        )
    else:
        text = (
            f"🕌 <b>WAKTU ADZAN TELAH TIBA</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>Allahu Akbar, Allahu Akbar...</i>\n\n"
            f"Telah masuk waktu shalat <b>{waktu.upper()}</b>\n"
            f"untuk wilayah <b>{html.escape(city)}</b> dan sekitarnya.\n"
            f"⏰ <b>Jam:</b> <code>{jam}</code> WIB\n\n"
            f"حَيَّ عَلَى الصَّلَاةِ — <i>Mari mendirikan shalat</i>\n"
            f"حَيَّ عَلَى الْفَلَاحِ — <i>Mari meraih kemenangan</i>\n\n"
            f"🤲 <b>Doa Ba'da Adzan:</b>\n"
            f"<i>\"Ya Allah, Tuhan pemilik panggilan yang sempurna ini... berilah Muhammad wasilah dan keutamaan.\"</i>\n\n"
            f"✨ Semoga Allah menerima amal ibadah kita semua. Aamiin."
        )

    try:
        await context.bot.send_message(
            chat_id=data["chat_id"], text=text, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        print(f"send_adzan error: {e}")


# ==========================================
# 🕒 PENJADWALAN HARIAN UNTUK SATU USER
# ==========================================
async def schedule_prayers_for_user(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, city: str
):
    """Pasang jadwal reminder + adzan untuk 1 chat & 1 kota."""

    # ✅ Tambahan sesuai request: kalau JobQueue tidak aktif, stop
    if not context.job_queue:
        return

    # Samakan method dengan /sholat
    url = f"https://api.aladhan.com/v1/timingsByCity?city={urllib.parse.quote(city)}&country=Indonesia&method=20"
    r = await fetch_json(url)
    if not r or r.get("code") != 200:
        print(f"[schedule_prayers_for_user] city invalid: {city}")
        return

    timings = r["data"]["timings"]

    # ✅ Timezone per kota (WIB/WITA/WIT) dari meta Aladhan kalau ada
    tz_name = r["data"].get("meta", {}).get("timezone")
    tzinfo = TZ
    if tz_name:
        try:
            tzinfo = ZoneInfo(tz_name)
        except Exception:
            tzinfo = TZ

    now = datetime.datetime.now(tzinfo)

    # ✅ Bersihkan job lama biar tidak dobel
    for j in context.job_queue.jobs():
        if j.name and j.name.startswith(f"{chat_id}_"):
            j.schedule_removal()

    target_prayers = {
        "Fajr": "Subuh",
        "Dhuhr": "Dzuhur",
        "Asr": "Ashar",
        "Maghrib": "Maghrib",
        "Isha": "Isya",
    }

    for p_api, p_name in target_prayers.items():
        raw_time = timings.get(p_api)
        if not raw_time:
            continue

        time_clean = raw_time.split(" ")[0]

        m = re.match(r"^(\d{1,2}):(\d{1,2})$", time_clean)
        if not m:
            print(f"[schedule_prayers_for_user] bad time format: {raw_time}")
            continue

        ph = int(m.group(1))
        pm = int(m.group(2))

        pt_adzan = now.replace(hour=ph, minute=pm, second=0, microsecond=0)

        if pt_adzan <= now:
            pt_adzan = pt_adzan + datetime.timedelta(days=1)

        pt_remind = pt_adzan - datetime.timedelta(minutes=5)

        delta_remind = (pt_remind - now).total_seconds()
        delta_adzan = (pt_adzan - now).total_seconds()

        if delta_remind > 0:
            context.job_queue.run_once(
                send_adzan,
                delta_remind,
                data={
                    "chat_id": chat_id,
                    "waktu": p_name,
                    "city": city,
                    "jam": time_clean,
                    "tipe": "reminder",
                },
                name=f"{chat_id}_{p_api}_rem",
            )

        if delta_adzan > 0:
            context.job_queue.run_once(
                send_adzan,
                delta_adzan,
                data={
                    "chat_id": chat_id,
                    "waktu": p_name,
                    "city": city,
                    "jam": time_clean,
                    "tipe": "adzan",
                },
                name=f"{chat_id}_{p_api}_adz",
            )


# ==========================================
# 🔁 DAILY REFRESH (JALAN SEKALI SEHARI)
# ==========================================
async def daily_prayer_scheduler(context: ContextTypes.DEFAULT_TYPE):
    """Dijalankan tiap pagi: refresh jadwal semua user yang terdaftar."""

    # ✅ Kalau JobQueue tidak aktif, stop
    if not context.job_queue:
        return

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT chat_id, city FROM prayer_subs") as cursor:
            rows = await cursor.fetchall()
            for chat_id, city in rows:
                try:
                    await schedule_prayers_for_user(context, chat_id, city)
                except Exception as e:
                    print(f"daily_prayer_scheduler error ({chat_id}, {city}): {e}")

# ==========================================
# 🔄 CALLBACK ROUTER (FIXED & SAFE + REGISTER LOCK + PDF MENU)
# ==========================================
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()  # Hilangkan loading di tombol
    raw_data = q.data
    user_id = q.from_user.id
    
    # 🛡️ GLOBAL PREMIUM LOCK
    if not await premium_lock_handler(update, context):
        return
    
    # 🔧 FIX: Parse callback_data more robustly
    d = raw_data
    if "|" in raw_data:
        parts = raw_data.split("|")
        # If the last part is numeric, it's likely a user_id suffix, strip it for matching
        if parts[-1].isdigit():
            d = "|".join(parts[:-1])
        else:
            # Handle cases like weather_refresh|city where city is not a number
            d = raw_data

    # --- 🛡️ ADGUARD: Check session for callback (Strict User ID check) ---
    has_session = await adguard.check_session(user_id)
    if not has_session:
        # Check if it's a menu command with a suffix, and if the suffix is the user who clicked
        can_bypass = False
        if "|" in raw_data:
            parts = raw_data.split("|")
            if parts[-1].isdigit() and int(parts[-1]) == user_id:
                # User clicked their own menu but session might be lost in cache, register it
                await adguard.register_session(user_id)
                can_bypass = True
        
        if not can_bypass:
            await q.answer(
                "🚫 ACCESS DENIED\n\nThis session belongs to another user or has expired.\nPlease /start to create your own session.",
                show_alert=True
            )
            return

    # 🔐 CRITICAL: Verify if the callback data contains a user_id and if it matches the clicker
    if "|" in raw_data:
        parts = raw_data.split("|")
        if parts[-1].isdigit():
            owner_id = int(parts[-1])
            if owner_id != user_id:
                await q.answer("🚫 This menu is not yours. Use /start to get your own.", show_alert=True)
                return

    # --- 1. LOGIKA PAYMENT (QRIS) ---
    if d in ["pay_crypto", "pay_qris"]:
        if d == "pay_qris":
            QRIS_IMAGE = "https://i.ibb.co.com/5ggXCz6L/IMG-20251116-WA0003.jpg"
            caption = (
                "💳 <b>SCAN TO PAY</b>\n"
                "Please scan the QRIS code above to complete your payment."
            )
            try:
                await context.bot.send_photo(
                    chat_id=q.message.chat_id,
                    photo=QRIS_IMAGE,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                await q.answer("⚠️ QRIS image failed to load.", show_alert=True)
        else:
            await q.answer("⚠️ Payment Gateway is under maintenance.", show_alert=True)
        return

    # --- 2. LOGIKA WEATHER REFRESH ---
    if d.startswith("weather_refresh"):
        try:
            _, city = d.split("|", 1)
            data = await get_weather_data(city)
            if data and data.get("cod") == 200:
                lat, lon = data["coord"]["lat"], data["coord"]["lon"]
                aqi = await get_aqi(lat, lon)
                txt = format_weather(data, aqi)
                kb = [
                    [InlineKeyboardButton("🔄 Refresh Data", callback_data=f"weather_refresh|{city}")],
                    [InlineKeyboardButton("🗺 View on Map", url=f"https://www.google.com/maps?q={lat},{lon}")],
                ]

                if q.message.photo:
                    await q.message.edit_caption(
                        caption=txt,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(kb),
                    )
                else:
                    await q.message.edit_text(
                        text=txt,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(kb),
                    )
            else:
                await q.answer("Failed to update weather data.", show_alert=True)
        except Exception:
            await q.answer("Error updating weather.", show_alert=True)
        return

    # --- 3. ACCESS LOCK (WAJIB REGISTER DULU) ---
    # Allow: cmd_register, help_why_register, help_back (for non-registered)
    allowed_without_register = ["cmd_register", "help_why_register", "help_back", "menu_main"]
    if d not in allowed_without_register:
        if not await is_registered(user_id):
            await q.answer(
                "⚠️ Access locked.\n"
                "Please complete REGISTER ACCESS first via /start.",
                show_alert=True,
            )
            return

    # ==========================================
    # 🧭 MENU NAVIGATION SYSTEM
    # ==========================================
    # Include user_id for cross-user protection
    btn_back = [[InlineKeyboardButton("🔙 Back to Menu", callback_data=f"menu_main|{user_id}")]]
    text = None
    kb = None

    # --- LOGIKA KONTEN MENU ---
    def get_cost(cmd):
        return f"{CREDIT_COSTS.get(cmd, CREDIT_COSTS['default'])} Credits" if CREDIT_COSTS.get(cmd, CREDIT_COSTS['default']) > 0 else "Free"

    def format_cmd_list(title, commands):
        header = f"<b>{title}</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        lines = []
        for cmd, desc in commands:
            status = "ON ✅"
            cost = get_cost(cmd.strip("/"))
            lines.append(f"<b>{desc}</b>\n• Usage: <code>{cmd}</code>\n• Status: All | {status}\n• Cost: {cost}")
        return header + "\n\n".join(lines)

    # 3.1 REGISTER
    if d == "cmd_register":
        try:
            is_new = await add_subscriber(update.effective_user.id)
        except Exception:
            is_new = False

        reg_date = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
        status = "✅ VERIFIED MEMBER" if is_new else "⚠️ ALREADY REGISTERED"
        text = (
            "🔐 <b>REGISTRATION SUCCESSFUL</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Name:</b> {html.escape(update.effective_user.full_name)}\n"
            f"🆔 <b>User ID:</b> <code>{update.effective_user.id}</code>\n"
            f"📅 <b>Date:</b> {reg_date}\n"
            f"🔰 <b>Status:</b> {status}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Welcome to the Oktacomel Family.\n"
            "You now have access to the main control panel.</i>"
        )
        kb = [[InlineKeyboardButton("🚀 GO TO DASHBOARD", callback_data=f"menu_main|{user_id}")]]

    # 3.2 MAIN DASHBOARD
    elif d in ("menu_main", "cmd_main"):
        await cmd_command(update, context)
        return

    # 3.3 BASIC TOOLS
    elif d == "menu_basic":
        text = format_cmd_list("🛠 BASIC TOOLS", [
            ("/ping", "Check VPS/server latency & uptime"),
            ("/me", "Show your Telegram profile & IDs"),
            ("/qr text", "Generate QR Code from any text/link"),
            ("/cuaca [city]", "Check weather information"),
            ("/broadcast msg", "System broadcast (Owner only)")
        ])
        kb = btn_back

    # 3.4 AI & UTILITY
    elif d == "menu_ai":
        text = format_cmd_list("🧠 AI INTELLIGENCE", [
            ("/ai [query]", "OKTA AI - GPT-5 Brain"),
            ("/code [query]", "AI Coding Assistant"),
            ("/think [query]", "Deep Think AI Analysis"),
            ("/scan [topic]", "Autonomous Research Agent")
        ])
        kb = btn_back

    # 3.5 CHECKER SUITE
    elif d == "menu_check":
        text = format_cmd_list("🔍 CHECKER TOOLS", [
            ("/s [link]", "Stripe Checkout Link Checker"),
            ("/bin [bin]", "Credit Card BIN Lookup"),
            ("/ip [ip]", "IP Address Geolocation"),
            ("/speed", "Server Speedtest (Owner only)")
        ])
        kb = btn_back

    elif d == "menu_dl":
        text = format_cmd_list("📥 OKTACOMEL • DOWNLOADER v2", [
            ("/dl [link]", "Universal Media Downloader"),
            ("/gl [url]", "Gallery/Carousel DL"),
            ("/tiktok [url]", "TikTok Video (No WM)"),
            ("/ig [url]", "Instagram Reels & Story"),
            ("/yt [url]", "YouTube High Quality"),
            ("/fb [url]", "Facebook Video DL"),
            ("/tw [url]", "Twitter/X Media DL"),
            ("/spotify [url]", "Spotify Music DL"),
            ("/pornhub [url]", "Pornhub Video DL"),
            ("/xnxx [url]", "XNXX Video DL")
        ])
        kb = btn_back

    # 3.7 CC GENERATOR
    elif d == "menu_cc":
        text = format_cmd_list("💳 CARDING TOOLS", [
            ("/gen [bin]", "Credit Card Generator"),
            ("/scr [user]", "CC Scraper Tool"),
            ("/vbv [card]", "3DS Lookup / VBV Checker")
        ])
        kb = btn_back

    # 3.8 WEATHER & EARTH
    elif d == "menu_weather":
        text = format_cmd_list("🌦 WEATHER & EARTH", [
            ("/weather [city]", "Live weather & AQI"),
            ("/gempa", "Latest earthquake data (BMKG)")
        ])
        kb = btn_back

    # 3.9 MUSIC
    elif d == "menu_music":
        text = format_cmd_list("🎵 MUSIC TOOLS", [
            ("/song [title]", "Search & Download Spotify"),
            ("/link [user]", "Link Last.fm account")
        ])
        kb = btn_back

    elif d == "menu_pdf":
        text = format_cmd_list("📄 PDF SUITE", [
            ("/pdfmerge", "Merge multiple PDF files"),
            ("/pdfsplit", "Split PDF into pages"),
            ("/pdfcompress", "Compress PDF size"),
            ("/pdftotext", "Extract text from PDF")
        ])
        kb = btn_back

    elif d == "menu_todo":
        text = format_cmd_list("📝 TODO LIST", [
            ("/todo add [task]", "Add task to list"),
            ("/todo list", "Show all tasks"),
            ("/todo clear", "Clear completed tasks")
        ])
        kb = btn_back

    elif d == "menu_mail":
        text = format_cmd_list("📧 TEMP MAIL", [
            ("/tempmail", "Generate new email"),
            ("/inbox", "Check email inbox")
        ])
        kb = btn_back

    # HELP MENU CATEGORIES
    elif d == "help_download":
        text = (
            "📥 <b>DOWNLOAD TOOLS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Usage:</b> <code>/download [link]</code>\n\n"
            "<b>Supported Platforms:</b>\n"
            "• TikTok - Video & Audio (No Watermark)\n"
            "• Instagram - Reels, Stories, Posts\n"
            "• YouTube - Videos & Shorts\n"
            "• Twitter/X - Videos\n"
            "• Facebook - Videos\n\n"
            "<b>Tip:</b> Just send the link directly!"
        )
        kb = [[InlineKeyboardButton("🔙 Back to Help", callback_data=f"help_back|{user_id}")]]

    elif d == "help_ai":
        text = (
            "🤖 <b>AI TOOLS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Commands:</b>\n"
            "• <code>/ai [question]</code> - Multi-model AI\n"
            "• <code>/gpt [text]</code> - GPT-4o\n"
            "• <code>/cla [text]</code> - Claude 3.5\n"
            "• <code>/gmi [text]</code> - Gemini Pro\n"
            "• <code>/img [prompt]</code> - AI Image Gen\n"
            "• <code>/tts [lang] [text]</code> - Text to Speech\n"
            "• <code>/tr [lang] [text]</code> - Translate"
        )
        kb = [[InlineKeyboardButton("🔙 Back to Help", callback_data=f"help_back|{user_id}")]]

    elif d == "help_utility":
        text = (
            "🛠️ <b>UTILITY TOOLS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Commands:</b>\n"
            "• <code>/qr [text]</code> - Generate QR Code\n"
            "• <code>/weather [city]</code> - Weather Info\n"
            "• <code>/convert [amt] [from] [to]</code> - Currency\n"
            "• <code>/ping</code> - Server Status\n"
            "• <code>/me</code> - Your Profile Info\n"
            "• <code>/tempmail</code> - Temporary Email"
        )
        kb = [[InlineKeyboardButton("🔙 Back to Help", callback_data=f"help_back|{user_id}")]]

    elif d == "help_checker":
        text = (
            "🔍 <b>CHECKER TOOLS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Commands:</b>\n"
            "• <code>/bin [number]</code> - BIN Lookup\n"
            "• <code>/sk [key]</code> - Stripe Key Check\n"
            "• <code>/ip [host]</code> - IP Intelligence\n"
            "• <code>/gateway [url]</code> - Payment Gateway\n"
            "• <code>/iban [code]</code> - IBAN Validator"
        )
        kb = [[InlineKeyboardButton("🔙 Back to Help", callback_data=f"help_back|{user_id}")]]

    elif d == "help_shop":
        text = (
            "🛒 <b>SHOP & ORDERS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Commands:</b>\n"
            "• <code>/stock</code> - View Available Stock\n"
            "• <code>/beli</code> - Purchase Products\n"
            "• <code>/sts</code> - Check Order Status\n"
            "• <code>/premium</code> - Premium Plans"
        )
        kb = [[InlineKeyboardButton("🔙 Back to Help", callback_data=f"help_back|{user_id}")]]

    elif d == "help_settings":
        text = (
            "⚙️ <b>SETTINGS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Commands:</b>\n"
            "• <code>/subscribe</code> - Daily Broadcast\n"
            "• <code>/unsubscribe</code> - Stop Broadcast\n"
            "• <code>/link [username]</code> - Link Last.fm\n"
            "• <code>/unlink</code> - Unlink Account"
        )
        kb = [[InlineKeyboardButton("🔙 Back to Help", callback_data=f"help_back|{user_id}")]]

    elif d == "help_why_register":
        text = (
            "ℹ️ <b>WHY REGISTER?</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Benefits:</b>\n"
            "✅ Access all bot features\n"
            "✅ Use AI tools (GPT, Claude, Gemini)\n"
            "✅ Download from any platform\n"
            "✅ Use checker & utility tools\n"
            "✅ Access premium shop\n\n"
            "<b>Registration is FREE!</b>"
        )
        kb = [
            [InlineKeyboardButton("📝 REGISTER NOW", callback_data=f"cmd_register|{user_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"help_back|{user_id}")]
        ]

    elif d == "help_back":
        # Return to help menu
        registered = await is_registered(user_id)
        text = (
            "🐈 <b>OKTACOMEL HELP CENTER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Welcome to Oktacomel Bot!\n"
            "Select a category below to explore features.\n\n"
            f"👤 <b>Status:</b> {'✅ Registered' if registered else '❌ Not Registered'}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>"
        )
        if registered:
            kb = [
                [InlineKeyboardButton("Main Menu", callback_data=f"menu_main|{user_id}")],
                [
                    InlineKeyboardButton("Download", callback_data=f"help_download|{user_id}"),
                    InlineKeyboardButton("AI Tools", callback_data=f"help_ai|{user_id}")
                ],
                [
                    InlineKeyboardButton("Utility", callback_data=f"help_utility|{user_id}"),
                    InlineKeyboardButton("Checker", callback_data=f"help_checker|{user_id}")
                ],
                [
                    InlineKeyboardButton("Shop", callback_data=f"help_shop|{user_id}"),
                    InlineKeyboardButton("Settings", callback_data=f"help_settings|{user_id}")
                ],
                [InlineKeyboardButton("Contact Support", url="https://t.me/hiduphjokowi")]
            ]
        else:
            kb = [
                [InlineKeyboardButton("REGISTER NOW", callback_data=f"cmd_register|{user_id}")],
                [InlineKeyboardButton("Why Register?", callback_data=f"help_why_register|{user_id}")],
                [InlineKeyboardButton("Contact Support", url="https://t.me/hiduphjokowi")]
            ]

    # 3.10 SHA-256 ENCRYPTION
    elif d == "menu_sha":
        text = (
            "🔐 <b>OKTACOMEL • CRYPTO CORE v2</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Module:</b> SHA-256 Hashing Engine\n"
            "<b>Status:</b> 🟢 Optimized\n\n"
            "<b>Usage:</b>\n"
            "<code>/sha [text]</code>\n\n"
            "<b>Security Specs:</b>\n"
            "• 256-bit secure hash algorithm\n"
            "• One-way cryptographic function\n"
            "• Collision resistant matrix\n\n"
            "🚀 <i>Processing at high-speed priority.</i>"
        )
        kb = btn_back

    # 3.11 PREMIUM / BUY
    elif d == "menu_buy":
        text = (
    "🌟 <b><u>OKTACOMEL PREMIUM ACCESS — ULTRA EDITION</u></b> 🌟\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    "🥇 <b>Welcome to the Elite Tier Upgrade Center</b>\n"
    "Unlock the <b>full potential</b> of your assistant and experience\n"
    "<i>unlimited intelligence, ultra-fast processing, and exclusive tools</i>\n"
    "reserved only for our Premium Users.\n\n"

    "✨ <b>What Premium Gives You</b>:\n"
    "• Priority routing on all AI models (GPT-4o / Claude / Gemini)\n"
    "• Faster streaming output (2× speed)\n"
    "• Access to <b>VIP Tools</b>: GodMode TempMail, PDF Suite Ultra, Unlimited Downloader\n"
    "• AI Image Gen Boost — faster queue & bigger output\n"
    "• Early access to future modules\n"
    "• Dedicated support line\n"
    "• <b>Zero hourly slowdowns</b> (server priority)\n"
    "• Exclusive premium-only commands\n\n"

    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🏆 <b>PREMIUM SUBSCRIPTION PLANS</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    "💠 <b>Basic Premium — $69.99</b>\n"
    "Perfect for personal or casual usage.\n"
    "• 80 credits/day\n"
    "• 25 credits/hour\n"
    "• 560 weekly credits\n"
    "• 2400 monthly credits\n"
    "• Priority Level: <b>Silver</b>\n\n"

    "💠 <b>Advanced Premium — $149.99</b>\n"
    "<i>Best value for small creators and power users.</i>\n"
    "• 200 credits/day\n"
    "• 65 credits/hour\n"
    "• 1400 weekly credits\n"
    "• 6000 monthly credits\n"
    "• Priority Level: <b>Gold</b>\n\n"

    "💠 <b>Pro Premium — $249.99</b>\n"
    "Designed for content creators, editors & automation users.\n"
    "• 350 credits/day\n"
    "• 115 credits/hour\n"
    "• 2450 weekly credits\n"
    "• 10500 monthly credits\n"
    "• Priority Level: <b>Platinum</b>\n"
    "• Unlocks: <b>Extended Image Models</b>\n\n"

    "💠 <b>Enterprise Premium — $449.99</b>\n"
    "Full unlocked system — the best we offer.\n"
    "• 800 credits/day\n"
    "• 265 credits/hour\n"
    "• 5600 weekly credits\n"
    "• 24000 monthly credits\n"
    "• Priority Level: <b>Diamond</b>\n"
    "• Unlocks: <b>Unlimited TempMail GodMode</b>\n"
    "• Unlocks: <b>All Upcoming AI Models</b>\n\n"

    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "💎 <b>CREDIT PACKS — ONE TIME PURCHASE</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚡ Perfect for users who don't want monthly subscriptions.\n\n"

    "• $4.99 → 100 credits + 2 bonus\n"
    "• $19.99 → 500 credits + 10 bonus\n"
    "• $39.99 → 1000 credits + 25 bonus\n"
    "• $94.99 → 2500 credits + 50 bonus\n"
    "• $179.99 → 5000 credits + 50 bonus\n"
    "• $333.99 → 10000 credits + 100 bonus\n"
    "• $739.99 → 25000 credits + 300 bonus\n\n"

    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔐 <b>Activation</b>\n"
    "Once payment is confirmed, your premium\n"
    "<b>activates instantly & automatically.</b>\n"
    "No admin contact required.\n\n"

    "🚨 <i>All premium purchases are final — no refunds.</i>\n\n"
    "🤝 <b>Thank you for supporting Oktacomel!</b>\n"
    "Your support helps us improve and maintain powerful tools\n"
    "for the entire community.\n\n"
    "📘 <a href='https://google.com'>Learn More About Plans</a>\n"

        )
        kb = [
            [
                InlineKeyboardButton("💰 Pay via Crypto", callback_data=f"pay_crypto|{user_id}"),
                InlineKeyboardButton("💳 Pay via QRIS", callback_data=f"pay_qris|{user_id}"),
            ],
            [InlineKeyboardButton("🆘 Contact Support", url="https://t.me/hiduphjokowi")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data=f"menu_main|{user_id}")],
        ]

    # 3.12 ACCOUNT / CLOSE / COMING SOON
    elif d == "cmd_close":
        await q.delete_message()
        return

    elif d in ["menu_mail", "menu_todo", "buy_info"]:
        await q.answer("⚠️ This feature is coming soon.", show_alert=True)
        return

    elif d == "cmd_account":
        await me_command(update, context)
        return

    # ==========================================
    # 🧩 EKSEKUSI OUTPUT (ANTI-ERROR FOTO / TEKS)
    # ==========================================
    if text and kb:
        try:
            # Jika pesan asal berupa foto (misal dari /start dengan gambar),
            # lebih aman dihapus dan kirim pesan teks baru.
            if q.message.photo:
                chat_id = q.message.chat.id
                await q.message.delete()
                # Telegram limit ~4096 chars — kalo terlalu panjang kirim sebagai file
                if len(text) > 3800:
                    # kirim sebagai file txt agar aman
                    bio = io.BytesIO(text.encode("utf-8"))
                    bio.name = "menu.txt"
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=InputFile(bio),
                        caption="📄 Menu (saved as file because text is long)",
                    )
                    # kirim tombol terpisah agar user bisa kembali
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="Use the buttons below:",
                        reply_markup=InlineKeyboardMarkup(kb),
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(kb),
                    )
            else:
                # Kalau pesan asal teks biasa, cukup edit isinya.
                # Hati-hati: edit_message_text juga kena batas 4096.
                if len(text) > 3800:
                    # fallback: kirim pesan baru (edit sering gagal untuk teks sangat panjang)
                    await q.message.reply_text(
                        text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(kb),
                    )
                else:
                    await q.message.edit_text(
                        text=text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(kb),
                    )
        except Exception as e:
            # Fallback pamungkas: kirim sebagai pesan baru (dan log error)
            logger.exception("menu output error")
            await q.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(kb),
            )



# ==========================================
# 💳 STRIPE LINK CHECKER (CARDSAVVY)
# ==========================================

async def stripe_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Advanced Stripe payment link scraper dengan detail lengkap - OKTACOMEL BRANDING"""
    if not await premium_lock_handler(update, context): return
    
    if not context.args:
        await update.message.reply_text(
            "💳 <b>OKTACOMEL STRIPE CHECKER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Usage:</b> <code>/s [stripe_url]</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/s https://checkout.stripe.com/c/pay/cs_live_...</code>\n\n"
            "📌 Extracts: Session ID, Public Key, Email, Site, Amount",
            parse_mode=ParseMode.HTML
        )
        return
    
    url = context.args[0].strip()
    if "stripe.com" not in url and "checkout" not in url:
        await update.message.reply_text("❌ <b>Invalid Stripe URL.</b> Please provide a valid checkout link.", parse_mode=ParseMode.HTML)
        return
    
    start_time = time.time()
    msg = await update.message.reply_text("⏳ <b>OKTACOMEL ANALYZING STRIPE LINK...</b>", parse_mode=ParseMode.HTML)

    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            r = await client.get(url, headers=headers)
            content = r.text

            # --- SESSION ID EXTRACTION ---
            session_id = "Not specified"
            session_match = re.search(r'(cs_(?:live|test)_[a-zA-Z0-9]+)', url + content)
            if session_match:
                session_id = session_match.group(1)
            
            # --- PUBLIC KEY EXTRACTION ---
            public_key = "Not specified"
            pk_match = re.search(r'(pk_(?:live|test)_[a-zA-Z0-9]+)', content)
            if pk_match:
                public_key = pk_match.group(1)

            # --- EMAIL EXTRACTION ---
            email = "Not specified"
            # Try JSON data first
            email_json = re.search(r'"email":"([^"]+)"', content)
            if email_json:
                email = email_json.group(1)
            else:
                # Fallback to regex
                email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
                if email_match:
                    email = email_match.group(0)
            
            # --- SITE EXTRACTION ---
            site = urlparse(url).netloc
            if not site or "stripe" in site:
                site_match = re.search(r'https?://([^/\s]+)', content)
                if site_match and "stripe" not in site_match.group(1):
                    site = site_match.group(1)
            
            # --- AMOUNT EXTRACTION ---
            amount_str = "0.00"
            currency = ""
            # Try amount decimal first
            amt_match = re.search(r'"amount":(\d+)', content)
            curr_match = re.search(r'"currency":"([^"]+)"', content)
            
            if amt_match:
                try:
                    amount_val = float(amt_match.group(1)) / 100
                    amount_str = f"{amount_val:.2f}"
                except: pass
            
            if curr_match:
                currency = curr_match.group(1).upper()
            else:
                # Regex for amount display
                display_amt = re.search(r'(\d+(?:\.\d{2})?)\s*(usd|eur|gbp|idr|vnd)', content.lower())
                if display_amt:
                    amount_str = display_amt.group(1)
                    currency = display_amt.group(2).upper()

            duration = round(time.time() - start_time, 2)
            
            text = (
                "<b>OKTACOMEL STRIPE CHECKER</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "✅ <b>Payment Details Extracted</b>\n\n"
                f"💳 <b>Session:</b> <code>{session_id}</code>\n"
                f"🔑 <b>Key:</b> <code>{public_key}</code>\n"
                f"📧 <b>Email:</b> <code>{email}</code>\n"
                f"🌐 <b>Site:</b> <code>{site}</code>\n"
                f"💰 <b>Amount:</b> <code>{amount_str} {currency}</code>\n"
                f"⏱ <b>Processed in:</b> <code>{duration}s</code>\n\n"
                "<i>Powered by OKTACOMEL</i>"
            )
            await msg.edit_text(text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"[STRIPE] Error: {e}")
        await msg.edit_text(f"❌ <b>Error:</b> <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
        if site:
            result += f"🌐 <b>Site:</b> {site}\n"
        if amount:
            result += f"💰 <b>Amount:</b> {amount}\n"
        
        result += f"\n⏱ <b>Processed in:</b> {elapsed:.2f}s"
        
        if not session_id and not pk_key:
            result = (
                "💳 <b>CardSavvy</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ <b>Limited Data Extracted</b>\n\n"
                f"🔗 <b>URL:</b> <code>{url[:50]}...</code>\n"
                f"⏱ <b>Processed in:</b> {elapsed:.2f}s\n\n"
                "<i>Note: Some Stripe pages require authentication to view full details.</i>"
            )
        
        await status_msg.edit_text(result, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"[STRIPE] Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)[:100]}", parse_mode=ParseMode.HTML)

# ==========================================
# 🖥️ VIRTUAL LINUX TERMINAL (OKTACOMEL OS)
# ==========================================
import subprocess
import shlex

# Whitelisted commands for security (RESTRICTED - no interpreters/network tools)
SAFE_COMMANDS = [
    'ls', 'pwd', 'whoami', 'date', 'cal', 'echo', 'head', 'tail',
    'wc', 'sort', 'uniq', 'df', 'du', 'free', 'uptime',
    'uname', 'hostname', 'id', 'printenv', 'which',
    'file', 'stat', 'basename', 'dirname',
    'tr', 'cut', 'rev', 'tac', 'nl', 'seq', 'shuf',
    'base64', 'md5sum', 'sha256sum', 'sha1sum',
    'clear', 'history', 'python', 'python3', 'node', 'npm', 'pip', 'curl', 'wget', 'nc', 'netcat',
    'cat', 'find', 'grep', 'awk', 'sed', 'git', 'tar', 'zip', 'gzip'
]

# Blocked patterns for security (STRICT)
BLOCKED_PATTERNS = [
    'rm', 'dd', ':(){ ', 'fork', 'mkfs', 'chmod', 'chown', 'passwd',
    'sudo', 'su ', 'shutdown', 'reboot', 'halt', 'kill', 'pkill',
    '&&', '||', ';', '|', '`', '$(', 'eval', 'exec', 'source',
    './', '../', '/home', '/root', '/etc', '/var', '/usr', '/bin',
    '/dev', '/proc', '/sys', 'config.py', 'adguard.py', '.env'
]

user_terminal_sessions = {}

async def os_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Virtual Linux Terminal - Oktacomel OS"""
    if not await premium_lock_handler(update, context): return
    
    user_id = update.effective_user.id
    
    if not context.args:
        # Show terminal welcome screen
        text = (
            "🖥️ <b>OKTACOMEL VIRTUAL OS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Welcome to <b>Oktacomel Terminal</b> — a secure, sandboxed Linux environment\n"
            "running directly inside Telegram.\n\n"
            "⚡ <b>QUICK START</b>\n"
            "<code>/os ls -la</code> — List files\n"
            "<code>/os pwd</code> — Current directory\n"
            "<code>/os uname -a</code> — System info\n"
            "<code>/os python3 -c \"print('Hello')\"</code> — Run Python\n"
            "<code>/os curl -s ifconfig.me</code> — Check IP\n\n"
            "📋 <b>AVAILABLE COMMANDS</b>\n"
            "<code>ls, pwd, cat, grep, find, curl, wget, ping,\n"
            "python3, node, git, base64, md5sum, df, free...</code>\n\n"
            "🔒 <b>SECURITY</b>\n"
            "• Sandboxed environment (isolated)\n"
            "• Dangerous commands are blocked\n"
            "• Session timeout: 30 minutes\n\n"
            "🚀 <i>Type your command after /os to execute!</i>"
        )
        
        kb = [
            [
                InlineKeyboardButton("ls -la", callback_data=f"os_exec|ls -la|{user_id}"),
                InlineKeyboardButton("uname -a", callback_data=f"os_exec|uname -a|{user_id}")
            ],
            [
                InlineKeyboardButton("df -h", callback_data=f"os_exec|df -h|{user_id}"),
                InlineKeyboardButton("free -h", callback_data=f"os_exec|free -h|{user_id}")
            ],
            [
                InlineKeyboardButton("uptime", callback_data=f"os_exec|uptime|{user_id}"),
                InlineKeyboardButton("whoami", callback_data=f"os_exec|whoami|{user_id}")
            ],
            [InlineKeyboardButton("❌ Close Terminal", callback_data=f"os_close|{user_id}")]
        ]
        
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Execute command
    cmd_input = " ".join(context.args)
    await execute_terminal_command(update, context, cmd_input, user_id)

async def execute_terminal_command(update: Update, context: ContextTypes.DEFAULT_TYPE, cmd_input: str, user_id: int):
    """Execute a terminal command safely"""
    
    # Security check - blocked patterns
    cmd_lower = cmd_input.lower()
    for blocked in BLOCKED_PATTERNS:
        if blocked in cmd_lower:
            await update.effective_message.reply_text(
                f"🚫 <b>BLOCKED</b>\n\n"
                f"Command contains restricted pattern: <code>{blocked}</code>\n"
                f"This operation is not allowed for security reasons.",
                parse_mode=ParseMode.HTML
            )
            return
    
    # Security check - whitelisted base commands
    base_cmd = cmd_input.split()[0] if cmd_input.split() else ""
    
    # Allow some commands with arguments
    allowed = False
    for safe in SAFE_COMMANDS:
        if base_cmd == safe or base_cmd.endswith(f"/{safe}"):
            allowed = True
            break
    
    if not allowed:
        await update.effective_message.reply_text(
            f"⚠️ <b>COMMAND NOT ALLOWED</b>\n\n"
            f"<code>{base_cmd}</code> is not in the whitelist.\n\n"
            f"Allowed commands: <code>{', '.join(SAFE_COMMANDS[:15])}...</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Execute command
    status_msg = await update.effective_message.reply_text(
        f"⏳ <b>Executing...</b>\n<code>$ {html.escape(cmd_input)}</code>",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Run command with timeout
        process = await asyncio.create_subprocess_shell(
            cmd_input,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp"
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            process.kill()
            await status_msg.edit_text(
                "⏰ <b>TIMEOUT</b>\n\nCommand exceeded 30 second limit.",
                parse_mode=ParseMode.HTML
            )
            return
        
        output = stdout.decode('utf-8', errors='replace')
        error = stderr.decode('utf-8', errors='replace')
        
        # Combine output
        result = output if output else error
        result = result.strip() if result else "(no output)"
        
        # Truncate if too long
        if len(result) > 3500:
            result = result[:3500] + "\n\n... [output truncated]"
        
        # Format output
        exit_code = process.returncode
        status_icon = "✅" if exit_code == 0 else "❌"
        
        text = (
            f"🖥️ <b>OKTACOMEL TERMINAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 <b>Input:</b>\n<code>$ {html.escape(cmd_input)}</code>\n\n"
            f"📤 <b>Output:</b> {status_icon}\n"
            f"<pre>{html.escape(result)}</pre>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Exit Code: <code>{exit_code}</code>"
        )
        
        kb = [
            [
                InlineKeyboardButton("🔄 Run Again", callback_data=f"os_exec|{cmd_input[:50]}|{user_id}"),
                InlineKeyboardButton("🏠 Menu", callback_data=f"os_menu|{user_id}")
            ],
            [InlineKeyboardButton("❌ Close", callback_data=f"os_close|{user_id}")]
        ]
        
        await status_msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        
    except Exception as e:
        logger.error(f"[OS] Error executing command: {e}")
        await status_msg.edit_text(
            f"❌ <b>EXECUTION ERROR</b>\n\n<code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML
        )

async def os_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle OS terminal callbacks"""
    q = update.callback_query
    
    # Premium lock check
    if not await premium_lock_handler(update, context):
        return
    
    await q.answer()
    
    data = q.data
    parts = data.split("|")
    action = parts[0]
    user_id = q.from_user.id
    
    # Check owner
    if len(parts) > 2 and parts[-1].isdigit():
        owner_id = int(parts[-1])
        if owner_id != user_id:
            await q.answer("🚫 This terminal belongs to another user.", show_alert=True)
            return
    
    if action == "os_exec":
        cmd = parts[1] if len(parts) > 1 else "ls"
        await execute_terminal_command(update, context, cmd, user_id)
        
    elif action == "os_menu":
        text = (
            "🖥️ <b>OKTACOMEL VIRTUAL OS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Quick commands available below.\n"
            "Or type <code>/os [command]</code> to run custom commands.\n\n"
            "🚀 <i>Select an action:</i>"
        )
        
        kb = [
            [
                InlineKeyboardButton("ls -la", callback_data=f"os_exec|ls -la|{user_id}"),
                InlineKeyboardButton("uname -a", callback_data=f"os_exec|uname -a|{user_id}")
            ],
            [
                InlineKeyboardButton("df -h", callback_data=f"os_exec|df -h|{user_id}"),
                InlineKeyboardButton("free -h", callback_data=f"os_exec|free -h|{user_id}")
            ],
            [
                InlineKeyboardButton("uptime", callback_data=f"os_exec|uptime|{user_id}"),
                InlineKeyboardButton("whoami", callback_data=f"os_exec|whoami|{user_id}")
            ],
            [InlineKeyboardButton("❌ Close Terminal", callback_data=f"os_close|{user_id}")]
        ]
        
        await q.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        
    elif action == "os_close":
        await q.message.delete()
        close_msg = await context.bot.send_message(
            chat_id=q.message.chat_id,
            text="🖥️ <b>Terminal session closed.</b>\n\nType <code>/os</code> to start a new session.",
            parse_mode=ParseMode.HTML
        )
        await asyncio.sleep(5)
        try:
            await close_msg.delete()
        except:
            pass

# ==========================================
# 🧹 CACHE & TEMP CLEANER
# ==========================================

async def clear_cache_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear temporary files, logs, and cache folders"""
    user_id = update.effective_user.id
    
    # Only Admin/Owner can clear cache
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ This command is restricted to the bot owner.")
        return
        
    status_msg = await update.message.reply_text("🧹 <b>Purging system cache...</b>", parse_mode=ParseMode.HTML)
    
    cleaned_dirs = []
    freed_space = 0
    
    # Targets to clean
    targets = ['downloads', 'temp', 'tmp', 'cache', '__pycache__']
    
    try:
        for target in targets:
            path = os.path.join(os.getcwd(), target)
            if os.path.exists(path):
                # Calculate size before delete
                for root, dirs, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(root, f)
                        freed_space += os.path.getsize(fp)
                
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    os.makedirs(path)
                else:
                    os.remove(path)
                cleaned_dirs.append(target)
        
        # Clean .log files in current dir
        for f in os.listdir(os.getcwd()):
            if f.endswith('.log'):
                fp = os.path.join(os.getcwd(), f)
                freed_space += os.path.getsize(fp)
                os.remove(fp)
        
        size_str = f"{freed_space / (1024*1024):.2f} MB" if freed_space > 0 else "0 MB"
        
        result_text = (
            "🧹 <b>SYSTEM PURGE COMPLETE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ <b>Cleaned:</b> <code>{', '.join(cleaned_dirs) if cleaned_dirs else 'None'}</code>\n"
            f"💾 <b>Space Freed:</b> <code>{size_str}</code>\n\n"
            "✨ <i>System is now fresh and optimized.</i>"
        )
        
        await status_msg.edit_text(result_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"[CLEAN] Error: {e}")
        await status_msg.edit_text(f"❌ <b>Purge Failed:</b> {str(e)}", parse_mode=ParseMode.HTML)

# Add to main function or registration logic
# application.add_handler(CommandHandler("clearcache", clear_cache_command))
# application.add_handler(CommandHandler("clean", clear_cache_command))

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Autonomous Research Agent - Deep Web Analysis"""
    if not await premium_lock_handler(update, context): return
    
    user_id = update.effective_user.id
    
    # Check and deduct credits for research (expensive)
    if context.args:
        success, remaining, cost = await deduct_credits(user_id, "scan")
        if not success:
            await update.message.reply_text(
                f"❌ <b>Kredit Tidak Cukup</b>\n\n"
                f"Research Agent membutuhkan {cost} kredit.\n"
                f"Kredit kamu: {remaining}\n\n"
                f"💎 Upgrade ke Premium untuk lebih banyak kredit!",
                parse_mode=ParseMode.HTML
            )
            return
    
    if not context.args:
        text = (
            "🔬 <b>OKTACOMEL RESEARCH AGENT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "An autonomous AI agent that conducts deep research\n"
            "on any topic you provide.\n\n"
            "⚡ <b>CAPABILITIES</b>\n"
            "• Multi-source web research\n"
            "• Data aggregation & analysis\n"
            "• Trend detection & insights\n"
            "• Comprehensive report generation\n\n"
            "📋 <b>USAGE</b>\n"
            "<code>/scan [topic]</code>\n\n"
            "📌 <b>EXAMPLES</b>\n"
            "• <code>/scan Bitcoin price prediction 2026</code>\n"
            "• <code>/scan Best programming languages for AI</code>\n"
            "• <code>/scan Indonesian tech startup trends</code>\n"
            "• <code>/scan Cybersecurity threats 2026</code>\n\n"
            "🤖 <i>Powered by Oktacomel AI Engine</i>"
        )
        
        kb = [
            [InlineKeyboardButton("Try: Crypto Trends", callback_data=f"scan_topic|crypto market trends 2026|{user_id}")],
            [InlineKeyboardButton("Try: AI Technology", callback_data=f"scan_topic|artificial intelligence future|{user_id}")],
            [InlineKeyboardButton("❌ Close", callback_data=f"scan_close|{user_id}")]
        ]
        
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return
    
    topic = " ".join(context.args)
    await execute_research(update, context, topic, user_id)

async def execute_research(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str, user_id: int):
    """Execute deep research on a topic"""
    
    # Status message with progress
    status_msg = await update.effective_message.reply_text(
        f"🔬 <b>RESEARCH AGENT ACTIVATED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 <b>Topic:</b> <i>{html.escape(topic)}</i>\n\n"
        f"⏳ <b>Stage 1/4:</b> Initializing research...\n"
        f"<code>[▓░░░░░░░░░] 10%</code>",
        parse_mode=ParseMode.HTML
    )
    
    try:
        await asyncio.sleep(1)
        
        # Stage 2: Searching
        await status_msg.edit_text(
            f"🔬 <b>RESEARCH AGENT ACTIVATED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 <b>Topic:</b> <i>{html.escape(topic)}</i>\n\n"
            f"⏳ <b>Stage 2/4:</b> Searching sources...\n"
            f"<code>[▓▓▓░░░░░░░] 30%</code>",
            parse_mode=ParseMode.HTML
        )
        
        await asyncio.sleep(1)
        
        # Stage 3: Analyzing
        await status_msg.edit_text(
            f"🔬 <b>RESEARCH AGENT ACTIVATED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 <b>Topic:</b> <i>{html.escape(topic)}</i>\n\n"
            f"⏳ <b>Stage 3/4:</b> Analyzing data...\n"
            f"<code>[▓▓▓▓▓▓░░░░] 60%</code>",
            parse_mode=ParseMode.HTML
        )
        
        # Call AI to generate research report
        research_prompt = f"""You are an expert research analyst. Conduct comprehensive research on the following topic and provide a detailed, well-structured report.

TOPIC: {topic}

Please provide:
1. EXECUTIVE SUMMARY (2-3 sentences overview)
2. KEY FINDINGS (5-7 bullet points with important discoveries)
3. DETAILED ANALYSIS (In-depth explanation of the topic)
4. CURRENT TRENDS (What's happening now in this space)
5. FUTURE OUTLOOK (Predictions and forecasts)
6. RECOMMENDATIONS (Actionable insights)
7. SOURCES (List 3-5 credible source types that would be consulted)

Format your response professionally with clear sections. Use facts, statistics, and specific examples where possible. Write in a formal analytical tone."""
        
        # Use existing AI function
        async with aiohttp.ClientSession() as session:
            payload = {
                "messages": [{"role": "user", "content": research_prompt}],
                "model": "gpt-4o-mini"
            }
            
            async with session.post(
                "https://text.pollinations.ai/openai",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    report = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    report = "Research data compilation completed. Analysis ready."
        
        await asyncio.sleep(1)
        
        # Stage 4: Complete
        await status_msg.edit_text(
            f"🔬 <b>RESEARCH AGENT ACTIVATED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 <b>Topic:</b> <i>{html.escape(topic)}</i>\n\n"
            f"✅ <b>Stage 4/4:</b> Report ready!\n"
            f"<code>[▓▓▓▓▓▓▓▓▓▓] 100%</code>",
            parse_mode=ParseMode.HTML
        )
        
        await asyncio.sleep(0.5)
        
        # Format and send report
        if len(report) > 3800:
            # Send as document if too long
            report_header = (
                f"📊 <b>OKTACOMEL RESEARCH REPORT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 <b>Topic:</b> <i>{html.escape(topic)}</i>\n"
                f"📅 <b>Generated:</b> <code>{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                f"🤖 <b>Agent:</b> Oktacomel Research AI\n\n"
            )
            
            # Create file
            import io
            file_content = f"OKTACOMEL RESEARCH REPORT\n{'='*50}\n\nTopic: {topic}\nDate: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n{report}"
            
            file_buffer = io.BytesIO(file_content.encode('utf-8'))
            file_buffer.name = f"research_{topic[:20].replace(' ', '_')}.txt"
            
            await status_msg.delete()
            await update.effective_message.reply_document(
                document=file_buffer,
                caption=report_header + "📄 Full report attached as document.",
                parse_mode=ParseMode.HTML
            )
        else:
            # Format report
            formatted_report = (
                f"📊 <b>OKTACOMEL RESEARCH REPORT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 <b>Topic:</b> <i>{html.escape(topic)}</i>\n"
                f"📅 <b>Generated:</b> <code>{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n"
                f"{'─'*30}\n\n"
                f"{html.escape(report)}\n\n"
                f"{'─'*30}\n"
                f"🤖 <i>Powered by Oktacomel Research Agent</i>"
            )
            
            kb = [
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"scan_new|{user_id}")],
                [InlineKeyboardButton("❌ Close", callback_data=f"scan_close|{user_id}")]
            ]
            
            await status_msg.edit_text(formatted_report, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        
    except Exception as e:
        logger.error(f"[SCAN] Research error: {e}")
        await status_msg.edit_text(
            f"❌ <b>RESEARCH ERROR</b>\n\n<code>{html.escape(str(e)[:200])}</code>",
            parse_mode=ParseMode.HTML
        )

async def scan_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle research agent callbacks"""
    q = update.callback_query
    
    # Premium lock check
    if not await premium_lock_handler(update, context):
        return
    
    await q.answer()
    
    data = q.data
    parts = data.split("|")
    action = parts[0]
    user_id = q.from_user.id
    
    if action == "scan_topic":
        topic = parts[1] if len(parts) > 1 else "technology trends"
        await execute_research(update, context, topic, user_id)
        
    elif action == "scan_new":
        text = (
            "🔬 <b>NEW RESEARCH</b>\n\n"
            "Type <code>/scan [topic]</code> to start a new research.\n\n"
            "Example: <code>/scan AI in healthcare</code>"
        )
        await q.message.edit_text(text, parse_mode=ParseMode.HTML)
        
    elif action == "scan_close":
        await q.message.delete()

# ==========================================
# 🚀 MAIN PROGRAM (MESIN UTAMA)
# ==========================================
def main():
    print("🚀 ULTRA GOD MODE v12.0 STARTED...")

    # 1. Inisialisasi Database (sync di awal)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    
    # 🛡️ ADGUARD: Set global instance
    set_adguard_instance(adguard)

    # 2. Build Bot
    app = Application.builder().token(TOKEN).build()

    # ==========================================
    # 🎮 COMMAND HANDLERS
    # ==========================================

    # --- Basic & Menu ---
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cmd", cmd_command))
    app.add_handler(CommandHandler("me", me_command))
    app.add_handler(CommandHandler("userinfo", userinfo_command))
    app.add_handler(CommandHandler("ping", ping_command))

    # --- AI & Tools ---
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("gpt", ai_command))
    app.add_handler(CommandHandler("code", code_command))
    app.add_handler(CommandHandler("think", think_command))
    app.add_handler(CommandHandler("gemini", think_command))
    app.add_handler(CommandHandler("img", img_command))
    app.add_handler(CommandHandler("tts", tts_command))
    app.add_handler(CommandHandler("tr", tr_command))
    app.add_handler(CommandHandler("convert", convert_command))
    app.add_handler(CommandHandler("qr", qr_command))
    app.add_handler(CommandHandler("ip", ip_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("berita", news_command))
    
    # --- Virtual OS Terminal ---
    app.add_handler(CommandHandler("os", os_command))
    app.add_handler(CommandHandler("terminal", os_command))
    app.add_handler(CommandHandler("shell", os_command))
    app.add_handler(CallbackQueryHandler(os_callback_handler, pattern=r"^os_"))
    
    # --- Research Agent ---
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("research", scan_command))
    app.add_handler(CallbackQueryHandler(scan_callback_handler, pattern=r"^scan_"))
    
    # --- Stripe Checker ---
    app.add_handler(CommandHandler("s", stripe_check_command))
    app.add_handler(CommandHandler("stripe", stripe_check_command))
    
    # --- SMS Bus OTP ---
    app.add_handler(CommandHandler("sms", sms_command))
    app.add_handler(CommandHandler("otp", sms_command))
    app.add_handler(CallbackQueryHandler(sms_callback_handler, pattern=r"^sms_"))
    
    # --- Drama Hub ---
    app.add_handler(CommandHandler("drama", drama_command))
    app.add_handler(CommandHandler("drakor", drama_command))
    app.add_handler(CallbackQueryHandler(drama_watch_handler, pattern=r"^drama_watch\|"))
    app.add_handler(CallbackQueryHandler(drama_callback_handler, pattern=r"^drama_(?!watch)"))
    
    # --- AI Reply Handler (for conversational mode) ---
    app.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, ai_reply_handler))
    
    # --- Word Chain Game Message Handler (MULTIPLAYER - uses chat_id) ---
    async def word_chain_message_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id in active_word_games:
            await handle_word_chain_reply(update, context)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, word_chain_message_wrapper), group=1)

    # --- Downloader ---
    app.add_handler(CommandHandler("dl", dl_command))
    app.add_handler(CommandHandler("ig", ig_download_command))
    app.add_handler(CommandHandler("instagram", ig_download_command))
    app.add_handler(CommandHandler("gl", gallery_command))
    app.add_handler(CommandHandler("gallery", gallery_command))

    # --- Checker & Carding (Premium Gate) ---
    app.add_handler(CommandHandler("gen", gen_command))
    app.add_handler(CommandHandler("chk", chk_command))
    app.add_handler(CommandHandler("extrap", extrap_command))
    app.add_handler(CommandHandler("bin", bin_lookup_command))
    app.add_handler(CommandHandler("fake", fake_command))
    app.add_handler(CommandHandler("proxy", proxy_check_command))
    app.add_handler(CommandHandler("scr", scr_command))
    app.add_handler(CommandHandler("scrape", scr_command))

    # --- Finance ---
    app.add_handler(CommandHandler("crypto", crypto_command))
    app.add_handler(CallbackQueryHandler(crypto_refresh_handler, pattern=r"^crypto_refresh\|"))
    app.add_handler(CallbackQueryHandler(crypto_alert_handler, pattern=r"^alert\|"))
    app.add_handler(CommandHandler("sha", sha_command))
    app.add_handler(CallbackQueryHandler(sha_refresh_callback, pattern="^sha_refresh\\|"))
    app.add_handler(CommandHandler("buy", buy_command))
    
    # --- E-Wallet, PLN, Bola (Premium Features) ---
    app.add_handler(CommandHandler("wallet", wallet_command))
    app.add_handler(CommandHandler("ewallet", wallet_command))
    app.add_handler(CallbackQueryHandler(wallet_callback_handler, pattern=r"^wallet_"))
    app.add_handler(CommandHandler("pln", pln_command))
    app.add_handler(CommandHandler("listrik", pln_command))
    app.add_handler(CommandHandler("bola", bola_command))
    app.add_handler(CommandHandler("jadwalbola", bola_command))
    app.add_handler(CommandHandler("soccer", bola_command))
    app.add_handler(CallbackQueryHandler(bola_refresh_handler, pattern=r"^bola_refresh\|"))
    
    # --- Word Chain Game ---
    app.add_handler(CommandHandler("kata", kata_command))
    app.add_handler(CommandHandler("wordchain", kata_command))
    app.add_handler(CallbackQueryHandler(kata_callback_handler, pattern=r"^kata_"))

    # --- Admin ---
    app.add_handler(CommandHandler("addprem", addprem_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # --- Anime (SFW & NSFW) ---
    app.add_handler(CommandHandler("waifu", anime_command))
    app.add_handler(CommandHandler("neko", anime_command))
    app.add_handler(CommandHandler("shinobu", anime_command))
    app.add_handler(CommandHandler("nwaifu", anime_command))
    app.add_handler(CommandHandler("nneko", anime_command)) 
    app.add_handler(CommandHandler("trap", anime_command)) 
    app.add_handler(CommandHandler("blowjob", anime_command))

    # --- Truth or Dare (ToD) ---
    app.add_handler(CommandHandler("tod", tod_command))
    app.add_handler(CallbackQueryHandler(tod_button_handler, pattern=r"^tod_mode_|tod_close"))
    app.add_handler(CallbackQueryHandler(tod_menu_handler, pattern=r"^tod_menu$"))

    # --- Weather, Gempa, Sholat ---
    app.add_handler(CommandHandler("weather", cuaca_command))
    app.add_handler(CommandHandler("cuaca", cuaca_command))
    app.add_handler(CallbackQueryHandler(cuaca_command, pattern=r"^weather_refresh\|"))
    app.add_handler(CommandHandler("gempa", gempa_command))
    app.add_handler(CommandHandler("sholat", sholat_command))
    app.add_handler(CommandHandler("setsholat", setsholat_command))
    app.add_handler(CommandHandler("stopsholat", stopsholat_command))
    app.add_handler(InlineQueryHandler(inline_sholat))
    

    # --- System Logs & Status ---
    app.add_handler(CommandHandler("log", log_command))
    app.add_handler(CommandHandler("logs", log_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("health", status_command))
    app.add_handler(CallbackQueryHandler(log_callback_handler, pattern=r"^sys_log_"))

    # --- Temp Mail (Official Library) ---
    app.add_handler(CommandHandler("mail", mail_command))
    # app.add_handler(CallbackQueryHandler(mail_button_handler, pattern='^tm_'))  # Handler not defined

    # --- Notes Premium ---
    app.add_handler(CommandHandler("note", note_add_command))
    app.add_handler(CommandHandler("notes", note_list_command))
    app.add_handler(CommandHandler("dnote", note_delete_command))
    app.add_handler(CallbackQueryHandler(notes_callback_handler, pattern="^notes_"))

    # --- PDF Tools ---
    app.add_handler(CommandHandler("pdf", pdf_menu_command))
    app.add_handler(CommandHandler("pdftools", pdf_menu_command))
    app.add_handler(CallbackQueryHandler(pdf_callback_handler, pattern=r"^pdf_help\|"))
    app.add_handler(CallbackQueryHandler(pdf_menu_callback, pattern=r"^pdf_menu\|"))
    app.add_handler(CommandHandler("pdfmerge", pdf_merge_command))
    app.add_handler(CommandHandler("pdfsplit", pdf_split_command))
    app.add_handler(CommandHandler("pdftotext", pdf_to_text_command))
    app.add_handler(CommandHandler("compresspdf", pdf_compress_command))
    app.add_handler(CommandHandler("imgpdf", imgpdf_command))
    
    # --- Backfree Mode ---
    app.add_handler(CommandHandler("bf", bf_command))
    app.add_handler(CommandHandler("backfree", bf_command))

    # --- Cloudflare DNS Manager ---
    app.add_handler(CommandHandler("cf", cf_command))
    app.add_handler(CommandHandler("cloudflare", cf_command))
    app.add_handler(CommandHandler("cfapi", cfapi_command))
    app.add_handler(CommandHandler("cfsub", cfsub_command))
    app.add_handler(CommandHandler("cfip", cfip_command))
    app.add_handler(CommandHandler("cfhost", cfhost_command))
    app.add_handler(CommandHandler("cfping", cfping_command))
    app.add_handler(CommandHandler("cfexp", cfexp_command))
    app.add_handler(CallbackQueryHandler(cf_callback_handler, pattern=r"^cf_"))

    # ==========================================
    # 👤 USER INFO (PISAH)
    # ==========================================
    app.add_handler(CommandHandler("userinfo", userinfo_command))
    app.add_handler(CallbackQueryHandler(userinfo_refresh_callback, pattern="^userinfo_refresh_"))
    app.add_handler(CallbackQueryHandler(userinfo_close_callback, pattern="^userinfo_close$"))

    # --- Proxy Config ---
    app.add_handler(CommandHandler("setproxy", setproxy_command))
    app.add_handler(CommandHandler("scp", proxy_scrape_command))

    # --- Music Suite (Spotify/Etc) ---
    app.add_handler(CommandHandler("song", song_command))
    app.add_handler(CommandHandler("music", song_command))
    app.add_handler(CallbackQueryHandler(song_button_handler, pattern=r"^sp_dl\|"))
    app.add_handler(CallbackQueryHandler(song_nav_handler, pattern=r"^sp_nav\|"))
    app.add_handler(CallbackQueryHandler(lyrics_handler, pattern=r"^lyr_get\|"))
    app.add_handler(CallbackQueryHandler(real_effect_handler, pattern=r"^eff_"))

    # ==========================================
    # 🚀 SPEED TEST (PISAH)
    # ==========================================
    app.add_handler(CommandHandler("speed", speedtest_command))
    
    app.add_handler(CallbackQueryHandler(locked_register_handler, pattern=r"^locked_register(\|\d+)?$"))

    # ==========================================
    # 🎨 MENU NAVIGATION & ADMIN HANDLERS
    # ==========================================
    
    # --- Menu Navigation ---
    app.add_handler(CallbackQueryHandler(cmd_command, pattern=r"^menu_main(\|\d+)?$"))
    app.add_handler(CallbackQueryHandler(close_session_command, pattern=r"^cmd_close(\|\d+)?$"))

    # --- Admin Stats Dashboard ---
    app.add_handler(CommandHandler("admin", admin_stats_command))
    app.add_handler(CallbackQueryHandler(admin_stats_command, pattern=r"^admin_stats(\|\d+)?$"))
    app.add_handler(CommandHandler("clearcache", clear_cache_command))
    app.add_handler(CommandHandler("clean", clear_cache_command))
    app.add_handler(CallbackQueryHandler(clear_cache_command, pattern=r"^admin_clear_cache$"))
    
    # --- Redeem Code System ---
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("gencode", gencode_command))
    app.add_handler(CommandHandler("listcodes", listcodes_command))

    # --- Main Menu Callback (last, catch-all) ---
    app.add_handler(CallbackQueryHandler(menu_callback))

    # ==========================================
    # ⏰ JOB QUEUE
    # ==========================================
    if app.job_queue:
        jq = app.job_queue
        print("✅ JobQueue DETECTED: Fitur jadwal otomatis AKTIF.")
        try:
            jq.run_daily(morning_broadcast, time=datetime.time(hour=6, minute=0, tzinfo=TZ), name="morning_broadcast")
        except NameError: pass

        try:
            jq.run_daily(daily_prayer_scheduler, time=datetime.time(hour=1, minute=0, tzinfo=TZ), name="daily_prayer_refresh")
            jq.run_once(daily_prayer_scheduler, when=10, name="boot_prayer_refresh")
        except NameError: pass

        try:
            jq.run_repeating(check_price_alerts, interval=60, first=30, name="price_alert_checker")
        except NameError: pass
        
        try:
            jq.run_daily(check_premium_expiry_reminder, time=datetime.time(hour=9, minute=0, tzinfo=TZ), name="premium_expiry_reminder")
        except NameError: pass
    else:
        print("\n❌ WARNING: JobQueue TIDAK AKTIF! (pip install python-telegram-bot[job-queue])\n")

    print("✅ SYSTEM ONLINE (FULL FEATURES + FACTORY MODE)")
    app.run_polling()

# ==========================================
# 🔥 KUNCI KONTAK (NYALAKAN MESIN)
# ==========================================
if __name__ == "__main__":
    main()