***Settings***

***api_credentials***
Please note, that there three variables are set in a separate file ```secrets.json```

```api_key```: Binance API key.

```api_secret```: Binance API secret.

```base_url```: Binance Futures service URL. ```"https://fapi.binance.com"``` for production environment and ```"https://testnet.binancefuture.com"``` for test environment. Note that separate API secrets are required for both test and production environments.


***crypto_settings***

```symbol```: Cryptocurrency pair to trade.

```grid_levels```: Number of grid levels. This specifies the number of buy levels and the number of sell levels. The total number of orders is twice the grid levels, as it includes both buy and sell orders.

```order_quantity```: Order quantity. This should specify the amount of the trading pair to be used in each order.

```working_type```: Price type definition (CONTRACT_PRICE or MARK_PRICE).

```leverage```: Leverage amount for the trading pair.

```progressive_grid```: This setting determines whether the grid gaps in neutral mode are fixed ("False") or expanding at the edges ("True").

```grid_progression```: The setting defines the magnitude of the growth in grid spacing and order quantity for a progressive grid eg. 1.1. The multiplier changes the grid intervals and the size of orders exponentially, so it is recommended to use small multipliers, for example, between 1.1 and 1.7. Ensure with particular caution that the size of the multiplier takes into account the market risks you are willing to accept.

***Notes***

Ensure grid_progression is chosen carefully, as a high multiplier increases risk.

The margin type is assumed to be CROSS, as it is not explicitly set in the current configuration.



