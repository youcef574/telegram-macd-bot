import telebot
import ccxt
import pandas as pd
import numpy as np
import time

# ✅ Bot Settings
TOKEN = "7759691958:AAFj2QOC4OsoO1ffCjs1biwP3UMnYkYxQPk"  # Insert your bot token here
bot = telebot.TeleBot(TOKEN)

# ✅ Exchange Settings
exchange = ccxt.binance()

# ✅ Timeframe used in strategy
TIMEFRAME = "15m"

# ✅ Risk-reward ratio
RISK_REWARD_RATIO = 3

# ✅ Function to calculate EMA
def calculate_ema(prices, window):
    return prices.ewm(span=window, adjust=False).mean()

# ✅ Function to calculate MACD
def calculate_macd(prices, short_window=12, long_window=26, signal_window=9):
    short_ema = prices.ewm(span=short_window, adjust=False).mean()
    long_ema = prices.ewm(span=long_window, adjust=False).mean()
    macd = short_ema - long_ema
    signal = macd.ewm(span=signal_window, adjust=False).mean()
    return macd, signal

# ✅ Function to calculate RSI
def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ✅ Function to fetch market data
def get_market_data(symbol, timeframe=TIMEFRAME, limit=100):
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['close'] = df['close'].astype(float)
        df['ema_50'] = calculate_ema(df['close'], 50)
        df['ema_200'] = calculate_ema(df['close'], 200)
        df['rsi'] = calculate_rsi(df['close'])
        macd, signal = calculate_macd(df['close'])
        df['macd'] = macd
        df['signal'] = signal
        return df
    except Exception as e:
        print(f"⚠️ Error fetching data for {symbol} ({timeframe}): {e}")
        return None

# ✅ Function to check strategy conditions
def check_strategy(symbol):
    df = get_market_data(symbol)
    if df is not None and df.shape[0] > 2:
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        unmet_criteria = []

        if not (last_row['close'] > last_row['ema_50']):
            unmet_criteria.append("Price not above EMA 50")
        if not (last_row['ema_50'] > last_row['ema_200']):
            unmet_criteria.append("EMA 50 not above EMA 200")
        if not (last_row['close'] > prev_row['ema_50'] and prev_row['close'] < prev_row['ema_50']):
            unmet_criteria.append("No retest confirmation")
        if not (30 <= last_row['rsi'] <= 50):
            unmet_criteria.append("RSI not between 30 and 50")
        if not (prev_row['macd'] < prev_row['signal'] and last_row['macd'] > last_row['signal']):
            unmet_criteria.append("MACD did not cross above signal line")

        if not unmet_criteria:
            entry_price = last_row['close']
            stop_loss = prev_row['low']
            take_profit = entry_price + (entry_price - stop_loss) * RISK_REWARD_RATIO
            return True, entry_price, stop_loss, take_profit, None
        else:
            return False, None, None, None, unmet_criteria
    return False, None, None, None, None

# ✅ Function to get all active trading pairs against USDT on Binance
def get_all_symbols():
    try:
        markets = exchange.load_markets()
        symbols = [symbol for symbol in markets.keys() if symbol.endswith("/USDT")]
        return symbols
    except Exception as e:
        print(f"⚠️ Error fetching trading pairs: {e}")
        return []

# ✅ Monitoring function
def monitor():
    chat_id = "6411238713"  # Insert your chat ID here
    symbols = get_all_symbols()
    num_symbols = len(symbols)
    bot.send_message(chat_id, f"📊 The bot is monitoring {num_symbols} crypto pairs against USDT on {TIMEFRAME} timeframe...")
    
    while True:
        potential_symbols = []
        for symbol in symbols:
            try:
                signal, entry_price, stop_loss, take_profit, unmet_criteria = check_strategy(symbol)
                if signal:
                    message = (
                        f"🚨 URGENT: Buy Signal in {symbol} on {TIMEFRAME} timeframe!\n"
                        f"🔹 Entry Price: {entry_price:.4f} USDT\n"
                        f"🔸 Stop Loss: {stop_loss:.4f} USDT\n"
                        f"🟢 Take Profit: {take_profit:.4f} USDT"
                    )
                    bot.send_message(chat_id, message)
                else:
                    potential_symbols.append(f"{symbol} (Missing: {', '.join(unmet_criteria)})")
            except Exception as e:
                print(f"⚠️ Error in {symbol}: {e}")
        
        if potential_symbols:
            bot.send_message(chat_id, f"🔍 Cryptos close to meeting strategy criteria:\n" + "\n".join(potential_symbols[:5]))
        else:
            bot.send_message(chat_id, "🚫 No cryptocurrencies are currently close to meeting the strategy criteria.")
        
        time.sleep(60)  # Update every minute

# ✅ Run monitoring in background
import threading
@bot.message_handler(commands=['start'])
def start_message(message):
    chat_id = message.chat.id
    symbols = get_all_symbols()
    num_symbols = len(symbols)
    bot.send_message(chat_id, f"Hello! The bot is monitoring {num_symbols} crypto pairs against USDT on {TIMEFRAME} timeframe...")
    monitor()

t = threading.Thread(target=monitor)
t.start()
bot.polling()
