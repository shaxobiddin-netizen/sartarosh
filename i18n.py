LANG_UZ = "uz"
LANG_RU = "ru"

_TRANSLATIONS = {
    "main.find_barber": {
        "uz": "✂️ Sartarosh topish",
        "ru": "✂️ Найти парикмахера",
    },
    "main.my_appointments": {
        "uz": "📅 Mening uchrashuvlarim",
        "ru": "📅 Мои записи",
    },
    "main.history": {
        "uz": "📜 Tarix",
        "ru": "📜 История",
    },
    "main.nearby": {
        "uz": "📍 Yaqindagi sartaroshlar",
        "ru": "📍 Ближайшие мастера",
    },
    "main.profile": {
        "uz": "👤 Mening profilim",
        "ru": "👤 Мой профиль",
    },
    "main.help": {
        "uz": "ℹ️ Yordam",
        "ru": "ℹ️ Помощь",
    },
    "main.menu": {
        "uz": "Bosh menyu:",
        "ru": "Главное меню:",
    },
    "cancel": {
        "uz": "❌ Bekor qilish",
        "ru": "❌ Отмена",
    },
    "nav.back": {
        "uz": "⬅️ Orqaga",
        "ru": "⬅️ Назад",
    },
    "nav.home": {
        "uz": "🏠 Bosh menyu",
        "ru": "🏠 Главное меню",
    },
    "catalog.maps": {
        "uz": "🗺 Google Maps",
        "ru": "🗺 Google Maps",
    },
    "catalog.portfolio": {
        "uz": "🖼 Portfolio",
        "ru": "🖼 Портфолио",
    },
    "catalog.chat": {
        "uz": "📩 Xabar",
        "ru": "📩 Сообщение",
    },
    "barber.appointments": {
        "uz": "📋 Uchrashuvlar",
        "ru": "📋 Записи",
    },
    "barber.services": {
        "uz": "✂️ Xizmatlarim",
        "ru": "✂️ Мои услуги",
    },
    "barber.portfolio": {
        "uz": "🖼 Portfoliom",
        "ru": "🖼 Портфолио",
    },
    "barber.blacklist": {
        "uz": "🚫 Qora ro'yxat",
        "ru": "🚫 Черный список",
    },
    "barber.stats": {
        "uz": "📊 Statistika",
        "ru": "📊 Статистика",
    },
    "barber.settings": {
        "uz": "⚙️ Sozlamalar",
        "ru": "⚙️ Настройки",
    },
    "barber.ads": {
        "uz": "📢 Reklama yuborish",
        "ru": "📢 Реклама",
    },
    "barber.profile": {
        "uz": "🏪 Profilim",
        "ru": "🏪 Мой профиль",
    },
    "admin.users": {
        "uz": "👥 Foydalanuvchilar",
        "ru": "👥 Пользователи",
    },
    "admin.barbers": {
        "uz": "✂️ Sartaroshlar",
        "ru": "✂️ Мастера",
    },
    "admin.appointments": {
        "uz": "📅 Uchrashuvlar",
        "ru": "📅 Записи",
    },
    "admin.stats": {
        "uz": "📊 Umumiy statistika",
        "ru": "📊 Общая статистика",
    },
    "admin.broadcast": {
        "uz": "📢 Xabar yuborish",
        "ru": "📢 Рассылка",
    },
    "admin.exit": {
        "uz": "🔙 Chiqish",
        "ru": "🔙 Выход",
    },
    "lang.choose": {
        "uz": "🌍 Tilni tanlang:",
        "ru": "🌍 Выберите язык:",
    },
    "lang.set_ok": {
        "uz": "✅ Til saqlandi.",
        "ru": "✅ Язык сохранен.",
    },
}


def tr(lang: str, key: str) -> str:
    data = _TRANSLATIONS.get(key)
    if not data:
        return key
    return data.get(lang) or data.get(LANG_UZ) or key
