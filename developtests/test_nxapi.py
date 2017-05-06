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
    ip_of_switch = ''
    
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
            ip_of_switch = arg
        elif opt in ("-p", "--password"):
            pswd = arg



    # sanity checks
    if ip_of_switch and (not cscofunc.is_ip_valid(ip_of_switch)):
        print("Invalid IP address")
        sys.exit(2)
    if not username:
        print("Username is not specified")
        sys.exit(2)


    if pswd == '':
        pswd = getpass.getpass('Password:')

    sh_int_switch = cscofunc.nxapi_post_cmd(ip_of_switch, 8443, username, pswd, 'cli_show', 'show interface switchport')
    print(sh_int_switch)
    conf_vlan = cscofunc.nxapi_post_cmd(ip_of_switch, 8443, username, pswd, 'cli_conf', 'vlan 333 ;name ThreeThreeThree')
    print(conf_vlan)


if __name__ == "__main__":
    main()
