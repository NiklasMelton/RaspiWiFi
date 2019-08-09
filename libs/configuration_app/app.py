from flask import Flask, render_template, request
import subprocess
import os
import time
from threading import Thread
import fileinput

app = Flask(__name__)
app.debug = True


@app.route('/')
def index():
    wifi_ap_array = scan_wifi_networks()
    config_hash = config_file_hash()
    lat,lon,zoom,ring = load_lat_and_lon()
    return render_template('app.html', wifi_ap_array = wifi_ap_array, config_hash = config_hash,lat=lat,lon=lon,zoom=zoom,ring=ring)


@app.route('/manual_ssid_entry')
def manual_ssid_entry():
    lat,lon,zoom,ring = load_lat_and_lon()
    return render_template('manual_ssid_entry.html',lat=lat,lon=lon,zoom=zoom,ring=ring)

@app.route('/wpa_settings')
def wpa_settings():
    config_hash = config_file_hash()
    return render_template('wpa_settings.html', wpa_enabled = config_hash['wpa_enabled'], wpa_key = config_hash['wpa_key'])


@app.route('/save_credentials', methods = ['GET', 'POST'])
def save_credentials():
    ssid = request.form['ssid']
    wifi_key = request.form['wifi_key']
    lat = request.form['latitude']
    lon = request.form['longitude']
    zoom = request.form['zoom']
    ring = request.form['ring']

    create_wpa_supplicant(ssid, wifi_key)
    
    
    
    set_lat_and_lon(lat,lon,zoom,ring)
    
    # Call set_ap_client_mode() in a thread otherwise the reboot will prevent
    # the response from getting to the browser
    def sleep_and_start_ap():
        time.sleep(2)
        set_ap_client_mode()
    t = Thread(target=sleep_and_start_ap)
    t.start()

    return render_template('save_credentials.html', ssid = ssid, lat=lat, lon=lon)


@app.route('/save_wpa_credentials', methods = ['GET', 'POST'])
def save_wpa_credentials():
    config_hash = config_file_hash()
    wpa_enabled = request.form.get('wpa_enabled')
    wpa_key = request.form['wpa_key']
    

    if str(wpa_enabled) == '1':
        update_wpa(1, wpa_key)
    else:
        update_wpa(0, wpa_key)

    def sleep_and_reboot_for_wpa():
        time.sleep(2)
        os.system('reboot')

    t = Thread(target=sleep_and_reboot_for_wpa)
    t.start()

    config_hash = config_file_hash()
    return render_template('save_wpa_credentials.html', wpa_enabled = config_hash['wpa_enabled'], wpa_key = config_hash['wpa_key'])




######## FUNCTIONS ##########

def scan_wifi_networks():
    iwlist_raw = subprocess.Popen(['/sbin/iwlist', 'scan'], stdout=subprocess.PIPE)
    ap_list, err = iwlist_raw.communicate()
    ap_array = []

    for line in ap_list.decode('utf-8').rsplit('\n'):
        if 'ESSID' in line:
            ap_ssid = line[27:-1]
            if ap_ssid != '':
                ap_array.append(ap_ssid)

    return ap_array

def create_wpa_supplicant(ssid, wifi_key):
    temp_conf_file = open('wpa_supplicant.conf.tmp', 'w')

    temp_conf_file.write('ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n')
    temp_conf_file.write('update_config=1\n')
    temp_conf_file.write('\n')
    temp_conf_file.write('network={\n')
    temp_conf_file.write('	ssid="' + ssid + '"\n')

    if wifi_key == '':
        temp_conf_file.write('	key_mgmt=NONE\n')
    else:
        temp_conf_file.write('	psk="' + wifi_key + '"\n')

    temp_conf_file.write('	}')

    temp_conf_file.close

    os.system('mv wpa_supplicant.conf.tmp /etc/wpa_supplicant/wpa_supplicant.conf')
    
def set_lat_and_lon(lat,lon, zoom, ring):
    template = open('/usr/lib/raspiwifi/reset_device/static_files/config.js','r').read()
    formatted_template = template.replace('$DUMMYLAT$',lat).replace('$DUMMYLON$',lon).replace('$DUMMYZOOM$',zoom)
    ring = int(ring)
    for i in range(3):
        formatted_template = formatted_template.replace('$DUMMYRING{}$'.format(i),str(int(ring*(1+i))))
    open('/usr/share/dump1090-mutability/lat_lon.log','w').write(','.join([str(lat),str(lon),str(zoom),str(ring)]))
    open('config.js.tmp','w').write(formatted_template)
    os.system('mv config.js.tmp /usr/share/dump1090-mutability/html/config.js')
    
def load_lat_and_lon():
    valid = False
    if os.path.exists('/usr/share/dump1090-mutability/lat_lon.log'):
        data = open('/usr/share/dump1090-mutability/lat_lon.log','r').read().split(',')
        if len(data) == 4:
            lat = data[0]
            lon = data[1]
            zoom = data[2]
            ring = data[3]
            valid = True
    if not valid:
        lat = '51.4934'
        lon = '0.0000'
        zoom = '9'
        ring = '25'
    return lat, lon, zoom, ring
    
    

def set_ap_client_mode():
    os.system('rm -f /etc/raspiwifi/host_mode')
    os.system('rm /etc/cron.raspiwifi/aphost_bootstrapper')
    os.system('cp /usr/lib/raspiwifi/reset_device/static_files/apclient_bootstrapper /etc/cron.raspiwifi/')
    os.system('chmod +x /etc/cron.raspiwifi/apclient_bootstrapper')
    os.system('cp /usr/lib/raspiwifi/reset_device/static_files/dnsmasq.conf.off /etc/dnsmasq.conf')
    os.system('cp /usr/lib/raspiwifi/reset_device/static_files/dhcpcd.conf.off /etc/dhcpcd.conf')
    os.system('cp /usr/lib/raspiwifi/reset_device/static_files/hostapd.off /etc/default/hostapd')
    os.system('reboot')

def update_wpa(wpa_enabled, wpa_key):
    with fileinput.FileInput('/etc/raspiwifi/raspiwifi.conf', inplace=True) as raspiwifi_conf:
        for line in raspiwifi_conf:
            if 'wpa_enabled=' in line:
                line_array = line.split('=')
                line_array[1] = wpa_enabled
                print(line_array[0] + '=' + str(line_array[1]))

            if 'wpa_key=' in line:
                line_array = line.split('=')
                line_array[1] = wpa_key
                print(line_array[0] + '=' + line_array[1])

            if 'wpa_enabled=' not in line and 'wpa_key=' not in line:
                print(line, end='')


def config_file_hash():
    config_file = open('/etc/raspiwifi/raspiwifi.conf')
    config_hash = {}

    for line in config_file:
        line_key = line.split("=")[0]
        line_value = line.split("=")[1].rstrip()
        config_hash[line_key] = line_value

    return config_hash


if __name__ == '__main__':
    config_hash = config_file_hash()

    if config_hash['ssl_enabled'] == "1":
        app.run(host = '0.0.0.0', port = int(config_hash['server_port']), ssl_context='adhoc')
    else:
        app.run(host = '0.0.0.0', port = int(config_hash['server_port']))
