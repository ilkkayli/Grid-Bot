import time
import json
from order_management import handle_grid_orders, get_open_orders, reset_grid, clear_orders_file
from binance_futures import set_leverage_if_needed

# Load settings from JSON file
def load_config(file_path='config.json'):
    with open(file_path, 'r') as file:
        return json.load(file)

# Update active symbols and handle removed symbols
def update_active_symbols(current_symbols, active_symbols, api_key, api_secret):
    removed_symbols = active_symbols - current_symbols
    if removed_symbols:
        for symbol in removed_symbols:
            print(f"Symbol {symbol} was removed from the configuration. Resetting its grid...")
            reset_grid(symbol, api_key, api_secret)
    return current_symbols

# Main program
def main():
    config = load_config()
    api_credentials = config.get("api_credentials", {})
    api_key = api_credentials.get("api_key")
    api_secret = api_credentials.get("api_secret")
    crypto_settings = config.get("crypto_settings", {})

    if not get_open_orders:
        clear_orders_file()

    active_symbols = set(crypto_settings.keys())
    previous_settings = {}

    while True:
        print("Starting a new loop...")
        config = load_config()
        crypto_settings = config.get("crypto_settings", {})
        current_symbols = set(crypto_settings.keys())
        active_symbols = update_active_symbols(current_symbols, active_symbols, api_key, api_secret)

        for symbol, params in crypto_settings.items():
            if symbol in previous_settings:
                if params != previous_settings[symbol]:
                    print(f"Parameters changed for {symbol}. Resetting grid...")
                    reset_grid(symbol, api_key, api_secret)
            else:
                print(f"Parameters have not changed for {symbol}.")

            previous_settings[symbol] = params

            # Extract parameters
            leverage = params.get("leverage")
            grid_levels = params.get("grid_levels")
            order_quantity = params.get("order_quantity")
            working_type = params.get("working_type")
            margin_type = params.get("margin_type")
            quantity_multiplier = params.get("quantity_multiplier")
            mode = params.get("mode")
            spacing_percentage = params.get("spacing_percentage")
            progressive_grid = params.get("progressive_grid", "False").lower() == "true"

            print("-----------------------------")
            print(f"Symbol: {symbol}")
            # Check and set leverage
            set_leverage_if_needed(symbol, leverage, api_key, api_secret)

            # Call the order management function
            handle_grid_orders(
                symbol=symbol,
                grid_levels=grid_levels,
                order_quantity=order_quantity,
                working_type=working_type,
                leverage=leverage,
                margin_type=margin_type,
                quantity_multiplier=quantity_multiplier,
                mode=mode,
                spacing_percentage=spacing_percentage,
                progressive_grid=progressive_grid
            )

        time.sleep(10)

if __name__ == "__main__":
    main()
