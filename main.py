import time
import json
from order_management import handle_grid_orders, get_open_orders, reset_grid, clear_orders_file
from binance_futures import set_leverage_if_needed


def load_config(file_path="config.json"):
    """
    Load configuration from a JSON file.

    Args:
        file_path (str): Path to the configuration file.

    Returns:
        dict: Configuration settings as a dictionary.
    """
    with open(file_path, "r") as file:
        return json.load(file)


def update_active_symbols(current_symbols, active_symbols, api_key, api_secret):
    """
    Update the active symbols list by removing symbols no longer in the configuration.
    Reset grids for removed symbols.

    Args:
        current_symbols (set): Symbols currently in the configuration.
        active_symbols (set): Previously active symbols.
        api_key (str): API key for Binance.
        api_secret (str): API secret for Binance.

    Returns:
        set: Updated set of active symbols.
    """
    removed_symbols = active_symbols - current_symbols
    for symbol in removed_symbols:
        print(f"Symbol {symbol} was removed from the configuration. Resetting its grid...")
        reset_grid(symbol, api_key, api_secret)
    return current_symbols


def process_symbol(symbol, params, previous_settings, api_key, api_secret):
    """
    Process a single symbol: check parameters, reset grid if needed, and manage orders.

    Args:
        symbol (str): The trading symbol.
        params (dict): Configuration parameters for the symbol.
        previous_settings (dict): Previously stored settings for comparison.
        api_key (str): API key for Binance.
        api_secret (str): API secret for Binance.
    """
    # Detect parameter changes and reset grid if necessary
    print("-----------------------------")
    print(f"Processing symbol: {symbol}")
    if symbol in previous_settings and params != previous_settings[symbol]:
        print(f"Parameters changed for {symbol}. Resetting grid...")
        reset_grid(symbol, api_key, api_secret)
    else:
        print(f"Parameters for {symbol} remain unchanged.")

    # Update previous settings
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
    grid_progression = params.get("grid_progression")

    # Check and set leverage
    set_leverage_if_needed(symbol, leverage, api_key, api_secret)

    # Manage grid orders
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
        progressive_grid=progressive_grid,
        grid_progression=grid_progression
    )


def main_loop():
    """
    Main execution loop for the grid bot.
    """
    # Load initial configuration
    config = load_config()
    api_credentials = config.get("api_credentials", {})
    api_key = api_credentials.get("api_key")
    api_secret = api_credentials.get("api_secret")
    crypto_settings = config.get("crypto_settings", {})

    # Initialize active symbols and clear orders file if needed
    active_symbols = set(crypto_settings.keys())
    if not get_open_orders:
        clear_orders_file()

    previous_settings = {}

    while True:
        print("Starting a new loop...")
        # Reload configuration to detect changes
        config = load_config()
        crypto_settings = config.get("crypto_settings", {})
        current_symbols = set(crypto_settings.keys())

        # Update active symbols and handle removed symbols
        active_symbols = update_active_symbols(current_symbols, active_symbols, api_key, api_secret)

        # Process each active symbol
        for symbol, params in crypto_settings.items():
            process_symbol(symbol, params, previous_settings, api_key, api_secret)

        # Wait before starting the next loop
        time.sleep(20)


if __name__ == "__main__":
    main_loop()
