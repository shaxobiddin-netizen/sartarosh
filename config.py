import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    BARBER_IDS: set = None  # populated in __post_init__
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///barbercrm.db"
    )

    # To'lov tizimlari
    CLICK_MERCHANT_ID: str = os.getenv("CLICK_MERCHANT_ID", "")
    PAYME_MERCHANT_ID: str = os.getenv("PAYME_MERCHANT_ID", "")

    # Tariflar
    SUBSCRIPTION_PRICE: int = 100_000  # so'm

    # Eslatma vaqtlari (kunlarda)
    REMINDER_INTERVALS: list = field(default_factory=lambda: [21, 14, 7, 0])

    # Default ish soatlari
    DEFAULT_WORK_START: str = "09:00"
    DEFAULT_WORK_END: str = "20:00"
    DEFAULT_MAX_CLIENTS: int = 20
    DEFAULT_SLOT_DURATION: int = 30  # minut

    # AI funksiyalari
    ENABLE_AI_FEATURES: bool = False

    # Bot branding - URL yoki fayl yo'li (ixtiyoriy)
    BOT_WELCOME_PHOTO: str = os.getenv("BOT_WELCOME_PHOTO", "")

    # Xavfsizlik sozlamalari
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
    """Webhook uchun maxfiy token (deploy qilinganda)"""

    RATE_LIMIT_MAX: int = int(os.getenv("RATE_LIMIT_MAX", "25"))
    """1 daqiqada max xabar soni"""

    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    """Rate limiting oynasi (sekund)"""

    ALLOWED_GROUP_IDS: list = field(default_factory=list)
    """Faqat shu guruhlarda ishlashi mumkin (bo'sh = hamma)"""

    def __post_init__(self):
        # Parse BARBER_IDS from comma-separated env string
        raw = os.getenv("BARBER_IDS", "")
        self.BARBER_IDS = {
            int(x.strip()) for x in raw.split(",") if x.strip().isdigit()
        }
        # Parse ALLOWED_GROUP_IDS
        groups_raw = os.getenv("ALLOWED_GROUP_IDS", "")
        self.ALLOWED_GROUP_IDS = [
            int(x.strip()) for x in groups_raw.split(",") if x.strip().isdigit()
        ]


config = Config()
