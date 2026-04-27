import ccxt
import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
import time

# 1. Konfigurasi API Gate.io
exchange = ccxt.gateio({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET_KEY',
    'enableRateLimit': True,
})

symbol = 'BTC/USDT'
timeframe = '5m'  # Data per jam

def fetch_data(symbol, timeframe):
    """Mengambil data historis harga closing"""
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df['close'].astype(float)

def forecast_price(series):
    """Forecasting harga periode berikutnya menggunakan model ARIMA"""
    try:
        # Model ARIMA (p,d,q) sederhana
        model = ARIMA(series, order=(5, 1, 0))
        model_fit = model.fit()
        forecast = model_fit.forecast(steps=1)
        return forecast.iloc[0]
    except:
        return None

def execute_trade():
    print(f"Memulai pemindaian untuk {symbol}...")
    
    # Ambil data terbaru
    prices = fetch_data(symbol, timeframe)
    current_price = prices.iloc[-1]
    
    # Prediksi harga jam berikutnya
    predicted_price = forecast_price(prices)
    
    if predicted_price:
        change_pct = ((predicted_price - current_price) / current_price) * 100
        print(f"Harga Sekarang: {current_price:.2f} | Prediksi: {predicted_price:.2f} ({change_pct:.2f}%)")

        # LOGIKA STRATEGI (Contoh Sederhana)
        # Jika prediksi naik lebih dari 0.5%, maka BELI
        if change_pct > 0.15:
            print("Sinyal: BELI (Menanam)")
            # order = exchange.create_market_buy_order(symbol, 0.001)
            
        # Jika prediksi turun lebih dari 0.15%, maka JUAL
        elif change_pct < -0.15:
            print("Sinyal: JUAL (Menebang)")
            # order = exchange.create_market_sell_order(symbol, 0.001)
        else:
            print("Sinyal: HOLD (Pantau)")
# Loop utama robot
while True:
    try:
        execute_trade()
    except Exception as e:
        print(f"Error: {e}")
    
    time.sleep(30) # Cek setiap 0.5menit