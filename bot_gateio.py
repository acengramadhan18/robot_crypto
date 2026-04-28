import ccxt
import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
import time
import warnings
from statsmodels.tools.sm_exceptions import ConvergenceWarning

# --- PENGATURAN PRIVASI & WARNING ---
warnings.simplefilter('ignore', ConvergenceWarning)
warnings.filterwarnings("ignore")

# --- MODE OPERASI ---
# Set ke False jika ingin menggunakan API Key Sub-Account untuk trading riil
IS_SIMULATION = False 

# --- KONEKSI BURSA ---
if IS_SIMULATION:
    exchange = ccxt.gateio() # Tanpa API Key untuk simulasi
else:
    exchange = ccxt.gateio({
        'apiKey': 'b190501effe8bfa0ac2cebff9dc4485a',
        'secret': 'ea89e07f98fccd70d491aa608d0fbd74d16dece42e9594268583d3d99d0d473c',
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })

# --- PARAMETER STRATEGI (BISA DIUBAH) ---
SYMBOL = 'HYPE/USDT'  # Nama koin dinamis
TIMEFRAME = '1m'          # Scalping 5 menit
USDT_TO_SPEND = 5.0      # Modal per transaksi (USDT)
THRESHOLD_ARIMA = -0.01    # Sinyal ARIMA (%)
CHECK_INTERVAL = 5       # Cek setiap 30 detik

# --- PENGAMAN (RISK MANAGEMENT) ---
TAKE_PROFIT = 0.03        # Target untung 0.15%
STOP_LOSS = 0.40          # Batas rugi 0.10%
MAX_TRANSAKSI = 2         # Maksimal cicilan posisi

# --- STATE MANAGEMENT ---
jumlah_posisi_saat_ini = 0
harga_beli_rata_rata = 0.0
total_profit_realized = 0.0

def ambil_data():
    try:
        bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=200)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df['close'] = df['close'].astype(float)
        return df
    except Exception as e:
        print(f"Gagal menarik data pasar: {e}")
        return None

def analisa_teknikal(df):
    """Mata Tambahan: RSI dan EMA (Manual Tanpa pandas_ta)"""
    # 1. Hitung EMA 20
    ema_now = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
    
    # 2. Hitung RSI 14 secara manual
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    
    rs = gain / loss
    rsi_now = 100 - (100 / (1 + rs.iloc[-1]))
    
    return rsi_now, ema_now

def eksekusi_riil(side, price, alasan):
    global jumlah_posisi_saat_ini, harga_beli_rata_rata, total_profit_realized
    
    print(f"\n>>> [ EKSEKUSI RIIL {side.upper()} ] --- Alasan: {alasan}")
    
    try:
        if side == 'buy':
            # PENTING: Untuk Gate.io Market Buy, kita masukkan nominal USDT di kolom 'amount'
            # Kita tambahkan params khusus agar Gate.io tidak minta harga lagi
            params = {'createMarketBuyOrderRequiresPrice': False}
            
            # Kita kirim order dengan nominal USDT yang ditentukan di USDT_TO_SPEND
            order = exchange.create_order(
                symbol=SYMBOL, 
                type='market', 
                side='buy', 
                amount=USDT_TO_SPEND, 
                price=None, 
                params=params
            )
            
            print(f"✅ BERHASIL BELI RIIL: ID {order['id']}")
            
            # Update Logika Internal (Gunakan harga eksekusi dari bursa jika ada, atau harga terakhir)
            exec_price = order.get('price', price) if order.get('price') else price
            total_cost = (harga_beli_rata_rata * jumlah_posisi_saat_ini) + exec_price
            jumlah_posisi_saat_ini += 1
            harga_beli_rata_rata = total_cost / jumlah_posisi_saat_ini
            
        elif side == 'sell':
            # Ambil saldo koin yang tersedia di sub-akun untuk dijual semua
            balance = exchange.fetch_balance()
            coin_name = SYMBOL.split('/')[0] 
            amount_to_sell = balance.get(coin_name, {}).get('free', 0)
            
            if amount_to_sell > 0:
                # Market Sell menggunakan jumlah koin
                order = exchange.create_order(
                    symbol=SYMBOL, 
                    type='market', 
                    side='sell', 
                    amount=amount_to_sell
                )
                print(f"✅ BERHASIL JUAL RIIL: ID {order['id']}")
                
                # Hitung Profit berdasarkan harga eksekusi
                exec_price_sell = order.get('price', price) if order.get('price') else price
                profit_persen = ((exec_price_sell - harga_beli_rata_rata) / harga_beli_rata_rata) * 100
                profit_usdt = (profit_persen / 100) * (USDT_TO_SPEND * jumlah_posisi_saat_ini)
                total_profit_realized += profit_usdt
                
                jumlah_posisi_saat_ini = 0 
                harga_beli_rata_rata = 0
            else:
                print("❌ GAGAL JUAL: Saldo koin tidak cukup di Akun Spot.")

    except Exception as e:
        print(f"❌ GAGAL EKSEKUSI RIIL: {e}")

    print(f"Posisi {SYMBOL}: {jumlah_posisi_saat_ini}/{MAX_TRANSAKSI}")
    print(f"Total Profit Akumulasi: {total_profit_realized:+.4f} USDT")
    print("------------------------------------------")

def running_robot():
    global jumlah_posisi_saat_ini, harga_beli_rata_rata, total_profit_realized
    print(f"\n--- SCANNING {SYMBOL} ({time.strftime('%H:%M:%S')}) ---")
    
    df = ambil_data()
    if df is None: return

    try:
        current_price = df['close'].iloc[-1]
        rsi_sekarang, ema_sekarang = analisa_teknikal(df)
        
        # Ramalan ARIMA
        model = ARIMA(df['close'], order=(2,1,0))
        model_fit = model.fit()
        forecast = model_fit.forecast(steps=1).iloc[0]
        
        diff_pct = ((forecast - current_price) / current_price) * 100
        amount_koin = round(USDT_TO_SPEND / current_price, 6)

        # Cek Profit/Loss berjalan (Floating PNL)
        pnl = 0.0
        if jumlah_posisi_saat_ini > 0:
            pnl = ((current_price - harga_beli_rata_rata) / harga_beli_rata_rata) * 100

        # --- OUTPUT TERMINAL DINAMIS ---
        print(f"Harga Sekarang  : {current_price:.4f}")
        print(f"Ramalan ARIMA   : {forecast:.4f} ({diff_pct:+.4f}%)")
        print(f"Indikator RSI   : {rsi_sekarang:.2f} | EMA20: {ema_sekarang:.4f}")
        
        # Penambahan status posisi & akumulasi di setiap scanning
        print(f"Posisi {SYMBOL} : {jumlah_posisi_saat_ini}/{MAX_TRANSAKSI}")
        print(f"Total Profit Akum: {total_profit_realized:+.4f} USDT")
        
        if jumlah_posisi_saat_ini > 0:
            print(f"Floating PNL    : {pnl:+.2f}%")

        # --- LOGIKA EKSEKUSI (TP/SL/BUY/SELL) ---
        # 1. CEK EXIT PRIORITAS (TP / SL)
        if jumlah_posisi_saat_ini > 0 and (pnl <= -STOP_LOSS or pnl >= TAKE_PROFIT):
            alasan_out = "STOP LOSS" if pnl <= -STOP_LOSS else "TAKE PROFIT"
            eksekusi_riil('sell', current_price, alasan_out)

        # 2. CEK ENTRY (BELI)
        elif diff_pct > THRESHOLD_ARIMA and jumlah_posisi_saat_ini < MAX_TRANSAKSI:
            if (rsi_sekarang > 35 and rsi_sekarang < 70) and (current_price > (ema_sekarang * 0.997)):
                eksekusi_riil('buy', current_price, "KONFLUENSI BULLISH / REBOUND")
            else:
                if rsi_sekarang <= 35:
                    print(f"--- Pending: Menunggu Pantulan (RSI {rsi_sekarang:.2f}) ---")
                elif rsi_sekarang >= 70:
                    print(f"--- Pending: Harga Pucuk (RSI {rsi_sekarang:.2f}) ---")
                elif current_price <= (ema_sekarang * 0.997):
                    print("--- Pending: Tren Masih Turun (Bawah EMA) ---")
        
        # 3. CEK EXIT DARURAT (HANYA JIKA SUDAH PUCUK BANGET & PROFIT)
        # Kita hapus 'diff_pct < -THRESHOLD_ARIMA' agar tidak panik jual saat minus
        elif rsi_sekarang > 85 and jumlah_posisi_saat_ini > 0 and pnl > 0:
            eksekusi_riil('sell', current_price, "EXTREME OVERBOUGHT (SECURE PROFIT)")

    except Exception as e:
        print(f"Error Logika: {e}")

if __name__ == "__main__":
    status_mode = "SIMULASI" if IS_SIMULATION else "RIIL (SUB-ACCOUNT)"
    print(f"=== ROBOT PINUS V5 DIMULAI ({status_mode}) ===")
    print(f"Target Operasi: {SYMBOL}")
    
    while True:
        running_robot()
        time.sleep(CHECK_INTERVAL)