''' Module implements functions which read/change configuration of PRTG

'''

# pylint: disable=C0301, C0103

import sys
import re
import json
import requests
import time


from datetime import date
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
    :returns devices_list: list of devices
    """
    columns = 'objid,type,active,host,device,status,downtime,message,tags,location'
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

def get_paused_dev_list(all_dev_list, days_paused, pause_type=7):
    """
    Filters device list according to parameters days_paused and pause_type
    Only devices of specific pause_type and paused longer or equal days_paused days paused

    :param all_dev_list: list of devices which are to be filterd
    :param days_paused: days paused threshold
    :param pause_type:  7=Paused by User, 8=Paused by Dependency, 9=Paused by Schedule
    :returns ret_list: list of devices
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
