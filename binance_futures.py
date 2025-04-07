import requests
import hashlib
import hmac
import time
import sys
from logging_config import logger
from file_utils import load_json
import pandas as pd
import numpy as np
from datetime import datetime


# Fetch settings
secrets = load_json("secrets.json")
api_key = secrets.get("api_key")
api_secret = secrets.get("api_secret")
base_url = secrets.get("base_url")

def get_market_price(symbol, api_key, api_secret):
    try:
        endpoint = '/fapi/v1/ticker/price'
        params = {'symbol': symbol}
        response = requests.get(base_url + endpoint, params=params)
        if response.status_code == 200:
            return float(response.json()['price'])
        else:
            print(f"Failed to get market price: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_server_time(api_key, api_secret):
    """
    Fetches the current time from the Binance server.

    Args:
        api_key (str): API key.
        api_secret (str): API secret.

    Returns:
        int: Server's timestamp.
    """
    endpoint = '/fapi/v1/time'
    headers = {'X-MBX-APIKEY': api_key}

    try:
        response = requests.get(base_url + endpoint, headers=headers)
        response.raise_for_status()  # Check if the response is successful
        return response.json()['serverTime']
    except Exception as e:
        print(f"Error fetching server time: {e}")
        return None

def create_signature(query_string, secret):
    return hmac.new(secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def get_open_positions(symbol, api_key, api_secret):
    """
    Fetches open positions for a given symbol.

    Args:
        symbol (str): Trading symbol, e.g., "BTCUSDT".
        api_key (str): API key.
        api_secret (str): API secret.

    Returns:
        list: List of open positions where positionAmt != 0.
        dict: {"error": "message"} if an error occurs.
    """
    endpoint = '/fapi/v2/positionRisk'
    timestamp = int(time.time() * 1000)  # Generate local timestamp

    params = {'timestamp': timestamp}
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = create_signature(query_string, api_secret)
    params['signature'] = signature
    headers = {'X-MBX-APIKEY': api_key}

    try:
        response = requests.get(base_url + endpoint, headers=headers, params=params)
        response.raise_for_status()
        positions = response.json()

        # Return only positions with an open amount (positionAmt != 0)
        return [pos for pos in positions if pos['symbol'] == symbol and float(pos['positionAmt']) != 0]

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        return {"error": f"HTTP Error {e.response.status_code}"}
    except Exception as e:
        print(f"Error fetching open positions: {e}")
        return {"error": "API request failed"}

def get_open_orders(symbol, api_key, api_secret):
    """
    Fetches open orders for a given symbol.

    Args:
        symbol (str): Trading symbol, e.g., "BTCUSDT".
        api_key (str): API key.
        api_secret (str): API secret.

    Returns:
        list: List of open orders if successful.
        dict: {"error": "message"} if an error occurs.
    """
    endpoint = '/fapi/v1/openOrders'
    timestamp = int(time.time() * 1000)  # Paikallinen aikaleima

    params = {
        'symbol': symbol,
        'timestamp': timestamp,
        'recvWindow': 10000  # 10 sekuntia
    }
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = create_signature(query_string, api_secret)
    params['signature'] = signature
    headers = {'X-MBX-APIKEY': api_key}

    try:
        response = requests.get(base_url + endpoint, headers=headers, params=params)
        response.raise_for_status()
        orders = response.json()
        return orders if orders else []  # Return an empty list if no open orders found
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        return {"error": f"HTTP Error {e.response.status_code}"}
    except Exception as e:
        print(f"Error fetching open orders: {e}")
        return {"error": "API request failed"}

def cancel_existing_orders(symbol, api_key, api_secret):
    open_orders = get_open_orders(symbol, api_key, api_secret)

    if open_orders:
        print(f"Found {len(open_orders)} open orders for {symbol}. Cancelling all orders...")
        cancelled_orders = 0

        for order in open_orders:
            print(f"Cancelling order ID: {order['orderId']} for {symbol} at price {order['price']}")

            endpoint = '/fapi/v1/order'
            timestamp = int(time.time() * 1000)
            params = {'symbol': symbol, 'orderId': order['orderId'], 'timestamp': timestamp}
            query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
            signature = create_signature(query_string, api_secret)
            params['signature'] = signature
            headers = {'X-MBX-APIKEY': api_key}

            response = requests.delete(base_url + endpoint, headers=headers, params=params)
            if response.status_code == 200:
                print(f"Order {order['orderId']} cancelled successfully.")
                cancelled_orders += 1
            else:
                print(f"Failed to cancel order {order['orderId']}. Status code: {response.status_code}. Response: {response.text}")

        print(f"Total cancelled orders: {cancelled_orders}")
    else:
        print(f"No open orders found for {symbol}.")

def get_symbol_info(symbol, api_key, api_secret):
    url = f"https://fapi.binance.com/fapi/v1/exchangeInfo?symbol={symbol}"
    response = requests.get(url)
    data = response.json()

    if 'symbols' in data:
        return data['symbols'][0]
    else:
        print(f"Error fetching symbol info: {data}")
        return None

def get_tick_size(symbol, api_key, api_secret):
    endpoint = "/fapi/v1/exchangeInfo"

    try:
        response = requests.get(base_url + endpoint)
        data = response.json()

        if "symbols" in data:
            for s in data['symbols']:
                if s['symbol'] == symbol:
                    for filter in s['filters']:
                        if filter['filterType'] == 'PRICE_FILTER':
                            tick_size = float(filter['tickSize'])
                            return tick_size
        print(f"Symbol {symbol} not found in exchange info.")
        return None

    except Exception as e:
        print(f"Error fetching tick size: {e}")
        return None

def cancel_order(symbol, order_id, api_key, api_secret):

    #base_url = "https://fapi.binance.com"
    endpoint = "/fapi/v1/order"
    url = base_url + endpoint

    # Create the request parameters
    timestamp = int(time.time() * 1000)
    params = {
        'symbol': symbol,
        'orderId': order_id,
        'timestamp': timestamp
    }

    # Sign the request
    query_string = '&'.join([f"{key}={params[key]}" for key in params])
    signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params['signature'] = signature

    headers = {
        'X-MBX-APIKEY': api_key
    }

    # Send the request to cancel the order
    response = requests.delete(url, headers=headers, params=params)

    if response.status_code == 200:
        print(f"Order {order_id} canceled successfully.")
    else:
        print(f"Failed to cancel order {order_id}. Error: {response.text}")

    return response.json()

def place_limit_order(symbol, side, quantity, price, api_key, api_secret, position_side, working_type):
    time.sleep(0.5)
    log_timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    endpoint = '/fapi/v1/order'
    timestamp = int(time.time() * 1000)
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'LIMIT',
        'quantity': round(quantity, 3),
        'price': round(price, 7),
        'timeInForce': 'GTC',
        'timestamp': timestamp,
        'workingType': working_type
    }

    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = create_signature(query_string, api_secret)
    params['signature'] = signature

    headers = {'X-MBX-APIKEY': api_key}

    try:
        response = requests.post(base_url + endpoint, headers=headers, data=params)
        response_data = response.json()
        print(f"{log_timestamp} Limit order response: {response_data}")
        logger.info(f"Limit order response: {response_data}")
        # Check if the response is an error
        if 'code' in response_data:
            handle_binance_error(response_data, symbol, api_key, api_secret)
            return None
        elif 'orderId' not in response_data:
            print(f"{log_timestamp} Warning: Limit order response missing orderId for {symbol}. Triggering grid reset.")
            logger.warning(f"Limit order response missing orderId for {symbol}. Triggering grid reset.")
            reset_grid(symbol, api_key, api_secret)  # Reset grid as a precaution
            return None

        return response_data

    except Exception as e:
        print(f"Error placing limit order: {e}")
        logger.error(f"Error placing limit order: {e}")
        return None

def place_stop_market_order(symbol, side, quantity, stop_price, api_key, api_secret, working_type):
    time.sleep(0.5)
    log_timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    endpoint = '/fapi/v1/order'
    timestamp = int(time.time() * 1000)
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'STOP_MARKET',
        'quantity': round(quantity, 3),
        'stopPrice': round(stop_price, 7),
        'timestamp': timestamp,
        'workingType': working_type
    }

    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = create_signature(query_string, api_secret)
    params['signature'] = signature

    headers = {'X-MBX-APIKEY': api_key}

    try:
        response = requests.post(base_url + endpoint, headers=headers, data=params)
        response_data = response.json()
        print(f"{log_timestamp} Stop Market order response: {response_data}")
        logger.info(f"Stop Market order response: {response_data}")

        # Check if the response is an error
        if 'code' in response_data:
            handle_binance_error(response_data, symbol, api_key, api_secret)
            return None
        elif 'orderId' not in response_data:
            print(f"{log_timestamp} Warning: Stop Market order response missing orderId for {symbol}. Triggering grid reset.")
            logger.warning(f"Warning: Stop Market order response missing orderId for {symbol}. Triggering grid reset.")
            reset_grid(symbol, api_key, api_secret)  # Reset grid as a precaution
            return None

        return response_data

    except Exception as e:
        print(f"Error placing stop-market order: {e}")
        logger.error(f"Error placing stop-market order: {e}")
        return None

def place_market_order(symbol, side, quantity, api_key, api_secret):
    """
    Places a market order to close a position.

    Args:
        symbol (str): Trading pair.
        side (str): "BUY" or "SELL".
        quantity (float): Amount to close.
        api_key (str): API key.
        api_secret (str): API secret.

    Returns:
        dict: API response for the market order.
    """
    endpoint = '/fapi/v1/order'

    # Call get_server_time and ensure it does not return None
    timestamp = get_server_time(api_key, api_secret)

    if not timestamp:
        print("Failed to fetch server time. Aborting order placement.")
        return None

    params = {
        'symbol': symbol,
        'side': side,
        'type': 'MARKET',
        'quantity': quantity,
        'timestamp': timestamp
    }

    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    signature = create_signature(query_string, api_secret)
    headers = {'X-MBX-APIKEY': api_key}
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

    try:
        response = requests.post(base_url + endpoint + '?' + query_string + '&signature=' + signature, headers=headers)
        response.raise_for_status()  # Check if the response is successful
        print(f"{timestamp} Place market order response: {response}")
        return response.json()
    except Exception as e:
        print(f"{timestamp} Error placing market order: {e}")
        return None

def open_trailing_stop_order(symbol, side, quantity, callback_rate, api_key, api_secret, working_type):
    endpoint = '/fapi/v1/order'
    timestamp = int(time.time() * 1000)
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'TRAILING_STOP_MARKET',
        'quantity': abs(round(quantity, 3)),  # Ensure quantity is positive and round to 3 decimal places
        'callbackRate': callback_rate,
        'timestamp': timestamp,
        'workingType': working_type
    }

    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = create_signature(query_string, api_secret)  # Create a signature
    params['signature'] = signature

    headers = {
        'X-MBX-APIKEY': api_key
    }

    response = requests.post(base_url + endpoint, headers=headers, data=params)
    print(f"Trailing stop order response: {response.json()}")
    logger.info(f"Trailing stop order response: {response.json()}")
    return response.json()

def close_open_positions(symbol, api_key, api_secret):
    """
    Closes all open positions for a given symbol.

    Args:
        symbol (str): Trading symbol, such as "BTCUSDT".
        api_key (str): API key.
        api_secret (str): API secret.
    """
    try:
        # Retrieve open positions
        positions = get_open_positions(symbol, api_key, api_secret)

        if not positions:
            print(f"No open positions found for {symbol}.")
            return

        for position in positions:
            if position['positionAmt'] != 0:  # Check if there are open positions
                if float(position['positionAmt']) > 0:  # If the position is long
                    close_side = "SELL"
                else:  # If the position is short
                    close_side = "BUY"

                # Attempt to close the position using a market order
                success = close_position(symbol, close_side, abs(float(position['positionAmt'])), api_key, api_secret)

                # Check position closing
                if not success:
                    print(f"Failed to close position for {symbol}. Initiating grid reset.")
                    reset_grid(symbol, api_key, api_secret)
                    return  # Cancel if position still open
                else:
                    print(f"Position closed for {symbol} successfully.")
                    logger.info(f"Position closed for {symbol} successfully.")

    except Exception as e:
        print(f"Error closing positions: {e}")
        reset_grid(symbol, api_key, api_secret)  # Reset as precaution

def close_position(symbol, side, quantity, api_key, api_secret):
    """
    Places a market order to close the position.

    Args:
        symbol (str): Trading symbol, such as "BTCUSDT".
        side (str): "BUY" or "SELL" side to close the position.
        quantity (float): Amount to close.
        api_key (str): API key.
        api_secret (str): API secret.

    Returns:
        bool: True if the position was successfully closed, False otherwise.
    """
    try:
        order = place_market_order(symbol, side, quantity, api_key, api_secret)
        print(f"Placed market order to close position: {order}")

        # Tarkistetaan, että toimeksianto onnistui
        if 'orderId' in order:
            return True
        else:
            print(f"Order response did not contain 'orderId': {order}")
            return False

    except Exception as e:
        print(f"Error placing market order: {e}")
        logger.error(f"Error placing market order: {e}")
        return False

def set_leverage_if_needed(symbol, leverage, api_key, api_secret):
    """
    Set leverage for the given symbol if needed.

    Args:
        symbol (str): Trading symbol, such as "BTCUSDT".
        leverage (int): 1-125 Depending on the symbol. Please check the maximum leverage at https://www.binance.com/en/futures/
        timestamp (str): Timestamp in milliseconds
        signature (str): Signature in sha256 encoded.
        api_key (str): API key.
        api_secret (str): API secret.
    """

    headers = {"X-MBX-APIKEY": api_key}

    # Get current timestamp in milliseconds
    timestamp = get_server_time(api_key, api_secret)

    query_string = f"symbol={symbol}&leverage={leverage}&timestamp={timestamp}"

    # Create the signature
    signature = create_signature(query_string, api_secret)

    # Create params dictionary for the request
    params = {
        "symbol": symbol,
        "leverage": leverage,
        "timestamp": timestamp,
        "signature": signature
    }

    try:
        response = requests.post(base_url, headers=headers, params=params)
        response.raise_for_status()
        result = response.json()
        print(f"Leverage for {symbol} set to {leverage}x successfully.")
        return result
    except requests.exceptions.HTTPError as e:
        print(f"Failed to set leverage for {symbol}.")
        return None
    except Exception as e:
        print(f"Unhandled error while setting leverage for {symbol}: {e}")
        return None

def reset_grid(symbol, api_key, api_secret):
    """
    Performs a grid reset:
    1. Closes all open positions.
    2. Cancels all buy and sell orders.
    3. Clears the symbol-specific JSON file.
    4. Prints a notification of the reset.

    Args:
        symbol (str): Trading symbol, such as "BTCUSDT".
        api_key (str): API key.
        api_secret (str): API secret.
    """
    from order_management import clear_orders_file
    # Close open positions
    close_open_positions(symbol, api_key, api_secret)

    # Cancel all buy and sell orders
    cancel_existing_orders(symbol, api_key, api_secret)

    # Clear the JSON file
    clear_orders_file(f"{symbol}_open_orders.json")  # Use a symbol-specific file

    # Notify that the grid has been reset
    message = f"{symbol} Grid reset, bot will now place new orders in the next loop."
    log_and_print(message)

def handle_binance_error(error, symbol, api_key, api_secret):
    """
    Handles a Binance error and performs a grid reset or other actions if needed.

    Args:
        error (dict): Binance API error containing 'code' and 'msg'.
        symbol (str): Trading symbol, such as "BTCUSDT".
        api_key (str): API key.
        api_secret (str): API secret.
    """
    error_code = error.get('code')
    error_message = error.get('msg')

    print(f"Binance API Error: {error_code} - {error_message}")

    # Fetch all symbols from config.json
    config = load_json("config.json")
    crypto_settings = config.get("crypto_settings", {})
    symbols = [settings["symbol"] for settings in crypto_settings.values()]

    # Handle different error codes
    if error_code == -1021:  # Timestamp error
        print("Timestamp issue detected. Synchronizing time and resetting grid...")
        time.sleep(2)  # Wait a moment before synchronizing time
        reset_grid(symbol, api_key, api_secret)
        return

    elif error_code == -1102:  #  Mandatory parameter 'price' was not sent, was empty/null, or malformed..
        message = f"{symbol}  Mandatory parameter 'price' was not sent, was empty/null, or malformed..."
        log_and_print(message)
        return

    elif error_code == -2019:  # Insufficient margin
        message = "Insufficient margin detected. Closing positions and resetting grid for all symbols, then shutting down the bot..."
        log_and_print(message)

        # Reset all symbols before shutting down
        for active_symbol in symbols:
            try:
                reset_grid(active_symbol, api_key, api_secret)
            except Exception as e:
                logger.error(f"Error while resetting grid for {active_symbol}: {e}")
                print(f"Error while resetting grid for {active_symbol}: {e}")

        sys.exit("Bot stopped due to insufficient margin.")

    elif error_code == 400:  # Bad Request
        message = f"{symbol} Bad Request error detected. Checking symbol validity and resetting grid if necessary..."
        log_and_print(message)
        reset_grid(symbol, api_key, api_secret)
        return

    elif error_code == -1008: # Server is currently overloaded with other requests. Please try again in a few minutes.
        message = f"{symbol} Server is currently overloaded with other requests. Please try again in a few minutes.."
        log_and_print(message)
        time.sleep(2)
        return

    elif error_code == -4164:  # Insufficient notional. Skip the symbol
        message = f"{symbol} Order's notional must be no smaller than 5 (unless you choose reduce only)."
        log_and_print(message)
        return

    # Additional common error codes can be added here
    else:
        message = f"{symbol} Unhandled error ({error_code}): {error_message}. Closing positions and resetting grid as a precaution"
        log_and_print(message)
        reset_grid(symbol, api_key, api_secret)
        return

def get_step_size(symbol, api_key, api_secret):
    endpoint = "/fapi/v1/exchangeInfo"
    try:
        response = requests.get(base_url + endpoint)
        response.raise_for_status()
        data = response.json()
        if "symbols" in data:
            for s in data['symbols']:
                if s['symbol'] == symbol:
                    for f in s['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            step_size = float(f['stepSize'])
                            return step_size
        print(f"Symbol {symbol} not found in exchange info.")
        return None
    except Exception as e:
        print(f"Error fetching Futures step size: {e}")
        return None

def log_and_print(message):
    print(message)
    logger.info(message)

def get_bollinger_bands(symbol, api_key, api_secret, klines_interval, bb_period, limit=None):
    """
    Fetches candlestick data and calculates Bollinger Bands.

    Args:
        symbol (str): Trading pair, e.g., "BTCUSDT".
        api_key (str): API key.
        api_secret (str): API secret.
        klines_interval (str): Candlestick interval (e.g., "1h", "4h").
        bb_period (int): Number of periods for Bollinger Bands calculation.
        limit (int, optional): Number of candles to fetch. If None, defaults to bb_period.

    Returns:
        dict: Contains SMA, Upper Band, Lower Band, BBW, and raw candles.
              Returns None if data fetch fails.
    """
    base_url = "https://fapi.binance.com"
    endpoint = "/fapi/v1/klines"
    limit = limit if limit is not None else bb_period
    params = {
        "symbol": symbol.upper(),
        "interval": klines_interval,
        "limit": limit
    }

    try:
        response = requests.get(base_url + endpoint, params=params)
        response.raise_for_status()
        candles = response.json()

        if len(candles) < bb_period:
            logger.warning(f"Insufficient candles ({len(candles)}) for {symbol}. Required: {bb_period}.")
            return None

        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                                            'quote_asset_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
        df = df.astype(float)

        # Calculate Bollinger Bands
        df['SMA'] = df['close'].rolling(window=bb_period, min_periods=bb_period).mean()
        df['SD'] = df['close'].rolling(window=bb_period, min_periods=bb_period).std()
        df['UpperBand'] = df['SMA'] + (2 * df['SD'])
        df['LowerBand'] = df['SMA'] - (2 * df['SD'])
        df['BBW'] = np.where(df['SMA'] > 0, (df['UpperBand'] - df['LowerBand']) / df['SMA'], np.nan)

        return {
            'sma': df['SMA'].iloc[-1],
            'upper_band': df['UpperBand'].iloc[-1],
            'lower_band': df['LowerBand'].iloc[-1],
            'bbw': df['BBW'].iloc[-1],
            'candles': candles,
            'df': df  # Full DataFrame for further analysis
        }

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error for {symbol}: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Error fetching Bollinger Bands for {symbol}: {e}")
        return None

def calculate_dynamic_base_spacing(symbol, api_key, api_secret, multiplier=0.3, min_spacing=0.0001, min_percentage=0.003):
    default_spacing = 0.007

    # Fetch Bollinger Bands (only 3 candles for amplitude)
    bb_data = get_bollinger_bands(symbol, api_key, api_secret, klines_interval="4h", bb_period=3, limit=3)
    if bb_data is None:
        logger.warning(f"Falling back to default base_spacing: {default_spacing:.5%}")
        return default_spacing

    candles = bb_data['candles']
    amplitudes = []
    for candle in candles:
        high = float(candle[2])
        low = float(candle[3])
        if low > 0:
            amplitude = (high - low) / low
            amplitudes.append(amplitude)

    if not amplitudes:
        logger.warning(f"No amplitude data available for {symbol}. Using default base_spacing: {default_spacing:.5%}")
        return default_spacing

    avg_amplitude = sum(amplitudes) / len(amplitudes)
    latest_price = float(candles[-1][4])

    dynamic_base_spacing = max(avg_amplitude * multiplier * latest_price, min_spacing)
    min_allowed_spacing = latest_price * min_percentage
    dynamic_base_spacing = max(dynamic_base_spacing, min_allowed_spacing)

    return dynamic_base_spacing

def calculate_bot_trigger(symbol, api_key, api_secret, bbw_threshold, klines_interval, bot_active, bb_period=15, candle_size_multiplier=1.3, min_candles=5):
    """
    Determines whether to start or stop the grid bot based on BBW value.

    Parameters:
    - symbol: Trading pair (e.g., 'BTCUSDT')
    - api_key, api_secret: Binance API keys
    - bbw_threshold: BBW threshold value (e.g., 0.04)
    - klines_interval: Candlestick interval (e.g., '1h')
    - bot_active: Boolean, whether the bot is currently active
    - bb_period: Length of Bollinger Bands period (e.g., 15)
    - candle_size_multiplier: Multiplier for candle size (not used in decision)
    - min_candles: Minimum number of candles for size analysis

    Returns:
    - dict: {
        'start_bot': Boolean (True = start, False = stop/no action),
        'strategy': str ('grid' or 'none'),
        'bbw': float (current BBW value),
        'candle_outside_bb': Boolean,
        'candle_size_deviation': float,
        'message': str (explanation for decision)
    }
    """
    # Fetch Bollinger Bands
    bb_data = get_bollinger_bands(symbol, api_key, api_secret, klines_interval, bb_period, limit=bb_period + max(min_candles, 10))
    if bb_data is None:
        return {'start_bot': False, 'strategy': 'none', 'message': "Data fetch failed."}

    df = bb_data['df']
    latest_bbw = bb_data['bbw']
    if pd.isna(latest_bbw):
        logger.warning(f"BBW NaN for {symbol}.")
        return {'start_bot': False, 'strategy': 'none', 'message': "BBW calculation failed."}

    latest_close = df['close'].iloc[-1]
    latest_upper = bb_data['upper_band']
    latest_lower = bb_data['lower_band']
    bb_tolerance = 0.001
    candle_outside_bb = (latest_close > latest_upper * (1 + bb_tolerance) or
                         latest_close < latest_lower * (1 - bb_tolerance))

    # Candle size analysis (retained but not affecting breakout)
    df['CandleSize'] = df['high'] - df['low']
    latest_candle_size = df['CandleSize'].iloc[-1]
    avg_candle_size = df['CandleSize'].iloc[-min_candles-1:-1].mean()
    candle_size_deviation = latest_candle_size / avg_candle_size if avg_candle_size > 0 else None

    # Hybrid criterion: Start when BBW < bbw_threshold / 2, stop when BBW > bbw_threshold
    bbw_start_threshold = bbw_threshold / 2  # E.g., if bbw_threshold=0.04, start when BBW < 0.02

    if not bot_active:
        # Bot is not active: check if it should start
        if latest_bbw < bbw_start_threshold:
            decision = True
            strategy = 'grid'
            message = f"BBW narrow. Start grid bot. | BBW={latest_bbw:.4f}, Start Threshold={bbw_start_threshold:.4f}"
        else:
            decision = False
            strategy = 'none'
            message = f"BBW ({latest_bbw:.4f}) above start threshold ({bbw_start_threshold:.4f}). Do nothing."
    else:
        # Bot is active: check if it should stop
        if latest_bbw > bbw_threshold:
            decision = False
            strategy = 'none'
            message = f"BBW ({latest_bbw:.4f}) exceeds stop threshold ({bbw_threshold:.4f}). Stop bot."
        else:
            decision = True
            strategy = 'grid'
            message = f"BBW still narrow. Keep grid bot running. | BBW={latest_bbw:.4f}, Stop Threshold={bbw_threshold:.4f}"

    print(f"{symbol}: {message} | Upper={latest_upper:.2f}, Lower={latest_lower:.2f}, SMA={bb_data['sma']:.2f}, Close={latest_close:.2f}")
    return {
        'start_bot': decision,
        'strategy': strategy,
        'bbw': latest_bbw,
        'candle_outside_bb': candle_outside_bb,
        'candle_size_deviation': candle_size_deviation,
        'message': message
    }
