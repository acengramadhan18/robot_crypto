import ccxt
import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
import time

# --- KONFIGURASI OPERASI (RAHASIA) ---
exchange = ccxt.gateio({
    'apiKey': 'ISI_API_KEY_ANDA_DISINI',
    'secret': 'ISI_SECRET_KEY_ANDA_DISINI',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'} 
})

# --- PARAMETER STRATEGI ---
SYMBOL = 'BTC/USDT'
TIMEFRAME = '1h'          # Menggunakan 1 jam agar lebih stabil
USDT_TO_SPEND = 10.0      # Modal per transaksi
THRESHOLD = 0.5           # Sinyal ARIMA (%)
CHECK_INTERVAL = 300      # Cek pasar setiap 5 menit (300 detik)

# --- PENGAMAN PROFIT & RUGI ---
TAKE_PROFIT = 1.5         # Jual otomatis jika untung 1.5%
STOP_LOSS = 1.0           # Jual otomatis jika rugi 1.0%
MAX_TRANSAKSI = 2

# --- STATE MANAGEMENT ---
jumlah_posisi_saat_ini = 0
harga_beli_rata_rata = 0.0

def ambil_data():
    try:
        bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=150)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        return df['close'].astype(float)
    except Exception as e:
        print(f"Gagal menarik data: {e}")
        return None

def eksekusi_tanam_tebang(side, amount_btc, price):
    global jumlah_posisi_saat_ini, harga_beli_rata_rata
    try:
        if side == 'buy':
            print(f"\n[!] EKSEKUSI BELI: {amount_btc:.6f} BTC di harga {price}")
            order = exchange.create_market_buy_order(SYMBOL, amount_btc)
            # Update harga rata-rata beli
            total_cost = (harga_beli_rata_rata * jumlah_posisi_saat_ini) + price
            jumlah_posisi_saat_ini += 1
            harga_beli_rata_rata = total_cost / jumlah_posisi_saat_ini
            print(f"Berhasil Beli! Harga rata-rata sekarang: {harga_beli_rata_rata:.2f}")
            
        elif side == 'sell':
            print(f"\n[!] EKSEKUSI JUAL: Menjual 1 posisi BTC di harga {price}")
            order = exchange.create_market_sell_order(SYMBOL, amount_btc)
            jumlah_posisi_saat_ini -= 1
            if jumlah_posisi_saat_ini == 0: harga_beli_rata_rata = 0
            print(f"Berhasil Jual! Sisa posisi: {jumlah_posisi_saat_ini}")
        
    except Exception as e:
        print(f"Gagal Transaksi: {e}")

def running_robot():
    global jumlah_posisi_saat_ini, harga_beli_rata_rata
    print(f"\n--- SCANNING ({time.strftime('%H:%M:%S')}) ---")
    
    prices = ambil_data()
    if prices is None: return

    try:
        current_price = prices.iloc[-1]
        model = ARIMA(prices, order=(2,1,0))
        model_fit = model.fit()
        forecast = model_fit.forecast(steps=1).iloc[0]
        
        diff_pct = ((forecast - current_price) / current_price) * 100
        amount_btc = round(USDT_TO_SPEND / current_price, 6)

        # Hitung profit/loss saat ini jika punya posisi
        pnl = 0.0
        if jumlah_posisi_saat_ini > 0:
            pnl = ((current_price - harga_beli_rata_rata) / harga_beli_rata_rata) * 100

        print(f"Harga BTC : {current_price:.2f}")
        print(f"Prediksi  : {forecast:.2f} ({diff_pct:+.4f}%)")
        print(f"Posisi    : {jumlah_posisi_saat_ini}/{MAX_TRANSAKSI} | Floating PNL: {pnl:+.2f}%")

        # --- LOGIKA EKSEKUSI ---

        # 1. STOP LOSS (Paling Utama)
        if jumlah_posisi_saat_ini > 0 and pnl <= -STOP_LOSS:
            print(">>> EMERGENCY: Stop Loss terkena! Menyelamatkan modal...")
            eksekusi_tanam_tebang('sell', amount_btc, current_price)

        # 2. TAKE PROFIT
        elif jumlah_posisi_saat_ini > 0 and pnl >= TAKE_PROFIT:
            print(">>> PROFIT: Target tercapai! Mengambil keuntungan...")
            eksekusi_tanam_tebang('sell', amount_btc, current_price)

        # 3. BELI (Berdasarkan ARIMA)
        elif diff_pct > THRESHOLD and jumlah_posisi_saat_ini < MAX_TRANSAKSI:
            eksekusi_tanam_tebang('buy', amount_btc, current_price)
        
        # 4. JUAL (Berdasarkan ARIMA)
        elif diff_pct < -THRESHOLD and jumlah_posisi_saat_ini > 0:
            eksekusi_tanam_tebang('sell', amount_btc, current_price)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print(f"=== ROBOT PINUS V4 FINAL AKTIF ===")
    while True:
        running_robot()
        time.sleep(CHECK_INTERVAL)