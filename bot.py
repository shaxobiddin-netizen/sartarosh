import asyncio
import logging
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, and_

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import config
from database.db import init_db, close_db, async_session_maker
from database.models import Appointment, AppointmentStatus, User, NotificationLog, BarberProfile
from middlewares import DbSessionMiddleware
from handlers import common, barber, client, admin, ai_assistant

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def send_reminders(bot: Bot):
    """Background job to send reminders at multiple intervals."""
    now = datetime.datetime.now()
    today = now.date()

    async with async_session_maker() as session:
        # ──────────────────────────────────────────────
        # 1. 1 DAY BEFORE reminders (for tomorrow's appointments)
        # ──────────────────────────────────────────────
        tomorrow = today + datetime.timedelta(days=1)
        stmt_day = select(Appointment).where(
            and_(
                Appointment.status == AppointmentStatus.CONFIRMED,
                Appointment.appointment_date == tomorrow
            )
        )
        result_day = await session.execute(stmt_day)
        for appt in result_day.scalars().all():
            # Check if 1-day reminder already sent
            log_stmt = select(NotificationLog).where(
                and_(
                    NotificationLog.appointment_id == appt.id,
                    NotificationLog.notification_type == "reminder_1d"
                )
            )
            if (await session.execute(log_stmt)).scalar():
                continue

            # Send evening reminder (after 18:00)
            if now.hour >= 18:
                try:
                    await bot.send_message(
                        appt.client_id,
                        f"📅 <b>Ertangi uchrashuv eslatmasi</b>\n\n"
                        f"Ertaga sizning uchrashuvingiz bor:\n"
                        f"🕒 Vaqt: {appt.start_time.strftime('%H:%M')}\n"
                        f"✂️ Sartarosh: {appt.barber.salon_name or 'Sartarosh'}\n"
                        f"📍 Manzil: {appt.barber.address or '—'}\n\n"
                        f"Tayyor turishingizni unutmang! 👋"
                    )
                    # Log
                    session.add(NotificationLog(
                        user_id=appt.client_id,
                        appointment_id=appt.id,
                        notification_type="reminder_1d",
                        message_text="1-day reminder sent"
                    ))
                except Exception as e:
                    logger.error(f"Error sending 1-day reminder: {e}")

        # ──────────────────────────────────────────────
        # 2. MORNING reminders (all appointments today)
        # ──────────────────────────────────────────────
        if now.hour == 8 and now.minute < 5:  # 8:00 AM
            stmt_morning = select(Appointment).where(
                and_(
                    Appointment.status == AppointmentStatus.CONFIRMED,
                    Appointment.appointment_date == today
                )
            )
            result_morning = await session.execute(stmt_morning)
            for appt in result_morning.scalars().all():
                try:
                    await bot.send_message(
                        appt.client_id,
                        f"🌅 <b>Kunlik eslatma</b>\n\n"
                        f"Bugun sizda uchrashuv bor:\n"
                        f"🕒 {appt.start_time.strftime('%H:%M')} - {appt.barber.salon_name or 'Sartarosh'}\n\n"
                        f"Omadli kun! ✨"
                    )
                except Exception as e:
                    logger.error(f"Error sending morning reminder: {e}")

        # ──────────────────────────────────────────────
        # 3. 3 HOURS BEFORE reminders
        # ──────────────────────────────────────────────
        stmt_3h = select(Appointment).where(
            and_(
                Appointment.status == AppointmentStatus.CONFIRMED,
                Appointment.appointment_date == today
            )
        )
        result_3h = await session.execute(stmt_3h)
        for appt in result_3h.scalars().all():
            log_stmt = select(NotificationLog).where(
                and_(
                    NotificationLog.appointment_id == appt.id,
                    NotificationLog.notification_type == "reminder_3h"
                )
            )
            if (await session.execute(log_stmt)).scalar():
                continue

            appt_time = datetime.datetime.combine(today, appt.start_time)
            diff = appt_time - now

            # 2:50-3:10 hours away
            if datetime.timedelta(minutes=170) <= diff <= datetime.timedelta(minutes=190):
                try:
                    await bot.send_message(
                        appt.client_id,
                        f"⏰ <b>3 soatdan so'ng</b>\n"
                        f"Sizning uchrashuvingiz boshlanadi!\n"
                        f"🕒 {appt.start_time.strftime('%H:%M')} - {appt.barber.salon_name or 'Sartarosh'}"
                    )
                    session.add(NotificationLog(
                        user_id=appt.client_id,
                        appointment_id=appt.id,
                        notification_type="reminder_3h",
                        message_text="3-hour reminder sent"
                    ))
                except Exception as e:
                    logger.error(f"Error sending 3h reminder: {e}")

        # ──────────────────────────────────────────────
        # 4. 1 HOUR BEFORE reminders (existing)
        # ──────────────────────────────────────────────
        stmt_1h = select(Appointment).where(
            and_(
                Appointment.status == AppointmentStatus.CONFIRMED,
                Appointment.appointment_date == today
            )
        )
        result_1h = await session.execute(stmt_1h)
        for appt in result_1h.scalars().all():
            log_stmt = select(NotificationLog).where(
                and_(
                    NotificationLog.appointment_id == appt.id,
                    NotificationLog.notification_type == "reminder_1h"
                )
            )
            if (await session.execute(log_stmt)).scalar():
                continue

            appt_time = datetime.datetime.combine(today, appt.start_time)
            diff = appt_time - now

            if datetime.timedelta(minutes=50) <= diff <= datetime.timedelta(minutes=70):
                # Send to client
                try:
                    await bot.send_message(
                        appt.client_id,
                        f"⏰ <b>Eslatma:</b> Sizning uchrashuvingizga 1 soatga yaqin vaqt qoldi!\n"
                        f"🕒 Vaqt: {appt.start_time.strftime('%H:%M')}\n"
                        f"📍 Manzil: {appt.barber.address or '—'}"
                    )
                except Exception as e:
                    logger.error(f"Error sending 1h client reminder: {e}")

                # Send to barber
                try:
                    await bot.send_message(
                        appt.barber.user_id,
                        f"⏰ <b>Eslatma:</b> Keyingi uchrashuvga 1 soat qoldi!\n"
                        f"👤 Mijoz: {appt.client.first_name}\n"
                        f"🕒 Vaqt: {appt.start_time.strftime('%H:%M')}"
                    )
                except Exception as e:
                    logger.error(f"Error sending 1h barber reminder: {e}")

                session.add(NotificationLog(
                    user_id=appt.client_id,
                    appointment_id=appt.id,
                    notification_type="reminder_1h",
                    message_text="1-hour reminder sent"
                ))

        await session.commit()


async def send_birthday_wishes(bot: Bot):
    """Background job to send birthday wishes every morning."""
    now = datetime.datetime.now()
    today = now.date()

    async with async_session_maker() as session:
        # Find users whose birthday is today and haven't been notified this year
        from sqlalchemy import extract
        stmt = select(User).where(
            and_(
                extract('month', User.birthday) == today.month,
                extract('day', User.birthday) == today.day,
                User.birthday_notified_this_year == False,
                User.is_active == True
            )
        )
        result = await session.execute(stmt)
        birthday_users = result.scalars().all()

        for user in birthday_users:
            try:
                # Send birthday greeting with promo code
                await bot.send_message(
                    user.id,
                    f"🎂 <b>Tug'ilgan kuningiz bilan!</b> 🎉\n\n"
                    f"Hurmatli {user.first_name}, sizni bugungi ajoyib kuningiz bilan tabriklaymiz!\n\n"
                    f"🎁 <b>Sovg'a:</b> Bugun bron qilgan uchrashuvingizga <b>20% chegirma!</b>\n"
                    f"Promo kod: <code>HBD20</code>\n\n"
                    f"Yana bir yil sog'lik va farovonlik tilaymiz! 🙏",
                    parse_mode="HTML"
                )

                # Mark as notified
                user.birthday_notified_this_year = True
                logger.info(f"Sent birthday wish to user {user.id}")

            except Exception as e:
                logger.error(f"Error sending birthday wish to {user.id}: {e}")

        # Reset flags on January 1st for new year
        if today.month == 1 and today.day == 1:
            reset_stmt = select(User).where(User.birthday_notified_this_year == True)
            reset_result = await session.execute(reset_stmt)
            for user in reset_result.scalars().all():
                user.birthday_notified_this_year = False

        await session.commit()


async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🚀 Botni ishga tushirish"),
        BotCommand(command="help", description="❓ Yordam"),
        BotCommand(command="profile", description="👤 Profilim"),
    ]
    await bot.set_my_commands(commands)


async def main():
    # Initialize database (create tables)
    await init_db()
    logger.info("✅ Database initialized")

    # Create bot & dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register startup hook (sets /start menu button)
    dp.startup.register(set_bot_commands)

    # Register middleware
    dp.update.middleware(DbSessionMiddleware())

    # Register routers
    dp.include_router(admin.router)
    dp.include_router(common.router)
    dp.include_router(barber.router)
    dp.include_router(client.router)
    dp.include_router(ai_assistant.router)

    # Initialize scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, "interval", minutes=5, args=[bot])
    scheduler.add_job(send_birthday_wishes, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()
    logger.info("⏰ Scheduler started (Reminders every 5 min, Birthday wishes at 9 AM)")

    logger.info("🤖 Bot starting...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await close_db()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
