# pylint: disable=C0301, C0103, E0401, C0413

import sys
import getpass
import getopt
import os
import yaml

import cscofunc


def load_cfg_file(config_file):
    """
    """

    if os.path.isfile(config_file):        #zpracovani souboru nsconfig.json
        try:
            with open(config_file) as data_file:
                config_dict = yaml.load(data_file.read())
        except IOError:
            print("Unable to read the file", config_file)
            exit(1)
        data_file.close()
    
    return config_dict
        
def print_devices(device_list):
    """
    """

    print("sep=;")
    print("Device;IP;Platform;Version;Host")
    for device in device_list:
        if 'Host' in device['capability']:
            capab = 'Host'
        else:
            capab = ''
        print(device['device_id']+';'+device['ip_addr']+';'+device['platform_id']+';'+device['version']+';'+capab)

def print_devices_to_file(device_list, file):
    """
    """
    try:
        data_file = open(file, 'w')
    except IOError:
        print("Unable to create the file", file)
        exit(1)
    data_file.write("sep=;\n")
    data_file.write("Device;IP;Platform;Version;Host\n")
    for device in device_list:
        if 'Phone' in device['capability']:
            capab = 'Phone'
        elif 'Router' in device['capability'] and 'Switch' in device['capability']:
            capab = 'SwitchRouter'
        elif 'Router' in device['capability']:
            capab = 'Router'
        elif 'Switch' in device['capability']:
            capab = 'Switch'
        elif 'Trans-Bridge' in device['capability']:
            capab = 'Trans-Bridge'
        elif 'Host' in device['capability']:
            capab = 'Host'
        else:
            capab = ''
        data_file.write(device['device_id']+';'+device['ip_addr']+';'+device['platform_id']+';'+device['version']+';'+capab)
        data_file.write("\n")
    
    data_file.close()
def main():
    ''' Main
    '''
    usage_str = '''
    Prints devices which are paused in PRTG
    Usage: prtgpaused.py [OPTIONS]
    -h,     --help                      display help
    -i,     --ipaddr                    IP address of PRTG server
    -u,     --username                  username
    -p,     --password                  password, optional
    -d,     --days                      more than days paused, default 0
    -o,     --objid                     PRTG object id where to start, default 0
    '''
    username = ''
    pswd = ''
    found_devices = []
    passwords = {}
    config_file = ''
    output_file = ''
    
    argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "hp:i:u:c:o:", ["help", "password=", "username=", "cfgfile=", "outfile="])
    except getopt.GetoptError:
        print(usage_str)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(usage_str)
            sys.exit()

        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-p", "--password"):
            pswd = arg
        elif opt in ("-c", "--cfgfile"):
            config_file = arg
        elif opt in ("-o", "--outfile"):
            output_file = arg


    if not config_file:
        print("Config file not specified")
        sys.exit(2)

    config_dict = load_cfg_file(config_file)
    # sanity checks


    
    if 'seeds' in config_dict:
        for seed in config_dict['seeds']:
            if 'ip' not in seed:
                print('IP address is not specified in config file')
                sys.exit(1)
            if not cscofunc.is_ip_valid(seed['ip']):
                print('Invalid IP address', seed['ip'])
                sys.exit(1)
            if 'level' in seed:
                level = seed['level']
            else:
                level = 5
            if not seed['username'] in passwords:
                passwords[seed['username']] = getpass.getpass("Password for "+seed['username']+":")
        for seed in config_dict['seeds']:
            found_devices = cscofunc.get_device_list_cdp(seed['ip'], seed['username'], passwords[seed['username']], found_devices, level)
    if not output_file:
        print_devices(found_devices)            # print output to screen
    else:
        print_devices_to_file(found_devices, output_file)       # print output to file

if __name__ == "__main__":
    main()