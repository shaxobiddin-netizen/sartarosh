"""middlewares/security.py — Xavfsizlik middleware'lari"""
import time
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

logger = logging.getLogger(__name__)

# Rate limiting: user_id -> [(timestamp, count), ...]
_rate_limits: Dict[int, list] = {}

# Blocked users (spam qilganlar)
_blocked_users: set = set()


class SecurityMiddleware(BaseMiddleware):
    """
    Rate limiting va spam himoyasi.
    Har bir user 1 daqiqada max 20 ta xabar yubora oladi.
    """

    def __init__(self, max_messages: int = 20, window_seconds: int = 60):
        self.max_messages = max_messages
        self.window = window_seconds
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None

        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id is None:
            return await handler(event, data)

        # Bloklangan user'ni tekshirish
        if user_id in _blocked_users:
            logger.warning(f"Blocked user {user_id} attempted access")
            return None

        # Rate limit tekshirish
        now = time.time()
        user_history = _rate_limits.get(user_id, [])

        # Eski yozuvlarni tozalash
        user_history = [t for t in user_history if now - t < self.window]
        user_history.append(now)
        _rate_limits[user_id] = user_history

        if len(user_history) > self.max_messages:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            if isinstance(event, Message):
                await event.answer(
                    "⛔ Siz juda ko'p so'rov yubordingiz. Iltimos, biroz kuting."
                )
            return None

        return await handler(event, data)


class AdminRequiredMiddleware(BaseMiddleware):
    """
    Faqat admin uchun handlerlar.
    is_admin=True qilingan handlerlarga qo'llaniladi.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        from config import config

        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id and user_id == config.ADMIN_ID:
            return await handler(event, data)

        logger.warning(f"Unauthorized admin access attempt by user {user_id}")
        if isinstance(event, Message):
            await event.answer("⛔ Bu buyruq faqat adminlar uchun.")
        elif isinstance(event, CallbackQuery):
            await event.answer("Admin huquqi yo'q!", show_alert=True)
        return None


def validate_phone(phone: str) -> bool:
    """Telefon raqam validatsiyasi: +998XXXXXXXXX"""
    if not phone:
        return False
    cleaned = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    # Uzbekistan: +998XXXXXXXXX
    if cleaned.startswith("+998") and len(cleaned) == 13:
        return cleaned[1:].isdigit()
    if cleaned.startswith("998") and len(cleaned) == 12:
        return cleaned.isdigit()
    if cleaned.startswith("9") and len(cleaned) == 9:
        return cleaned.isdigit()
    return False


def sanitize_input(text: str, max_length: int = 4096) -> str:
    """Xavfsiz matn tozalash. HTML injection oldini olish."""
    if not text:
        return ""
    # HTML taglarni tozalash
    import html
    text = html.escape(text)
    # Max uzunlik
    return text[:max_length]


def validate_price(text: str) -> int | None:
    """Narx validatsiyasi: faqat musbat butun son."""
    try:
        cleaned = text.replace(" ", "").replace(",", "").replace(".", "")
        price = int(cleaned)
        if price <= 0 or price > 10_000_000:  # 10 million so'mdan oshmasin
            return None
        return price
    except (ValueError, AttributeError):
        return None


def validate_duration(text: str) -> int | None:
    """Xizmat davomiyligi: 5-480 daqiqa."""
    try:
        duration = int(text.strip())
        if 5 <= duration <= 480:
            return duration
        return None
    except (ValueError, AttributeError):
        return None
