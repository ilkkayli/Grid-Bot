import json
import websocket
from threading import Thread
import time
import signal
from file_utils import load_json  # Import function to load config.json

latest_prices = {}  # Stores the latest prices for different symbols
price_received = {}  # Tracks if price data has been received for each symbol
ws = None
SYMBOLS = []  # List of trading symbols from config.json

def load_symbols():
    """ Loads trading symbols from config.json. """
    global SYMBOLS
    config = load_json("config.json")
    crypto_settings = config.get("crypto_settings", {})
    SYMBOLS = list(crypto_settings.keys())  # Extract symbols

def on_message(ws, message):
    """ Handles incoming WebSocket messages. """
    global latest_prices
    data = json.loads(message)

    if "data" in data and "p" in data["data"] and "s" in data["data"]:
        symbol = data["data"]["s"].lower()
        latest_prices[symbol] = float(data["data"]["p"])
        # print(f"Price update: {symbol.upper()} - {latest_prices[symbol]}")  # Debugging print

def on_open(ws):
    """ Subscribes to all configured symbols when the WebSocket connection opens. """
    payload = {
        "method": "SUBSCRIBE",
        "params": [f"{symbol}@trade" for symbol in latest_prices.keys()],
        "id": 1
    }
    ws.send(json.dumps(payload))
    print(f"WebSocket Subscription Sent for: {', '.join(latest_prices.keys())}")

def on_close(ws, close_status_code, close_msg):
    """ Handles WebSocket disconnection and attempts to reconnect. """
    print("WebSocket closed. Reconnecting in 5 seconds...")
    time.sleep(5)
    start_websocket(SYMBOLS)  # Restart WebSocket

def on_error(ws, error):
    """ Handles WebSocket errors. """
    print(f"WebSocket Error: {error}")

def get_latest_price(symbol):
    """ Returns the latest price for a given symbol. """
    return latest_prices.get(symbol.lower())

def start_websocket(symbols):
    """Starts a WebSocket connection to Binance for the given symbols."""
    global ws
    global price_received
    global latest_prices

    if isinstance(symbols, str):  # Convert single symbol to a list
        symbols = [symbols]

    # Update SYMBOLS-list
    global SYMBOLS
    SYMBOLS = symbols

    # Define latest_prices and price_received
    latest_prices.update({symbol.lower(): None for symbol in symbols})
    price_received.update({symbol.lower(): False for symbol in symbols})

    stream_name = "/".join([f"{symbol.lower()}@trade" for symbol in symbols])
    url = f"wss://fstream.binance.com/stream?streams={stream_name}"

    def run():
        global ws
        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_open=on_open,
            on_close=on_close,
            on_error=on_error
        )
        ws.run_forever()

    thread = Thread(target=run, daemon=True)
    thread.start()

# Handle Ctrl+C to close WebSocket safely
def signal_handler(sig, frame):
    """ Handles SIGINT (Ctrl+C) to gracefully stop WebSocket. """
    print("Ctrl+C detected, closing WebSocket...")
    stop_ws()
    exit(0)

def stop_ws():
    """ Closes the WebSocket connection. """
    global ws
    if ws:
        ws.close()
        print("WebSocket Closed Manually")

signal.signal(signal.SIGINT, signal_handler)

# Start WebSocket automatically on script execution
if __name__ == "__main__":
    start_websocket()
