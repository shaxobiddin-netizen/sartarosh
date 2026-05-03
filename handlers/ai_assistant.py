"""handlers/ai_assistant.py — AI yordamchi, avtomatik FAQ javoblari"""
import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import FAQ, User
from middlewares import DbSessionMiddleware

router = Router()
router.message.middleware(DbSessionMiddleware())
router.callback_query.middleware(DbSessionMiddleware())


# ──────────────────────────────────────────────
# AI Assistant for clients - Avtomatik javoblar
# ──────────────────────────────────────────────

@router.message(F.text)
async def ai_faq_handler(message: Message, session: AsyncSession):
    """Avtomatik FAQ javoblari - har bir xabarni tekshiradi."""
    # Faqat matnli xabarlarni qayta ishlaymiz
    if not message.text:
        return

    # Admin/barber commands should not trigger AI
    if message.text.startswith('/'):
        return

    # Get user language
    user = await session.get(User, message.from_user.id)
    lang = user.language if user else "uz"

    # Search for matching FAQ
    text_lower = message.text.lower()
    words = set(text_lower.split())

    # Get all active FAQs
    stmt = select(FAQ).where(FAQ.is_active == True)
    result = await session.execute(stmt)
    faqs = result.scalars().all()

    best_match = None
    best_score = 0

    for faq in faqs:
        # Parse keywords
        keywords = [k.strip().lower() for k in faq.keywords.split(',')]
        score = sum(1 for kw in keywords if kw in text_lower or any(kw in word for word in words))

        if score > best_score:
            best_score = score
            best_match = faq

    # Agar 1 dan ko'p kalit so'z mos kelsa, javob yuboramiz
    if best_match and best_score >= 1:
        # Update usage count
        best_match.usage_count += 1
        await session.commit()

        # Select answer based on language
        if lang == "ru" and best_match.answer_ru:
            answer = best_match.answer_ru
        else:
            answer = best_match.answer_uz

        await message.reply(
            f"🤖 <b>Avtomatik yordamchi:</b>\n\n{answer}\n\n"
            f"<i>Batafsil yordam uchun @admin ga murojaat qiling.</i>",
            parse_mode="HTML"
        )


# ──────────────────────────────────────────────
# Admin FAQ Management
# ──────────────────────────────────────────────

@router.message(Command("faq_admin"))
async def faq_admin_panel(message: Message, session: AsyncSession):
    """Admin panel for managing FAQs."""
    from config import config
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return

    from keyboards import kb_faq_admin

    # Get FAQ stats
    total = await session.scalar(select(func.count(FAQ.id)))
    active = await session.scalar(select(func.count(FAQ.id)).where(FAQ.is_active == True))

    await message.answer(
        f"🤖 <b>FAQ Boshqaruvi</b>\n\n"
        f"📋 Jami savollar: <b>{total}</b>\n"
        f"✅ Aktiv: <b>{active}</b>\n\n"
        f"Yangi savol qo'shish yoki mavjudlarini boshqarish:",
        parse_mode="HTML",
        reply_markup=kb_faq_admin()
    )


@router.callback_query(F.data == "faq:list")
async def faq_list(callback: CallbackQuery, session: AsyncSession):
    """List all FAQs."""
    from config import config
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("Admin huquqi yo'q!", show_alert=True)
        return

    stmt = select(FAQ).order_by(FAQ.usage_count.desc())
    result = await session.execute(stmt)
    faqs = result.scalars().all()

    if not faqs:
        await callback.answer("Hali savollar qo'shilmagan.", show_alert=True)
        return

    text = "📋 <b>FAQ Ro'yxati</b>\n\n"
    for i, faq in enumerate(faqs[:10], 1):
        status = "✅" if faq.is_active else "❌"
        text += f"{i}. {status} <b>{faq.question_uz[:40]}...</b>\n"
        text += f"   🔑 Kalit so'zlar: {faq.keywords[:50]}...\n"
        text += f"   📊 {faq.usage_count} marta ishlatilgan\n\n"

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "faq:stats")
async def faq_stats(callback: CallbackQuery, session: AsyncSession):
    """Show FAQ usage statistics."""
    from config import config
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("Admin huquqi yo'q!", show_alert=True)
        return

    total = await session.scalar(select(func.count(FAQ.id)))
    active = await session.scalar(select(func.count(FAQ.id)).where(FAQ.is_active == True))
    total_usage = await session.scalar(select(func.sum(FAQ.usage_count))) or 0

    # Top 5 most used
    stmt = select(FAQ).order_by(FAQ.usage_count.desc()).limit(5)
    result = await session.execute(stmt)
    top_faqs = result.scalars().all()

    text = (
        f"📊 <b>FAQ Statistikasi</b>\n\n"
        f"📋 Jami savollar: <b>{total}</b>\n"
        f"✅ Aktiv: <b>{active}</b>\n"
        f"🎯 Jami foydalanish: <b>{total_usage}</b>\n\n"
        f"🏆 <b>Eng mashhur savollar:</b>\n"
    )

    for i, faq in enumerate(top_faqs, 1):
        text += f"{i}. {faq.question_uz[:40]}... ({faq.usage_count} marta)\n"

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()
