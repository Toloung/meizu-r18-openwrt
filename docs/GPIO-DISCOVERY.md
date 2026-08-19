# Meizu R18 GPIO, Button, and LED Discovery

Stage 4.1 completed a non-destructive investigation on an R18 running
OpenWrt 25.12.5. No GPIO was exported, driven, or read directly during this
work; no button or LED Device Tree node was added.

## Buttons

- **WPS:** The MZ-R18 Padavan board profile leaves
  `BOARD_GPIO_BTN_WPS` undefined. A runtime short press produced no kernel,
  ubus, hotplug, input, or hostapd event. Its GPIO and electrical polarity are
  unknown, so OpenWrt runtime WPS remains deferred. This does not change the
  separate bootloader WPS/TFTP recovery procedure.
- **Reset:** The same source profile names GPIO43 as the reset-button pin, but
  does not declare its active level. It has no OpenWrt `gpio-keys` binding.
  The stock reset handler can reboot or factory-reset a device, so it was not
  pressed for this investigation.

## LEDs

- **Power:** Padavan source identifies GPIO4 as a power LED candidate, but
  gives no electrical polarity. The observed blue chassis LED was continuously
  lit; that observation alone cannot establish GPIO4 wiring or polarity.
- **MT7628 LED-function pads:** GPIO39=P4, GPIO40=P3, GPIO41=P2,
  GPIO42=P1, GPIO43=P0, and GPIO44=WLAN. They are SoC mux functions, not proof
  of chassis LED wiring. LAN1, LAN2, and WAN cable changes produced no observed
  chassis LED change.
- **Wi-Fi:** `mt76-phy0` and `mt76-phy1` expose driver LED-class devices, but
  no physical chassis LED association was established.

## Result

No button or LED has all of GPIO number, electrical polarity, and physical
function confirmed. RC5 therefore deliberately contains no `gpio-keys` or
`gpio-leds` nodes and does not alter GPIO39-44 muxing. These are deferred
hardware-integration items, not known hardware faults.
