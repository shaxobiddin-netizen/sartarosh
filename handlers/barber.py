"""handlers/barber.py — Barber profile management, services, schedule, appointments"""
import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import (
    User, UserRole, BarberProfile, BarberSchedule, Service,
    Appointment, AppointmentStatus, DayOfWeek, AppointmentPhoto
)
from states import BarberProfileStates, ServiceStates, PortfolioStates, ChatStates, AdvertisementStates, CancellationStates
from keyboards import (
    kb_main_menu_barber, kb_cancel, kb_skip_cancel,
    kb_barber_profile_setup, kb_my_services, kb_service_edit,
    kb_appointments_list, kb_appointment_actions, kb_remove,
    kb_request_location, kb_rate_barber, kb_chat_reply,
    kb_advertisement_menu, kb_ad_target_selection,
    kb_promo_menu, kb_promo_item, kb_promo_confirm, kb_skip_expiry,
    kb_cancellation_reasons
)
from aiogram.types import FSInputFile
from config import config

router = Router()

DAY_NAMES_UZ = {
    "monday": "Dushanba",
    "tuesday": "Seshanba",
    "wednesday": "Chorshanba",
    "thursday": "Payshanba",
    "friday": "Juma",
    "saturday": "Shanba",
    "sunday": "Yakshanba",
}


# ──────────────────────────────────────────────
# /barber — xuddi /admin kabi sartarosh sifatida kirish
# ──────────────────────────────────────────────

@router.message(Command("barber"))
async def barber_entry(message: Message, session: AsyncSession):
    uid = message.from_user.id

    if uid not in config.BARBER_IDS and uid != config.ADMIN_ID:
        await message.answer(
            "⛔ Sizning ID ingiz sartaroshlar ro'yxatida yo'q.\n"
            "Adminga murojaat qiling."
        )
        return

    user = await session.get(User, uid)
    if not user:
        from handlers.common import get_or_create_user
        user = await get_or_create_user(session, message.from_user)

    if user.role != UserRole.BARBER:
        user.role = UserRole.BARBER
        await session.commit()

    await message.answer(
        "✂️ <b>Sartarosh paneliga xush kelibsiz!</b>\n\n"
        "Profilingizni sozlash va uchrashuvlarni boshqarish uchun "
        "quyidagi menyudan foydalaning:",
        parse_mode="HTML",
        reply_markup=kb_main_menu_barber()
    )



# ──────────────────────────────────────────────
# Guard: only barbers can use these handlers
# ──────────────────────────────────────────────

async def ensure_barber(session: AsyncSession, user_id: int) -> tuple[User | None, BarberProfile | None]:
    user = await session.get(User, user_id)
    if not user or user.role != UserRole.BARBER:
        return None, None
    profile = user.barber_profile
    return user, profile


# ──────────────────────────────────────────────
# Barber main menu / profile
# ──────────────────────────────────────────────

@router.message(F.text.in_({"🏪 Profilim", "🏪 Мой профиль"}))
async def barber_profile_menu(message: Message, session: AsyncSession):
    user, profile = await ensure_barber(session, message.from_user.id)
    if not user:
        await message.answer("Bu bo'lim faqat sartaroshlar uchun.")
        return

    if not profile:
        await message.answer(
            "Siz hali profil yaratmadingiz. Profil yarating:",
            reply_markup=kb_barber_profile_setup()
        )
        return

    text = (
        f"🏪 <b>{profile.salon_name or user.first_name}</b>\n\n"
        f"📍 Manzil: {profile.address or '—'}\n"
        f"📝 Bio: {profile.bio or '—'}\n"
        f"⏰ Ish soatlari: {profile.work_start or '—'} — {profile.work_end or '—'}\n"
        f"⭐ Reyting: {profile.rating:.1f} ({profile.review_count} sharh)\n"
        f"📊 Jami uchrashuvlar: {profile.total_appointments}\n"
        f"💳 Obuna: {'✅ Faol' if profile.subscription_active else '❌ Faol emas'}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb_barber_profile_setup())


@router.callback_query(F.data == "barber:edit_profile")
@router.callback_query(F.data == "barber:profile")
async def barber_edit_profile_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "✏️ Salon nomini kiriting (yoki o'tkazib yuborish):",
        reply_markup=kb_skip_cancel()
    )
    await state.set_state(BarberProfileStates.waiting_for_salon_name)
    await callback.answer()


@router.message(BarberProfileStates.waiting_for_salon_name)
async def barber_salon_name(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return

    name = None if message.text == "⏭️ O'tkazib yuborish" else message.text
    await state.update_data(salon_name=name)
    await message.answer("📍 Salon manzilini kiriting:", reply_markup=kb_skip_cancel())
    await state.set_state(BarberProfileStates.waiting_for_address)


@router.message(BarberProfileStates.waiting_for_address)
async def barber_address(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return

    address = None if message.text == "⏭️ O'tkazib yuborish" else message.text
    await state.update_data(address=address)
    await message.answer(
        "📍 Endi lokatsiyangizni yuboring (yoki o'tkazib yuboring):",
        reply_markup=kb_request_location()
    )
    await state.set_state(BarberProfileStates.waiting_for_location)


@router.message(BarberProfileStates.waiting_for_location)
async def barber_location(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return

    lat, lon = None, None
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude

    await state.update_data(latitude=lat, longitude=lon)
    await message.answer(
        "📝 O'zingiz haqida qisqacha yozing (bio):",
        reply_markup=kb_skip_cancel()
    )
    await state.set_state(BarberProfileStates.waiting_for_bio)


@router.message(BarberProfileStates.waiting_for_bio)
async def barber_bio(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return

    bio = None if message.text == "⏭️ O'tkazib yuborish" else message.text
    await state.update_data(bio=bio)
    await message.answer(
        "⏰ Ish boshlanish vaqtini kiriting (masalan: 09:00):",
        reply_markup=kb_skip_cancel()
    )
    await state.set_state(BarberProfileStates.waiting_for_work_start)


@router.message(BarberProfileStates.waiting_for_work_start)
async def barber_work_start(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return

    work_start = None
    if message.text != "⏭️ O'tkazib yuborish":
        try:
            work_start = datetime.time.fromisoformat(message.text.strip())
        except ValueError:
            await message.answer("❗ Noto'g'ri format. Masalan: 09:00")
            return

    await state.update_data(work_start=work_start.isoformat() if work_start else None)
    await message.answer(
        "⏰ Ish tugash vaqtini kiriting (masalan: 20:00):",
        reply_markup=kb_skip_cancel()
    )
    await state.set_state(BarberProfileStates.waiting_for_work_end)


@router.message(BarberProfileStates.waiting_for_work_end)
async def barber_work_end(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return

    work_end = None
    if message.text != "⏭️ O'tkazib yuborish":
        try:
            work_end = datetime.time.fromisoformat(message.text.strip())
        except ValueError:
            await message.answer("❗ Noto'g'ri format. Masalan: 20:00")
            return

    data = await state.get_data()
    await state.clear()

    user = await session.get(User, message.from_user.id)
    profile = user.barber_profile

    work_start_str = data.get("work_start")
    if profile is None:
        profile = BarberProfile(
            user_id=user.id,
            salon_name=data.get("salon_name"),
            address=data.get("address"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            bio=data.get("bio"),
            work_start=datetime.time.fromisoformat(work_start_str) if work_start_str else None,
            work_end=work_end,
            slot_duration=config.DEFAULT_SLOT_DURATION,
            max_clients_per_day=config.DEFAULT_MAX_CLIENTS,
        )
        session.add(profile)
    else:
        if data.get("salon_name") is not None:
            profile.salon_name = data["salon_name"]
        if data.get("address") is not None:
            profile.address = data["address"]
        if data.get("latitude") is not None:
            profile.latitude = data["latitude"]
        if data.get("longitude") is not None:
            profile.longitude = data["longitude"]
        if data.get("bio") is not None:
            profile.bio = data["bio"]
        if work_start_str:
            profile.work_start = datetime.time.fromisoformat(work_start_str)
        if work_end:
            profile.work_end = work_end

    await session.commit()
    await message.answer(
        "✅ <b>Profil saqlandi!</b>",
        parse_mode="HTML",
        reply_markup=kb_main_menu_barber()
    )


# ──────────────────────────────────────────────
# Services
# ──────────────────────────────────────────────

@router.message(F.text.in_({"✂️ Xizmatlarim", "✂️ Мои услуги"}))
@router.callback_query(F.data == "barber:list_services")
async def barber_list_services(event, session: AsyncSession):
    if isinstance(event, CallbackQuery):
        user_id = event.from_user.id
        answer = event.message.answer
        await event.answer()
    else:
        user_id = event.from_user.id
        answer = event.answer

    user = await session.get(User, user_id)
    if not user or user.role != UserRole.BARBER:
        await answer("Bu bo'lim faqat sartaroshlar uchun.")
        return

    profile = user.barber_profile
    if not profile:
        await answer("Avval profilingizni yarating.")
        return

    services = profile.services
    if not services:
        from keyboards import InlineKeyboardBuilder, InlineKeyboardButton
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="➕ Xizmat qo'shish", callback_data="barber:add_service"))
        await answer(
            "Hali xizmat qo'shilmagan. Birinchi xizmatni qo'shing:",
            reply_markup=builder.as_markup()
        )
        return

    await answer(
        f"✂️ <b>Xizmatlaringiz</b> ({len(services)} ta):",
        parse_mode="HTML",
        reply_markup=kb_my_services(services)
    )


@router.callback_query(F.data == "barber:add_service")
async def add_service_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not user:
        await callback.answer("Bu bo'lim faqat sartaroshlar uchun.", show_alert=True)
        return
    if not profile:
        await callback.answer("Avval profilingizni yarating.", show_alert=True)
        return

    await callback.message.answer(
        "✂️ Xizmat nomini kiriting (masalan: Soch olish):",
        reply_markup=kb_cancel()
    )
    await state.set_state(ServiceStates.waiting_for_service_name)
    await callback.answer()


@router.message(F.text == "✂️ Xizmat qo'shish")
async def add_service_text(message: Message, state: FSMContext, session: AsyncSession):
    user, profile = await ensure_barber(session, message.from_user.id)
    if not user or not profile:
        await message.answer("Avval profilingizni yarating.")
        return
    await message.answer("✂️ Xizmat nomini kiriting:", reply_markup=kb_cancel())
    await state.set_state(ServiceStates.waiting_for_service_name)


@router.message(ServiceStates.waiting_for_service_name)
async def service_name(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return
    await state.update_data(name=message.text.strip())
    await message.answer(
        "💰 Xizmat narxini so'mda kiriting (masalan: 30000):",
        reply_markup=kb_cancel()
    )
    await state.set_state(ServiceStates.waiting_for_service_price)


@router.message(ServiceStates.waiting_for_service_price)
async def service_price(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return
    try:
        price = int(message.text.replace(" ", "").replace(",", ""))
        assert price > 0
    except (ValueError, AssertionError):
        await message.answer("❗ Iltimos, to'g'ri narx kiriting (musbat son).")
        return

    await state.update_data(price=price)
    await message.answer(
        "⏱ Xizmat davomiyligini daqiqada kiriting (masalan: 30):",
        reply_markup=kb_cancel()
    )
    await state.set_state(ServiceStates.waiting_for_service_duration)


@router.message(ServiceStates.waiting_for_service_duration)
async def service_duration(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return
    try:
        duration = int(message.text.strip())
        assert 5 <= duration <= 480
    except (ValueError, AssertionError):
        await message.answer("❗ Iltimos, 5 dan 480 gacha bo'lgan daqiqa kiriting.")
        return

    await state.update_data(duration=duration)
    await message.answer(
        "📝 Xizmat ta'rifini kiriting (ixtiyoriy):",
        reply_markup=kb_skip_cancel()
    )
    await state.set_state(ServiceStates.waiting_for_service_description)


@router.message(ServiceStates.waiting_for_service_description)
async def service_description(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=kb_main_menu_barber())
        return

    description = None if message.text == "⏭️ O'tkazib yuborish" else message.text
    data = await state.get_data()
    await state.clear()

    user = await session.get(User, message.from_user.id)
    profile = user.barber_profile

    svc = Service(
        barber_id=profile.id,
        name=data["name"],
        price=data["price"],
        duration=data["duration"],
        description=description,
        is_active=True,
    )
    session.add(svc)
    await session.commit()

    await message.answer(
        f"✅ <b>Xizmat qo'shildi!</b>\n\n"
        f"📌 Nom: {svc.name}\n"
        f"💰 Narx: {svc.price:,} so'm\n"
        f"⏱ Davomiylik: {svc.duration} daqiqa",
        parse_mode="HTML",
        reply_markup=kb_main_menu_barber()
    )


@router.callback_query(F.data.startswith("edit_service:"))
async def edit_service(callback: CallbackQuery, session: AsyncSession):
    service_id = int(callback.data.split(":")[1])
    svc = await session.get(Service, service_id)
    if not svc:
        await callback.answer("Xizmat topilmadi.", show_alert=True)
        return

    status = "✅ Faol" if svc.is_active else "❌ Nofaol"
    await callback.message.edit_text(
        f"✂️ <b>{svc.name}</b>\n\n"
        f"💰 Narx: {svc.price:,} so'm\n"
        f"⏱ Davomiylik: {svc.duration} daqiqa\n"
        f"📝 Ta'rif: {svc.description or '—'}\n"
        f"Holat: {status}",
        parse_mode="HTML",
        reply_markup=kb_service_edit(svc.id, svc.is_active)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svc:toggle:"))
async def toggle_service(callback: CallbackQuery, session: AsyncSession):
    service_id = int(callback.data.split(":")[2])
    svc = await session.get(Service, service_id)
    if not svc:
        await callback.answer("Xizmat topilmadi.", show_alert=True)
        return
    svc.is_active = not svc.is_active
    await session.commit()
    status = "yoqildi ✅" if svc.is_active else "o'chirildi ❌"
    await callback.answer(f"{svc.name} {status}")
    await callback.message.edit_reply_markup(
        reply_markup=kb_service_edit(svc.id, svc.is_active)
    )


@router.callback_query(F.data.startswith("svc:delete:"))
async def delete_service(callback: CallbackQuery, session: AsyncSession):
    service_id = int(callback.data.split(":")[2])
    svc = await session.get(Service, service_id)
    if not svc:
        await callback.answer("Xizmat topilmadi.", show_alert=True)
        return
    name = svc.name
    await session.delete(svc)
    await session.commit()
    await callback.answer(f"'{name}' o'chirildi.")
    await callback.message.edit_text(f"🗑 <b>{name}</b> xizmati o'chirildi.", parse_mode="HTML")


# ──────────────────────────────────────────────
# Appointments (barber view)
# ──────────────────────────────────────────────

@router.message(F.text.in_({"📋 Uchrashuvlar", "📋 Записи"}))
async def barber_appointments(message: Message, session: AsyncSession):
    user, profile = await ensure_barber(session, message.from_user.id)
    if not user or not profile:
        await message.answer("Bu bo'lim faqat sartaroshlar uchun.")
        return

    stmt = (
        select(Appointment)
        .where(
            Appointment.barber_id == profile.id,
            Appointment.appointment_date >= datetime.date.today(),
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        )
        .order_by(Appointment.appointment_date, Appointment.start_time)
    )
    result = await session.execute(stmt)
    appointments = result.scalars().all()

    if not appointments:
        await message.answer("📅 Kelgusi uchrashuvlar yo'q.", reply_markup=kb_main_menu_barber())
        return

    await message.answer(
        f"📋 <b>Kelgusi uchrashuvlar</b> ({len(appointments)} ta):",
        parse_mode="HTML",
        reply_markup=kb_appointments_list(appointments, is_barber=True)
    )


@router.callback_query(F.data.startswith("view_appt:"))
async def view_appointment(callback: CallbackQuery, session: AsyncSession):
    appt_id = int(callback.data.split(":")[1])
    appt = await session.get(Appointment, appt_id)
    if not appt:
        await callback.answer("Uchrashuv topilmadi.", show_alert=True)
        return

    client = await session.get(User, appt.client_id)
    service = await session.get(Service, appt.service_id) if appt.service_id else None

    status_text = {
        "pending": "🕐 Kutilmoqda",
        "confirmed": "✅ Tasdiqlangan",
        "completed": "✔️ Bajarilgan",
        "cancelled": "❌ Bekor qilingan",
    }.get(appt.status.value, "—")

    text = (
        f"📅 <b>Uchrashuv #{appt.id}</b>\n\n"
        f"📆 Sana: {appt.appointment_date}\n"
        f"⏰ Vaqt: {appt.start_time.strftime('%H:%M')} — {appt.end_time.strftime('%H:%M')}\n"
        f"👤 Mijoz: {client.first_name} {client.last_name or ''}\n"
        f"📱 Telefon: {client.phone or '—'}\n"
        f"✂️ Xizmat: {service.name if service else '—'}\n"
        f"📝 Izoh: {appt.notes or '—'}\n"
        f"Holat: {status_text}"
    )

    # Determine if user is barber or client for this appointment
    viewer = await session.get(User, callback.from_user.id)
    is_barber = viewer and viewer.role == UserRole.BARBER

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb_appointment_actions(appt.id, is_barber=is_barber, status=appt.status.value)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("appt:confirm:"))
async def confirm_appointment(callback: CallbackQuery, session: AsyncSession):
    appt_id = int(callback.data.split(":")[2])
    appt = await session.get(Appointment, appt_id)
    if not appt:
        await callback.answer("Uchrashuv topilmadi.", show_alert=True)
        return
    appt.status = AppointmentStatus.CONFIRMED
    await session.commit()
    await callback.answer("✅ Uchrashuv tasdiqlandi!")
    await callback.message.edit_reply_markup(
        reply_markup=kb_appointment_actions(appt.id, is_barber=True, status=appt.status.value)
    )
    # Notify client
    client_u = await session.get(User, appt.client_id)
    b_profile = await session.get(BarberProfile, appt.barber_id)
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    if b_profile.latitude and b_profile.longitude:
        kb.row(InlineKeyboardButton(
            text="📍 Manzilni xaritada ko'rish", 
            url=f"https://www.google.com/maps/search/?api=1&query={b_profile.latitude},{b_profile.longitude}"
        ))

    try:
        await callback.bot.send_message(
            client_u.id,
            f"✅ <b>Uchrashuvingiz tasdiqlandi!</b>\n\n"
            f"🏪 Salon: <b>{b_profile.salon_name or '—'}</b>\n"
            f"📆 Sana: {appt.appointment_date}\n"
            f"🕒 Vaqt: {appt.start_time.strftime('%H:%M')}\n"
            f"📍 Manzil: {b_profile.address or '—'}",
            parse_mode="HTML",
            reply_markup=kb.as_markup() if b_profile.latitude else None
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("appt:cancel:"))
async def cancel_appointment_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Start cancellation flow - ask for reason."""
    appt_id = int(callback.data.split(":")[2])
    appt = await session.get(Appointment, appt_id)
    if not appt:
        await callback.answer("Uchrashuv topilmadi.", show_alert=True)
        return

    # Save appointment id to state
    await state.update_data(cancel_appt_id=appt_id)
    await state.set_state(CancellationStates.waiting_for_reason)

    await callback.message.edit_text(
        f"❌ <b>Uchrashuvni bekor qilish</b>\n\n"
        f"📆 {appt.appointment_date}, ⏰ {appt.start_time.strftime('%H:%M')}\n"
        f"👤 Mijoz: {appt.client.first_name if appt.client else '—'}\n\n"
        f"Bekor qilish sababini tanlang:",
        parse_mode="HTML",
        reply_markup=kb_cancellation_reasons()
    )
    await callback.answer()


@router.callback_query(CancellationStates.waiting_for_reason, F.data.startswith("cancel:reason:"))
async def cancel_reason_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle reason selection and confirm cancellation."""
    reason_code = callback.data.split(":")[2]
    reason_map = {
        "other_work": "Boshqa ish chiqdi",
        "health": "Sog'lig'im yomon",
        "plan_changed": "Reja o'zgardi",
        "unsatisfied": "Xizmatdan norozi",
        "other": "Boshqa sabab"
    }
    reason_text = reason_map.get(reason_code, "Boshqa")

    data = await state.get_data()
    appt_id = data.get("cancel_appt_id")

    if not appt_id:
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        await state.clear()
        return

    appt = await session.get(Appointment, appt_id)
    if not appt:
        await callback.answer("Uchrashuv topilmadi.", show_alert=True)
        await state.clear()
        return

    # Cancel appointment with reason
    appt.status = AppointmentStatus.CANCELLED
    appt.cancellation_reason = reason_text
    appt.cancelled_by = "barber" if callback.from_user.id == appt.barber.user_id else "client"
    await session.commit()
    await state.clear()

    await callback.message.edit_text(
        f"❌ <b>Uchrashuv bekor qilindi</b>\n\n"
        f"📆 {appt.appointment_date}, ⏰ {appt.start_time.strftime('%H:%M')}\n"
        f"📝 Sabab: {reason_text}",
        parse_mode="HTML",
        reply_markup=kb_appointment_actions(appt.id, is_barber=True, status=appt.status.value)
    )
    await callback.answer("Bekor qilindi!")

    # Notify other party
    viewer = await session.get(User, callback.from_user.id)
    notify_id = appt.client_id if (viewer and viewer.role == UserRole.BARBER) else None
    if notify_id:
        try:
            await callback.bot.send_message(
                notify_id,
                f"❌ <b>Sizning uchrashuvingiz bekor qilindi</b>\n\n"
                f"📆 {appt.appointment_date}, ⏰ {appt.start_time.strftime('%H:%M')}\n"
                f"📝 Sabab: {reason_text}\n\n"
                f"Yangi vaqtga yozilish uchun bot menyusidan foydalaning."
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("appt:complete:"))
async def complete_appointment(callback: CallbackQuery, session: AsyncSession):
    appt_id = int(callback.data.split(":")[2])
    appt = await session.get(Appointment, appt_id)
    if not appt:
        await callback.answer("Uchrashuv topilmadi.", show_alert=True)
        return
    appt.status = AppointmentStatus.COMPLETED
    # Update barber stats
    profile = await session.get(BarberProfile, appt.barber_id)
    if profile:
        profile.total_appointments += 1
    await session.commit()
    await callback.answer("✔️ Uchrashuv bajarildi deb belgilandi!")
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_reply_markup(
            reply_markup=kb_appointment_actions(appt.id, is_barber=True, status=appt.status.value)
        )
    except TelegramBadRequest:
        pass

    # Send QR code for client confirmation and ask for rating
    client = await session.get(User, appt.client_id)
    if client:
        try:
            # Generate QR code data
            qr_data = f"CONFIRM:{appt.id}:{appt.client_id}:{int(datetime.datetime.now().timestamp())}"

            await callback.bot.send_message(
                client.id,
                f"✅ <b>Uchrashuv bajarildi!</b>\n\n"
                f"Sartarosh uchrashuvni bajarildi deb belgiladi.\n\n"
                f"📋 Tasdiqlash kodi: <code>{qr_data}</code>\n\n"
                f"Iltimos, xizmatingizni baholang:",
                parse_mode="HTML",
                reply_markup=kb_rating_stars(appt.id)
            )
        except Exception as e:
            logger.error(f"Error sending completion notification: {e}")

@router.callback_query(F.data.startswith("appt:photo:"))
async def start_photo_upload(callback: CallbackQuery, state: FSMContext):
    appt_id = int(callback.data.split(":")[2])
    await state.update_data(photo_appt_id=appt_id)
    await state.set_state(PortfolioStates.waiting_for_photo)
    await callback.message.answer("📸 Iltimos, portfolio uchun rasm yuboring (yoki bekor qilish uchun /cancel):")
    await callback.answer()


@router.message(PortfolioStates.waiting_for_photo, F.photo)
async def process_portfolio_photo(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    appt_id = data.get("photo_appt_id")

    if not appt_id:
        await state.clear()
        await message.answer(
            "❌ Xatolik: Uchrashuv ID topilmadi. Iltimos, qayta urinib ko'ring.",
            reply_markup=kb_main_menu_barber()
        )
        return

    # Verify appointment exists
    appt = await session.get(Appointment, appt_id)
    if not appt:
        await state.clear()
        await message.answer(
            "❌ Xatolik: Uchrashuv topilmadi.",
            reply_markup=kb_main_menu_barber()
        )
        return

    # Get highest resolution photo
    photo = message.photo[-1]
    file_id = photo.file_id

    new_photo = AppointmentPhoto(
        appointment_id=appt_id,
        file_id=file_id,
        uploaded_at=datetime.datetime.utcnow()
    )
    session.add(new_photo)
    await session.commit()

    await state.clear()
    await message.answer("✅ Rasm muvaffaqiyatli yuklandi va portfoliongizga qo'shildi!")


@router.message(PortfolioStates.waiting_for_photo, Command("cancel"))
async def portfolio_photo_cancel(message: Message, state: FSMContext):
    """Cancel photo upload."""
    await state.clear()
    await message.answer("❌ Rasm yuklash bekor qilindi.", reply_markup=kb_main_menu_barber())


@router.message(PortfolioStates.waiting_for_photo, F.text.startswith("/"))
async def portfolio_photo_commands(message: Message):
    """Handle any other commands during photo upload."""
    await message.answer(
        "⚠️ Rasm yuklash jarayonida. Bekor qilish uchun /cancel yuboring yoki rasm yuboring."
    )


@router.message(PortfolioStates.waiting_for_photo)
async def invalid_photo_upload(message: Message):
    """Handle non-photo messages during photo upload state."""
    if message.photo:
        # This shouldn't happen as F.photo handler should catch it, but just in case
        return
    await message.answer("⚠️ Iltimos, rasm yuboring. Bekor qilish uchun /cancel deb yozing.")


@router.callback_query(F.data.startswith("appt:block:"))
async def block_client(callback: CallbackQuery, session: AsyncSession):
    appt_id = int(callback.data.split(":")[2])
    from database.models import Blacklist
    
    appt = await session.get(Appointment, appt_id)
    if not appt:
        await callback.answer("Uchrashuv topilmadi.", show_alert=True)
        return
    
    # Check if already blocked
    from sqlalchemy import and_
    stmt = select(Blacklist).where(
        and_(
            Blacklist.barber_id == appt.barber_id,
            Blacklist.client_id == appt.client_id
        )
    )
    existing = (await session.execute(stmt)).scalar()
    if existing:
        await callback.answer("⚠️ Ushbu mijoz allaqachon bloklangan.", show_alert=True)
        return
        
    new_block = Blacklist(
        barber_id=appt.barber_id,
        client_id=appt.client_id,
        reason=f"Appointment #{appt_id} context"
    )
    session.add(new_block)
    await session.commit()
    
    await callback.answer("🚫 Mijoz qora ro'yxatga qo'shildi!", show_alert=True)


# ──────────────────────────────────────────────
# Blacklist management from main menu
# ──────────────────────────────────────────────

@router.message(F.text.in_({"🚫 Qora ro'yxat", "🚫 Черный список"}))
async def blacklist_menu(message: Message, session: AsyncSession):
    user, profile = await ensure_barber(session, message.from_user.id)
    if not user or not profile:
        await message.answer("Bu bo'lim faqat sartaroshlar uchun.")
        return

    from database.models import Blacklist
    stmt = select(Blacklist).where(Blacklist.barber_id == profile.id)
    result = await session.execute(stmt)
    blocked = result.scalars().all()

    count = len(blocked)
    text = (
        f"🚫 <b>Qora ro'yxat</b>\n\n"
        f"Bloklangan mijozlar: <b>{count}</b> ta\n\n"
        "Mijozlarni qo'shish yoki ro'yxatni ko'rish uchun tugmalardan foydalaning:"
    )
    from keyboards import kb_blacklist_main
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb_blacklist_main(has_entries=count > 0)
    )


@router.callback_query(F.data == "blacklist:add")
async def blacklist_add_start(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    # Get unique clients from this barber's appointments
    stmt = (
        select(Appointment.client_id)
        .where(Appointment.barber_id == profile.id)
        .distinct()
    )
    result = await session.execute(stmt)
    client_ids = [r for r in result.scalars().all()]

    if not client_ids:
        await callback.answer("Sizda hali mijozlar yo'q.", show_alert=True)
        return

    # Exclude already blocked
    from database.models import Blacklist
    stmt_blk = select(Blacklist.client_id).where(
        Blacklist.barber_id == profile.id,
        Blacklist.client_id.in_(client_ids)
    )
    res_blk = await session.execute(stmt_blk)
    blocked_ids = {r for r in res_blk.scalars().all()}

    available = [cid for cid in client_ids if cid not in blocked_ids]
    if not available:
        await callback.answer("Barcha mijozlar allaqachon bloklangan.", show_alert=True)
        return

    # Fetch names
    stmt_users = select(User).where(User.id.in_(available))
    res_users = await session.execute(stmt_users)
    users = res_users.scalars().all()
    clients = [(u.id, u.first_name or str(u.id)) for u in users]

    from keyboards import kb_blacklist_add
    await callback.message.edit_text(
        "🚫 <b>Bloklash uchun mijoz tanlang:</b>\n\n"
        "Quyida sizga uchrashuv qilgan mijozlar ro'yxati:",
        parse_mode="HTML",
        reply_markup=kb_blacklist_add(clients)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("blacklist:add:"))
async def blacklist_add_client(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    client_id = int(callback.data.split(":")[2])

    from database.models import Blacklist
    from sqlalchemy import and_
    stmt = select(Blacklist).where(
        and_(
            Blacklist.barber_id == profile.id,
            Blacklist.client_id == client_id
        )
    )
    existing = (await session.execute(stmt)).scalar()
    if existing:
        await callback.answer("⚠️ Mijoz allaqachon bloklangan.", show_alert=True)
        return

    new_block = Blacklist(
        barber_id=profile.id,
        client_id=client_id,
        reason="Qo'lda qora ro'yxatga qo'shildi"
    )
    session.add(new_block)
    await session.commit()

    await callback.answer("🚫 Mijoz qora ro'yxatga qo'shildi!", show_alert=True)
    # Refresh menu
    from keyboards import kb_blacklist_main
    await callback.message.edit_reply_markup(
        reply_markup=kb_blacklist_main(has_entries=True)
    )


@router.callback_query(F.data.startswith("blacklist:remove:"))
async def blacklist_remove_client(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    client_id = int(callback.data.split(":")[2])

    from database.models import Blacklist
    from sqlalchemy import and_
    stmt = select(Blacklist).where(
        and_(
            Blacklist.barber_id == profile.id,
            Blacklist.client_id == client_id
        )
    )
    entry = (await session.execute(stmt)).scalar()
    if not entry:
        await callback.answer("⚠️ Topilmadi.", show_alert=True)
        return

    await session.delete(entry)
    await session.commit()
    await callback.answer("✅ Mijoz blokdan chiqarildi.", show_alert=True)

    # Refresh list view
    stmt_all = select(Blacklist).where(Blacklist.barber_id == profile.id)
    result = await session.execute(stmt_all)
    blocked = result.scalars().all()

    if not blocked:
        from keyboards import kb_blacklist_main
        await callback.message.edit_text(
            "🚫 <b>Qora ro'yxat bo'sh.</b>",
            parse_mode="HTML",
            reply_markup=kb_blacklist_main(has_entries=False)
        )
        return

    text = "🚫 <b>Bloklangan mijozlar</b>\n\nChiqarish uchun quyidagi tugmalardan birini bosing:"
    clients = []
    for b in blocked:
        client = await session.get(User, b.client_id)
        name = client.first_name if client else str(b.client_id)
        clients.append((b.client_id, name))

    from keyboards import kb_blacklist_list
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb_blacklist_list(clients)
    )


@router.callback_query(F.data == "blacklist:list")
async def blacklist_list(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    from database.models import Blacklist
    stmt = select(Blacklist).where(Blacklist.barber_id == profile.id)
    result = await session.execute(stmt)
    blocked = result.scalars().all()

    if not blocked:
        from keyboards import kb_blacklist_main
        await callback.message.edit_text(
            "🚫 <b>Qora ro'yxat bo'sh.</b>",
            parse_mode="HTML",
            reply_markup=kb_blacklist_main(has_entries=False)
        )
        await callback.answer()
        return

    text = "🚫 <b>Bloklangan mijozlar</b>\n\nChiqarish uchun quyidagi tugmalardan birini bosing:"
    clients = []
    for b in blocked:
        client = await session.get(User, b.client_id)
        name = client.first_name if client else str(b.client_id)
        clients.append((b.client_id, name))

    from keyboards import kb_blacklist_list
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb_blacklist_list(clients)
    )
    await callback.answer()


@router.callback_query(F.data == "blacklist:back")
async def blacklist_back(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    from database.models import Blacklist
    stmt = select(Blacklist).where(Blacklist.barber_id == profile.id)
    result = await session.execute(stmt)
    blocked = result.scalars().all()

    from keyboards import kb_blacklist_main
    await callback.message.edit_text(
        f"🚫 <b>Qora ro'yxat</b>\n\nBloklangan mijozlar: <b>{len(blocked)}</b> ta",
        parse_mode="HTML",
        reply_markup=kb_blacklist_main(has_entries=len(blocked) > 0)
    )
    await callback.answer()


# Statistics
# ──────────────────────────────────────────────

@router.message(F.text.in_({"📊 Statistika", "📊 Статистика"}))
async def barber_stats(message: Message, session: AsyncSession):
    user, profile = await ensure_barber(session, message.from_user.id)
    if not user or not profile:
        await message.answer("Bu bo'lim faqat sartaroshlar uchun.")
        return

    today = datetime.date.today()
    month_start = today.replace(day=1)

    # Count by status
    stmt_status = (
        select(Appointment.status, func.count(Appointment.id))
        .where(Appointment.barber_id == profile.id)
        .group_by(Appointment.status)
    )
    result_status = await session.execute(stmt_status)
    status_counts = {str(s): c for s, c in result_status.all()}

    total = sum(status_counts.values())
    pending = status_counts.get("pending", 0)
    confirmed = status_counts.get("confirmed", 0)
    completed = status_counts.get("completed", 0)
    cancelled = status_counts.get("cancelled", 0)

    # Completed this month
    stmt_month = select(func.count(Appointment.id)).where(
        Appointment.barber_id == profile.id,
        Appointment.appointment_date >= month_start,
        Appointment.status == AppointmentStatus.COMPLETED,
    )
    month_count = (await session.execute(stmt_month)).scalar() or 0

    # Pending/confirmed today
    stmt_today = select(func.count(Appointment.id)).where(
        Appointment.barber_id == profile.id,
        Appointment.appointment_date == today,
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
    )
    today_count = (await session.execute(stmt_today)).scalar() or 0

    # Build keyboard with stats and reviews buttons
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐ Sharhlarni ko'rish", callback_data="reviews:list")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Batafsil hisobot", callback_data="stats:detailed")
    )

    await message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"📋 <b>Jami uchrashuvlar:</b> {total}\n"
        f"  🕐 Kutilmoqda: {pending}\n"
        f"  ✅ Tasdiqlangan: {confirmed}\n"
        f"  ✔️ Bajarilgan: {completed}\n"
        f"  ❌ Bekor qilingan: {cancelled}\n\n"
        f"📅 <b>Bugun:</b> {today_count}\n"
        f"✔️ <b>Bu oy bajarilgan:</b> {month_count}\n\n"
        f"⭐ <b>Reyting:</b> {profile.rating:.1f} ({profile.review_count} sharh)",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "reviews:list")
async def view_reviews(callback: CallbackQuery, session: AsyncSession):
    """Show all reviews for barber with visibility toggle."""
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    from database.models import Review
    stmt = (
        select(Review)
        .where(Review.barber_id == profile.id)
        .order_by(Review.created_at.desc())
        .limit(10)
    )
    result = await session.execute(stmt)
    reviews = result.scalars().all()

    if not reviews:
        await callback.message.edit_text(
            "⭐ <b>Sharhlar</b>\n\nHozircha sharhlar yo'q.",
            reply_markup=kb_main_menu_barber()
        )
        await callback.answer()
        return

    visible_count = sum(1 for r in reviews if r.is_visible)

    text = f"⭐ <b>Barcha sharhlar</b> ({visible_count}/{len(reviews)} ko'rinadi)\n\n"
    for r in reviews:
        stars = "⭐" * r.rating
        client_name = r.client.first_name if r.client else "Mijoz"
        comment = f"\n💬 {r.comment[:80]}..." if r.comment and len(r.comment) > 80 else f"\n💬 {r.comment}" if r.comment else ""
        eye = "👁" if r.is_visible else "🚫"
        text += f"{eye} {stars} <b>{r.rating}</b> — {client_name}\n🗓 {r.created_at.strftime('%d.%m.%Y')}{comment}\n\n"

    text += f"📈 Umumiy reyting: <b>{profile.rating:.1f}</b>\n\n<i>Sharhni yashirish/ko'rsatish uchun quyidagi tugmalardan foydalaning:</i>"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    for r in reviews[:5]:
        eye = "👁 Yashirish" if r.is_visible else "👁 Ko'rsatish"
        builder.row(
            InlineKeyboardButton(
                text=f"{eye} #{r.id}",
                callback_data=f"review:toggle:{r.id}"
            )
        )

    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back"))

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("review:toggle:"))
async def toggle_review_visibility(callback: CallbackQuery, session: AsyncSession):
    """Toggle is_visible for a review."""
    review_id = int(callback.data.split(":")[2])
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    from database.models import Review
    review = await session.get(Review, review_id)
    if not review or review.barber_id != profile.id:
        await callback.answer("Sharh topilmadi.", show_alert=True)
        return

    review.is_visible = not review.is_visible
    await session.commit()

    status = "ko'rinadi" if review.is_visible else "yashirildi"
    await callback.answer(f"Sharh {status}!")

    # Refresh the reviews list
    await view_reviews(callback, session)


@router.callback_query(F.data == "stats:detailed")
async def detailed_stats(callback: CallbackQuery, session: AsyncSession):
    """Show detailed monthly statistics."""
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    import datetime
    from collections import Counter

    # Get last 30 days completed appointments
    month_ago = datetime.date.today() - datetime.timedelta(days=30)
    stmt = (
        select(Appointment)
        .where(
            Appointment.barber_id == profile.id,
            Appointment.status == AppointmentStatus.COMPLETED,
            Appointment.appointment_date >= month_ago
        )
    )
    result = await session.execute(stmt)
    appointments = result.scalars().all()

    if not appointments:
        await callback.message.edit_text(
            "📊 <b>So'nggi 30 kunlik hisobot</b>\n\n"
            "Bajarilgan uchrashuvlar yo'q.",
            reply_markup=kb_main_menu_barber()
        )
        await callback.answer()
        return

    # Calculate stats
    total_revenue = sum([a.service.price for a in appointments if a.service])
    daily_counts = Counter([a.appointment_date.weekday() for a in appointments])
    most_busy_day = max(daily_counts.items(), key=lambda x: x[1])
    day_names = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

    # Get most popular service
    service_counts = Counter([a.service.name for a in appointments if a.service])
    most_popular = service_counts.most_common(1)[0] if service_counts else ("Noma'lum", 0)

    text = (
        f"📊 <b>So'nggi 30 kunlik hisobot</b>\n\n"
        f"✔️ <b>Bajarilgan uchrashuvlar:</b> {len(appointments)}\n"
        f"💰 <b>Taxminiy daromad:</b> {total_revenue:,} so'm\n\n"
        f"📈 <b>Eng mashhur xizmat:</b>\n"
        f"   {most_popular[0]} ({most_popular[1]} marta)\n\n"
        f"📅 <b>Eng band kun:</b>\n"
        f"   {day_names[most_busy_day[0]]} ({most_busy_day[1]} uchrashuv)\n\n"
        f"⭐ <b>Reyting:</b> {profile.rating:.1f} ({profile.review_count} sharh)"
    )

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb_main_menu_barber())
    await callback.answer()


@router.message(F.text.in_({"🖼 Portfoliom", "🖼 Портфолио"}))
async def view_portfolio_menu(message: Message, session: AsyncSession):
    user, profile = await ensure_barber(session, message.from_user.id)
    if not profile:
        return

    from database.models import PortfolioItem
    stmt = select(PortfolioItem).where(PortfolioItem.barber_id == profile.id)
    result = await session.execute(stmt)
    items = result.scalars().all()

    count = len(items)
    text = (
        f"🖼 <b>Portfolio</b>\n\n"
        f"Yuklangan ishlaringiz: <b>{count}</b> ta\n\n"
        "Yangi ish qo'shish yoki mavjudlarni ko'rish uchun tugmalardan foydalaning:"
    )
    from keyboards import kb_portfolio_main
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb_portfolio_main(has_items=count > 0)
    )


@router.callback_query(F.data == "portfolio:add")
async def portfolio_add_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PortfolioStates.waiting_for_photo)
    await callback.message.edit_text(
        "📸 <b>Yangi ish qo'shish</b>\n\n"
        "Iltimos, portfolio uchun rasm yuboring:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(PortfolioStates.waiting_for_photo, F.photo)
async def portfolio_add_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(portfolio_file_id=photo.file_id)
    await state.set_state(PortfolioStates.waiting_for_title)
    await message.answer(
        "✅ Rasm qabul qilindi!\n\n"
        "Endi ish sarlavhasini kiriting (masalan: <b>Erkcha soch turmak</b>):",
        parse_mode="HTML"
    )


@router.message(PortfolioStates.waiting_for_title, Command("cancel"))
async def portfolio_title_cancel(message: Message, state: FSMContext):
    """Cancel portfolio item creation at title step."""
    await state.clear()
    await message.answer("❌ Portfolio ish qo'shish bekor qilindi.", reply_markup=kb_main_menu_barber())


@router.message(PortfolioStates.waiting_for_title)
async def portfolio_add_title(message: Message, state: FSMContext):
    await state.update_data(portfolio_title=message.text)
    await state.set_state(PortfolioStates.waiting_for_description)
    await message.answer(
        "📝 <b>Tavsif qo'shish</b> (ixtiyoriy):\n\n"
        "Ish haqida qisqa tavsif yozing yoki o'tkazib yuborish uchun «O'tkazib yuborish» tugmasini bosing.",
        reply_markup=kb_skip_cancel()
    )


@router.message(PortfolioStates.waiting_for_description, Command("cancel"))
async def portfolio_description_cancel(message: Message, state: FSMContext):
    """Cancel portfolio item creation at description step."""
    await state.clear()
    await message.answer("❌ Portfolio ish qo'shish bekor qilindi.", reply_markup=kb_main_menu_barber())


@router.message(PortfolioStates.waiting_for_description, F.text == "⏩ O'tkazib yuborish")
async def portfolio_skip_description(message: Message, state: FSMContext, session: AsyncSession):
    await _save_portfolio_item(message, state, session, description=None)


@router.message(PortfolioStates.waiting_for_description)
async def portfolio_add_description(message: Message, state: FSMContext, session: AsyncSession):
    await _save_portfolio_item(message, state, session, description=message.text)


async def _save_portfolio_item(message: Message, state: FSMContext, session: AsyncSession, description: str | None):
    data = await state.get_data()
    user, profile = await ensure_barber(session, message.from_user.id)
    if not profile:
        await message.answer("Profil topilmadi.")
        await state.clear()
        return

    from database.models import PortfolioItem
    item = PortfolioItem(
        barber_id=profile.id,
        file_id=data["portfolio_file_id"],
        title=data.get("portfolio_title"),
        description=description,
    )
    session.add(item)
    await session.commit()
    await state.clear()

    await message.answer(
        "✅ <b>Portfolio muvaffaqiyatli qo'shildi!</b>",
        parse_mode="HTML",
        reply_markup=kb_main_menu_barber()
    )


@router.callback_query(F.data == "portfolio:list")
async def portfolio_list(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    from database.models import PortfolioItem
    stmt = select(PortfolioItem).where(PortfolioItem.barber_id == profile.id).order_by(PortfolioItem.created_at.desc())
    result = await session.execute(stmt)
    items = result.scalars().all()

    if not items:
        from keyboards import kb_portfolio_main
        await callback.message.edit_text(
            "😔 Portfolio bo'sh.",
            reply_markup=kb_portfolio_main(has_items=False)
        )
        await callback.answer()
        return

    # Show first item with details and navigation
    item = items[0]
    text = _format_portfolio_item(item, 1, len(items))
    from keyboards import kb_portfolio_item
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=item.file_id,
        caption=text,
        parse_mode="HTML",
        reply_markup=kb_portfolio_item(item.id)
    )
    await callback.answer()


def _format_portfolio_item(item, current: int, total: int) -> str:
    title = item.title or "📸 Portfolio ishi"
    desc = f"\n📝 {item.description}\n" if item.description else ""
    return (
        f"<b>{title}</b>{desc}\n"
        f"📅 {item.created_at.strftime('%d.%m.%Y')}\n"
        f"— {current} / {total} —"
    )


@router.callback_query(F.data.startswith("portfolio:delete:"))
async def portfolio_delete(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    item_id = int(callback.data.split(":")[2])
    from database.models import PortfolioItem
    stmt = select(PortfolioItem).where(
        PortfolioItem.id == item_id,
        PortfolioItem.barber_id == profile.id
    )
    item = (await session.execute(stmt)).scalar()
    if not item:
        await callback.answer("Topilmadi.", show_alert=True)
        return

    await session.delete(item)
    await session.commit()
    await callback.answer("🗑 O'chirildi.", show_alert=True)

    # Refresh list
    stmt_all = select(PortfolioItem).where(PortfolioItem.barber_id == profile.id)
    result = await session.execute(stmt_all)
    items = result.scalars().all()

    from keyboards import kb_portfolio_main
    if not items:
        await callback.message.edit_text(
            "😔 Portfolio bo'sh.",
            reply_markup=kb_portfolio_main(has_items=False)
        )
    else:
        await callback.message.edit_text(
            f"🖼 <b>Portfolio</b>\n\nYuklangan ishlaringiz: <b>{len(items)}</b> ta",
            parse_mode="HTML",
            reply_markup=kb_portfolio_main(has_items=True)
        )


@router.callback_query(F.data == "barber:work_days")
async def edit_work_days(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile: return
    
    # Get current working days
    stmt = select(BarberSchedule).where(
        BarberSchedule.barber_id == profile.id,
        BarberSchedule.is_working == True
    )
    res = await session.execute(stmt)
    working_days = {s.day_of_week.value for s in res.scalars().all()}
    
    from keyboards import kb_work_days
    await callback.message.edit_text(
        "📅 <b>Ish kunlarini tanlang:</b>\n\n"
        "Tugmalarni bosish orqali ish kunlarini yoqishingiz yoki o'chirishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=kb_work_days(working_days)
    )


@router.callback_query(F.data.startswith("wd:toggle:"))
async def toggle_work_day(callback: CallbackQuery, session: AsyncSession):
    day_name = callback.data.split(":")[2]
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile: return
    
    stmt = select(BarberSchedule).where(
        BarberSchedule.barber_id == profile.id,
        BarberSchedule.day_of_week == day_name
    )
    sched = (await session.execute(stmt)).scalar()
    
    if sched:
        sched.is_working = not sched.is_working
    else:
        sched = BarberSchedule(
            barber_id=profile.id,
            day_of_week=day_name,
            is_working=True
        )
        session.add(sched)
    
    await session.commit()
    
    # Refresh view
    stmt_all = select(BarberSchedule).where(
        BarberSchedule.barber_id == profile.id,
        BarberSchedule.is_working == True
    )
    res = await session.execute(stmt_all)
    working_days = {s.day_of_week.value for s in res.scalars().all()}
    
    from keyboards import kb_work_days
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_reply_markup(reply_markup=kb_work_days(working_days))
    except TelegramBadRequest:
        pass
    await callback.answer()


@router.callback_query(F.data == "barber:work_hours")
async def edit_work_hours(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🕒 <b>Ish vaqtini kiriting</b>\n\n"
        "Masalan: <code>09:00-20:00</code>\n"
        "(Format: HH:MM-HH:MM)",
        parse_mode="HTML"
    )
    await state.set_state(BarberProfileStates.waiting_for_work_hours)
    await callback.answer()


@router.message(BarberProfileStates.waiting_for_work_hours)
async def save_work_hours(message: Message, state: FSMContext, session: AsyncSession):
    text = message.text.strip()
    try:
        from datetime import time
        start_str, end_str = text.split("-")
        start_time = time.fromisoformat(start_str.strip())
        end_time = time.fromisoformat(end_str.strip())
        
        user, profile = await ensure_barber(session, message.from_user.id)
        profile.work_start = start_time
        profile.work_end = end_time
        await session.commit()
        
        await state.clear()
        await message.answer(
            f"✅ Ish vaqti saqlandi: <b>{start_str}-{end_str}</b>",
            parse_mode="HTML",
            reply_markup=kb_main_menu_barber()
        )
    except Exception:
        await message.answer("⚠️ Noto'g'ri format. Iltimos, 09:00-20:00 formatida yuboring.")


@router.callback_query(F.data == "barber:subscription")
async def manage_subscription(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile: return
    
    status = "✅ Faol" if profile.subscription_active else "❌ Faol emas"
    until = profile.subscription_until.strftime("%d.%m.%Y") if profile.subscription_until else "—"
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Obunani yangilash (100,000 so'm)", callback_data="barber:pay_subscription"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="barber:settings"))
    
    await callback.message.edit_text(
        f"💳 <b>Obuna holati:</b> {status}\n"
        f"📅 Muddat: {until}\n\n"
        "Obuna bo'lish orqali barcha premium funksiyalardan cheksiz foydalanishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "barber:pay_subscription")
async def pay_subscription(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    price = config.SUBSCRIPTION_PRICE  # so'm
    order_id = f"sub_{callback.from_user.id}_{int(datetime.datetime.now().timestamp())}"

    builder = InlineKeyboardBuilder()

    # Click
    if config.CLICK_MERCHANT_ID:
        click_url = (
            f"https://my.click.uz/services/pay?"
            f"service_id={config.CLICK_MERCHANT_ID}&"
            f"merchant_id={config.CLICK_MERCHANT_ID}&"
            f"amount={price}&"
            f"transaction_param={order_id}"
        )
        builder.row(InlineKeyboardButton(text="💳 Click orqali to'lash", url=click_url))

    # Payme
    if config.PAYME_MERCHANT_ID:
        payme_amount = price * 100  # tiyin
        payme_url = f"https://checkout.paycom.uz/{config.PAYME_MERCHANT_ID}?amount={payme_amount}"
        builder.row(InlineKeyboardButton(text="💳 Payme orqali to'lash", url=payme_url))

    # Fallback if no merchant configured
    if not config.CLICK_MERCHANT_ID and not config.PAYME_MERCHANT_ID:
        builder.row(InlineKeyboardButton(text="📩 Admin bilan bog'lanish", url=f"tg://user?id={config.ADMIN_ID}"))

    builder.row(InlineKeyboardButton(text="✅ To'lovni tasdiqladim", callback_data=f"sub_confirm:{order_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="barber:subscription"))

    await callback.message.edit_text(
        f"💳 <b>To'lov uchun yo'nalishlar</b>\n\n"
        f"Obuna narxi: <b>{price:,} so'm</b>\n"
        f"Buyurtma raqami: <code>{order_id}</code>\n\n"
        f"1. Quyidagi tugmalardan birini tanlang va to'lovni amalga oshiring.\n"
        f"2. To'lovdan so'ng <b>«✅ To'lovni tasdiqladim»</b> tugmasini bosing.\n"
        f"3. Admin to'lovni tekshirib, obunangizni faollashtiradi.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub_confirm:"))
async def confirm_subscription_payment(callback: CallbackQuery, session: AsyncSession):
    order_id = callback.data.split(":", 1)[1]
    user = await session.get(User, callback.from_user.id)
    if not user or not user.barber_profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    await callback.answer("✅ So'rovingiz adminlarga yuborildi. Tez orada obunangiz faollashtiriladi.", show_alert=True)

    # Notify admin
    try:
        await callback.bot.send_message(
            config.ADMIN_ID,
            f"🆕 <b>Yangi to'lov so'rovi</b>\n\n"
            f"👤 Foydalanuvchi: <b>{user.first_name}</b>\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"💰 Summa: {config.SUBSCRIPTION_PRICE:,} so'm\n"
            f"📋 Buyurtma: <code>{order_id}</code>\n\n"
            f"Faollashtirish uchun:\n"
            f"<code>/activate_sub {user.id}</code>",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.message(F.successful_payment)
async def process_sub_payment(message: Message, session: AsyncSession):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("sub:"):
        user_id = int(payload.split(":")[1])
        user = await session.get(User, user_id)
        if user and user.barber_profile:
            p = user.barber_profile
            p.subscription_active = True

            from datetime import timedelta, date
            start_date = p.subscription_until if (p.subscription_until and p.subscription_until > date.today()) else date.today()
            p.subscription_until = start_date + timedelta(days=30)
            await session.commit()

            await message.answer(
                f"✅ <b>Obuna muvaffaqiyatli yangilandi!</b>\n"
                f"📅 Yangi muddat: {p.subscription_until.strftime('%d.%m.%Y')}",
                parse_mode="HTML",
                reply_markup=kb_main_menu_barber()
            )


# ──────────────────────────────────────────────
# Chat with clients
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("chat:client:"))
async def start_chat_with_client(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    appt_id = int(callback.data.split(":")[2])
    appt = await session.get(Appointment, appt_id)
    if not appt:
        await callback.answer("Uchrashuv topilmadi.", show_alert=True)
        return
    await state.update_data(chat_target_client=appt.client_id, chat_appt_id=appt_id)
    await state.set_state(ChatStates.waiting_for_message_to_client)
    await callback.message.edit_text(
        "📩 <b>Mijozga xabar yozish</b>\n\n"
        f"Buyurtma #{appt_id} bo'yicha mijozga xabar yuboring\n"
        "(yoki bekor qilish uchun /cancel):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ChatStates.waiting_for_message_to_client, Command("cancel"))
async def cancel_chat_with_client(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Xabar yuborish bekor qilindi.", reply_markup=kb_main_menu_barber())


@router.message(ChatStates.waiting_for_message_to_client)
async def send_message_to_client(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    client_id = data.get("chat_target_client")
    if not client_id:
        await message.answer("Xatolik: Mijoz tanlanmagan.", reply_markup=kb_main_menu_barber())
        await state.clear()
        return

    client = await session.get(User, client_id)
    if not client:
        await message.answer("Xatolik: Mijoz topilmadi.", reply_markup=kb_main_menu_barber())
        await state.clear()
        return

    barber = await session.get(User, message.from_user.id)
    appt_id = data.get("chat_appt_id")
    appt_text = f"Buyurtma #{appt_id} bo'yicha" if appt_id else ""

    # Forward message to client
    try:
        await message.bot.send_message(
            client_id,
            f"📨 <b>Yangi xabar sartaroshdan</b>\n\n"
            f"✂️ {barber.first_name}\n"
            f"{appt_text}\n\n"
            f"<i>{message.text}</i>",
            parse_mode="HTML",
            reply_markup=kb_chat_reply(barber.id, is_barber=False)
        )
        await message.answer(
            f"✅ Xabaringiz mijozga yuborildi!\n\n"
            f"Javobni kuting...",
            reply_markup=kb_main_menu_barber()
        )
    except Exception:
        await message.answer(
            "❌ Xatolik: Xabar yuborilmadi. Mijoz botni bloklagan bo'lishi mumkin.",
            reply_markup=kb_main_menu_barber()
        )

    await state.clear()


@router.callback_query(F.data.startswith("reply:client:"))
async def reply_to_client_start(callback: CallbackQuery, state: FSMContext):
    client_id = int(callback.data.split(":")[2])
    await state.update_data(chat_target_client=client_id)
    await state.set_state(ChatStates.waiting_for_message_to_client)
    await callback.message.edit_text(
        "📩 <b>Mijozga javob yozish</b>\n\n"
        "Xabaringizni yozing (yoki bekor qilish uchun /cancel):",
        parse_mode="HTML",
        reply_markup=None
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Advertisement / Promotional messages
# ──────────────────────────────────────────────

@router.message(F.text.in_({"📢 Reklama yuborish", "📢 Реклама"}))
async def advertisement_menu(message: Message, session: AsyncSession):
    user, profile = await ensure_barber(session, message.from_user.id)
    if not profile:
        return

    await message.answer(
        "📢 <b>Reklama boshqaruvi</b>\n\n"
        "Mijozlarga reklama xabarlar yuborish, promo kodlar yaratish va statistikani ko'rish:",
        parse_mode="HTML",
        reply_markup=kb_advertisement_menu()
    )


@router.callback_query(F.data == "ad:send_clients")
async def advertisement_target_select(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdvertisementStates.waiting_for_ad_target)
    await callback.message.edit_text(
        "📢 <b>Reklama yuborish</b>\n\n"
        "Qaysi mijozlarga reklama yubormoqchisiz?",
        parse_mode="HTML",
        reply_markup=kb_ad_target_selection()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ad_target:"))
async def advertisement_target_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    target = callback.data.split(":")[1]
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    # Get target client count
    if target == "all":
        stmt = select(Appointment).where(Appointment.barber_id == profile.id).distinct(Appointment.client_id)
        result = await session.execute(stmt)
        clients = result.scalars().all()
        target_ids = list(set([a.client_id for a in clients]))
    elif target == "past":
        stmt = select(Appointment).where(
            Appointment.barber_id == profile.id,
            Appointment.status == AppointmentStatus.COMPLETED
        ).distinct(Appointment.client_id)
        result = await session.execute(stmt)
        clients = result.scalars().all()
        target_ids = list(set([a.client_id for a in clients]))
    elif target == "returning":
        stmt = select(Appointment).where(
            Appointment.barber_id == profile.id,
            Appointment.status == AppointmentStatus.COMPLETED
        )
        result = await session.execute(stmt)
        all_clients = result.scalars().all()
        from collections import Counter
        client_counts = Counter([a.client_id for a in all_clients])
        target_ids = [cid for cid, count in client_counts.items() if count >= 2]
    else:
        target_ids = []

    await state.update_data(ad_target_ids=target_ids, ad_target_type=target)
    await state.set_state(AdvertisementStates.waiting_for_ad_content)

    target_names = {
        "all": "Barcha mijozlar",
        "past": "Uchrashuv qilganlar",
        "returning": "Qayta mijozlar"
    }

    await callback.message.edit_text(
        f"📢 <b>Reklama yuborish</b>\n\n"
        f"Maqsad: <b>{target_names.get(target, 'Noma\'lum')}</b>\n"
        f"Qabul qiluvchilar: <b>{len(target_ids)}</b> ta\n\n"
        f"Endi reklama matnini yozing:\n"
        f"(yoki bekor qilish uchun /cancel)",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdvertisementStates.waiting_for_ad_content, Command("cancel"))
async def advertisement_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Reklama yuborish bekor qilindi.", reply_markup=kb_main_menu_barber())


@router.message(AdvertisementStates.waiting_for_ad_content)
async def advertisement_send(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    target_ids = data.get("ad_target_ids", [])

    if not target_ids:
        await message.answer("❌ Mijozlar ro'yxati bo'sh.", reply_markup=kb_main_menu_barber())
        await state.clear()
        return

    user, profile = await ensure_barber(session, message.from_user.id)
    barber_name = profile.salon_name or user.first_name

    sent_count = 0
    failed_count = 0

    for client_id in target_ids:
        try:
            await message.bot.send_message(
                client_id,
                f"📢 <b>Reklama</b> — {barber_name}\n\n"
                f"{message.text}\n\n"
                f"<i>Reklama xabarini ko'rish uchun /start buyrug'ini yuboring</i>",
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception:
            failed_count += 1

    await message.answer(
        f"✅ <b>Reklama yuborildi!</b>\n\n"
        f"📤 Yuborildi: {sent_count} ta\n"
        f"❌ Muvaffaqiyatsiz: {failed_count} ta",
        reply_markup=kb_main_menu_barber()
    )
    await state.clear()


@router.callback_query(F.data == "ad:promo_code")
async def promo_code_menu(callback: CallbackQuery, session: AsyncSession):
    """Show promo code management menu."""
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    from database.models import PromoCode
    stmt = select(PromoCode).where(PromoCode.barber_id == profile.id).order_by(PromoCode.created_at.desc())
    result = await session.execute(stmt)
    promo_codes = result.scalars().all()

    active_count = len([p for p in promo_codes if p.is_active])
    total_used = sum([p.used_count for p in promo_codes])

    await callback.message.edit_text(
        f"🎁 <b>Promo kodlar boshqaruvi</b>\n\n"
        f"📊 Jami kodlar: <b>{len(promo_codes)}</b>\n"
        f"✅ Aktiv: <b>{active_count}</b>\n"
        f"🎯 Jami foydalanish: <b>{total_used}</b>\n\n"
        f"Yangi promo kod yaratish yoki mavjudlarni boshqarish:",
        parse_mode="HTML",
        reply_markup=kb_promo_menu(promo_codes)
    )
    await callback.answer()


@router.callback_query(F.data == "promo:list")
async def promo_code_list(callback: CallbackQuery, session: AsyncSession):
    """Refresh promo code list."""
    await promo_code_menu(callback, session)


@router.callback_query(F.data == "promo:create")
async def promo_create_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new promo code."""
    await state.set_state(AdvertisementStates.waiting_for_promo_code)
    await callback.message.edit_text(
        "🎁 <b>Yangi promo kod yaratish</b>\n\n"
        "Promo kod matnini kiriting (masalan: SALE20, SUMMER2024):\n"
        "(yoki bekor qilish uchun /cancel)",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdvertisementStates.waiting_for_promo_code, Command("cancel"))
async def promo_create_cancel(message: Message, state: FSMContext):
    """Cancel promo code creation."""
    await state.clear()
    await message.answer("❌ Promo kod yaratish bekor qilindi.", reply_markup=kb_main_menu_barber())


@router.message(AdvertisementStates.waiting_for_promo_code)
async def promo_code_entered(message: Message, state: FSMContext, session: AsyncSession):
    """Process promo code text and ask for discount percent."""
    code = message.text.strip().upper()

    # Validate code format
    if not code.isalnum() or len(code) < 3 or len(code) > 20:
        await message.answer(
            "❌ Noto'g'ri format. Promo kod:\n"
            "• Kamida 3 ta belgi\n"
            "• Ko'pi bilan 20 ta belgi\n"
            "• Faqat harf va raqamlar\n\n"
            "Qayta kiriting:"
        )
        return

    # Check if code already exists for this barber
    user, profile = await ensure_barber(session, message.from_user.id)
    if not profile:
        return

    from database.models import PromoCode
    stmt = select(PromoCode).where(
        PromoCode.barber_id == profile.id,
        PromoCode.code == code
    )
    existing = (await session.execute(stmt)).scalar()
    if existing:
        await message.answer(
            "❌ Bu promo kod allaqachon mavjud. Boshqa kod kiriting:\n"
            "(yoki bekor qilish uchun /cancel)"
        )
        return

    await state.update_data(promo_code=code)
    await state.set_state(AdvertisementStates.waiting_for_promo_percent)

    await message.answer(
        f"✅ Promo kod: <b>{code}</b>\n\n"
        f"Endi chegirma foizini kiriting (masalan: 10, 20, 25):\n"
        f"(yoki bekor qilish uchun /cancel)",
        parse_mode="HTML"
    )


@router.message(AdvertisementStates.waiting_for_promo_percent, Command("cancel"))
async def promo_percent_cancel(message: Message, state: FSMContext):
    """Cancel promo code creation at percent step."""
    await state.clear()
    await message.answer("❌ Promo kod yaratish bekor qilindi.", reply_markup=kb_main_menu_barber())


@router.message(AdvertisementStates.waiting_for_promo_percent)
async def promo_percent_entered(message: Message, state: FSMContext):
    """Process discount percent and ask for max uses."""
    try:
        percent = int(message.text.strip())
        if percent < 1 or percent > 100:
            raise ValueError("Invalid range")
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format. 1 dan 100 gacha butun son kiriting:\n"
            "(yoki bekor qilish uchun /cancel)"
        )
        return

    await state.update_data(promo_percent=percent)
    await state.set_state(AdvertisementStates.waiting_for_promo_max_uses)

    await message.answer(
        f"✅ Chegirma: <b>{percent}%</b>\n\n"
        f"Promo kod necha marta ishlatilishi mumkin?\n"
        f"(masalan: 10, 50, 100, yoki cheksiz uchun 999):\n"
        f"(yoki bekor qilish uchun /cancel)",
        parse_mode="HTML"
    )


@router.message(AdvertisementStates.waiting_for_promo_max_uses, Command("cancel"))
async def promo_max_uses_cancel(message: Message, state: FSMContext):
    """Cancel promo code creation at max uses step."""
    await state.clear()
    await message.answer("❌ Promo kod yaratish bekor qilindi.", reply_markup=kb_main_menu_barber())


@router.message(AdvertisementStates.waiting_for_promo_max_uses)
async def promo_max_uses_entered(message: Message, state: FSMContext):
    """Process max uses and ask for expiry date."""
    try:
        max_uses = int(message.text.strip())
        if max_uses < 1:
            raise ValueError("Must be positive")
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format. Musbat butun son kiriting:\n"
            "(yoki bekor qilish uchun /cancel)"
        )
        return

    await state.update_data(promo_max_uses=max_uses)
    await state.set_state(AdvertisementStates.waiting_for_promo_expiry)

    await message.answer(
        f"✅ Maksimal foydalanish: <b>{max_uses}</b> marta\n\n"
        f"Promo kod muddati (kunlarda) kiriting:\n"
        f"(masalan: 7, 30, 90), yoki muddat chegarasiz uchun \"0\" yozing:\n"
        f"(yoki bekor qilish uchun /cancel)",
        parse_mode="HTML",
        reply_markup=kb_skip_expiry()
    )


@router.callback_query(F.data == "promo:expiry:none")
async def promo_expiry_skip(callback: CallbackQuery, state: FSMContext):
    """Skip expiry date - create promo code without expiration."""
    await state.update_data(promo_expiry_days=0)
    await _show_promo_confirmation(callback, state)


@router.message(AdvertisementStates.waiting_for_promo_expiry, Command("cancel"))
async def promo_expiry_cancel(message: Message, state: FSMContext):
    """Cancel promo code creation at expiry step."""
    await state.clear()
    await message.answer("❌ Promo kod yaratish bekor qilindi.", reply_markup=kb_main_menu_barber())


@router.message(AdvertisementStates.waiting_for_promo_expiry)
async def promo_expiry_entered(message: Message, state: FSMContext):
    """Process expiry days and show confirmation."""
    try:
        days = int(message.text.strip())
        if days < 0:
            raise ValueError("Must be non-negative")
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format. Butun son kiriting (0 = cheksiz):\n"
            "(yoki bekor qilish uchun /cancel)"
        )
        return

    await state.update_data(promo_expiry_days=days)

    # Show inline keyboard for confirmation
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="promo:confirm:yes"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="promo:confirm:no"),
    )

    data = await state.get_data()
    expiry_text = f"{days} kun" if days > 0 else "Cheksiz"

    await message.answer(
        f"🎁 <b>Promo kod tasdiqlash</b>\n\n"
        f"📌 Kod: <code>{data['promo_code']}</code>\n"
        f"💰 Chegirma: <b>{data['promo_percent']}%</b>\n"
        f"🎯 Maksimal foydalanish: <b>{data['promo_max_uses']}</b>\n"
        f"⏰ Muddati: <b>{expiry_text}</b>\n\n"
        f"Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdvertisementStates.waiting_for_promo_confirm)


async def _show_promo_confirmation(callback: CallbackQuery, state: FSMContext):
    """Helper to show promo code confirmation."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="promo:confirm:yes"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="promo:confirm:no"),
    )

    data = await state.get_data()
    days = data.get('promo_expiry_days', 0)
    expiry_text = f"{days} kun" if days > 0 else "Cheksiz"

    await callback.message.edit_text(
        f"🎁 <b>Promo kod tasdiqlash</b>\n\n"
        f"📌 Kod: <code>{data['promo_code']}</code>\n"
        f"💰 Chegirma: <b>{data['promo_percent']}%</b>\n"
        f"🎯 Maksimal foydalanish: <b>{data['promo_max_uses']}</b>\n"
        f"⏰ Muddati: <b>{expiry_text}</b>\n\n"
        f"Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdvertisementStates.waiting_for_promo_confirm)


@router.callback_query(F.data == "promo:confirm:yes")
async def promo_create_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Create the promo code."""
    data = await state.get_data()
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    import datetime
    from database.models import PromoCode

    days = data.get('promo_expiry_days', 0)
    expires_at = None
    if days > 0:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=days)

    promo = PromoCode(
        barber_id=profile.id,
        code=data['promo_code'],
        discount_percent=data['promo_percent'],
        max_uses=data['promo_max_uses'],
        expires_at=expires_at,
        is_active=True
    )

    session.add(promo)
    await session.commit()

    expiry_text = f"{days} kun" if days > 0 else "Cheksiz"

    await callback.message.edit_text(
        f"✅ <b>Promo kod yaratildi!</b>\n\n"
        f"📌 Kod: <code>{data['promo_code']}</code>\n"
        f"💰 Chegirma: <b>{data['promo_percent']}%</b>\n"
        f"🎯 Maksimal foydalanish: <b>{data['promo_max_uses']}</b>\n"
        f"⏰ Muddati: <b>{expiry_text}</b>\n\n"
        f"Mijozlaringizga ushbu kodni ulashing!",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer("Promo kod yaratildi!", show_alert=True)


@router.callback_query(F.data == "promo:confirm:no")
async def promo_create_reject(callback: CallbackQuery, state: FSMContext):
    """Cancel promo code creation."""
    await state.clear()
    await callback.message.edit_text(
        "❌ Promo kod yaratish bekor qilindi.",
        reply_markup=kb_advertisement_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "promo:cancel")
async def promo_cancel_callback(callback: CallbackQuery, state: FSMContext):
    """Cancel promo code creation from keyboard."""
    await state.clear()
    await promo_code_menu(callback, None)


@router.callback_query(F.data.startswith("promo:view:"))
async def promo_view(callback: CallbackQuery, session: AsyncSession):
    """View individual promo code details."""
    promo_id = int(callback.data.split(":")[2])

    from database.models import PromoCode
    promo = await session.get(PromoCode, promo_id)
    if not promo:
        await callback.answer("Promo kod topilmadi.", show_alert=True)
        return

    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile or promo.barber_id != profile.id:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    import datetime
    expiry_text = "Cheksiz"
    if promo.expires_at:
        days_left = (promo.expires_at - datetime.datetime.utcnow()).days
        if days_left < 0:
            expiry_text = "❌ Muddati o'tgan"
        else:
            expiry_text = f"{days_left} kun qoldi"

    status = "✅ Aktiv" if promo.is_active else "❌ Deaktiv"
    usage_percent = (promo.used_count / promo.max_uses * 100) if promo.max_uses > 0 else 0

    await callback.message.edit_text(
        f"🎁 <b>Promo kod ma'lumotlari</b>\n\n"
        f"📌 Kod: <code>{promo.code}</code>\n"
        f"💰 Chegirma: <b>{promo.discount_percent}%</b>\n"
        f"🎯 Foydalanish: <b>{promo.used_count}/{promo.max_uses}</b> ({usage_percent:.0f}%)\n"
        f"📊 Status: <b>{status}</b>\n"
        f"⏰ Muddati: <b>{expiry_text}</b>\n\n"
        f"Yaratilgan: {promo.created_at.strftime('%d.%m.%Y')}",
        parse_mode="HTML",
        reply_markup=kb_promo_item(promo.id, promo.is_active)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("promo:deactivate:"))
async def promo_deactivate(callback: CallbackQuery, session: AsyncSession):
    """Deactivate a promo code."""
    promo_id = int(callback.data.split(":")[2])

    from database.models import PromoCode
    promo = await session.get(PromoCode, promo_id)
    if not promo:
        await callback.answer("Promo kod topilmadi.", show_alert=True)
        return

    promo.is_active = False
    await session.commit()

    await callback.answer("❌ Promo kod deaktiv qilindi.", show_alert=True)
    await promo_view(callback, session)


@router.callback_query(F.data.startswith("promo:activate:"))
async def promo_activate(callback: CallbackQuery, session: AsyncSession):
    """Activate a promo code."""
    promo_id = int(callback.data.split(":")[2])

    from database.models import PromoCode
    promo = await session.get(PromoCode, promo_id)
    if not promo:
        await callback.answer("Promo kod topilmadi.", show_alert=True)
        return

    promo.is_active = True
    await session.commit()

    await callback.answer("✅ Promo kod aktiv qilindi.", show_alert=True)
    await promo_view(callback, session)


@router.callback_query(F.data.startswith("promo:delete:"))
async def promo_delete(callback: CallbackQuery, session: AsyncSession):
    """Delete a promo code."""
    promo_id = int(callback.data.split(":")[2])

    from database.models import PromoCode
    promo = await session.get(PromoCode, promo_id)
    if not promo:
        await callback.answer("Promo kod topilmadi.", show_alert=True)
        return

    await session.delete(promo)
    await session.commit()

    await callback.answer("🗑 Promo kod o'chirildi.", show_alert=True)
    await promo_code_menu(callback, session)


@router.callback_query(F.data == "ad:main")
async def advertisement_main(callback: CallbackQuery, session: AsyncSession):
    """Return to advertisement main menu."""
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    await callback.message.edit_text(
        "📢 <b>Reklama boshqaruvi</b>\n\n"
        "Mijozlarga reklama xabarlar yuborish, promo kodlar yaratish va statistikani ko'rish:",
        parse_mode="HTML",
        reply_markup=kb_advertisement_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "ad:stats")
async def advertisement_stats(callback: CallbackQuery, session: AsyncSession):
    user, profile = await ensure_barber(session, callback.from_user.id)
    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    # Get client statistics
    stmt = select(Appointment).where(Appointment.barber_id == profile.id)
    result = await session.execute(stmt)
    appointments = result.scalars().all()

    total_clients = len(set([a.client_id for a in appointments]))
    completed = len([a for a in appointments if a.status == AppointmentStatus.COMPLETED])
    returning = len([cid for cid, count in __import__('collections').Counter([a.client_id for a in appointments]).items() if count >= 2])

    # Get promo code statistics
    from database.models import PromoCode
    stmt_promo = select(PromoCode).where(PromoCode.barber_id == profile.id)
    result_promo = await session.execute(stmt_promo)
    promo_codes = result_promo.scalars().all()
    total_promos = len(promo_codes)
    active_promos = len([p for p in promo_codes if p.is_active])
    total_promo_uses = sum([p.used_count for p in promo_codes])

    await callback.message.edit_text(
        f"📊 <b>Reklama statistikasi</b>\n\n"
        f"👥 <b>Mijozlar:</b>\n"
        f"   Jami mijozlar: <b>{total_clients}</b>\n"
        f"   ✅ Bajarilgan uchrashuvlar: <b>{completed}</b>\n"
        f"   🔄 Qayta mijozlar: <b>{returning}</b>\n\n"
        f"🎁 <b>Promo kodlar:</b>\n"
        f"   Jami kodlar: <b>{total_promos}</b>\n"
        f"   ✅ Aktiv: <b>{active_promos}</b>\n"
        f"   🎯 Jami foydalanish: <b>{total_promo_uses}</b>\n\n"
        f"<i>Reklama samaradorligi uchun qayta mijozlar eng qimmatli auditoriya!</i>",
        parse_mode="HTML",
        reply_markup=kb_advertisement_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "ad:cancel")
async def advertisement_cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Reklama yuborish bekor qilindi.",
        reply_markup=kb_advertisement_menu()
    )
    await callback.answer()
