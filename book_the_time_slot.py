from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext, Filters
from datetime import datetime, timedelta
import sqlite3
import logging

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
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id text, booking_date text, start_time text, end_time text)''')

# Save (commit) the changes
conn.commit()

def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Book a time", callback_data='1'),
         InlineKeyboardButton("Cancel time", callback_data='2')],
        [InlineKeyboardButton("View your bookings", callback_data='3')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Please choose:', reply_markup=reply_markup)

# Helper function to generate the next 7 days
def generate_dates():
    dates = [datetime.now() + timedelta(days=i) for i in range(7)]
    return [date.strftime('%Y-%m-%d (%A)') for date in dates]

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
        start(update, context)

def display_booked_times(update: Update, context: CallbackContext, selected_date: str) -> None:
    # Create a new SQLite connection and cursor
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    # Query the database for the bookings on the selected date
    c.execute("SELECT * FROM bookings WHERE booking_date = ? ORDER BY start_time", (selected_date,))

    bookings = c.fetchall()

    # Close the connection
    conn.close()

    if bookings:
        message_text = "The following time slots are already taken on this date:\n"
        for booking in bookings:
            _, _, _, start_time, end_time = booking
            message_text += f"From {start_time} to {end_time}\n"
        context.bot.send_message(chat_id=update.effective_chat.id, text=message_text)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="No time slots are booked on this date.")

from dateutil.parser import parse as parse_time

def book_time(update: Update, context: CallbackContext) -> None:
    if update.message is not None:
        message_text = update.message.text
        if 'selected_date' in context.user_data:
            try:
                start_time, end_time = message_text.split('-')
                # Check if the start time is later than or equal to the end time
                if start_time >= end_time:
                    update.message.reply_text("The start time cannot be later than or equal to the end time.")
                    return

                booking_date = context.user_data['selected_date']
                user_id = update.message.from_user.id

                conn = sqlite3.connect('bookings.db')
                c = conn.cursor()

                # Convert the times to datetime objects and subtract 30 minutes from the start time and add 30 minutes to the end time
                start_time_datetime = parse_time(start_time) - timedelta(minutes=30)
                end_time_datetime = parse_time(end_time) + timedelta(minutes=30)

                # Format the times back to strings
                start_time_30_min_prior = start_time_datetime.strftime('%H:%M')
                end_time_30_min_after = end_time_datetime.strftime('%H:%M')

                # Check if the time slot is available
                c.execute("SELECT * FROM bookings WHERE booking_date = ? AND ((start_time <= ? AND end_time > ?) OR (start_time < ? AND end_time >= ?))", (booking_date, start_time_30_min_prior, start_time_30_min_prior, end_time_30_min_after, end_time_30_min_after))
                if c.fetchone() is None:
                    c.execute("INSERT INTO bookings VALUES (NULL, ?, ?, ?, ?)", (user_id, booking_date, start_time, end_time))
                    conn.commit()
                    update.message.reply_text(f"Successfully booked time slot from {start_time} to {end_time} on {booking_date}")
                else:
                    update.message.reply_text("This time slot or the time slot 30 minutes prior or after is already taken")
                start(update, context)

                conn.close()
            except ValueError:
                update.message.reply_text("Please enter a valid time range in the format 'HH:MM-HH:MM'")
        else:
            update.message.reply_text("Please select a date first by clicking 'Book a time'")
            start(update, context)

def view_bookings(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    # Get the current date
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Retrieve the user's bookings
    c.execute("SELECT * FROM bookings WHERE user_id = ? AND booking_date >= ? ORDER BY booking_date, start_time", (user_id, current_date))

    bookings = c.fetchall()

    conn.close()

    if bookings:
        message_text = "Your bookings are:\n"
        for booking in bookings:
            id, _, booking_date, start_time, end_time = booking
            message_text += f"{booking_date}: from {start_time} to {end_time}\n"
        update.callback_query.edit_message_text(message_text)
    else:
        update.callback_query.edit_message_text("You have no upcoming bookings.")
    start(update, context)

def cancel_time(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    # Retrieve the user's bookings
    c.execute("SELECT * FROM bookings WHERE user_id = ?", (user_id,))

    bookings = c.fetchall()

    conn.close()

    if bookings:
        keyboard = []
        for booking in bookings:
            id, _, booking_date, start_time, end_time = booking
            keyboard.append([InlineKeyboardButton(f"{booking_date}: from {start_time} to {end_time}", callback_data=f'cancel_{id}_{booking_date}_{start_time}_{end_time}')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.edit_message_text('Please choose a booking to cancel:', reply_markup=reply_markup)
    else:
        update.callback_query.edit_message_text("You have no bookings.")
    start(update, context)

def delete_booking(update: Update, context: CallbackContext) -> None:
    if update.callback_query.data.startswith('cancel_'):
        user_id = update.callback_query.from_user.id
        _, id, booking_date, start_time, end_time = update.callback_query.data.split('_')

        conn = sqlite3.connect('bookings.db')
        c = conn.cursor()

        # Delete the booking
        c.execute("DELETE FROM bookings WHERE id = ?", (id,))

        conn.commit()

        conn.close()

        update.callback_query.edit_message_text(f"Cancelled booking on {booking_date} from {start_time} to {end_time}")
        start(update, context)

def main() -> None:
    updater = Updater('YOUR_TOKEN', use_context=True)

    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button, pattern='^(?!cancel_)'))
    dispatcher.add_handler(CallbackQueryHandler(delete_booking, pattern='^cancel_'))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, book_time))

    updater.start_polling()

    updater.idle()

if __name__ == '__main__':
    main()
