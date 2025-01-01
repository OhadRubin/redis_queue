import requests
import os
from socket import gethostname
import functools
from loguru import _defaults
# _defaults.LOGURU_FORMAT


from contextlib import contextmanager
import contextlib
@contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull"""
    with open(os.devnull, 'w') as fnull:
        with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
            yield
            
def get_ip():
    return requests.get('https://checkip.amazonaws.com').text.strip()

def init_logger():
    from loguru import logger
    return logger
    # if "LOKI_URL" in os.environ:
    #     try:
    #         from logging_loki import LokiHandler
    #         loki_handler = LokiHandler(url=os.environ["LOKI_URL"],
    #                             auth=tuple(os.environ["LOKI_UP"].split(":")),
    #                             version="1")
    #         logger.add(loki_handler,format= _defaults.LOGURU_FORMAT+" {extra}")
    #     except Exception as e:
    #         import traceback
    #         logger.warning("Failed to add LokiHandler",stacktrace=traceback.format_exc())
        
    # logger = logger.bind(ip=get_ip(),host=gethostname())



def logger_wraps(*, entry=True, exit=True, level="DEBUG"):
    from loguru import logger
    def wrapper(func):
        name = func.__name__

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            logger_ = logger.opt(depth=1)
            if entry:
                logger_.log(level, "Entering '{}' (args={}, kwargs={})", name, args, kwargs)
            result = func(*args, **kwargs)
            if exit:
                logger_.log(level, "Exiting '{}' (result={})", name, result)
            return result

        return wrapped

    return wrapper

def log_obj(**kwargs):
    return " ".join([f"{k}={v}" for k,v in kwargs.items()])


 