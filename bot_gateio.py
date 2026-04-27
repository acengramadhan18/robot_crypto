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

# Parameter Kebun
SYMBOL = 'BTC/USDT'  # Sektor Kayu Jati
TIMEFRAME = '5m'     # Siklus 5 Menit
AMOUNT_TO_BUY = 0.0001 # Jumlah beli (Sesuaikan dengan saldo & min order Gate.io)
THRESHOLD = 0.15     # % Prediksi untuk eksekusi (Sensitivitas Scalping)

def ambil_data():
    """Menarik data pertumbuhan dari pasar"""
    bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=150)
    df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
    return df['close'].astype(float)

def eksekusi_tanam_tebang(side, price):
    """Fungsi untuk transaksi riil"""
    try:
        if side == 'buy':
            print(f">>> INSTRUKSI: Kondisi subur. Sedang MENANAM {AMOUNT_TO_BUY} {SYMBOL}")
            order = exchange.create_market_buy_order(SYMBOL, AMOUNT_TO_BUY)
        elif side == 'sell':
            print(f">>> INSTRUKSI: Hama terdeteksi. Sedang MENEBANG {AMOUNT_TO_BUY} {SYMBOL}")
            order = exchange.create_market_sell_order(SYMBOL, AMOUNT_TO_BUY)
        
        print(f"Laporan Berhasil: {order['id']}")
    except Exception as e:
        print(f"Gagal beroperasi: {e}")

def running_robot():
    print(f"\n--- SIKLUS PINUS AKTIF ({time.strftime('%H:%M:%S')}) ---")
    
    try:
        # 1. Ambil data harga terbaru
        prices = ambil_data()
        current_price = prices.iloc[-1]

        # 2. Forecasting (Prediksi Cuaca Harga)
        # Menggunakan ARIMA (2,1,0) agar lebih responsif terhadap perubahan cepat
        model = ARIMA(prices, order=(2,1,0))
        model_fit = model.fit()
        forecast = model_fit.forecast(steps=1).iloc[0]

        # 3. Hitung Selisih (Gunakan presisi 4 desimal agar tidak 0.00%)
        diff_pct = ((forecast - current_price) / current_price) * 100
        
        print(f"Kayu Jati Saat Ini: {current_price:.2f}")
        print(f"Prediksi 5 Menit Depan: {forecast:.2f} ({diff_pct:+.4f}%)")

        # 4. Logika Keputusan Otomatis
        if diff_pct > THRESHOLD:
            eksekusi_tanam_tebang('buy', current_price)
        elif diff_pct < -THRESHOLD:
            eksekusi_tanam_tebang('sell', current_price)
        else:
            print("Status: Pertumbuhan stabil. Pantau lahan...")

    except Exception as e:
        print(f"Gangguan sinyal hutan: {e}")

# --- JALANKAN PROGRAM ---
if __name__ == "__main__":
    print(f"Memulai Operasi Scalping Otomatis di {SYMBOL}...")
    while True:
        running_robot()
        # Untuk scalping 5m, kita cek setiap 30 detik agar tidak ketinggalan momentum
        time.sleep(30)