Section: IOS configuration
hostname gb-brs-rtr-demo
ip domain-name demo.netboxlabs.com
username iosuser privilege 15 secret ${router_password}
ip ssh version 2
ip ssh server algorithm hostkey ecdsa-sha2-nistp256 rsa-sha2-512 rsa-sha2-256
ip ssh server algorithm authentication password keyboard
line vty 0 4
 transport input ssh
 login local
ip route 0.0.0.0 0.0.0.0 172.16.0.1
event manager applet ECDSA-KEYGEN authorization bypass
 event timer countdown time 60
 action 1.0 cli command "enable"
 action 2.0 cli command "configure terminal"
 action 3.0 cli command "crypto key generate ec keysize 256 label SSHKEY"
 action 4.0 cli command "end"
 action 5.0 cli command "write memory"
 action 6.0 cli command "no event manager applet ECDSA-KEYGEN"
 action 7.0 cli command "write memory"
