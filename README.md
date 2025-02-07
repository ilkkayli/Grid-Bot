# Grid-Bot

***Note: Use this bot at your own risk. We strongly recommend thoroughly testing your strategy in Binance's test environment before deploying it in live markets. Trading in leveraged environments can be highly volatile, and improper configuration may result in significant losses.***

This Grid Bot is a trading algorithm designed for Binance futures, capable of executing grid trading strategies by automatically placing buy and sell orders in a grid pattern. The bot captures profits from price fluctuations within a specified range.

# Features

**Grid Strategy:** Places buy and sell orders at predefined intervals to capitalize on market movements. The bot supports two types of grids: one with fixed gaps, where orders are evenly spaced, and a progressive grid where spacing increases towards the edges. Additionally, the progressive grid increases the order sizes at the outer levels, aiming to optimize risk and reward distribution. It is recommended to familiarize yourself with how the position price is calculated on the platform, as it directly impacts the profitability of trades.

**Order Management:** Automatically places and replaces orders based on fill status. When a buy order is filled, a corresponding sell order is placed at a higher level to capture profit, while a stop-loss mechanism is included to mitigate risk.

**Grid Reset:** Clears all existing orders and resets the grid in response to significant price movement beyond the grid’s boundaries.

**Error Handling and Resilience:** Manages errors and API call issues to maintain continuous operation, including handling insufficient margin, timestamp discrepancies, and order placement failures.

# Configuration

The bot allows custom configuration through a dictionary in the ```config.json``` file for each trading pair. Key parameters include:
```
- grid_levels: Number of grid levels.
- base_order_quantity: Quantity per order.
- spacing_percentage: Defines spacing between grid levels, typically as a percentage of market price.
- leverage, margin_type, and other Binance futures-specific settings.
```

If setting the leverage doesn't work for some reason, you can set it manually either through the browser or the Binance app.

# Setup Instructions

1. Configure API keys for Binance in the bot’s environment.
2. Adjust parameters in the ```config.json``` settings file as needed. The file contains example runtime settings for two cryptocurrencies. Modify them as desired. You can modify the settings file at runtime; add or remove symbols and update their parameters. Note that changing the coin settings will result in the closure of any open positions and a grid reset. Refer to the ```config_doc.md``` file for detailed descriptions of the settings.
3. Run the bot (main.py) on a compatible environment (e.g., Python3 as a prerequisite).

This bot is a powerful tool for grid-based trading strategies, automating repetitive order management with risk controls. However, it requires caution and careful parameter setup, especially in highly leveraged trading environments.


