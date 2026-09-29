import logging
import sys

class UniversalLog:
    def __init__(self, info):
        # 1. Define handlers for both the file and the console (stdout)
        file_handler = logging.FileHandler("newfile.log")
        console_handler = logging.StreamHandler(sys.stdout)
        
        # 2. Apply your configuration with the handlers
        logging.basicConfig(
            level=logging.NOTSET, # Allow handlers/loggers to manage their own levels
            format='[%(asctime)s] %(levelname)s: %(message)s',
            handlers=[file_handler, console_handler]
        )
        
        logger = logging.getLogger()
        
        # 3. Check states and log matching severities
        if info[0] == "IDLE":
            logger.setLevel(logging.INFO)
            logger.info(info[0])
        elif info[0] == "TRACKING":
            logger.setLevel(logging.INFO)
            logger.info(info[0])
        elif info[0] == "DOCK":
            logger.setLevel(logging.INFO)
            logger.info(info[0])
        else:
            logger.setLevel(logging.ERROR)
            # Changed to .error() so it meets the ERROR threshold set above
            logger.error(f'Undefined state: {info[0]}') 

class main:
    state = ["TRACKING", "cheese"]
    UniversalLog(state)