import logging
from logging.handlers import RotatingFileHandler

from static.helper.AppContns import LOG_TEST_FILE, LOG_SIGN_FILE, LOG_REPORT_FILE, LOG_REQ_WAREHOUSE_FILE, LOG_SPECIAL_FILE

def create_logger(logger_name):
    all_logs_files = {'test_logger': LOG_TEST_FILE, 'sign_logger': LOG_SIGN_FILE, 'report_logger': LOG_REPORT_FILE, 'request_warehouse': LOG_REQ_WAREHOUSE_FILE, 'special': LOG_SPECIAL_FILE}

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()

    handler = RotatingFileHandler(all_logs_files[logger_name], maxBytes=1_000_000, backupCount=5,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)
    logger.propagate = False

    return logger
