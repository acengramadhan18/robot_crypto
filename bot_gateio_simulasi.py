import ccxt
import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
import time
import warnings
from statsmodels.tools.sm_exceptions import ConvergenceWarning

# --- SETUP ---
warnings.simplefilter('ignore', ConvergenceWarning)
warnings.filterwarnings("ignore")

# MODE SIMULASI
IS_SIMULATION = True 
exchange = ccxt.gateio()

# --- PARAMETER SCANNER ---
WATCHLIST = ['HYPE/USDT', 'BTC/USDT', 'ETH/USDT', 'FARTCOIN/USDT', 'ORCA/USDT', 'FLOKI/USDT', 'SHIB/USDT', 'DOGE/USDT', 'ADA/USDT', 'SOL/USDT']
USDT_PER_COIN = 30.0
MAX_SLOT = 3 
CHECK_INTERVAL = 5

# --- STRATEGI ---
THRESHOLD_ARIMA = 0.01
TAKE_PROFIT = 0.50
STOP_LOSS = 0.50

# --- STATE ---
dompet_simulasi = {} 
total_profit_akumulasi = 0.0

def ambil_data(simbol):
    try:
        bars = exchange.fetch_ohlcv(simbol, timeframe='1m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df['close'] = df['close'].astype(float)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        return df
    except:
        return None

def analisa_teknikal(df):
    ema = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
    return rsi, ema

def deteksi_pola_candle(df):
    c1 = df.iloc[-2] # Candle menit lalu
    c2 = df.iloc[-1] # Candle menit ini
    
    body = abs(c2['close'] - c2['open'])
    if body == 0: body = 0.000001
    
    lower_shadow = min(c2['open'], c2['close']) - c2['low']
    upper_shadow = c2['high'] - max(c2['open'], c2['close'])
    
    # Pola Hammer (Indikasi pantulan bawah)
    is_hammer = lower_shadow > (1.5 * body) and upper_shadow < (0.5 * body)
    
    # Pola Bullish Engulfing (Hijau memakan Merah)
    is_engulfing = (c2['close'] > c2['open'] and c1['close'] < c1['open'] and 
                    c2['close'] > c1['open'] and c2['open'] < c1['close'])
    
    if is_hammer: return "HAMMER"
    if is_engulfing: return "ENGULFING"
    return None

def eksekusi_simulasi(side, simbol, price, alasan):
    global total_profit_akumulasi
    print(f"\n>>> [ SIMULASI {side.upper()} ] {simbol} --- {alasan}")
    
    if side == 'buy':
        dompet_simulasi[simbol] = {
            'harga_beli': price,
            'waktu': time.strftime('%H:%M:%S')
        }
        print(f"🛍️ Beli {simbol} di harga {price:.4f}")
        
    elif side == 'sell':
        harga_beli = dompet_simulasi[simbol]['harga_beli']
        profit_pct = ((price - harga_beli) / harga_beli) * 100
        profit_usdt = (profit_pct / 100) * USDT_PER_COIN
        total_profit_akumulasi += profit_usdt
        
        print(f"💰 Jual {simbol} di harga {price:.4f} | Hasil: {profit_pct:+.2f}%")
        del dompet_simulasi[simbol]
    
    print(f"Slot: {len(dompet_simulasi)}/{MAX_SLOT} | Total Profit: {total_profit_akumulasi:+.4f} USDT")
    print("------------------------------------------")

def patroli_pasar():
    print(f"\n--- SCANNER PATROL ({time.strftime('%H:%M:%S')}) ---")
    
    for simbol in WATCHLIST:
        df = ambil_data(simbol)
        if df is None: continue
        
        current_price = df['close'].iloc[-1]
        price_prev = df['close'].iloc[-2]
        rsi, ema = analisa_teknikal(df)
        pola = deteksi_pola_candle(df)
        
        # 1. LOGIKA JUAL
        if simbol in dompet_simulasi:
            harga_beli = dompet_simulasi[simbol]['harga_beli']
            pnl = ((current_price - harga_beli) / harga_beli) * 100
            
            if pnl >= TAKE_PROFIT or pnl <= -STOP_LOSS:
                alasan = "TAKE PROFIT" if pnl >= TAKE_PROFIT else "STOP LOSS"
                eksekusi_simulasi('sell', simbol, current_price, alasan)
            else:
                print(f"Checking {simbol}: Floating {pnl:+.2f}% | RSI: {rsi:.2f}")

        # 2. LOGIKA BELI
        elif len(dompet_simulasi) < MAX_SLOT:
            try:
                model = ARIMA(df['close'], order=(2,1,0))
                forecast = model.fit().forecast(steps=1).iloc[0]
                diff_pct = ((forecast - current_price) / current_price) * 100
            except:
                diff_pct = 0
            
            # GABUNGAN SYARAT:
            # Wajib: RSI Murah + Pantulan (Price > Prev) + Di atas EMA
            # Pendorong: ARIMA Positif ATAU Ada Pola Candle
            syarat_wajib = (rsi < 35 and current_price > price_prev and current_price > ema)
            syarat_pendorong = (diff_pct > THRESHOLD_ARIMA or pola is not None)

            if syarat_wajib and syarat_pendorong:
                alasan = f"REBOUND {pola if pola else 'PRICE ACTION'}"
                eksekusi_simulasi('buy', simbol, current_price, alasan)
            else:
                status = "Pucuk" if rsi > 70 else "Wait"
                print(f"Scanning {simbol}: RSI {rsi:.2f} ({status})")

    print(f">> Status Slot: {len(dompet_simulasi)}/{MAX_SLOT} | Total Profit Akumulasi: {total_profit_akumulasi:+.4f} USDT")

if __name__ == "__main__":
    print(f"=== PINUS SCANNER V9 AKTIF (SIMULASI) ===")
    print(f"Monitoring: {WATCHLIST}")
    while True:
        patroli_pasar()
        time.sleep(CHECK_INTERVAL)