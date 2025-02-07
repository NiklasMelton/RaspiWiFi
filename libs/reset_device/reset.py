import RPi.GPIO as GPIO
import os
import time
import subprocess
import reset_lib

GPIO.setmode(GPIO.BCM)
GPIO.setup(3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

counter = 0
serial_last_four = subprocess.check_output(['cat', '/proc/cpuinfo'])[-5:-1].decode('utf-8')
config_hash = reset_lib.config_file_hash()
ssid_prefix = config_hash['ssid_prefix'] + " "
reboot_required = False


reboot_required = reset_lib.wpa_check_activate(config_hash['wpa_enabled'], config_hash['wpa_key'])

#reboot_required = reset_lib.update_ssid(ssid_prefix, serial_last_four)

if reboot_required == True:
    os.system('reboot')
    
time.sleep(30)

# This is the main logic loop waiting for a button to be pressed on GPIO 18 for 10 seconds.
# If that happens the device will reset to its AP Host mode allowing for reconfiguration on a new network.
while True:
    while GPIO.input(3) == 0:
        time.sleep(0.8)
        counter = counter + 1

        print(counter)

        if counter == 5:
            reset_lib.reset_to_host_mode()
            print('reset to host')

        if GPIO.input(3) == 1:
            if 2 <= counter < 5:
                print('shutdown')
                os.system('shutdown 0')
            counter = 0
            break
    time.sleep(1)
