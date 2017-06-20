# Device discovery using CDP

   Discovers devices using CDP
    Usage: discoverdevices.py [OPTIONS]
    -h,     --help                      display help
    -c,     --cfgfile                   yaml config file                     
    -o,     --outfile                   csv outputfile


### YAML file format

seeds:
  - ip: 192.168.0.241
    level: 1
    username: user1
  - ip: 192.168.0.177
    level: 3
    username: user1
ranges:
  - range: 10.1.0.0/28
    username: user2

seeds:
Discovery is performed starting on seed device (ip) and then recurrently continues on found neighbors. The level specifies diameter from seed devices, i.e. level of recurrency.
If seed device was already analyzed for CDP information, it is not processed. Regardless of level.

ranges:
Discovery is performed by conntacting each host IP (subnet and broadcast IP is not conntacted) in range specified. CDP information of each conntacted device is processed.
