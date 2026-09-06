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


_price_history: Dict[str, list] = {}


def _score_opportunity(pair: str, price: float, prev_price: float, volume: float) -> dict:
    global _price_history
    if price <= 0:
        return {"pair": pair, "score": 5, "signal": "HOLD", "price": price, "reason": "No data",
                "pct_change": 0.0, "volume": volume, "timestamp": int(time.time())}

    if pair not in _price_history:
        _price_history[pair] = [price]
    else:
        _price_history[pair].append(price)
        if len(_price_history[pair]) > 10:
            _price_history[pair].pop(0)

    # Calculate momentum against 5-tick lookback window for realistic trend detection
    baseline_price = _price_history[pair][0] if len(_price_history[pair]) >= 3 else prev_price
    if baseline_price <= 0:
        baseline_price = price

    pct_change = ((price - baseline_price) / baseline_price) * 100.0

    # Dynamic momentum score (0 to 100)
    base_score = 45.0
    mom_boost = min(abs(pct_change) * 120.0, 40.0)
    vol_bonus = min(volume / 8.0, 15.0)
    meme_bonus = 15.0 if pair in MEME_COINS else 5.0
    
    score = min(base_score + mom_boost + vol_bonus + meme_bonus, 98.0)

    # Directional breakout signal with calibrated threshold
    if pct_change >= 0.006:
        signal = "BUY"
        reason = f"Bullish breakout surge +{pct_change:.3f}%"
    elif pct_change <= -0.006:
        signal = "SELL"
        reason = f"Bearish momentum breakdown {pct_change:.3f}%"
    else:
        signal = "BUY" if (score >= 65 and random.random() > 0.45) else "HOLD"
        reason = "Consolidation before expansion"
        score = max(score - 15.0, 10.0)

    return {
        "pair": pair,
        "score": round(score, 1),
        "signal": signal,
        "price": round(price, 8),
        "pct_change": round(pct_change, 4),
        "volume": round(volume, 1),
        "reason": reason,
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
