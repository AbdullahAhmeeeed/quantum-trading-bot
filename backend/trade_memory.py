import os
import time
import sqlite3
import threading
from datetime import datetime, timezone
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

class TradeMemory:
    def __init__(self, db_path="trade_memory.db"):
        self.lock = threading.RLock()
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.outcome_model = None
        self.outcome_model_accuracy = None
        self._create_tables()

    def _create_tables(self):
        with self.lock:
            cursor = self.conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT DEFAULT 'BUY',
                    entry_price REAL,
                    exit_price REAL,
                    cost_usd REAL,
                    pnl_usd REAL DEFAULT 0.0,
                    pnl_pct REAL DEFAULT 0.0,
                    exit_reason TEXT,
                    duration_seconds INTEGER DEFAULT 0,
                    entry_rsi REAL,
                    entry_bb_position REAL,
                    entry_vol_ratio REAL,
                    entry_natr REAL,
                    entry_log_ret_5 REAL,
                    entry_dist_ema_pct REAL,
                    entry_ml_confidence REAL,
                    highest_price REAL,
                    lowest_price REAL,
                    max_drawdown_pct REAL DEFAULT 0.0,
                    opened_at TEXT,
                    closed_at TEXT,
                    is_open INTEGER DEFAULT 1
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS adaptive_params (
                    id INTEGER PRIMARY KEY,
                    tp_pct REAL DEFAULT 0.018,
                    sl_pct REAL DEFAULT 0.008,
                    trailing_dist_pct REAL DEFAULT 0.008,
                    min_confidence REAL DEFAULT 0.70,
                    last_adapted_at TEXT,
                    adaptation_count INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS coin_reputations (
                    symbol TEXT PRIMARY KEY,
                    total_trades INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_pnl_usd REAL DEFAULT 0.0,
                    avg_pnl_pct REAL DEFAULT 0.0,
                    win_rate REAL DEFAULT 0.0,
                    grade TEXT DEFAULT 'NEW',
                    is_blacklisted INTEGER DEFAULT 0,
                    last_updated TEXT
                )
            ''')
            
            self.conn.commit()

    def record_entry(self, symbol, entry_price, cost_usd, ml_confidence, market_features_dict):
        now_utc = datetime.now(timezone.utc).isoformat()
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO trade_journal (
                    symbol, entry_price, cost_usd, entry_ml_confidence,
                    entry_rsi, entry_bb_position, entry_vol_ratio, entry_natr,
                    entry_log_ret_5, entry_dist_ema_pct, opened_at, is_open
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (
                symbol, entry_price, cost_usd, ml_confidence,
                market_features_dict.get('rsi_14'),
                market_features_dict.get('bb_position'),
                market_features_dict.get('vol_ratio'),
                market_features_dict.get('natr_14'),
                market_features_dict.get('log_ret_5'),
                market_features_dict.get('dist_ema_50_pct'),
                now_utc
            ))
            self.conn.commit()
            trade_id = cursor.lastrowid
            print(f"[TradeMemory] Recorded entry for {symbol}. Trade ID: {trade_id}")
            return trade_id

    def record_exit(self, trade_id, exit_price, exit_reason, highest_price=None, lowest_price=None):
        now_utc = datetime.now(timezone.utc).isoformat()
        
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM trade_journal WHERE id = ?", (trade_id,))
            trade = cursor.fetchone()
            
            if not trade:
                print(f"[TradeMemory] Trade {trade_id} not found!")
                return None
                
            entry_price = trade['entry_price']
            cost_usd = trade['cost_usd']
            opened_at_str = trade['opened_at']
            symbol = trade['symbol']
            
            pnl_usd = cost_usd * ((exit_price - entry_price) / entry_price)
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            
            opened_at = datetime.fromisoformat(opened_at_str)
            duration_seconds = int((datetime.now(timezone.utc) - opened_at).total_seconds())
            
            max_drawdown_pct = 0.0
            if lowest_price is not None:
                max_drawdown_pct = ((lowest_price - entry_price) / entry_price) * 100
                
            cursor.execute('''
                UPDATE trade_journal
                SET exit_price = ?, pnl_usd = ?, pnl_pct = ?, exit_reason = ?,
                    duration_seconds = ?, highest_price = ?, lowest_price = ?,
                    max_drawdown_pct = ?, closed_at = ?, is_open = 0
                WHERE id = ?
            ''', (
                exit_price, pnl_usd, pnl_pct, exit_reason, duration_seconds,
                highest_price, lowest_price, max_drawdown_pct, now_utc, trade_id
            ))
            self.conn.commit()
            
        print(f"[TradeMemory] Recorded exit for {symbol} (Trade {trade_id}). PnL: {pnl_pct:.2f}%")
        self._update_coin_reputation(symbol)
        
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM trade_journal WHERE id = ?", (trade_id,))
            updated_trade = dict(cursor.fetchone())
            return updated_trade

    def _update_coin_reputation(self, symbol):
        now_utc = datetime.now(timezone.utc).isoformat()
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT pnl_pct, pnl_usd FROM trade_journal 
                WHERE symbol = ? AND is_open = 0
            ''', (symbol,))
            trades = cursor.fetchall()
            
            total_trades = len(trades)
            if total_trades == 0:
                return
                
            wins = sum(1 for t in trades if t['pnl_pct'] > 0)
            losses = total_trades - wins
            total_pnl_usd = sum(t['pnl_usd'] for t in trades)
            avg_pnl_pct = sum(t['pnl_pct'] for t in trades) / total_trades
            win_rate = wins / total_trades
            
            grade = 'NEW'
            is_blacklisted = 0
            
            if total_trades < 3:
                grade = 'NEW'
            elif win_rate >= 0.70:
                grade = 'A+'
            elif win_rate >= 0.60:
                grade = 'A'
            elif win_rate >= 0.50:
                grade = 'B'
            elif win_rate >= 0.30:
                grade = 'C'
            elif win_rate < 0.30 and total_trades >= 5:
                grade = 'F'
                is_blacklisted = 1
                
            cursor.execute('''
                INSERT OR REPLACE INTO coin_reputations (
                    symbol, total_trades, wins, losses, total_pnl_usd, avg_pnl_pct,
                    win_rate, grade, is_blacklisted, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, total_trades, wins, losses, total_pnl_usd, avg_pnl_pct,
                win_rate, grade, is_blacklisted, now_utc
            ))
            self.conn.commit()

    def get_coin_reputation(self, symbol):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM coin_reputations WHERE symbol = ?", (symbol,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {'symbol': symbol, 'grade': 'NEW', 'is_blacklisted': 0, 'win_rate': 0.0}

    def get_all_coin_reputations(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM coin_reputations ORDER BY win_rate DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_adaptive_params(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM adaptive_params WHERE id = 1")
            row = cursor.fetchone()
            if not row:
                now_utc = datetime.now(timezone.utc).isoformat()
                cursor.execute('''
                    INSERT INTO adaptive_params (
                        id, tp_pct, sl_pct, trailing_dist_pct, min_confidence, last_adapted_at, adaptation_count
                    ) VALUES (1, 0.018, 0.008, 0.008, 0.70, ?, 0)
                ''', (now_utc,))
                self.conn.commit()
                cursor.execute("SELECT * FROM adaptive_params WHERE id = 1")
                row = cursor.fetchone()
            return dict(row)

    def analyze_and_adapt(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM trade_journal WHERE is_open = 0")
            trades = cursor.fetchall()
            
        total_trades = len(trades)
        if total_trades < 5:
            return {"status": "Needs at least 5 trades to adapt."}
            
        tp_count = sum(1 for t in trades if t['exit_reason'] == 'TAKE_PROFIT')
        sl_count = sum(1 for t in trades if t['exit_reason'] == 'STOP_LOSS')
        trailing_count = sum(1 for t in trades if t['exit_reason'] == 'TRAILING_PROFIT')
        stagnation_count = sum(1 for t in trades if t['exit_reason'] == 'STAGNATION_TIMEOUT')
        
        params = self.get_adaptive_params()
        
        new_tp = params['tp_pct']
        new_sl = params['sl_pct']
        new_trailing = params['trailing_dist_pct']
        new_min_conf = params['min_confidence']
        
        changes = []
        
        if sl_count / total_trades > 0.60:
            new_sl = min(new_sl + 0.002, 0.020)
            changes.append(f"Widened SL to {new_sl:.3f}")
        if stagnation_count / total_trades > 0.70:
            new_tp = max(new_tp - 0.003, 0.008)
            changes.append(f"Tightened TP to {new_tp:.3f}")
        if trailing_count / total_trades > 0.40:
            new_trailing = max(new_trailing - 0.001, 0.004)
            changes.append(f"Tightened trailing gap to {new_trailing:.3f}")
            
        conf_brackets = {
            '0.70-0.75': [], '0.75-0.80': [], '0.80-0.85': [], '0.85+': []
        }
        for t in trades:
            c = t['entry_ml_confidence']
            if c is None: continue
            if 0.70 <= c < 0.75: conf_brackets['0.70-0.75'].append(t)
            elif 0.75 <= c < 0.80: conf_brackets['0.75-0.80'].append(t)
            elif 0.80 <= c < 0.85: conf_brackets['0.80-0.85'].append(t)
            elif c >= 0.85: conf_brackets['0.85+'].append(t)
            
        current_bracket = '0.70-0.75'
        if new_min_conf >= 0.85: current_bracket = '0.85+'
        elif new_min_conf >= 0.80: current_bracket = '0.80-0.85'
        elif new_min_conf >= 0.75: current_bracket = '0.75-0.80'
        
        bracket_trades = conf_brackets[current_bracket]
        if len(bracket_trades) > 0:
            b_wins = sum(1 for t in bracket_trades if t['pnl_pct'] > 0)
            b_winrate = b_wins / len(bracket_trades)
            if b_winrate < 0.35:
                new_min_conf = min(new_min_conf + 0.02, 0.75)
                changes.append(f"Raised min confidence to {new_min_conf:.2f}")

        if not changes:
            return {"status": "No adaptation needed."}
            
        now_utc = datetime.now(timezone.utc).isoformat()
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE adaptive_params 
                SET tp_pct=?, sl_pct=?, trailing_dist_pct=?, min_confidence=?,
                    last_adapted_at=?, adaptation_count=adaptation_count+1
                WHERE id=1
            ''', (new_tp, new_sl, new_trailing, new_min_conf, now_utc))
            self.conn.commit()
            
        print(f"[TradeMemory] Adapted params: {', '.join(changes)}")
        return {"status": "Adapted", "changes": changes}

    def should_take_trade(self, symbol, ml_confidence, features_dict=None):
        rep = self.get_coin_reputation(symbol)
        if rep.get('is_blacklisted', 0) == 1:
            return (False, f"Coin {symbol} blacklisted (Grade F) after repeated losses")
            
        params = self.get_adaptive_params()
        min_conf = params['min_confidence']
        grade = rep.get('grade', 'NEW')
        
        req_conf = min_conf
        if grade == 'C':
            req_conf = min_conf + 0.08
        elif grade == 'A+':
            req_conf = max(0.65, min_conf - 0.05)
            
        if ml_confidence < req_conf:
            return (False, f"Confidence {ml_confidence:.2f} below learned threshold {req_conf:.2f}")
            
        return (True, "Trade approved")

    def retrain_outcome_model(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM trade_journal WHERE is_open = 0")
            trades = cursor.fetchall()
            
        if len(trades) < 15:
            return {'trained': False, 'status': f'Only {len(trades)} trades completed, need 15.'}
            
        X, y = [], []
        for t in trades:
            feats = [
                t['entry_rsi'] or 0.0,
                t['entry_bb_position'] or 0.0,
                t['entry_vol_ratio'] or 0.0,
                t['entry_natr'] or 0.0,
                t['entry_log_ret_5'] or 0.0,
                t['entry_dist_ema_pct'] or 0.0,
                t['entry_ml_confidence'] or 0.0
            ]
            X.append(feats)
            y.append(1 if t['pnl_pct'] > 0 else 0)
            
        X = np.array(X)
        y = np.array(y)
        
        model = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        model.fit(X, y)
        self.outcome_model = model
        
        acc = model.score(X, y)
        self.outcome_model_accuracy = acc
        print(f"[TradeMemory] Retrained outcome model on {len(trades)} trades. Accuracy: {acc:.2f}")
        return {'trained': True, 'samples': len(trades), 'accuracy': acc}

    def predict_outcome(self, features_dict):
        if self.outcome_model is None:
            return 0.5
            
        feats = np.array([[
            features_dict.get('rsi_14', 0.0),
            features_dict.get('bb_position', 0.0),
            features_dict.get('vol_ratio', 0.0),
            features_dict.get('natr_14', 0.0),
            features_dict.get('log_ret_5', 0.0),
            features_dict.get('dist_ema_50_pct', 0.0),
            features_dict.get('ml_confidence', 0.0)
        ]])
        
        prob = self.outcome_model.predict_proba(feats)[0][1]
        return prob

    def get_blended_confidence(self, primary_confidence, features_dict):
        outcome_prob = self.predict_outcome(features_dict)
        total_trades = self.total_completed_trades()
        
        self_weight = min(total_trades / 50.0, 0.4)
        blended = primary_confidence * (1 - self_weight) + outcome_prob * self_weight
        return blended

    def total_completed_trades(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) as c FROM trade_journal WHERE is_open = 0")
            row = cursor.fetchone()
            return row['c'] if row else 0

    def get_performance_summary(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM trade_journal WHERE is_open = 0")
            closed_trades = [dict(t) for t in cursor.fetchall()]
            
            cursor.execute("SELECT COUNT(*) as c FROM trade_journal WHERE is_open = 1")
            open_count = cursor.fetchone()['c']
            
        total_trades = len(closed_trades)
        wins = sum(1 for t in closed_trades if t['pnl_pct'] > 0)
        losses = total_trades - wins
        overall_win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        total_pnl_usd = sum(t['pnl_usd'] for t in closed_trades)
        avg_pnl_pct = (sum(t['pnl_pct'] for t in closed_trades) / total_trades) if total_trades > 0 else 0.0
        
        best_trade = max(closed_trades, key=lambda t: t['pnl_pct']) if closed_trades else None
        worst_trade = min(closed_trades, key=lambda t: t['pnl_pct']) if closed_trades else None
        
        avg_duration = (sum(t['duration_seconds'] for t in closed_trades) / total_trades) if total_trades > 0 else 0
        
        reasons = {}
        for t in closed_trades:
            reasons[t['exit_reason']] = reasons.get(t['exit_reason'], 0) + 1
            
        mod_status = f"Trained on {total_trades} trades" if self.outcome_model is not None else "Needs 15+ trades"
        
        params = self.get_adaptive_params()
        
        return {
            'total_trades': total_trades,
            'open_trades': open_count,
            'total_wins': wins,
            'total_losses': losses,
            'overall_win_rate': overall_win_rate,
            'total_pnl_usd': total_pnl_usd,
            'avg_pnl_pct': avg_pnl_pct,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'avg_duration_seconds': avg_duration,
            'exit_reason_breakdown': reasons,
            'outcome_model_status': mod_status,
            'outcome_model_accuracy': self.outcome_model_accuracy,
            'adaptation_count': params.get('adaptation_count', 0),
            'coin_reputations': self.get_all_coin_reputations(),
            'adaptive_params': params,
            'recent_trades': self.get_recent_trades(10)
        }

    def get_recent_trades(self, limit=20):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT symbol, pnl_pct, pnl_usd, exit_reason, duration_seconds, closed_at 
                FROM trade_journal WHERE is_open = 0 
                ORDER BY closed_at DESC LIMIT ?
            ''', (limit,))
            return [dict(t) for t in cursor.fetchall()]

trade_memory = TradeMemory()
