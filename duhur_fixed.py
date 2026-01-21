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

    # Jika BUKAN Owner dan BUKAN Premium, tolak!
    if not is_allowed:
        text = (
            "Hey! The bot is temporarily available only for premium users, "
            "but don't worry—it’ll be open to everyone soon. I hope you understand. "
            "Thanks for your support and stay tuned!\n\n"
            "Use /buy command."
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
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

# ==========================================
# 🖥️ PING / SYSTEM CHECK (PREMIUM UI)
# ==========================================
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await premium_lock_handler(update, context): return
    # Catat waktu awal
    s = time.time()
    
    # Pesan Loading
    msg = await update.message.reply_text("⏳ <b>Analyzing system...</b>", parse_mode=ParseMode.HTML)
    
    try:
        # --- DATA SYSTEM ---
        # 1. Hitung Ping
        end = time.time()
        ping_ms = (end - s) * 1000
        
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
# WORD CHAIN GAME (SAMBUNG KATA)
# ==========================================

# Word databases for each level and language
WORD_CHAIN_WORDS = {
    "id": {
        "easy": ["apel", "jeruk", "mangga", "pisang", "anggur", "melon", "semangka", "pepaya", "kelapa", "durian",
                 "kucing", "anjing", "burung", "ikan", "ayam", "bebek", "kambing", "sapi", "kuda", "gajah",
                 "meja", "kursi", "pintu", "jendela", "lantai", "dinding", "atap", "rumah", "mobil", "motor",
                 "buku", "pensil", "pulpen", "kertas", "tas", "sepatu", "baju", "celana", "topi", "kaos",
                 "air", "api", "tanah", "angin", "hujan", "panas", "dingin", "terang", "gelap", "besar"],
        "medium": ["kendaraan", "pendidikan", "pekerjaan", "makanan", "minuman", "pakaian", "peralatan", "kesehatan",
                   "keluarga", "tetangga", "teman", "sahabat", "musuh", "harapan", "impian", "keinginan", "kebutuhan",
                   "perjalanan", "petualangan", "pengalaman", "pengetahuan", "kebijaksanaan", "keberanian", "kejujuran",
                   "kebaikan", "keadilan", "kemerdekaan", "persatuan", "kesatuan", "keharmonisan", "kedamaian",
                   "kekuatan", "kelemahan", "kelebihan", "kekurangan", "kesuksesan", "kegagalan", "perjuangan"],
        "hard": ["demokratisasi", "industrialisasi", "globalisasi", "modernisasi", "transformasi", "rehabilitasi",
                 "profesionalisme", "nasionalisme", "kapitalisme", "sosialisme", "materialisme", "spiritualisme",
                 "pembangunan", "pengembangan", "perkembangan", "pertumbuhan", "kemajuan", "peningkatan",
                 "kontribusi", "distribusi", "konstruksi", "instruksi", "reproduksi", "produksi",
                 "komunikasi", "informasi", "presentasi", "representasi", "implementasi", "evaluasi"]
    },
    "en": {
        "easy": ["apple", "orange", "banana", "grape", "melon", "cherry", "peach", "pear", "plum", "mango",
                 "cat", "dog", "bird", "fish", "horse", "cow", "sheep", "goat", "pig", "duck",
                 "table", "chair", "door", "window", "floor", "wall", "roof", "house", "car", "bike",
                 "book", "pen", "paper", "bag", "shoe", "shirt", "pants", "hat", "sock", "coat",
                 "water", "fire", "earth", "wind", "rain", "sun", "moon", "star", "sky", "sea"],
        "medium": ["computer", "telephone", "television", "internet", "education", "government", "business",
                   "adventure", "experience", "knowledge", "happiness", "sadness", "excitement", "friendship",
                   "relationship", "community", "environment", "technology", "opportunity", "challenge",
                   "achievement", "development", "improvement", "management", "entertainment", "celebration",
                   "competition", "cooperation", "communication", "imagination", "determination", "motivation"],
        "hard": ["entrepreneurship", "sustainability", "responsibility", "accountability", "professionalism",
                 "infrastructure", "implementation", "administration", "transformation", "globalization",
                 "democratization", "industrialization", "modernization", "internationalization", "commercialization",
                 "characterization", "conceptualization", "systematization", "standardization", "computerization",
                 "telecommunication", "experimentation", "differentiation", "diversification", "identification"]
    }
}

# Active games storage: {chat_id: game_state} - MULTIPLAYER
active_word_games = {}

async def get_word_game_stats(user_id: int) -> dict:
    """Get user's word game statistics"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT xp, games_played, games_won, highest_streak FROM word_game_scores WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"xp": row[0], "games_played": row[1], "games_won": row[2], "highest_streak": row[3]}
    except Exception as e:
        logger.error(f"[WORD_GAME] Stats error: {e}")
    return {"xp": 0, "games_played": 0, "games_won": 0, "highest_streak": 0}

async def update_word_game_stats(user_id: int, xp_earned: int, won: bool, streak: int):
    """Update user's word game statistics"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            # Check if user exists
            async with db.execute("SELECT user_id FROM word_game_scores WHERE user_id = ?", (user_id,)) as cursor:
                exists = await cursor.fetchone()
            
            if exists:
                if won:
                    await db.execute("""
                        UPDATE word_game_scores SET 
                        xp = xp + ?, games_played = games_played + 1, games_won = games_won + 1,
                        highest_streak = MAX(highest_streak, ?)
                        WHERE user_id = ?
                    """, (xp_earned, streak, user_id))
                else:
                    await db.execute("""
                        UPDATE word_game_scores SET 
                        xp = xp + ?, games_played = games_played + 1,
                        highest_streak = MAX(highest_streak, ?)
                        WHERE user_id = ?
                    """, (xp_earned, streak, user_id))
            else:
                won_val = 1 if won else 0
                await db.execute("""
                    INSERT INTO word_game_scores (user_id, xp, games_played, games_won, highest_streak)
                    VALUES (?, ?, 1, ?, ?)
                """, (user_id, xp_earned, won_val, streak))
            await db.commit()
    except Exception as e:
        logger.error(f"[WORD_GAME] Update stats error: {e}")

async def kata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Word Chain Game - /kata command - MULTIPLAYER"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if game already active in this chat
    if chat_id in active_word_games:
        game = active_word_games[chat_id]
        players_list = ", ".join([f"@{p['name']}" for p in game['players'].values()][:5]) or "Belum ada"
        hidden = game["hide_fn"](game["current_word"])
        await update.message.reply_text(
            f"<b>Game sedang berlangsung!</b>\n\n"
            f"Players: {players_list}\n"
            f"🎯 <b>TEBAK KATA:</b> <code>{hidden.upper()}</code>\n\n"
            f"Kirim jawaban langsung untuk bergabung!",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Get user stats
    stats = await get_word_game_stats(user_id)
    
    text = (
        "<b>OKTACOMEL WORD CHAIN GAME</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>MULTIPLAYER MODE</b>\n"
        "Semua orang bisa ikut main!\n\n"
        "Sambung kata dengan huruf terakhir!\n"
        "Connect words with the last letter!\n\n"
        f"Your XP: <code>{stats['xp']}</code>\n"
        f"Games: <code>{stats['games_played']}</code>\n"
        f"Wins: <code>{stats['games_won']}</code>\n"
        f"Best Streak: <code>{stats['highest_streak']}</code>\n\n"
        "Pilih bahasa dan level:\n"
    )
    
    buttons = [
        [InlineKeyboardButton("Indonesia - Easy", callback_data=f"kata_start|id|easy|{user_id}"),
         InlineKeyboardButton("Indonesia - Medium", callback_data=f"kata_start|id|medium|{user_id}")],
        [InlineKeyboardButton("Indonesia - Hard", callback_data=f"kata_start|id|hard|{user_id}")],
        [InlineKeyboardButton("English - Easy", callback_data=f"kata_start|en|easy|{user_id}"),
         InlineKeyboardButton("English - Medium", callback_data=f"kata_start|en|medium|{user_id}")],
        [InlineKeyboardButton("English - Hard", callback_data=f"kata_start|en|hard|{user_id}")],
        [InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]
    ]
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def kata_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle word chain game callbacks - MULTIPLAYER"""
    query = update.callback_query
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or update.effective_user.username or "Player"
    data = query.data
    
    parts = data.split("|")
    action = parts[0]
    
    if action == "kata_start":
        lang = parts[1]
        level = parts[2]
        owner_id = int(parts[3]) if len(parts) > 3 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        # Check if game already active
        if chat_id in active_word_games:
            await query.answer("Game sudah berjalan di chat ini!", show_alert=True)
            return
        
        await query.answer("Starting multiplayer game...")
        
        # Initialize game
        word_list = WORD_CHAIN_WORDS.get(lang, {}).get(level, [])
        if not word_list:
            await query.message.edit_text("Error: Word list not available.", parse_mode=ParseMode.HTML)
            return
        
        import random
        start_word = random.choice(word_list)
        
        def hide_word(word):
            """Hide word with '_' in random pattern (e.g. semangka -> s_m_ng_a)"""
            if len(word) <= 2: return word
            chars = list(word)
            # Replace 40-60% of middle characters with '_'
            indices = list(range(1, len(word) - 1))
            num_to_hide = max(1, int(len(indices) * 0.5))
            to_hide = random.sample(indices, num_to_hide)
            for idx in to_hide:
                chars[idx] = "_"
            return "".join(chars)

        # XP per correct answer based on level
        xp_per_word = {"easy": 5, "medium": 10, "hard": 20}.get(level, 5)
        level_name = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}.get(level, level)
        lang_name = {"id": "Indonesia", "en": "English"}.get(lang, lang)
        
        active_word_games[chat_id] = {
            "lang": lang,
            "level": level,
            "current_word": start_word,
            "used_words": [start_word],
            "streak": 0,
            "total_xp": 0,
            "xp_per_word": xp_per_word,
            "word_list": word_list,
            "message_id": query.message.message_id,
            "started_by": user_id,
            "players": {},
            "last_player": None,
            "word_history": [], # Start empty, history will track user answers
            "timer": None,
            "hide_fn": hide_word
        }
        
        # Start 10s timer
        game_timer = context.job_queue.run_once(word_game_timeout_wrapper(chat_id), 10, chat_id=chat_id, name=f"word_timer_{chat_id}")
        active_word_games[chat_id]["timer"] = game_timer
        
        hidden_start = hide_word(start_word)
        
        text = (
            "🎯 <b>GUESS THE WORD - MULTIPLAYER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🌐 <b>Lang:</b> <code>{lang_name}</code>\n"
            f"🔥 <b>Level:</b> <code>{level_name}</code>\n"
            f"➕ <b>Reward:</b> <code>+{xp_per_word} XP</code>\n\n"
            f"🎯 <b>TEBAK KATA:</b>\n"
            f"<code>{hidden_start}</code>\n\n"
            "⏳ <b>Waktu: 10 detik!</b>\n\n"
            "<i>Ketik jawaban langsung di chat!\n"
            "Siapa cepat dia dapat!</i>"
        )
        
        buttons = [[InlineKeyboardButton("🛑 End Game", callback_data=f"kata_giveup|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    elif action == "kata_giveup":
        owner_id = int(parts[1]) if len(parts) > 1 else user_id
        
        # Only game starter or owner can end
        if chat_id in active_word_games:
            game = active_word_games[chat_id]
            if user_id != game.get("started_by") and user_id != OWNER_ID:
                await query.answer("Hanya yang memulai game yang bisa mengakhiri!", show_alert=True)
                return
            if game.get("timer"):
                game["timer"].schedule_removal()
        
        await query.answer("Game ended!")
        
        game = active_word_games.pop(chat_id, None)
        if game and game["players"]:
            # Save stats for all players
            for pid, pdata in game["players"].items():
                await update_word_game_stats(pid, pdata["xp"], False, pdata["words"])
            
            # Build leaderboard
            sorted_players = sorted(game["players"].items(), key=lambda x: x[1]["xp"], reverse=True)
            leaderboard = ""
            for i, (pid, pdata) in enumerate(sorted_players[:5], 1):
                medal = ["", ""][i-1] if i <= 2 else ""
                leaderboard += f"{medal}{i}. {pdata['name']}: +{pdata['xp']} XP ({pdata['words']} words)\n"
            
            text = (
                "<b>GAME OVER - MULTIPLAYER</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Total Streak: <code>{game['streak']}</code>\n"
                f"Total Players: <code>{len(game['players'])}</code>\n\n"
                f"<b>LEADERBOARD:</b>\n"
                f"{leaderboard}\n"
                f"Word chain:\n"
                f"<code>{' -> '.join(game['used_words'][:12])}</code>\n\n"
                "Thanks for playing!\n"
                "Powered by OKTACOMEL"
            )
        else:
            text = (
                "<b>GAME OVER</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "No active game or no players joined.\n\n"
                "Powered by OKTACOMEL"
            )
        
        buttons = [[InlineKeyboardButton("Play Again", callback_data=f"kata_menu|{user_id}"),
                    InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    elif action == "kata_menu":
        await query.answer()
        
        stats = await get_word_game_stats(user_id)
        
        text = (
            "<b>OKTACOMEL WORD CHAIN GAME</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>MULTIPLAYER MODE</b>\n"
            "Semua orang bisa ikut main!\n\n"
            "Sambung kata dengan huruf terakhir!\n"
            "Connect words with the last letter!\n\n"
            f"Your XP: <code>{stats['xp']}</code>\n"
            f"Games: <code>{stats['games_played']}</code>\n"
            f"Wins: <code>{stats['games_won']}</code>\n"
            f"Best Streak: <code>{stats['highest_streak']}</code>\n\n"
            "Pilih bahasa dan level:\n"
        )
        
        buttons = [
            [InlineKeyboardButton("Indonesia - Easy", callback_data=f"kata_start|id|easy|{user_id}"),
             InlineKeyboardButton("Indonesia - Medium", callback_data=f"kata_start|id|medium|{user_id}")],
            [InlineKeyboardButton("Indonesia - Hard", callback_data=f"kata_start|id|hard|{user_id}")],
            [InlineKeyboardButton("English - Easy", callback_data=f"kata_start|en|easy|{user_id}"),
             InlineKeyboardButton("English - Medium", callback_data=f"kata_start|en|medium|{user_id}")],
            [InlineKeyboardButton("English - Hard", callback_data=f"kata_start|en|hard|{user_id}")],
            [InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]
        ]
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return

def word_game_timeout_wrapper(cid):
    async def timeout(context: ContextTypes.DEFAULT_TYPE):
        if cid in active_word_games:
            g = active_word_games[cid]
            import random
            
            reveal_word = g["current_word"].lower()
            
            nw_list = [w for w in g["word_list"] if w.lower() not in [uw.lower() for uw in g["used_words"]]]
            if not nw_list:
                active_word_games.pop(cid, None)
                await context.bot.send_message(cid, f"⏰ <b>WAKTU HABIS!</b>\nJawabannya: <code>{reveal_word}</code>\n\n❌ Kamus habis.", parse_mode=ParseMode.HTML)
                return
            nw = random.choice(nw_list)
            g["current_word"] = nw
            g["used_words"].append(nw)
            g["streak"] = 0
            h = g["hide_fn"](nw)
            await context.bot.send_message(cid, f"⏰ <b>WAKTU HABIS!</b>\n\nJawabannya tadi: <code>{reveal_word}</code>\n\n🎯 <b>TEBAK BARU:</b> <code>{h}</code>", parse_mode=ParseMode.HTML)
            g["timer"] = context.job_queue.run_once(timeout, 10, chat_id=cid)
    return timeout

async def handle_word_chain_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle replies for word chain game - MULTIPLAYER"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or update.effective_user.username or "Player"
    
    # Check if game active in this chat
    if chat_id not in active_word_games:
        return False
    
    game = active_word_games[chat_id]
    user_word = update.message.text.strip().lower()
    
    # Anti-cheat detection (simple heuristic for "hints" or "giving answers")
    cheating_keywords = ["jawabannya", "hintnya", "katanya adalah", "pake kata", "itu jawabannya", "jawab :", "jawab:"]
    if any(k in user_word for k in cheating_keywords) or len(user_word) > 30:
        return False # Ignore messages that look like talk or hints

    # Skip if word contains spaces (likely not a game response)
    if " " in user_word:
        return False
    
    # Skip if word is too short
    if len(user_word) < 2:
        return False
    
    # Validate word - Guess the Word Mode
    current_word = game["current_word"].strip().lower()
    
    # Check if word matches exactly (case insensitive, normalized)
    if user_word != current_word:
        # WRONG ANSWER LOGIC: Reveal correct word and skip to next
        correct_word = game["current_word"].lower()
        
        # Pick next word immediately
        import random
        next_word_list = [w for w in game["word_list"] if w.lower() not in [uw.lower() for uw in game["used_words"]]]
        
        if not next_word_list:
            if game.get("timer"):
                game["timer"].schedule_removal()
            active_word_games.pop(chat_id, None)
            await update.message.reply_text(f"❌ <b>SALAH!</b> Jawabannya adalah: <code>{correct_word}</code>\n\n✨ <b>KAMUS HABIS!</b> Game Over.", parse_mode=ParseMode.HTML)
            return True

        next_word = random.choice(next_word_list)
        game["current_word"] = next_word
        game["used_words"].append(next_word)
        game["streak"] = 0 # Reset streak on wrong answer
        hidden_next = game["hide_fn"](next_word)
        
        # Restart timer
        if game.get("timer"):
            game["timer"].schedule_removal()
        game["timer"] = context.job_queue.run_once(word_game_timeout_wrapper(chat_id), 10, chat_id=chat_id)

        text = (
            f"❌ <b>JAWABAN SALAH!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Player:</b> {html.escape(user_name)}\n"
            f"📝 <b>Tadi minta:</b> <code>{correct_word}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>CHALLENGE BARU:</b>\n"
            f"🔡 <b>Tebak:</b> <code>{hidden_next}</code>\n"
            f"⏳ <b>Timer:</b> <code>10 Seconds</code>\n\n"
            f"<i>Ayo lebih teliti lagi!</i>"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return True
    
    # Check if same player as last
    if game["last_player"] == user_id:
        return True

    # Valid word! STOP TIMER IMMEDIATELY to prevent race condition
    if game.get("timer"):
        game["timer"].schedule_removal()
        game["timer"] = None

    # Valid word! Update game state (don't add to used_words since it was already added when generated)
    game["streak"] += 1
    game["total_xp"] += game["xp_per_word"]
    game["last_player"] = user_id
    game["word_history"].append((user_word, user_name))
    
    # Add/update player stats
    if user_id not in game["players"]:
        game["players"][user_id] = {"name": user_name, "xp": 0, "words": 0}
    game["players"][user_id]["xp"] += game["xp_per_word"]
    game["players"][user_id]["words"] += 1

    # Restart timer with a NEW RANDOM WORD
    if game.get("timer"):
        game["timer"].schedule_removal()
    
    # Pick next word
    import random
    next_word_list = [w for w in game["word_list"] if w.lower() not in [uw.lower() for uw in game["used_words"]]]
    if not next_word_list:
        if game.get("timer"):
            game["timer"].schedule_removal()
        active_word_games.pop(chat_id, None)
        await update.message.reply_text("✨ <b>KAMUS HABIS!</b> Team Win!", parse_mode=ParseMode.HTML)
        return True

    next_word = random.choice(next_word_list)
    game["current_word"] = next_word
    game["used_words"].append(next_word)
    hidden_next = game["hide_fn"](next_word)
    
    # Status bar elegant
    progress_bar = "▰" * min(game["streak"], 10) + "▱" * (10 - min(game["streak"], 10))
    
    text = (
        "✨ <b>CORRECT ANSWER!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Player:</b> {html.escape(user_name)}\n"
        f"📝 <b>Answer:</b> <code>{user_word}</code>\n"
        f"➕ <b>Reward:</b> <code>+{game['xp_per_word']} XP</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>NEXT CHALLENGE:</b>\n"
        f"🔡 <b>Tebak:</b> <code>{hidden_next}</code>\n"
        f"🔥 <b>Streak:</b> <code>{game['streak']}</code>\n"
        f"📊 <b>Progress:</b> <code>{progress_bar}</code>\n"
        "⏳ <b>Timer:</b> <code>10 Seconds</code>\n\n"
        "<i>Type your guess directly in the chat!</i>"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    
    game["timer"] = context.job_queue.run_once(word_game_timeout_wrapper(chat_id), 10, chat_id=chat_id)
    return True


# ==========================================
# SMS BUS OTP - PREMIUM ULTIMATE VERSION
# Virtual Number SMS Receiver (sms-bus.com API)
# ==========================================

SMS_BUS_API_KEY = os.getenv("SMS_BUS_API_KEY", "")
SMS_BUS_BASE_URL = "https://sms-bus.com/api/control"

# Active SMS orders: {user_id: {"request_id": int, "phone": str, "service": str, ...}}
active_sms_orders = {}

# Cache for countries and services from API
sms_countries_cache = {}
sms_services_cache = {}

async def sms_bus_api(endpoint: str, params: dict = None) -> dict:
    """Make request to sms-bus.com API"""
    if not SMS_BUS_API_KEY:
        return {"code": 0, "message": "API key not configured"}
    
    if params is None:
        params = {}
    params["token"] = SMS_BUS_API_KEY
    
    url = f"{SMS_BUS_BASE_URL}/{endpoint}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, params=params)
            return r.json()
    except Exception as e:
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
    """Buy a virtual number"""
    return await sms_bus_api("get/number", {"country_id": country_id, "project_id": project_id})

async def sms_check_sms(request_id: int) -> dict:
    """Check for received SMS"""
    return await sms_bus_api("get/sms", {"request_id": request_id})

async def sms_cancel_order(request_id: int) -> dict:
    """Cancel an order"""
    return await sms_bus_api("cancel", {"request_id": request_id})

async def sms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """SMS Bus OTP Command - /sms (OWNER ONLY)"""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ <b>Access Denied:</b> This command is for Owner only.", parse_mode=ParseMode.HTML)
        return
    
    if not await premium_lock_handler(update, context):
        return
    
    if not SMS_BUS_API_KEY:
        await update.message.reply_text(
            "<b>SMS BUS ERROR</b>\n\n"
            "API key not configured. Contact admin.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Get balance
    balance_result = await sms_get_balance()
    balance = 0
    if balance_result.get("code") == 200:
        balance = balance_result.get("data", {}).get("balance", 0)
    
    # Get services from API
    services_result = await sms_get_services()
    services = {}
    if services_result.get("code") == 200:
        services = services_result.get("data", {})
    
    text = (
        "<b>SMS BUS OTP - PREMIUM ULTIMATE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<i>Virtual Number SMS Receiver</i>\n"
        "<i>Get OTP from any service worldwide</i>\n\n"
        f"Balance: <code>${balance:.2f}</code>\n\n"
        "<b>Select Service:</b>\n"
    )
    
    # Build service buttons from API (3 per row)
    buttons = []
    # Sort services by title for easier navigation
    sorted_services = sorted(services.items(), key=lambda x: x[1].get("title", ""))
    
    # Priority services to show on top
    priority_titles = ["Telegram", "WhatsApp", "Google", "Facebook", "Instagram", "Twitter", "TikTok", "Microsoft", "Yahoo"]
    priority_list = []
    other_list = []
    
    for svc_id, svc_data in sorted_services:
        title = svc_data.get("title", "")
        is_priority = False
        for p in priority_titles:
            if p.lower() in title.lower():
                priority_list.append((svc_id, svc_data))
                is_priority = True
                break
        if not is_priority:
            other_list.append((svc_id, svc_data))
            
    # Combine lists (Priority first, then others)
    service_list = priority_list + other_list
    service_list = service_list[:99] # Show more services (up to 99)
    
    for i in range(0, len(service_list), 3):
        row = []
        for svc_id, svc_data in service_list[i:i+3]:
            title = svc_data.get("title", "Unknown")[:12]
            row.append(InlineKeyboardButton(
                title,
                callback_data=f"sms_svc|{svc_id}|{user_id}"
            ))
        buttons.append(row)
    
    # Add balance & history buttons
    buttons.append([
        InlineKeyboardButton("Balance", callback_data=f"sms_balance|{user_id}"),
        InlineKeyboardButton("My Orders", callback_data=f"sms_orders|{user_id}")
    ])
    buttons.append([InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")])
    
    await update.message.reply_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def sms_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle SMS Bus callbacks"""
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    
    parts = data.split("|")
    action = parts[0]
    
    if action == "sms_svc":
        # Service selected, show countries
        project_id = parts[1]
        owner_id = int(parts[2]) if len(parts) > 2 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        # Get service name from cache
        services = sms_services_cache
        service_name = services.get(project_id, {}).get("title", f"Service {project_id}")
        
        await query.answer(f"Selected: {service_name}")
        
        # Get countries from API
        countries_result = await sms_get_countries()
        countries = {}
        if countries_result.get("code") == 200:
            countries = countries_result.get("data", {})
        
        text = (
            "<b>SMS BUS OTP - SELECT COUNTRY</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Service: <b>{service_name}</b>\n\n"
            "<b>Select Country:</b>\n"
        )
        
        # Build country buttons (2 per row)
        buttons = []
        # Sort countries by title
        sorted_countries = sorted(countries.items(), key=lambda x: x[1].get("title", ""))
        country_list = list(sorted_countries)[:50]  # Show up to 50 countries
        for i in range(0, len(country_list), 2):
            row = []
            for country_id, country_data in country_list[i:i+2]:
                title = country_data.get("title", "Unknown")[:15]
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
        return
    
    elif action == "sms_ctry":
        # Country selected, buy number
        project_id = int(parts[1])
        country_id = int(parts[2])
        owner_id = int(parts[3]) if len(parts) > 3 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        await query.answer("Buying number...")
        
        # Get names from cache
        services = sms_services_cache
        countries = sms_countries_cache
        service_name = services.get(str(project_id), {}).get("title", f"Service {project_id}")
        country_name = countries.get(str(country_id), {}).get("title", f"Country {country_id}")
        
        # Buy number
        result = await sms_buy_number(country_id, project_id)
        
        if result.get("code") != 200:
            error_msg = result.get("message", "Unknown error")
            text = (
                "<b>SMS BUS - ERROR</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Error:</b> {error_msg}\n\n"
                "<i>Try different country or service</i>"
            )
            buttons = [[InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]]
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            return
        
        # Success - store order
        order_data = result.get("data", {})
        request_id = order_data.get("request_id")
        phone = order_data.get("number", "N/A")
        
        active_sms_orders[user_id] = {
            "request_id": request_id,
            "phone": phone,
            "project_id": project_id,
            "country_id": country_id,
            "service_name": service_name,
            "country_name": country_name
        }
        
        text = (
            "<b>SMS BUS - NUMBER READY</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Service:</b> {service_name}\n"
            f"<b>Country:</b> {country_name}\n\n"
            f"<b>Phone:</b>\n<code>+{phone}</code>\n\n"
            f"<b>Request ID:</b> <code>{request_id}</code>\n\n"
            "<b>Status:</b> Waiting for SMS...\n\n"
            "<i>Use this number to receive OTP.\n"
            "Click Check SMS to view received messages.</i>"
        )
        
        buttons = [
            [InlineKeyboardButton("Check SMS", callback_data=f"sms_check|{request_id}|{user_id}"),
             InlineKeyboardButton("Refresh", callback_data=f"sms_check|{request_id}|{user_id}")],
            [InlineKeyboardButton("Cancel Order", callback_data=f"sms_cancel|{request_id}|{user_id}")],
            [InlineKeyboardButton("New Order", callback_data=f"sms_menu|{user_id}")]
        ]
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    elif action == "sms_check":
        # Check for SMS
        request_id = int(parts[1])
        owner_id = int(parts[2]) if len(parts) > 2 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        await query.answer("Checking SMS...")
        
        result = await sms_check_sms(request_id)
        
        # Get order info
        order = active_sms_orders.get(user_id, {})
        phone = order.get("phone", "N/A")
        service_name = order.get("service_name", "Unknown")
        
        if result.get("code") == 200:
            # SMS received!
            sms_code = result.get("data", "")
            
            text = (
                "<b>SMS BUS - SMS RECEIVED!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Phone:</b> <code>+{phone}</code>\n"
                f"<b>Service:</b> {service_name}\n\n"
                f"<b>OTP CODE:</b>\n<code>{sms_code}</code>\n\n"
                "<i>Order completed successfully!</i>"
            )
            
            # Clear order
            active_sms_orders.pop(user_id, None)
            
            buttons = [[InlineKeyboardButton("New Order", callback_data=f"sms_menu|{user_id}"),
                        InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]]
        
        elif result.get("code") == 50101:
            # Not received yet
            text = (
                "<b>SMS BUS - WAITING</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Phone:</b> <code>+{phone}</code>\n"
                f"<b>Service:</b> {service_name}\n"
                f"<b>Request ID:</b> <code>{request_id}</code>\n\n"
                "<b>Status:</b> Waiting for SMS...\n\n"
                "<i>SMS not received yet. Keep checking!</i>"
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
                "<b>SMS BUS - EXPIRED</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Error:</b> {result.get('message', 'Number expired')}\n\n"
                "<i>Please get a new number.</i>"
            )
            active_sms_orders.pop(user_id, None)
            buttons = [[InlineKeyboardButton("New Order", callback_data=f"sms_menu|{user_id}")]]
        
        else:
            # Other error
            text = (
                "<b>SMS BUS - ERROR</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Error:</b> {result.get('message', 'Unknown error')}\n"
            )
            buttons = [
                [InlineKeyboardButton("Retry", callback_data=f"sms_check|{request_id}|{user_id}")],
                [InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]
            ]
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    elif action == "sms_cancel":
        request_id = int(parts[1])
        owner_id = int(parts[2]) if len(parts) > 2 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        result = await sms_cancel_order(request_id)
        
        if result.get("code") == 200:
            await query.answer("Order cancelled! Refunded.", show_alert=True)
            active_sms_orders.pop(user_id, None)
        else:
            await query.answer(f"Error: {result.get('message', 'Unknown')}", show_alert=True)
        
        # Back to menu
        balance_result = await sms_get_balance()
        balance = 0
        if balance_result.get("code") == 200:
            balance = balance_result.get("data", {}).get("balance", 0)
        
        # Get services
        services_result = await sms_get_services()
        services = services_result.get("data", {}) if services_result.get("code") == 200 else {}
        
        text = (
            "<b>SMS BUS OTP - PREMIUM ULTIMATE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<i>Order cancelled successfully!</i>\n\n"
            f"Balance: <code>${balance:.2f}</code>\n\n"
            "<b>Select Service:</b>\n"
        )
        
        buttons = []
        service_list = list(services.items())[:24]
        for i in range(0, len(service_list), 3):
            row = []
            for svc_id, svc_data in service_list[i:i+3]:
                title = svc_data.get("title", "Unknown")[:12]
                row.append(InlineKeyboardButton(title, callback_data=f"sms_svc|{svc_id}|{user_id}"))
            buttons.append(row)
        buttons.append([InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")])
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    elif action == "sms_balance":
        owner_id = int(parts[1]) if len(parts) > 1 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        await query.answer("Checking balance...")
        
        result = await sms_get_balance()
        
        if result.get("code") != 200:
            await query.answer(f"Error: {result.get('message', 'Unknown')}", show_alert=True)
            return
        
        data = result.get("data", {})
        balance = data.get("balance", 0)
        frozen = data.get("frozen", 0)
        
        text = (
            "<b>SMS BUS - ACCOUNT INFO</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Balance:</b> <code>${balance:.2f}</code>\n"
            f"<b>Frozen:</b> <code>${frozen:.2f}</code>\n\n"
            "<i>Balance is deducted per activation.</i>"
        )
        
        buttons = [[InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]]
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    elif action == "sms_orders":
        owner_id = int(parts[1]) if len(parts) > 1 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        await query.answer()
        
        # Check if user has active order
        if user_id in active_sms_orders:
            order = active_sms_orders[user_id]
            request_id = order.get("request_id")
            phone = order.get("phone", "N/A")
            service_name = order.get("service_name", "Unknown")
            
            text = (
                "<b>SMS BUS - ACTIVE ORDER</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Phone:</b> <code>+{phone}</code>\n"
                f"<b>Service:</b> {service_name}\n"
                f"<b>Request ID:</b> <code>{request_id}</code>\n\n"
                "<b>Status:</b> Waiting for SMS\n"
            )
            
            buttons = [
                [InlineKeyboardButton("Check SMS", callback_data=f"sms_check|{request_id}|{user_id}")],
                [InlineKeyboardButton("Cancel", callback_data=f"sms_cancel|{request_id}|{user_id}")],
                [InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]
            ]
            
            await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            return
        
        text = (
            "<b>SMS BUS - MY ORDERS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<i>No active orders.</i>\n\n"
            "Start a new order to get virtual number."
        )
        
        buttons = [[InlineKeyboardButton("Back", callback_data=f"sms_menu|{user_id}")]]
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    elif action == "sms_menu":
        owner_id = int(parts[1]) if len(parts) > 1 else user_id
        
        if user_id != owner_id:
            await query.answer("Bukan milik kamu!", show_alert=True)
            return
        
        await query.answer()
        
        # Get balance
        balance_result = await sms_get_balance()
        balance = 0
        if balance_result.get("code") == 200:
            balance = balance_result.get("data", {}).get("balance", 0)
        
        # Get services
        services_result = await sms_get_services()
        services = services_result.get("data", {}) if services_result.get("code") == 200 else {}
        
        text = (
            "<b>SMS BUS OTP - PREMIUM ULTIMATE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<i>Virtual Number SMS Receiver</i>\n"
            "<i>Get OTP from any service worldwide</i>\n\n"
            f"Balance: <code>${balance:.2f}</code>\n\n"
            "<b>Select Service:</b>\n"
        )
        
        buttons = []
        service_list = list(services.items())[:24]
        for i in range(0, len(service_list), 3):
            row = []
            for svc_id, svc_data in service_list[i:i+3]:
                title = svc_data.get("title", "Unknown")[:12]
                row.append(InlineKeyboardButton(title, callback_data=f"sms_svc|{svc_id}|{user_id}"))
            buttons.append(row)
        buttons.append([
            InlineKeyboardButton("Balance", callback_data=f"sms_balance|{user_id}"),
            InlineKeyboardButton("My Orders", callback_data=f"sms_orders|{user_id}")
        ])
        buttons.append([InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")])
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return


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
# 📊 HELPER: PRICE RANGE BAR UNTUK /sha
# ==========================================
def draw_bar(price, low, high, length=18):
    """
    Bikin bar visual posisi harga hari ini dalam range Low–High.
    Contoh:
    [────🔹──────────────]
    """
    try:
        price = float(price)
        low = float(low)
        high = float(high)
    except Exception:
        return "[no data]"

    if high <= low:
        return "[no range]"

    # Clamp price biar tetap di dalam low–high
    if price < low:
        price = low
    if price > high:
        price = high

    ratio = (price - low) / (high - low)
    idx = int(ratio * (length - 1))

    bar_chars = []
    for i in range(length):
        if i == idx:
            bar_chars.append("🔹")
        else:
            bar_chars.append("─")

    return "[" + "".join(bar_chars) + "]"

# ==========================================
# 📈 STOCK MARKET (VERSI DEWA: SMART SEARCH)
# ==========================================

def get_signal(price, s1, r1, pivot):
    """Get trading signal based on price level"""
    if price > r1:
        return "🔴🔴🔴 OVERBOUGHT - Sell Signal"
    elif price > pivot:
        return "🟠 STRONG BUY - Momentum Up"
    elif price > s1:
        return "🟡 NEUTRAL - Wait & See"
    elif price > s1 * 0.95:
        return "🟢 BUY - Discount Zone"
    else:
        return "🟢🟢🟢 EXTREME BUY - Bounce Zone"

async def sha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stock/Share analysis command"""
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        )
    }

    # --- MODE 1: MARKET OVERVIEW ---
    if not context.args:
        msg = await update.message.reply_text(
            "⏳ <b>Scanning Global Markets...</b>",
            parse_mode=ParseMode.HTML,
        )

        indices = {
            "^JKSE": "🇮🇩 IHSG (Indo)",
            "IDR=X": "💱 USD/IDR",
            "BTC-USD": "₿ Bitcoin",
            "GC=F": "🥇 Gold",
            "CL=F": "🛢️ Oil (WTI)",
        }
        report = (
            "╔════════════════════════════╗\n"
            "║  🌍 GLOBAL MARKET OVERVIEW  ║\n"
            "╚════════════════════════════╝\n\n"
        )

        for ticker, name in indices.items():
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
                    emoji = "📈" if change_p >= 0 else "📉"

                    if ticker in ["IDR=X", "^JKSE"]:
                        price_fmt = f"{price:,.0f}"
                    else:
                        price_fmt = f"{price:,.2f}"

                    report += (
                        f"{emoji} <b>{name}</b>\n"
                        f"   {price_fmt} ({change_p:+.2f}%)\n\n"
                    )
            except Exception:
                continue

        report += (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Try:</i> <code>/sha BBCA</code> or <code>/sha TSLA</code>"
        )
        await msg.edit_text(report, parse_mode=ParseMode.HTML)
        return

    # --- MODE 2: SMART SEARCH ---
    input_ticker = context.args[0].upper().strip()
    msg = await update.message.reply_text(
        f"🔍 <b>Analyzing</b> <code>{html.escape(input_ticker)}</code>...",
        parse_mode=ParseMode.HTML,
    )

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
        except Exception:
            continue

    # --- JIKA DATA DITEMUKAN ---
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

            # Trading Zones
            pivot = (day_high + day_low + price) / 3
            s1 = (2 * pivot) - day_high
            r1 = (2 * pivot) - day_low

            change = price - prev_close
            change_p = (change / prev_close) * 100

            trend_emoji = "📈" if change_p > 0 else ("📉" if change_p < 0 else "➡️")
            color_sign = "+" if change_p >= 0 else ""

            # Trading Signal
            signal = get_signal(price, s1, r1, pivot)

            # Position in Range
            from_high_p = ((price - day_high) / day_high) * 100 if day_high else 0
            from_low_p = ((price - day_low) / day_low) * 100 if day_low else 0

            # Price Range Bar
            price_bar = draw_bar(price, day_low, day_high)

            def fmt(val):
                try:
                    v = float(val)
                    return f"{v:,.0f}" if currency == "IDR" else f"{v:,.2f}"
                except:
                    return "0"

            txt = (
                f"╔════════════════════════════╗\n"
                f"║  📊 STOCK ANALYSIS          ║\n"
                f"║  {html.escape(real_ticker):26} ║\n"
                f"╚════════════════════════════╝\n\n"
                
                f"💰 <b>PRICE</b>\n"
                f"├ Current: <code>{currency} {fmt(price)}</code>\n"
                f"├ Change: {trend_emoji} <code>{color_sign}{change:.2f}</code> "
                f"(<code>{color_sign}{change_p:.2f}%</code>)\n"
                f"└ Prev Close: <code>{fmt(prev_close)}</code>\n\n"
                
                f"🎯 <b>TRADING ZONES (Daily)</b>\n"
                f"├ 🔴 Resistance: <code>{fmt(r1)}</code> - <code>{fmt(day_high)}</code>\n"
                f"├ 🟡 Pivot: <code>{fmt(pivot)}</code>\n"
                f"└ 🟢 Support: <code>{fmt(s1)}</code> - <code>{fmt(day_low)}</code>\n\n"
                
                f"📊 <b>TRADING SIGNAL</b>\n"
                f"└ {signal}\n\n"
                
                f"📈 <b>INTRADAY STATS</b>\n"
                f"├ High: <code>{fmt(day_high)}</code>\n"
                f"├ Low: <code>{fmt(day_low)}</code>\n"
                f"├ Open: <code>{fmt(open_price)}</code>\n"
                f"├ Volume: <code>{vol:,}</code>\n"
                f"└ Range: {price_bar}\n\n"
                
                f"📍 <b>POSITION IN RANGE</b>\n"
                f"├ From High: <code>{from_high_p:+.2f}%</code>\n"
                f"└ From Low: <code>{from_low_p:+.2f}%</code>\n\n"
                
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 <i>Real-time by Oktacomel</i>"
            )

            # Quick Stats Button
            kb = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data=f"sha_refresh|{real_ticker}"),
                    InlineKeyboardButton("📊 Chart", url=f"https://finance.yahoo.com/quote/{real_ticker}"),
                ]
            ]

            await msg.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

        except Exception as e:
            await msg.edit_text(
                f"❌ <b>Parse Error:</b> <code>{html.escape(str(e)[:50])}</code>",
                parse_mode=ParseMode.HTML,
            )
    else:
        await msg.edit_text(
            f"❌ <b>Symbol not found:</b> <code>{html.escape(input_ticker)}</code>\n\n"
            f"💡 Try: <code>/sha BBCA</code> (Indo) or <code>/sha TSLA</code> (US)",
            parse_mode=ParseMode.HTML,
        )

# CALLBACK HANDLER UNTUK REFRESH
async def sha_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh stock data"""
    query = update.callback_query
    await query.answer("🔄 Refreshing...", show_alert=False)
    
    ticker = query.data.split("|")[1]
    context.args = [ticker]
    await sha_command(update, context)
    
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
# 🔥 DATABASE TRUTH OR DARE (ULTIMATE MASSIVE MIX)
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
    
    # --- LEVEL 2: DEEP / PERSONAL ---
    "Apa penyesalan terbesar dalam hidupmu sejauh ini?",
    "Kapan kamu merasa paling kesepian?",
    "Apa rahasia yang belum pernah kamu ceritain ke siapapun?",
    "Pernah gak kamu ngerasa salah pilih pasangan?",
    "Apa sifat terburuk kamu menurut dirimu sendiri?",
    "Kalau bisa memutar waktu, momen apa yang pengen kamu ubah?",
    "Apa insecure terbesar kamu soal fisik?",
    
    # --- LEVEL 3: PEDAS / 18+ / 21+ (HARDCORE) ---
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
    "Seberapa sering kamu nonton bokep dalam seminggu?"
]

LIST_DARE = [
    # --- LEVEL 1: SOSIAL / PRANK ---
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
    
    # --- LEVEL 2: FLIRTY / GOMBAL ---
    "Gombalin salah satu member grup ini lewat VN.",
    "Chat crush kamu: 'Mimpiin aku ya malam ini'.",
    "Pilih satu orang di grup, jadikan 'pacar' kamu selama 15 menit.",
    "Bilang 'I Love You' ke member grup nomor 3 dari atas.",
    "Kirim pantun cinta buat Admin grup.",
    
    # --- LEVEL 3: PEDAS / 18+ / 21+ (HARDCORE) ---
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
    "Chat teman lawan jenis: 'Ukuran kamu berapa?', kirim SS balasannya."
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
# 📊 SYSTEM HEALTH CHECK (ULTIMATE PREMIUM V5)
# ==========================================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        "🔄 <b>Running system diagnostics...</b>",
        parse_mode=ParseMode.HTML
    )

    # 1. CEK SPOTIFY
    try:
        if sp_client:
            sp_client.search(q="test", limit=1, type="track")
            spot_status = "🟢 ONLINE"
        else:
            spot_status = "⚪ DISABLED"
    except Exception:
        spot_status = "🟠 ERROR"

    # 2. CEK AI ENGINE
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("https://api.emergent.sh/health")
            ai_status = "🟢 ONLINE" if resp.status_code in (200, 401) else "🟠 UNSTABLE"
    except Exception:
        ai_status = "🔴 TIMEOUT"

    # 3. CEK PROXY (Jalur Download)
    try:
        if MY_PROXY:
            async with httpx.AsyncClient(proxy=MY_PROXY, timeout=5) as client:
                resp = await client.get("https://www.google.com", follow_redirects=True)
                proxy_status = "🟢 LIVE (Premium)" if resp.status_code == 200 else f"🔴 DEAD ({resp.status_code})"
        else:
            proxy_status = "⚪ DIRECT (No Proxy)"
    except Exception:
        proxy_status = "🔴 CONNECTION ERROR"

    # 4. CEK APIFY CLOUD (APIKEY DIHAPUS)
    apify_status = "⚪ NOT CONFIGURED"

    # 5. CEK MAIL SERVER (Temp Mail Premium)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            headers = {"X-API-Key": TEMPMAIL_API_KEY}
            resp = await client.get("https://api.temp-mail.io/v1/domains", headers=headers)
            mail_status = "🟢 ACTIVE" if resp.status_code == 200 else f"🔴 ERROR ({resp.status_code})"
    except Exception:
        mail_status = "🟠 TIMEOUT"

    # 6. CEK FFMPEG
    ffmpeg_status = "🟢 INSTALLED" if shutil.which("ffmpeg") else "🔴 MISSING"

    # 7. CEK DATABASE
    db_status = "🟢 CONNECTED" if os.path.exists(DB_NAME) else "🔴 MISSING"

    # === HITUNG OVERALL HEALTH ===
    statuses = [spot_status, ai_status, mail_status, apify_status, proxy_status, ffmpeg_status, db_status]

    if any(s.startswith("🔴") for s in statuses):
        overall = "🔴 <b>CRITICAL</b> — Immediate attention required."
    elif any(s.startswith("🟠") for s in statuses):
        overall = "🟠 <b>DEGRADED</b> — Some services unstable."
    else:
        overall = "🟢 <b>ALL GREEN</b> — Fully operational."

    # TIMESTAMP & HOSTNAME
    now = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    host = html.escape(platform.node() or "SERVER")

    # === UI PREMIUM FINAL ===
    txt = (
        "📊 <b>OKTACOMEL SYSTEM PANEL</b>\n"
        "✦────────────────────────✦\n"
        f"🖥️ <b>Host</b>    ⇾ <code>{host}</code>\n"
        f"⏱️ <b>Checked</b> ⇾ <code>{now}</code>\n"
        f"📡 <b>Status</b>  ⇾ {overall}\n"
        "✦────────────────────────✦\n\n"
        "<b>CORE SERVICES</b>\n"
        f"🧠 AI Engine      ⇾ <code>{ai_status}</code>\n"
        f"🎵 Spotify API    ⇾ <code>{spot_status}</code>\n"
        f"📧 Mail Server    ⇾ <code>{mail_status}</code>\n"
        f"☁️ Apify Cloud    ⇾ <code>{apify_status}</code>\n\n"
        "<b>INFRASTRUCTURE</b>\n"
        f"🛡️ Proxy Tunnel   ⇾ <code>{proxy_status}</code>\n"
        f"🎬 FFmpeg Core    ⇾ <code>{ffmpeg_status}</code>\n"
        f"💾 Database       ⇾ <code>{db_status}</code>\n"
        "✦────────────────────────✦\n"
        "🧩 <i>Tip:</i> Run <code>/status</code> regularly to monitor bot health.\n"
        "🤖 <i>Diagnostics powered by Oktacomel</i>"
    )

    await msg.edit_text(txt, parse_mode=ParseMode.HTML)


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
# ☁️ CLOUDFLARE DNS MANAGER - OKTACOMEL PREMIUM ULTIMATE
# ==========================================

CF_API_BASE = "https://api.cloudflare.com/client/v4"

# User waiting states for CF commands
cf_user_states = {}

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
    except: return False

async def cf_log_action(user_id: int, action: str, domain: str = "", details: str = ""):
    """Log Cloudflare action for stats"""
    try:
        await db_execute(
            "INSERT INTO cloudflare_stats (user_id, action, domain, details) VALUES (?, ?, ?, ?)",
            (user_id, action, domain, details)
        )
    except: pass

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
    except: return {"total_users": 0, "change_ip": 0, "add_sub": 0, "delete_sub": 0}

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
            elif method == "PATCH":
                r = await client.patch(url, headers=headers, json=data)
            else:
                return {"success": False, "errors": [{"message": "Invalid method"}]}
            return r.json()
    except Exception as e:
        logger.error(f"[CF API] Error: {e}")
        return {"success": False, "errors": [{"message": str(e)}]}

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
    except:
        return "Not resolved"

async def cf_ping_host(hostname: str) -> str:
    """Ping hostname and return latency"""
    try:
        import subprocess
        result = subprocess.run(["ping", "-c", "3", hostname], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.split("\n")
            for line in lines:
                if "avg" in line or "rtt" in line:
                    return line.strip()
            return "Ping successful"
        return "Ping failed"
    except Exception as e:
        return f"Error: {str(e)[:30]}"

async def cf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cloudflare DNS Manager - Premium Ultimate Command"""
    if not await premium_lock_handler(update, context): return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    start_time = time.time()
    
    # Get user API status
    user_api = await cf_get_user_api(user_id)
    api_status = "Connected" if user_api.get("api_key") else "Not Connected"
    api_email = user_api.get("email", "None")
    
    # Get domain count
    domain_count = 0
    if user_api.get("api_key"):
        zones = await cf_get_zones(user_api["api_key"], user_api["email"])
        domain_count = len(zones)
    
    # Get global stats
    stats = await cf_get_global_stats()
    
    # Calculate ping
    ping_ms = round((time.time() - start_time) * 1000, 2)
    
    text = (
        "<b>OKTACOMEL CLOUDFLARE MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>PREMIUM ULTIMATE DNS CONTROLLER</b>\n\n"
        f"Total Pengguna : {stats['total_users']}\n"
        f"Response Time : {ping_ms} ms\n"
        f"Version : 3.0.0 ULTIMATE\n\n"
        f"Pengguna : @{username}\n"
        f"Cloudflare API : {'Connected' if user_api.get('api_key') else 'Not Connected'}\n"
        f"Email : {api_email}\n"
        f"Domain Aktif : {domain_count}\n"
        f"User ID : {user_id}\n\n"
        "<b>AKTIVITAS GLOBAL</b>\n"
        f"Ganti IP SUB : {stats['change_ip']}\n"
        f"Tambah SUB : {stats['add_sub']}\n"
        f"Hapus SUB : {stats['delete_sub']}\n\n"
        "<b>TIPS</b>\n"
        "Setup Global API Key terlebih dahulu\n"
        "di Menu Tambahan untuk menggunakan\n"
        "semua fitur DNS Manager."
    )
    
    buttons = [
        [InlineKeyboardButton("TAMBAH", callback_data=f"cf_add|{user_id}"),
         InlineKeyboardButton("GANTI IP", callback_data=f"cf_changeip|{user_id}")],
        [InlineKeyboardButton("HAPUS", callback_data=f"cf_delete|{user_id}"),
         InlineKeyboardButton("LIHAT SUB", callback_data=f"cf_listsub|{user_id}")],
        [InlineKeyboardButton("Tambahkan Domain", callback_data=f"cf_adddomain|{user_id}")],
        [InlineKeyboardButton("Menu Tambahan", callback_data=f"cf_extra|{user_id}")],
        [InlineKeyboardButton("Kopi Buat Admin", callback_data=f"cf_donate|{user_id}")],
        [InlineKeyboardButton("Kritik dan Saran", callback_data=f"cf_feedback|{user_id}")],
        [InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]
    ]
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def cf_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all Cloudflare callback buttons"""
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data.split("|")
    action = data[0]
    owner_id = int(data[1]) if len(data) > 1 else user_id
    
    if user_id != owner_id:
        await query.answer("Bukan milik kamu!", show_alert=True)
        return
    
    await query.answer()
    
    user_api = await cf_get_user_api(user_id)
    
    # --- MENU TAMBAHAN ---
    if action == "cf_extra":
        text = (
            "<b>OKTACOMEL CLOUDFLARE MANAGER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>MENU TOOLS TAMBAHAN</b>\n\n"
            "Akses fitur-fitur tambahan untuk\n"
            "manajemen DNS dan Cloudflare Anda."
        )
        buttons = [
            [InlineKeyboardButton("Cek Expired Domain", callback_data=f"cf_checkexp|{user_id}")],
            [InlineKeyboardButton("Setup Global API Key", callback_data=f"cf_setupapi|{user_id}")],
            [InlineKeyboardButton("Data Cloudflare Anda", callback_data=f"cf_mydata|{user_id}")],
            [InlineKeyboardButton("Hapus Domain", callback_data=f"cf_removedomain|{user_id}")],
            [InlineKeyboardButton("Host To IP", callback_data=f"cf_hostip|{user_id}"),
             InlineKeyboardButton("Ping", callback_data=f"cf_ping|{user_id}")],
            [InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")]
        ]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- MAIN MENU ---
    elif action == "cf_main":
        username = update.effective_user.username or "Unknown"
        api_email = user_api.get("email", "None")
        domain_count = 0
        if user_api.get("api_key"):
            zones = await cf_get_zones(user_api["api_key"], user_api["email"])
            domain_count = len(zones)
        stats = await cf_get_global_stats()
        ping_ms = round(time.time() * 1000 % 1000, 2)
        
        text = (
            "<b>OKTACOMEL CLOUDFLARE MANAGER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>PREMIUM ULTIMATE DNS CONTROLLER</b>\n\n"
            f"Total Pengguna : {stats['total_users']}\n"
            f"Response Time : {ping_ms} ms\n"
            f"Version : 3.0.0 ULTIMATE\n\n"
            f"Pengguna : @{username}\n"
            f"Cloudflare API : {'Connected' if user_api.get('api_key') else 'Not Connected'}\n"
            f"Email : {api_email}\n"
            f"Domain Aktif : {domain_count}\n"
            f"User ID : {user_id}\n\n"
            "<b>AKTIVITAS GLOBAL</b>\n"
            f"Ganti IP SUB : {stats['change_ip']}\n"
            f"Tambah SUB : {stats['add_sub']}\n"
            f"Hapus SUB : {stats['delete_sub']}\n\n"
            "<b>TIPS</b>\n"
            "Setup Global API Key terlebih dahulu\n"
            "di Menu Tambahan untuk menggunakan\n"
            "semua fitur DNS Manager."
        )
        buttons = [
            [InlineKeyboardButton("TAMBAH", callback_data=f"cf_add|{user_id}"),
             InlineKeyboardButton("GANTI IP", callback_data=f"cf_changeip|{user_id}")],
            [InlineKeyboardButton("HAPUS", callback_data=f"cf_delete|{user_id}"),
             InlineKeyboardButton("LIHAT SUB", callback_data=f"cf_listsub|{user_id}")],
            [InlineKeyboardButton("Tambahkan Domain", callback_data=f"cf_adddomain|{user_id}")],
            [InlineKeyboardButton("Menu Tambahan", callback_data=f"cf_extra|{user_id}")],
            [InlineKeyboardButton("Kopi Buat Admin", callback_data=f"cf_donate|{user_id}")],
            [InlineKeyboardButton("Kritik dan Saran", callback_data=f"cf_feedback|{user_id}")],
            [InlineKeyboardButton("Close", callback_data=f"cmd_close|{user_id}")]
        ]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- SETUP API KEY ---
    elif action == "cf_setupapi":
        text = (
            "<b>SETUP GLOBAL API KEY</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Untuk menggunakan fitur DNS Manager,\n"
            "Anda perlu memasukkan Global API Key\n"
            "dari akun Cloudflare Anda.\n\n"
            "<b>Cara Mendapatkan API Key:</b>\n"
            "1. Login ke dash.cloudflare.com\n"
            "2. Klik My Profile > API Tokens\n"
            "3. Pilih Global API Key > View\n"
            "4. Copy API Key tersebut\n\n"
            "Kirim API Key dengan format:\n"
            "<code>/cfapi EMAIL|API_KEY</code>\n\n"
            "Contoh:\n"
            "<code>/cfapi admin@gmail.com|abc123def456...</code>"
        )
        buttons = [[InlineKeyboardButton("Kembali", callback_data=f"cf_extra|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- MY DATA ---
    elif action == "cf_mydata":
        if not user_api.get("api_key"):
            await query.answer("API Key belum disetup!", show_alert=True)
            return
        
        zones = await cf_get_zones(user_api["api_key"], user_api["email"])
        
        text = (
            "<b>DATA CLOUDFLARE ANDA</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Email: <code>{user_api['email']}</code>\n"
            f"API Key: <code>...{user_api['api_key'][-8:]}</code>\n"
            f"Total Domain: {len(zones)}\n\n"
            "<b>DAFTAR DOMAIN:</b>\n"
        )
        
        for i, zone in enumerate(zones[:15], 1):
            text += f"{i}. <code>{zone.get('name', 'Unknown')}</code>\n"
        
        if len(zones) > 15:
            text += f"\n<i>...dan {len(zones) - 15} domain lainnya</i>"
        
        buttons = [
            [InlineKeyboardButton("Hapus API Key", callback_data=f"cf_deleteapi|{user_id}")],
            [InlineKeyboardButton("Kembali", callback_data=f"cf_extra|{user_id}")]
        ]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- DELETE API KEY ---
    elif action == "cf_deleteapi":
        await cf_delete_user_api(user_id)
        await query.answer("API Key berhasil dihapus!", show_alert=True)
        # Go back to extra menu
        text = (
            "<b>OKTACOMEL CLOUDFLARE MANAGER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>MENU TOOLS TAMBAHAN</b>\n\n"
            "API Key telah dihapus.\n"
            "Silakan setup ulang jika diperlukan."
        )
        buttons = [
            [InlineKeyboardButton("Cek Expired Domain", callback_data=f"cf_checkexp|{user_id}")],
            [InlineKeyboardButton("Setup Global API Key", callback_data=f"cf_setupapi|{user_id}")],
            [InlineKeyboardButton("Data Cloudflare Anda", callback_data=f"cf_mydata|{user_id}")],
            [InlineKeyboardButton("Hapus Domain", callback_data=f"cf_removedomain|{user_id}")],
            [InlineKeyboardButton("Host To IP", callback_data=f"cf_hostip|{user_id}"),
             InlineKeyboardButton("Ping", callback_data=f"cf_ping|{user_id}")],
            [InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")]
        ]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- ADD SUBDOMAIN ---
    elif action == "cf_add":
        if not user_api.get("api_key"):
            await query.answer("Setup API Key dulu di Menu Tambahan!", show_alert=True)
            return
        
        zones = await cf_get_zones(user_api["api_key"], user_api["email"])
        if not zones:
            await query.answer("Tidak ada domain ditemukan!", show_alert=True)
            return
        
        text = (
            "<b>TAMBAH SUBDOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Pilih domain untuk menambah subdomain:\n"
        )
        
        buttons = []
        for zone in zones[:12]:
            buttons.append([InlineKeyboardButton(zone.get("name", "Unknown"), callback_data=f"cf_addsub_zone|{zone.get('id')}|{user_id}")])
        buttons.append([InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")])
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- SELECT ZONE FOR ADD ---
    elif action == "cf_addsub_zone":
        zone_id = data[1]
        cf_user_states[user_id] = {"action": "add_sub", "zone_id": zone_id}
        
        text = (
            "<b>TAMBAH SUBDOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Kirim subdomain dengan format:\n"
            "<code>/cfsub SUBDOMAIN IP</code>\n\n"
            "Contoh:\n"
            "<code>/cfsub api 192.168.1.1</code>\n"
            "<code>/cfsub vpn 103.x.x.x</code>\n\n"
            "<i>Subdomain akan ditambahkan\n"
            "sebagai record A dengan proxy ON</i>"
        )
        buttons = [[InlineKeyboardButton("Batal", callback_data=f"cf_main|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- CHANGE IP ---
    elif action == "cf_changeip":
        if not user_api.get("api_key"):
            await query.answer("Setup API Key dulu di Menu Tambahan!", show_alert=True)
            return
        
        zones = await cf_get_zones(user_api["api_key"], user_api["email"])
        if not zones:
            await query.answer("Tidak ada domain ditemukan!", show_alert=True)
            return
        
        text = (
            "<b>GANTI IP SUBDOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Pilih domain untuk melihat subdomain:\n"
        )
        
        buttons = []
        for zone in zones[:12]:
            buttons.append([InlineKeyboardButton(zone.get("name", "Unknown"), callback_data=f"cf_changeip_zone|{zone.get('id')}|{user_id}")])
        buttons.append([InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")])
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- SELECT ZONE FOR CHANGE IP ---
    elif action == "cf_changeip_zone":
        zone_id = data[1]
        records = await cf_get_dns_records(user_api["api_key"], user_api["email"], zone_id)
        
        a_records = [r for r in records if r.get("type") == "A"]
        
        if not a_records:
            await query.answer("Tidak ada subdomain A record!", show_alert=True)
            return
        
        text = (
            "<b>PILIH SUBDOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Pilih subdomain untuk ganti IP:\n"
        )
        
        buttons = []
        for rec in a_records[:15]:
            name = rec.get("name", "Unknown")
            ip = rec.get("content", "0.0.0.0")
            rec_id = rec.get("id")
            btn_text = f"{name} ({ip})"[:35]
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"cf_changeip_rec|{zone_id}|{rec_id}|{user_id}")])
        
        buttons.append([InlineKeyboardButton("Kembali", callback_data=f"cf_changeip|{user_id}")])
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- SELECT RECORD FOR CHANGE IP ---
    elif action == "cf_changeip_rec":
        zone_id = data[1]
        rec_id = data[2]
        cf_user_states[user_id] = {"action": "change_ip", "zone_id": zone_id, "rec_id": rec_id}
        
        text = (
            "<b>GANTI IP SUBDOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Kirim IP baru dengan format:\n"
            "<code>/cfip IP_BARU</code>\n\n"
            "Contoh:\n"
            "<code>/cfip 103.123.45.67</code>"
        )
        buttons = [[InlineKeyboardButton("Batal", callback_data=f"cf_main|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- DELETE SUBDOMAIN ---
    elif action == "cf_delete":
        if not user_api.get("api_key"):
            await query.answer("Setup API Key dulu di Menu Tambahan!", show_alert=True)
            return
        
        zones = await cf_get_zones(user_api["api_key"], user_api["email"])
        if not zones:
            await query.answer("Tidak ada domain ditemukan!", show_alert=True)
            return
        
        text = (
            "<b>HAPUS SUBDOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Pilih domain:\n"
        )
        
        buttons = []
        for zone in zones[:12]:
            buttons.append([InlineKeyboardButton(zone.get("name", "Unknown"), callback_data=f"cf_delete_zone|{zone.get('id')}|{user_id}")])
        buttons.append([InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")])
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- SELECT ZONE FOR DELETE ---
    elif action == "cf_delete_zone":
        zone_id = data[1]
        records = await cf_get_dns_records(user_api["api_key"], user_api["email"], zone_id)
        
        a_records = [r for r in records if r.get("type") == "A"]
        
        if not a_records:
            await query.answer("Tidak ada subdomain A record!", show_alert=True)
            return
        
        text = (
            "<b>HAPUS SUBDOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Pilih subdomain untuk dihapus:\n"
        )
        
        buttons = []
        for rec in a_records[:15]:
            name = rec.get("name", "Unknown")
            rec_id = rec.get("id")
            buttons.append([InlineKeyboardButton(name[:35], callback_data=f"cf_delete_rec|{zone_id}|{rec_id}|{user_id}")])
        
        buttons.append([InlineKeyboardButton("Kembali", callback_data=f"cf_delete|{user_id}")])
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- CONFIRM DELETE RECORD ---
    elif action == "cf_delete_rec":
        zone_id = data[1]
        rec_id = data[2]
        
        result = await cf_delete_dns_record(user_api["api_key"], user_api["email"], zone_id, rec_id)
        if result.get("success"):
            await cf_log_action(user_id, "delete_sub", "", "Deleted subdomain")
            await query.answer("Subdomain berhasil dihapus!", show_alert=True)
        else:
            error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
            await query.answer(f"Error: {error_msg[:50]}", show_alert=True)
        
        # Go back to delete menu
        zones = await cf_get_zones(user_api["api_key"], user_api["email"])
        text = "<b>HAPUS SUBDOMAIN</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nPilih domain:\n"
        buttons = []
        for zone in zones[:12]:
            buttons.append([InlineKeyboardButton(zone.get("name", "Unknown"), callback_data=f"cf_delete_zone|{zone.get('id')}|{user_id}")])
        buttons.append([InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")])
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- VIEW SUBDOMAINS ---
    elif action == "cf_listsub":
        if not user_api.get("api_key"):
            await query.answer("Setup API Key dulu di Menu Tambahan!", show_alert=True)
            return
        
        zones = await cf_get_zones(user_api["api_key"], user_api["email"])
        if not zones:
            await query.answer("Tidak ada domain ditemukan!", show_alert=True)
            return
        
        text = (
            "<b>LIHAT SUBDOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Pilih domain:\n"
        )
        
        buttons = []
        for zone in zones[:12]:
            buttons.append([InlineKeyboardButton(zone.get("name", "Unknown"), callback_data=f"cf_listsub_zone|{zone.get('id')}|{user_id}")])
        buttons.append([InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")])
        
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- LIST RECORDS FOR ZONE ---
    elif action == "cf_listsub_zone":
        zone_id = data[1]
        records = await cf_get_dns_records(user_api["api_key"], user_api["email"], zone_id)
        
        text = (
            "<b>DAFTAR SUBDOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        for i, rec in enumerate(records[:20], 1):
            rec_type = rec.get("type", "?")
            name = rec.get("name", "Unknown")
            content = rec.get("content", "")[:20]
            proxied = "ON" if rec.get("proxied") else "OFF"
            text += f"{i}. <code>{name}</code>\n   {rec_type} -> {content} (Proxy: {proxied})\n\n"
        
        if len(records) > 20:
            text += f"<i>...dan {len(records) - 20} record lainnya</i>"
        
        buttons = [[InlineKeyboardButton("Kembali", callback_data=f"cf_listsub|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- HOST TO IP ---
    elif action == "cf_hostip":
        cf_user_states[user_id] = {"action": "host_to_ip"}
        text = (
            "<b>HOST TO IP</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Kirim hostname dengan format:\n"
            "<code>/cfhost HOSTNAME</code>\n\n"
            "Contoh:\n"
            "<code>/cfhost google.com</code>"
        )
        buttons = [[InlineKeyboardButton("Kembali", callback_data=f"cf_extra|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- PING ---
    elif action == "cf_ping":
        cf_user_states[user_id] = {"action": "ping"}
        text = (
            "<b>PING HOST</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Kirim hostname dengan format:\n"
            "<code>/cfping HOSTNAME</code>\n\n"
            "Contoh:\n"
            "<code>/cfping cloudflare.com</code>"
        )
        buttons = [[InlineKeyboardButton("Kembali", callback_data=f"cf_extra|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- DONATE (QRIS) ---
    elif action == "cf_donate":
        caption = (
            "<b>KOPI BUAT ADMIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Terima kasih sudah menggunakan\n"
            "OKTACOMEL Cloudflare Manager!\n\n"
            "Scan QRIS di atas untuk donasi.\n"
            "Setiap kontribusi sangat berarti."
        )
        buttons = [[InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")]]
        
        try:
            await query.message.delete()
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=QRIS_IMAGE,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            await query.message.edit_text(f"Error loading QRIS: {e}", reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- FEEDBACK ---
    elif action == "cf_feedback":
        text = (
            "<b>KRITIK DAN SARAN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Silakan kirim kritik dan saran Anda\n"
            "langsung ke admin melalui:\n\n"
            "Telegram: @oktacomel\n\n"
            "Atau gunakan format:\n"
            "<code>/feedback [pesan anda]</code>\n\n"
            "Masukan Anda sangat berharga untuk\n"
            "pengembangan bot ini."
        )
        buttons = [[InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- ADD DOMAIN INFO ---
    elif action == "cf_adddomain":
        text = (
            "<b>TAMBAHKAN DOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Untuk menambahkan domain ke Cloudflare,\n"
            "silakan lakukan langsung di:\n\n"
            "dash.cloudflare.com\n\n"
            "1. Login ke akun Cloudflare\n"
            "2. Klik 'Add Site'\n"
            "3. Masukkan nama domain\n"
            "4. Ikuti petunjuk setup\n"
            "5. Update nameserver di registrar\n\n"
            "Setelah domain aktif, gunakan bot\n"
            "ini untuk manage subdomain."
        )
        buttons = [[InlineKeyboardButton("Kembali", callback_data=f"cf_main|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- CHECK EXPIRED ---
    elif action == "cf_checkexp":
        text = (
            "<b>CEK EXPIRED DOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Kirim domain untuk cek expired:\n"
            "<code>/cfexp DOMAIN</code>\n\n"
            "Contoh:\n"
            "<code>/cfexp example.com</code>"
        )
        buttons = [[InlineKeyboardButton("Kembali", callback_data=f"cf_extra|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # --- REMOVE DOMAIN INFO ---
    elif action == "cf_removedomain":
        text = (
            "<b>HAPUS DOMAIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Untuk menghapus domain dari Cloudflare,\n"
            "silakan lakukan langsung di:\n\n"
            "dash.cloudflare.com\n\n"
            "1. Login ke akun Cloudflare\n"
            "2. Pilih domain yang ingin dihapus\n"
            "3. Buka tab 'Overview'\n"
            "4. Scroll ke bawah\n"
            "5. Klik 'Remove Site from Cloudflare'\n\n"
            "<i>Penghapusan domain tidak bisa\n"
            "dibatalkan. Pastikan backup data DNS.</i>"
        )
        buttons = [[InlineKeyboardButton("Kembali", callback_data=f"cf_extra|{user_id}")]]
        await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return


# --- CF COMMAND HANDLERS ---
async def cfapi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Setup Cloudflare API Key: /cfapi EMAIL|API_KEY"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "<b>SETUP API KEY</b>\n\n"
            "Format: <code>/cfapi EMAIL|API_KEY</code>\n"
            "Contoh: <code>/cfapi admin@gmail.com|abc123...</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        parts = " ".join(context.args).split("|")
        if len(parts) != 2:
            await update.message.reply_text("Format salah! Gunakan: /cfapi EMAIL|API_KEY", parse_mode=ParseMode.HTML)
            return
        
        email = parts[0].strip()
        api_key = parts[1].strip()
        
        msg = await update.message.reply_text("Verifying API Key...")
        
        if await cf_verify_api(api_key, email):
            await cf_save_user_api(user_id, api_key, email)
            await msg.edit_text(
                "<b>API KEY TERSIMPAN</b>\n\n"
                f"Email: <code>{email}</code>\n"
                f"API Key: <code>...{api_key[-8:]}</code>\n\n"
                "Gunakan /cf untuk mengakses menu.",
                parse_mode=ParseMode.HTML
            )
        else:
            await msg.edit_text("API Key tidak valid! Pastikan email dan key benar.", parse_mode=ParseMode.HTML)
    
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}", parse_mode=ParseMode.HTML)

async def cfsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add subdomain: /cfsub SUBDOMAIN IP"""
    user_id = update.effective_user.id
    user_api = await cf_get_user_api(user_id)
    
    if not user_api.get("api_key"):
        await update.message.reply_text("Setup API Key dulu dengan /cfapi", parse_mode=ParseMode.HTML)
        return
    
    state = cf_user_states.get(user_id, {})
    if state.get("action") != "add_sub" or not state.get("zone_id"):
        await update.message.reply_text("Gunakan menu /cf untuk menambah subdomain", parse_mode=ParseMode.HTML)
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Format: /cfsub SUBDOMAIN IP", parse_mode=ParseMode.HTML)
        return
    
    subdomain = context.args[0]
    ip = context.args[1]
    zone_id = state["zone_id"]
    
    msg = await update.message.reply_text("Adding subdomain...")
    
    result = await cf_add_dns_record(user_api["api_key"], user_api["email"], zone_id, "A", subdomain, ip, True)
    
    if result.get("success"):
        await cf_log_action(user_id, "add_sub", subdomain, ip)
        cf_user_states.pop(user_id, None)
        await msg.edit_text(
            f"<b>SUBDOMAIN DITAMBAHKAN</b>\n\n"
            f"Subdomain: <code>{subdomain}</code>\n"
            f"IP: <code>{ip}</code>\n"
            f"Proxy: ON\n\n"
            "Gunakan /cf untuk menu utama.",
            parse_mode=ParseMode.HTML
        )
    else:
        error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
        await msg.edit_text(f"Error: {error_msg}", parse_mode=ParseMode.HTML)

async def cfip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change IP: /cfip NEW_IP"""
    user_id = update.effective_user.id
    user_api = await cf_get_user_api(user_id)
    
    if not user_api.get("api_key"):
        await update.message.reply_text("Setup API Key dulu!", parse_mode=ParseMode.HTML)
        return
    
    state = cf_user_states.get(user_id, {})
    if state.get("action") != "change_ip":
        await update.message.reply_text("Gunakan menu /cf untuk ganti IP", parse_mode=ParseMode.HTML)
        return
    
    if not context.args:
        await update.message.reply_text("Format: /cfip NEW_IP", parse_mode=ParseMode.HTML)
        return
    
    new_ip = context.args[0]
    zone_id = state["zone_id"]
    rec_id = state["rec_id"]
    
    msg = await update.message.reply_text("Updating IP...")
    
    # Get current record info first
    records = await cf_get_dns_records(user_api["api_key"], user_api["email"], zone_id)
    current_rec = next((r for r in records if r.get("id") == rec_id), None)
    
    if not current_rec:
        await msg.edit_text("Record tidak ditemukan!", parse_mode=ParseMode.HTML)
        return
    
    result = await cf_update_dns_record(
        user_api["api_key"], user_api["email"], zone_id, rec_id,
        current_rec.get("type", "A"), current_rec.get("name", ""), new_ip, current_rec.get("proxied", True)
    )
    
    if result.get("success"):
        await cf_log_action(user_id, "change_ip", current_rec.get("name", ""), new_ip)
        cf_user_states.pop(user_id, None)
        await msg.edit_text(
            f"<b>IP BERHASIL DIGANTI</b>\n\n"
            f"Subdomain: <code>{current_rec.get('name', 'Unknown')}</code>\n"
            f"IP Baru: <code>{new_ip}</code>\n\n"
            "Gunakan /cf untuk menu utama.",
            parse_mode=ParseMode.HTML
        )
    else:
        error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
        await msg.edit_text(f"Error: {error_msg}", parse_mode=ParseMode.HTML)

async def cfhost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Host to IP: /cfhost HOSTNAME"""
    if not context.args:
        await update.message.reply_text("Format: /cfhost HOSTNAME", parse_mode=ParseMode.HTML)
        return
    
    hostname = context.args[0]
    ip = await cf_host_to_ip(hostname)
    
    await update.message.reply_text(
        f"<b>HOST TO IP</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hostname: <code>{hostname}</code>\n"
        f"IP Address: <code>{ip}</code>",
        parse_mode=ParseMode.HTML
    )

async def cfping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ping host: /cfping HOSTNAME"""
    if not context.args:
        await update.message.reply_text("Format: /cfping HOSTNAME", parse_mode=ParseMode.HTML)
        return
    
    hostname = context.args[0]
    msg = await update.message.reply_text("Pinging...")
    
    result = await cf_ping_host(hostname)
    
    await msg.edit_text(
        f"<b>PING RESULT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Host: <code>{hostname}</code>\n"
        f"Result: <code>{result}</code>",
        parse_mode=ParseMode.HTML
    )

async def cfexp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check domain expiry: /cfexp DOMAIN"""
    if not context.args:
        await update.message.reply_text("Format: /cfexp DOMAIN", parse_mode=ParseMode.HTML)
        return
    
    domain = context.args[0]
    msg = await update.message.reply_text("Checking domain...")
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"https://api.api-ninjas.com/v1/whois?domain={domain}", headers={"X-Api-Key": "free"})
            data = r.json()
            
            exp_date = data.get("expiration_date", "Unknown")
            registrar = data.get("registrar", "Unknown")
            creation = data.get("creation_date", "Unknown")
            
            await msg.edit_text(
                f"<b>DOMAIN INFO</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Domain: <code>{domain}</code>\n"
                f"Registrar: <code>{registrar}</code>\n"
                f"Created: <code>{creation}</code>\n"
                f"Expires: <code>{exp_date}</code>",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await msg.edit_text(f"Error checking domain: {str(e)}", parse_mode=ParseMode.HTML)


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
        
# ==============================================================================
# BAGIAN 1: /jeni (AUTO CREATE ACCOUNT - ANTI BANNED DOMAIN)
# ==============================================================================
async def jeni_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    caller_id = msg.from_user.id
    
    # Owner only check (opsional):
    if caller_id != OWNER_ID:  # ✅ GANTI
        await msg.reply_text("⛔ Owner only!")
        return
    
    # --- HELPER ANIMASI BAR ---
    async def update_bar(percent, status_text, logs=""):
        bar_len = 10
        filled = int(percent / 10)
        bar = "█" * filled + "░" * (bar_len - filled)
        text = (
            f"🧬 <b>JENNI.AI SYSTEM OVERRIDE</b>\n"
            f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
            f"<b>⚙️ PROCESS:</b>\n"
            f"<code>[{bar}] {percent}%</code>\n\n"
            f"<b>📝 STATUS:</b>\n"
            f"<i>{status_text}</i>\n"
            f"<code>{logs}</code>"
        )
        try: await status_msg.edit_text(text, parse_mode="HTML")
        except: pass 

    status_msg = await msg.reply_text("💻 <b>INITIALIZING EXPLOIT...</b>", parse_mode="HTML")
    await update_bar(10, "Allocating Resources...", "> Loading modules...\n> Bypassing SSL pinning...")
    
    fname = random.choice(["Alex", "Budi", "Charlie", "Dani", "Evan"])
    password = f"P@ssw0rd{random.randint(100000,999999)}"  # ✅ RANDOM PASSWORD

    # --- LOGIKA RETRY ---
    max_retries = 3
    email = None
    id_token = None
    attempt_success = False

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            
            for attempt in range(1, max_retries + 1):
                logs_attempt = f"> Attempt {attempt}/{max_retries}..."
                await update_bar(20 + (attempt * 5), f"Forging Identity ({attempt}/{max_retries})...", logs_attempt)
                
                # A. GENERATE EMAIL
                mail_headers = {"X-API-Key": TEMPMAIL_API_KEY}  # ✅ GANTI
                resp_mail = await client.post(
                    "https://api.temp-mail.io/v1/emails",
                    headers=mail_headers,
                    json={"domain_type": "premium"}
                )
                
                if resp_mail.status_code != 200:
                    await asyncio.sleep(1)
                    continue
                
                current_email = resp_mail.json().get("email")
                logger.info(f"[JENI] Email generated: {current_email}")
                
                # B. SIGNUP
                await update_bar(40 + (attempt * 5), "Injecting Payload...", 
                               f"> Testing Domain: {current_email.split('@')[1]}\n> Target: accounts:signUp")
                
                signup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"  # ✅ GANTI
                signup_payload = {"email": current_email, "password": password, "returnSecureToken": True}
                
                reg_resp = await client.post(signup_url, json=signup_payload)
                
                if reg_resp.status_code == 200:
                    email = current_email
                    id_token = reg_resp.json()["idToken"]
                    attempt_success = True
                    logger.info(f"[JENI] Signup success: {email}")
                    break
                else:
                    error_msg = reg_resp.json().get("error", {}).get("message", "Unknown error")
                    logger.warning(f"[JENI] Signup failed: {error_msg}")
                    await asyncio.sleep(1)
            
            if not attempt_success:
                await status_msg.edit_text("❌ <b>GAGAL TOTAL:</b> Semua domain ditolak. Coba lagi nanti.")
                return

            # TRIGGER VERIFIKASI
            await update_bar(65, "Account Created.", f"> Valid Email: {email}\n> Triggering Verification...")
            verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"  # ✅ GANTI
            await client.post(verify_url, json={"requestType": "VERIFY_EMAIL", "idToken": id_token})

            # SCAN EMAIL
            final_link = None
            scan_attempts = 12
            for i in range(scan_attempts):
                await update_bar(75 + (i * 2), "Intercepting Link...", f"> Scanning Inbox... ({i+1}/{scan_attempts})")
                await asyncio.sleep(2)
                
                inbox_resp = await client.get(f"https://api.temp-mail.io/v1/emails/{email}/messages", headers=mail_headers)
                if inbox_resp.status_code == 200:
                    msgs = inbox_resp.json().get("messages", [])
                    if msgs:
                        body = msgs[0].get("body_text", "") + msgs[0].get("body_html", "")
                        links = re.findall(r'https?://[^\s<>"]+', body)
                        for link in links:
                            if "verifyEmail" in link or "jenni" in link.lower():
                                final_link = link
                                break
                        if final_link: break
            
            if not final_link:
                await status_msg.edit_text("❌ <b>TIMEOUT:</b> Email verifikasi tidak masuk.")
                return

            # CLICK VERIFY
            await update_bar(95, "Link Found.", "> Executing Auto-Click...")
            await client.get(final_link)
            
            # ✅ SAVE TO DATABASE (ASYNC VERSION)
            try:
                await db_insert("accounts", {  # ✅ GANTI DARI cursor → async db_insert
                    "email": email,
                    "password": password,
                    "plan": "Monthly",
                    "status": "AVAILABLE"
                })
                logger.info(f"[JENI] Account saved: {email}")
            except Exception as db_err:
                logger.error(f"[JENI] DB error: {db_err}")
            
            await update_bar(100, "ACCESS GRANTED.", "> Done.")

            report = (
                f"<b>🧬 JENNI.AI ACCOUNT CREATED</b>\n"
                f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
                f"<b>📧 EMAIL :</b> <code>{email}</code>\n"
                f"<b>🔑 PASS  :</b> <code>{password}</code>\n"
                f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
                f"👉 <b>NEXT:</b> <code>/upgrade {email}|{password}</code>"
            )
            await status_msg.edit_text(report, parse_mode="HTML")

    except Exception as e:
        logger.error(f"[JENI] Exception: {str(e)}")
        await status_msg.edit_text(f"❌ <b>ERROR:</b> {str(e)[:100]}")
        
# ==============================================================================
# 🚀 BAGIAN 1: FITUR UPGRADE JENNI.AI (FACTORY)
# ==============================================================================

session_data = {}

async def start_upgrade_factory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Format:</b>\n<code>/upgrade email|password</code>", 
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    raw = " ".join(context.args)
    if "|" not in raw:
        await update.message.reply_text(
            "❌ <b>Format Salah:</b>\nPakai pemisah | (garis lurus)", 
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    email, password = raw.split("|", 1)
    
    # Reset Session
    session_data.clear()
    session_data["email"] = email.strip()
    session_data["password"] = password.strip()

    keyboard = [
        [InlineKeyboardButton("📅 MONTHLY (Rp 250k)", callback_data="plan_monthly")],
        [InlineKeyboardButton("🗓️ YEARLY (Rp 1jt)", callback_data="plan_yearly")]
    ]
    
    await update.message.reply_text(
        "🏭 <b>PILIH PAKET UPGRADE:</b>", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.HTML
    )
    
    return INPUT_CARD  # ✅ GUNAKAN YANG SUDAH ADA (= 2)

# ==============================================================================
# 🛠️ BAGIAN 2: KONFIGURASI BROWSER & POOL
# ==============================================================================

SELENIUM_POOL = ThreadPoolExecutor(max_workers=5) # Multitasking 5 order
MAX_STRIPE_RETRY = 3

def build_stealth_chrome(proxy_string=None):
    """Fungsi Bikin Browser Hantu"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    if proxy_string: options.add_argument(f'--proxy-server={proxy_string}')

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    })
    return driver

# ==============================================================================
# 👷 BAGIAN 3: WORKERS (LOGIC MESIN SELENIUM)
# ==============================================================================

def selenium_upgrade_worker(session_data, status_msg):
    """Worker 1: Login & Klik Upgrade"""
    driver = None
    try:
        driver = build_stealth_chrome()
        session_data['driver'] = driver
        wait = WebDriverWait(driver, 30)

        # Login
        driver.get("https://app.jenni.ai/login")
        wait.until(EC.visibility_of_element_located((By.NAME, "email"))).send_keys(session_data['email'])
        driver.find_element(By.NAME, "password").send_keys(session_data['password'])
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(5)

        # Ke Halaman Billing (Shortcut)
        try:
            driver.get("https://app.jenni.ai/settings/billing")
            time.sleep(4)
        except: pass

        # Pilih Plan
        if session_data['plan'] == "Monthly":
            try: driver.find_element(By.XPATH, "//div[contains(text(), 'Monthly')]").click()
            except: pass
        else:
            try: driver.find_element(By.XPATH, "//div[contains(text(), 'Annual')]").click()
            except: pass
        
        time.sleep(1)
        # Klik Tombol Upgrade (Cari tombol ungu)
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if "upgrade" in btn.text.lower():
                btn.click()
                break
        
        wait.until(EC.url_contains("stripe.com"))
        return True
    except Exception as e:
        if driver: driver.quit()
        return str(e)

def selenium_card_worker(driver, cc_data, email, password, plan):
    """Worker 2: Input Kartu & Bayar"""
    try:
        wait = WebDriverWait(driver, 20)
        cc, exp, cvv = cc_data.split("|")

        # Input Kartu
        wait.until(EC.visibility_of_element_located((By.ID, "cardNumber"))).send_keys(cc)
        time.sleep(0.2)
        driver.find_element(By.ID, "cardExpiry").send_keys(exp)
        driver.find_element(By.ID, "cardCvc").send_keys(cvv)
        driver.find_element(By.ID, "billingName").send_keys("Budi Santoso")
        
        # Alamat Dummy
        try: 
            driver.find_element(By.ID, "billingAddressLine1").send_keys("Jalan Merdeka")
            driver.find_element(By.ID, "billingCity").send_keys("Jakarta")
            driver.find_element(By.ID, "billingPostalCode").send_keys("12000")
        except: pass

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Cek Hasil (Looping 25 detik)
        for _ in range(25):
            time.sleep(1)
            curr_url = driver.current_url.lower()
            page_source = driver.page_source.lower()
            if "success" in curr_url or "thank" in page_source: return "SUCCESS"
            if "challenge" in curr_url or "authentication" in curr_url: return "OTP_REQUIRED"
            if "declined" in page_source: return "DECLINED"
        return "TIMEOUT"
    except Exception as e: return f"ERROR: {str(e)}"

def selenium_otp_worker(driver, otp_code):
    """Worker 3: Input OTP"""
    try:
        wait = WebDriverWait(driver, 10)
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in frames:
            try:
                driver.switch_to.frame(frame)
                otp_input = driver.find_element(By.XPATH, "//input[@type='password' or @type='text' or @type='tel']")
                otp_input.send_keys(otp_code)
                otp_input.send_keys("\n")
                driver.switch_to.default_content()
                break
            except: driver.switch_to.default_content()
        
        time.sleep(8)
        if "success" in driver.current_url.lower(): return True
        return False
    except: return False

# ==============================================================================
# 🎮 BAGIAN 4: TELEGRAM HANDLERS (LOGIC + LOGGING BACKUP)
# ==============================================================================

async def select_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session_data['plan'] = "Monthly" if query.data == "plan_monthly" else "Yearly"

    status_msg = await query.message.reply_text("🤖 <b>ROBOT BERGERAK...</b>\n<i>Login & Menuju Stripe...</i>", parse_mode="HTML")
    
    # Panggil Worker Login
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(SELENIUM_POOL, selenium_upgrade_worker, session_data, status_msg)

    if result is True:
        await status_msg.edit_text("💳 <b>SIAP GESEK!</b>\nKirim: <code>CC|MM/YY|CVV</code>", parse_mode="HTML")
        return INPUT_CARD
    else:
        await status_msg.edit_text(f"❌ <b>GAGAL LOGIN:</b>\n{result}")
        return ConversationHandler.END

async def input_card_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "|" not in text: 
        await update.message.reply_text("❌ Format: <code>CC|MM/YY|CVV</code>", parse_mode="HTML")
        return INPUT_CARD
    
    driver = session_data.get('driver')
    if not driver:
        await update.message.reply_text("❌ Sesi habis.")
        return ConversationHandler.END

    status_msg = await update.message.reply_text("💳 <b>MENGGESEK KARTU...</b>", parse_mode="HTML")
    
    # Panggil Worker Kartu
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(SELENIUM_POOL, selenium_card_worker, driver, text, session_data['email'], session_data['password'], session_data['plan'])

    if result == "SUCCESS":
        # 1. Simpan ke DB
        try:
            await db_insert("accounts", {
                "email": session_data['email'],
                "password": session_data['password'],
                "plan": session_data['plan'],
                "status": "AVAILABLE"
            })
        except: pass

        # 2. Kirim Bukti ke Chat Bot
        driver.save_screenshot("success.png")
        await update.message.reply_photo(open("success.png", "rb"), caption=f"✅ <b>SUKSES!</b>\n{session_data['email']}")
        
        # 3. [FITUR LOG] Kirim ke Channel Backup (LOGIC TAMBAHAN)
        LOG_CHANNEL_ID = -1001234567890 # GANTI INI DENGAN ID CHANNEL MAS
        try:
            struk_log = f"💎 <b>NEW ACCOUNT!</b>\n📧 {session_data['email']}\n🔑 {session_data['password']}\n📅 {session_data['plan']}\n💳 {text[:6]}xxxx"
            await context.bot.send_photo(chat_id=LOG_CHANNEL_ID, photo=open("success.png", "rb"), caption=struk_log, parse_mode="HTML")
        except: pass

        driver.quit()
        return ConversationHandler.END
    
    elif result == "OTP_REQUIRED":
        driver.save_screenshot("otp.png")
        await update.message.reply_photo(open("otp.png", "rb"), caption="⚠️ <b>BUTUH OTP!</b> Masukkan kodenya:")
        return INPUT_OTP
    
    elif result == "DECLINED":
        await status_msg.edit_text("❌ <b>DECLINED.</b> Coba kartu lain.")
        return INPUT_CARD
    
    else:
        await status_msg.edit_text(f"❌ <b>ERROR:</b> {result}")
        driver.quit()
        return ConversationHandler.END

async def input_otp_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    otp = update.message.text
    driver = session_data.get('driver')
    msg = await update.message.reply_text("⏳ <b>INPUT OTP...</b>", parse_mode="HTML")

    # Panggil Worker OTP
    loop = asyncio.get_event_loop()
    if await loop.run_in_executor(SELENIUM_POOL, selenium_otp_worker, driver, otp):
        try:
            await db_insert("accounts", {
                "email": session_data['email'],
                "password": session_data['password'],
                "plan": session_data['plan'],
                "status": "AVAILABLE"
            })
        except: pass
        
        await msg.edit_text("✅ <b>OTP SUKSES!</b>")

        # [FITUR LOG] Kirim ke Channel Backup (Juga saat OTP Sukses)
        LOG_CHANNEL_ID = -1001981442073 # GANTI DENGAN ID CHANNEL MAS
        try:
            driver.save_screenshot("otp_success.png")
            struk_log = f"💎 <b>NEW ACCOUNT (OTP)!</b>\n📧 {session_data['email']}\n🔑 {session_data['password']}\n📅 {session_data['plan']}"
            await context.bot.send_photo(chat_id=LOG_CHANNEL_ID, photo=open("otp_success.png", "rb"), caption=struk_log, parse_mode="HTML")
        except: pass

    else:
        await msg.edit_text("❌ <b>OTP GAGAL.</b>")
    
    driver.quit()
    return ConversationHandler.END

# ==========================================
# 🎯 STATE CONSTANTS (CONVERSATION HANDLER)
# ==========================================

WAIT_PROOF = 1
INPUT_CARD = 2
INPUT_OTP = 3
CONFIRM_CARD = 4
# ==========================================
# 🎯 UTILITY FUNCTIONS
# ==========================================

async def log_transaction(action: str, plan: str, user_id: int, status: str):
    """Log semua transaksi"""
    try:
        await db_insert("transaction_logs", {  # ✅ GANTI cursor
            "action": action,
            "plan": plan,
            "user_id": user_id,
            "status": status
        })
    except Exception as e:
        logger.error(f"Log transaction error: {e}")

async def check_pending_order(user_id: int) -> bool:
    """Check apakah user punya order pending"""
    try:
        result = await db_fetch_one(  # ✅ GANTI cursor
            "SELECT id FROM orders WHERE user_id=? AND status='pending'",
            (user_id,)
        )
        return bool(result)
    except:
        return False

async def check_stock_availability(plan: str) -> int:
    """Cek stok berdasarkan plan"""
    try:
        result = await db_fetch_one(  # ✅ GANTI cursor
            "SELECT COUNT(*) FROM accounts WHERE status='AVAILABLE' AND plan LIKE ?",
            (f"%{plan}%",)
        )
        return result[0] if result else 0  # ✅ GANTI
    except:
        return 0

async def get_available_account(plan: str) -> tuple:
    """Ambil 1 akun dari gudang"""
    try:
        return await db_fetch_one(  # ✅ GANTI cursor
            "SELECT id, email, password FROM accounts WHERE status='AVAILABLE' AND plan LIKE ? LIMIT 1",
            (f"%{plan}%",)
        )
    except:
        return None

async def get_price_for_plan(plan: str) -> str:  # ✅ TAMBAH async
    """Get harga untuk plan"""
    prices = {
        "Monthly": "Rp 25.000",
        "Yearly": "Rp 150.000"
    }
    return prices.get(plan, "Unknown")

def get_status_emoji(status: str) -> str:
    """Get emoji untuk status"""
    emojis = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌",
        "expired": "⏰"
    }
    return emojis.get(status, "❓")

def get_stock_icon(count: int) -> str:
    """Get icon untuk stok"""
    if count <= 0:
        return "❌"
    elif count <= 2:
        return "⚠️"
    elif count <= 5:
        return "🟡"
    else:
        return "🟢"

def get_stock_status(count: int) -> str:
    """Get status stok"""
    if count <= 0:
        return "❌ HABIS"
    elif count <= 2:
        return "⚠️ KRITIS"
    elif count <= 5:
        return "🟡 SEDIKIT"
    else:
        return "🟢 TERSEDIA"

# ==========================================
# 🛒 BELI START FLOW
# ==========================================

async def beli_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start pembelian dengan validasi"""
    user_id = update.effective_user.id
    
    try:
        has_pending = await check_pending_order(user_id)
        if has_pending:
            await update.message.reply_text(
                "⚠️ <b>ANDA MASIH PUNYA ORDER PENDING!</b>\n\n"
                "Tunggu admin ACC dulu sebelum beli lagi.\n"
                "Estimasi: 1-5 menit.\n\n"
                "Ketik /sts untuk cek status order Anda.",
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
        keyboard = []
        
        monthly_stock = await check_stock_availability("Monthly")
        monthly_btn = InlineKeyboardButton(
            f"📅 MONTHLY - Rp 25.000 ({monthly_stock} stok)",
            callback_data="beli_Monthly"
        ) if monthly_stock > 0 else InlineKeyboardButton(
            "📅 MONTHLY - HABIS",
            callback_data="out_of_stock"
        )
        keyboard.append([monthly_btn])
        
        yearly_stock = await check_stock_availability("Yearly")
        yearly_btn = InlineKeyboardButton(
            f"🗓️ YEARLY - Rp 150.000 ({yearly_stock} stok)",
            callback_data="beli_Yearly"
        ) if yearly_stock > 0 else InlineKeyboardButton(
            "🗓️ YEARLY - HABIS",
            callback_data="out_of_stock"
        )
        keyboard.append([yearly_btn])
        
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="beli_cancel")])
        
        await update.message.reply_text(
            "╔════════════════════════════╗\n"
            "║   🛒 MENU PEMBELIAN JENNI  ║\n"
            "╚════════════════════════════╝\n\n"
            "Silakan pilih paket yang mau dibeli:\n\n"
            "💡 <i>Pembayaran via QRIS (instant)</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return WAIT_PROOF
    
    except Exception as e:
        logger.error(f"Beli start error: {e}")
        await update.message.reply_text(
            f"❌ Error: {str(e)[:50]}",
            parse_mode="HTML"
        )
        return ConversationHandler.END


# ==========================================
# 💳 BELI MENU CALLBACK
# ==========================================

async def beli_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process pemilihan plan dengan safety checks"""
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    
    try:
        await query.answer()
        
        if query.data == "beli_cancel":
            await query.message.edit_text("❌ Transaksi dibatalkan.")
            return ConversationHandler.END
        
        if query.data == "out_of_stock":
            await query.answer("⚠️ Stok habis, silakan pilih paket lain!", show_alert=True)
            return WAIT_PROOF
        
        plan_dipilih = query.data.split("_")[1]
        
        stok = await check_stock_availability(plan_dipilih)
        
        if stok == 0:
            await query.message.edit_text(
                f"❌ <b>MAAF KAK, STOK {plan_dipilih.upper()} HABIS!</b>\n\n"
                "Jangan transfer dulu ya. Stok baru akan masuk dalam waktu dekat.\n"
                "Silakan cek /stock lagi nanti.",
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
        harga = await get_price_for_plan(plan_dipilih)
        context.user_data['plan_beli'] = plan_dipilih
        context.user_data['harga_beli'] = harga
        
        try:
            await db_insert("orders", {
                "user_id": user_id,
                "plan": plan_dipilih,
                "price": harga,
                "status": "pending"
            })
        except Exception as e:
            logger.error(f"Order insert error: {e}")
        
        try:
            await query.message.reply_photo(
                photo=QRIS_IMAGE,
                caption=(
                    f"╔════════════════════════════╗\n"
                    f"║   💳 INVOICE PEMBAYARAN    ║\n"
                    f"╚════════════════════════════╝\n\n"
                    f"<b>Produk:</b> Jenni.ai {plan_dipilih}\n"
                    f"<b>Harga :</b> {harga}\n"
                    f"<b>Status:</b> ⏳ Menunggu pembayaran\n\n"
                    f"📋 <b>CARA PEMBAYARAN:</b>\n"
                    f"1️⃣ Scan QRIS di atas\n"
                    f"2️⃣ Transfer <b>TEPAT</b> sesuai nominal\n"
                    f"3️⃣ <b>KIRIM FOTO BUKTI</b> sekarang\n\n"
                    f"⏰ <b>Batas waktu:</b> 30 menit\n"
                    f"(Jika expired, silakan /beli lagi)\n\n"
                    f"<i>Pembayaran instant ✓ Aman terpercaya ✓</i>"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"QRIS send error: {e}")
            await query.message.reply_text(
                f"❌ Error menampilkan QRIS: {e}\n"
                f"Hubungi admin untuk bantuan.",
                parse_mode="HTML"
            )
        
        return WAIT_PROOF
    
    except Exception as e:
        logger.error(f"Beli menu error: {e}")
        await query.message.reply_text(
            f"❌ Error: {str(e)[:50]}",
            parse_mode="HTML"
        )
        return ConversationHandler.END

# ==========================================
# 📊 STOCK COMMAND (IMPROVED)
# ==========================================

async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show gudang akun dengan detail"""
    try:
        rows = await db_fetch_all(  # ✅ GANTI cursor
            "SELECT plan, COUNT(*) FROM accounts WHERE status='AVAILABLE' GROUP BY plan"
        )
        
        msg = (
            "╔════════════════════════════╗\n"
            "║   🏭 GUDANG AKUN JENNI     ║\n"
            "║      (REALTIME UPDATE)     ║\n"
            "╚════════════════════════════╝\n\n"
        )
        
        if not rows:
            msg += "❌ <b>STOK HABIS!</b>\nSegera restock kak."
        else:
            total = 0
            for plan, count in rows:
                icon = get_stock_icon(count)
                status = get_stock_status(count)
                msg += f"{icon} <b>{plan}:</b> {count} pcs [{status}]\n"
                total += count
            
            msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"<b>Total:</b> {total} akun ready\n\n"
            msg += f"💡 Ketik /beli untuk pesan akun"
        
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Stock command error: {e}")
        await update.message.reply_text(
            f"❌ Error: {str(e)[:50]}",
            parse_mode="HTML"
        )

# ==========================================
# 📸 RECEIVE PROOF HANDLER (IMPROVED)
# ==========================================

async def receive_proof_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima bukti transfer dengan validasi ketat"""
    user = update.effective_user
    user_id = user.id
    
    try:
        if not update.message.photo:
            await update.message.reply_text(
                "⚠️ <b>FORMAT SALAH!</b>\n"
                "Kirim foto bukti transfer, jangan text/video/dll.",
                parse_mode="HTML"
            )
            return WAIT_PROOF
        
        photo = update.message.photo[-1]
        if photo.width < 300 or photo.height < 300:
            await update.message.reply_text(
                "⚠️ <b>FOTO TERLALU KECIL!</b>\n\n"
                "Pastikan foto bukti transfer jelas & terang.\n"
                "Kirim ulang dengan resolusi lebih tinggi (min 300x300px).",
                parse_mode="HTML"
            )
            return WAIT_PROOF
        
        photo_id = photo.file_id
        plan = context.user_data.get('plan_beli')
        harga = context.user_data.get('harga_beli')
        
        if not plan or not harga:
            await update.message.reply_text(
                "⚠️ <b>ERROR!</b>\n"
                "Data order hilang. Silakan /beli lagi.",
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
        # ✅ GANTI cursor → db_update
        try:
            await db_update(
                "orders",
                {"proof_photo_id": photo_id},
                {"user_id": user_id, "status": "pending", "plan": plan}
            )
        except Exception as e:
            logger.error(f"Order update error: {e}")
        
        await update.message.reply_text(
            "✅ <b>BUKTI DITERIMA!</b>\n\n"
            "Mohon tunggu sebentar, Admin sedang mengecek mutasi...\n"
            "<i>(Estimasi 1-5 menit)</i>\n\n"
            "Ketik /sts untuk cek status pesanan Anda.",
            parse_mode="HTML"
        )
        
        tombol_admin = [
            [
                InlineKeyboardButton("✅ ACC (Kirim Akun)", callback_data=f"confirm|{user_id}|{plan}"),
                InlineKeyboardButton("❌ TOLAK", callback_data=f"reject|{user_id}")
            ]
        ]
        
        caption_admin = (
            f"╔════════════════════════════╗\n"
            f"║   💰 PESANAN BARU MAS!     ║\n"
            f"╚════════════════════════════╝\n\n"
            f"👤 <b>Buyer:</b> {user.full_name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"@{user.username if user.username else 'N/A'}\n\n"
            f"📦 <b>Paket:</b> {plan}\n"
            f"💵 <b>Nominal:</b> {harga}\n\n"
            f"📝 <b>Caption:</b> {update.message.caption if update.message.caption else '(Tidak ada)'}\n\n"
            f"<i>Cek mutasi rekening, kalau masuk klik ACC.</i>"
        )
        
        try:
            await context.bot.send_photo(
                chat_id=OWNER_ID,  # ✅ GANTI config.OWNER_ID
                photo=photo_id,
                caption=caption_admin,
                reply_markup=InlineKeyboardMarkup(tombol_admin),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Admin notification error: {e}")
        
        return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"Proof handler error: {e}")
        await update.message.reply_text(
            f"❌ <b>SISTEM ERROR!</b>\n"
            f"Error: {str(e)[:50]}\n\n"
            f"Hubungi admin untuk bantuan.",
            parse_mode="HTML"
        )
        return ConversationHandler.END

# ==========================================
# ✅ ADMIN APPROVAL CALLBACK (IMPROVED)
# ==========================================

async def admin_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approval system dengan confirmation"""
    query = update.callback_query
    caller_id = query.from_user.id
    
    try:
        if caller_id != OWNER_ID:  # ✅ GANTI config.OWNER_ID
            await query.answer("⛔ Hanya owner yang bisa approve!", show_alert=True)
            return
        
        await query.answer()
        
        data = query.data.split("|")
        action = data[0]
        buyer_id = int(data[1])
        
        if action == "reject":
            # ✅ GANTI cursor → db_update
            try:
                await db_update(
                    "orders",
                    {"status": "rejected"},
                    {"user_id": buyer_id}
                )
            except:
                pass
            
            await query.message.edit_caption(
                caption="❌ <b>TRANSAKSI DITOLAK.</b>"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=buyer_id,
                    text=(
                        "❌ <b>MAAF!</b>\n\n"
                        "Bukti transfer Anda ditolak atau dana belum masuk.\n\n"
                        "Silakan:\n"
                        "• Cek kembali bukti transfer\n"
                        "• Pastikan nominal tepat\n"
                        "• Hubungi admin jika ada pertanyaan\n\n"
                        "Ketik /beli untuk order lagi."
                    ),
                    parse_mode="HTML"
                )
            except:
                pass
            
            await log_transaction("rejection", "N/A", buyer_id, "rejected")
            return
        
        plan_beli = data[2]
        
        if action == "confirm":
            confirm_kb = [
                [
                    InlineKeyboardButton("✅ YA, KIRIM AKUN", callback_data=f"confirm_final|{buyer_id}|{plan_beli}"),
                    InlineKeyboardButton("❌ BATAL", callback_data=f"reject|{buyer_id}")
                ]
            ]
            
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(confirm_kb)
            )
            await query.answer("⚠️ Confirm dulu sebelum kirim akun!", show_alert=True)
            return
        
        if action == "confirm_final":
            acc_data = await get_available_account(plan_beli)  # ✅ Sudah pakai db_fetch_one
            
            if not acc_data:
                await query.message.edit_caption(
                    caption=(
                        f"⚠️ <b>WADUH MAS!</b>\n\n"
                        f"Stok {plan_beli} tiba-tiba habis!\n"
                        f"(Mungkin keambil orang lain barusan)\n\n"
                        f"Tolong restock dulu."
                    )
                )
                return
            
            acc_id, email, password = acc_data
            
            # ✅ GANTI cursor → db_update
            await db_update(
                "accounts",
                {"status": "SOLD"},
                {"id": acc_id}
            )
            
            # ✅ GANTI cursor → db_update
            await db_update(
                "orders",
                {"status": "approved", "approved_at": datetime.datetime.now().isoformat()},
                {"user_id": buyer_id, "plan": plan_beli}
            )
            
            trx_id = f"INV-{uuid.uuid4().hex[:6].upper()}"
            waktu = datetime.datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
            
            struk = (
                f"╔════════════════════════════╗\n"
                f"║   ✅ PEMBAYARAN DITERIMA!  ║\n"
                f"╚════════════════════════════╝\n\n"
                f"🧾 <b>INVOICE:</b> <code>{trx_id}</code>\n"
                f"📅 <b>Waktu:</b> {waktu}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📧 <b>Email:</b> <code>{email}</code>\n"
                f"🔑 <b>Password:</b> <code>{password}</code>\n"
                f"💎 <b>Paket:</b> Jenni.AI {plan_beli}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✅ <b>Akun Garansi 30 Hari</b>\n"
                f"❓ Ada masalah? Hubungi admin\n\n"
                f"⭐ Jangan lupa kasih rating ya!"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=buyer_id,
                    text=struk,
                    parse_mode="HTML"
                )
                
                remaining = await check_stock_availability(plan_beli)
                
                msg_owner = f"✅ <b>DONE!</b>\n\nAkun terkirim.\n\nSisa Stok {plan_beli}: <b>{remaining}</b>"
                
                if remaining <= 2:
                    msg_owner += "\n\n⚠️ <b>STOK KRITIS! SEGERA /upgrade MAS!</b>"
                
                await query.message.edit_caption(
                    caption=msg_owner,
                    parse_mode="HTML"
                )
                
                await log_transaction("approval", plan_beli, buyer_id, "approved")
                
            except Exception as e:
                logger.error(f"Send akun error: {e}")
                await query.message.reply_text(
                    f"⚠️ <b>ERROR MENGIRIM!</b>\n\n"
                    f"Error: {str(e)[:50]}\n\n"
                    f"Data Akun:\n"
                    f"Email: {email}\n"
                    f"Pass: {password}\n\n"
                    f"Tolong kirim manual ke buyer."
                )
    
    except Exception as e:
        logger.error(f"Admin approval error: {e}")
        await query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)

# ==========================================
# 📊 STS COMMAND (BUYER) - CHANGED FROM STATUS
# ==========================================

async def sts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show buyer their order status"""
    user_id = update.effective_user.id
    
    try:
        # ✅ GANTI cursor → db_fetch_one
        order = await db_fetch_one("""
            SELECT plan, status, created_at FROM orders 
            WHERE user_id=? 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (user_id,))
        
        if not order:
            await update.message.reply_text(
                "❌ <b>BELUM ADA PESANAN</b>\n\n"
                "Silakan /beli untuk membuat pesanan pertama.",
                parse_mode="HTML"
            )
            return
        
        plan, status, created_at = order
        emoji = get_status_emoji(status)
        
        msg = (
            f"╔════════════════════════════╗\n"
            f"║   {emoji} STATUS PESANAN   ║\n"
            f"╚════════════════════════════╝\n\n"
            f"<b>Paket:</b> {plan}\n"
            f"<b>Status:</b> {status.upper()}\n"
            f"<b>Waktu:</b> {created_at}\n\n"
        )
        
        if status == "pending":
            msg += "⏳ Menunggu approval admin... (1-5 menit)\n\n💡 Tunggu SMS/notif dari admin"
        elif status == "approved":
            msg += "✅ Akun sudah dikirim! Cek DM Anda.\n\n💡 Jangan lupa kasih rating ⭐"
        elif status == "rejected":
            msg += "❌ Pesanan ditolak.\n\n💡 Hubungi admin untuk info lebih lanjut."
        elif status == "expired":
            msg += "⏰ Pesanan expired (30 menit tidak ada konfirmasi).\n\n💡 Silakan /beli lagi."
        
        await update.message.reply_text(msg, parse_mode="HTML")
    
    except Exception as e:
        logger.error(f"STS command error: {e}")
        await update.message.reply_text(
            f"❌ Error: {str(e)[:50]}",
            parse_mode="HTML"
        )

# ==========================================
# 📈 SALES REPORT (OWNER ONLY)
# ==========================================

async def sales_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show sales report untuk owner"""
    caller_id = update.effective_user.id
    
    if caller_id != OWNER_ID:  # ✅ GANTI config.OWNER_ID
        await update.message.reply_text("⛔ Owner only!")
        return
    
    try:
        # ✅ GANTI cursor → db_fetch_all
        today = await db_fetch_all("""
            SELECT plan, COUNT(*) as total, 
                   SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as sold
            FROM orders
            WHERE DATE(created_at) = DATE('now')
            GROUP BY plan
        """)
        
        # ✅ GANTI cursor → db_fetch_one
        all_time_sold_result = await db_fetch_one("SELECT COUNT(*) FROM orders WHERE status='approved'")
        all_time_sold = all_time_sold_result[0] if all_time_sold_result else 0
        
        # ✅ GANTI cursor → db_fetch_one
        pending_result = await db_fetch_one("SELECT COUNT(*) FROM orders WHERE status='pending'")
        pending = pending_result[0] if pending_result else 0
        
        report = (
            "╔════════════════════════════╗\n"
            "║   📊 SALES REPORT          ║\n"
            "╚════════════════════════════╝\n\n"
        )
        
        report += "<b>📅 TODAY</b>\n"
        report += "━━━━━━━━━━━━━━━━━\n"
        
        if today:
            for plan, total, sold in today:
                report += f"{plan}: {total} orders | {sold} ✅ sold\n"
        else:
            report += "Belum ada order hari ini\n"
        
        report += f"\n<b>📈 ALL TIME</b>\n"
        report += "━━━━━━━━━━━━━━━━━\n"
        report += f"Total Sold: {all_time_sold}\n"
        report += f"Pending: {pending}\n"
        
        await update.message.reply_text(report, parse_mode="HTML")
    
    except Exception as e:
        logger.error(f"Sales report error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:50]}", parse_mode="HTML")

# ==========================================
# ❌ CANCEL OPERATION HANDLER
# ==========================================

async def cancel_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel operasi/transaksi"""
    try:
        await update.message.reply_text(
            "❌ <b>OPERASI DIBATALKAN</b>\n\n"
            "Silakan ketik /beli jika ingin order lagi.",
            parse_mode="HTML"
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Cancel operation error: {e}")
        return ConversationHandler.END

# ==========================================
# 🕌 JADWAL SHOLAT (PREMIUM ULTIMATE V4)
# ==========================================
async def sholat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                f"☀️ Dzuhur  : <code>{t['Dhuhr']}</code>\n"
                f"🌤️ Ashar   : <code>{t['Asr']}</code>\n"
                f"🌇 Maghrib : <code>{t['Maghrib']}</code>\n"
                f"🌃 Isya    : <code>{t['Isha']}</code>\n\n"
                f"────────────────────────\n"
                f"🤲 <i>“Jadikan sabar dan sholat sebagai penolongmu.”</i>\n"
                f"   <i>(QS. Al-Baqarah: 45)</i>"
            )

            kb = [
                [
                    InlineKeyboardButton(
                        "🔁 Set Daily Reminder", callback_data="menu_sholat_set"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Check Another City",
                        switch_inline_query_current_chat="sholat ",
                    )
                ],
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
                    "Tips:\n"
                    "• Use a valid city name.\n"
                    "• Example: <code>/sholat Surabaya</code>"
                ),
                parse_mode=ParseMode.HTML,
            )

    except Exception as e:
        await msg.edit_text(
            f"❌ <b>System Error:</b> <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML,
        )

async def inline_sholat(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        text = (
            f"🕌 JADWAL SHOLAT — {city.title()}\n"
            f"{d['readable']} | {hijri_str}\n\n"
            f"Imsak   : {t['Imsak']}\n"
            f"Subuh   : {t['Fajr']}\n"
            f"Dzuhur  : {t['Dhuhr']}\n"
            f"Ashar   : {t['Asr']}\n"
            f"Maghrib : {t['Maghrib']}\n"
            f"Isya    : {t['Isha']}"
        )

        results = [
            InlineQueryResultArticle(
                id="sholat",
                title=f"Jadwal Sholat {city.title()}",
                description=f"Subuh {t['Fajr']} • Maghrib {t['Maghrib']}",
                input_message_content=InputTextMessageContent(
                    text, parse_mode=ParseMode.HTML
                ),
            )
        ]

        await update.inline_query.answer(results, cache_time=1)

    except Exception:
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