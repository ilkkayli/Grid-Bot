import time
import json
from order_management import handle_grid_orders, get_open_orders, reset_grid, clear_orders_file

# Load settings from JSON file
def load_config(file_path='config.json'):
    """
    Load configuration from the specified file and return it as a dictionary.
    """
    with open(file_path, 'r') as file:
        config = json.load(file)
    print("Config loaded.")
    return config

# Load symbols from crypto_settings in the JSON file
def load_symbols_from_json(file_path):
    """
    Extract the list of symbols from the crypto_settings section of the JSON file.
    """
    with open(file_path, "r") as file:
        config = json.load(file)
    return set(config.get("crypto_settings", {}).keys())

# Update active symbols and handle removed symbols
def update_active_symbols(current_symbols, active_symbols, api_key, api_secret):
    """
    Compare current symbols from the JSON file with active symbols and reset grids
    for any symbols that were removed from the JSON file.
    """
    removed_symbols = active_symbols - current_symbols
    if removed_symbols:
        for symbol in removed_symbols:
            print(f"Symbol {symbol} was removed from the configuration. Resetting its grid...")
            reset_grid(symbol, api_key, api_secret)
    return current_symbols

# Main program
def main():
    # Load initial configuration
    config = load_config()
    api_credentials = config.get("api_credentials", {})
    api_key = api_credentials.get("api_key")
    api_secret = api_credentials.get("api_secret")
    crypto_settings = config.get("crypto_settings", {})

    # Clear the JSON file if there are no open orders
    if not get_open_orders:
        clear_orders_file()

    # Keep track of active symbols
    active_symbols = set(crypto_settings.keys())

    # Store previous settings for comparison
    previous_settings = {}

    # Infinite loop to manage orders
    while True:
        print("Starting a new loop...")

        # Reload configuration on each iteration
        config = load_config()
        api_credentials = config.get("api_credentials", {})
        api_key = api_credentials.get("api_key")
        api_secret = api_credentials.get("api_secret")
        crypto_settings = config.get("crypto_settings", {})

        # Load the current symbols and handle any removed symbols
        current_symbols = set(crypto_settings.keys())
        active_symbols = update_active_symbols(current_symbols, active_symbols, api_key, api_secret)

        for symbol, params in crypto_settings.items():
            # Check if parameters for the symbol have changed
            if symbol in previous_settings:
                if params != previous_settings[symbol]:
                    print(f"Parameters changed for {symbol}. Resetting grid...")
                    reset_grid(symbol, api_key, api_secret)
            else:
                print(f"Parameters have not changed for {symbol}.")

            # Update previous settings for the symbol
            previous_settings[symbol] = params

            # Extract parameters
            grid_levels = params.get("grid_levels")
            order_quantity = params.get("order_quantity")
            working_type = params.get("working_type")
            leverage = params.get("leverage")
            margin_type = params.get("margin_type")
            quantity_multiplier = params.get("quantity_multiplier")
            mode = params.get("mode")
            spacing_percentage = params.get("spacing_percentage")

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
                spacing_percentage=spacing_percentage
            )

        # Wait before the next iteration
        time.sleep(20)

if __name__ == "__main__":
    main()
