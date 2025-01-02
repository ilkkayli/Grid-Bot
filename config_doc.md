***Settings***

***api_credentials***

```api_key```: Binance API key.

```api_secret```: Binance API secret.

```base_url```: Binance Futures service URL. ```"https://fapi.binance.com"``` for production environment and ```"https://testnet.binancefuture.com"``` for test environment. Note that separate API secrets are required for both test and production environments.


***crypto_settings***

```symbol```: Cryptocurrency pair to trade.

```grid_levels```: Number of grid levels. This specifies the number of buy levels and the number of sell levels. The total number of orders is twice the grid levels, as it includes both buy and sell orders.

```order_quantity```: Order quantity. This should specify the amount of the trading pair to be used in each order.

```working_type```: Price type definition (CONTRACT_PRICE or MARK_PRICE).

```leverage```: Leverage amount for the trading pair.

```margin_type```: Margin type (always CROSS).

```quantity_multiplier```: A factor used for calculating order quantities.

```mode```: Bot's operation mode (e.g., long, short, or neutral).

```spacing_percentage```: Percentage difference between price levels. This represents the gap between consecutive orders as a percentage.

```progressive_grid```: This setting determines whether the grid gaps in neutral mode are fixed ("False") or expanding at the edges ("True").

```grid_progression```: The setting defines the magnitude of the growth in grid spacing for a progressive grid eg. 1.1

