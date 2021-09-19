#!/usr/bin/env python3

from supervisor import *

if __name__ == "__main__":
    
    try:
        main_supervisor()
    except Exception as e:
        LOGGER.exception(e)
        LOGGER.error(str(e))
        support.reboot_system()
