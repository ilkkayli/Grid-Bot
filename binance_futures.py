import requests
import hashlib
import hmac
import time
import sys
from logging_config import logger
from file_utils import load_json

# Fetch settings
secrets = load_json("secrets.json")
api_key = secrets.get("api_key")
api_secret = secrets.get("api_secret")
base_url = secrets.get("base_url")

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
    except Exception as e:
        print(f"Error fetching open positions: {e}")
    return None

def get_open_orders(symbol, api_key, api_secret):
    """
    Fetches open orders for a given symbol.

    Args:
        symbol (str): Trading symbol, e.g., "BTCUSDT".
        api_key (str): API key.
        api_secret (str): API secret.

    Returns:
        list: List of open orders.
    """
    endpoint = '/fapi/v1/openOrders'
    timestamp = int(time.time() * 1000)  # Generate local timestamp

    params = {'symbol': symbol, 'timestamp': timestamp}
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
    except Exception as e:
        print(f"Error fetching open orders: {e}")
    return None

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
        print(f"Limit order response: {response_data}")
        logger.info(f"Limit order response: {response_data}")

        # Check if the response is an error
        if 'code' in response_data:
            handle_binance_error(response_data, symbol, api_key, api_secret)
            return None
        elif 'orderId' not in response_data:
            print(f"Warning: Limit order response missing orderId for {symbol}. Triggering grid reset.")
            logger.warning(f"Limit order response missing orderId for {symbol}. Triggering grid reset.")
            reset_grid(symbol, api_key, api_secret)  # Reset grid as a precaution
            return None

        return response_data

    except Exception as e:
        print(f"Error placing limit order: {e}")
        logger.error(f"Error placing limit order: {e}")
        return None

def place_stop_market_order(symbol, side, quantity, stop_price, api_key, api_secret, working_type):
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
        print(f"Stop Market order response: {response_data}")
        logger.info(f"Stop Market order response: {response_data}")

        # Check if the response is an error
        if 'code' in response_data:
            handle_binance_error(response_data, symbol, api_key, api_secret)
            return None
        elif 'orderId' not in response_data:
            print(f"Warning: Stop Market order response missing orderId for {symbol}. Triggering grid reset.")
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

    try:
        response = requests.post(base_url + endpoint + '?' + query_string + '&signature=' + signature, headers=headers)
        response.raise_for_status()  # Check if the response is successful
        return response.json()
    except Exception as e:
        print(f"Error placing market order: {e}")
        return None

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
