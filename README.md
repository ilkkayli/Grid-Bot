# Money Bot - Your Ultimate, Versatile Grid Trading Solution for Cryptocurrency Markets

***Note: Use this bot at your own risk. We strongly recommend thoroughly testing your strategy in Binance's test environment before deploying it in live markets. Trading in leveraged environments can be highly volatile, and improper configuration may result in significant losses.***

This Grid Bot is a trading algorithm designed for Binance futures, capable of executing grid trading strategies by automatically placing buy and sell orders in a grid pattern. The bot captures profits from price fluctuations within a specified range, using Bollinger Bands to define its operational boundaries. It activates when price volatility consolidates (narrow BBW) and remains idle during excessive fluctuations (wide BBW).

## Features

**Grid Strategy:** Places buy and sell orders at predefined intervals to capitalize on market movements. The bot supports two types of grids:
- Fixed gaps, where orders are evenly spaced.
- Progressive grid, where spacing increases towards the edges using a configurable multiplier (`grid_progression`).  
Currently, order sizes remain constant across levels; progressive sizing is planned but not yet implemented.

**Order Management:** Automatically places and replaces orders based on fill status. When a buy order is filled, a corresponding sell order is placed at a higher level to capture profit (and vice versa). A trailing stop mechanism is available for breakout strategies, but not currently implemented in the grid strategy.

**Grid Reset:** Clears all existing orders and resets the grid if price moves significantly beyond the Bollinger Bands boundaries, with a configurable tolerance (default: 1%).

**Error Handling and Resilience:** Manages errors and API call issues to maintain continuous operation, including handling insufficient margin, timestamp discrepancies, and order placement failures.

**Market Price Retrieval:** 
- Currently uses REST API calls (`get_market_price`) to fetch market prices. WebSocket support is also available.

## Configuration

The bot allows custom configuration through a dictionary in the `config.json` file for each trading pair. Key parameters include:
- `grid_levels`: Number of grid levels on each side.
- `order_quantity`: Quantity per order.
- `leverage`: Leverage level for futures trading.
- `progressive_grid`: Boolean to enable progressive spacing.
- `grid_progression`: Multiplier for progressive grid spacing.
- `bbw_threshold`: Bollinger Bands Width threshold for starting/stopping the bot.
- `klines_interval`: Candlestick interval for BB calculations (e.g., "4h").

Grid spacing is dynamically calculated based on Bollinger Bands width or market amplitude, with an optional `spacing_percent` parameter in the code (default: 1.0). If leverage setting fails, adjust it manually via Binance's interface.

## Setup Instructions

1. **Configure API keys for Binance** in `secrets.json`.
2. **Adjust parameters** in the `config.json` settings file as needed. The file contains example settings for trading pairs. Modify them at runtime to add/remove symbols or update parameters. Note: Changing settings closes open positions and resets the grid. See `config_doc.md` for details.
3. **Run the bot** (`main.py`) in a Python 3 environment.

This bot is a powerful tool for grid-based trading strategies, automating order management with risk controls. Use caution and test thoroughly, especially in leveraged markets.
