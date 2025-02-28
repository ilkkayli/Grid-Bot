import time
from order_management import handle_grid_orders, get_open_orders, reset_grid, clear_orders_file
from binance_futures import set_leverage_if_needed, calculate_bot_trigger, log_and_print
from file_utils import load_json
from binance_websockets import start_websocket

def update_active_symbols(current_symbols, active_symbols, api_key, api_secret):
    removed_symbols = active_symbols - current_symbols
    for symbol in removed_symbols:
        print(f"Symbol {symbol} was removed from the configuration. Resetting its grid...")
        reset_grid(symbol, api_key, api_secret)
    return current_symbols

def process_symbol(symbol, params, previous_settings, previous_bot_states, api_key, api_secret):
    print("-----------------------------")
    print(f"Processing symbol: {symbol}")

    if symbol in previous_settings and params != previous_settings[symbol]:
        print(f"Parameters changed for {symbol}. Resetting grid...")
        reset_grid(symbol, api_key, api_secret)
    else:
        print(f"Parameters for {symbol} remain unchanged.")

    previous_settings[symbol] = params

    leverage = params.get("leverage")
    grid_levels = params.get("grid_levels")
    order_quantity = params.get("order_quantity")
    working_type = params.get("working_type")
    progressive_grid = params.get("progressive_grid", "False").lower() == "true"
    grid_progression = params.get("grid_progression")
    use_websocket = False

    # Check Bollinger Bands -triggering
    trigger_result = calculate_bot_trigger(symbol, api_key, api_secret)
    print(trigger_result['message'])

    previous_state = previous_bot_states.get(symbol, False)

    current_state = trigger_result['start_bot']
    previous_bot_states[symbol] = current_state

    # Reset grid only when changing from running state (True) to idle (False)
    if previous_state and not current_state:
        message = f"Stopping {symbol}: Resetting grid and waiting for new entry conditions."
        log_and_print(message)
        reset_grid(symbol, api_key, api_secret)
        return
    elif not current_state:
        print(f"Bot for {symbol} remains stopped. No grid reset needed.")
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
        use_websocket=use_websocket
    )

def main_loop():
    config = load_json("config.json")
    secrets = load_json("secrets.json")
    api_key = secrets.get("api_key")
    api_secret = secrets.get("api_secret")
    crypto_settings = config.get("crypto_settings", {})

    active_symbols = set(crypto_settings.keys())
    if not get_open_orders:
        clear_orders_file()

    start_websocket(list(active_symbols))

    previous_settings = {}
    previous_bot_states = {}

    while True:
        print("Starting a new loop...")
        config = load_json("config.json")
        crypto_settings = config.get("crypto_settings", {})
        current_symbols = set(crypto_settings.keys())

        active_symbols = update_active_symbols(current_symbols, active_symbols, api_key, api_secret)

        for symbol, params in crypto_settings.items():
            process_symbol(symbol, params, previous_settings, previous_bot_states, api_key, api_secret)

        time.sleep(15)

if __name__ == "__main__":
    main_loop()
