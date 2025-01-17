# Grid-Bot

***Note: Use this bot at your own risk. We strongly recommend thoroughly testing your strategy in Binance's test environment before deploying it in live markets. Trading in leveraged environments can be highly volatile, and improper configuration may result in significant losses.***

This Grid Bot is a trading algorithm designed for Binance futures, capable of executing neutral, long, and short grid strategies. By configuring the bot’s behavior through various parameters, users can implement distinct trading strategies based on market trends. The bot automatically places buy and sell orders in a grid pattern, aiming to capture profits from price fluctuations within a specified range.

## Features
Three Modes: Supports neutral, long, and short modes.

**Neutral Mode:** Places buy and sell orders both above and below the market price to capture profits from any direction. Neutral mode supports two types of grids: one with fixed gaps, where orders are evenly spaced, and a progressive grid where the spacing between orders is denser in the middle and sparser at the edges. Additionally, the progressive grid increases the order sizes toward the edges, aiming to minimize losses in the grid's boundary areas. It is recommended to familiarize yourself with how the position price is calculated on the platform, as it directly impacts the profitability of trades.

**Long Mode:** Places buy orders above the market price and sell orders above buy orders, aligning with an upward trend.

**Short Mode:** Places sell orders below the market and buy orders below buy orders, designed to profit from a downward trend.

**Order Management:** Automatically places and replaces orders based on fill status. For example, in long mode, when a buy order is filled, a corresponding sell order is waiting as a take-profit level, while a stop-loss order is also added.

**Grid Reset:** Clears all existing orders and resets the grid in response to significant price movement or when the highest sell order is filled (long mode) or the lowest buy order is filled (short mode). Neutral mode resets if the market moves beyond the grid’s top or bottom.

**Error Handling and Resilience:** Manages errors and API call issues to maintain continuous operation, including insufficient margin, timestamp discrepancies etc.

## Configuration
The bot allows custom configuration through a dictionary in ```config.json``` file for each trading pair. Key parameters include:
```
grid_levels: Number of grid levels.
base_order_quantity: Quantity per order.
spacing_percentage: Defines spacing between grid levels, typically as a percentage of market price.
leverage, margin_type, and other Binance futures-specific settings.
```
If setting the leverage doesn't work for some reason, you can set it manually either through the browser or the Binance app.

## Setup Instructions
Configure API keys for Binance in the bot’s environment.

Adjust parameters in ```config.json``` settings file as needed. The file contains example runtime settings for two cryptocurrencies. Modify them as desired. You can modify the settings file at runtime; add or remove symbols and update their parameters. Refer to the ```config_doc.md``` file for detailed descriptions of the settings.

Run the bot ```(main.py)``` on a compatible environment (e.g. ```Python3``` as a prerequisite).

This bot is a powerful tool for grid-based trading strategies, automating repetitive order management with risk controls. However, it requires caution and careful parameter setup, especially in highly leveraged trading environments.

Let me know if there’s anything more to add!
