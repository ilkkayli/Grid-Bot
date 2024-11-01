# Binance Futures Testnet URL
base_url = 'https://testnet.binancefuture.com'
api_key = 'YOUR_TEST_API_KEY'
api_secret = 'YOUR_TEST_API_SECRET'

# Production URL (uncomment the lines below if you want to use the production environment)
#api_key = 'YOUR_PRODUCTION_API_KEY'
#api_secret = 'YOUR_PRODUCTION_API_SECRET'
#base_url = 'https://fapi.binance.com'

# Settings
crypto_settings = {
    "BTCUSDT": {
        "symbol": "BTCUSDT",
        "grid_levels": 1,
        "base_order_quantity": 0.002,
        "working_type": "CONTRACT_PRICE",
        "leverage": 125,
        "margin_type": "CROSS",
        "quantity_multiplier": 1,
        "mode": "neutral", # mode: long, neutral, short
        "spacing_percentage": 1
    }
}
# The explanations of the settings using the example of the 1000PEPEUSDT symbol:
# "symbol": "BTCUSDT",  # The trading pair for the grid bot; determines the market in which the bot will operate.
# "grid_levels": 1,  # Number of grid levels, i.e., the number of buy and sell order levels on each side. Here, "1" means only one buy and sell order.
# "base_order_quantity": 0.002,  # Quantity of the asset to be traded in each order; each order will be for a quantity of 0.002 BTCUSDT.
# "working_type": "CONTRACT_PRICE",  # Price type the bot uses for calculations; "CONTRACT_PRICE" uses the asset’s contract price as the reference.
# "leverage": 125,  # Leverage level for the trading account, set here to 125x. Leverage allows the bot to open larger positions with smaller capital but increases risk proportionally.
# "margin_type": "CROSS",  # Margin type; "CROSS" uses the entire account balance as collateral for positions, affecting risk and capital efficiency. Can't be adjusted.
# "quantity_multiplier": 1,  # Used only in "neutral" mode. Controls the distribution of order quantities within the grid. When set to 1, each order has the same quantity. Higher values scale order size closer to the center of the grid based on the multiplier.
# "mode": "long",  # The bot's trading mode, which can be set to "long", "neutral", or "short". "Long" mode places the grid above the market price with buy orders below sell orders. "Neutral" mode places buy orders below the market price and sell orders above the market price.
# "spacing_percentage": 1,  # Spacing between grid orders as a percentage of the market price. A 1% spacing means each order is placed 1% away from the previous order level, creating a consistent distance between grid orders.
