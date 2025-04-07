import time
from datetime import datetime
from order_management import handle_grid_orders, get_open_orders, reset_grid, clear_orders_file, handle_breakout_strategy
from binance_futures import set_leverage_if_needed, calculate_bot_trigger, get_open_positions
from file_utils import load_json
import random
from logging_config import logger
import pytz

def update_active_symbols(current_symbols, active_symbols, api_key, api_secret):
    removed_symbols = active_symbols - current_symbols
    for symbol in removed_symbols:
        print(f"Symbol {symbol} was removed. Resetting its grid...")
        reset_grid(symbol, api_key, api_secret)
    return current_symbols

def process_symbol(symbol, params, previous_settings, previous_bot_states, api_key, api_secret):
    # Time zone eg. "Europe/London", "America/New_York", "Asia/Tokyo",...
    timezone = pytz.timezone("Europe/Helsinki")
    helsinki_time = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')
    print("-----------------------------")
    print(f"Processing symbol: {symbol}")
    print(f"{helsinki_time} | Processing symbol: {symbol}")

    if symbol in previous_settings and params != previous_settings[symbol]:
        print(f"Parameters changed for {symbol}. Resetting grid and breakout...")
        reset_grid(symbol, api_key, api_secret)
        active_breakouts = previous_bot_states.setdefault('active_breakouts', {})
        if symbol in active_breakouts:
            del active_breakouts[symbol]
    else:
        print(f"Parameters for {symbol} remain unchanged.")

    previous_settings[symbol] = params

    leverage = params.get("leverage")
    grid_levels = params.get("grid_levels")
    order_quantity = params.get("order_quantity")
    working_type = params.get("working_type", "CONTRACT_PRICE")
    progressive_grid = params.get("progressive_grid", "False").lower() == "true"
    grid_progression = params.get("grid_progression")
    trailing_stop_rate = params.get("trailing_stop_rate", 0.5)
    bbw_threshold = params.get("bbw_threshold", 0.07)
    klines_interval = params.get("klines_interval", "4h")
    use_websocket = False

    # Fetch the current bot state from the previous_bot_states dictionary
    bot_active = previous_bot_states.get(symbol, False)

    # Pass bot_active to the calculate_bot_trigger function
    trigger_result = calculate_bot_trigger(
        symbol,
        api_key,
        api_secret,
        bbw_threshold=bbw_threshold,
        klines_interval=klines_interval,
        bot_active=bot_active
    )
    print(trigger_result['message'])

    previous_state = previous_bot_states.get(symbol, False)
    current_state = trigger_result['start_bot']
    previous_bot_states[symbol] = current_state

    active_breakouts = previous_bot_states.setdefault('active_breakouts', {})

    # Grid bot logic
    if previous_state and not current_state:
        print(f"Stopping {symbol} grid: Resetting grid and checking breakout.")
        reset_grid(symbol, api_key, api_secret)
    elif not current_state:
        print(f"{symbol} grid remains stopped. Checking breakout...")
    else:
        # Check breakout before initializing the grid
        if symbol in active_breakouts:
            open_positions = get_open_positions(symbol, api_key, api_secret)
            if not open_positions:
                print(f"{symbol} breakout closed by trailing stop. Enabling grid.")
                logger.info(f"{symbol} breakout closed. Enabling grid.")
                del active_breakouts[symbol]
            else:
                print(f"Skipping grid creation for {symbol} due to active breakout.")
                return
        set_leverage_if_needed(symbol, leverage, api_key, api_secret)
        handle_grid_orders(
            symbol=symbol,
            grid_levels=grid_levels,
            order_quantity=order_quantity,
            working_type=working_type,
            leverage=leverage,
            progressive_grid=progressive_grid,
            grid_progression=grid_progression,
            use_websocket=use_websocket,
            klines_interval=klines_interval
        )

    # Breakout strategy (checked every loop when the bot is stopped)
    if not current_state:
        handle_breakout_strategy(
            symbol=symbol,
            trigger_result=trigger_result,
            order_quantity=order_quantity,
            trailing_stop_rate=trailing_stop_rate,
            api_key=api_key,
            api_secret=api_secret,
            working_type=working_type,
            active_breakouts=active_breakouts
        )
        print("Breakout check done.")

def main_loop():
    config = load_json("config.json")
    secrets = load_json("secrets.json")
    api_key = secrets.get("api_key")
    api_secret = secrets.get("api_secret")
    crypto_settings = config.get("crypto_settings", {})

    active_symbols = set(crypto_settings.keys())
    previous_settings = {}
    previous_bot_states = {}

    # Check open orders and synchronize state at startup
    print("Checking existing grid states and orders on startup...")
    has_open_orders = False  # Track if any symbol has open orders
    for symbol in crypto_settings.keys():
        open_orders = get_open_orders(symbol, api_key, api_secret)  # Fetch symbol-specific orders
        if open_orders and len(open_orders) > 0:  # If there are orders
            print(f"Detected active grid for {symbol} on platform.")
            previous_bot_states[symbol] = True  # Mark the bot as active
            has_open_orders = True  # Indicate that orders were found
        else:
            previous_bot_states[symbol] = False  # Assume the grid is not active

    # Clear JSON files for all symbols if no open orders are found
    if not has_open_orders:
        print("No open orders found for any symbol. Clearing orders files...")
        for symbol in crypto_settings.keys():
            clear_orders_file()  # Clear the orders file for each symbol

    while True:
        print("Starting a new loop...")
        config = load_json("config.json")
        crypto_settings = config.get("crypto_settings", {})
        current_symbols = set(crypto_settings.keys())

        active_symbols = update_active_symbols(current_symbols, active_symbols, api_key, api_secret)

        for symbol, params in crypto_settings.items():
            process_symbol(symbol, params, previous_settings, previous_bot_states, api_key, api_secret)

        time.sleep(random.uniform(20, 30))

if __name__ == "__main__":
    main_loop()
