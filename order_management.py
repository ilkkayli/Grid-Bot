import json
import os
from binance_futures import get_open_orders, get_tick_size, place_limit_order, reset_grid, get_open_positions, log_and_print, get_step_size, calculate_dynamic_base_spacing, get_market_price, open_trailing_stop_order, place_market_order, get_bollinger_bands
from file_utils import load_json
# from binance_websockets import get_latest_price

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

def clear_orders_file(symbol=None):
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

def handle_grid_orders(symbol, grid_levels, order_quantity, working_type, leverage, progressive_grid, grid_progression, use_websocket, klines_interval, use_bollinger_bands=True, spacing_percent=1.0):
    # Fetch market price
    if use_websocket:
        market_price = get_latest_price(symbol)
        if market_price is None:
            market_price = get_market_price(symbol, api_key, api_secret)
    else:
        market_price = get_market_price(symbol, api_key, api_secret)

    if market_price is None:
        print(f"Error: Could not retrieve market price for {symbol}.")
        return None

    market_price = float(market_price)

    # Fetch tick/step size
    tick_size = get_tick_size(symbol, api_key, api_secret)
    step_size = get_step_size(symbol, api_key, api_secret)
    if not tick_size or not step_size:
        print("Error: Could not retrieve tick/step size.")
        return

    # Fetch Bollinger Bands data
    if use_bollinger_bands:
        bb_data = get_bollinger_bands(symbol, api_key, api_secret, klines_interval, 20)
        if bb_data is None:
            print(f"Error: Could not fetch Bollinger Bands for {symbol}. Using fallback bounds.")
            upper_band = market_price * 1.05
            lower_band = market_price * 0.95
            bbw = None
            sma = market_price  # Fallback value
        else:
            upper_band = bb_data['upper_band']
            lower_band = bb_data['lower_band']
            bbw = (upper_band - lower_band) / market_price
            sma = (upper_band + lower_band) / 2  # Explicitly calculate SMA
            # Ensure market price is within bands
            if market_price < lower_band:
                print(f"Warning: market_price ({market_price}) is below lower_band ({lower_band}). Adjusting lower_band.")
                lower_band = market_price * 0.95
            if market_price > upper_band:
                print(f"Warning: market_price ({market_price}) is above upper_band ({upper_band}). Adjusting upper_band.")
                upper_band = market_price * 1.05
    else:
        bbw = None
        sma = market_price
        upper_band = market_price * 1.05
        lower_band = market_price * 0.95

    open_orders = get_open_orders(symbol, api_key, api_secret)
    if isinstance(open_orders, dict) and "error" in open_orders:
        print(f"Skipping this loop due to API error: {open_orders['error']}")
        return

    previous_orders = load_open_orders_from_file(symbol)
    new_orders = []
    limit_orders = {}

    # Check orders in Bollinger Bands mode
    if use_bollinger_bands and bbw is not None:
        check_orders_within_bands(symbol, open_orders, api_key, api_secret, upper_band, lower_band)
        # Update open_orders if a reset occurred
        updated_orders = get_open_orders(symbol, api_key, api_secret)
        if isinstance(updated_orders, dict) and "error" in updated_orders:
            print(f"Skipping this loop due to API error after reset: {updated_orders['error']}")
            return
        open_orders = updated_orders

    # Fetch or calculate base_spacing
    if symbol not in spacing_cache:
        if use_bollinger_bands and bbw is not None:
            total_levels = grid_levels * 2
            base_spacing = (upper_band - lower_band) / total_levels
            spacing_cache[symbol] = base_spacing
        else:
            base_spacing = calculate_dynamic_base_spacing(symbol, api_key, api_secret)
        if base_spacing is None:
            print(f"Error: Could not calculate base spacing for {symbol}.")
            return
        spacing_cache[symbol] = base_spacing
    else:
        base_spacing = spacing_cache[symbol]

    print(f"Debug: market_price={market_price}, sma={sma}, base_spacing={base_spacing}, tick_size={tick_size}, lower_band={lower_band}, upper_band={upper_band}, use_bollinger_bands={use_bollinger_bands}")

    if not open_orders:
        # Check if market price is close to SMA (only during grid creation)
        if use_bollinger_bands and abs(market_price - sma) > base_spacing:
            print(f"{symbol}: Market price ({market_price}) is not close to SMA ({sma}). Skipping grid setup. Distance: {abs(market_price - sma)}, Threshold: {base_spacing}")
            return

        order_quantity_adjusted = round_to_step_size(order_quantity, step_size)

        if use_bollinger_bands:
            # Start from market price
            starting_price = round_to_tick_size(market_price, tick_size)

            # Place SELL orders above
            current_price = starting_price
            count = 0
            sell_orders = []
            while count < grid_levels:  # Removed upper_band restriction
                if current_price <= market_price:
                    current_price = round_to_tick_size(current_price + base_spacing, tick_size)
                    continue
                side = 'SELL'
                position_side = 'SHORT'
                print(f"Checking {side} order at {current_price}, count={count}/{grid_levels}")
                order = place_limit_order(symbol, side, order_quantity_adjusted, current_price, api_key, api_secret, position_side, working_type)
                if order and 'orderId' in order:
                    sell_orders.append({
                        'orderId': order['orderId'],
                        'price': current_price,
                        'side': side,
                        'quantity': order_quantity_adjusted
                    })
                    print(f"{side} at {current_price}")
                    count += 1
                else:
                    print(f"Order failed at {current_price}, skipping this level.")
                current_price = round_to_tick_size(current_price + base_spacing, tick_size)

            # Place BUY orders below
            current_price = starting_price
            count = 0
            buy_orders = []
            while count < grid_levels:  # Removed lower_band restriction
                if current_price >= market_price:
                    current_price = round_to_tick_size(current_price - base_spacing, tick_size)
                    continue
                side = 'BUY'
                position_side = 'LONG'
                print(f"Checking {side} order at {current_price}, count={count}/{grid_levels}")
                order = place_limit_order(symbol, side, order_quantity_adjusted, current_price, api_key, api_secret, position_side, working_type)
                if order and 'orderId' in order:
                    buy_orders.append({
                        'orderId': order['orderId'],
                        'price': current_price,
                        'side': side,
                        'quantity': order_quantity_adjusted
                    })
                    print(f"{side} at {current_price}")
                    count += 1
                else:
                    print(f"Order failed at {current_price}, skipping this level.")
                current_price = round_to_tick_size(current_price - base_spacing, tick_size)

            new_orders = sell_orders + buy_orders
            print(f"Grid setup complete: {len(new_orders)} orders placed (SELL: {len(sell_orders)}, BUY: {len(buy_orders)})")

        else:  # Basic bot logic
            for level in range(1, grid_levels + 1):
                buy_spacing = base_spacing
                sell_spacing = base_spacing
                buy_price = round_to_tick_size(market_price - (level * buy_spacing), tick_size)
                sell_price = round_to_tick_size(market_price + (level * sell_spacing), tick_size)

                buy_order = place_limit_order(symbol, 'BUY', order_quantity_adjusted, buy_price, api_key, api_secret, 'LONG', working_type)
                if buy_order and 'orderId' in buy_order:
                    new_orders.append({'orderId': buy_order['orderId'], 'price': buy_price, 'side': 'BUY', 'quantity': order_quantity_adjusted})
                    print(f"BUY at {buy_price}")

                sell_order = place_limit_order(symbol, 'SELL', order_quantity_adjusted, sell_price, api_key, api_secret, 'SHORT', working_type)
                if sell_order and 'orderId' in sell_order:
                    new_orders.append({'orderId': sell_order['orderId'], 'price': sell_price, 'side': 'SELL', 'quantity': order_quantity_adjusted})
                    print(f"SELL at {sell_price}")

        previous_orders = {'orders': new_orders, 'limit_orders': limit_orders}
        save_open_orders_to_file(symbol, previous_orders)

    else:  # Replacement logic
        limit_orders = previous_orders.get('limit_orders', {}).copy()
        tolerance = 0.001 * market_price

        for previous_order in previous_orders.get('orders', []):
            matching_order = next((order for order in open_orders if order['orderId'] == previous_order['orderId']), None)
            if matching_order:
                new_orders.append(previous_order)
            else:
                open_positions = get_open_positions(symbol, api_key, api_secret)
                if isinstance(open_positions, dict) and "error" in open_positions:
                    log_and_print(f"Skipping this loop due to API error: {open_positions['error']}")
                    return

                if not open_positions:
                    message = f"{symbol} No open positions detected. Assuming that position is closed. Resetting grid."
                    log_and_print(message)
                    reset_grid(symbol, api_key, api_secret)
                    if symbol in spacing_cache:
                        del spacing_cache[symbol]
                    return

                side = previous_order['side']
                new_side = 'SELL' if side == 'BUY' else 'BUY'
                base_price = float(open_positions[0]['entryPrice'])

                if use_bollinger_bands:
                    spacing = base_spacing
                else:
                    level = round(abs(previous_order['price'] - market_price) / base_spacing)
                    spacing = calculate_variable_grid_spacing(level, base_spacing, grid_progression) if progressive_grid else base_spacing

                new_price = (
                    round_to_tick_size(base_price - spacing, tick_size) if new_side == 'BUY'
                    else round_to_tick_size(base_price + spacing, tick_size)
                )

                if use_bollinger_bands:
                    if new_side == 'BUY' and new_price >= market_price:
                        new_price = round_to_tick_size(base_price - (0.002 * base_price), tick_size)
                    elif new_side == 'SELL' and new_price <= market_price:
                        new_price = round_to_tick_size(base_price + (0.002 * base_price), tick_size)
                else:
                    if new_side == 'BUY' and new_price > base_price:
                        new_price = round_to_tick_size(base_price - (0.002 * base_price), tick_size)
                    elif new_side == 'SELL' and new_price < base_price:
                        new_price = round_to_tick_size(base_price + (0.002 * base_price), tick_size)

                if any(abs(float(order['price']) - new_price) <= tolerance and order['side'] == new_side for order in open_orders):
                    message = f"{symbol} {new_side} order already exists at {new_price} within tolerance range. Skipping order replacement."
                    log_and_print(message)
                    continue

                print(f"Placing new {new_side} order at {new_price} with quantity {previous_order['quantity']} "
                      f"to replace filled {side} order")
                new_order = place_limit_order(
                    symbol, new_side, previous_order['quantity'], new_price, api_key, api_secret,
                    'SHORT' if new_side == 'SELL' else 'LONG', working_type
                )

                if new_order is None:
                    print(f"Error placing new {new_side} order at {new_price}. Skipping to the next iteration.")
                    continue
                elif 'orderId' in new_order:
                    new_orders.append({
                        'orderId': new_order['orderId'],
                        'price': new_price,
                        'side': new_side,
                        'quantity': previous_order['quantity']
                    })
                    message = f"{symbol} Placed a new replacement order {new_side} at {new_price}."
                    log_and_print(message)
                else:
                    print(f"Error placing new order at {new_price}")
                    continue

        previous_orders = {'orders': new_orders, 'limit_orders': limit_orders}
        save_open_orders_to_file(symbol, previous_orders)

def check_orders_within_bands(symbol, open_orders, api_key, api_secret, upper_band, lower_band, tolerance=0.01):
    """
    Checks if open orders are within Bollinger Bands with tolerance and resets the grid if they are not (when no positions are open).

    Args:
        symbol (str): Trading pair symbol (e.g., "BTCUSDC").
        open_orders (list): List of open orders.
        api_key (str): API key.
        api_secret (str): API secret.
        upper_band (float): Upper Bollinger Band limit.
        lower_band (float): Lower Bollinger Band limit.
        tolerance (float): Percentage tolerance (e.g., 0.01 = 1%).
    """
    open_positions = get_open_positions(symbol, api_key, api_secret)
    if open_positions and len(open_positions) > 0:
        return  # Positions exist, no check needed

    if not isinstance(open_orders, list):
        print(f"Invalid open_orders format in check_orders_within_bands: {open_orders}")
        return

    if not open_orders:
        return

    # Calculate expanded bounds with tolerance
    band_width = upper_band - lower_band
    lower_bound = lower_band - (band_width * tolerance)
    upper_bound = upper_band + (band_width * tolerance)

    for order in open_orders:
        try:
            order_price = float(order['price'])
            if order_price < lower_bound or order_price > upper_bound:
                message = f"{symbol}: Order at {order_price} is outside Bollinger Bands with tolerance ({lower_bound} - {upper_bound}). Resetting grid."
                log_and_print(message)
                reset_grid(symbol, api_key, api_secret)
                if symbol in spacing_cache:
                    del spacing_cache[symbol]
                return
        except (KeyError, TypeError) as e:
            print(f"Error processing order in check_orders_within_bands: {order}, Error: {e}")
            continue

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

    # Check if breakout is active and position is still open
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
