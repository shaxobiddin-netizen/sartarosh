"""handlers/admin.py — Admin panel: foydalanuvchilar, sartaroshlar, statistika"""
import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import (
    User, UserRole, BarberProfile, Service,
    Appointment, AppointmentStatus, Payment, PaymentStatus
)
from config import config

router = Router()


# ──────────────────────────────────────────────
# Guard: faqat admin foydalana oladi
# ──────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


def admin_only(func):
    """Decorator — faqat admin uchun."""
    import functools
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        uid = event.from_user.id if hasattr(event, 'from_user') else 0
        if not is_admin(uid):
            if hasattr(event, 'answer'):
                await event.answer("⛔ Sizda admin huquqi yo'q.")
            return
        return await func(event, *args, **kwargs)
    return wrapper


# ──────────────────────────────────────────────
# Admin klaviatura
# ──────────────────────────────────────────────

from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import KeyboardButton, InlineKeyboardButton


def kb_admin_main():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👥 Foydalanuvchilar"),
        KeyboardButton(text="✂️ Sartaroshlar"),
    )
    builder.row(
        KeyboardButton(text="📅 Uchrashuvlar"),
        KeyboardButton(text="📊 Umumiy statistika"),
    )
    builder.row(
        KeyboardButton(text="📢 Xabar yuborish"),
        KeyboardButton(text="🔙 Chiqish"),
    )
    return builder.as_markup(resize_keyboard=True)


def kb_users_list(users: list):
    builder = InlineKeyboardBuilder()
    for u in users:
        role_emoji = {"client": "👤", "barber": "✂️", "admin": "👑"}.get(u.role.value, "👤")
        name = f"{u.first_name} {u.last_name or ''}".strip()
        builder.row(
            InlineKeyboardButton(
                text=f"{role_emoji} {name} (@{u.username or 'noma\'lum'})",
                callback_data=f"admin_user:{u.id}"
            )
        )
    return builder.as_markup()


def kb_user_actions(user_id: int, is_active: bool):
    builder = InlineKeyboardBuilder()
    toggle = "❌ Bloklash" if is_active else "✅ Blokdan chiqarish"
    builder.row(
        InlineKeyboardButton(text=toggle, callback_data=f"admin_toggle:{user_id}"),
        InlineKeyboardButton(text="✂️ Admin qilish", callback_data=f"admin_make_admin:{user_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_users_back"),
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# /admin buyrug'i
# ──────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return

    # User ni admin qilib belgilash
    user = await session.get(User, message.from_user.id)
    if user and user.role != UserRole.ADMIN:
        user.role = UserRole.ADMIN
        await session.commit()

    await message.answer(
        "👑 <b>Admin Panel</b>\n\n"
        "Xush kelibsiz! Quyidagi bo'limlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=kb_admin_main()
    )


# ──────────────────────────────────────────────
# Foydalanuvchilar ro'yxati
# ──────────────────────────────────────────────

@router.message(F.text.in_({"👥 Foydalanuvchilar", "👥 Пользователи"}))
async def admin_users(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    stmt = select(User).order_by(User.created_at.desc()).limit(30)
    result = await session.execute(stmt)
    users = result.scalars().all()

    total = await session.execute(select(func.count(User.id)))
    total_count = total.scalar()

    await message.answer(
        f"👥 <b>Foydalanuvchilar</b> (jami: {total_count})\n"
        f"Oxirgi 30 ta ko'rsatilmoqda:",
        parse_mode="HTML",
        reply_markup=kb_users_list(users)
    )


@router.callback_query(F.data.startswith("admin_user:"))
async def admin_view_user(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    user = await session.get(User, user_id)
    if not user:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    role_text = {"client": "Mijoz", "barber": "Sartarosh", "admin": "Admin"}.get(
        user.role.value, "—"
    )

    # Count appointments
    stmt = select(func.count(Appointment.id)).where(Appointment.client_id == user_id)
    appt_count = (await session.execute(stmt)).scalar() or 0

    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Ism: {user.first_name} {user.last_name or ''}\n"
        f"Username: @{user.username or '—'}\n"
        f"Telefon: {user.phone or '—'}\n"
        f"Rol: {role_text}\n"
        f"Holat: {'✅ Faol' if user.is_active else '❌ Bloklangan'}\n"
        f"Uchrashuvlar: {appt_count}\n"
        f"Ro'yxatdan: {user.created_at.strftime('%d.%m.%Y %H:%M')}"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb_user_actions(user.id, user.is_active)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_toggle:"))
async def admin_toggle_user(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    user = await session.get(User, user_id)
    if not user:
        await callback.answer("Topilmadi.", show_alert=True)
        return

    user.is_active = not user.is_active
    await session.commit()

    status = "faollashtirildi ✅" if user.is_active else "bloklandi ❌"
    await callback.answer(f"{user.first_name} {status}")
    await callback.message.edit_reply_markup(
        reply_markup=kb_user_actions(user.id, user.is_active)
    )


@router.callback_query(F.data.startswith("admin_make_admin:"))
async def admin_make_admin(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    user = await session.get(User, user_id)
    if not user:
        await callback.answer("Topilmadi.", show_alert=True)
        return

    user.role = UserRole.ADMIN
    await session.commit()
    await callback.answer(f"{user.first_name} admin qilindi! 👑")


@router.callback_query(F.data == "admin_users_back")
async def admin_users_back(callback: CallbackQuery, session: AsyncSession):
    stmt = select(User).order_by(User.created_at.desc()).limit(30)
    result = await session.execute(stmt)
    users = result.scalars().all()
    await callback.message.edit_text(
        "👥 <b>Foydalanuvchilar:</b>",
        parse_mode="HTML",
        reply_markup=kb_users_list(users)
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Sartaroshlar
# ──────────────────────────────────────────────

@router.message(F.text.in_({"✂️ Sartaroshlar", "✂️ Мастера"}))
async def admin_barbers(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    stmt = (
        select(BarberProfile, User)
        .join(User, User.id == BarberProfile.user_id)
        .order_by(BarberProfile.created_at.desc())
    )
    result = await session.execute(stmt)
    barbers = result.all()

    if not barbers:
        await message.answer("Hali sartarosh yo'q.")
        return

    text = f"✂️ <b>Sartaroshlar</b> ({len(barbers)} ta):\n\n"
    for profile, user in barbers:
        name = profile.salon_name or user.first_name
        sub = "✅" if profile.subscription_active else "❌"
        svc_count = len(profile.services)
        appt_count = profile.total_appointments
        text += (
            f"• <b>{name}</b> (@{user.username or '—'})\n"
            f"  Obuna: {sub} | Xizmatlar: {svc_count} | Uchrashuvlar: {appt_count}\n\n"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=kb_admin_main())


# ──────────────────────────────────────────────
# Uchrashuvlar
# ──────────────────────────────────────────────

@router.message(F.text.in_({"📅 Uchrashuvlar", "📅 Записи"}))
async def admin_appointments(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    today = datetime.date.today()
    stmt = (
        select(Appointment)
        .where(Appointment.appointment_date == today)
        .order_by(Appointment.start_time)
    )
    result = await session.execute(stmt)
    appointments = result.scalars().all()

    if not appointments:
        await message.answer(
            f"📅 Bugun ({today}) uchrashuvlar yo'q.",
            reply_markup=kb_admin_main()
        )
        return

    text = f"📅 <b>Bugungi uchrashuvlar</b> ({len(appointments)} ta):\n\n"
    status_emoji = {
        "pending": "🕐", "confirmed": "✅",
        "completed": "✔️", "cancelled": "❌"
    }
    for appt in appointments:
        emoji = status_emoji.get(appt.status.value, "📅")
        client = await session.get(User, appt.client_id)
        profile = await session.get(BarberProfile, appt.barber_id)
        barber_user = await session.get(User, profile.user_id) if profile else None
        text += (
            f"{emoji} {appt.start_time.strftime('%H:%M')} — "
            f"{client.first_name if client else '?'} → "
            f"{profile.salon_name or (barber_user.first_name if barber_user else '?')}\n"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=kb_admin_main())


# ──────────────────────────────────────────────
# Umumiy statistika
# ──────────────────────────────────────────────

@router.message(F.text.in_({"📊 Umumiy statistika", "📊 Общая статистика"}))
async def admin_stats(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    today = datetime.date.today()
    month_start = today.replace(day=1)

    # Users
    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    total_barbers = (await session.execute(
        select(func.count(User.id)).where(User.role == UserRole.BARBER)
    )).scalar() or 0
    total_clients = (await session.execute(
        select(func.count(User.id)).where(User.role == UserRole.CLIENT)
    )).scalar() or 0

    # New users this month
    new_users = (await session.execute(
        select(func.count(User.id)).where(User.created_at >= month_start)
    )).scalar() or 0

    # Appointments
    total_appts = (await session.execute(select(func.count(Appointment.id)))).scalar() or 0
    today_appts = (await session.execute(
        select(func.count(Appointment.id)).where(Appointment.appointment_date == today)
    )).scalar() or 0
    month_appts = (await session.execute(
        select(func.count(Appointment.id)).where(Appointment.appointment_date >= month_start)
    )).scalar() or 0
    completed_appts = (await session.execute(
        select(func.count(Appointment.id)).where(
            Appointment.status == AppointmentStatus.COMPLETED
        )
    )).scalar() or 0

    text = (
        f"📊 <b>Umumiy statistika</b>\n\n"
        f"👥 <b>Foydalanuvchilar:</b>\n"
        f"  Jami: {total_users}\n"
        f"  Sartaroshlar: {total_barbers}\n"
        f"  Mijozlar: {total_clients}\n"
        f"  Bu oyda yangi: {new_users}\n\n"
        f"📅 <b>Uchrashuvlar:</b>\n"
        f"  Jami: {total_appts}\n"
        f"  Bugun: {today_appts}\n"
        f"  Bu oy: {month_appts}\n"
        f"  Bajarilgan: {completed_appts}\n"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=kb_admin_main())


# ──────────────────────────────────────────────
# Xabar yuborish (broadcast)
# ──────────────────────────────────────────────

from aiogram.fsm.state import State, StatesGroup

class BroadcastState(StatesGroup):
    waiting_for_message = State()


@router.message(F.text.in_({"📢 Xabar yuborish", "📢 Рассылка"}))
async def broadcast_start(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    from aiogram.types import KeyboardButton
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    await message.answer(
        "📢 Barcha foydalanuvchilarga yubormoqchi bo'lgan xabarni yozing:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.set_state(BroadcastState.waiting_for_message)


@router.message(BroadcastState.waiting_for_message)
async def broadcast_send(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_admin_main())
        return

    # Get all active users
    stmt = select(User).where(User.is_active == True)
    result = await session.execute(stmt)
    users = result.scalars().all()

    sent = 0
    failed = 0
    for user in users:
        if user.id == message.from_user.id:
            continue
        try:
            await message.bot.send_message(
                user.id,
                f"📢 <b>Admin xabari:</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await state.clear()
    await message.answer(
        f"✅ Xabar yuborildi!\n"
        f"✔️ Muvaffaqiyatli: {sent}\n"
        f"❌ Xato: {failed}",
        reply_markup=kb_admin_main()
    )


# ──────────────────────────────────────────────
# Admin paneldan chiqish
# ──────────────────────────────────────────────

@router.message(F.text.in_({"🔙 Chiqish", "🔙 Выход"}))
async def admin_exit(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    from keyboards import kb_main_menu_barber, kb_main_menu_client
    user = await session.get(User, message.from_user.id)
    if user and user.role in (UserRole.ADMIN, UserRole.BARBER):
        kb = kb_main_menu_barber()
    else:
        kb = kb_main_menu_client()

    await message.answer(
        "Admin paneldan chiqdingiz.",
        reply_markup=kb
    )


# ──────────────────────────────────────────────
# Admin: manual subscription management
# ──────────────────────────────────────────────

@router.message(Command("activate_sub"))
async def admin_activate_sub(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Ishlatish: <code>/activate_sub &lt;user_id&gt;</code>\nMisol: /activate_sub 123456789", parse_mode="HTML")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❗ Noto'g'ri ID format.")
        return

    user = await session.get(User, user_id)
    if not user:
        await message.answer("❗ Foydalanuvchi topilmadi.")
        return

    if not user.barber_profile:
        await message.answer("❗ Bu foydalanuvchi sartarosh emas.")
        return

    p = user.barber_profile
    p.subscription_active = True
    from datetime import date, timedelta
    start = p.subscription_until if (p.subscription_until and p.subscription_until > date.today()) else date.today()
    p.subscription_until = start + timedelta(days=30)
    await session.commit()

    await message.answer(
        f"✅ <b>{user.first_name}</b> ({user_id}) obunasi faollashtirildi!\n"
        f"📅 Muddat: {p.subscription_until.strftime('%d.%m.%Y')}",
        parse_mode="HTML"
    )

    # Notify barber
    try:
        await message.bot.send_message(
            user_id,
            f"🎉 <b>Tabriklaymiz!</b>\n\n"
            f"Admin tomonidan obunangiz faollashtirildi.\n"
            f"📅 Muddat: {p.subscription_until.strftime('%d.%m.%Y')}",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.message(Command("deactivate_sub"))
async def admin_deactivate_sub(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Ishlatish: <code>/deactivate_sub &lt;user_id&gt;</code>\nMisol: /deactivate_sub 123456789", parse_mode="HTML")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❗ Noto'g'ri ID format.")
        return

    user = await session.get(User, user_id)
    if not user or not user.barber_profile:
        await message.answer("❗ Sartarosh topilmadi.")
        return

    p = user.barber_profile
    p.subscription_active = False
    p.subscription_until = None
    await session.commit()

    await message.answer(
        f"❌ <b>{user.first_name}</b> ({user_id}) obunasi o'chirildi.",
        parse_mode="HTML"
    )

    try:
        await message.bot.send_message(
            user_id,
            "⚠️ <b>Obunangiz o'chirildi.</b>\n\n"
            "Yangi obuna sotib olish uchun Sozlamalar → Obuna boshqaruvi.",
            parse_mode="HTML"
        )
    except Exception:
        pass
