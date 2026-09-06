"""
bot_manager.py - Quantum AI Swarm Bot Lifecycle Engine
Manages individual bot instances: creation, monitoring, kill, spawn.
$10 starting capital per bot -> $100 daily target -> spawn 9 clones on success.
"""
import time
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional

# --- In-memory swarm state ---
swarm_bots: Dict[str, dict] = {}
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

DAILY_TARGET_USD = 100.0
STARTING_CAPITAL = 10.0
SPAWN_COUNT      = 9
MAX_BOTS         = 50
DEATH_THRESHOLD  = 0.50

STATUS_ACTIVE     = "ACTIVE"
STATUS_TARGET_HIT = "TARGET_HIT"
STATUS_DEAD       = "DEAD"


def _make_bot(bot_number: int, generation: int = 1, parent_id: str = None) -> dict:
    bot_id = f"BOT-{bot_number:03d}-G{generation}"
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
        "active_pair": None,
        "trades_today": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "spawned_children": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "died_at": None,
        "target_hit_at": None,
        "strategy_mode": "MOMENTUM",
        "last_signal": None,
        "last_confidence": 0.0,
        "thought": "Scanning market opportunities...",
    }


def create_primary_bot() -> dict:
    """Create the first bot of the day with $10."""
    with swarm_lock:
        swarm_stats["total_bots_ever"] += 1
        swarm_stats["dead_bots_today"] = 0
        swarm_stats["target_hit_today"] = 0
        swarm_stats["total_pnl_today"] = 0.0
        swarm_stats["day_started_at"] = datetime.now(timezone.utc).isoformat()
        bot = _make_bot(bot_number=swarm_stats["total_bots_ever"], generation=1, parent_id=None)
        swarm_bots[bot["id"]] = bot
        swarm_stats["active_bots"] = len([b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE])
        return bot


def spawn_children(parent_bot_id: str) -> List[dict]:
    """Spawn 9 new bots when parent hits $100 profit target."""
    spawned = []
    with swarm_lock:
        if parent_bot_id not in swarm_bots:
            return []
        parent = swarm_bots[parent_bot_id]
        parent["status"] = STATUS_TARGET_HIT
        parent["target_hit_at"] = datetime.now(timezone.utc).isoformat()
        parent["spawned_children"] = SPAWN_COUNT
        swarm_stats["target_hit_today"] += 1
        swarm_stats["swarm_generation"] = parent["generation"] + 1
        active_count = len([b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE])
        slots = min(SPAWN_COUNT, MAX_BOTS - active_count)
        for i in range(slots):
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
        bot["died_at"] = datetime.now(timezone.utc).isoformat()
        bot["thought"] = f"DEAD: {reason}"
        swarm_stats["dead_bots_today"] += 1
        swarm_stats["active_bots"] = len([b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE])
    return True


def update_bot_trade(bot_id: str, pnl_delta: float, pair: str, signal: str, confidence: float):
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
        if pnl_delta > 0:
            bot["winning_trades"] += 1
            bot["thought"] = f"WIN +${pnl_delta:.2f} | Bal: ${bot['current_balance']:.2f} | {pair} {signal} {confidence*100:.0f}%"
        else:
            bot["losing_trades"] += 1
            bot["thought"] = f"LOSS -${abs(pnl_delta):.2f} | Bal: ${bot['current_balance']:.2f} | {pair} {signal} {confidence*100:.0f}%"
        if bot["current_balance"] < DEATH_THRESHOLD:
            bot["status"] = STATUS_DEAD
            bot["died_at"] = datetime.now(timezone.utc).isoformat()
            bot["thought"] = f"DEAD - Capital exhausted. Final: ${bot['current_balance']:.4f}"
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
        return list(swarm_bots.values())


def get_swarm_summary() -> dict:
    with swarm_lock:
        bots = list(swarm_bots.values())
        active = [b for b in bots if b["status"] == STATUS_ACTIVE]
        dead = [b for b in bots if b["status"] == STATUS_DEAD]
        winners = [b for b in bots if b["status"] == STATUS_TARGET_HIT]
        total_capital = sum(b["current_balance"] for b in active)
        total_pnl = swarm_stats["total_pnl_today"]
        progress_to_goal = (total_pnl / 10000.0) * 100
        return {
            "bots": bots,
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
        }


def ensure_primary_bot():
    """Make sure at least one active bot exists. Called at startup."""
    with swarm_lock:
        active = [b for b in swarm_bots.values() if b["status"] == STATUS_ACTIVE]
        if not active:
            pass
        else:
            return active[0]
    return create_primary_bot()
