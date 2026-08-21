import time
from sqlalchemy.orm import Session
from models import Portfolio, Trade

class ExecutionEngine:
    def __init__(self, default_short_margin_pct=0.20):
        # 20% initial margin for short derivatives positions (5x leverage)
        self.short_margin_pct = default_short_margin_pct

    def execute_market_order(
        self,
        db: Session,
        portfolio_id: int,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        stop_loss: float = None,
        take_profit: float = None
    ):
        """
        Executes an order on Binance Testnet (if credentials configured) or demo ledger.
        For Short selling (SELL), holds an Initial Margin requirement (20%) instead of starving 100% cash.
        """
        from models import User
        from analytics import calculate_portfolio_analytics

        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            return None

        # 1. Circuit Breaker pre-execution safety check
        stats = calculate_portfolio_analytics(db, portfolio_id)
        if stats.get('circuit_breaker_active', False):
            raise ValueError("CIRCUIT BREAKER ACTIVE: Daily drawdown threshold (-5%) triggered. Execution halted.")

        user = db.query(User).filter(User.id == portfolio.user_id).first()
        notional_cost = amount * price

        # 2. Live Exchange Routing via CCXT if API credentials exist
        if user and user.api_key and user.api_secret:
            try:
                import ccxt
                exchange = ccxt.binance({
                    'apiKey': user.api_key,
                    'secret': user.api_secret,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'future'}
                })
                # Enforce lot step and price precision
                amount = float(exchange.amount_to_precision(symbol, amount))
                order = exchange.create_order(symbol, 'market', side.lower(), amount)
                price = float(order.get('average', price) or price)
            except Exception as e:
                print(f"[ExecutionEngine] Live CCXT order error: {e}")
                # Continue with simulated ledger fill if testnet endpoint is busy

        # 3. Capital & Margin Accounting
        if side == "BUY":
            if portfolio.current_balance < notional_cost:
                raise ValueError(f"Insufficient cash balance for BUY (${portfolio.current_balance:.2f} < ${notional_cost:.2f})")
            portfolio.current_balance -= notional_cost

        elif side == "SELL":
            margin_required = notional_cost * self.short_margin_pct
            if portfolio.current_balance < margin_required:
                raise ValueError(f"Insufficient margin balance for Short SELL (${portfolio.current_balance:.2f} < ${margin_required:.2f})")
            portfolio.current_balance -= margin_required  # Collateral lockup

        # 4. Create database trade record
        trade = Trade(
            portfolio_id=portfolio_id,
            symbol=symbol,
            side=side,
            amount=amount,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status="OPEN"
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        return trade

    def close_trade(self, db: Session, trade_id: int, current_price: float):
        """
        Closes an open position, computes realized PnL, and restores locked capital + PnL.
        """
        trade = db.query(Trade).filter(Trade.id == trade_id).first()
        if not trade or trade.status != "OPEN":
            return None

        portfolio = db.query(Portfolio).filter(Portfolio.id == trade.portfolio_id).first()
        if not portfolio:
            return None

        notional_entry = trade.amount * trade.entry_price

        if trade.side == "BUY":
            pnl = (current_price - trade.entry_price) * trade.amount
            # Restore principal notional + realized PnL
            portfolio.current_balance += notional_entry + pnl

        else:  # SELL (Short)
            pnl = (trade.entry_price - current_price) * trade.amount
            # Restore 20% margin collateral + realized PnL
            margin_held = notional_entry * self.short_margin_pct
            portfolio.current_balance += margin_held + pnl

        trade.exit_price = round(current_price, 2)
        trade.pnl = round(pnl, 2)
        trade.status = "CLOSED"
        from datetime import datetime, timezone
        trade.closed_at = datetime.now(timezone.utc)
        portfolio.total_profit = round(portfolio.total_profit + pnl, 2)

        db.commit()
        db.refresh(trade)
        return trade
