# pylint: disable=C0301, C0103

import sys
import getpass
import getopt
import os
from time import sleep
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from paramiko.ssh_exception import SSHException


import cscofunc


def process_cfg_file(fname):
    ''' Read IP addresses from cfg file
    '''
    # iplist = []
    if os.path.isfile(fname):        # check file exists
        try:
            with open(fname) as data_file:
                loadedfile = data_file.read()
        except IOError:
            print("Unable to read the file", fname)
            exit(1)
    else:
        print("Cannot find the file", fname)
        exit(1)
    loadedfile = loadedfile.replace(' ', '')         # delete spaces
    iplist = loadedfile.split("\n")
    iplist = list(filter(None, iplist))         # delete empty lines
    for ips in iplist:
        if not cscofunc.is_ip_valid(ips):
            print("Invalid IP address in config file:", ips)
            exit(1)
    return iplist




# ============================ Main ==========================================

def main():
    ''' Main
    '''

    usage_str = '''
    Usage: addvlan.py [OPTIONS]
    -v,     --verbose                   verbose
    -h,     --help                      display help
    -w,     --writeconf                 write device configuration after config change (wr m)
    -i,     --ipaddr                    IP address of the switch
    -a,     --action                    test, t, process, p
    -u,     --username                  username
    -p,     --password                  password, optional
    -c,     --cfgfile                   cfg file with IP addresses list, one IP per line
    -m,     --vlan                      vlan already configured in allowed list on trunk
    -n,     --newvlan                   new vlan added to allowed list
    -e,     --newvlanname               name of the new vlan in quotation marks, i.e. -e "VlanName1"
    '''

    int_trunk_list = []     # list of interfaces where vlan is configured and interface is in trunk mode
    device_ip_list = []       # list of IPs of devices whose configuration is going to be changed
    ip_of_switch = ''
    config_file = ''
    vlan_match = ''
    vlan_new = ''
    vlan_new_name = ''      # name of the new Vlan, optional
    vlan_new_not_configured = False
    username = ''
    debug = False
    pswd = ''
    paction = 't'       # test mode is default
    write_conf = False
    config_was_changed = True       # configuration of the switch was changed

    argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "vwhp:i:c:u:a:m:n:e:", ["verbose", "help", "writeconf", "password=", "ipaddr=", "cfgfile=", "username=", "action=", "matchedvlan=", "newvlan=", "newvlanname="])
    except getopt.GetoptError:
        print(usage_str)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(usage_str)
            sys.exit()
        elif opt in ("-v", "--verbose"):
            debug = True
        elif opt in ("-w", "--write"):
            write_conf = True
        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-i", "--ipaddr"):
            ip_of_switch = arg
        elif opt in ("-p", "--password"):
            pswd = arg
        elif opt in ("-c", "--cfgfile"):
            config_file = arg
        elif opt in ("-a", "--action"):
            paction = arg
        elif opt in ("-m", "--matchedvlan"):
            vlan_match = arg
        elif opt in ("-n", "--newvlan"):
            vlan_new = arg
        elif opt in ("-e", "--newvlanname"):
            vlan_new_name = arg

    # sanity checks
    if (not ip_of_switch) and (not config_file):        # both variables are empty
        print("No IP address specified")
        print(ip_of_switch)
        sys.exit(2)
    if ip_of_switch and config_file:
        print("Both IP address and config file are specified")
        sys.exit(2)
    if ip_of_switch and (not cscofunc.is_ip_valid(ip_of_switch)):
        print("Invalid IP address")
        sys.exit(2)
    if not vlan_match:
        print("VLAN to be matched is not specified")
        sys.exit(2)
    if not vlan_new:
        print("New VLAN is not specified")
        sys.exit(2)
    if not username:
        print("Username is not specified")
        sys.exit(2)
    if not cscofunc.is_valid_vlan_number(vlan_match):
        print("Matched Vlan number is not valid")
        sys.exit(2)
    if not cscofunc.is_valid_vlan_number(vlan_new):
        print("New Vlan number " + vlan_new + " is not valid")
        sys.exit(2)
    if vlan_new_name:
        if not cscofunc.is_valid_vlan_name(vlan_new_name):
            print("New Vlan name", vlan_new_name, "is not valid")
            sys.exit(2)


    if pswd == '':
        pswd = getpass.getpass('Password:')

    if config_file:
        device_ip_list = process_cfg_file(config_file)  # list will contain IPs from config file
    else:
        device_ip_list.append(ip_of_switch) # list will contain only IP of one device

    print("")
    if paction == 't':
        print("Script is running in test mode. Devices configuration will not be affected")
    elif paction == 'p':
        print("Script is running in process mode. Devices Configuration WILL BE CHANGED !!!")
        sleep(5)

    for switch in device_ip_list:           # go through all switches
        config_was_changed = False
        int_trunk_list = []
        nr_iface_configured = 0             # counter for number of interfaces affected on this switch
        print("\nProcessing device:", switch)
        try:
            net_connect = ConnectHandler(device_type='cisco_ios', ip=switch, username=username, password=pswd)
        except NetMikoTimeoutException:
            print("- unable to connect to the device, timeout")
            continue
        except (EOFError, SSHException):
            print("- unable to connect to the device, error")
            continue
        if not cscofunc.is_it_switch(net_connect):
            print("- device is probably not a switch")
            continue
        if not cscofunc.is_vlan_configured(net_connect, vlan_new):      # check if new vlan is configured on the switch
            print("- WARNING: Vlan", vlan_new, "is not configured on the switch")
            vlan_new_not_configured = True
        else:
            vlan_new_not_configured = False
        int_list = cscofunc.get_intlist_vlan(net_connect, vlan_match)    # get interfaces list where is specific vlan configured

        if int_list:    # is at least one interface configured with "vlan_match" ?
            for interface in int_list:      # select trunk interfaces where "allowed vlans" command is configured
                if cscofunc.is_int_admin_trunk(net_connect, interface) and cscofunc.is_int_allowed_vlan_configured(net_connect, interface): # is interface trunk with allowed Vlans configured?
                    int_trunk_list.append(interface)    # result is in int_trunk_list


            #print(int_list)
            #print(int_trunk_list)
            if int_trunk_list and vlan_new_not_configured:  #vlan is to be added to some trunks but not configured on the switch
                if paction == 'p':  # process mode
                    if cscofunc.configure_vlan(net_connect, vlan_new, vlan_new_name):
                        print("- Vlan", vlan_new, "was configured on the switch")
                        config_was_changed = True
                    else:
                        print("- WARNING: Vlan", vlan_new, "was NOT configured on the switch for some reason")
                else:           # test mode
                    print("- Vlan", vlan_new, "would have been configured on the switch (test mode)")
            for interface in int_trunk_list:    # go through all trunk interfaces where matched vlan is allowed
                if cscofunc.is_vlan_in_allowed_list(net_connect, interface, vlan_new): # new vlan already configured on interface
                    continue                                # continue with processing of next interface
                if paction == 't':    # test only
                    print("- interface", interface, "would have been changed (test mode)")
                    nr_iface_configured = nr_iface_configured + 1
                if paction == 'p':      # process mode
                    if cscofunc.add_vlan_to_int_trunk_allowed(net_connect, interface, vlan_new):       # add vlan to allowd list
                        if cscofunc.is_vlan_in_allowed_list(net_connect, interface, vlan_new):            # check if vlan was really added                            print("- interface", interface, "would have been changed (test mode)")
                            print("- vlan", vlan_new, "was added to allowed vlans on interface", interface)
                            nr_iface_configured = nr_iface_configured + 1
                        else:
                            print("- ERROR: for some reason vlan", vlan_new, "was NOT added to allowed vlans on interface", interface)
                    else:
                        print("- ERROR during device configuration: vlan", vlan_new, "was probably NOT added to allowed vlans on interface", interface)
        else:       # nothing to do on this device
            print("- no interface configured in Vlan", vlan_match)
        # print summary results related to device which has been processed/tested
        if paction == 't':    # test only
            print("-", nr_iface_configured, "interface(s) would have been changed (test mode)")
        if paction == 'p':    # process mode
            print("-", nr_iface_configured, "interface(s) was changed")
            if nr_iface_configured > 0:
                config_was_changed = True

        if write_conf and config_was_changed:
            cscofunc.write_running_to_startup(net_connect)              # write mem
            print("- configuration was written to startup config")

        net_connect.disconnect()        # disconnect from the switch

if __name__ == "__main__":
    main()




