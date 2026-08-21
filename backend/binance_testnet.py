"""
Binance Testnet Connector
URL: https://testnet.binance.vision
Free demo account with real market prices but fake money.
"""
import ccxt
import time

TESTNET_BASE_URL = 'https://testnet.binance.vision'

class BinanceTestnet:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
            },
            'urls': {
                'api': {
                    'public':  f'{TESTNET_BASE_URL}/api',
                    'private': f'{TESTNET_BASE_URL}/api',
                    'v3':      f'{TESTNET_BASE_URL}/api/v3',
                },
            }
        })
        try:
            self.exchange.load_markets()
        except Exception:
            pass

    def test_connection(self) -> dict:
        """Verify connection to testnet and return account balances."""
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {}).get('free', 0)
            btc  = balance.get('BTC',  {}).get('free', 0)
            return {
                'connected': True,
                'usdt_balance': float(usdt),
                'btc_balance': float(btc),
                'exchange': 'Binance Testnet'
            }
        except Exception as e:
            return {'connected': False, 'error': str(e)}

    def get_price(self, symbol: str = 'BTC/USDT') -> float:
        """Get the latest real market price."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            print(f"Testnet price fetch error: {e}")
            return 0.0

    def place_market_order(self, symbol: str, side: str, usdt_amount: float) -> dict:
        """
        Place a real market order on Binance Testnet with LOT_SIZE and MIN_NOTIONAL compliance.
        """
        try:
            price = self.get_price(symbol)
            if price <= 0:
                return {'success': False, 'error': 'Could not fetch price'}

            # Minimum notional filter: Binance requires at least 5 USDT per order
            if usdt_amount < 5.0:
                usdt_amount = 5.0

            raw_qty = usdt_amount / price

            # CCXT precision formatting
            qty_str = self.exchange.amount_to_precision(symbol, raw_qty)
            quantity = float(qty_str)

            if quantity <= 0:
                return {'success': False, 'error': 'Quantity below minimum step size'}

            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side.lower(),
                amount=quantity
            )

            return {
                'success': True,
                'order_id': order['id'],
                'symbol': symbol,
                'side': side.upper(),
                'amount': quantity,
                'price': float(order.get('average', price) or price),
                'status': order['status'],
                'timestamp': order['timestamp']
            }
        except Exception as e:
            print(f"[BinanceTestnet] Order error: {e}")
            return {'success': False, 'error': str(e)}

    def place_stop_loss_order(self, symbol: str, side: str, quantity: float, stop_price: float) -> dict:
        """Place a real stop-loss order on Binance Testnet with precision compliance."""
        try:
            stop_side = 'sell' if side.upper() == 'BUY' else 'buy'
            qty = float(self.exchange.amount_to_precision(symbol, quantity))
            stop_px = float(self.exchange.price_to_precision(symbol, stop_price))

            order = self.exchange.create_order(
                symbol=symbol,
                type='STOP_LOSS_LIMIT',
                side=stop_side,
                amount=qty,
                price=stop_px,
                params={'stopPrice': stop_px}
            )
            return {
                'success': True,
                'stop_order_id': order['id'],
                'stop_price': stop_price
            }
        except Exception as e:
            print(f"[BinanceTestnet] Stop loss error: {e}")
            return {'success': False, 'error': str(e)}

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            print(f"Cancel order error: {e}")
            return False

    def get_open_orders(self, symbol: str = None) -> list:
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            return [{'id': o['id'], 'symbol': o['symbol'], 'type': o['type'],
                     'side': o['side'], 'price': o['price'], 'amount': o['amount']} for o in orders]
        except Exception as e:
            print(f"Fetch open orders error: {e}")
            return []

    def get_account_balance(self) -> dict:
        try:
            balance = self.exchange.fetch_balance()
            result = {}
            for asset, data in balance['total'].items():
                if float(data) > 0:
                    result[asset] = {
                        'free':  float(balance['free'].get(asset, 0)),
                        'used':  float(balance['used'].get(asset, 0)),
                        'total': float(data)
                    }
            return result
        except Exception as e:
            print(f"Balance fetch error: {e}")
            return {}
