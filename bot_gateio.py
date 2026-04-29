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
    'apiKey': 'b190501effe8bfa0ac2cebff9dc4485a',    # Masukkan API Key Sub-Akun
    'secret': 'ea89e07f98fccd70d491aa608d0fbd74d16dece42e9594268583d3d99d0d473c', # Masukkan Secret Key Sub-Akun
    'enableRateLimit': True,
})

# --- PARAMETER SCANNER (Sesuai Request Anda) ---
WATCHLIST = ['HYPE/USDT', 'BTC/USDT', 'ETH/USDT', 'FARTCOIN/USDT', 'ORCA/USDT', 'FLOKI/USDT', 'SHIB/USDT', 'DOGE/USDT', 'TAO/USDT']
USDT_PER_COIN = 50.0
MAX_SLOT = 3 
CHECK_INTERVAL = 5

# --- STRATEGI (Sesuai Request Anda) ---
THRESHOLD_ARIMA = 0.01
TAKE_PROFIT = 0.50
STOP_LOSS = 0.50

# --- STATE MANAGEMENT ---
posisi_riil = {} 
total_profit_realized = 0.0

def ambil_data(simbol):
    try:
        bars = exchange.fetch_ohlcv(simbol, timeframe='1m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df['close'] = df['close'].astype(float)
        return df
    except:
        return None

def analisa_teknikal(df):
    # EMA 20
    ema = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
    # RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
    return rsi, ema

def eksekusi_riil(side, simbol, price, alasan):
    global total_profit_realized
    print(f"\n>>> [ EKSEKUSI RIIL {side.upper()} ] {simbol} --- {alasan}")
    
    try:
        if side == 'buy':
            params = {'createMarketBuyOrderRequiresPrice': False}
            order = exchange.create_order(
                symbol=simbol, 
                type='market', 
                side='buy', 
                amount=USDT_PER_COIN, 
                params=params
            )
            exec_price = order.get('price', price) if order.get('price') else price
            posisi_riil[simbol] = exec_price
            print(f"✅ BERHASIL BELI: {simbol} di harga {exec_price}")
            return True

        elif side == 'sell':
            balance = exchange.fetch_balance()
            coin_name = simbol.split('/')[0]
            amount_to_sell = balance.get(coin_name, {}).get('free', 0)
            
            if amount_to_sell > 0:
                order = exchange.create_order(
                    symbol=simbol, 
                    type='market', 
                    side='sell', 
                    amount=amount_to_sell
                )
                exec_price_sell = order.get('price', price) if order.get('price') else price
                harga_beli = posisi_riil[simbol]
                profit_pct = ((exec_price_sell - harga_beli) / harga_beli) * 100
                profit_usdt = (profit_pct / 100) * USDT_PER_COIN
                total_profit_realized += profit_usdt
                
                print(f"✅ BERHASIL JUAL: {simbol} | Hasil: {profit_pct:+.2f}%")
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
        rsi, ema = analisa_teknikal(df)
        
        # 1. CEK JUAL
        if simbol in posisi_riil:
            harga_beli = posisi_riil[simbol]
            pnl = ((current_price - harga_beli) / harga_beli) * 100
            
            if pnl >= TAKE_PROFIT or pnl <= -STOP_LOSS:
                alasan = "TAKE PROFIT" if pnl >= TAKE_PROFIT else "STOP LOSS"
                eksekusi_riil('sell', simbol, current_price, alasan)
            else:
                print(f"Checking {simbol}: Floating {pnl:+.2f}% | RSI: {rsi:.2f}")

        # 2. CEK BELI
        elif len(posisi_riil) < MAX_SLOT:
            try:
                model = ARIMA(df['close'], order=(2,1,0))
                forecast = model.fit().forecast(steps=1).iloc[0]
                diff_pct = ((forecast - current_price) / current_price) * 100
            except:
                diff_pct = 0
            
            price_prev = df['close'].iloc[-2]

            # Syarat: RSI < 35 + Pantulan (Price > Prev) + Di atas EMA + ARIMA Positif
            if rsi < 35 and current_price > price_prev and diff_pct > THRESHOLD_ARIMA:
                eksekusi_riil('buy', simbol, current_price, "KONFIRMASI PEMBALIKAN ARAH")
            else:
                status = "Pucuk" if rsi > 70 else "Wait"
                print(f"Scanning {simbol}: RSI {rsi:.2f} ({status})")

    print(f">> Status Slot: {len(posisi_riil)}/{MAX_SLOT} | Total Profit Realized: {total_profit_realized:+.4f} USDT")

if __name__ == "__main__":
    print(f"🚀 PINUS RIIL V8 DIMULAI (Watchlist: {len(WATCHLIST)} koin)")
    while True:
        patroli_pasar()
        time.sleep(CHECK_INTERVAL)