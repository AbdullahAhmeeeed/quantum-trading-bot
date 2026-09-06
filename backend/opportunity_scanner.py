"""
opportunity_scanner.py - Multi-Asset Momentum Scanner
Scans 14+ trading pairs. Returns ranked list by momentum score.
"""
import time
import threading
from typing import List, Dict, Optional
import random

TRADING_UNIVERSE = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT",
    "PAXG/USDT", "DOGE/USDT", "SHIB/USDT", "PEPE/USDT",
    "WIF/USDT", "BONK/USDT", "XRP/USDT", "ADA/USDT",
    "AVAX/USDT", "MATIC/USDT",
]

_opportunity_cache: Dict[str, dict] = {}
_cache_lock = threading.Lock()
_prev_prices: Dict[str, float] = {}

MEME_COINS = {"DOGE/USDT", "SHIB/USDT", "PEPE/USDT", "WIF/USDT", "BONK/USDT"}


def _score_opportunity(pair: str, price: float, prev_price: float, volume: float) -> dict:
    if prev_price <= 0 or price <= 0:
        return {"pair": pair, "score": 0, "signal": "HOLD", "price": price, "reason": "No data",
                "pct_change": 0.0, "volume": volume, "timestamp": int(time.time())}

    pct_change = ((price - prev_price) / prev_price) * 100.0
    momentum_score = min(abs(pct_change) * 20, 60)
    vol_bonus = min(volume / 100.0, 20)
    meme_bonus = 10 if pair in MEME_COINS else 0
    score = min(momentum_score + vol_bonus + meme_bonus, 100)

    if pct_change > 0.03:
        signal = "BUY"
        reason = f"Upward momentum +{pct_change:.3f}%"
    elif pct_change < -0.03:
        signal = "SELL"
        reason = f"Downward momentum {pct_change:.3f}%"
    else:
        signal = "HOLD"
        reason = "Low momentum - waiting"
        score = max(score - 30, 5)

    return {
        "pair": pair, "score": round(score, 1), "signal": signal,
        "price": round(price, 8), "pct_change": round(pct_change, 4),
        "volume": round(volume, 2), "reason": reason,
        "timestamp": int(time.time()),
    }


def scan_opportunities(live_prices: Dict[str, float], live_volumes: Dict[str, float] = None) -> List[dict]:
    global _prev_prices
    if live_volumes is None:
        live_volumes = {}

    opportunities = []
    for pair in TRADING_UNIVERSE:
        price = live_prices.get(pair, 0.0)
        if price <= 0:
            continue
        prev = _prev_prices.get(pair, price)
        vol = live_volumes.get(pair, random.uniform(20, 200))
        opp = _score_opportunity(pair, price, prev, vol)
        opportunities.append(opp)

    for pair, price in live_prices.items():
        if price > 0:
            _prev_prices[pair] = price

    opportunities.sort(key=lambda x: x["score"], reverse=True)

    with _cache_lock:
        for opp in opportunities:
            _opportunity_cache[opp["pair"]] = opp

    return opportunities


def get_best_opportunity(exclude_pairs: List[str] = None) -> Optional[dict]:
    exclude_pairs = exclude_pairs or []
    with _cache_lock:
        candidates = [
            opp for opp in _opportunity_cache.values()
            if opp["signal"] in ["BUY", "SELL"] and opp["pair"] not in exclude_pairs
        ]
    if not candidates:
        return None
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0]


def get_cached_opportunities() -> List[dict]:
    with _cache_lock:
        result = list(_opportunity_cache.values())
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


DEFAULT_PRICES = {
    "BTC/USDT": 82000.0, "ETH/USDT": 3200.0, "BNB/USDT": 580.0,
    "SOL/USDT": 145.0, "PAXG/USDT": 4430.0, "DOGE/USDT": 0.38,
    "SHIB/USDT": 0.000024, "PEPE/USDT": 0.0000085, "WIF/USDT": 2.4,
    "BONK/USDT": 0.000032, "XRP/USDT": 2.15, "ADA/USDT": 0.72,
    "AVAX/USDT": 35.0, "MATIC/USDT": 0.52,
}
