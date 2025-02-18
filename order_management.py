import json
import os
from binance_futures import get_open_orders, get_tick_size,place_limit_order, reset_grid, get_open_positions, log_and_print, get_step_size, calculate_dynamic_base_spacing, get_market_price
from file_utils import load_json
from binance_websockets import get_latest_price

# Fetch settings
secrets = load_json("secrets.json")
api_key = secrets.get("api_key")
api_secret = secrets.get("api_secret")
base_url = secrets.get("base_url")

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

def round_to_step_size(quantity, step_size, offset=0.000001):
    """Rounds the quantity to the nearest step size with a small offset."""
    return round((quantity + offset) / step_size) * step_size

def calculate_variable_grid_spacing(level, base_spacing, grid_progression, max_spacing=None):
    """Calculate progressive grid spacing using a multiplier, constrained by a max_spacing value."""
    spacing = base_spacing * (grid_progression ** (level - 1))
    if max_spacing is not None:
        return min(spacing, max_spacing)
    return spacing

# Modified handle_grid_orders function for neutral, long, and short modes
def handle_grid_orders(symbol, grid_levels, order_quantity, working_type, leverage, progressive_grid, grid_progression, use_websocket):

    # Retrieve current market price
    if use_websocket:
        market_price = get_latest_price(symbol)
        print(f"WebSocket price retrieved {symbol} {market_price}")
        if market_price is None:  # Fallback to API call if websocket is not respoding
            print(f"WebSocket price unavailable, fetching from API for {symbol}...")
            market_price = get_market_price(symbol, api_key, api_secret)
    else:
        market_price = get_market_price(symbol, api_key, api_secret)

    if market_price is None:
        print(f"Error: Could not retrieve market price for {symbol}.")
        return None

    print(f"Market price for {symbol}: {market_price}")

    # Retrieve tick size for the trading pair
    tick_size = get_tick_size(symbol, api_key, api_secret)
    if tick_size is None:
        print("Error: Could not retrieve tick size.")
        return

    print(f"Tick size: {tick_size}")

    # Retrieve step size for the trading pair
    step_size = get_step_size(symbol, api_key, api_secret)
    if step_size is None:
        print("Error: Could not retrieve step size.")
        return
    print(f"Step size: {step_size}")

    # Calculate base grid_spacing
    base_spacing = calculate_dynamic_base_spacing(symbol, api_key, api_secret)
    print(f"Base grid spacing: {base_spacing}")

    # Define price tolerance (5% of base spacing, adjustable)
    tolerance = base_spacing * 0.05

    # Fetch current open orders from Binance. If any errors occur, the grid will be reset, and open positions will be closed.
    open_orders = get_open_orders(symbol, api_key, api_secret)

    # Check for error indication in the response
    if open_orders is None:
        message = f"{symbol} Error detected in open orders response."
        log_and_print(message)
        return # Abort the loop
    else:
        # print(f"Current open orders: {open_orders}") # This is for debugging
        print("Open orders retrieved.")

    # Load previous open orders from file
    previous_orders = load_open_orders_from_file(symbol)

    new_orders = []
    limit_orders = {}

    if not open_orders:
        # If there are no open orders, create new grid orders
        # Neutral mode: orders on both sides of the market price
        print(f"Grid progression:  {progressive_grid}")
        for level in range(1, grid_levels + 1):

            if progressive_grid == True:
                # Calculate variable spacing if progressive_grid flag is True
                buy_spacing = calculate_variable_grid_spacing(level, base_spacing, grid_progression)
                sell_spacing = calculate_variable_grid_spacing(level, base_spacing, grid_progression)
                print(f"Variable Spacing for BUY: {buy_spacing}, SELL: {sell_spacing}")
                order_quantity_adjusted = round_to_step_size(order_quantity * (grid_progression ** (level - 1)), step_size)
                print(f"Adjusted Order Quantity: {order_quantity_adjusted}")
            else:
                # Use fixed spacing if progressive_grid flag is False
                buy_spacing = sell_spacing = base_spacing
                order_quantity_adjusted = round_to_step_size(order_quantity, step_size)
                print(f"Fixed Spacing: {base_spacing}")
                print(f"Fixed Order Quantity: {order_quantity_adjusted}")

            buy_price = round_to_tick_size(market_price - (level * buy_spacing), tick_size)
            sell_price = round_to_tick_size(market_price + (level * sell_spacing), tick_size)

            print(f"Market Price: {market_price}, Buy Price: {buy_price}, Sell Price: {sell_price}")
            print(f"TICK SIZE: {tick_size}")

            # Placing BUY orders
            print(f"Placing BUY order at {buy_price}")
            buy_order = place_limit_order(
                symbol, 'BUY', order_quantity_adjusted, buy_price, api_key, api_secret, 'LONG', working_type
            )

            # Check if buy order was successfully placed
            if buy_order is None:
                print(f"Error placing BUY order at {buy_price}. Skipping to the next iteration.")
                break  # Stop processing this symbol's grid and exit the loop
            elif 'orderId' in buy_order:
                # Save order details, including quantity
                new_orders.append({
                    'orderId': buy_order['orderId'],
                    'price': buy_price,
                    'side': 'BUY',
                    'quantity': round_to_step_size(order_quantity_adjusted, step_size)
                })
                limit_orders['lowest_buy_order_price'] = buy_price
                print(f"BUY Order Placed Successfully: {buy_order['orderId']}, Quantity: {order_quantity_adjusted}")
            else:
                print(f"Error placing BUY order at {buy_price}. Unexpected API response: {buy_order}")
                break  # Stop processing this symbol's grid due to an unexpected response

            # Placing SELL orders
            print(f"Placing SELL order at {sell_price}")
            sell_order = place_limit_order(
                symbol, 'SELL', order_quantity_adjusted, sell_price, api_key, api_secret, 'SHORT', working_type
            )

            # Check if SELL order was successfully placed
            if sell_order is None:
                print(f"Error placing SELL order at {sell_price}. Stopping grid creation for {symbol}.")
                break  # Stop processing this symbol's grid
            elif 'orderId' in sell_order:
                # Save order details, including quantity
                new_orders.append({
                    'orderId': sell_order['orderId'],
                    'price': sell_price,
                    'side': 'SELL',
                    'quantity': round_to_step_size(order_quantity_adjusted, step_size)
                })
                limit_orders['highest_sell_order_price'] = sell_price
                print(f"SELL Order Placed Successfully: {sell_order['orderId']}, Quantity: {order_quantity_adjusted}")
            else:
                print(f"Error placing SELL order at {sell_price}. Unexpected API response: {sell_order}")
                break  # Stop processing this symbol's grid due to an unexpected response

    else:
        # Check if the order already exists
        # Initialize limit_orders with the values from previous_orders, or use an empty dict if not available
        limit_orders = previous_orders.get('limit_orders', {}).copy()

        # Correct iteration over 'orders' in the dictionary
        for previous_order in previous_orders.get('orders', []):
            matching_order = next((order for order in open_orders if order['orderId'] == previous_order['orderId']), None)

            if matching_order:
                new_orders.append(previous_order)
            else:
                open_positions = get_open_positions(symbol, api_key, api_secret)
                if not open_positions:
                    message = f"{symbol} No open positions detected. Assuming that position is closed. Resetting grid."
                    log_and_print(message)
                    reset_grid(symbol, api_key, api_secret)
                    return

                # Order filled, calculate replacement order
                side = previous_order['side']
                new_side = 'SELL' if side == 'BUY' else 'BUY'

                # Use position entry price as a base point
                base_price = float(open_positions[0]['entryPrice'])

                # Calculate level in the grid
                level = round(abs(previous_order['price'] - market_price) / base_spacing)

                # Calculate spacing progressively or as a fixed value
                new_spacing = calculate_variable_grid_spacing(level, base_spacing, grid_progression) if progressive_grid else base_spacing

                # Determine new order price relative to position price
                price = (
                    base_price - new_spacing if new_side == 'BUY'
                    else base_price + new_spacing
                )
                new_order_price = round_to_tick_size(price, tick_size)

                # Ensure the price does not exceed position entry price on the wrong side
                if new_side == 'BUY' and new_order_price > base_price:
                    new_order_price = round_to_tick_size(base_price - (0.002 * base_price), tick_size)
                elif new_side == 'SELL' and new_order_price < base_price:
                    new_order_price = round_to_tick_size(base_price + (0.002 * base_price), tick_size)

                # Prevent duplicate orders
                if any(
                    abs(float(order['price']) - new_order_price) <= tolerance
                    and order['side'] == new_side
                    for order in open_orders
                ):
                    print(f"{new_side} order already exists at {new_order_price} within tolerance range.")
                    continue

                # Place new order
                print(f"Placing new {new_side} order at {new_order_price} with quantity {previous_order['quantity']} "
                      f"to replace filled {side} order")
                new_order = place_limit_order(
                    symbol, new_side, previous_order['quantity'], new_order_price, api_key, api_secret,
                    'SHORT' if new_side == 'SELL' else 'LONG', working_type
                )

                # Check if the order placement was successful
                if new_order is None:
                    print(f"Error placing new {new_side} order at {new_order_price}. Skipping to the next iteration.")
                    break
                elif 'orderId' in new_order:
                    new_orders.append({
                        'orderId': new_order['orderId'],
                        'price': new_order_price,
                        'side': new_side,
                        'quantity': previous_order['quantity']
                    })
                else:
                    print(f"Error placing new order at {new_order_price}")
                    break

        # Check if the grid needs to be reset when price exceeds a certain threshold
        # Extract the lowest buy and highest sell order price from limit_orders
        lowest_buy_order_price = limit_orders.get('lowest_buy_order_price')
        highest_sell_order_price = limit_orders.get('highest_sell_order_price')

        # Debug
        #print(f"Market price: {market_price}, Lowest Buy Order Price: {lowest_buy_order_price}, Highest Sell Order Price: {highest_sell_order_price}, Base spacing: {base_spacing}")

        # Stop-loss-check
        if lowest_buy_order_price is not None and market_price < lowest_buy_order_price - (base_spacing * 1.5 + tolerance):
            message = f"{symbol} Market price dropped too far below the lowest buy order. Performing stop-loss."
            log_and_print(message)
            reset_grid(symbol, api_key, api_secret)
            return

        if highest_sell_order_price is not None and market_price > highest_sell_order_price + (base_spacing * 1.5 + tolerance):
            message = f"{symbol} Market price rose too far above the highest sell order. Performing stop-loss."
            log_and_print(message)
            reset_grid(symbol, api_key, api_secret)
            return

    # Save updated orders and preserve original limit_orders
    data_to_save = {
        "orders": new_orders,
        "limit_orders": limit_orders
    }
    save_open_orders_to_file(symbol, data_to_save)
