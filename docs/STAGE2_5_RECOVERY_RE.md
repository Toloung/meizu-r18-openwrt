# Meizu R18 Stage 2.5 — WPS/TFTP Recovery 离线逆向

## 范围与输入

本阶段仅静态读取 `F:\R18_Backup_20260815\mtd0_Bootloader.bin`；没有读取 Config、Factory、Storage 或其它分区，没有启动 TFTP、触发 WPS、写入 MTD，也没有把私有 Flash 内容复制到仓库。

`mtd0_Bootloader.bin` 与 `mtd0_Bootloader_verify.bin` 均为 `0x30000`，MD5 均为 `f0f49f8e2a73dc3288bab13351ba111e`；分析副本 SHA-256 为 `8f567d27f83ea4d2516f05a62ce1f043efea2def9cae892bae503dcab9618b45`。运行时映射 `0xbc000000 + file offset` 由代码和命令表指针交叉验证。

## 已证实的菜单与写入链

| 事项 | 结论 | 静态证据 |
|---|---|---|
| 菜单 1 | RAM 下载路径 | `0xbc00249c` 打印 “Load Linux to SDRAM”；以模式 `1` 调用共同下载入口 `0xbc001320`，其紧随分支未调用 Flash writer。最终 RAM 地址尚未完全复原。 |
| 菜单 2 | 下载后写 Flash | `0xbc0024d4` 显示警告并要求 `Y/y`；`0xbc002528` 以模式 `2` 下载，`0xbc002594` 调用 `0xbc008218(source, 0x50000, downloaded_length)`。 |
| 下载入口 | 菜单专用 | `0xbc001320` 接收模式 1/2/8/9；不是命令表中的 `tftpboot`，所以不能用 CLI 默认地址替代菜单地址。 |
| CLI `tftpboot` | 已注册 | 命令表 `0x15ab0`：名称 `0xbc0142c4`、处理器 `0xbc00adb0`。 |
| 编译内置默认值 | 可确认，非运行时快照 | `ipaddr=10.10.10.123` (`0x14d75`)、`serverip=10.10.10.3` (`0x14d89`)、`bootfile="meizu_r18.bin"` (`0x14d9d`)、`loadaddr=0x80A00000`。 |
| 写入性质 | 擦除、写入、读回比较 | `0xbc008218` 按擦除块对齐并调用擦除/编程/比较子例程；不是 RAM copy。 |
| 最大输入 | 当前硬件为 `0x00fb0000` | `0xbc008270–0xbc008284` 检查 `flash_capacity - 0x50000 < length`；16 MiB SPI 即 `0x1000000 - 0x50000`。 |
| 擦写范围 | `[0x50000, 0x50000 + round_up(length, erase_block))` | `0xbc008398–0xbc0085c0` 的块对齐循环；最大可达 Flash 末尾。 |
| 已保护区域 | Bootloader / Config / Factory | 菜单 2 固定目的偏移从 `0x50000` 开始，不能向前覆盖 `0x000000–0x04ffff`。 |
| Storage | 不受菜单 2 保护 | firmware 结束于 `0xf50000`，而例程允许 `0xfb0000` 输入并可到 `0x1000000`；超出 `0xf00000` 的输入会进入 Storage。 |
| CLI `erase linux` | 部分定位 | `erase` 命令表记录位于 `0x15a20`，处理器 `0xbc008734`，帮助文本含 `erase linux`；未完整复原参数分支，不能与菜单 2 判定等价。 |
| CLI `cp.linux` | 部分定位 | 私有命令文本在 `0x1352d`/`0x138a0`；处理器及范围尚未复原。 |
| 正常 Flash 启动 | 强代码证据为 `0xbc050000` | 菜单选择 `3` 在 `0xbc0023e8–0xbc0023fc` 把该地址交给命令执行链；标准 `bootm` 已注册（表 `0x15a80`，处理器 `0xbc009ad4`）。 |

## 验证与 WPS 边界

`bootm` 处理器含 legacy uImage magic `0x27051956` 检查以及 header/data CRC 相关代码。这只证明 **`bootm` 命令**会验证 uImage，未证明菜单 2 或 WPS 在写入前调用它，也未发现明确的厂商、TRX、Meizu 名称或 model 检查。

Bootloader 中没有 `wps` 文本；仅发现 `pin_reset=0/1` 默认环境文本，不能据此确定 WPS GPIO、极性或它是否复用菜单 1/2。因此 WPS GPIO/极性、WPS 路径、WPS RAM 缓冲、WPS 是否调用菜单 2、自动重启及 WPS 验证链均为 **UNVERIFIED**。

历史操作说明与内置默认值相符：主机 `10.10.10.3`、文件名 `meizu_r18.bin`、按 WPS 上电约 4–7 秒；但不能替代 GPIO/control-flow 证据。[原始说明](https://goodguy.cc/archives/skill1.html)；[独立复述](https://topic.alibabacloud.com/tc/a/the-phantom-by-the-upgrade-process-abnormal-power-change-brick-how-to-restore_8_8_10138355.html)

## 安全结论

**WPS recovery 仍不可用于 RAM-only OpenWrt 启动。** 已证实菜单 2 会擦写，且其上限会触及 Storage；虽然 WPS 是否调用该链尚未证实，但也未发现 WPS 的非写入分支。Stage 2 仅允许 TTL 下由人工确认的 RAM 加载与 `bootm`。

只读可复现脚本：`scripts/analyze_r18_bootloader_recovery.py`。输出仅含偏移、受限字符串和摘要，不含原始 Bootloader 内容。
