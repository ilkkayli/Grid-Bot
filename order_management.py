import time
import json
import os
import sys
from binance_futures import get_market_price, cancel_existing_orders, get_open_orders, get_open_positions, get_tick_size, place_market_order, place_limit_order, place_stop_market_order, close_open_positions, close_position
from logging_config import logger

# Fetch settings
def load_config(file_path='config.json'):
    with open(file_path, 'r') as file:
        return json.load(file)

config = load_config()
api_credentials = config.get("api_credentials", {})
api_key = api_credentials.get("api_key")
api_secret = api_credentials.get("api_secret")
base_url = api_credentials.get("base_url")

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

def round_to_tick_size(price, tick_size, offset=0.000001):
    """Rounds the price to the nearest tick size with a small offset to avoid repeated prices."""
    return round((price + offset) / tick_size) * tick_size

def calculate_variable_grid_spacing(level, base_spacing, progression=1.1, max_spacing=None):
    """Lasketaan progressiivinen ruudukon väli käyttäen kerrointa, rajoitettu max_spacing-arvoon."""
    spacing = base_spacing * (progression ** (level - 1))
    if max_spacing is not None:
        return min(spacing, max_spacing)
    return spacing

# Modified handle_grid_orders function for neutral, long, and short modes
def handle_grid_orders(symbol, grid_levels, order_quantity, working_type, leverage, margin_type, quantity_multiplier, mode, spacing_percentage, progressive_grid):
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
    if open_orders is None:
        print("Error detected in open orders response.")
        reset_grid(symbol, api_key, api_secret)  # Reset grid on error
    else:
        # print(f"Current open orders: {open_orders}") # This is for debugging
        print("Open orders retrieved.")

    # Load previous open orders from file
    previous_orders = load_open_orders_from_file(symbol)

    new_orders = []

    calculate_spacing = (
    lambda level: calculate_variable_grid_spacing(level, base_spacing)
    if progressive_grid
    else lambda level: base_spacing
    )

    if not open_orders:
        # If there are no open orders, create new grid orders depending on mode
        print(f"Mode: {mode}")

        if mode == 'neutral':
            # Neutral mode: orders on both sides of the market price
            print(f"Grid progression:  {progressive_grid}")
            for level in range(1, grid_levels + 1):
                print(f"Current Level: {level}")

                if progressive_grid == True:
                    # Calculate variable spacing if progressive_grid flag is True
                    buy_spacing = calculate_spacing(level)
                    sell_spacing = calculate_spacing(level)
                    print(f"Variable Spacing for BUY: {buy_spacing}, SELL: {sell_spacing}")
                else:
                    # Use fixed spacing if progressive_grid flag is False
                    buy_spacing = sell_spacing = base_spacing
                    print(f"Fixed Spacing: {base_spacing}")

                buy_price = round_to_tick_size(market_price - (level * buy_spacing), tick_size)
                sell_price = round_to_tick_size(market_price + (level * sell_spacing), tick_size)

                print(f"Market Price: {market_price}, Buy Price: {buy_price}, Sell Price: {sell_price}")
                print(f"TICK SIZE: {tick_size}")

                # Placing BUY orders
                print(f"Placing BUY order at {buy_price}")
                buy_order = place_limit_order(symbol, 'BUY', order_quantity, buy_price, api_key, api_secret, 'LONG', working_type)

                # Check if buy order was successfully placed
                if buy_order is None:
                    print(f"Error placing BUY order at {buy_price}. Skipping to the next iteration.")
                    break  # Stop processing this symbol's grid and exit the loop
                elif 'orderId' in buy_order:
                    new_orders.append({'orderId': buy_order['orderId'], 'price': buy_price, 'side': 'BUY'})
                    print(f"BUY Order Placed Successfully: {buy_order['orderId']}")
                else:
                    print(f"Error placing BUY order at {buy_price}. Unexpected API response: {buy_order}")
                    break  # Stop processing this symbol's grid due to an unexpected response

                # Placing SELL orders
                print(f"Placing SELL order at {sell_price}")
                sell_order = place_limit_order(symbol, 'SELL', order_quantity, sell_price, api_key, api_secret, 'SHORT', working_type)

                # Check if SELL order was successfully placed
                if sell_order is None:
                    print(f"Error placing SELL order at {sell_price}. Stopping grid creation for {symbol}.")
                    break  # Stop processing this symbol's grid
                elif 'orderId' in sell_order:
                    new_orders.append({'orderId': sell_order['orderId'], 'price': sell_price, 'side': 'SELL'})
                    print(f"SELL Order Placed Successfully: {sell_order['orderId']}")
                else:
                    print(f"Error placing SELL order at {sell_price}. Unexpected API response: {sell_order}")
                    break  # Stop processing this symbol's grid due to an unexpected response

        elif mode == 'long':
            # Long mode: grid created above the market price
            for level in range(1, grid_levels + 1):
                buy_price = round_to_tick_size(market_price + (level * base_spacing), tick_size)
                sell_price = round_to_tick_size(buy_price + grid_levels * base_spacing, tick_size)

                # Check if a BUY order is already set at the same level (with tolerance)
                if open_orders is not None and any(abs(float(order['price']) - buy_price) <= tolerance and order['side'] == 'BUY' for order in open_orders):
                    print(f"Buy order already exists at {buy_price} within tolerance range.")
                    continue

                print(f"Placing BUY order at {buy_price}")
                buy_order = place_stop_market_order(symbol, 'BUY', order_quantity, buy_price, api_key, api_secret, working_type)

                # Check if buy order was successfully placed
                if buy_order is None:
                    print(f"Error placing BUY order at {buy_price}. Skipping to the next iteration.")
                    break  # Stop processing this symbol's grid and exit the loop
                elif 'orderId' in buy_order:
                    new_orders.append({'orderId': buy_order['orderId'], 'price': buy_price, 'side': 'BUY', 'type': buy_order['type']})
                else:
                    print(f"Error placing BUY order at {buy_price}")
                    break  # Stop processing this symbol's grid due to an unexpected response

                # Check if a SELL order is already set at the same level (with tolerance)
                if any(abs(float(order['price']) - sell_price) <= tolerance and order['side'] == 'SELL' for order in open_orders):
                    print(f"Sell order already exists at {sell_price} within tolerance range.")
                    continue

                print(f"Placing SELL order at {sell_price}")
                sell_order = place_limit_order(symbol, 'SELL', order_quantity, sell_price, api_key, api_secret, 'SHORT', working_type)

                # Check if sell order was successfully placed
                if sell_order is None:
                    print(f"Error placing SELL order at {sell_price}. Stopping grid creation for {symbol}.")
                    break  # Stop processing this symbol's grid
                elif 'orderId' in sell_order:
                    new_orders.append({'orderId': sell_order['orderId'], 'price': sell_price, 'side': 'SELL', 'type': sell_order['type']})
                else:
                    print(f"Error placing SELL order at {sell_price}")
                    break

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

                # Check if sell order was successfully placed
                if sell_order is None:
                    print(f"Error placing SELL order at {sell_price}. Stopping grid creation for {symbol}.")
                    break  # Stop processing this symbol's grid
                elif 'orderId' in sell_order:
                    new_orders.append({'orderId': sell_order['orderId'], 'price': sell_price, 'side': 'SELL', 'type': sell_order['type']})
                else:
                    print(f"Error placing SELL order at {sell_price}")
                    break

                # Check if a BUY order is already set at the same level (with tolerance)
                if any(abs(float(order['price']) - buy_price) <= tolerance and order['side'] == 'BUY' for order in open_orders):
                    print(f"Buy order already exists at {buy_price} within tolerance range.")
                    continue

                print(f"Placing BUY order at {buy_price}")
                buy_order = place_limit_order(symbol, 'BUY', order_quantity, buy_price, api_key, api_secret, 'LONG', working_type)

                # Check if buy order was successfully placed
                if buy_order is None:
                    print(f"Error placing BUY order at {buy_price}. Skipping to the next iteration.")
                    break  # Stop processing this symbol's grid and exit the loop
                elif 'orderId' in buy_order:
                    new_orders.append({'orderId': buy_order['orderId'], 'price': buy_price, 'side': 'BUY', 'type': buy_order['type']})
                else:
                    print(f"Error placing BUY order at {buy_price}")
                    break

    else:
        # Here we handle cases where orders already exist
        if mode == 'neutral':
            # Check that open orders match the grid
            for previous_order in previous_orders:
                matching_order = next((order for order in open_orders if order['orderId'] == previous_order['orderId']), None)

                if matching_order:
                    # Order still exists, add it to new orders
                    new_orders.append(previous_order)
                else:
                    # Order filled, calculate replacement order
                    side = previous_order['side']
                    new_side = 'SELL' if side == 'BUY' else 'BUY'

                    # Calculate the level of the filled order relative to market price
                    level = abs(previous_order['price'] - market_price) // base_spacing

                    # Calculate spacing for the replacement order
                    if progressive_grid:
                        new_spacing = calculate_variable_grid_spacing(level, base_spacing)
                    else:
                        new_spacing = base_spacing

                    price = (
                        previous_order['price'] - new_spacing if side == 'SELL'
                        else previous_order['price'] + new_spacing
                    )
                    new_order_price = round_to_tick_size(price, tick_size)

                    # Check if an order already exists at this level within tolerance
                    if any(
                        abs(float(order['price']) - new_order_price) <= tolerance
                        and order['side'] == new_side
                        for order in open_orders
                    ):
                        print(f"{new_side} order already exists at {new_order_price} within tolerance range.")
                        continue

                    # Place new order to replace the filled order
                    print(f"Placing new {new_side} order at {new_order_price} to replace filled {side} order")
                    new_order = place_limit_order(
                        symbol, new_side, order_quantity, new_order_price, api_key, api_secret,
                        'SHORT' if new_side == 'SELL' else 'LONG', working_type
                    )

                    # Check if the new order was successfully placed
                    if new_order is None:
                        print(f"Error placing new {new_side} order at {new_order_price}. Skipping to the next iteration.")
                        break  # Stop processing this symbol's grid and exit the loop
                    elif 'orderId' in new_order:
                        new_orders.append({'orderId': new_order['orderId'], 'price': new_order_price, 'side': new_side})
                    else:
                        print(f"Error placing new order at {new_order_price}")
                        break

            # Check if the grid needs to be reset when price exceeds a certain threshold
            sell_orders = [float(order['price']) for order in open_orders if order['side'] == 'SELL']
            buy_orders = [float(order['price']) for order in open_orders if order['side'] == 'BUY']

            # Determine boundary prices
            lowest_sell_price = min(sell_orders) if sell_orders else None
            highest_buy_price = max(buy_orders) if buy_orders else None

            # Check stop-loss threshold
            if (sell_orders and not buy_orders) or (buy_orders and not sell_orders):
                if lowest_sell_price is not None or highest_buy_price is not None:
                    print(f"Market price: {market_price}, Lowest sell: {lowest_sell_price}, Highest buy: {highest_buy_price}, Base spacing: {base_spacing}")

                    if (lowest_sell_price is not None and market_price < lowest_sell_price - base_spacing * 1.5 - tolerance) or \
                       (highest_buy_price is not None and market_price > highest_buy_price + base_spacing * 1.5 + tolerance):
                        print("Price exceeded stop-loss threshold with tolerance. Resetting grid.")
                        reset_grid(symbol, api_key, api_secret)
                        return
                elif not sell_orders and not buy_orders:
                    print("No open orders found. Skipping grid reset check.")
                else:
                    print("Boundary prices not properly defined. No grid reset performed.")


        elif mode == 'long':

            # Check if the lowest stop-market BUY order is too far from the market price
            buy_orders = [order for order in open_orders if order['side'] == 'BUY']
            print("Open orders found.")
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
                # print(f"Previous order - ID: {previous_order['orderId']}, Price: {previous_order['price']}") # Uncomment for debugging
                matching_order = next((order for order in open_orders if order['orderId'] == previous_order['orderId']), None)

                if matching_order:
                    # print(f"Matching order found: {matching_order}") # # Uncomment for debugging
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
            print("Open orders found.")
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
                # print(f"Previous order - ID: {previous_order['orderId']}, Price: {previous_order['price']}") # Uncomment for debugging
                matching_order = next((order for order in open_orders if order['orderId'] == previous_order['orderId']), None)

                if matching_order:
                    #print(f"Matching order found: {matching_order}") # Uncomment for debugging
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

    # Fetch all symbols from config.json
    crypto_settings = config.get("crypto_settings", {})
    symbols = [settings["symbol"] for settings in crypto_settings.values()]

    # Handle different error codes
    if error_code == -1021:  # Timestamp error
        print("Timestamp issue detected. Synchronizing time and resetting grid...")
        time.sleep(2)  # Wait a moment before synchronizing time
        reset_grid(symbol, api_key, api_secret)
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
        print("Server is currently overloaded with other requests. Please try again in a few minutes.")
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

def log_and_print(message):
    print(message)
    logger.info(message)
