Section: IOS configuration
hostname gb-brs-rtr-demo
ip domain-name demo.netboxlabs.com
username iosuser privilege 15 secret ${router_password}
ip ssh version 2
ip ssh server algorithm hostkey rsa-sha2-512 rsa-sha2-256
line vty 0 4
 transport input ssh
 login local
ip route 0.0.0.0 0.0.0.0 172.16.0.1
