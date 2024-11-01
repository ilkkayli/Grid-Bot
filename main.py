import time
from order_management import handle_grid_orders, get_open_orders
from config import crypto_settings
from order_management import clear_orders_file

# Clear the JSON file on bot startup if there are no open orders.
if not get_open_orders:
    clear_orders_file()

# Infinite loop to continuously check and manage orders
while True:
    print("Starting a new loop..")
    for symbol, params in crypto_settings.items():
        grid_levels = params["grid_levels"]  # Number of grid levels
        base_order_quantity = params["base_order_quantity"]  # Order quantity for each level
        working_type = params["working_type"]  # The type of price to use ('MARK_PRICE' or 'LAST_PRICE')
        leverage = params["leverage"]  # Leverage for the position
        margin_type = params["margin_type"]  # Margin type ('ISOLATED' or 'CROSSED')
        quantity_multiplier = params["quantity_multiplier"]  # quantity_multiplier
        mode = params["mode"]
        spacing_percentage = params["spacing_percentage"]

        # Call the handle_grid_orders function with the extracted parameters
        handle_grid_orders(symbol, grid_levels, base_order_quantity, working_type, leverage, margin_type, quantity_multiplier, mode, spacing_percentage)

    time.sleep(10)  # Sleep for a specified time before the next iteration
