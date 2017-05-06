# pylint: disable=C0301, C0103

import sys
import json
import requests


requests.packages.urllib3.disable_warnings()
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def apicem_get_token(ip, ver, username, password):
    '''
    Returns dictionary with ticket.
    When POST request is successful, then key 'result' in r_json contains 'OK' and ticket is in ['response']['serviceTicket']
    otherwise 'result' contains 'NOK'
    '''

    r_json = {
        "username":username, "password":password
    }
    post_url = "https://"+ip+"/api/"+ver+"/ticket"
    headers = {'content-type':'application/json'}

    try:
        resp = requests.post(post_url, data=json.dumps(r_json), headers=headers, verify=False)
        r_json = resp.json()
        if 'serviceTicket' in r_json["response"].keys():
            r_json['result'] = 'OK'
        else:
            r_json['result'] = 'NOK'
    except (requests.ConnectionError, requests.ConnectTimeout):

        r_json['result'] = 'NOK'
    return r_json


def apicem_get(ip, ver, token, api='', params=''):
    '''
    GET
    '''

    headers = {"X-Auth-Token": token}
    url = "https://"+ip+"/api/"+ver+"/"+api
    try:
        resp = requests.get(url, headers=headers, params=params, verify=False)
        r_json = resp.json()
        r_json['result'] = 'OK'
    except (requests.ConnectionError, requests.ConnectTimeout):
        r_json['result'] = 'NOK'
    return r_json

def apicem_post(ip, ver, token, api='', data=''):
    '''
    POST
    '''
    headers = {"content-type" : "application/json", "X-Auth-Token": token}
    url = "https://"+ip+"/api/"+ver+"/"+api
    try:
        resp = requests.post(url, json.dumps(data), headers=headers, verify=False)
        r_json = resp.json()
        r_json['result'] = 'OK'
    except (requests.ConnectionError, requests.ConnectTimeout):
        r_json['result'] = 'NOK'
    return r_json

def apicem_put(ip, ver, token, api='', data=''):
    '''
    PUT
    '''
    headers = {"content-type" : "application/json", "X-Auth-Token": token}
    url = "https://"+ip+"/api/"+ver+"/"+api
    try:
        resp = requests.put(url, json.dumps(data), headers=headers, verify=False)
        r_json = resp.json()
        r_json['result'] = 'OK'
    except (requests.ConnectionError, requests.ConnectTimeout):
        r_json['result'] = 'NOK'
    return r_json


def apicem_delete(ip, ver, token, api='', params=''):
    '''
    DELETE
    '''

    headers = {"X-Auth-Token": token, 'content-type': 'application/json'}
    url = "https://"+ip+"/api/"+ver+"/"+api
    try:
        resp = requests.delete(url, headers=headers, params=params, verify=False)
        r_json = resp.json()
        r_json['result'] = 'OK'
    except (requests.ConnectionError, requests.ConnectTimeout):
        r_json['result'] = 'NOK'
    return r_json
    