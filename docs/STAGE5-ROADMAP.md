# Meizu R18 Stage 5 Roadmap

本路线图以 `v0.4.0-rc5` 为稳定基线：OpenWrt 25.12.5、Linux 6.12.94、
S25FL128S1 专用 256-byte page-size fix、recovery、LAN/WAN、双频 Wi-Fi、
Argon/Bootstrap、JFFS2 稳定性、只读 healthcheck 与默认禁用的
`r18-net-rescue` 均已完成验证。Stage 5 的目标是优化、验证和硬件证据补全，
不是重做已稳定的基础功能。

相关 GitHub Issue：#1–#9。

## 优先级与依赖

| 优先级 | 工作项 | GitHub Issue | 依赖 / 交付条件 |
| --- | --- | --- | --- |
| P0 | hostname 保留修复 | #1 | clean install 为 `Meizu-R18`；普通 sysupgrade 保留用户自定义 hostname |
| P1 | 启动时序 profiling | #2 | 先采集证据，再决定是否优化 |
| P1 | 16 MiB 软件包容量评估 | #3 | 所有建议须满足 overlay 剩余空间至少 4 MiB |
| P1 | 24–72 小时稳定性测试 | #9 | final stable 前完成 |
| P2 | 轻量 LuCI R18 状态页 | #4 | 只读、无大型依赖 |
| P2 | `r18-healthcheck` 扩展 | #5 | 保持严格只读 |
| P3 | Power LED 适配 | #6 | GPIO、极性和物理功能三项均确认后才能改 DTS |
| P3 | Reset 按钮确认 | #7 | 确认 GPIO43 极性后才能设计安全按键行为 |
| P4 | runtime WPS 调查 | #8 | 保持 deferred，不影响 bootloader WPS/TFTP recovery |

## Stage 5.1 - System Configuration & Boot Optimization

### A. hostname keep-settings fix（P0）

RC5 已确认的唯一配置回归来自
`/etc/uci-defaults/97-r18-stage3-defaults`：它无条件执行
`uci set system.@system[0].hostname='Meizu-R18'`，因而普通、保留配置的
sysupgrade 后会覆盖用户 hostname。

Stage 5 的修复验收标准：

- clean install 的 hostname 是 `Meizu-R18`；
- 若 hostname 为空或为 `OpenWrt`，才设置为 `Meizu-R18`；
- 其它用户自定义 hostname 在普通 sysupgrade 后必须原样保留；
- 不得用此修复覆盖任何其它系统设置。

### B. Boot profiling first（P1）

先 profiling，后优化。历史实机时间线约为：kernel/switch 很早启动、overlay
约 30 秒、procd 约 33 秒、netifd 约 77 秒、LAN 约 91 秒、Wi-Fi 约
102–106 秒。重点调查 procd 到 netifd 之间的等待。

允许的调查范围仅包括 init script timing、服务依赖和 blocking/sleep 分析。
禁止为缩短启动时间修改 SPI NOR page-size fix、JFFS2 mount logic、flash layout、
network topology、EEPROM/MAC 或 bootloader。目标是定位明显异常等待，而非追求
极限启动时间。

## Stage 5.2 - Storage & Package Integration

16 MiB SPI NOR 上 RC5 overlay 仍约有 8 MiB 级空间。未来 CI 容量门槛为：

```text
remaining overlay >= 4 MiB  -> PASS
remaining overlay < 4 MiB   -> FAIL
```

每个候选 package 必须记录 package name、dependencies、SquashFS increase、
runtime RAM impact、usefulness 和 recommendation，并分类为：
`RECOMMENDED`、`OPTIONAL` 或 `NOT SUITABLE`。

先评估而非立即纳入镜像的候选：

- 低成本工具：`ethtool`、`iperf3`、`tcpdump-mini`、`curl`、`nano`；
- 网络/LuCI：DDNS、UPnP、WireGuard。

大型代理套件、Docker 和大型 runtime 不适合作为基础固件默认组件。

未来 overlay CI guard 应同时输出 kernel size、SquashFS bytes_used、
rootfs_data offset 和 remaining overlay。

## Stage 5.3 - LuCI / R18 Status Enhancement

研究轻量、只读的 `luci-app-r18-status`，展示：Board、OpenWrt、Kernel、
SPI NOR、JEDEC、page size、overlay free space、2.4G state、5G state、
MT7662 state、WAN state 与 healthcheck summary。

此页面不得执行 MTD 写入、reset、firstboot、jffs2reset 或 GPIO control，且不得
引入大型依赖。

## Stage 5.4 - Healthcheck Enhancement

在保留 `r18-healthcheck` 严格只读性质的前提下，考虑增加：hostname、当前
LuCI theme、overlay free space、uptime、WAN DHCP status、default route、DNS
和 MT7662 firmware state。

不得写 UCI、重启 network、重启设备、操作 MTD 或修改 SPI NOR。

## Stage 5.5 - LED Hardware Adaptation

当前证据如下：Power LED 的 GPIO4 已由源码确认，但 polarity 未知。MT7628
switch LED pads 为 GPIO39=P4、GPIO40=P3、GPIO41=P2、GPIO42=P1、GPIO43=P0、
GPIO44=WLAN；机身实际接线仍未确认。

只有 GPIO、polarity 和 physical function 三项均由原厂 GPL/更完整 board source、
PCB trace 或 multimeter measurement 确认后，才能加入 DTS。禁止遍历 GPIO，且不得
主动触碰 GPIO7–10（SPI）、GPIO12–13（UART）或 GPIO36（PCIe reset）。

## Stage 5.6 - Reset Button

GPIO43 是 source-confirmed candidate，但 polarity 未知，因此现在不加入
`gpio-keys`。确认后再设计短按与长按行为，并优先避免误触发 factory reset。

## Stage 5.7 - WPS

runtime WPS 的 GPIO 和 polarity 仍未知；Padavan 中 `BOARD_GPIO_BTN_WPS` 未定义，
OpenWrt runtime 短按也无事件。OpenWrt runtime WPS 继续 deferred；保留现有
bootloader WPS/TFTP recovery，绝不为此修改 bootloader。

## Stage 5.8 - Long-Term Stability

在 final stable 前完成 24–72 小时 soak test。按固定时间间隔、非持久化地收集
memory、JFFS2、Wi-Fi、MT7662、netifd、hostapd、WAN DHCP、overlay 和 kernel
warnings；不要向 Flash 写入大量持久日志。

## Stage 5.1A - First Implementation Scope

下一次实际代码修改只包含：

1. hostname keep-settings fix；
2. boot profiling instrumentation / documentation；
3. overlay capacity CI guard。

不会同时加入 plugins、`gpio-keys`、`gpio-leds` 或 LuCI status app，以避免一次
引入过多变量。

## Frozen Components

除非有明确回归证据，Stage 5 继续冻结：

- S25FL128S1 dedicated page-size fix 与 JEDEC matching；
- SPI frequency、flash partitions、`0xF00000` recovery format、rootfs_data marker strategy；
- sysupgrade metadata；
- LAN1=P1、LAN2=P3、WAN=P4、CPU=P6；
- EEPROM offsets 与 MAC offsets；
- mt76/mt76x2e base chain。

## Version Plan

| 用途 | 版本 |
| --- | --- |
| 当前稳定基线 | `v0.4.0-rc5` |
| Stage 5 开发 | `v0.5.0-dev` |
| 第一批测试候选 | `v0.5.0-rc1` |

不得覆盖 `v0.4.0-rc5`，也不在此路线图阶段发布 `v0.5.0`。

## Test Gates Before Final Stable

- P0 hostname 保留路径通过；
- boot profiling 结论有日志证据；
- 任何新增软件包保持 overlay 剩余空间至少 4 MiB；
- 24–72 小时 soak test 无 JFFS2、Wi-Fi、MT7662、network 或 kernel 回归；
- 若进行 LED/Reset/WPS 开发，必须先满足各自的硬件证据要求。
