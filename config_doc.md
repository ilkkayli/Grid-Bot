Settings
api_credentials

```api_key```: Binance API key.
```api_secret```: Binance API secret.
```base_url```: Binance Futures service URL.

crypto_settings

```symbol```: Cryptocurrency pair to trade.
```grid_levels```: Number of grid levels. This specifies the number of buy levels and the number of sell levels. The total number of orders is twice the grid levels, as it includes both buy and sell orders.
```order_quantity```: Order quantity. This should specify the amount of the trading pair to be used in each order.
```working_type```: Price type definition (CONTRACT_PRICE or MARK_PRICE).
```leverage```: Leverage amount for the trading pair.
```margin_type```: Margin type (e.g., CROSS).
```quantity_multiplier```: A factor used for calculating order quantities.
```mode```: Bot's operation mode (e.g., long, short, or neutral).
```spacing_percentage```: Percentage difference between price levels. This represents the gap between consecutive orders as a percentage.
