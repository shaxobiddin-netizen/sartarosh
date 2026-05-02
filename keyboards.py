from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import List
from i18n import tr

# ──────────────────────────────────────────────
# Common keyboards
# ──────────────────────────────────────────────

def kb_remove():
    return ReplyKeyboardRemove()


def kb_main_menu_client(lang: str = "uz"):
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=tr(lang, "main.find_barber")),
        KeyboardButton(text=tr(lang, "main.my_appointments")),
    )
    builder.row(
        KeyboardButton(text=tr(lang, "main.history")),
        KeyboardButton(text=tr(lang, "main.nearby")),
    )
    builder.row(
        KeyboardButton(text=tr(lang, "main.profile")),
        KeyboardButton(text=tr(lang, "main.help")),
    )
    return builder.as_markup(resize_keyboard=True)


def kb_main_menu_barber(lang: str = "uz"):
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=tr(lang, "barber.appointments")),
        KeyboardButton(text=tr(lang, "barber.services")),
    )
    builder.row(
        KeyboardButton(text=tr(lang, "barber.portfolio")),
        KeyboardButton(text=tr(lang, "barber.blacklist")),
    )
    builder.row(
        KeyboardButton(text=tr(lang, "barber.stats")),
        KeyboardButton(text=tr(lang, "barber.settings")),
    )
    builder.row(
        KeyboardButton(text=tr(lang, "barber.ads")),
        KeyboardButton(text=tr(lang, "barber.profile")),
    )
    return builder.as_markup(resize_keyboard=True)


def kb_role_selection():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✂️ Sartarosh", callback_data="role:barber"),
        InlineKeyboardButton(text="👤 Mijoz", callback_data="role:client"),
    )
    return builder.as_markup()


def kb_request_phone():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True))
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def kb_request_location():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True))
    builder.row(
        KeyboardButton(text="⏭️ O'tkazib yuborish"),
        KeyboardButton(text="❌ Bekor qilish"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def kb_cancel():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def kb_back_cancel():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="⬅️ Orqaga"),
        KeyboardButton(text="❌ Bekor qilish"),
    )
    return builder.as_markup(resize_keyboard=True)


def kb_skip_cancel():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="⏭️ O'tkazib yuborish"),
        KeyboardButton(text="❌ Bekor qilish"),
    )
    return builder.as_markup(resize_keyboard=True)


# ──────────────────────────────────────────────
# Barber keyboards
# ──────────────────────────────────────────────

def kb_barber_list(barbers: list):
    """barbers: list of (BarberProfile, User) tuples"""
    builder = InlineKeyboardBuilder()
    for profile, user in barbers:
        name = profile.salon_name or user.first_name
        rating_str = f"⭐ {profile.rating:.1f}" if profile.review_count > 0 else "⭐ Yangi"
        builder.row(
            InlineKeyboardButton(
                text=f"✂️ {name} ({rating_str})",
                callback_data=f"barber:{profile.id}"
            )
        )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))
    return builder.as_markup()


def kb_service_list(services: list, lat=None, lon=None, barber_id: int = None):
    """services: list of Service objects"""
    builder = InlineKeyboardBuilder()
    
    if lat is not None and lon is not None:
        builder.row(
            InlineKeyboardButton(
                text="🗺 Google Maps orqali ko'rish",
                url=f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            )
        )

    if barber_id:
        builder.row(
            InlineKeyboardButton(
                text="🖼 Portfolioni ko'rish (Rasmlar)",
                callback_data=f"portfolio:{barber_id}"
            ),
            InlineKeyboardButton(
                text="📩 Xabar yozish",
                callback_data=f"chat:barber:{barber_id}"
            )
        )

    for svc in services:
        builder.row(
            InlineKeyboardButton(
                text=f"{svc.name} — {svc.price:,} so'm ({svc.duration} min)",
                callback_data=f"service:{svc.id}"
            )
        )
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back"))
    return builder.as_markup()


def kb_date_picker(dates: list):
    """dates: list of datetime.date objects"""
    builder = InlineKeyboardBuilder()
    days_uz = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    months_uz = [
        "", "Yan", "Fev", "Mar", "Apr", "May", "Iyun",
        "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"
    ]
    for d in dates:
        day_name = days_uz[d.weekday()]
        label = f"{day_name}, {d.day} {months_uz[d.month]}"
        builder.button(
            text=label,
            callback_data=f"date:{d.isoformat()}"
        )
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back"))
    return builder.as_markup()


def kb_time_slots(slots: list):
    """slots: list of time strings 'HH:MM'"""
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(text=slot, callback_data=f"time:{slot}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back"))
    return builder.as_markup()


def kb_confirm_booking(barber_name: str, service_name: str, date: str, time: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_booking"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"),
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Appointment management keyboards
# ──────────────────────────────────────────────

def kb_appointment_actions(appointment_id: int, is_barber: bool = False, status: str = "pending"):
    builder = InlineKeyboardBuilder()
    if is_barber:
        if status == "pending":
            builder.row(
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"appt:confirm:{appointment_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"appt:cancel:{appointment_id}"),
            )
        elif status == "confirmed":
            builder.row(
                InlineKeyboardButton(text="✔️ Bajarildi", callback_data=f"appt:complete:{appointment_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"appt:cancel:{appointment_id}"),
            )
        elif status in ("completed", "cancelled"):
            if status == "completed":
                builder.row(InlineKeyboardButton(text="📸 Portfolio uchun rasm yuklash", callback_data=f"appt:photo:{appointment_id}"))
            builder.row(InlineKeyboardButton(text="🚫 Mijozni bloklash", callback_data=f"appt:block:{appointment_id}"))
        # Message client button for barber
        builder.row(InlineKeyboardButton(text="📩 Mijozga xabar yozish", callback_data=f"chat:client:{appointment_id}"))
    else:
        if status in ("pending", "confirmed"):
            builder.row(
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"appt:cancel:{appointment_id}"),
            )
        # Message barber button for client
        builder.row(InlineKeyboardButton(text="📩 Sartaroshga xabar yozish", callback_data=f"chat:barber_appt:{appointment_id}"))
    return builder.as_markup()


def kb_appointments_list(appointments: list, is_barber: bool = False):
    """appointments: list of Appointment objects"""
    builder = InlineKeyboardBuilder()
    status_emoji = {
        "pending": "🕐",
        "confirmed": "✅",
        "completed": "✔️",
        "cancelled": "❌",
    }
    for appt in appointments:
        emoji = status_emoji.get(appt.status.value, "📅")
        label = f"{emoji} {appt.appointment_date} {appt.start_time.strftime('%H:%M')}"
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"view_appt:{appt.id}"
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="main_menu"))
    return builder.as_markup()


def kb_rate_barber(barber_id: int, appt_id: int):
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.row(
            InlineKeyboardButton(
                text="⭐" * i + f" ({i} yulduz)",
                callback_data=f"rate:{barber_id}:{appt_id}:{i}"
            )
        )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Barber profile / service management keyboards
# ──────────────────────────────────────────────

def kb_barber_profile_setup():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏪 Profil tahrirlash", callback_data="barber:edit_profile"),
    )
    builder.row(
        InlineKeyboardButton(text="✂️ Xizmat qo'shish", callback_data="barber:add_service"),
        InlineKeyboardButton(text="📋 Xizmatlar", callback_data="barber:list_services"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Jadval", callback_data="barber:schedule"),
    )
    return builder.as_markup()


def kb_my_services(services: list):
    builder = InlineKeyboardBuilder()
    for svc in services:
        status = "✅" if svc.is_active else "❌"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {svc.name} — {svc.price:,} so'm",
                callback_data=f"edit_service:{svc.id}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Yangi xizmat", callback_data="barber:add_service"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="barber:profile"),
    )
    return builder.as_markup()


def kb_barber_settings():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏪 Profil tahrirlash", callback_data="barber:edit_profile"),
        InlineKeyboardButton(text="✂️ Xizmatlar", callback_data="barber:list_services"),
    )
    builder.row(
        InlineKeyboardButton(text="🕒 Ish soatlari", callback_data="barber:work_hours"),
        InlineKeyboardButton(text="📅 Ish kunlari", callback_data="barber:work_days"),
    )
    builder.row(
        InlineKeyboardButton(text="💳 Obuna boshqaruvi", callback_data="barber:subscription"),
    )
    return builder.as_markup()


def kb_service_edit(service_id: int, is_active: bool):
    builder = InlineKeyboardBuilder()
    toggle_text = "❌ O'chirish" if is_active else "✅ Yoqish"
    builder.row(
        InlineKeyboardButton(text=toggle_text, callback_data=f"svc:toggle:{service_id}"),
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"svc:delete:{service_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="barber:list_services"),
    )
    return builder.as_markup()


def kb_schedule_days():
    days = [
        ("Du", "monday"), ("Se", "tuesday"), ("Ch", "wednesday"),
        ("Pa", "thursday"), ("Ju", "friday"), ("Sh", "saturday"), ("Ya", "sunday"),
    ]
    builder = InlineKeyboardBuilder()
    for label, value in days:
        builder.button(text=label, callback_data=f"sched:{value}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="✅ Tayyor", callback_data="sched:done"))
    return builder.as_markup()


def kb_blacklist_main(has_entries: bool = False):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Mijoz qo'shish", callback_data="blacklist:add"),
    )
    if has_entries:
        builder.row(
            InlineKeyboardButton(text="📋 Ro'yxatni ko'rish", callback_data="blacklist:list"),
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="barber:profile"),
    )
    return builder.as_markup()


def kb_blacklist_add(clients: list):
    """clients: list of (user_id, first_name) tuples"""
    builder = InlineKeyboardBuilder()
    for uid, name in clients:
        builder.row(
            InlineKeyboardButton(
                text=f"🚫 {name}",
                callback_data=f"blacklist:add:{uid}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="blacklist:back"),
    )
    return builder.as_markup()


def kb_portfolio_main(has_items: bool = False):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Yangi ish qo'shish", callback_data="portfolio:add"),
    )
    if has_items:
        builder.row(
            InlineKeyboardButton(text="📋 Portfolioni ko'rish", callback_data="portfolio:list"),
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="barber:profile"),
    )
    return builder.as_markup()


def kb_portfolio_item(item_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"portfolio:delete:{item_id}"),
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="portfolio:list"),
    )
    return builder.as_markup()


def kb_advertisement_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Mijozlarga reklama", callback_data="ad:send_clients"),
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Promo kod yaratish", callback_data="ad:promo_code"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Reklama statistikasi", callback_data="ad:stats"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="barber:main"),
    )
    return builder.as_markup()


def kb_ad_target_selection():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Barcha mijozlar", callback_data="ad_target:all"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Uchrashuv qilganlar", callback_data="ad_target:past"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Qayta mijozlar", callback_data="ad_target:returning"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="ad:cancel"),
    )
    return builder.as_markup()


def kb_promo_menu(promo_codes: list):
    """Menu for managing promo codes."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Yangi promo kod", callback_data="promo:create"),
    )
    for promo in promo_codes:
        status = "✅" if promo.is_active else "❌"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {promo.code} (-{promo.discount_percent}%)",
                callback_data=f"promo:view:{promo.id}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="ad:main"),
    )
    return builder.as_markup()


def kb_promo_item(promo_id: int, is_active: bool = True):
    """Keyboard for individual promo code actions."""
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.row(
            InlineKeyboardButton(text="❌ Deaktivlash", callback_data=f"promo:deactivate:{promo_id}"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="✅ Aktivlash", callback_data=f"promo:activate:{promo_id}"),
        )
    builder.row(
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"promo:delete:{promo_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Promo kodlar ro'yxati", callback_data="promo:list"),
    )
    return builder.as_markup()


def kb_promo_confirm():
    """Keyboard for confirming promo code creation."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="promo:confirm:yes"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="promo:confirm:no"),
    )
    return builder.as_markup()


def kb_skip_expiry():
    """Keyboard to skip expiry date selection."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭️ Muddat chegarasiz", callback_data="promo:expiry:none"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="promo:cancel"),
    )
    return builder.as_markup()


def kb_promo_input(barber_id: int):
    """Keyboard for client to enter promo code during booking."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎁 Promo kod kiritish", callback_data=f"promo:input:{barber_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="⏭️ O'tkazib yuborish", callback_data=f"promo:skip:{barber_id}"),
    )
    return builder.as_markup()


def kb_chat_reply(target_user_id: int, is_barber: bool = False):
    builder = InlineKeyboardBuilder()
    label = "📩 Javob yozish"
    prefix = "reply:client" if is_barber else "reply:barber"
    builder.row(
        InlineKeyboardButton(text=label, callback_data=f"{prefix}:{target_user_id}")
    )
    return builder.as_markup()


def kb_rating_stars(appointment_id: int):
    """1-5 yulduz baholash tugmalari."""
    builder = InlineKeyboardBuilder()
    stars = [
        ("⭐", 1), ("⭐⭐", 2), ("⭐⭐⭐", 3), ("⭐⭐⭐⭐", 4), ("⭐⭐⭐⭐⭐", 5)
    ]
    builder.row(
        *[InlineKeyboardButton(text=emoji, callback_data=f"rate:{appointment_id}:{value}") for emoji, value in stars]
    )
    builder.row(
        InlineKeyboardButton(text="⏭️ Baholashni o'tkazib yuborish", callback_data=f"rate:{appointment_id}:skip")
    )
    return builder.as_markup()


def kb_skip_comment():
    """Keyboard to skip comment/review."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭️ Sharh yozmaslik", callback_data="review:skip")
    )
    return builder.as_markup()


def kb_review_confirm():
    """Confirm or edit review."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="review:confirm"),
        InlineKeyboardButton(text="✏️ Qayta baholash", callback_data="review:retry")
    )
    return builder.as_markup()


def kb_cancellation_reasons():
    """Keyboard for selecting cancellation reason."""
    builder = InlineKeyboardBuilder()
    reasons = [
        ("Boshqa ish chiqdi", "other_work"),
        ("Sog'lig'im yomon", "health"),
        ("Reja o'zgardi", "plan_changed"),
        ("Xizmatdan norozi", "unsatisfied"),
        ("Boshqa", "other")
    ]
    for text, data in reasons:
        builder.row(InlineKeyboardButton(text=text, callback_data=f"cancel:reason:{data}"))
    return builder.as_markup()


def kb_blacklist_item(client_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Blokdan chiqarish",
            callback_data=f"blacklist:remove:{client_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="blacklist:list"),
    )
    return builder.as_markup()


def kb_blacklist_list(blocked: list):
    """blocked: list of (client_id, name) tuples"""
    builder = InlineKeyboardBuilder()
    for client_id, name in blocked:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ {name} — blokdan chiqarish",
                callback_data=f"blacklist:remove:{client_id}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="blacklist:back"),
    )
    return builder.as_markup()


def kb_work_days(working_days: set):
    """Generate keyboard for toggling work days. Active days highlighted."""
    days = [
        ("Du", "monday"), ("Se", "tuesday"), ("Ch", "wednesday"),
        ("Pa", "thursday"), ("Ju", "friday"), ("Sh", "saturday"), ("Ya", "sunday"),
    ]
    builder = InlineKeyboardBuilder()
    for label, value in days:
        active = value in working_days
        text = f"✅ {label}" if active else f"☑️ {label}"
        builder.button(text=text, callback_data=f"wd:toggle:{value}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="barber:settings"))
    return builder.as_markup()
