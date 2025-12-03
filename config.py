import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHANNEL_ID = int(os.getenv('ADMIN_CHANNEL_ID', '0'))
PAYMENT_AMOUNT = os.getenv('PAYMENT_AMOUNT', '500')
PAYMENT_DETAILS = os.getenv(
    'PAYMENT_DETAILS', 'Номер карты: 1234 5678 9012 3456\nПолучатель: Иванова Светлана')

# Список username администраторов (без @)
ADMIN_USERNAMES = ['popdevp', 'Vedu_k_money', 'elsessertrener']
