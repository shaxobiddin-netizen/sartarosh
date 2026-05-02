import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, DateTime, Date, Time,
    Float, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class UserRole(str, enum.Enum):
    CLIENT = "client"
    BARBER = "barber"
    ADMIN = "admin"


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentProvider(str, enum.Enum):
    CLICK = "click"
    PAYME = "payme"
    CASH = "cash"


class DayOfWeek(str, enum.Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=False)
    """Telegram user_id — primary key"""

    username = Column(String(64), nullable=True)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=True)
    phone = Column(String(20), nullable=True)

    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.CLIENT)
    is_active = Column(Boolean, default=True, nullable=False)

    birthday = Column(Date, nullable=True)
    """Tug'ilgan kun (MM-DD format)"""

    birthday_notified_this_year = Column(Boolean, default=False, nullable=False)
    """Bu yili tug'ilgan kun tabrigi yuborilganmi"""

    language = Column(String(10), default="uz", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # relationships
    barber_profile = relationship("BarberProfile", back_populates="user", uselist=False, lazy="selectin")
    appointments_as_client = relationship(
        "Appointment",
        foreign_keys="Appointment.client_id",
        back_populates="client",
        lazy="selectin",
    )
    payments = relationship("Payment", back_populates="user", lazy="selectin")


class BarberProfile(Base):
    __tablename__ = "barber_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)

    salon_name = Column(String(256), nullable=True)
    address = Column(String(512), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    bio = Column(Text, nullable=True)

    # Subscription info
    subscription_active = Column(Boolean, default=False, nullable=False)
    subscription_until = Column(Date, nullable=True)

    # Work hours settings
    work_start = Column(Time, nullable=True)
    work_end = Column(Time, nullable=True)
    slot_duration = Column(Integer, default=30, nullable=False)  # minutes
    max_clients_per_day = Column(Integer, default=20, nullable=False)

    # Statistics
    total_appointments = Column(Integer, default=0, nullable=False)
    rating = Column(Float, default=0.0, nullable=False)
    review_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # relationships
    user = relationship("User", back_populates="barber_profile", lazy="selectin")
    schedules = relationship("BarberSchedule", back_populates="barber", lazy="selectin")
    services = relationship("Service", back_populates="barber", lazy="selectin")
    appointments_as_barber = relationship(
        "Appointment",
        foreign_keys="Appointment.barber_id",
        back_populates="barber",
        lazy="selectin",
    )
    portfolio_items = relationship("PortfolioItem", back_populates="barber", lazy="selectin")
    promo_codes = relationship("PromoCode", back_populates="barber", lazy="selectin")
    reviews = relationship("Review", back_populates="barber", lazy="selectin")
    client_notes = relationship("ClientNote", back_populates="barber", lazy="selectin")


class BarberSchedule(Base):
    __tablename__ = "barber_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barber_id = Column(Integer, ForeignKey("barber_profiles.id"), nullable=False)

    day_of_week = Column(SAEnum(DayOfWeek), nullable=False)
    is_working = Column(Boolean, default=True, nullable=False)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)

    # relationships
    barber = relationship("BarberProfile", back_populates="schedules", lazy="selectin")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barber_id = Column(Integer, ForeignKey("barber_profiles.id"), nullable=False)

    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)  # so'm
    duration = Column(Integer, nullable=False)  # minutes
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # relationships
    barber = relationship("BarberProfile", back_populates="services", lazy="selectin")
    appointments = relationship("Appointment", back_populates="service", lazy="selectin")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barber_id = Column(Integer, ForeignKey("barber_profiles.id"), nullable=False)
    client_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)

    appointment_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    status = Column(
        SAEnum(AppointmentStatus),
        nullable=False,
        default=AppointmentStatus.PENDING,
    )
    notes = Column(Text, nullable=True)

    cancellation_reason = Column(String(256), nullable=True)
    """Bekor qilish sababi"""

    cancelled_by = Column(String(20), nullable=True)
    """Kim tomonidan bekor qilingan: client, barber, system"""

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # relationships
    barber = relationship("BarberProfile", back_populates="appointments_as_barber", lazy="selectin")
    client = relationship(
        "User", foreign_keys=[client_id], back_populates="appointments_as_client", lazy="selectin"
    )
    service = relationship("Service", back_populates="appointments", lazy="selectin")
    photos = relationship("AppointmentPhoto", back_populates="appointment", lazy="selectin")
    payment = relationship("Payment", back_populates="appointment", uselist=False, lazy="selectin")
    review = relationship("Review", back_populates="appointment", uselist=False, lazy="selectin")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), unique=True, nullable=False)
    client_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    barber_id = Column(Integer, ForeignKey("barber_profiles.id"), nullable=False)

    rating = Column(Integer, nullable=False)
    """1-5 yulduz reyting"""

    comment = Column(Text, nullable=True)
    """Mijozning sharhi/takifi"""

    is_visible = Column(Boolean, default=True, nullable=False)
    """Sartarosh tomonidan yashirish mumkin"""

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # relationships
    appointment = relationship("Appointment", back_populates="review", lazy="selectin")
    client = relationship("User", foreign_keys=[client_id], lazy="selectin")
    barber = relationship("BarberProfile", back_populates="reviews", lazy="selectin")


class ClientNote(Base):
    __tablename__ = "client_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barber_id = Column(Integer, ForeignKey("barber_profiles.id"), nullable=False)
    client_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)

    note_text = Column(Text, nullable=False)
    """Sartaroshning mijoz haqida qaydi"""

    category = Column(String(50), nullable=True)
    """Kategoriya: preference, allergy, history, etc."""

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # relationships
    barber = relationship("BarberProfile", back_populates="client_notes", lazy="selectin")
    client = relationship("User", foreign_keys=[client_id], lazy="selectin")


class AppointmentPhoto(Base):
    __tablename__ = "appointment_photos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)

    file_id = Column(String(512), nullable=False)
    """Telegram file_id"""

    angle = Column(String(20), nullable=True)
    """Rasm burchagi: front, back, left, right, top, etc."""

    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # relationships
    appointment = relationship("Appointment", back_populates="photos", lazy="selectin")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)

    amount = Column(Integer, nullable=False)  # so'm
    provider = Column(SAEnum(PaymentProvider), nullable=False)
    status = Column(SAEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)

    # To'lov tizimi ma'lumotlari
    transaction_id = Column(String(128), nullable=True)
    perform_time = Column(DateTime, nullable=True)
    cancel_time = Column(DateTime, nullable=True)
    reason = Column(String(256), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # relationships
    user = relationship("User", back_populates="payments", lazy="selectin")
    appointment = relationship("Appointment", back_populates="payment", lazy="selectin")


class PortfolioItem(Base):
    __tablename__ = "portfolio_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barber_id = Column(Integer, ForeignKey("barber_profiles.id"), nullable=False)

    file_id = Column(String(512), nullable=False)
    """Telegram photo file_id"""

    title = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # relationships
    barber = relationship("BarberProfile", back_populates="portfolio_items", lazy="selectin")


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barber_id = Column(Integer, ForeignKey("barber_profiles.id"), nullable=False)

    code = Column(String(50), nullable=False, unique=True)
    """Promo code text (e.g., SALE20)"""

    discount_percent = Column(Integer, nullable=False, default=10)
    """Discount percentage (e.g., 20 for 20%)"""

    max_uses = Column(Integer, nullable=False, default=100)
    """Maximum number of times this code can be used"""

    used_count = Column(Integer, nullable=False, default=0)
    """How many times this code has been used"""

    is_active = Column(Boolean, nullable=False, default=True)
    """Whether this promo code is currently active"""

    expires_at = Column(DateTime, nullable=True)
    """Optional expiration date"""

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # relationships
    barber = relationship("BarberProfile", back_populates="promo_codes", lazy="selectin")


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)

    notification_type = Column(String(64), nullable=False)
    """reminder, confirmation, cancellation, subscription_expiry"""

    channel = Column(String(32), nullable=False, default="telegram")
    message_text = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
class Blacklist(Base):
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barber_id = Column(Integer, ForeignKey("barber_profiles.id"), nullable=False)
    client_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    
    reason = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
