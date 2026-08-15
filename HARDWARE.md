# Meizu R18 hardware findings (stage 1)

## Confirmed

- **SoC:** MediaTek/Ralink **MT7628** family. The decompressed vendor kernel contains `Ralink`, `MT7628`, MT7628 PCIe initialization messages, and a Meizu-specific symbol (`meizu_nl_send_msg`).
- **CPU architecture:** 32-bit little-endian MIPS. The uImage header declares MIPS (architecture ID 5); OpenWrt's matching target uses `ARCH:=mipsel`.
- **CPU core count / CPU type:** one MIPS24KEc core at 575/580 MHz. This is a family-level confirmation from the [MediaTek MT7628 product page](https://www.mediatek.com/products/home-networking/mt7628k-n-a), consistent with the kernel evidence above.
- **Kernel:** Linux 3.10.14; built 2016-05-09 15:28:22 CST. See `analysis/reports/kernel-strings.txt`.
- **Target candidate:** `ramips` / `mt76x8` in OpenWrt v25.12.5. The checked-out reference has `target/linux/ramips/mt76x8/target.mk` and `ARCH:=mipsel`.

## High confidence

- **2.4 GHz Wi-Fi:** MT7628 integrated 2T2R 802.11n radio. This is documented by MediaTek and is the intended `&wmac` device in the matching OpenWrt target.
- **Flash interface:** serial flash is documented for the MT7628 family; the R18's exact device is reported as 16 MB Serial flash by contemporaneous R18 specifications. The *actual chip ID and partition offsets remain unverified*.

## Medium confidence (model-specific, external corroboration)

The R18 identifier is associated with Meizu's "router speed edition". Its contemporaneous specifications report:

- **RAM:** 128 MB DDR (not independently observable in this upgrade image).
- **Flash capacity:** 16 MB serial flash.
- **5 GHz Wi-Fi:** MT7612E over PCIe, dual-band AC; the R18 firmware kernel contains MT7628 PCIe RC initialization, which is compatible with this claim but does not itself identify the PCIe card.
- **Physical Ethernet:** one 10/100 WAN and two 10/100 LAN ports.
- **USB:** USB 2.0 present.

Sources: [Meizu speed-edition overview](https://m.meizu.com/smart/router_s/summary.html) (128 MB / dual-band / USB), and [contemporaneous R18 review/specification](https://www.znds.com/tv-593904-1-1.html) (model mapping, MT7612E, 16 MB, ports). Treat these as design inputs to verify with a flash dump or serial boot log, not as a partition-writing specification.

## Unknown

- Exact flash manufacturer and JEDEC ID; NOR versus any other serial flash implementation has not been measured from hardware.
- Exact MTD partition table, factory/calibration offsets, MAC addresses, and bootloader environment.
- MT7612E EEPROM/calibration source and offset.
- Ethernet switch port-to-jack mapping, PHY IDs, GPIO, LED, and reset/WPS GPIOs.
- A stock DTB/DTS. No structurally valid FDT was found in the decompressed kernel, consistent with this vendor's older non-DT Ralink kernel design.

## Safety rule

All unidentified physical-flash regions are treated as potentially holding bootloader, MAC, factory, EEPROM, RF calibration, or serial-number data. They are **not writable** until verified from a hardware flash dump and boot log.
