"""handlers/client.py — Client booking flow: find barber → pick service → pick date/time → confirm"""
import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import (
    User, UserRole, BarberProfile, Service, Appointment,
    AppointmentStatus, BarberSchedule
)
from states import BookingStates, BookingPromoStates, ReviewStates
from keyboards import (
    kb_barber_list, kb_service_list, kb_date_picker,
    kb_time_slots, kb_confirm_booking, kb_appointments_list,
    kb_appointment_actions, kb_main_menu_client, kb_remove, kb_chat_reply,
    kb_promo_input, kb_rating_stars, kb_skip_comment
)
from states import ChatStates

router = Router()

DAY_MAP = {
    0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
    4: "friday", 5: "saturday", 6: "sunday"
}


def generate_available_slots(
    work_start: datetime.time,
    work_end: datetime.time,
    slot_minutes: int,
    booked_slots: list[tuple[datetime.time, datetime.time]],
    date: datetime.date,
) -> list[str]:
    """Generate list of available HH:MM slot strings for the given date."""
    slots = []
    now = datetime.datetime.now()
    current = datetime.datetime.combine(date, work_start)
    end = datetime.datetime.combine(date, work_end)

    while current + datetime.timedelta(minutes=slot_minutes) <= end:
        slot_start = current.time()
        slot_end = (current + datetime.timedelta(minutes=slot_minutes)).time()

        # Skip past slots for today
        if date == now0.date() and slot_start <= now.time():
            current += datetime.timedelta(minutes=slot_minutes)
            continue

        # Check collision with booked slots
        collision = any(
            not (slot_end <= bs or slot_start >= be)
            for bs, be in booked_slots
        )
        if not collision:
            slots.append(slot_start.strftime("%H:%M"))

        current += datetime.timedelta(minutes=slot_minutes)

    return slots


# ──────────────────────────────────────────────
# Step 1: Find barbers
# ──────────────────────────────────────────────

@router.message(F.text.in_({"✂️ Sartarosh topish", "✂️ Найти парикмахера"}))
async def find_barbers(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()

    stmt = (
        select(BarberProfile, User)
        .join(User, User.id == BarberProfile.user_id)
        .where(User.is_active == True)
    )
    result = await session.execute(stmt)
    barbers = result.all()

    if not barbers:
        await message.answer(
            "😔 Hozircha ro'yxatda sartarosh yo'q.\nKeyinroq urinib ko'ring.",
            reply_markup=kb_main_menu_client()
        )
        return

    await message.answer(
        f"✂️ <b>Mavjud sartaroshlar</b> ({len(barbers)} ta):\n\n"
        "Quyidan sartarosh tanlang:",
        parse_mode="HTML",
        reply_markup=kb_barber_list(barbers)
    )
    await state.set_state(BookingStates.selecting_barber)


@router.callback_query(BookingStates.selecting_barber, F.data.startswith("barber:"))
async def barber_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    barber_id = int(callback.data.split(":")[1])
    profile = await session.get(BarberProfile, barber_id)
    if not profile:
        await callback.answer("Sartarosh topilmadi.", show_alert=True)
        return

    barber_user = await session.get(User, profile.user_id)
    # Blacklist check
    from database.models import Blacklist
    from sqlalchemy import and_
    stmt = select(Blacklist).where(
        and_(
            Blacklist.barber_id == barber_id,
            Blacklist.client_id == callback.from_user.id
        )
    )
    is_blocked = (await session.execute(stmt)).scalar()
    if is_blocked:
        await callback.answer(
            "🚫 Kechirasiz, bu sartarosh sizni qora ro'yxatga kiritgan. "
            "Uning xizmatlaridan foydalana olmaysiz.",
            show_alert=True
        )
        return

    services = [s for s in profile.services if s.is_active]

    if not services:
        await callback.answer(
            "Bu sartaroshda hozircha xizmat yo'q.",
            show_alert=True
        )
        return

    name = profile.salon_name or barber_user.first_name
    work_info = ""
    if profile.work_start and profile.work_end:
        work_info = f"\n⏰ Ish soatlari: {profile.work_start.strftime('%H:%M')} — {profile.work_end.strftime('%H:%M')}"

    rating_info = f"\n⭐ Reyting: {profile.rating:.1f} ({profile.review_count} sharh)" if profile.review_count > 0 else "\n⭐ Reyting: Yangi"

    await callback.message.edit_text(
        f"✂️ <b>{name}</b>\n"
        f"📍 {profile.address or '—'}\n"
        f"📝 {profile.bio or ''}{work_info}{rating_info}\n\n"
        "Xizmat tanlang:",
        parse_mode="HTML",
        reply_markup=kb_service_list(services, profile.latitude, profile.longitude, barber_id=barber_id)
    )
    await state.update_data(barber_id=barber_id, barber_name=name)
    await state.set_state(BookingStates.selecting_service)
    await callback.answer()


# ──────────────────────────────────────────────
# Step 2: Select service
# ──────────────────────────────────────────────

@router.callback_query(BookingStates.selecting_service, F.data.startswith("service:"))
async def service_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    service_id = int(callback.data.split(":")[1])
    svc = await session.get(Service, service_id)
    if not svc:
        await callback.answer("Xizmat topilmadi.", show_alert=True)
        return

    await state.update_data(
        service_id=service_id,
        service_name=svc.name,
        service_duration=svc.duration,
        service_price=svc.price,
    )

    # Generate next 7 available days
    data = await state.get_data()
    barber_id = data["barber_id"]
    profile = await session.get(BarberProfile, barber_id)

    # Check which days of week barber works
    stmt = select(BarberSchedule).where(
        BarberSchedule.barber_id == barber_id,
        BarberSchedule.is_working == True
    )
    result = await session.execute(stmt)
    working_schedules = result.scalars().all()
    working_days = {s.day_of_week.value for s in working_schedules}

    available_dates = []
    today = datetime.date.today()
    for i in range(1, 15):  # next 14 days
        d = today + datetime.timedelta(days=i)
        day_name = DAY_MAP[d.weekday()]
        # If schedule set, filter by it; otherwise show all days
        if working_days and day_name not in working_days:
            continue
        available_dates.append(d)
        if len(available_dates) >= 7:
            break

    if not available_dates:
        available_dates = [today + datetime.timedelta(days=i) for i in range(1, 8)]

    await callback.message.edit_text(
        f"✅ Xizmat: <b>{svc.name}</b> — {svc.price:,} so'm\n\n"
        "📆 Sanani tanlang:",
        parse_mode="HTML",
        reply_markup=kb_date_picker(available_dates)
    )
    await state.set_state(BookingStates.selecting_date)
    await callback.answer()


# ──────────────────────────────────────────────
# Step 3: Select date
# ──────────────────────────────────────────────

@router.callback_query(BookingStates.selecting_date, F.data.startswith("date:"))
async def date_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    date_str = callback.data.split(":")[1]
    selected_date = datetime.date.fromisoformat(date_str)

    data = await state.get_data()
    barber_id = data["barber_id"]
    service_duration = data["service_duration"]

    profile = await session.get(BarberProfile, barber_id)

    # Get work hours for this specific day from schedule
    day_name = DAY_MAP[selected_date.weekday()]
    stmt = select(BarberSchedule).where(
        BarberSchedule.barber_id == barber_id,
        BarberSchedule.day_of_week == day_name,
    )
    result = await session.execute(stmt)
    schedule = result.scalar_one_or_none()

    if schedule and not schedule.is_working:
        await callback.answer("Bu kunda sartarosh ishlamaydi.", show_alert=True)
        return

    work_start = (schedule.start_time if schedule and schedule.start_time else profile.work_start) or datetime.time(9, 0)
    work_end = (schedule.end_time if schedule and schedule.end_time else profile.work_end) or datetime.time(20, 0)
    slot_minutes = profile.slot_duration or 30

    # Get booked slots for this date
    stmt2 = select(Appointment).where(
        Appointment.barber_id == barber_id,
        Appointment.appointment_date == selected_date,
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
    )
    result2 = await session.execute(stmt2)
    booked = result2.scalars().all()
    booked_slots = [(a.start_time, a.end_time) for a in booked]

    available_slots = generate_available_slots(
        work_start, work_end, service_duration, booked_slots, selected_date
    )

    if not available_slots:
        await callback.answer("Bu kunda bo'sh vaqt yo'q. Boshqa kun tanlang.", show_alert=True)
        return

    await state.update_data(date=date_str)
    await callback.message.edit_text(
        f"📆 Sana: <b>{selected_date.strftime('%d.%m.%Y')}</b>\n\n"
        "⏰ Vaqtni tanlang:",
        parse_mode="HTML",
        reply_markup=kb_time_slots(available_slots)
    )
    await state.set_state(BookingStates.selecting_time)
    await callback.answer()


# ──────────────────────────────────────────────
# Step 4: Select time
# ──────────────────────────────────────────────

@router.callback_query(BookingStates.selecting_time, F.data.startswith("time:"))
async def time_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    time_str = callback.data.split(":")[1]
    data = await state.get_data()

    barber_name = data["barber_name"]
    service_name = data["service_name"]
    service_price = data["service_price"]
    date_str = data["date"]

    selected_date = datetime.date.fromisoformat(date_str)

    await state.update_data(time=time_str)
    await callback.message.edit_text(
        f"📋 <b>Buyurtma tasdiqlash</b>\n\n"
        f"✂️ Sartarosh: <b>{barber_name}</b>\n"
        f"🔧 Xizmat: <b>{service_name}</b>\n"
        f"💰 Narx: <b>{service_price:,} so'm</b>\n"
        f"📆 Sana: <b>{selected_date.strftime('%d.%m.%Y')}</b>\n"
        f"⏰ Vaqt: <b>{time_str}</b>\n\n"
        "Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=kb_confirm_booking(barber_name, service_name, date_str, time_str)
    )
    await state.set_state(BookingStates.confirming)
    await callback.answer()


# ──────────────────────────────────────────────
# Step 5: Confirm booking
# ──────────────────────────────────────────────

@router.callback_query(BookingStates.confirming, F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.clear()

    barber_id = data["barber_id"]
    service_id = data["service_id"]
    service_duration = data["service_duration"]
    service_price = data["service_price"]
    date_str = data["date"]
    time_str = data["time"]

    selected_date = datetime.date.fromisoformat(date_str)
    start_time = datetime.time.fromisoformat(time_str)
    end_time = (
        datetime.datetime.combine(selected_date, start_time)
        + datetime.timedelta(minutes=service_duration)
    ).time()

    appt = Appointment(
        barber_id=barber_id,
        client_id=callback.from_user.id,
        service_id=service_id,
        appointment_date=selected_date,
        start_time=start_time,
        end_time=end_time,
        status=AppointmentStatus.PENDING,
    )
    session.add(appt)
    await session.commit()
    await session.refresh(appt)

    # Payment via external URL
    if config.CLICK_MERCHANT_ID or config.PAYME_MERCHANT_ID:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        order_id = f"appt_{appt.id}_{int(datetime.datetime.now().timestamp())}"
        builder = InlineKeyboardBuilder()

        if config.CLICK_MERCHANT_ID:
            click_url = (
                f"https://my.click.uz/services/pay?"
                f"service_id={config.CLICK_MERCHANT_ID}&"
                f"merchant_id={config.CLICK_MERCHANT_ID}&"
                f"amount={service_price}&"
                f"transaction_param={order_id}"
            )
            builder.row(InlineKeyboardButton(text="💳 Click orqali to'lash", url=click_url))

        if config.PAYME_MERCHANT_ID:
            payme_amount = service_price * 100  # tiyin
            payme_url = f"https://checkout.paycom.uz/{config.PAYME_MERCHANT_ID}?amount={payme_amount}"
            builder.row(InlineKeyboardButton(text="💳 Payme orqali to'lash", url=payme_url))

        builder.row(InlineKeyboardButton(text="✅ To'lovni tasdiqladim", callback_data=f"appt_confirm_pay:{appt.id}"))

        await callback.message.edit_text(
            f"✅ <b>Buyurtma yaratildi!</b>\n\n"
            f"📋 Buyurtma #: {appt.id}\n"
            f"📆 Sana: {selected_date.strftime('%d.%m.%Y')}\n"
            f"⏰ Vaqt: {time_str}\n"
            f"💰 Narx: {service_price:,} so'm\n\n"
            f"To'lovni amalga oshirish uchun quyidagi tugmalardan foydalaning. "
            f"To'lovdan so'ng <b>«✅ To'lovni tasdiqladim»</b> tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    else:
        # No payment configured — normal flow
        await callback.message.edit_text(
            f"✅ <b>Muvaffaqiyatli buyurtma qilindi!</b>\n\n"
            f"📋 Buyurtma #: {appt.id}\n"
            f"📆 Sana: {selected_date.strftime('%d.%m.%Y')}\n"
            f"⏰ Vaqt: {time_str}\n\n"
            "Sartarosh tez orada tasdiqlaydi.",
            parse_mode="HTML",
        )
        await callback.message.answer("Bosh menyu:", reply_markup=kb_main_menu_client())

    # Notify barber
    profile = await session.get(BarberProfile, barber_id)
    barber_user = await session.get(User, profile.user_id)
    client_user = await session.get(User, callback.from_user.id)
    svc = await session.get(Service, service_id)
    try:
        await callback.bot.send_message(
            profile.user_id,
            f"🔔 <b>Yangi buyurtma!</b>\n\n"
            f"👤 Mijoz: {client_user.first_name}\n"
            f"✂️ Xizmat: {svc.name}\n"
            f"📆 {selected_date.strftime('%d.%m.%Y')}, ⏰ {time_str}",
            reply_markup=kb_appointment_actions(appt.id, is_barber=True, status=appt.status.value)
        )
    except Exception:
        pass

    await callback.answer()


# ──────────────────────────────────────────────
# Payment Handlers
# ──────────────────────────────────────────────

from aiogram.types import PreCheckoutQuery

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.callback_query(F.data.startswith("appt_confirm_pay:"))
async def confirm_appointment_payment(callback: CallbackQuery, session: AsyncSession):
    appt_id = int(callback.data.split(":")[1])
    appt = await session.get(Appointment, appt_id)
    if not appt:
        await callback.answer("Buyurtma topilmadi.", show_alert=True)
        return

    await callback.answer("✅ To'lov so'rovi sartaroshga yuborildi. U tasdiqlagach buyurtma aktiv bo'ladi.", show_alert=True)

    # Notify barber
    profile = await session.get(BarberProfile, appt.barber_id)
    client_user = await session.get(User, appt.client_id)
    svc = await session.get(Service, appt.service_id)
    try:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"appt:confirm:{appt.id}"))
        kb.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"appt:cancel:{appt.id}"))
        await callback.bot.send_message(
            profile.user_id,
            f"💰 <b>Mijoz to'lov qildi!</b>\n\n"
            f"👤 Mijoz: {client_user.first_name if client_user else '—'}\n"
            f"📋 Buyurtma #{appt.id}\n"
            f"✂️ Xizmat: {svc.name if svc else '—'}\n"
            f"📆 {appt.appointment_date}, ⏰ {appt.start_time.strftime('%H:%M')}\n\n"
            f"Iltimos, buyurtmani tasdiqlang:",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
    except Exception:
        pass


# ──────────────────────────────────────────────
# My appointments (client view)
# ──────────────────────────────────────────────

@router.message(F.text.in_({"📅 Mening uchrashuvlarim", "📅 Мои записи"}))
async def my_appointments(message: Message, session: AsyncSession):
    stmt = (
        select(Appointment)
        .where(
            Appointment.client_id == message.from_user.id,
            Appointment.appointment_date >= datetime.date.today(),
        )
        .order_by(Appointment.appointment_date, Appointment.start_time)
    )
    result = await session.execute(stmt)
    appointments = result.scalars().all()

    if not appointments:
        await message.answer(
            "📅 Sizda kelgusi uchrashuvlar yo'q.\n\n"
            "Sartarosh topish uchun «✂️ Sartarosh topish» tugmasini bosing.",
            reply_markup=kb_main_menu_client()
        )
        return

    await message.answer(
        f"📅 <b>Kelgusi uchrashuvlaringiz</b> ({len(appointments)} ta):",
        parse_mode="HTML",
        reply_markup=kb_appointments_list(appointments, is_barber=False)
    )


# ──────────────────────────────────────────────
# Navigation back button
# ──────────────────────────────────────────────

@router.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    """Simple back — clears state and returns to main menu."""
    current = await state.get_state()
    await state.clear()
    await callback.message.answer(
        "Bosh menyuga qaytildi.",
        reply_markup=kb_main_menu_client()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Barber rating & reviews
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("rate:"))
async def rate_barber_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Start rating flow - handle star selection."""
    parts = callback.data.split(":")
    appointment_id = int(parts[1])
    action = parts[2]

    if action == "skip":
        await callback.message.edit_text(
            "⏭️ Baholash o'tkazib yuborildi.\n\n"
            "Siz istalgan vaqt menyu orqali tarixdan baholashingiz mumkin.",
            reply_markup=kb_main_menu_client()
        )
        await callback.answer()
        await state.clear()
        return

    rating = int(action)

    # Check if already reviewed
    from database.models import Review
    stmt = select(Review).where(Review.appointment_id == appointment_id)
    existing = (await session.execute(stmt)).scalar()
    if existing:
        await callback.answer("Siz allaqachon bu uchrashuvni baholagansiz!", show_alert=True)
        return

    await state.update_data(
        review_appointment_id=appointment_id,
        review_rating=rating
    )
    await state.set_state(ReviewStates.waiting_for_comment)

    star_emoji = "⭐" * rating
    await callback.message.edit_text(
        f"{star_emoji}\n\n"
        f"Bahoyingiz: <b>{rating}</b> yulduz\n\n"
        f"Xizmatingiz haqida qisqa fikr qoldirmoqchimisiz?\n"
        f"(yoki «Sharh yozmaslik» tugmasini bosing)",
        parse_mode="HTML",
        reply_markup=kb_skip_comment()
    )
    await callback.answer()


@router.callback_query(ReviewStates.waiting_for_comment, F.data == "review:skip")
async def skip_review_comment(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Skip comment and save review with rating only."""
    await _save_review(callback, state, session, comment=None)


@router.message(ReviewStates.waiting_for_comment)
async def review_comment_entered(message: Message, state: FSMContext, session: AsyncSession):
    """Save review with comment."""
    await _save_review(message, state, session, comment=message.text)


async def _save_review(event, state: FSMContext, session: AsyncSession, comment: str | None):
    """Helper to save review and update barber rating."""
    data = await state.get_data()
    appointment_id = data.get("review_appointment_id")
    rating = data.get("review_rating")

    if not appointment_id:
        if isinstance(event, CallbackQuery):
            await event.message.edit_text("❌ Xatolik yuz berdi.")
        else:
            await event.answer("❌ Xatolik yuz berdi.")
        await state.clear()
        return

    # Get appointment details
    from database.models import Appointment, Review, BarberProfile
    appointment = await session.get(Appointment, appointment_id)
    if not appointment:
        if isinstance(event, CallbackQuery):
            await event.message.edit_text("❌ Uchrashuv topilmadi.")
        else:
            await event.answer("❌ Uchrashuv topilmadi.")
        await state.clear()
        return

    # Create review
    review = Review(
        appointment_id=appointment_id,
        client_id=appointment.client_id,
        barber_id=appointment.barber_id,
        rating=rating,
        comment=comment,
        is_visible=True
    )
    session.add(review)

    # Update barber rating
    profile = await session.get(BarberProfile, appointment.barber_id)
    if profile:
        current_total = profile.rating * profile.review_count
        profile.review_count += 1
        profile.rating = (current_total + rating) / profile.review_count

    await session.commit()
    await state.clear()

    star_emoji = "⭐" * rating
    comment_text = f"\n💬 Sharh: <i>{comment}</i>" if comment else ""

    msg_text = (
        f"✅ <b>Bahoingiz uchun rahmat!</b>\n\n"
        f"{star_emoji} Baho: {rating}\n"
        f"{comment_text}\n\n"
        f"Fikringiz sartaroshning rivojlanishiga yordam beradi! 🙏"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(msg_text, parse_mode="HTML", reply_markup=kb_main_menu_client())
        await event.answer("Baho saqlandi!")
    else:
        await event.answer(msg_text, parse_mode="HTML", reply_markup=kb_main_menu_client())

    # Notify barber
    try:
        await event.bot.send_message(
            profile.user_id,
            f"⭐ <b>Yangi baho!</b>\n\n"
            f"Mijoz sizni {rating} yulduz bilan baholdi!\n"
            f"{f'� Sharh: {comment}' if comment else ''}\n\n"
            f"📈 Yangi reyting: <b>{profile.rating:.1f}</b> ({profile.review_count} sharh)",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("portfolio:"))
async def view_portfolio(callback: CallbackQuery, session: AsyncSession):
    barber_id = int(callback.data.split(":")[1])
    
    # Get last 10 photos for this barber's appointments
    from database.models import AppointmentPhoto, Appointment
    from aiogram.types import InputMediaPhoto

    stmt = (
        select(AppointmentPhoto)
        .join(Appointment, Appointment.id == AppointmentPhoto.appointment_id)
        .where(Appointment.barber_id == barber_id)
        .order_by(AppointmentPhoto.uploaded_at.desc())
        .limit(10)
    )
    result = await session.execute(stmt)
    photos = result.scalars().all()
    
    if not photos:
        await callback.answer("😔 Bu sartarosh hali portfolio rasmlarini yuklamagan.", show_alert=True)
        return
    
    await callback.answer("Portfolio yuklanmoqda...")
    
    media = [InputMediaPhoto(media=p.file_id) for p in photos]
    
    if len(media) >= 2:
        # Media group for multiple photos
        await callback.message.answer_media_group(media=media)
    else:
        # Single photo
        await callback.message.answer_photo(
            photo=photos[0].file_id,
            caption="Sartaroshning ishlaridan namuna ✂️"
        )


@router.message(F.text.in_({"📜 Tarix", "📜 История"}))
async def appointment_history(message: Message, session: AsyncSession):
    from database.models import Review

    stmt = (
        select(Appointment)
        .where(
            Appointment.client_id == message.from_user.id,
            Appointment.status == AppointmentStatus.COMPLETED
        )
        .order_by(Appointment.appointment_date.desc())
        .limit(10)
    )
    result = await session.execute(stmt)
    appts = result.scalars().all()

    if not appts:
        await message.answer("Sizda hali yakunlangan uchrashuvlar yo'q.")
        return

    text = "📜 <b>Sizning uchrashuvlaringiz tarixi:</b>\n\n"
    for a in appts:
        b_name = a.barber.salon_name or "Sartarosh"

        # Check if reviewed
        stmt_review = select(Review).where(Review.appointment_id == a.id)
        review = (await session.execute(stmt_review)).scalar()

        if review:
            stars = "⭐" * review.rating
            text += f"• {a.appointment_date} — {b_name} {stars}\n"
        else:
            text += f"• {a.appointment_date} — {b_name} (⭐ Baholash mumkin)\n"

    await message.answer(text, parse_mode="HTML")

    # Show unreviewed appointments with rating buttons
    unreviewed = [a for a in appts if not (await session.execute(select(Review).where(Review.appointment_id == a.id))).scalar()]
    if unreviewed:
        await message.answer(
            "⭐ <b>Baholashga tayyor uchrashuvlar:</b>",
            parse_mode="HTML"
        )
        for a in unreviewed[:3]:  # Show max 3
            b_name = a.barber.salon_name or "Sartarosh"
            await message.answer(
                f"🗓 {a.appointment_date}\n"
                f"✂️ {b_name}\n"
                f"⏰ {a.start_time.strftime('%H:%M')}",
                reply_markup=kb_rating_stars(a.id)
            )


@router.message(F.text.in_({"📍 Yaqindagi sartaroshlar", "📍 Ближайшие мастера"}))
async def nearby_barbers_request(message: Message):
    from keyboards import kb_request_location
    await message.answer(
        "📍 Yaqin atrofdagi sartaroshlarni topish uchun joylashuvingizni yuboring:",
        reply_markup=kb_request_location()
    )


@router.message(F.location)
async def nearby_barbers_result(message: Message, session: AsyncSession):
    user_lat = message.location.latitude
    user_lon = message.location.longitude

    stmt = (
        select(BarberProfile, User)
        .join(User, User.id == BarberProfile.user_id)
        .where(
            BarberProfile.latitude != None,
            BarberProfile.longitude != None,
            User.is_active == True
        )
    )
    result = await session.execute(stmt)
    barbers = result.all()

    from math import radians, sin, cos, sqrt, atan2

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    nearby = []
    for profile, user in barbers:
        dist = haversine(user_lat, user_lon, profile.latitude, profile.longitude)
        if dist <= 10.0:  # 10 km radius
            nearby.append((profile, user, dist))

    nearby.sort(key=lambda x: x[2])

    if not nearby:
        await message.answer(
            "😔 10 km radiusda sartarosh topilmadi.\nBoshqa hududni sinab ko'ring.",
            reply_markup=kb_main_menu_client()
        )
        return

    text = "📍 <b>Yaqin atrofdagi sartaroshlar:</b>\n\n"
    for profile, user, dist in nearby[:10]:
        name = profile.salon_name or user.first_name
        rating = f"⭐ {profile.rating:.1f}" if profile.review_count > 0 else "⭐ Yangi"
        text += (
            f"• <b>{name}</b> ({rating})\n"
            f"  📍 {profile.address or '—'}\n"
            f"  📏 {dist:.1f} km\n\n"
        )

    from keyboards import InlineKeyboardBuilder, InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    for profile, user, dist in nearby[:10]:
        name = profile.salon_name or user.first_name
        builder.row(
            InlineKeyboardButton(
                text=f"✂️ {name}",
                callback_data=f"barber:{profile.id}"
            )
        )

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


# ──────────────────────────────────────────────
# Chat with barbers
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("chat:barber:"))
async def start_chat_with_barber(callback: CallbackQuery, state: FSMContext):
    barber_id = int(callback.data.split(":")[2])
    await state.update_data(chat_target_barber=barber_id)
    await state.set_state(ChatStates.waiting_for_message_to_barber)
    await callback.message.edit_text(
        "📩 <b>Sartaroshga xabar yozish</b>\n\n"
        "Iltimos, xabaringizni yozing (yoki bekor qilish uchun /cancel):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("chat:barber_appt:"))
async def start_chat_from_appt(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    appt_id = int(callback.data.split(":")[2])
    appt = await session.get(Appointment, appt_id)
    if not appt:
        await callback.answer("Uchrashuv topilmadi.", show_alert=True)
        return
    await state.update_data(chat_target_barber=appt.barber_id, chat_appt_id=appt_id)
    await state.set_state(ChatStates.waiting_for_message_to_barber)
    await callback.message.edit_text(
        "📩 <b>Sartaroshga xabar yozish</b>\n\n"
        f"Buyurtma #{appt_id} bo'yicha xabar yuboring\n"
        "(yoki bekor qilish uchun /cancel):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ChatStates.waiting_for_message_to_barber, Command("cancel"))
async def cancel_chat_with_barber(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Xabar yuborish bekor qilindi.", reply_markup=kb_main_menu_client())


@router.message(ChatStates.waiting_for_message_to_barber)
async def send_message_to_barber(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    barber_id = data.get("chat_target_barber")
    if not barber_id:
        await message.answer("Xatolik: Sartarosh tanlanmagan.", reply_markup=kb_main_menu_client())
        await state.clear()
        return

    profile = await session.get(BarberProfile, barber_id)
    if not profile:
        await message.answer("Xatolik: Sartarosh profili topilmadi.", reply_markup=kb_main_menu_client())
        await state.clear()
        return

    client = await session.get(User, message.from_user.id)
    appt_id = data.get("chat_appt_id")
    appt_text = f"Buyurtma #{appt_id} bo'yicha" if appt_id else ""

    # Forward message to barber
    try:
        await message.bot.send_message(
            profile.user_id,
            f"📨 <b>Yangi xabar mijozdan</b>\n\n"
            f"👤 {client.first_name} (ID: {client.id})\n"
            f"{appt_text}\n\n"
            f"<i>{message.text}</i>",
            parse_mode="HTML",
            reply_markup=kb_chat_reply(client.id, is_barber=True)
        )
        await message.answer(
            f"✅ Xabaringiz sartaroshga yuborildi!\n\n"
            f"Javobni kuting...",
            reply_markup=kb_main_menu_client()
        )
    except Exception:
        await message.answer(
            "❌ Xatolik: Xabar yuborilmadi. Sartarosh botni bloklagan bo'lishi mumkin.",
            reply_markup=kb_main_menu_client()
        )

    await state.clear()


@router.callback_query(F.data.startswith("reply:barber:"))
async def reply_to_barber_start(callback: CallbackQuery, state: FSMContext):
    barber_user_id = int(callback.data.split(":")[2])
    await state.update_data(chat_target_barber_user=barber_user_id)
    await state.set_state(ChatStates.waiting_for_message_to_barber)
    await callback.message.edit_text(
        "📩 <b>Sartaroshga javob yozish</b>\n\n"
        "Xabaringizni yozing (yoki bekor qilish uchun /cancel):",
        parse_mode="HTML",
        reply_markup=None
    )
    await callback.answer()