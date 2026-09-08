"""
bot_manager.py - Quantum AI Swarm Autonomous Survival Engine
Each bot starts with $10.
Survival Instinct:
- Goal: Make $100 profit within 24 hours.
- If balance drops to 0 or near 0 (<= $0.20): Instant DEATH.
- If 24-hour deadline expires without reaching $100: Instant DEATH.
- If $100 target achieved: TARGET HIT! Spawns 9 clone bots, each starting with $10.
- Autonomous authority: Trades any coin in the universe (BTC, ETH, SOL, PEPE, DOGE, SHIB, WIF, BONK, etc.).
"""
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

swarm_bots: Dict[str, dict] = {}
swarm_trades: List[dict] = []
swarm_lock = threading.Lock()

swarm_stats = {
    "total_bots_ever": 0,
    "active_bots": 0,
    "dead_bots_today": 0,
    "target_hit_today": 0,
    "total_pnl_today": 0.0,
    "swarm_generation": 1,
    "day_started_at": datetime.now(timezone.utc).isoformat(),
}

# Real Money Spot Trading Allocation Engine
real_trading_active: bool = False
real_allocated_capital: float = 0.0

DAILY_TARGET_USD = 100.0
STARTING_CAPITAL = 10.0
SPAWN_COUNT      = 9
MAX_BOTS         = 50
DEATH_THRESHOLD  = 0.20
SURVIVAL_DURATION_HOURS = 24.0

STATUS_ACTIVE     = "ACTIVE"
STATUS_TARGET_HIT = "TARGET_HIT"
STATUS_DEAD       = "DEAD"


def _make_bot(bot_number: int, generation: int = 1, parent_id: str = None) -> dict:
    bot_id = f"BOT-{bot_number:03d}-G{generation}"
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=SURVIVAL_DURATION_HOURS)
    return {
        "id": bot_id,
        "bot_number": bot_number,
        "generation": generation,
        "parent_id": parent_id,
        "starting_capital": STARTING_CAPITAL,
        "current_balance": STARTING_CAPITAL,
        "daily_pnl": 0.0,
        "daily_target": DAILY_TARGET_USD,
        "status": STATUS_ACTIVE,
        "survival_state": "HUNTING",
        "active_pair": None,
        "trades_today": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "spawned_children": 0,
        "created_at": now.isoformat(),
        "deadline_at": deadline.isoformat(),
        "deadline_epoch": int(deadline.timestamp()),
        "died_at": None,
        "death_reason": None,
        "target_hit_at": None,
        "strategy_mode": "AUTONOMOUS_SURVIVAL",
        "last_signal": None,
        "last_confidence": 0.0,
        "thought": "Hunting high-momentum setups. Survival mission: $10 -> $100 or die.",
    }


def create_primary_bot() -> dict:
    """Create primary Bot #1 with fresh $10 capital and 24h survival instinct."""
    with swarm_lock:
        swarm_stats["total_bots_ever"] += 1
        bot = _make_bot(bot_number=swarm_stats["total_bots_ever"], generation=1, parent_id=None)
        swarm_bots[bot["id"]] = bot
        swarm_stats["active_bots"] = len([b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE])
        return bot


def spawn_children(parent_bot_id: str) -> List[dict]:
    """Spawn 9 clones when parent hits $100 target."""
    spawned = []
    with swarm_lock:
        if parent_bot_id not in swarm_bots:
            return []
        parent = swarm_bots[parent_bot_id]
        parent["status"] = STATUS_TARGET_HIT
        parent["survival_state"] = "TARGET_ACHIEVED"
        parent["target_hit_at"] = datetime.now(timezone.utc).isoformat()
        parent["spawned_children"] = SPAWN_COUNT
        parent["thought"] = f"🏆 TARGET ACHIEVED! $100 Profit unlocked! Spawning {SPAWN_COUNT} clone bots."
        swarm_stats["target_hit_today"] += 1
        swarm_stats["swarm_generation"] = max(swarm_stats["swarm_generation"], parent["generation"] + 1)
        
        active_count = len([b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE])
        slots = min(SPAWN_COUNT, MAX_BOTS - active_count)
        for _ in range(slots):
            swarm_stats["total_bots_ever"] += 1
            child = _make_bot(
                bot_number=swarm_stats["total_bots_ever"],
                generation=parent["generation"] + 1,
                parent_id=parent_bot_id
            )
            swarm_bots[child["id"]] = child
            spawned.append(child)
        swarm_stats["active_bots"] = len([b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE])
    return spawned


def kill_bot(bot_id: str, reason: str = "Balance exhausted") -> bool:
    with swarm_lock:
        if bot_id not in swarm_bots:
            return False
        bot = swarm_bots[bot_id]
        bot["status"] = STATUS_DEAD
        bot["survival_state"] = "DEAD"
        bot["died_at"] = datetime.now(timezone.utc).isoformat()
        bot["death_reason"] = reason
        bot["thought"] = f"💀 DEAD: {reason}"
        swarm_stats["dead_bots_today"] += 1
        swarm_stats["active_bots"] = len([b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE])
    return True


def check_daily_deadlines():
    """Checks if any active bot ran out of time without making $100. If so, IT DIES."""
    now_epoch = int(time.time())
    with swarm_lock:
        for bot in list(swarm_bots.values()):
            if bot["status"] == STATUS_ACTIVE:
                # 1. Check if deadline passed
                if now_epoch >= bot.get("deadline_epoch", 0):
                    if bot["daily_pnl"] < bot["daily_target"]:
                        bot["status"] = STATUS_DEAD
                        bot["survival_state"] = "DEAD"
                        bot["died_at"] = datetime.now(timezone.utc).isoformat()
                        bot["death_reason"] = f"Failed $100 target before 24h deadline (Made: ${bot['daily_pnl']:.2f})"
                        bot["thought"] = f"💀 DEAD: 24h survival deadline expired. PnL: ${bot['daily_pnl']:.2f} / $100 target."
                        swarm_stats["dead_bots_today"] += 1
                
                # 2. Check if balance zeroed out
                elif bot["current_balance"] <= DEATH_THRESHOLD:
                    bot["status"] = STATUS_DEAD
                    bot["survival_state"] = "DEAD"
                    bot["died_at"] = datetime.now(timezone.utc).isoformat()
                    bot["death_reason"] = f"Capital liquidated (Balance: ${bot['current_balance']:.4f})"
                    bot["thought"] = f"💀 DEAD: Balance wiped out to ${bot['current_balance']:.4f}. Immediate termination."
                    swarm_stats["dead_bots_today"] += 1

        swarm_stats["active_bots"] = len([b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE])


def update_bot_trade(bot_id: str, pnl_delta: float, pair: str, signal: str, confidence: float, trade_capital: float = 0.0):
    with swarm_lock:
        if bot_id not in swarm_bots:
            return
        bot = swarm_bots[bot_id]
        if bot["status"] != STATUS_ACTIVE:
            return

        bot["current_balance"] = max(0.0, bot["current_balance"] + pnl_delta)
        bot["daily_pnl"] += pnl_delta
        bot["trades_today"] += 1
        bot["active_pair"] = pair
        bot["last_signal"] = signal
        bot["last_confidence"] = confidence

        now_str = datetime.now(timezone.utc).isoformat()
        trade_record = {
            "time": now_str,
            "bot_id": bot_id,
            "pair": pair,
            "signal": signal,
            "capital_risked": round(trade_capital, 4),
            "pnl": round(pnl_delta, 4),
            "bot_balance_after": round(bot["current_balance"], 4),
            "result": "WIN" if pnl_delta > 0 else "LOSS",
            "confidence": round(confidence, 4),
        }
        swarm_trades.insert(0, trade_record)
        if len(swarm_trades) > 200:
            swarm_trades.pop()

        # Update survival psychological state based on balance & progress
        if pnl_delta > 0:
            bot["winning_trades"] += 1
            if bot["daily_pnl"] >= 50.0:
                bot["survival_state"] = "THRIVING"
                bot["thought"] = f"🔥 THRIVING +${pnl_delta:.2f}! PnL: ${bot['daily_pnl']:.2f} | 50%+ to $100 target! ({pair} {signal})"
            else:
                bot["survival_state"] = "HUNTING"
                bot["thought"] = f"✅ WIN +${pnl_delta:.2f} on {pair}! Bal: ${bot['current_balance']:.2f} | PnL: ${bot['daily_pnl']:.2f}"
        else:
            bot["losing_trades"] += 1
            if bot["current_balance"] < 3.0:
                bot["survival_state"] = "CRITICAL"
                bot["thought"] = f"⚠️ CRITICAL SURVIVAL: Bal ${bot['current_balance']:.2f}! Strict capital preservation active."
            else:
                bot["survival_state"] = "HUNTING"
                bot["thought"] = f"❌ LOSS -${abs(pnl_delta):.2f} on {pair}. Recalibrating survival trajectory. Bal: ${bot['current_balance']:.2f}"

        # Death check on zero
        if bot["current_balance"] <= DEATH_THRESHOLD:
            bot["status"] = STATUS_DEAD
            bot["survival_state"] = "DEAD"
            bot["died_at"] = now_str
            bot["death_reason"] = f"Capital wiped out to ${bot['current_balance']:.4f}"
            bot["thought"] = f"💀 DEAD: Capital exhausted ($0.00). Terminated instantly."
            swarm_stats["dead_bots_today"] += 1

        swarm_stats["total_pnl_today"] += pnl_delta
        swarm_stats["active_bots"] = len([b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE])


def check_target_hit(bot_id: str) -> bool:
    with swarm_lock:
        if bot_id not in swarm_bots:
            return False
        bot = swarm_bots[bot_id]
        return bot["status"] == STATUS_ACTIVE and bot["daily_pnl"] >= bot["daily_target"]


def get_active_bots() -> List[dict]:
    with swarm_lock:
        return [b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE]


def get_all_bots() -> List[dict]:
    with swarm_lock:
        now_epoch = int(time.time())
        bots = []
        for b in swarm_bots.values():
            bot_copy = dict(b)
            # Add live human-readable countdown
            diff = max(0, bot_copy.get("deadline_epoch", 0) - now_epoch)
            hrs, rem = divmod(diff, 3600)
            mins, secs = divmod(rem, 60)
            bot_copy["countdown"] = f"{hrs:02d}h {mins:02d}m {secs:02d}s" if bot_copy["status"] == STATUS_ACTIVE else "EXPIRED"
            bots.append(bot_copy)
        return bots


def get_swarm_summary() -> dict:
    ensure_primary_bot()
    check_daily_deadlines()
    with swarm_lock:
        now_epoch = int(time.time())
        bots = []
        for b in swarm_bots.values():
            bot_copy = dict(b)
            diff = max(0, bot_copy.get("deadline_epoch", 0) - now_epoch)
            hrs, rem = divmod(diff, 3600)
            mins, secs = divmod(rem, 60)
            bot_copy["countdown"] = f"{hrs:02d}h {mins:02d}m {secs:02d}s" if bot_copy["status"] == STATUS_ACTIVE else "EXPIRED"
            bots.append(bot_copy)

        active = [b for b in bots if b["status"] == STATUS_ACTIVE]
        dead = [b for b in bots if b["status"] == STATUS_DEAD]
        winners = [b for b in bots if b["status"] == STATUS_TARGET_HIT]
        total_capital = sum(b["current_balance"] for b in active)
        total_pnl = swarm_stats["total_pnl_today"]
        progress_to_goal = (total_pnl / 10000.0) * 100
        return {
            "bots": bots,
            "recent_trades": swarm_trades[:30],
            "active_count": len(active),
            "dead_count": len(dead),
            "target_hit_count": len(winners),
            "total_bots": len(bots),
            "total_capital_deployed": round(total_capital, 2),
            "total_pnl_today": round(total_pnl, 2),
            "progress_to_10k_pct": round(progress_to_goal, 4),
            "swarm_generation": swarm_stats["swarm_generation"],
            "day_started_at": swarm_stats["day_started_at"],
            "daily_target_per_bot": DAILY_TARGET_USD,
            "starting_capital_per_bot": STARTING_CAPITAL,
            "real_trading_active": real_trading_active,
            "real_allocated_capital": real_allocated_capital,
        }


def ensure_primary_bot():
    check_daily_deadlines()
    with swarm_lock:
        active = [b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE]
        if not active:
            pass
        else:
            return active[0]
    return create_primary_bot()


def set_primary_bot_capital(amount: float) -> dict:
    """Set custom starting capital allocated to the primary swarm bot (e.g. $4.00)."""
    with swarm_lock:
        global STARTING_CAPITAL
        cap = max(1.0, float(amount))
        STARTING_CAPITAL = cap
        active = [b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE]
        if active:
            bot = active[0]
            bot["starting_capital"] = cap
            bot["current_balance"] = cap
            bot["daily_pnl"] = 0.0
            bot["winning_trades"] = 0
            bot["losing_trades"] = 0
            bot["thought"] = f"💰 Capital allocated: ${cap:.2f}. Minimum-risk survival mission initialized on Little Bot."
            return bot
        else:
            return create_primary_bot()


real_trading_mode = "SAFE"
initial_real_wallet_usd = 0.0


def enable_real_trading(amount: float, mode: str = "SAFE", initial_wallet_usd: float = 0.0) -> dict:
    """Activates Real Money Binance Spot execution exclusively in institutional SAFE mode."""
    global real_trading_active, real_allocated_capital, STARTING_CAPITAL, real_trading_mode, initial_real_wallet_usd
    with swarm_lock:
        cap = max(1.0, float(amount))
        real_trading_active = True
        real_allocated_capital = cap
        real_trading_mode = "SAFE"
        initial_real_wallet_usd = float(initial_wallet_usd) if initial_wallet_usd > 0 else cap
        STARTING_CAPITAL = cap
        
        mode_tag = "🛡️ SAFE INSTITUTIONAL MODE (70%+ ML Edge, Limit Entries)"
        active = [b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE]
        if active:
            bot = active[0]
            bot["starting_capital"] = cap
            bot["current_balance"] = cap
            bot["daily_pnl"] = 0.0
            bot["is_real_money"] = True
            bot["trading_mode"] = "SAFE"
            bot["thought"] = f"🔴 REAL SPOT ACTIVE ({mode_tag}): ${cap:.2f} deployed on Binance."
            return bot
        else:
            bot = create_primary_bot()
            bot["is_real_money"] = True
            bot["starting_capital"] = cap
            bot["current_balance"] = cap
            bot["trading_mode"] = "SAFE"
            bot["thought"] = f"🔴 REAL SPOT ACTIVE ({mode_tag}): ${cap:.2f} deployed on Binance."
            return bot


def disable_real_trading() -> bool:
    global real_trading_active
    with swarm_lock:
        real_trading_active = False
        active = [b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE]
        if active:
            active[0]["is_real_money"] = False
    return True


def is_real_trading_enabled() -> bool:
    return real_trading_active


def get_real_trading_mode() -> str:
    return real_trading_mode


def get_initial_real_wallet_usd() -> float:
    return initial_real_wallet_usd


def get_real_allocated_capital() -> float:
    return real_allocated_capital


