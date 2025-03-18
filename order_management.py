import json
import os
from binance_futures import get_open_orders, get_tick_size,place_limit_order, reset_grid, get_open_positions, log_and_print, get_step_size, calculate_dynamic_base_spacing, get_market_price, open_trailing_stop_order, place_market_order
from file_utils import load_json
#from binance_websockets import get_latest_price

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

spacing_cache = {}

def handle_grid_orders(symbol, grid_levels, order_quantity, working_type, leverage, progressive_grid, grid_progression, use_websocket):
    # Retrieve current market price
    if use_websocket:
        market_price = get_latest_price(symbol)
        print(f"WebSocket price retrieved {symbol} {market_price}")
        if market_price is None:
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

    # Retrieve step size for the trading pair
    step_size = get_step_size(symbol, api_key, api_secret)
    if step_size is None:
        print("Error: Could not retrieve step size.")
        return

    # Fetch current open orders from Binance
    open_orders = get_open_orders(symbol, api_key, api_secret)
    if open_orders is None:
        message = f"{symbol} Error detected in open orders response."
        log_and_print(message)
        return
    else:
        print("Open orders retrieved.")

    # Load previous open orders from file
    previous_orders = load_open_orders_from_file(symbol)

    new_orders = []
    limit_orders = {}

    # Retrieve or calculate base_spacing from cache
    if symbol not in spacing_cache:
        base_spacing = calculate_dynamic_base_spacing(symbol, api_key, api_secret)
        if base_spacing is None:
            print(f"Error: Could not calculate base spacing for {symbol}.")
            return
        spacing_cache[symbol] = base_spacing
        print(f"Base grid spacing calculated and cached: {base_spacing}")
    else:
        base_spacing = spacing_cache[symbol]
        print(f"Base grid spacing retrieved from cache: {base_spacing}")

    # Define price tolerance (5% of base spacing, adjustable)
    tolerance = base_spacing * 0.05

    if not open_orders:
        # Create new grid orders
        print(f"Grid progression: {progressive_grid}")
        for level in range(1, grid_levels + 1):
            if progressive_grid:
                buy_spacing = calculate_variable_grid_spacing(level, base_spacing, grid_progression)
                sell_spacing = calculate_variable_grid_spacing(level, base_spacing, grid_progression)
                print(f"Variable Spacing for BUY: {buy_spacing}, SELL: {sell_spacing}")
                order_quantity_adjusted = round_to_step_size(order_quantity * (grid_progression ** (level - 1)), step_size)
                print(f"Adjusted Order Quantity: {order_quantity_adjusted}")
            else:
                buy_spacing = sell_spacing = base_spacing
                order_quantity_adjusted = round_to_step_size(order_quantity, step_size)
                print(f"Fixed Spacing: {base_spacing}")
                print(f"Fixed Order Quantity: {order_quantity_adjusted}")

            buy_price = round_to_tick_size(market_price - (level * buy_spacing), tick_size)
            sell_price = round_to_tick_size(market_price + (level * sell_spacing), tick_size)

            print(f"Market Price: {market_price}, Buy Price: {buy_price}, Sell Price: {sell_price}")

            # Placing BUY orders
            print(f"Placing BUY order at {buy_price}")
            buy_order = place_limit_order(
                symbol, 'BUY', order_quantity_adjusted, buy_price, api_key, api_secret, 'LONG', working_type
            )
            if buy_order is None:
                print(f"Error placing BUY order at {buy_price}. Skipping to the next iteration.")
                break
            elif 'orderId' in buy_order:
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
                break

            # Placing SELL orders
            print(f"Placing SELL order at {sell_price}")
            sell_order = place_limit_order(
                symbol, 'SELL', order_quantity_adjusted, sell_price, api_key, api_secret, 'SHORT', working_type
            )
            if sell_order is None:
                print(f"Error placing SELL order at {sell_price}. Stopping grid creation for {symbol}.")
                break
            elif 'orderId' in sell_order:
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
                break

        # Tallenna uudet tilaukset tiedostoon (base_spacing pysyy välimuistissa)
        previous_orders = {
            'orders': new_orders,
            'limit_orders': limit_orders
        }
        save_open_orders_to_file(symbol, previous_orders)

    else:
        # Check if the order already exists
        limit_orders = previous_orders.get('limit_orders', {}).copy()

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
                    # Tyhjennä välimuisti resetoinnin yhteydessä
                    if symbol in spacing_cache:
                        del spacing_cache[symbol]
                    return

                # Order filled, calculate replacement order
                side = previous_order['side']
                new_side = 'SELL' if side == 'BUY' else 'BUY'

                base_price = float(open_positions[0]['entryPrice'])
                level = round(abs(previous_order['price'] - market_price) / base_spacing)

                new_spacing = calculate_variable_grid_spacing(level, base_spacing, grid_progression) if progressive_grid else base_spacing
                price = (
                    base_price - new_spacing if new_side == 'BUY'
                    else base_price + new_spacing
                )
                new_order_price = round_to_tick_size(price, tick_size)

                if new_side == 'BUY' and new_order_price > base_price:
                    new_order_price = round_to_tick_size(base_price - (0.002 * base_price), tick_size)
                elif new_side == 'SELL' and new_order_price < base_price:
                    new_order_price = round_to_tick_size(base_price + (0.002 * base_price), tick_size)

                if any(
                    abs(float(order['price']) - new_order_price) <= base_spacing * tolerance
                    and order['side'] == new_side
                    for order in open_orders
                ):
                    message = f"{new_side} order already exists at {new_order_price} within tolerance range. Skipping order replacement."
                    log_and_print(message)
                    continue

                print(f"Placing new {new_side} order at {new_order_price} with quantity {previous_order['quantity']} "
                      f"to replace filled {side} order")
                new_order = place_limit_order(
                    symbol, new_side, previous_order['quantity'], new_order_price, api_key, api_secret,
                    'SHORT' if new_side == 'SELL' else 'LONG', working_type
                )

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
                    message = f"{symbol} Placed a new replacement order {new_side} at {new_order_price}."
                    log_and_print(message)
                else:
                    print(f"Error placing new order at {new_order_price}")
                    break

        # Tallenna päivitetyt tilaukset
        previous_orders = {
            'orders': new_orders,
            'limit_orders': limit_orders
        }
        save_open_orders_to_file(symbol, previous_orders)
        
def handle_breakout_strategy(symbol, trigger_result, order_quantity, trailing_stop_rate, api_key, api_secret, working_type, active_breakouts):
    """
    Handle breakout strategy: open market order and set trailing stop if conditions met.

    Args:
        symbol (str): Trading pair (e.g., "BTCUSDC").
        trigger_result (dict): Result from calculate_bot_trigger (contains 'strategy').
        order_quantity (float): Quantity for market order.
        trailing_stop_rate (float): Trailing stop callback rate (e.g., 1.0 for 1%).
        api_key (str): Binance API key.
        api_secret (str): Binance API secret.
        working_type (str): Order working type (e.g., "CONTRACT_PRICE").
        active_breakouts (dict): Dictionary tracking active breakout positions.
    """
    if trigger_result['strategy'] not in ['breakout_long', 'breakout_short']:
        return

    # Tarkista, onko breakout aktiivinen ja positio yhä auki
    if symbol in active_breakouts:
        open_positions = get_open_positions(symbol, api_key, api_secret)
        if not open_positions:
            log_and_print(f"Position closed for {symbol}. Removing from active_breakouts.")
            del active_breakouts[symbol]
        else:
            log_and_print(f"Breakout already active for {symbol}, skipping new position.")
            return

    # Breakout-long
    if trigger_result['strategy'] == 'breakout_long':
        print(f"Initiating long position for {symbol}.")
        market_order = place_market_order(symbol, "BUY", order_quantity, api_key, api_secret)
        if market_order:
            log_and_print(f"{symbol} Breakout long opened: {market_order}.")
            trailing_stop = open_trailing_stop_order(
                symbol=symbol, side="SELL", quantity=order_quantity,
                callback_rate=trailing_stop_rate, api_key=api_key, api_secret=api_secret, working_type=working_type
            )
            if trailing_stop:
                log_and_print(f"{symbol} Trailing stop set for long: {trailing_stop}.")
                active_breakouts[symbol] = 'long'
            else:
                log_and_print(f"Failed to set trailing stop for {symbol}. Closing position.")
                place_market_order(symbol, "SELL", order_quantity, api_key, api_secret)
        else:
            log_and_print(f"Failed to open long position for {symbol}.")

    # Breakout-short
    elif trigger_result['strategy'] == 'breakout_short':
        print(f"Initiating short position for {symbol}.")
        market_order = place_market_order(symbol, "SELL", order_quantity, api_key, api_secret)
        if market_order:
            log_and_print(f"{symbol} Short position opened: {market_order}")
            trailing_stop = open_trailing_stop_order(
                symbol=symbol, side="BUY", quantity=order_quantity,
                callback_rate=trailing_stop_rate, api_key=api_key, api_secret=api_secret, working_type=working_type
            )
            if trailing_stop:
                log_and_print(f"{symbol} Trailing stop set for short: {trailing_stop}")
                active_breakouts[symbol] = 'short'
            else:
                log_and_print(f"Failed to set trailing stop for {symbol}. Closing position.")
                place_market_order(symbol, "BUY", order_quantity, api_key, api_secret)
        else:
            log_and_print(f"Failed to open short position for {symbol}.")
