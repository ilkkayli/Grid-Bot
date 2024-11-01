import logging
import os

LOG_DIR = "logs"

def setup_logger():
    # Create the log directory if it doesn’t already exist
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # Set the logging level
    logging.basicConfig(level=logging.INFO)

def log_open_order(symbol, side, quantity, price, position_side, order_type):
    log_file = os.path.join(LOG_DIR, "orders.log")
    logger = logging.getLogger("order_logger")

    # Define the log file format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Create a file handler for the log file
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger
    logger.addHandler(file_handler)

    # Write the log entry
    logger.info(f"Opened {order_type} order for {position_side}: Symbol={symbol}, Side={side}, Quantity={quantity}, Price={price}")

    # Remove the file handler from the logger
    logger.removeHandler(file_handler)
