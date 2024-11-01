import requests
import hashlib
import hmac
import time
from config import api_key, api_secret, base_url

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
    timestamp = get_server_time(api_key, api_secret)

    if not timestamp:
        print("Failed to fetch server time.")
        return None

    query_string = f'timestamp={timestamp}'
    signature = create_signature(query_string, api_secret)
    headers = {'X-MBX-APIKEY': api_key}

    try:
        response = requests.get(base_url + endpoint + '?' + query_string + '&signature=' + signature, headers=headers)
        response.raise_for_status()
        positions = response.json()

        # Return only positions with an open amount (positionAmt != 0)
        return [pos for pos in positions if pos['symbol'] == symbol and float(pos['positionAmt']) != 0]

    except Exception as e:
        print(f"Error fetching open positions: {e}")
        return None

def get_open_orders(symbol, api_key, api_secret):
    # Fetch the server timestamp from Binance
    server_time = get_server_time(api_key, api_secret)
    if server_time is None:
        print("Failed to fetch server time.")
        return None

    # Use the server timestamp in the timestamp parameter
    endpoint = '/fapi/v1/openOrders'
    params = {'symbol': symbol, 'timestamp': server_time}

    # Create the signature
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = create_signature(query_string, api_secret)
    params['signature'] = signature

    headers = {'X-MBX-APIKEY': api_key}

    try:
        response = requests.get(base_url + endpoint, headers=headers, params=params)
        response.raise_for_status()  # Check if the response is successful
        return response.json()
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
