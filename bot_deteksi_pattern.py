import ccxt
import pandas as pd
import numpy as np
import time

# --- SETUP ---
exchange = ccxt.gateio()

def ambil_data_market():
    """Mengambil semua data ticker untuk mendapatkan volume dan PnL harian"""
    try:
        return exchange.fetch_tickers()
    except Exception as e:
        print(f"Gagal ambil data market: {e}")
        return {}

def deteksi_pola_cepat(df):
    """Logika deteksi pola Tactical 15m (Mini Pennant & Cup)"""
    if len(df) < 40: return None
    data = df['close'].tail(40).tolist()
    
    # 1. Deteksi Mini Pennant
    pole_start = data[0]
    pole_end = max(data[5:15])
    pole_height = (pole_end - pole_start) / pole_start * 100
    recent_max, recent_min = max(data[20:]), min(data[20:])
    range_pct = (recent_max - recent_min) / recent_min * 100

    if pole_height > 4.0 and range_pct < (pole_height * 0.5):
        return "🚩 PENNANT"

    # 2. Deteksi Mini Cup
    left_side = max(data[:10])
    bottom = min(data[10:30])
    right_side = max(data[30:38])
    if bottom < left_side * 0.97 and abs(left_side - right_side) / left_side < 0.02:
        if data[-1] < right_side: return "🏆 CUP"
            
    return None

def radar_high_volume_bullish():
    print(f"\n--- 💎 HIGH-VOLUME BULLISH RADAR ({time.strftime('%H:%M:%S')}) ---")
    
    tickers = ambil_data_market()
    
    # Filter Ketat:
    # 1. Pasangan USDT & Bukan koin Leverage
    # 2. Volume > 5,000,000 USDT (5M)
    # 3. PnL 24 Jam > 10%
    semua_koin = [
        s for s in tickers.keys() 
        if '/USDT' in s 
        and '3L' not in s and '3S' not in s 
        and tickers[s]['quoteVolume'] is not None and tickers[s]['quoteVolume'] > 1000000 
        and tickers[s]['percentage'] is not None and tickers[s]['percentage'] > 10.0
    ]
    
    print(f"Menyaring {len(semua_koin)} koin elit (Vol > 5M & PnL > 10%)...")
    
    found_count = 0
    for simbol in semua_koin:
        try:
            ticker = tickers[simbol]
            pnl_24h = ticker['percentage']
            vol_24h = ticker['quoteVolume']
            
            # Ambil data OHLCV 15m
            bars = exchange.fetch_ohlcv(simbol, timeframe='15m', limit=45)
            df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            
            pola = deteksi_pola_cepat(df)
            
            if pola:
                current_price = df['close'].iloc[-1]
                vol_display = f"{vol_24h/1000000:.1f}M"
                
                print(f"✨ [MATCH] {simbol:12} | Price: {current_price:12.4f} | PnL: {pnl_24h:+.2f}% | Vol: {vol_display:6} | Pola: {pola}")
                found_count += 1
            
            time.sleep(0.05) 
            
        except:
            continue
    
    if found_count == 0:
        print("Selesai. Tidak ada koin elit yang memenuhi pola saat ini.")

if __name__ == "__main__":
    print("🚀 Radar Elit Aktif! (Volume > 5M & PnL > 10%)")
    while True:
        radar_high_volume_bullish()
        print(f"\nScanning selesai. Menunggu 5 menit...")
        time.sleep(300)