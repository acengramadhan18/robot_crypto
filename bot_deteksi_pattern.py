import ccxt
import pandas as pd
import numpy as np
import time

# --- SETUP ---
exchange = ccxt.gateio()

def ambil_data_market():
    try:
        return exchange.fetch_tickers()
    except Exception as e:
        print(f"Gagal ambil data market: {e}")
        return {}

def deteksi_pola_spesifik(df):
    """Membedakan antara Pennant dan Cup"""
    if len(df) < 40: return None
    data = df['close'].tail(40).tolist()
    
    # 1. Check Pennant
    pole_start = data[0]
    pole_end = max(data[5:15])
    pole_height = (pole_end - pole_start) / pole_start * 100
    recent_range = (max(data[20:]) - min(data[20:])) / min(data[20:]) * 100
    if pole_height > 4.0 and recent_range < (pole_height * 0.5):
        return "PENNANT"

    # 2. Check Cup
    left, bottom, right = max(data[:10]), min(data[10:30]), max(data[30:38])
    if bottom < left * 0.97 and abs(left - right) / left < 0.02:
        if data[-1] < right: return "CUP"
            
    return None

def radar_quad_category():
    print(f"\n--- 🛰️ QUAD-CATEGORY RADAR ({time.strftime('%H:%M:%S')}) ---")
    
    tickers = ambil_data_market()
    
    # Filter: USDT, No Leverage, Vol > 2M (Lebih Solid)
    semua_koin = [
        s for s in tickers.keys() 
        if '/USDT' in s and '3L' not in s and '3S' not in s 
        and tickers[s]['quoteVolume'] is not None and tickers[s]['quoteVolume'] > 2000000
    ]
    
    print(f"Menyisir {len(semua_koin)} koin aktif...")
    found_count = 0

    for simbol in semua_koin:
        try:
            ticker = tickers[simbol]
            pnl_24h = ticker['percentage'] or 0
            vol_m = f"{ticker['quoteVolume']/1000000:.1f}M"
            
            # Ambil data OHLCV
            bars = exchange.fetch_ohlcv(simbol, timeframe='1h', limit=200)
            df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            
            # --- LOGIKA KLASIFIKASI ---
            
            # 1 & 2. Cek Pola Spesifik (Untuk yang Bullish > 10%)
            if pnl_24h > 10.0:
                pola = deteksi_pola_spesifik(df)
                if pola == "PENNANT":
                    print(f"🚩 [PENNANT] {simbol:12} | PnL: {pnl_24h:+.1f}% | Vol: {vol_m:5} | Status: Breakout Watch")
                elif pola == "CUP":
                    print(f"🏆 [CUP]     {simbol:12} | PnL: {pnl_24h:+.1f}% | Vol: {vol_m:5} | Status: Handle Forming")
                else:
                    # 3. Bullish Biasa
                    print(f"📈 [BULLISH] {simbol:12} | PnL: {pnl_24h:+.1f}% | Vol: {vol_m:5} | Status: Strong Momentum")
                found_count += 1

            # 4. Bearish (PnL Negatif & Di bawah EMA 200)
            elif pnl_24h < -5.0:
                ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
                if df['close'].iloc[-1] < ema200:
                    print(f"💀 [BEARISH] {simbol:12} | PnL: {pnl_24h:+.1f}% | Vol: {vol_m:5} | Status: Under EMA 200")
                    found_count += 1
            
            time.sleep(0.05)
            
        except:
            continue
    
    if found_count == 0:
        print("Selesai. Tidak ada koin yang masuk kategori ekstrem saat ini.")

if __name__ == "__main__":
    print("🚀 Pinus V15.1 Aktif: Categorized Market Radar")
    while True:
        radar_quad_category()
        print(f"\nScanning selesai. Menunggu 5 menit...")
        time.sleep(300)