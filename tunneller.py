#!/usr/bin/env python3


import threading, queue, time
import os.path

import support, networker

WIFI_CHECK_TIMER = 15
AUTOSSH_UP = False

def main():

    global AUTOSSH_UP

    LOGGER = support.setup_logger("ssh-tunnel", "tunnel")   

    ssh_script = "sudo /etc/init.d/"


    if os.path.isfile("ssh.flag"):
        ssh_script += "autossh-tunnel"
        output = support.bash_cmd("rm ssh.flag")
        LOGGER.info("Port SSH 1")
    else:
        ssh_script += "autossh-tunnel2"
        output = support.bash_cmd("touch ssh.flag")
        LOGGER.info("Port SSH 2")


    while True:

        time.sleep(5)

        if networker.iface_status("wlan0"):
            if networker.check_internet("wlan0"):
                if not AUTOSSH_UP:
                    output = support.bash_cmd(ssh_script + " start", 10)
                    time.sleep(1)
                    output = support.bash_cmd(ssh_script + " stop", 10)
                    time.sleep(1)
                    output = support.bash_cmd(ssh_script + " start", 10)
                    if "start" in output:
                        LOGGER.info("Autossh-tunnel correctly started")
                        AUTOSSH_UP = True
                    elif "Error" in output:
                        LOGGER.error("Couldn't start autossh-tunnel: "+str(output))
                        AUTOSSH_UP = False
                continue
        
        if AUTOSSH_UP:
            LOGGER.warning("Not on wifi anymore")
            output = support.bash_cmd(ssh_script + " stop", 10)
            if not "Error" in output:
                LOGGER.info("Shutting down autossh-tunnel")
                AUTOSSH_UP = False
            else:
                LOGGER.error("Couldn't stop autossh-tunnel: "+str(output))
        



#---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("main crashed. Error: %s", e)