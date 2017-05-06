# pylint: disable=C0301, C0103, E0401, C0413

import sys
import getpass
import getopt
import os
from time import sleep
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from paramiko.ssh_exception import SSHException

scriptPath = os.path.realpath(os.path.dirname(sys.argv[0]))
os.chdir(scriptPath)

#append the relative location you want to import from
sys.path.append("../nettools/")
import apicemfunc
import cscofunc


def main():
    ''' Main
    '''
    usage_str = '''
    Usage: addvlantr.py [OPTIONS]
    -h,     --help                      display help
    -i,     --ipaddr                    IP address of the switch
    -u,     --username                  username
    -p,     --password                  password, optional
    '''
    username = ''
    pswd = ''
    ip_apicem = ''
    
    argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "hp:i:u:", [ "help" "password=", "ipaddr=", "username="])
    except getopt.GetoptError:
        print(usage_str)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(usage_str)
            sys.exit()

        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-i", "--ipaddr"):
            ip_apicem = arg
        elif opt in ("-p", "--password"):
            pswd = arg



    # sanity checks
    if ip_apicem and (not cscofunc.is_ip_valid(ip_apicem)):
        print("Invalid IP address")
        sys.exit(2)
    if not username:
        print("Username is not specified")
        sys.exit(2)


    if pswd == '':
        pswd = getpass.getpass('Password:')

    resp = apicemfunc.apicem_get_token(ip_apicem, 'v1', username, pswd)
    if resp['result'] == 'OK':
        token = resp['response']['serviceTicket']
    else:
        exit(1)
    resp = apicemfunc.apicem_get(ip_apicem, 'v1', token, 'network-device')
    print(resp)


if __name__ == "__main__":
    main()
