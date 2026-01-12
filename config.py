import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHANNEL_ID = int(os.getenv('ADMIN_CHANNEL_ID', '0'))

# Основной рацион (14 дней, 1200-2100 ккал)
PAYMENT_AMOUNT = os.getenv('PAYMENT_AMOUNT', '3000')

# FMD Протокол (5 дней, диета имитирующая голодание)
FMD_PAYMENT_AMOUNT = os.getenv('FMD_PAYMENT_AMOUNT', '1190')

# Комплект (Рационы + FMD со скидкой)
BUNDLE_PAYMENT_AMOUNT = os.getenv('BUNDLE_PAYMENT_AMOUNT', '2990')

PAYMENT_DETAILS = os.getenv(
    'PAYMENT_DETAILS', 'Номер карты: 1234 5678 9012 3456\nПолучатель: Иванова Светлана')

# Список username администраторов (без @)
ADMIN_USERNAMES = ['popdevp', 'Vedu_k_money', 'elsessertrener']
