import json
import websocket
from threading import Thread
import time
import signal

latest_prices = {}  # Stores the latest prices for different symbols
price_received = {}  # Dictionary to track if price data has been received for each symbol
ws = None

def on_message(ws, message):
    """ Handles incoming WebSocket messages. """
    global latest_prices
    global price_received
    data = json.loads(message)

    if "p" in data and "s" in data:
        symbol = data["s"].lower()  # Symbol in lowercase
        latest_prices[symbol] = float(data["p"])  # Updates the latest price
        price_received[symbol] = True
        #print(f"Price data for {symbol.upper()} received.") # For debugging

def on_open(ws, symbol):
    """ Sends the subscription request for the correct symbol. """
    payload = {
        "method": "SUBSCRIBE",
        "params": [f"{symbol}@trade"],
        "id": 1
    }
    ws.send(json.dumps(payload))
    print(f"WebSocket Subscription Sent for {symbol.upper()}")
    global price_received
    price_received[symbol.lower()] = False  # Reset flag when connection opens

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def get_latest_price(symbol):
    """ Returns the latest price received from WebSocket for a specific symbol. """
    return latest_prices.get(symbol.lower())

def start_websocket(symbol):
    """ Starts the WebSocket for the given symbol in a separate thread and waits for price data. """
    global price_received
    price_received[symbol.lower()] = False  # Initialize flag for this symbol

    def run():
        ws = websocket.WebSocketApp(
            f"wss://fstream.binance.com/ws/{symbol}@trade",
            on_message=on_message,
            on_open=lambda ws: on_open(ws, symbol),
            on_close=on_close,
            on_error=on_error
        )
        ws.run_forever()

    thread = Thread(target=run, daemon=True)
    thread.start()

    # Wait for price data with a timeout
    timeout = 5  # seconds
    start_time = time.time()
    while not price_received.get(symbol.lower(), False):
        if time.time() - start_time > timeout:
            print(f"Timeout waiting for price data for {symbol.upper()}")
            break
        time.sleep(0.1)  # Small sleep to not overload CPU

# Handling Ctrl+C
def signal_handler(sig, frame):
    print("Ctrl+C detected, closing WebSocket...")
    stop_ws()
    exit(0)

def stop_ws():
    global ws
    if ws:
        ws.close()
        print("WebSocket Closed Manually")

signal.signal(signal.SIGINT, signal_handler)
