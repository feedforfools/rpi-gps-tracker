#!/usr/bin/env python3

import time
from serial import Serial
from serial import SerialException
from serial import SerialTimeoutException

import config

############################################################################
####                   GLOBAL VARIABLES AND CONSTANTS                   ####
############################################################################

SERIAL_PORT = None

SERIAL_TIMEOUT_HIST = 0b0000000              # 0 -> no timeout, 1 -> timeout

#########################################################################################################
####                                     Serial Debug Functions                                      ####
#########################################################################################################

def update_history(current_state = False):

    global SERIAL_TIMEOUT_HIST

    SERIAL_TIMEOUT_HIST = 0b01111111 & (SERIAL_TIMEOUT_HIST << 1)
    if current_state:
        SERIAL_TIMEOUT_HIST |= 0b1

    return 0


def check_history():
    global SERIAL_TIMEOUT_HIST

    if str(SERIAL_TIMEOUT_HIST).count("1") > 5 or int(SERIAL_TIMEOUT_HIST & 0b0001111) == 15:
        SERIAL_TIMEOUT_HIST = 0b0000000
        return True
    return False


#def unsolicited_result_codes_handler(serial_out):
# TODO: Handle unsolicited result codes



#########################################################################################################
####                                        Serial Functions                                         ####
#########################################################################################################

def init_serial_object(path, baud = 38400, timeout = 5): # After a test we know that => 9600(OK)-19200(OK)-38400(OK)-57600(OK? --> broken chars?)-115200(NO --> broken chars)

    global SERIAL_PORT

    SERIAL_PORT = Serial(path, baudrate=baud, timeout=float(timeout))# rtscts=True, dsrdtr=True)
    SERIAL_PORT.write("A\r".encode("utf-8"))
    
    return


def close_serial_object():

    if SERIAL_PORT.is_open:
        SERIAL_PORT.close()

    return


def write_to_serial(cmd, escape_char = "\r"):
    
    if isinstance(cmd, str):
        cmd_encoded = (cmd + escape_char).encode("utf-8")
    else:
        cmd_encoded = cmd

    SERIAL_PORT.write(cmd_encoded)
    
    return


def listen_to_serial(exit_word = "OK", timeout = 15, cmd = ""):

    decoded_full_serial_out = ""

    t_start = time.time()
    t_now = time.time()
    while exit_word not in decoded_full_serial_out and "ERROR" not in decoded_full_serial_out and (t_now-t_start)<timeout:
        line = SERIAL_PORT.read_until()

        line_decoded = str(line.decode("utf-8").split("\n")[0].strip())

        if cmd:
            if cmd not in line_decoded:
                if decoded_full_serial_out:
                    decoded_full_serial_out += " "
                decoded_full_serial_out += line_decoded
        else:
            if decoded_full_serial_out:
                decoded_full_serial_out += " "
            decoded_full_serial_out += line_decoded
        
        t_now = time.time()

    if "+PDP: DEACT" in decoded_full_serial_out:
        raise SerialException("Network disconnection registered: "+cmd+" "+decoded_full_serial_out)

    if (t_now-t_start)>=timeout:
        raise SerialTimeoutException("Modem serial external timeout: "+cmd+" "+decoded_full_serial_out)

    if "ERROR" in decoded_full_serial_out:
        raise SerialException("Error on command: "+cmd+" "+decoded_full_serial_out)
    
    return decoded_full_serial_out


def read_binary_get_serial_output(size, timeout = 15, cmd = ""):

    decoded_full_serial_out = ""

    t_start = time.time()
    t_now = time.time()
    # Reading the first two rows containing the command and the initial response
    while str(size) not in decoded_full_serial_out and "ERROR" not in decoded_full_serial_out and (t_now-t_start)<(timeout/2):
        line = SERIAL_PORT.read_until()

        line_decoded = str(line.decode("utf-8").split("\n")[0].strip())

        if cmd:
            if cmd not in line_decoded:
                if decoded_full_serial_out:
                    decoded_full_serial_out += " "
                decoded_full_serial_out += line_decoded
        else:
            if decoded_full_serial_out:
                decoded_full_serial_out += " "
            decoded_full_serial_out += line_decoded
        
        t_now = time.time()

    if "+PDP: DEACT" in decoded_full_serial_out:
        raise SerialException("Network disconnection registered: "+cmd+" "+decoded_full_serial_out)

    if (t_now-t_start)>=timeout:
        raise SerialTimeoutException("Modem serial external timeout: "+cmd+" "+decoded_full_serial_out)

    if "ERROR" in decoded_full_serial_out or str(size) not in decoded_full_serial_out:
        raise SerialException("Error on command: "+cmd+" "+decoded_full_serial_out)

    # Reading the actual bytes of the downloaded file
    bytes_line = SERIAL_PORT.read(size)

    decoded_full_serial_out = ""

    t_start = time.time()
    t_now = time.time()
    # Reading the rest of the command left on the serial port (it should be a \n and an OK\n)
    while "OK" not in decoded_full_serial_out and "ERROR" not in decoded_full_serial_out and (t_now-t_start)<(timeout/2):
        line = SERIAL_PORT.read_until()

        line_decoded = str(line.decode("utf-8").split("\n")[0].strip())

        if decoded_full_serial_out:
            decoded_full_serial_out += " "
        decoded_full_serial_out += line_decoded
        
        t_now = time.time()

    if "+PDP: DEACT" in decoded_full_serial_out:
        raise SerialException("Network disconnection registered: "+cmd+" "+decoded_full_serial_out)

    if "OK" not in decoded_full_serial_out:
        raise SerialException("Error on command: "+cmd+" "+decoded_full_serial_out)

    return bytes_line


def serial_command(cmd, exit_word = "OK", timeout = 15, escape_char = "\r", binary = False, size = False):

    write_to_serial(cmd, escape_char)
    try:
        if not binary:
            out = listen_to_serial(exit_word=exit_word, timeout=timeout, cmd=cmd)
        else:
            out = read_binary_get_serial_output(size, timeout, cmd)

        update_history(False)
        return out
    
    except SerialTimeoutException as e:
        update_history(True)
    
        if check_history():
            config.thread_comm("M1ser")

        raise e
    
    except Exception as e:
        raise e