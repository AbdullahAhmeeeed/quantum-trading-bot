"""
opportunity_scanner.py - Multi-Asset Momentum Scanner
Scans 14+ trading pairs. Returns ranked list by momentum score.
"""
import time
import threading
from typing import List, Dict, Optional
import random

TRADING_UNIVERSE = [
    # Mega Caps & Store of Value
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "PAXG/USDT",
    # Top Altcoins & High-Beta Layer 1s
    "XRP/USDT", "ADA/USDT", "AVAX/USDT", "SUI/USDT", "NEAR/USDT", 
    "APT/USDT", "LINK/USDT", "DOT/USDT", "LTC/USDT", "MATIC/USDT",
    # AI & DeFi Leaders
    "FET/USDT", "RENDER/USDT", "INJ/USDT", "AAVE/USDT", "UNI/USDT",
    # High-Velocity Meme & Momentum Coins
    "PEPE/USDT", "SHIB/USDT", "DOGE/USDT", "WIF/USDT", "BONK/USDT", 
    "FLOKI/USDT", "NEIRO/USDT", "BOME/USDT"
]

_opportunity_cache: Dict[str, dict] = {}
_cache_lock = threading.Lock()
_prev_prices: Dict[str, float] = {}

MEME_COINS = {"DOGE/USDT", "SHIB/USDT", "PEPE/USDT", "WIF/USDT", "BONK/USDT", "FLOKI/USDT", "NEIRO/USDT", "BOME/USDT"}


_price_history: Dict[str, list] = {}


def _score_opportunity(pair: str, price: float, prev_price: float, volume: float, sentiment_score: float = 0.0) -> dict:
    global _price_history
    if price <= 0:
        return {"pair": pair, "score": 5, "signal": "HOLD", "price": price, "reason": "No data",
                "pct_change": 0.0, "volume": volume, "sentiment": 0.0, "timestamp": int(time.time())}

    if pair not in _price_history:
        _price_history[pair] = [price]
    else:
        _price_history[pair].append(price)
        if len(_price_history[pair]) > 10:
            _price_history[pair].pop(0)

    baseline_price = _price_history[pair][0] if len(_price_history[pair]) >= 3 else prev_price
    if baseline_price <= 0:
        baseline_price = price

    pct_change = ((price - baseline_price) / baseline_price) * 100.0

    # Institutional quantitative momentum score (0 to 100)
    base_score = 45.0
    mom_boost = min(abs(pct_change) * 140.0, 35.0)
    vol_bonus = min(volume / 8.0, 15.0)
    meme_bonus = 12.0 if pair in MEME_COINS else 4.0
    sentiment_bonus = max(-15.0, min(sentiment_score * 30.0, 15.0))
    
    score = min(max(base_score + mom_boost + vol_bonus + meme_bonus + sentiment_bonus, 5.0), 98.0)

    # Clean directional breakout signal without random fallbacks
    if pct_change >= 0.005 and score >= 65.0:
        signal = "BUY"
        reason = f"Bullish breakout surge +{pct_change:.3f}% (Sentiment: {'+' if sentiment_score >= 0 else ''}{sentiment_score:.2f})"
    elif pct_change <= -0.008:
        signal = "SELL"
        reason = f"Bearish momentum breakdown {pct_change:.3f}%"
    else:
        signal = "HOLD"
        reason = "Awaiting institutional confluence"
        score = max(score - 10.0, 15.0)

    return {
        "pair": pair,
        "score": round(score, 1),
        "signal": signal,
        "price": round(price, 8),
        "pct_change": round(pct_change, 4),
        "volume": round(volume, 1),
        "sentiment": round(sentiment_score, 2),
        "reason": reason,
        "timestamp": int(time.time()),
    }


def scan_opportunities(live_prices: Dict[str, float], live_volumes: Dict[str, float] = None, sentiment_dict: Dict[str, float] = None) -> List[dict]:
    global _prev_prices
    if live_volumes is None:
        live_volumes = {}
    if sentiment_dict is None:
        sentiment_dict = {}

    opportunities = []
    for pair in TRADING_UNIVERSE:
        price = live_prices.get(pair, 0.0)
        if price <= 0:
            continue
        prev = _prev_prices.get(pair, price)
        vol = live_volumes.get(pair, random.uniform(20, 200))
        sent = sentiment_dict.get(pair, 0.0)
        opp = _score_opportunity(pair, price, prev, vol, sentiment_score=sent)
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

def get_default_prices() -> Dict[str, float]:
    return DEFAULT_PRICES

