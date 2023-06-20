# Booking Bot for Coliving Spaces 🏘️
<div align="left">
    <img src="assets/screencast.gif" alt="Booking bot demo">
</div>

---

## 📖 Overview
Booking Bot is a Telegram bot built to streamline and automate the process of booking a washing machine in a coliving space. 
It is built using the [python-telegram-bot v13.4.1](https://github.com/python-telegram-bot/python-telegram-bot/releases/tag/v13.4.1) library and uses SQLite3 as its database to store booking information.

## ✨ Features
- Book a time slot for using the washing machine.
- Cancel a previously booked time slot.
- View all booked time slots.
- Receive reminders 15 minutes prior to the start of a booking and immediately after the end of the booking.
- Automatic 30-minute cooldown period between bookings.

## 🛠️ Installation
### Prerequisites:
- Python 3.6 or higher
- SQLite3
- python-telegram-bot v13.4.1

### Steps:
1. Clone the repository:
```
git clone https://github.com/finchren/booking_bot.git
```
2. Navigate to the repository:
```
cd Booking_bot/src
```
3. Install the dependencies:
```
pip install python-telegram-bot==13.4.1
```
4. Add your Telegram Bot Token that you've recived from the BotFather to the following lines of the _book_the_time_slot.py_ and _remivder_service.py_:
```
def main() -> None:
    updater = Updater('KEY', use_context=True)
```
```
bot = Bot(token='KEY')
```
5. Start the bot:
```
python3 book_the_time_slot.py remivder_service.py
```
6. Open Telegram, search for your bot's username and start a conversation.
Follow the instructions provided by the bot to book, cancel or view bookings.

## 🤝 Contact
If you have any questions or feedback, feel free to reach out
https://t.me/finchren
