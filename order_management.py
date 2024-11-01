import requests
import time
import logging
import json
import os
from config import api_key, api_secret, base_url
from binance_futures import get_market_price, cancel_existing_orders, get_open_orders, get_open_positions, create_signature, get_tick_size, place_market_order

logger = logging.getLogger('order_management')
logger.setLevel(logging.INFO)
fh = logging.FileHandler('order_management.log')
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

ORDERS_FILE_TEMPLATE = "{}_open_orders.json"

def get_orders_file(symbol):
    """Returns the filename for the specific symbol."""
    return ORDERS_FILE_TEMPLATE.format(symbol)

def load_previous_orders(symbol):
    """Loads previous orders from a file for the specific symbol."""
    filename = get_orders_file(symbol)
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return json.load(file)
    return []

def save_current_orders(symbol, orders):
    """Saves current orders to a file for the specific symbol."""
    filename = get_orders_file(symbol)
    with open(filename, "w") as file:
        json.dump(orders, file)

def clear_orders_file(symbol):
    """Clears the file for the specific symbol when the bot starts."""
    filename = get_orders_file(symbol)
    with open(filename, 'w') as file:
        json.dump([], file)
    print(f"{filename} cleared.")

def save_open_orders_to_file(symbol, open_orders):
    """Saves open orders to a file for the specific symbol."""
    filename = get_orders_file(symbol)
    try:
        with open(filename, 'w') as file:
            json.dump(open_orders, file, indent=4)
        print(f"Saved open orders to {filename}.")
    except Exception as e:
        print(f"Error saving open orders to file: {e}")

def load_open_orders_from_file(symbol):
    """Reads open orders from the specific symbol's file."""
    filename = get_orders_file(symbol)
    try:
        with open(filename, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"{filename} not found. Assuming no previous orders.")
        return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {filename}. Assuming no valid orders.")
        return []
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return []

def round_to_tick_size(price, tick_size):
    """Rounds the price to the nearest tick size."""
    return round(price / tick_size) * tick_size

def calculate_variable_grid_spacing(level, grid_levels, base_spacing):
    """Calculates grid spacing where the spacing decreases towards the center."""
    mid_level = grid_levels // 2
    factor = 1 / (1 + abs(level - mid_level) / mid_level)
    return base_spacing * factor

# Modified handle_grid_orders function for neutral, long, and short modes
def handle_grid_orders(symbol, grid_levels, range_percentage, order_quantity, working_type, leverage, margin_type, quantity_multiplier, mode, spacing_percentage):
    # Retrieve current market price
    market_price = get_market_price(symbol, api_key, api_secret)
    if market_price is None:
        print("Error: Could not retrieve market price.")
        return

    print(f"Market price: {market_price}")

    # Retrieve tick size for the trading pair
    tick_size = get_tick_size(symbol, api_key, api_secret)
    if tick_size is None:
        print("Error: Could not retrieve tick size.")
        return

    print(f"Tick size: {tick_size}")

    # Calculate base grid_spacing
    base_spacing = market_price * (spacing_percentage / 100)  # from the market price
    print(f"Base grid spacing: {base_spacing}")

    # Define price tolerance (5% of base spacing, adjustable)
    tolerance = base_spacing * 0.05

    # Fetch current open orders from Binance. If any errors occur, the grid will be reset, and open positions will be closed.

    open_orders = get_open_orders(symbol, api_key, api_secret)

    # Check for error indication in the response
    if 'Error' in str(open_orders):
        print("Error detected in open orders response.")
        reset_grid(symbol, api_key, api_secret)  # Reset grid on error
    else:
        print(f"Current open orders: {open_orders}")

    # Load previous open orders from file
    previous_orders = load_open_orders_from_file(symbol)

    new_orders = []

    if not open_orders:
        # If there are no open orders, create new grid orders depending on mode
        print(f"Mode: {mode}")

        if mode == 'neutral':
            # Neutral mode: orders on both sides of the market price
            for level in range(1, grid_levels + 1):
                buy_price = round_to_tick_size(market_price - (level * base_spacing), tick_size)
                sell_price = round_to_tick_size(market_price + (level * base_spacing), tick_size)

                print(f"Placing BUY order at {buy_price}")
                buy_order = place_limit_order(symbol, 'BUY', order_quantity, buy_price, api_key, api_secret, 'LONG', working_type)

                # Check if buy order was successfully placed
                if 'orderId' in buy_order:
                    new_orders.append({'orderId': buy_order['orderId'], 'price': buy_price, 'side': 'BUY'})
                else:
                    print(f"Error placing BUY order at {buy_price}")

                print(f"Placing SELL order at {sell_price}")
                sell_order = place_limit_order(symbol, 'SELL', order_quantity, sell_price, api_key, api_secret, 'SHORT', working_type)

                # Check if sell order was successfully placed
                if 'orderId' in sell_order:
                    new_orders.append({'orderId': sell_order['orderId'], 'price': sell_price, 'side': 'SELL'})
                else:
                    print(f"Error placing SELL order at {sell_price}")

        elif mode == 'long':
            # Long mode: grid created above the market price
            for level in range(1, grid_levels + 1):
                buy_price = round_to_tick_size(market_price + (level * base_spacing), tick_size)
                sell_price = round_to_tick_size(buy_price + grid_levels * base_spacing, tick_size)

                # Check if a BUY order is already set at the same level (with tolerance)
                if any(abs(float(order['price']) - buy_price) <= tolerance and order['side'] == 'BUY' for order in open_orders):
                    print(f"Buy order already exists at {buy_price} within tolerance range.")
                    continue

                print(f"Placing BUY order at {buy_price}")
                buy_order = place_stop_market_order(symbol, 'BUY', order_quantity, buy_price, api_key, api_secret, working_type)

                # Check if a SELL order is already set at the same level (with tolerance)
                if any(abs(float(order['price']) - sell_price) <= tolerance and order['side'] == 'SELL' for order in open_orders):
                    print(f"Sell order already exists at {sell_price} within tolerance range.")
                    continue

                print(f"Placing SELL order at {sell_price}")
                sell_order = place_limit_order(symbol, 'SELL', order_quantity, sell_price, api_key, api_secret, 'SHORT', working_type)

                new_orders.append({'orderId': buy_order['orderId'], 'price': buy_price, 'side': 'BUY', 'type': buy_order['type']})
                new_orders.append({'orderId': sell_order['orderId'], 'price': sell_price, 'side': 'SELL', 'type': sell_order['type']})

        elif mode == 'short':
            # Short mode: grid created below the market price
            for level in range(1, grid_levels + 1):
                sell_price = round_to_tick_size(market_price - (level * base_spacing), tick_size)
                buy_price = round_to_tick_size(sell_price - grid_levels * base_spacing, tick_size)

                # Check if a SELL order is already set at the same level (with tolerance)
                if any(abs(float(order['price']) - sell_price) <= tolerance and order['side'] == 'SELL' for order in open_orders):
                    print(f"Sell order already exists at {sell_price} within tolerance range.")
                    continue

                print(f"Placing SELL order at {sell_price}")
                sell_order = place_stop_market_order(symbol, 'SELL', order_quantity, sell_price, api_key, api_secret, working_type)

                # Check if a BUY order is already set at the same level (with tolerance)
                if any(abs(float(order['price']) - buy_price) <= tolerance and order['side'] == 'BUY' for order in open_orders):
                    print(f"Buy order already exists at {buy_price} within tolerance range.")
                    continue

                print(f"Placing BUY order at {buy_price}")
                buy_order = place_limit_order(symbol, 'BUY', order_quantity, buy_price, api_key, api_secret, 'LONG', working_type)

                new_orders.append({'orderId': sell_order['orderId'], 'price': sell_price, 'side': 'SELL', 'type': sell_order['type']})
                new_orders.append({'orderId': buy_order['orderId'], 'price': buy_price, 'side': 'BUY', 'type': buy_order['type']})

    else:
        # Here we handle cases where orders already exist
        if mode == 'neutral':
            # Check that open orders match the grid
            for previous_order in previous_orders:
                matching_order = next((order for order in open_orders if order['orderId'] == previous_order['orderId']), None)

                if matching_order:
                    new_orders.append(previous_order)
                else:
                    side = previous_order['side']
                    new_side = 'SELL' if side == 'BUY' else 'BUY'
                    level = abs(previous_order['price'] - market_price) // base_spacing
                    new_spacing = calculate_variable_grid_spacing(level, grid_levels, base_spacing)
                    price = previous_order['price'] - new_spacing if side == 'SELL' else previous_order['price'] + new_spacing
                    new_order_price = round_to_tick_size(price, tick_size)

                    # Check if an order has already been placed at this level (within tolerance)
                    if any(abs(float(order['price']) - new_order_price) <= tolerance and order['side'] == new_side for order in open_orders):
                        print(f"{new_side} order already exists at {new_order_price} within tolerance range.")
                        continue

                    print(f"Placing new {new_side} order at {new_order_price} to replace filled {side} order")
                    new_order = place_limit_order(symbol, new_side, order_quantity, new_order_price, api_key, api_secret, 'SHORT' if new_side == 'SELL' else 'LONG', working_type)

                    new_orders.append({'orderId': new_order['orderId'], 'price': new_order_price, 'side': new_side})

            # Check if the grid needs to be reset based on price movement

            # Gather sell and buy order prices from open orders
            sell_orders = [float(order['price']) for order in open_orders if order['side'] == 'SELL']
            buy_orders = [float(order['price']) for order in open_orders if order['side'] == 'BUY']

            # Determine boundary prices based on the presence of open orders
            lowest_sell_price = min(sell_orders) if sell_orders else None
            highest_buy_price = max(buy_orders) if buy_orders else None

            # Reset condition based on price movement
            if highest_buy_price is not None and sell_orders == []:
                # Only buy orders are present, so reset if the market price exceeds the highest buy price by base_spacing
                if market_price > highest_buy_price + base_spacing:
                    print("Price exceeded upper threshold for buy orders. Resetting grid.")
                    reset_grid(symbol, api_key, api_secret)
                    return
            elif lowest_sell_price is not None and buy_orders == []:
                # Only sell orders are present, so reset if the market price falls below the lowest sell price by base_spacing
                if market_price < lowest_sell_price - base_spacing:
                    print("Price fell below lower threshold for sell orders. Resetting grid.")
                    reset_grid(symbol, api_key, api_secret)
                    return

        elif mode == 'long':

            # Check if the lowest stop-market BUY order is too far from the market price
            buy_orders = [order for order in open_orders if order['side'] == 'BUY']
            print(f"Buy orders found: {buy_orders}")
            if buy_orders:
                # Use the stopPrice field instead of price
                lowest_buy_order = min(buy_orders, key=lambda x: float(x['stopPrice']))
                print(f"Lowest buy stop-price: {lowest_buy_order['stopPrice']}, Market price: {market_price}, Base spacing: {base_spacing}")

                # If the lowest buy stop-price is too far from the market price, reset the grid
                if float(lowest_buy_order['stopPrice']) - float(market_price) > 2 * base_spacing:
                    print("Lowest buy order is too far from the market price, resetting the grid...")
                    reset_grid(symbol, api_key, api_secret)
                    return  # Stop here and return in the next loop to set new orders
            else:
                print("No BUY orders to evaluate for grid reset.")

            for previous_order in previous_orders:
                print(f"Previous order - ID: {previous_order['orderId']}, Price: {previous_order['price']}")
                matching_order = next((order for order in open_orders if order['orderId'] == previous_order['orderId']), None)

                if matching_order:
                    print(f"Matching order found: {matching_order}")
                    new_orders.append(previous_order)
                else:
                    side = previous_order['side']
                    if side == 'BUY':
                        # If a BUY order is filled, set a STOP-LOSS sell order below
                        new_side = 'SELL'
                        new_order_price = previous_order['price'] - base_spacing  # Stop-loss sell order below
                    elif side == 'SELL':
                        # If a SELL order is filled, place a new buy order above
                        new_side = 'BUY'
                        new_order_price = previous_order['price'] + base_spacing  # Buy order above sell order

                    new_order_price = round_to_tick_size(new_order_price, tick_size)

                    # Check if there is an existing order at the same price level within tolerance
                    if any(abs(float(order['price']) - new_order_price) <= tolerance and order['side'] == new_side for order in open_orders):
                        print(f"{new_side} order already exists at {new_order_price} within tolerance range.")
                        continue

                    # Use set_long_order_logic function to place the new order
                    print(f"Placing new {new_side} order at {new_order_price} to replace filled {side} order")
                    new_order, new_type = set_long_order_logic(
                        symbol,
                        new_side,
                        order_quantity,
                        new_order_price,
                        market_price,
                        api_key,
                        api_secret,
                        previous_order,
                        working_type
                    )

                    # Add new order to the list
                    new_orders.append({
                        'orderId': new_order['orderId'],
                        'price': new_order_price,
                        'side': new_side,
                        'type': new_type
                    })

            # Check if the highest sell order has been filled, in which case the grid is reset
            sell_orders = [order for order in previous_orders if order['side'] == 'SELL']

            if sell_orders:  # Ensure there are sell orders present
                highest_sell_order = max(sell_orders, key=lambda x: x['price'])

                # If the highest sell order is no longer in open orders, it has been filled
                if not any(order['orderId'] == highest_sell_order['orderId'] for order in open_orders):
                    print("Highest sell order filled, resetting the grid...")
                    reset_grid(symbol, api_key, api_secret)
                else:
                    print("Highest sell order is still open, no need to reset the grid.")
            else:
                print("No SELL orders found, skipping grid reset.")

        elif mode == 'short':

            # Check if the highest stop-market SELL order is too far from the market price
            sell_orders = [order for order in open_orders if order['side'] == 'SELL']
            print(f"Sell orders found: {sell_orders}")
            if sell_orders:
                # Use the stopPrice field instead of price
                highest_sell_order = max(sell_orders, key=lambda x: float(x['stopPrice']))
                print(f"Highest sell stop-price: {highest_sell_order['stopPrice']}, Market price: {market_price}, Base spacing: {base_spacing}")

                # If the highest sell stop-price is too far from the market price, reset the grid
                if float(market_price) - float(highest_sell_order['stopPrice']) > 2 * base_spacing:
                    print("Highest sell order is too far from the market price, resetting the grid...")
                    reset_grid(symbol, api_key, api_secret)
                    return  # Stop here and return in the next loop to set new orders
            else:
                print("No SELL orders to evaluate for grid reset.")

            for previous_order in previous_orders:
                print(f"Previous order - ID: {previous_order['orderId']}, Price: {previous_order['price']}")
                matching_order = next((order for order in open_orders if order['orderId'] == previous_order['orderId']), None)

                if matching_order:
                    print(f"Matching order found: {matching_order}")
                    new_orders.append(previous_order)
                else:
                    side = previous_order['side']
                    # If a SELL order is filled, create a STOP-LOSS order (BUY) above
                    if side == 'SELL':
                        new_side = 'BUY'
                        new_order_price = previous_order['price'] + base_spacing
                    # If a BUY order is filled, create a SELL order below it
                    elif side == 'BUY':
                        new_side = 'SELL'
                        new_order_price = previous_order['price'] - base_spacing

                    new_order_price = round_to_tick_size(new_order_price, tick_size)

                    # Check if there is an existing order at the same price level and side
                    if any(abs(float(order['price']) - new_order_price) <= tolerance and order['side'] == new_side for order in open_orders):
                        print(f"{new_side} order already exists at {new_order_price} within tolerance range.")
                        continue

                    print(f"Placing new {new_side} order at {new_order_price} to replace filled {side} order")

                    # Use set_short_order_logic function to place the order
                    new_order, new_type = set_short_order_logic(
                        symbol,
                        new_side,
                        order_quantity,
                        new_order_price,
                        market_price,
                        api_key,
                        api_secret,
                        previous_order,
                        working_type
                    )

                    new_orders.append({
                        'orderId': new_order['orderId'],
                        'price': new_order_price,
                        'side': new_side,
                        'type': new_type
                    })

            # Check if the lowest buy order has been filled, in which case the grid is reset
            buy_orders = [order for order in previous_orders if order['side'] == 'BUY']

            if buy_orders:  # Ensure there are buy orders present
                lowest_buy_order = min(buy_orders, key=lambda x: x['price'])

                # If the lowest buy order is no longer in open orders, it has been filled
                if not any(order['orderId'] == lowest_buy_order['orderId'] for order in open_orders):
                    print("Lowest buy order filled, resetting the grid...")
                    reset_grid(symbol, api_key, api_secret)
                else:
                    print("Lowest buy order is still open, no need to reset the grid.")
            else:
                print("No BUY orders found, skipping grid reset.")

    save_open_orders_to_file(symbol, new_orders)

def set_long_order_logic(symbol, new_side, order_quantity, new_order_price, market_price, api_key, api_secret, previous_order, working_type):
    """
    Sets the logic for a new order in the long version of the grid bot.
    The logic is based on the previous order's type and the market price, using the determine_order_type function.

    Args:
        symbol (str): Trading symbol.
        new_side (str): BUY or SELL.
        order_quantity (float): Order quantity.
        new_order_price (float): Price of the new order.
        market_price (float): Current market price.
        api_key (str): API key.
        api_secret (str): API secret.
        previous_order (dict): Previously set order.
        working_type (str): 'CONTRACT_PRICE' or 'MARK_PRICE'.

    Returns:
        new_order (dict): Details of the set order.
        new_type (str): Type of the set order ('LIMIT' or 'STOP-MARKET').
    """

    # Determine the new order type using the determine_order_type function
    order_info = determine_order_type_long(market_price, new_order_price, new_side)

    # Retrieve the specified order type and price
    new_type = order_info['order_type']
    determined_price = order_info['price']

    # Check the side of the new order (BUY or SELL) and set the correct order type
    if new_type == 'LIMIT':
        # Set a LIMIT order
        new_order = place_limit_order(symbol, new_side, order_quantity, determined_price, api_key, api_secret, 'LONG' if new_side == 'BUY' else 'SHORT', working_type)
    else:
        # Set a STOP-MARKET order
        new_order = place_stop_market_order(symbol, new_side, order_quantity, determined_price, api_key, api_secret, working_type)

    return new_order, new_type

def set_short_order_logic(symbol, new_side, order_quantity, new_order_price, market_price, api_key, api_secret, previous_order, working_type):
    """
    Sets the logic for a new order in the short version of the grid bot.
    The logic is based on the previous order's type and the market price, using the determine_order_type function.

    Args:
        symbol (str): Trading symbol.
        new_side (str): BUY or SELL.
        order_quantity (float): Order quantity.
        new_order_price (float): Price of the new order.
        market_price (float): Current market price.
        api_key (str): API key.
        api_secret (str): API secret.
        previous_order (dict): Previously set order.
        working_type (str): 'CONTRACT_PRICE' or 'MARK_PRICE'.

    Returns:
        new_order (dict): Details of the set order.
        new_type (str): Type of the set order ('LIMIT' or 'STOP-MARKET').
    """

    # Determine the new order type using the determine_order_type function
    order_info = determine_order_type_short(market_price, new_order_price, new_side)

    # Retrieve the specified order type and price
    new_type = order_info['order_type']
    determined_price = order_info['price']

    # Check the side of the new order (BUY or SELL) and set the correct order type
    if new_type == 'LIMIT':
        # Set a LIMIT order
        new_order = place_limit_order(symbol, new_side, order_quantity, determined_price, api_key, api_secret, 'SHORT' if new_side == 'SELL' else 'LONG', working_type)
    else:
        # Set a STOP-MARKET order
        new_order = place_stop_market_order(symbol, new_side, order_quantity, determined_price, api_key, api_secret, working_type)

    return new_order, new_type

def determine_order_type_long(market_price, previous_order_price, direction):
    """
    Determines the type of a new order (stop-market or limit) based on market price,
    the previous order price, and the direction (BUY/SELL).

    Args:
    market_price (float): Current market price.
    previous_order_price (float): Price of the previous order.
    direction (str): "BUY" or "SELL".

    Returns:
    dict: Contains the order type ("STOP-MARKET" or "LIMIT") and price.
    """

    # If it's a BUY order
    if direction == "BUY":
        if market_price > previous_order_price:
            # Market price is higher -> LIMIT BUY
            return {"order_type": "LIMIT", "price": previous_order_price}
        else:
            # Market price is lower -> STOP-MARKET BUY
            return {"order_type": "STOP-MARKET", "price": previous_order_price}

    # If it's a SELL order
    elif direction == "SELL":
        if market_price > previous_order_price:
            # Market price is higher -> STOP-MARKET SELL
            return {"order_type": "STOP-MARKET", "price": previous_order_price}
        else:
            # Market price is lower -> LIMIT SELL
            return {"order_type": "LIMIT", "price": previous_order_price}

    # If the given direction is neither BUY nor SELL
    else:
        raise ValueError("Invalid direction. Must be 'BUY' or 'SELL'.")

def determine_order_type_short(market_price, previous_order_price, direction):
    """
    Determines the type of a new order (stop-market or limit) using short-bot logic,
    based on market price, the previous order price, and the direction (BUY/SELL).

    Args:
    market_price (float): Current market price.
    previous_order_price (float): Price of the previous order.
    direction (str): "BUY" or "SELL".

    Returns:
    dict: Contains the order type ("STOP-MARKET" or "LIMIT") and price.
    """

    # If it's a SELL order in the short bot
    if direction == "SELL":
        if market_price < previous_order_price:
            # Market price is lower -> LIMIT SELL
            return {"order_type": "LIMIT", "price": previous_order_price}
        else:
            # Market price is higher -> STOP-MARKET SELL
            return {"order_type": "STOP-MARKET", "price": previous_order_price}

    # If it's a BUY order in the short bot
    elif direction == "BUY":
        if market_price < previous_order_price:
            # Market price is lower -> STOP-MARKET BUY
            return {"order_type": "STOP-MARKET", "price": previous_order_price}
        else:
            # Market price is higher -> LIMIT BUY
            return {"order_type": "LIMIT", "price": previous_order_price}

    # If the given direction is neither BUY nor SELL
    else:
        raise ValueError("Invalid direction. Must be 'BUY' or 'SELL'.")

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
        return response_data

    except Exception as e:
        print(f"Error placing limit order: {e}")
        logger.error(f"Error placing limit order: {e}")
        handle_binance_error({"code": "unknown", "msg": str(e)}, symbol, api_key, api_secret)

def place_stop_market_order(symbol, side, quantity, stop_price, api_key, api_secret, working_type):
    endpoint = '/fapi/v1/order'
    timestamp = int(time.time() * 1000)
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'STOP_MARKET',
        'quantity': round(quantity, 3),
        'stopPrice': round(stop_price, 7),  # Price level triggering the stop-market order
        'timestamp': timestamp,
        'workingType': working_type  # "CONTRACT_PRICE" or "MARK_PRICE"
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
        return response_data

    except Exception as e:
        print(f"Error placing stop-market order: {e}")
        logger.error(f"Error placing stop-market order: {e}")
        handle_binance_error({"code": "unknown", "msg": str(e)}, symbol, api_key, api_secret)

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
            return

        for position in positions:
            if position['positionAmt'] != 0:  # Check if there are open positions
                if float(position['positionAmt']) > 0:  # If the position is long
                    close_side = "SELL"
                else:  # If the position is short
                    close_side = "BUY"

                # Close the position using a market order
                close_position(symbol, close_side, abs(float(position['positionAmt'])), api_key, api_secret)

    except Exception as e:
        print(f"Error closing positions: {e}")

def close_position(symbol, side, quantity, api_key, api_secret):
    """
    Places a market order to close the position.

    Args:
        symbol (str): Trading symbol, such as "BTCUSDT".
        side (str): "BUY" or "SELL" side to close the position.
        quantity (float): Amount to close.
        api_key (str): API key.
        api_secret (str): API secret.
    """
    try:
        order = place_market_order(symbol, side, quantity, api_key, api_secret)
        print(f"Placed market order to close position: {order}")
    except Exception as e:
        print(f"Error placing market order: {e}")

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
    # Close open positions
    close_open_positions(symbol, api_key, api_secret)

    # Cancel all buy and sell orders
    cancel_existing_orders(symbol, api_key, api_secret)

    # Clear the JSON file
    clear_orders_file(f"{symbol}_open_orders.json")  # Use a symbol-specific file

    # Notify that the grid has been reset
    print("Grid reset, bot will now place new orders in the next loop.")

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

    # Handle different error codes
    if error_code == -1021:  # Timestamp error
        print("Timestamp issue detected. Synchronizing time and resetting grid...")
        time.sleep(2)  # Wait a moment before synchronizing time
        reset_grid(symbol, api_key, api_secret)

    elif error_code == -2019:  # Insufficient margin
        print("Insufficient margin detected. Closing positions and resetting grid...")
        close_open_positions(symbol, api_key, api_secret)
        reset_grid(symbol, api_key, api_secret)

    elif error_code == 400:  # Bad Request
        print("Bad Request error detected. Checking symbol validity and resetting grid if necessary...")
        close_open_positions(symbol, api_key, api_secret)
        reset_grid(symbol, api_key, api_secret)

    # Additional common error codes can be added here
    else:
        print(f"Unhandled error ({error_code}): {error_message}. Closing positions and resetting grid as a precaution.")
        close_open_positions(symbol, api_key, api_secret)
        reset_grid(symbol, api_key, api_secret)
