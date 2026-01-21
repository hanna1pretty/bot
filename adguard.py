# ==========================================
# 🛡️ ADGUARD SYSTEM - USER SESSION PROTECTION
# ==========================================

import time
import logging
import aiosqlite
from functools import wraps
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class AdguardSystem:
    """
    Adguard System - Proteksi akses bot
    User HARUS /start dulu sebelum bisa akses fitur apapun
    """
    
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.active_sessions = {}
        self.session_timeout = 86400 * 30
        
    async def init_table(self):
        """Buat tabel adguard_sessions jika belum ada"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS adguard_sessions (
                    user_id INTEGER PRIMARY KEY,
                    first_start REAL,
                    last_activity REAL,
                    start_count INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1
                )
            """)
            await db.commit()
        logger.info("[ADGUARD] Table initialized")
    
    async def register_session(self, user_id: int) -> bool:
        """Register user session saat /start"""
        current_time = time.time()
        
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute(
                    "SELECT start_count FROM adguard_sessions WHERE user_id=?",
                    (user_id,)
                )
                existing = await cursor.fetchone()
                
                if existing:
                    await db.execute("""
                        UPDATE adguard_sessions 
                        SET last_activity=?, start_count=start_count+1, is_active=1
                        WHERE user_id=?
                    """, (current_time, user_id))
                else:
                    await db.execute("""
                        INSERT INTO adguard_sessions (user_id, first_start, last_activity, start_count, is_active)
                        VALUES (?, ?, ?, 1, 1)
                    """, (user_id, current_time, current_time))
                
                await db.commit()
            
            self.active_sessions[user_id] = {
                "last_activity": current_time,
                "is_active": True
            }
            
            logger.info(f"[ADGUARD] Session registered for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[ADGUARD] Register error: {e}")
            return False
    
    async def unregister_session(self, user_id: int) -> bool:
        """Unregister user session (close)"""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("DELETE FROM adguard_sessions WHERE user_id=?", (user_id,))
                await db.commit()
            
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
                
            logger.info(f"[ADGUARD] Session unregistered for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"[ADGUARD] Unregister error: {e}")
            return False

    async def unregister_session(self, user_id: int) -> bool:
        """Unregister user session (close)"""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("DELETE FROM adguard_sessions WHERE user_id=?", (user_id,))
                await db.commit()
            
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
                
            logger.info(f"[ADGUARD] Session unregistered for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"[ADGUARD] Unregister error: {e}")
            return False

    async def unregister_session(self, user_id: int) -> bool:
        """Unregister user session (close)"""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("DELETE FROM adguard_sessions WHERE user_id=?", (user_id,))
                await db.commit()
            
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
                
            logger.info(f"[ADGUARD] Session unregistered for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"[ADGUARD] Unregister error: {e}")
            return False

    async def check_session(self, user_id: int) -> bool:
        """Cek apakah user punya session aktif"""
        current_time = time.time()
        
        if user_id in self.active_sessions:
            session = self.active_sessions[user_id]
            if session.get("is_active") and (current_time - session.get("last_activity", 0)) < self.session_timeout:
                self.active_sessions[user_id]["last_activity"] = current_time
                return True
        
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute(
                    "SELECT last_activity, is_active FROM adguard_sessions WHERE user_id=?",
                    (user_id,)
                )
                result = await cursor.fetchone()
                
                if result:
                    last_activity, is_active = result
                    
                    if is_active and (current_time - last_activity) < self.session_timeout:
                        self.active_sessions[user_id] = {
                            "last_activity": current_time,
                            "is_active": True
                        }
                        
                        await db.execute(
                            "UPDATE adguard_sessions SET last_activity=? WHERE user_id=?",
                            (current_time, user_id)
                        )
                        await db.commit()
                        return True
                    
                return False
                
        except Exception as e:
            logger.error(f"[ADGUARD] Check session error: {e}")
            return False
    
    async def invalidate_session(self, user_id: int) -> bool:
        """Invalidate user session"""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute(
                    "UPDATE adguard_sessions SET is_active=0 WHERE user_id=?",
                    (user_id,)
                )
                await db.commit()
            
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
            
            logger.info(f"[ADGUARD] Session invalidated for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[ADGUARD] Invalidate error: {e}")
            return False
    
    async def get_session_stats(self, user_id: int) -> dict:
        """Get session statistics untuk user"""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute(
                    "SELECT first_start, last_activity, start_count, is_active FROM adguard_sessions WHERE user_id=?",
                    (user_id,)
                )
                result = await cursor.fetchone()
                
                if result:
                    return {
                        "first_start": result[0],
                        "last_activity": result[1],
                        "start_count": result[2],
                        "is_active": bool(result[3])
                    }
                return None
                
        except Exception as e:
            logger.error(f"[ADGUARD] Get stats error: {e}")
            return None


# Global instance
_adguard_instance = None

def set_adguard_instance(instance: AdguardSystem):
    """Set global adguard instance"""
    global _adguard_instance
    _adguard_instance = instance

def require_start(func):
    """Decorator untuk require user sudah /start"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        global _adguard_instance
        
        if _adguard_instance is None:
            logger.error("[ADGUARD] Instance not set! Call set_adguard_instance() first")
            return await func(update, context)
        
        user_id = None
        if update.effective_user:
            user_id = update.effective_user.id
        elif update.callback_query and update.callback_query.from_user:
            user_id = update.callback_query.from_user.id
        elif update.inline_query and update.inline_query.from_user:
            user_id = update.inline_query.from_user.id
        
        if not user_id:
            logger.warning("[ADGUARD] Could not determine user_id")
            return await func(update, context)
        
        has_session = await _adguard_instance.check_session(user_id)
        
        if not has_session:
            error_message = (
                "🚫 <b>ACCESS DENIED</b>\n\n"
                "This feature is not available to you.\n"
                "If you want to use this bot, please type <code>/start</code> first.\n\n"
                "<i>Session required for security purposes.</i>"
            )
            
            try:
                if update.callback_query:
                    await update.callback_query.answer(
                        "🚫 ACCESS DENIED\n\nThis is not for you.\nIf you want to use this bot, please /start first.",
                        show_alert=True
                    )
                elif update.inline_query:
                    await update.inline_query.answer(
                        results=[
                            InlineQueryResultArticle(
                                id="no_session",
                                title="🚫 Session Required",
                                description="Please /start the bot first to use inline features",
                                input_message_content=InputTextMessageContent(
                                    message_text="🚫 Please /start the bot first to use this feature."
                                )
                            )
                        ],
                        cache_time=5
                    )
                else:
                    await update.message.reply_text(
                        error_message,
                        parse_mode=ParseMode.HTML
                    )
            except Exception as e:
                logger.error(f"[ADGUARD] Error sending denial message: {e}")
            
            logger.warning(f"[ADGUARD] Access denied for user {user_id} - no session")
            return
        
        return await func(update, context)
    
    return wrapper


def require_start_callback(func):
    """Decorator khusus untuk callback query handler"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        global _adguard_instance
        
        if _adguard_instance is None:
            return await func(update, context)
        
        q = update.callback_query
        if not q:
            return await func(update, context)
        
        user_id = q.from_user.id
        has_session = await _adguard_instance.check_session(user_id)
        
        if not has_session:
            await q.answer(
                "🚫 ACCESS DENIED\n\nThis is not for you.\nIf you want to use this bot, please /start first.",
                show_alert=True
            )
            logger.warning(f"[ADGUARD] Callback denied for user {user_id}")
            return
        
        return await func(update, context)
    
    return wrapper


def require_start_inline(func):
    """Decorator khusus untuk inline query handler"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        global _adguard_instance
        
        if _adguard_instance is None:
            return await func(update, context)
        
        query = update.inline_query
        if not query:
            return await func(update, context)
        
        user_id = query.from_user.id
        has_session = await _adguard_instance.check_session(user_id)
        
        if not has_session:
            await query.answer(
                results=[
                    InlineQueryResultArticle(
                        id="no_session",
                        title="🚫 Session Required",
                        description="Please /start the bot first",
                        input_message_content=InputTextMessageContent(
                            message_text="🚫 Please /start the bot first to use this feature."
                        )
                    )
                ],
                cache_time=5
            )
            logger.warning(f"[ADGUARD] Inline denied for user {user_id}")
            return
        
        return await func(update, context)
    
    return wrapper
