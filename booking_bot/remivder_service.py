from apscheduler.schedulers.blocking import BlockingScheduler
import pytz
import sqlite3
import datetime
import logging
from telegram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the bot
bot = Bot(token='YOUR_API_KEY_GOES_HERE')

# Function to send start reminders
def send_start_reminders():
    # Create a new SQLite connection and cursor
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    now = datetime.datetime.now()

    time_in_15_min = now + datetime.timedelta(minutes=15)

    # Retrieve bookings that are due to start in 15 minutes on the same day
    c.execute("SELECT * FROM bookings WHERE booking_date = ? AND start_time = ?", (now.strftime('%Y-%m-%d'), time_in_15_min.strftime('%H:%M')))
    bookings = c.fetchall()

    # Send a reminder for each booking
    for booking in bookings:
        id, user_id, booking_date, start_time, end_time = booking
        bot.send_message(chat_id=user_id, text=f"Reminder: Your booking is due to start at {start_time}")

    # Close the SQLite connection
    conn.close()

# Function to send end reminders
def send_end_reminders():
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    now = datetime.datetime.now()

    c.execute("SELECT * FROM bookings WHERE booking_date = ? AND end_time = ?", (now.strftime('%Y-%m-%d'), now.strftime('%H:%M')))
    bookings = c.fetchall()
    
    for booking in bookings:
        id, user_id, booking_date, start_time, end_time = booking
        bot.send_message(chat_id=user_id, text=f"Your booking has ended at {end_time}. Thank you for using our service.")

    conn.close()

# Initialize the scheduler
scheduler = BlockingScheduler(timezone=pytz.utc)

# Add a job to send start reminders every minute
scheduler.add_job(send_start_reminders, 'interval', minutes=1)

# Add a job to send end reminders every minute
scheduler.add_job(send_end_reminders, 'interval', minutes=1)

scheduler.start()
