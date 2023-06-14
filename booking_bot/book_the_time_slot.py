from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext, Filters
from datetime import datetime, timedelta
import sqlite3
import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

local_tz = pytz.timezone('Europe/Moscow')

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a SQLite database connection
conn = sqlite3.connect('bookings.db')

# Create a cursor object
c = conn.cursor()

# Create table
c.execute('''CREATE TABLE IF NOT EXISTS bookings
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id text, start_booking_date text, end_booking_date text, start_time text, end_time text)''')

# Save (commit) the changes
conn.commit()

# Create scheduler
scheduler = BackgroundScheduler()
scheduler.start()

def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Book a time", callback_data='1'),
         InlineKeyboardButton("Cancel time", callback_data='2')],
        [InlineKeyboardButton("View your bookings", callback_data='3')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Check if update.message is None
    if update.message:
        update.message.reply_text('Please choose:', reply_markup=reply_markup)
    else:
        update.callback_query.message.reply_text('Please choose:', reply_markup=reply_markup)

# Helper function to generate the next 7 days
def generate_dates():
    dates = [datetime.now() + timedelta(days=i) for i in range(7)]
    return [date.strftime('%d.%m.%Y (%A)') for date in dates]

def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query

    query.answer()

    if query.data == '1':
        dates = generate_dates()
        keyboard = [[InlineKeyboardButton(date, callback_data=f'date_{date.split(" ")[0]}')] for date in dates]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text="Please choose a date:", reply_markup=reply_markup)
    elif query.data.startswith('date_'):
        selected_date = query.data[5:]
        context.user_data['selected_date'] = selected_date
        display_booked_times(update, context, selected_date)
        query.edit_message_text(text="Please send me the time range you want to book in the format 'HH:MM-HH:MM'")
    elif query.data == '2':
        cancel_time(update, context)
    elif query.data == '3':
        view_bookings(update, context)

def display_booked_times(update: Update, context: CallbackContext, selected_date: str) -> None:
    # Create a new SQLite connection and cursor
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    # Get the current date and time
    current_time = datetime.now().strftime('%H:%M')
    current_date = datetime.now().strftime('%d.%m.%Y')

    # Query the database for the bookings on the selected date
    c.execute("SELECT * FROM bookings WHERE start_booking_date = ? AND ((start_booking_date > ?) OR (start_booking_date = ? AND end_time >= ?)) ORDER BY start_time", (selected_date, current_date, current_date, current_time))

    bookings = c.fetchall()

    # Close the connection
    conn.close()

    if bookings:
        message_text = "The following time slots are already taken on this date:\n"
        for booking in bookings:
            _, _, start_booking_date, end_booking_date, start_time, end_time = booking
            
            message_text += f"From {start_booking_date} {start_time} to {end_booking_date} {end_time}\n"
        
        context.bot.send_message(chat_id=update.effective_chat.id, text=message_text)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="No time slots are booked on this date.")


from dateutil.parser import parse as parse_time

def book_time(update: Update, context: CallbackContext) -> None:
    if update.message is not None:
        message_text = update.message.text if update.message else update.callback_query.message.text
        if 'selected_date' in context.user_data:
            try:
                # Splitting the message text and striping leading and trailing whitespaces
                start_time, end_time = [time.strip() for time in message_text.replace('\u2013', '-').split('-')]

                # Convert start_time and end_time to datetime objects for comparison
                start_time_dt = datetime.strptime(start_time, "%H:%M")
                end_time_dt = datetime.strptime(end_time, "%H:%M")

                # Check if the start time is later than or equal to the end time
                if start_time_dt >= end_time_dt:
                    keyboard = [
                        [InlineKeyboardButton("Yes", callback_data='confirm_yes')],
                        [InlineKeyboardButton("No", callback_data='confirm_no')]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    update.message.reply_text("The start time is later than or equal to the end time. Do you want to book from this day till the next one?", reply_markup=reply_markup)
                    context.user_data['start_time'] = start_time
                    context.user_data['end_time'] = end_time
                    return

                process_booking(update, context, start_time, end_time)

            except ValueError as e:
                update.message.reply_text(f"Error: {e}\nPlease enter a valid time range in the format 'HH:MM-HH:MM'")

        else:
            update.message.reply_text("Please select a date first by clicking 'Book a time'")
            start(update, context)

def confirm_booking(update: Update, context: CallbackContext) -> None:
    if update.callback_query.data == 'confirm_yes':
        start_time = context.user_data['start_time']
        end_time = context.user_data['end_time']
        
        # Book from selected day till the next one
        # Set end_booking_date as the next day from selected_date
        context.user_data['selected_end_date'] = context.user_data['selected_date']
        
        process_booking(update, context, start_time, end_time)
    elif update.callback_query.data == 'confirm_no':
        start(update, context)  # Restart dialog

def process_booking(update: Update, context: CallbackContext, start_time: str, end_time: str) -> None:
    booking_start_date = context.user_data['selected_date']
    booking_end_date = context.user_data.get('selected_end_date', booking_start_date)  # get end date from context or use start date if not set
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id

    # To handle callback_query as well as message
    reply_func = update.message.reply_text if update.message else update.callback_query.message.reply_text

    # Create a new SQLite connection and cursor
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    try:
        # Convert the times to datetime objects and subtract 30 minutes from the start time and add 30 minutes to the end time
        start_time_datetime = parse_time(start_time) - timedelta(minutes=30)
        end_time_datetime = parse_time(end_time) + timedelta(minutes=30)

        # Format the times back to strings
        start_time_30_min_prior = start_time_datetime.strftime('%H:%M')
        end_time_30_min_after = end_time_datetime.strftime('%H:%M')

        # Check if the time slot is available
        c.execute("SELECT * FROM bookings WHERE start_booking_date = ? AND ((start_time <= ? AND end_time > ?) OR (start_time < ? AND end_time >= ?))", (booking_start_date, start_time_30_min_prior, start_time_30_min_prior, end_time_30_min_after, end_time_30_min_after))
        if c.fetchone() is None:
            # If start_time is later than or equal to end_time, the booking spans across two days
            if start_time >= end_time:
                booking_end_date = (datetime.strptime(booking_start_date, "%d.%m.%Y") + timedelta(days=1)).strftime('%d.%m.%Y')

            c.execute("INSERT INTO bookings VALUES (NULL, ?, ?, ?, ?, ?)", (user_id, booking_start_date, booking_end_date, start_time, end_time))
            conn.commit()

            reply_func(f"Successfully booked time slot from {booking_start_date} {start_time} to {booking_end_date} {end_time}")
        else:
            reply_func("This time slot or the time slot 30 minutes prior or after is already taken")

    finally:
        # Close the connection
        conn.close()

    start(update, context)

def view_bookings(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id

    # Create a new SQLite connection and cursor
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    # Get the current date and time
    current_date = datetime.now().strftime('%d.%m.%Y')
    current_time = datetime.now().strftime('%H:%M')

    # Retrieving the user's bookings
    c.execute("""
        SELECT * FROM bookings
        WHERE user_id = ? AND ((start_booking_date > ?) OR (start_booking_date = ? AND end_time > ?))
        ORDER BY start_booking_date, start_time
    """, (user_id, current_date, current_date, current_time))

    bookings = c.fetchall()

    # Close the connection
    conn.close()

    if bookings:
        message_text = "Your bookings are:\n"
        for booking in bookings:
            id, _, start_booking_date, end_booking_date, start_time, end_time = booking
            message_text += f"{start_booking_date}: from {start_time} to {end_time}\n"
        update.callback_query.edit_message_text(message_text)
    else:
        update.callback_query.edit_message_text("You have no upcoming bookings.")
    start(update, context)


def cancel_time(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id

    # Create a new SQLite connection and cursor
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    # Get the current datetime
    now = datetime.now()

    # Convert the datetime to the format used in the database
    current_datetime = now.strftime('%d.%m.%Y %H:%M')

    # Retrieve the user's bookings that are later than the current time
    c.execute("""
        SELECT * FROM bookings
        WHERE user_id = ? AND start_booking_date || ' ' || end_time > ?
        ORDER BY start_booking_date, start_time
    """, (user_id, current_datetime))

    bookings = c.fetchall()

    # Close the connection
    conn.close()

    if bookings:
        keyboard = []
        for booking in bookings:
            id, _, start_booking_date, end_booking_date, start_time, end_time = booking
            keyboard.append([InlineKeyboardButton(f"{start_booking_date}: from {start_time} to {end_time}", callback_data=f'cancel_{id}_{start_booking_date}_{end_booking_date}_{start_time}_{end_time}')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.edit_message_text('Please choose a booking to cancel:', reply_markup=reply_markup)
    else:
        update.callback_query.edit_message_text("You have no future bookings.")


def delete_booking(update: Update, context: CallbackContext) -> None:
    if update.callback_query.data.startswith('cancel_'):
        user_id = update.callback_query.from_user.id
        _, id, start_booking_date, end_booking_date, start_time, end_time = update.callback_query.data.split('_')

        # Create a new SQLite connection and cursor
        conn = sqlite3.connect('bookings.db')
        c = conn.cursor()

        # Delete the booking
        c.execute("DELETE FROM bookings WHERE id = ?", (id,))

        conn.commit()

        # Close the connection
        conn.close()

        update.callback_query.edit_message_text(f"Cancelled booking from {start_booking_date} to {end_booking_date} from {start_time} to {end_time}")
        start(update, context)

def send_reminder(user_id: int, start_booking_date: str, end_booking_date: str, start_time: str, end_time: str) -> None:
    context.bot.send_message(chat_id=user_id, text=f"You have a booking from {start_booking_date} to {end_booking_date} from {start_time} to {end_time}. This is your 15-minute reminder.")

def main() -> None:
    updater = Updater('KEY', use_context=True)

    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button, pattern='^(?!cancel_|confirm_)'))
    dispatcher.add_handler(CallbackQueryHandler(delete_booking, pattern='^cancel_'))
    dispatcher.add_handler(CallbackQueryHandler(confirm_booking, pattern='^confirm_'))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, book_time))

    updater.start_polling()

    updater.idle()

if __name__ == '__main__':
    main()
