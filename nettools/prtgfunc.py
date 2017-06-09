''' Module implements functions which read/change configuration of PRTG

'''

# pylint: disable=C0301, C0103

import sys
import re
import json
import requests
import time


from datetime import date, datetime
requests.packages.urllib3.disable_warnings()
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_passhash(ip_addr, username, password):
    """
    Returns passhash

    :param ip_addr: IP address of PRTG server
    :param username:
    :param password:
    """

    url_params = {'username' : username, 'password' : password}
    # headers = {"X-Auth-Token": token}
    url = "https://"+ip_addr+"/api/getpasshash.htm"
    try:
        resp = requests.get(url, params=url_params, verify=False)
    except (requests.ConnectionError, requests.ConnectTimeout):
        print('Error')
        return None
    if resp.status_code != 200:
        return 'Error'
    return str(resp.content, 'utf-8')    # removes b, ie. b'12345678'

def get_device_list(ip_addr, username, passhash, obj_id=0, res_num=5000):
    """
    Returns list of devices configured under obj_id with max number of res_num items
    Devices are returned in list devices_list['devices']. Each item is directory

    :param ip_addr: IP address of PRTG server
    :param username:
    :param passhash: password hash
    :param obj_id: object id where searching starts, devices in tree under this id are returned
    :param res_num:  max. number of returned items
    :return devices_list: list of devices
    """
    columns = 'objid,type,active,host,device,status,downtime,message,tags,location,group'
    url = "https://"+ip_addr+"/api/table.json"
    url_params = {'content' : 'devices', \
                    'id' : obj_id, \
                    'output' : 'json', \
                    'columns' : columns, \
                    'count' : res_num, \
                    'username' : username, \
                    'passhash' : passhash}
    try:
        resp = requests.get(url, params=url_params, verify=False)
    except (requests.ConnectionError, requests.ConnectTimeout):
        print('Error')
        return None
    if resp.status_code != 200:
        return 'Error'
    devices_list = json.loads(resp.text)

    return devices_list
def get_sensors_under_device(ip_addr, username, passhash, device_id=0):
    """
    Get sensors defined under specific device

    :param ip_addr: IP address of PRTG server
    :param username:
    :param passhash: password hash
    :param  device_id: 
    :return sensor: list of sensors
    """
    columns = 'objid,type,name,tags,active,grpdev,probegroupdevice'
    url = "https://"+ip_addr+"/api/table.json"
    url_params = {'content' : 'table', \
                    'id' : device_id, \
                    'output' : 'json', \
                    'columns' : columns, \
                    'username' : username, \
                    'passhash' : passhash}
    try:
        resp = requests.get(url, params=url_params, verify=False)
    except (requests.ConnectionError, requests.ConnectTimeout):
        print('Error')
        return None
    if resp.status_code != 200:
        return 'Error'
    sensor = json.loads(resp.text)

    return sensor

def get_sensor(ip_addr, username, passhash, sensor_id=0):
    """
    Get sensor details

    :param ip_addr: IP address of PRTG server
    :param username:
    :param passhash: password hash
    :param sensor_id:
    :return sensor: sensor parameters
    """
    url = "https://"+ip_addr+"/api/getsensordetails.json"
    url_params = {
                    'id' : sensor_id, \
                    'output' : 'json', \
                    'username' : username, \
                    'passhash' : passhash}
    try:
        resp = requests.get(url, params=url_params, verify=False)
    except (requests.ConnectionError, requests.ConnectTimeout):
        print('Error')
        return None
    if resp.status_code != 200:
        return 'Error'
    sensor = json.loads(resp.text)

    return sensor

def is_sensor_valid(sens_dict):
    """
    Check if data returned by get_sensor are valid, i.e. wheather the sensor exists

    :param sens_dict: sensors dictionary
    :return Boolean:
    """

    if 'sensordata' in sens_dict:
        if sens_dict['sensordata']['sensortype'] == '(Object not found)':
            return False
        return True
    return False

def print_sensors_info(sensorlist):
    """
    Prints info about sensors

    :param sensorlist: list of sensors
    """

    for sensor in sensorlist:
        sensdata = sensor['sensordata']
        print('--------------')
        print('Name         : '+sensdata['parentdevicename']+'/'+sensdata['name'])
        print('Last message : '+sensdata['lastmessage'])
        print('Status       : '+sensdata['statustext'])
        lastup = extract_prtgtimestamp(sensdata['lastup'])
        if lastup:
            last_dt = convert_timestamp_from_prtg(lastup)
            print('Last up      : '+last_dt.strftime("%A, %d. %B %Y %I:%M%p"))
        lastdown = extract_prtgtimestamp(sensdata['lastdown'])
        if lastdown:
            last_dt = convert_timestamp_from_prtg(lastdown)
            print('Last down    : '+last_dt.strftime("%A, %d. %B %Y %I:%M%p"))
        lastcheck = extract_prtgtimestamp(sensdata['lastcheck'])
        if lastcheck:
            last_dt = convert_timestamp_from_prtg(lastcheck)
            print('Last check   : '+last_dt.strftime("%A, %d. %B %Y %I:%M%p"))




def extract_prtgtimestamp(string):
    """
    Extracts timestamp from response, i.e. from: "42875.7576289468 [18 d ago]"

    :param string:
    :return timestamp: PRTG timestamp
    """

    match = re.match(r"([0-9\.]+).*", string)
    if match:
        timestamp = match.group(1)
        return timestamp
    return ''

def convert_timestamp_from_prtg(prtg_timestamp):
    """
    Converts PRTG timestamp to datetime

    :param prtg_timestamp: PRTG timestamp
    :return datetime_value: date/time in datetime module structure
    """
    datetime_value = datetime.fromtimestamp((float(prtg_timestamp)-25569)* 86400)
    return datetime_value



def get_objectid_type(ip_addr, username, passhash, objid):
    """
    Returns type of Object ID
    0 - doesn't exist
    1 - group
    2 - device
    3 - sensor
    999 - error

    :param ip_addr: IP address of PRTG server
    :param username:
    :param passhash: password hash
    :param objid: PRTG object ID
    :return Integer: type of object
    """

    sens_dict = get_sensor(ip_addr, username, passhash, objid)

    if 'sensordata' in sens_dict:
        if sens_dict['sensordata']['sensortype'] == '(Object not found)':
            return 0    # objid doesn't exist
        if sens_dict['sensordata']['sensortype'] == 'group':
            return 1    # group
        if sens_dict['sensordata']['sensortype'] == 'device':
            return 2    # device
        if sens_dict['sensordata']['sensortype']:
            return 3    # sensor
    return 999      # error
        





def get_paused_dev_list(all_dev_list, days_paused, pause_type=7):
    """
    Filters device list according to parameters days_paused and pause_type
    Only devices of specific pause_type and paused longer or equal days_paused days paused

    :param all_dev_list: list of devices which are to be filterd
    :param days_paused: days paused threshold
    :param pause_type:  7=Paused by User, 8=Paused by Dependency, 9=Paused by Schedule
    :return ret_list: list of devices
    """
    ret_list = []
    today = date.today()

    for device in all_dev_list:
        if device['status_raw'] == pause_type:
            paused_date_info = re.search(r"Paused at\s+([0-9]+)\.([0-9]+)\.([0-9]+)", device['message_raw'])
            if paused_date_info:
                p_day = paused_date_info.group(1)
                p_month = paused_date_info.group(2)
                p_year = paused_date_info.group(3)
                paused_date = date(int(p_year), int(p_month), int(p_day))
                passed_days = abs(today - paused_date)
                if passed_days.days >= days_paused:
                    ret_list.append(device)
    return ret_list
