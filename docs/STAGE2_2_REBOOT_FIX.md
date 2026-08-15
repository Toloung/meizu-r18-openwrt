# Meizu R18 Stage 2.2 — Reboot diagnostic + delayed network recovery

## Observed Stage 2.1 behavior

The first Stage 2.1 boot was verified on hardware: LAN1 and LAN2 supplied
DHCP and reached `192.168.1.1`; WAN was isolated; the 2.4 GHz
`R18-OpenWrt-Test` AP, LuCI, and SSH worked.  The 5 GHz MT7662 radio was
detected but intentionally remained disabled.

After a normal `reboot` and more than five minutes of waiting, both LAN ports
and the 2.4 GHz SSID disappeared. Re-TFTPing the same image restored the first
boot behavior. Overlay/JFFS2 and the network/wireless UCI configuration were
verified persistent and correct, so this stage does not alter the Flash layout,
VLAN mapping, MAC source, Factory, or overlay.

## Stage 2.2 diagnostic mechanism

`r18-net-rescue` is a R18-only `procd` service with `START=99`. It launches a
one-shot worker without respawn, so its 60-second delay does not block boot.
The worker overwrites `/root/r18-boot-debug.log` with **BEFORE RESCUE** state,
restarts network, reloads Wi-Fi after ten seconds, then writes **AFTER RESCUE**
state. It records network, wireless, switch, kernel, and log data requested
for comparing the two states.

After SSH/LuCI access returns, read it with:

```sh
cat /root/r18-boot-debug.log
```

- BEFORE unavailable and AFTER restored: strongly suggests network/wireless
  initialization timing.
- Both unavailable: inspect switch/driver/kernel initialization next.
- Already working before rescue: Stage 2.2 changes may have affected timing;
  reproduce through further normal reboots.

The rescue is diagnostic only, not a permanent fix. It does not run any Flash,
reset, or firstboot command.

## Chinese LuCI and Wi-Fi

The one-time defaults script sets `luci.main.lang=zh_cn`. The image includes
`luci`, Bootstrap (default), and the Base, Firewall, and Package Manager
simplified-Chinese language packages. 2.4 GHz remains the secret-protected
debug AP on `lan`; 5 GHz remains disabled.
