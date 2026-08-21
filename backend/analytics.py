from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
from models import Trade, Portfolio

def calculate_portfolio_analytics(db: Session, portfolio_id: int):
    trades = db.query(Trade).filter(Trade.portfolio_id == portfolio_id, Trade.status == 'CLOSED').all()
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()

    if not trades or not portfolio:
        return {
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "circuit_breaker_active": False
        }

    # --- Win Rate ---
    winning_trades = sum(1 for t in trades if (t.pnl or 0) > 0)
    win_rate = winning_trades / len(trades) if len(trades) > 0 else 0.0

    # --- Daily Returns ---
    df = pd.DataFrame([{"pnl": t.pnl or 0, "date": t.created_at.date()} for t in trades])
    daily_returns = df.groupby('date')['pnl'].sum()

    # --- Sharpe Ratio (annualized, risk-free rate = 0) ---
    mean_return = daily_returns.mean()
    std_return = daily_returns.std()

    sharpe_ratio = 0.0
    if std_return and not np.isnan(std_return) and std_return != 0:
        sharpe_ratio = (mean_return / std_return) * np.sqrt(365)

    # --- Max Drawdown ---
    cumulative_pnl = daily_returns.cumsum()
    running_max = cumulative_pnl.cummax()
    drawdown = running_max - cumulative_pnl
    max_drawdown = float(drawdown.max()) if not drawdown.empty else 0.0

    # --- Circuit Breaker: activate if total loss > 5% of starting capital ---
    circuit_breaker_active = False
    if portfolio.allocated_balance and portfolio.allocated_balance > 0:
        threshold = -(portfolio.allocated_balance * 0.05)   # -5% of $100k = -$5,000
        if portfolio.total_profit < threshold:
            circuit_breaker_active = True

    return {
        "win_rate": float(win_rate),
        "sharpe_ratio": float(sharpe_ratio) if not np.isnan(sharpe_ratio) else 0.0,
        "max_drawdown": max_drawdown if not np.isnan(max_drawdown) else 0.0,
        "circuit_breaker_active": circuit_breaker_active
    }
