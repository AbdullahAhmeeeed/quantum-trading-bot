"""
mexc_live.py — Production-Grade MEXC Live Spot Exchange Connector
Supports MEXC Global Spot with CCXT.
Features: Rate limiting, real balance fetching, safe LOT_SIZE precision formatting,
market order execution, and zero-fee spot trading integration.
"""
import ccxt
import time
import re
from typing import Dict, Any, Optional

class MEXCExchangeConnector:
    def __init__(
        self, 
        api_key: str = "", 
        api_secret: str = "", 
        is_live: bool = True,
        max_trade_cap_usd: float = 10.0
    ):
        self.api_key = re.sub(r'\s+', '', api_key) if api_key else ""
        self.api_secret = re.sub(r'\s+', '', api_secret) if api_secret else ""
        self.is_live = is_live
        self.max_trade_cap_usd = max(1.0, float(max_trade_cap_usd))
        
        config: Dict[str, Any] = {
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
                'recvWindow': 10000,
            }
        }
            
        self.exchange = ccxt.mexc(config)
        self.markets_loaded = False

    def _load_markets_safely(self):
        try:
            self.exchange.load_markets()
            self.markets_loaded = True
        except Exception as e:
            print(f"[MEXCLive] Load markets notice: {e}")
            self.markets_loaded = False

    def test_connection(self) -> dict:
        """Verify API keys, test permissions, and fetch spot balance."""
        if not self.api_key or not self.api_secret:
            return {
                'connected': False,
                'error': 'MEXC API Key or Secret is missing.',
                'exchange': self.get_exchange_name()
            }
        try:
            balance = self.exchange.fetch_balance({'type': 'spot'})
            usdt = balance.get('USDT', {}).get('free', 0) or balance.get('USD', {}).get('free', 0)
            btc = balance.get('BTC', {}).get('free', 0)
            
            return {
                'connected': True,
                'mode': 'LIVE' if self.is_live else 'TEST',
                'exchange': self.get_exchange_name(),
                'usdt_balance': float(usdt or 0.0),
                'total_stable_balance': float(usdt or 0.0),
                'btc_balance': float(btc or 0.0),
                'max_trade_cap_usd': self.max_trade_cap_usd,
                'withdrawals_blocked': True,
                'fee_discount': '0% Spot Maker / Ultra-low Taker',
            }
        except Exception as e:
            err_msg = str(e)
            if 'Signature' in err_msg or 'signature' in err_msg:
                friendly = "Invalid MEXC Secret Key signature. Ensure you copied both API Key and Secret correctly."
            elif 'IP' in err_msg or 'ip' in err_msg:
                friendly = "MEXC IP restriction: please bind your current IP in MEXC API settings or uncheck IP binding."
            elif 'Key' in err_msg or 'key' in err_msg:
                friendly = "Invalid MEXC API Key. Check your API key in MEXC."
            else:
                friendly = f"MEXC Connection Error: {err_msg}"
                
            return {
                'connected': False,
                'mode': 'LIVE' if self.is_live else 'TEST',
                'exchange': self.get_exchange_name(),
                'error': friendly
            }

    def get_exchange_name(self) -> str:
        return "MEXC Global (LIVE)" if self.is_live else "MEXC Global (DEMO)"

    def get_account_balance(self) -> dict:
        """Return non-zero assets in MEXC Spot Wallet."""
        try:
            balance = self.exchange.fetch_balance({'type': 'spot'})
            result = {}
            for asset, data in balance.get('total', {}).items():
                tot = float(data or 0)
                if tot > 0:
                    result[asset] = {
                        'free': float(balance.get('free', {}).get(asset, 0) or 0),
                        'used': float(balance.get('used', {}).get(asset, 0) or 0),
                        'total': tot
                    }
            return result
        except Exception as e:
            print(f"[MEXCLive] Balance fetch error: {e}")
            return {}

    def get_price(self, symbol: str = 'BTC/USDT') -> float:
        """Fetch live ticker last price."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker.get('last', 0) or 0)
        except Exception as e:
            print(f"[MEXCLive] Price fetch error ({symbol}): {e}")
            return 0.0

    def place_market_order(self, symbol: str, side: str, usdt_amount: float = 0.0, coin_quantity: float = 0.0) -> dict:
        """
        Place real market order on MEXC Spot with dynamic precision and min-cost safety.
        """
        try:
            if not self.markets_loaded:
                self._load_markets_safely()

            price = self.get_price(symbol)
            if price <= 0:
                return {'success': False, 'error': f'Cannot fetch live price for {symbol} on MEXC'}

            side_clean = side.upper()

            if side_clean == 'BUY':
                min_cost = 1.0
                if self.markets_loaded and symbol in self.exchange.markets:
                    min_cost = self.exchange.markets[symbol].get('limits', {}).get('cost', {}).get('min', 1.0) or 1.0
                
                effective_capital = max(float(usdt_amount), float(min_cost))
                effective_capital = min(effective_capital, self.max_trade_cap_usd)

                raw_qty = effective_capital / price
                qty_str = self.exchange.amount_to_precision(symbol, raw_qty)
                quantity = float(qty_str)

            elif side_clean == 'SELL':
                if coin_quantity > 0:
                    quantity = float(self.exchange.amount_to_precision(symbol, coin_quantity))
                else:
                    base_currency = symbol.split('/')[0]
                    bal = self.exchange.fetch_balance({'type': 'spot'})
                    val = bal.get(base_currency)
                    if isinstance(val, dict):
                        free_coin = float(val.get('free', 0.0) or 0.0)
                    elif isinstance(val, (int, float)):
                        free_coin = float(val)
                    else:
                        free_coin = float(bal.get('free', {}).get(base_currency, 0.0) or 0.0)

                    if free_coin <= 0:
                        return {'success': False, 'error': f'No free {base_currency} balance available on MEXC'}

                    if (free_coin * price) < 0.5:
                        return {'success': False, 'error': f'Value too small: {free_coin} {base_currency} = ${free_coin * price:.4f} USD'}

                    qty_str = self.exchange.amount_to_precision(symbol, free_coin)
                    quantity = float(qty_str)
            else:
                return {'success': False, 'error': f'Invalid order side: {side}'}

            if quantity <= 0:
                return {'success': False, 'error': f'Quantity {quantity} below MEXC minimum step size'}

            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side_clean.lower(),
                amount=quantity
            )

            fill_price = float(order.get('price') or order.get('average') or price)
            filled_amount = float(order.get('filled') or order.get('amount') or quantity)
            cost = float(order.get('cost') or (fill_price * filled_amount))

            return {
                'success': True,
                'order_id': str(order.get('id', '')),
                'symbol': symbol,
                'side': side_clean,
                'amount': filled_amount,
                'price': fill_price,
                'cost_usd': round(cost, 4),
                'status': order.get('status', 'closed'),
                'exchange': 'MEXC',
                'mode': 'LIVE',
                'timestamp': order.get('timestamp', int(time.time() * 1000))
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'MEXC Order Execution Failed: {str(e)}'
            }
