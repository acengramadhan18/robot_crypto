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

# --- KONFIGURASI API ---
exchange = ccxt.gateio({
    'apiKey': 'b190501effe8bfa0ac2cebff9dc4485a',    
    'secret': 'ea89e07f98fccd70d491aa608d0fbd74d16dece42e9594268583d3d99d0d473c', 
    'enableRateLimit': True,
})

# --- PARAMETER SCANNER ---
WATCHLIST = ['HYPE/USDT', 'BTC/USDT', 'ETH/USDT', 'FARTCOIN/USDT', 'ORCA/USDT', 'FLOKI/USDT', 'SHIB/USDT', 'DOGE/USDT', 'ADA/USDT', 'SOL/USDT', 'PENGU/USDT']
USDT_PER_COIN = 30.0
MAX_SLOT = 3 
CHECK_INTERVAL = 5

# --- STRATEGI V10 (Napas Lebih Panjang) ---
THRESHOLD_ARIMA = 0.01
TAKE_PROFIT = 0.70    # Target profit dinaikkan dikit biar cover fee
STOP_LOSS = 1.00      # Stop loss diperlebar agar tidak kena gocek (V10)

# --- STATE ---
posisi_riil = {} 
total_profit_realized = 0.0

def ambil_data(simbol):
    try:
        bars = exchange.fetch_ohlcv(simbol, timeframe='1m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
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
    """Mendeteksi pola pembalikan arah Bullish"""
    c1 = df.iloc[-2]
    c2 = df.iloc[-1]
    body = abs(c2['close'] - c2['open'])
    if body == 0: body = 0.000001
    lower_shadow = min(c2['open'], c2['close']) - c2['low']
    upper_shadow = c2['high'] - max(c2['open'], c2['close'])
    
    is_hammer = lower_shadow > (1.5 * body) and upper_shadow < (0.5 * body)
    is_engulfing = (c2['close'] > c2['open'] and c1['close'] < c1['open'] and 
                    c2['close'] > c1['open'] and c2['open'] < c1['close'])
    
    if is_hammer: return "HAMMER"
    if is_engulfing: return "ENGULFING"
    return None

def eksekusi_riil(side, simbol, price, alasan):
    global total_profit_realized
    print(f"\n>>> [ EKSEKUSI RIIL {side.upper()} ] {simbol} --- {alasan}")
    try:
        if side == 'buy':
            params = {'createMarketBuyOrderRequiresPrice': False}
            order = exchange.create_order(symbol=simbol, type='market', side='buy', amount=USDT_PER_COIN, params=params)
            exec_price = order.get('price', price) if order.get('price') else price
            posisi_riil[simbol] = exec_price
            print(f"✅ BERHASIL BELI: {simbol} @ {exec_price}")
            return True
        elif side == 'sell':
            balance = exchange.fetch_balance()
            coin_name = simbol.split('/')[0]
            amount_to_sell = balance.get(coin_name, {}).get('free', 0)
            if amount_to_sell > 0:
                order = exchange.create_order(symbol=simbol, type='market', side='sell', amount=amount_to_sell)
                exec_price_sell = order.get('price', price) if order.get('price') else price
                harga_beli = posisi_riil[simbol]
                profit_pct = ((exec_price_sell - harga_beli) / harga_beli) * 100
                total_profit_realized += (profit_pct / 100) * USDT_PER_COIN
                print(f"✅ BERHASIL JUAL: {simbol} | Profit: {profit_pct:+.2f}%")
                del posisi_riil[simbol]
                return True
    except Exception as e:
        print(f"❌ GAGAL EKSEKUSI: {e}")
    return False

def patroli_pasar():
    print(f"\n--- SCANNER PATROL RIIL ({time.strftime('%H:%M:%S')}) ---")
    for simbol in WATCHLIST:
        df = ambil_data(simbol)
        if df is None: continue
        
        current_price = df['close'].iloc[-1]
        price_prev = df['close'].iloc[-2]
        rsi, ema = analisa_teknikal(df)
        pola = deteksi_pola_candle(df)
        
        # 1. CEK JUAL
        if simbol in posisi_riil:
            harga_beli = posisi_riil[simbol]
            pnl = ((current_price - harga_beli) / harga_beli) * 100
            if pnl >= TAKE_PROFIT or pnl <= -STOP_LOSS:
                alasan = "TAKE PROFIT" if pnl >= TAKE_PROFIT else "STOP LOSS"
                eksekusi_riil('sell', simbol, current_price, alasan)
            else:
                print(f"Checking {simbol}: Floating {pnl:+.2f}% | RSI: {rsi:.2f}")

        # 2. CEK BELI (LOGIKA V10: TANPA WAJIB EMA)
        elif len(posisi_riil) < MAX_SLOT:
            # Mode Serok Bawah (RSI < 30 & Harga Mantul)
            if rsi < 30 and current_price > price_prev:
                eksekusi_riil('buy', simbol, current_price, f"SEROK BAWAH (RSI {rsi:.2f})")
            # Mode Konfirmasi Pola (RSI 30-40 & Pola Bullish)
            elif 30 <= rsi < 40 and pola is not None:
                eksekusi_riil('buy', simbol, current_price, f"CANDLE: {pola}")
            else:
                status = "Pucuk" if rsi > 70 else "Wait"
                print(f"Scanning {simbol}: RSI {rsi:.2f} ({status})")

    print(f">> Slot: {len(posisi_riil)}/{MAX_SLOT} | Total Profit: {total_profit_realized:+.4f} USDT")

if __name__ == "__main__":
    print(f"🚀 PINUS RIIL V10 AKTIF (Anti-Boncos Edition)")
    while True:
        try:
            patroli_pasar()
        except Exception as e:
            print(f"⚠️ Sistem Error: {e}")
        time.sleep(CHECK_INTERVAL)