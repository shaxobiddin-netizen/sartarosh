from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_role = State()


class BarberProfileStates(StatesGroup):
    waiting_for_salon_name = State()
    waiting_for_address = State()
    waiting_for_location = State()
    waiting_for_bio = State()
    waiting_for_work_start = State()
    waiting_for_work_end = State()
    waiting_for_schedule = State()
    waiting_for_work_hours = State()


class PortfolioStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_title = State()
    waiting_for_description = State()


class ServiceStates(StatesGroup):
    waiting_for_service_name = State()
    waiting_for_service_price = State()
    waiting_for_service_duration = State()
    waiting_for_service_description = State()


class BookingStates(StatesGroup):
    selecting_barber = State()
    selecting_service = State()
    selecting_date = State()
    selecting_time = State()
    confirming = State()


class AppointmentPhotoStates(StatesGroup):
    waiting_for_photo = State()


class ChatStates(StatesGroup):
    waiting_for_message_to_barber = State()
    waiting_for_message_to_client = State()


class AdvertisementStates(StatesGroup):
    waiting_for_ad_content = State()
    waiting_for_ad_target = State()
    waiting_for_ad_photo = State()
    waiting_for_promo_code = State()
    waiting_for_promo_percent = State()
    waiting_for_promo_max_uses = State()
    waiting_for_promo_expiry = State()
    waiting_for_promo_confirm = State()


class BookingPromoStates(StatesGroup):
    waiting_for_promo_input = State()


class ReviewStates(StatesGroup):
    waiting_for_rating = State()
    waiting_for_comment = State()
    waiting_for_confirm = State()


class CancellationStates(StatesGroup):
    waiting_for_reason = State()
    waiting_for_confirm = State()


class NoteStates(StatesGroup):
    waiting_for_note_text = State()
    waiting_for_category = State()
