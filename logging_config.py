import logging

logger = logging.getLogger('order_management')
logger.setLevel(logging.INFO)
fh = logging.FileHandler('order_management.log')
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
