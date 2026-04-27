import ccxt
import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
import time

# --- MODE SIMULASI AKTIF ---
# Kita tidak butuh API Key asli untuk simulasi
exchange = ccxt.gateio() 

# --- PARAMETER STRATEGI ---
SYMBOL = 'ORCA/USDT'
TIMEFRAME = '1h'
USDT_TO_SPEND = 10.0      # Modal simulasi per transaksi
THRESHOLD = 0.01           # Sinyal ARIMA (%)
CHECK_INTERVAL = 30       # Untuk simulasi, kita percepat ceknya (30 detik)

# --- PENGAMAN PROFIT & RUGI ---
TAKE_PROFIT = 0.1         # Target simulasi untung 1.5%
STOP_LOSS = 0.1           # Target simulasi rugi 1.0%
MAX_TRANSAKSI = 3

# --- STATE MANAGEMENT (SIMULASI) ---
jumlah_posisi_saat_ini = 0
harga_beli_rata_rata = 0.0
total_profit_realized = 0.0 # Mencatat total cuan/rugi selama simulasi

def ambil_data():
    try:
        # Mengambil data asli untuk simulasi yang akurat
        bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=150)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        return df['close'].astype(float)
    except Exception as e:
        print(f"Gagal menarik data pasar: {e}")
        return None

def eksekusi_simulasi(side, amount_btc, price, alasan):
    global jumlah_posisi_saat_ini, harga_beli_rata_rata, total_profit_realized
    
    print(f"\n--- [ NOTIFIKASI SIMULASI: {side.upper()} ] ---")
    print(f"Alasan: {alasan}")
    
    if side == 'buy':
        total_cost = (harga_beli_rata_rata * jumlah_posisi_saat_ini) + price
        jumlah_posisi_saat_ini += 1
        harga_beli_rata_rata = total_cost / jumlah_posisi_saat_ini
        print(f"BERHASIL BELI: {amount_btc:.6f} BTC di harga {price:.2f}")
        
    elif side == 'sell':
        # Hitung profit/loss dari transaksi ini
        profit_persen = ((price - harga_beli_rata_rata) / harga_beli_rata_rata) * 100
        profit_usdt = (profit_persen / 100) * USDT_TO_SPEND
        total_profit_realized += profit_usdt
        
        print(f"BERHASIL JUAL: {amount_btc:.6f} BTC di harga {price:.2f}")
        print(f"Profit/Loss Transaksi Ini: {profit_persen:+.2f}% ({profit_usdt:+.4f} USDT)")
        
        jumlah_posisi_saat_ini -= 1
        if jumlah_posisi_saat_ini == 0: harga_beli_rata_rata = 0
    
    print(f"Total Posisi Aktif: {jumlah_posisi_saat_ini}")
    print(f"Akumulasi Profit Simulasi: {total_profit_realized:+.4f} USDT")
    print("------------------------------------------")

def running_robot():
    global jumlah_posisi_saat_ini, harga_beli_rata_rata
    print(f"\n--- SCANNING PASAR ({time.strftime('%H:%M:%S')}) ---")
    
    prices = ambil_data()
    if prices is None: return

    try:
        current_price = prices.iloc[-1]
        model = ARIMA(prices, order=(2,1,0))
        model_fit = model.fit()
        forecast = model_fit.forecast(steps=1).iloc[0]
        
        diff_pct = ((forecast - current_price) / current_price) * 100
        amount_btc = round(USDT_TO_SPEND / current_price, 6)

        pnl = 0.0
        if jumlah_posisi_saat_ini > 0:
            pnl = ((current_price - harga_beli_rata_rata) / harga_beli_rata_rata) * 100

        print(f"Harga BTC Saat Ini : {current_price:.2f}")
        print(f"Ramalan ARIMA      : {forecast:.2f} ({diff_pct:+.4f}%)")
        print(f"Status Posisi      : {jumlah_posisi_saat_ini}/{MAX_TRANSAKSI}")
        if jumlah_posisi_saat_ini > 0:
            print(f"Floating PNL       : {pnl:+.2f}%")

        # --- LOGIKA EKSEKUSI SIMULASI ---

        if jumlah_posisi_saat_ini > 0 and pnl <= -STOP_LOSS:
            eksekusi_simulasi('sell', amount_btc, current_price, "STOP LOSS")

        elif jumlah_posisi_saat_ini > 0 and pnl >= TAKE_PROFIT:
            eksekusi_simulasi('sell', amount_btc, current_price, "TAKE PROFIT")

        elif diff_pct > THRESHOLD and jumlah_posisi_saat_ini < MAX_TRANSAKSI:
            eksekusi_simulasi('buy', amount_btc, current_price, "SINYAL BELI ARIMA")
        
        elif diff_pct < -THRESHOLD and jumlah_posisi_saat_ini > 0:
            eksekusi_simulasi('sell', amount_btc, current_price, "SINYAL JUAL ARIMA")

    except Exception as e:
        print(f"Error Logika: {e}")

if __name__ == "__main__":
    print(f"=== ROBOT PINUS V4 (MODE SIMULASI) AKTIF ===")
    print(f"Mencoba strategi di {SYMBOL} tanpa risiko saldo.")
    while True:
        running_robot()
        time.sleep(CHECK_INTERVAL)