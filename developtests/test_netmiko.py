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

    print("\nProcessing device:", ip_of_switch)
    try:
        net_connect = ConnectHandler(device_type='cisco_ios', ip=ip_of_switch, username=username, password=pswd)
    except NetMikoTimeoutException:
        print("- unable to connect to the device, timeout")
        sys.exit(2)
    except (EOFError, SSHException):
        print("- unable to connect to the device, error")
        sys.exit(2)
    if not cscofunc.is_it_switch(net_connect):
        print("- device is probably not a switch")
        sys.exit(2)

    print ('MAC addr table')
    mac_table = cscofunc.get_cli_sh_mac_address_table(net_connect)
    print ('MAC addr table')
    mac_table2 = cscofunc.get_cli_sh_mac_address_table_dyn_dict(net_connect)
    print('Get sh ip int brie')
    int_brie = cscofunc.get_cli_sh_ip_int_brie(net_connect)
    print('Get sh int switchport')
#    int_switchport_list = cscofunc.get_cli_sh_int_switchport(net_connect)
    print('Get sh cdp nei')
#    cdp_table = cscofunc.get_cli_sh_cdp_neighbor(net_connect)
    print('Get sh vlan')
#    vlan_table = cscofunc.get_cli_sh_vlan_plus(net_connect)
#    print(vlan_table)

    net_connect.disconnect()        # disconnect from the switch


if __name__ == "__main__":
    main()
