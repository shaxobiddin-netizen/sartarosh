"""handlers/common.py — /start, registration, role selection"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User, UserRole, BarberProfile
from states import RegistrationStates, StatesGroup, State
from keyboards import (
    kb_role_selection, kb_request_phone, kb_cancel,
    kb_main_menu_client, kb_main_menu_barber, kb_remove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


async def get_or_create_user(session: AsyncSession, tg_user) -> User:
    result = await session.get(User, tg_user.id)
    if result is None:
        result = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name or "Foydalanuvchi",
            last_name=tg_user.last_name,
            role=UserRole.CLIENT,
        )
        session.add(result)
        await session.commit()
        await session.refresh(result)
    return result


def main_menu_kb(user: User):
    if user.role == UserRole.BARBER:
        return kb_main_menu_barber()
    return kb_main_menu_client()


async def send_welcome_photo(message: Message):
    """Send welcome photo if BOT_WELCOME_PHOTO is set in config."""
    from config import config
    photo_url = getattr(config, 'BOT_WELCOME_PHOTO', None)
    if photo_url:
        try:
            from aiogram.types import FSInputFile
            if photo_url.startswith('http'):
                await message.answer_photo(photo=photo_url, caption="🤖")
            else:
                await message.answer_photo(photo=FSInputFile(photo_url), caption="🤖")
        except Exception:
            pass


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(session, message.from_user)

    # Send welcome photo (optional branding)
    await send_welcome_photo(message)

    # Check if user needs phone number
    if not user.phone:
        await message.answer(
            f"👋 Assalomu alaykum, <b>{user.first_name}</b>!\n\n"
            "Botdan foydalanish uchun telefon raqamingizni yuboring:",
            parse_mode="HTML",
            reply_markup=kb_request_phone()
        )
        await state.set_state(RegistrationStates.waiting_for_phone)
        return

    # Check if role is selected
    if user.role == UserRole.CLIENT and not user.barber_profile:
        await message.answer(
            f"👋 Xush kelibsiz, <b>{user.first_name}</b>!\n\n"
            "Siz kim sifatida foydalanmoqchisiz?",
            parse_mode="HTML",
            reply_markup=kb_role_selection()
        )
        return

    # Build profile card
    role_emoji = {"client": "👤", "barber": "✂️", "admin": "👑"}.get(user.role.value, "👤")
    role_text = {"client": "Mijoz", "barber": "Sartarosh", "admin": "Admin"}.get(user.role.value, "—")

    profile_lines = [
        f"━━━━━━━━━━━━━━━━━━",
        f"{role_emoji} <b>{user.first_name} {user.last_name or ''}</b>",
        f"📱 {user.phone or '—'}",
        f"🏷 @{user.username or '—'}",
        f"🎭 Rol: <b>{role_text}</b>",
    ]

    # Extra info for barbers
    if user.role == UserRole.BARBER and user.barber_profile:
        p = user.barber_profile
        sub_status = "✅ Faol" if p.subscription_active else "❌ Faol emas"
        svc_count = len([s for s in p.services if s.is_active])
        svc_text = f"{svc_count} ta" if svc_count > 0 else "Hali qo'shilmagan"
        profile_lines += [
            f"🏪 Salon: <b>{p.salon_name or '—'}</b>",
            f"📍 {p.address or '—'}",
            f"⭐ Reyting: {p.rating:.1f} ({p.review_count} sharh)",
            f"✂️ Xizmatlar: {svc_text}",
            f"💳 Obuna: {sub_status}",
        ]

    profile_lines.append("━━━━━━━━━━━━━━━━━━")

    profile_card = "\n".join(profile_lines)

    await message.answer(
        f"👋 Xush kelibsiz!\n\n{profile_card}",
        parse_mode="HTML",
        reply_markup=main_menu_kb(user)
    )


@router.message(RegistrationStates.waiting_for_phone, F.contact)
async def received_phone(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_or_create_user(session, message.from_user)
    user.phone = message.contact.phone_number
    await session.commit()

    await message.answer(
        "✅ Telefon raqam saqlandi!\n\n"
        "Siz kim sifatida foydalanmoqchisiz?",
        reply_markup=kb_role_selection()
    )
    await state.clear()


@router.message(RegistrationStates.waiting_for_phone)
async def waiting_phone_text(message: Message):
    if message.text == "⬅️ Orqaga":
        await message.answer("Orqaga qaytildi.", reply_markup=kb_remove())
        return
    await message.answer(
        "Iltimos, quyidagi tugma orqali telefon raqamingizni yuboring 👇",
        reply_markup=kb_request_phone()
    )


@router.callback_query(F.data == "role:barber")
async def role_barber(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    user = await session.get(User, callback.from_user.id)
    user.role = UserRole.BARBER
    await session.commit()

    await callback.message.edit_text(
        "✂️ <b>Sartarosh sifatida ro'yxatdan o'tdingiz!</b>\n\n"
        "Endi saloningiz haqida ma'lumot kiriting.\n"
        "Salonning nomini yozing (yoki o'tkazib yuborish uchun «O'tkazib yuborish» tugmasini bosing):",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "Yoki quyida tugmalar:",
        reply_markup=kb_cancel()
    )
    from states import BarberProfileStates
    await state.set_state(BarberProfileStates.waiting_for_salon_name)
    await state.update_data(role="barber")
    await callback.answer()


@router.callback_query(F.data == "role:client")
async def role_client(callback: CallbackQuery, session: AsyncSession):
    user = await session.get(User, callback.from_user.id)
    user.role = UserRole.CLIENT
    await session.commit()

    await callback.message.edit_text(
        "👤 <b>Mijoz sifatida ro'yxatdan o'tdingiz!</b>\n\n"
        "Sartarosh topish uchun quyidagi menyudan foydalaning.",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "Bosh menyu:",
        reply_markup=kb_main_menu_client()
    )
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, session: AsyncSession):
    user = await session.get(User, callback.from_user.id)
    await callback.message.answer("Bosh menyu:", reply_markup=main_menu_kb(user))
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def universal_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    user = await session.get(User, callback.from_user.id)
    await callback.message.answer("❌ Bekor qilindi.", reply_markup=main_menu_kb(user))
    await callback.answer()


@router.message(F.text == "❌ Bekor qilish")
async def text_cancel(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    user = await session.get(User, message.from_user.id)
    await message.answer("❌ Bekor qilindi.", reply_markup=main_menu_kb(user))


@router.message(F.text == "ℹ️ Yordam")
async def help_handler(message: Message):
    await message.answer(
        "🤖 <b>Barber CRM Bot</b>\n\n"
        "Bu bot sartaroshlar va mijozlarni ulaydi:\n\n"
        "👤 <b>Mijozlar uchun:</b>\n"
        "• Sartarosh toping\n"
        "• Xizmat tanlang\n"
        "• Qulay vaqtga yoziling\n\n"
        "✂️ <b>Sartaroshlar uchun:</b>\n"
        "• Profilingizni yarating\n"
        "• Xizmatlar qo'shing\n"
        "• Uchrashuvlarni boshqaring\n\n"
        "❓ Muammo bo'lsa: @admin ga murojaat qiling",
        parse_mode="HTML"
    )


class ProfileStates(StatesGroup):
    waiting_for_birthday = State()


@router.message(Command("profile"))
@router.message(F.text == "👤 Mening profilim")
async def my_profile(message: Message, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    if not user:
        await message.answer("Avval /start buyrug'ini yuboring.")
        return

    role_text = {"client": "Mijoz", "barber": "Sartarosh", "admin": "Admin"}.get(
        user.role.value, "Noma'lum"
    )

    birthday_text = "—"
    if user.birthday:
        birthday_text = user.birthday.strftime('%d.%m.%Y')

    text = (
        f"👤 <b>Mening profilim</b>\n\n"
        f"📝 Ism: {user.first_name} {user.last_name or ''}\n"
        f"🔹 Username: @{user.username or '—'}\n"
        f"📱 Telefon: {user.phone or '—'}\n"
        f"🎂 Tug'ilgan kun: {birthday_text}\n"
        f"🏷 Rol: {role_text}\n"
        f"📅 Ro'yxatdan o'tgan: {user.created_at.strftime('%d.%m.%Y')}"
    )

    # Add keyboard to set birthday if not set
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if not user.birthday:
        builder.row(InlineKeyboardButton(text="🎂 Tug'ilgan kun qo'shish", callback_data="profile:set_birthday"))
    else:
        builder.row(InlineKeyboardButton(text="🎂 Tug'ilgan kunni o'zgartirish", callback_data="profile:set_birthday"))

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data == "profile:set_birthday")
async def set_birthday_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileStates.waiting_for_birthday)
    await callback.message.edit_text(
        "🎂 <b>Tug'ilgan kuningizni kiriting</b>\n\n"
        "Format: <code>DD.MM.YYYY</code> (masalan: 15.03.1995)\n\n"
        "Bekor qilish uchun /cancel",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ProfileStates.waiting_for_birthday, Command("cancel"))
async def set_birthday_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Tug'ilgan kun kiritish bekor qilindi.")


@router.message(ProfileStates.waiting_for_birthday)
async def set_birthday_save(message: Message, state: FSMContext, session: AsyncSession):
    import re
    date_str = message.text.strip()

    # Parse DD.MM.YYYY format
    match = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
    if not match:
        await message.answer(
            "❌ Noto'g'ri format. Iltimos DD.MM.YYYY formatida kiriting:\n"
            "(masalan: 15.03.1995)"
        )
        return

    day, month, year = map(int, match.groups())

    try:
        birthday = datetime.date(year, month, day)
    except ValueError:
        await message.answer("❌ Noto'g'ri sana. Iltimos qayta kiriting:")
        return

    # Save birthday
    user = await session.get(User, message.from_user.id)
    if not user:
        await message.answer("Xatolik yuz berdi.")
        await state.clear()
        return

    user.birthday = birthday
    await session.commit()
    await state.clear()

    await message.answer(
        f"✅ <b>Tug'ilgan kuningiz saqlandi!</b>\n\n"
        f"🎂 {birthday.strftime('%d.%m.%Y')}\n\n"
        f"Har yili bu kuningiz bilan tabriklaymiz va maxsus sovg'a taqdim etamiz! 🎁",
        parse_mode="HTML"
    )


# ──────────────────────────────────────────────
# Group chat support
# ──────────────────────────────────────────────

# Simple in-memory storage for muted groups (chat_id -> mute_status)
_muted_groups = set()


def is_group_muted(chat_id: int) -> bool:
    """Check if bot is muted in this group."""
    return chat_id in _muted_groups


@router.message(CommandStart(), F.chat.type.in_({"group", "supergroup"}))
async def cmd_start_group(message: Message):
    """Welcome message when bot is added to a group."""
    if is_group_muted(message.chat.id):
        return  # Don't respond if muted

    bot_username = (await message.bot.me()).username
    await message.answer(
        f"👋 <b>Assalomu alaykum!</b>\n\n"
        f"Men sartaroshlar va mijozlarni ulaydigan botman.\n\n"
        f"<b>Buyruqlar:</b>\n"
        f"• /start - Bosh menyu\n"
        f"• /help - Yordam\n"
        f"• /mute - Bot xabarlarini o'chirish (faqat adminlar)\n\n"
        f"Shaxsiy xabarlarimda to'liq ishlash mumkin: @{bot_username}",
        parse_mode="HTML"
    )


@router.message(Command("help"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_help_group(message: Message):
    """Help command for groups."""
    if is_group_muted(message.chat.id):
        return  # Don't respond if muted

    bot_username = (await message.bot.me()).username
    await message.answer(
        f"ℹ️ <b>Bot haqida</b>\n\n"
        f"Bu bot sartaroshlar va mijozlarni ulaydi:\n\n"
        f"👤 <b>Mijozlar uchun:</b>\n"
        f"• Sartarosh toping\n"
        f"• Xizmat tanlang\n"
        f"• Qulay vaqtga yoziling\n\n"
        f"✂️ <b>Sartaroshlar uchun:</b>\n"
        f"• Profilingizni yarating\n"
        f"• Xizmatlar qo'shing\n"
        f"• Uchrashuvlarni boshqaring\n\n"
        f"<b>Admin buyruqlari:</b>\n"
        f"• /mute - Bot javoblarini o'chirish\n"
        f"• /unmute - Bot javoblarini yoqish\n\n"
        f"To'liq funksiya uchun botga shaxsiy xabar yuboring: @{bot_username}",
        parse_mode="HTML"
    )


@router.message(Command("mute"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_mute_group(message: Message):
    """Mute bot in this group (admin only)."""
    # Check if user is admin
    try:
        chat_member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        if chat_member.status not in {"administrator", "creator"}:
            await message.answer("⚠️ Bu buyruq faqat adminlar uchun!")
            return
    except Exception:
        return

    _muted_groups.add(message.chat.id)
    await message.answer(
        "🔇 <b>Bot javoblari o'chirildi</b>\n\n"
        "Bot endi bu guruhda xabar yubormaydi.\n"
        "Yoqish uchun: /unmute"
    )


@router.message(Command("unmute"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_unmute_group(message: Message):
    """Unmute bot in this group (admin only)."""
    # Check if user is admin
    try:
        chat_member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        if chat_member.status not in {"administrator", "creator"}:
            await message.answer("⚠️ Bu buyruq faqat adminlar uchun!")
            return
    except Exception:
        return

    _muted_groups.discard(message.chat.id)
    await message.answer(
        "🔊 <b>Bot javoblari yoqildi</b>\n\n"
        "Bot endi bu guruhda yana xabar yuboradi."
    )


@router.message(F.chat.type.in_({"group", "supergroup"}), F.text.contains("@"))
async def mention_handler(message: Message):
    """Respond when bot is mentioned in a group."""
    if is_group_muted(message.chat.id):
        return  # Don't respond if muted

    try:
        bot_user = await message.bot.me()
        if f"@{bot_user.username}" in message.text:
            await message.reply(
                f"👋 Salom! Men shaxsiy xabarlarimda to'liq ishlayman.\n"
                f"Murojaat uchun: @{bot_user.username}"
            )
    except Exception:
        pass
