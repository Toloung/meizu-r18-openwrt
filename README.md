# Meizu R18 OpenWrt

基于 OpenWrt 25.12.5 的魅族路由器极速版（Meizu R18）适配项目。

本项目为 MediaTek MT7628 平台的 Meizu R18 提供 OpenWrt 固件支持，包括：

- Recovery 救援镜像
- Sysupgrade 升级镜像
- 双频无线支持
- LAN/WAN 网络适配
- LuCI Web 管理界面
- SPI NOR Flash 修复
- 安全升级机制

> 本项目不是 OpenWrt 官方支持设备（official target）。
>
> 固件仅适用于 Meizu R18，请勿用于其它型号设备。

当前发布候选版本：**v0.4.0-rc5**。

## 功能特性

- OpenWrt 25.12.5，Linux 6.12.94
- S25FL128S1 SPI NOR 修复：仅为 JEDEC
  `01 20 18 4d 01 80`
  应用 256 字节 page programming
- 全尺寸 WPS/TFTP recovery 镜像，带干净的 `rootfs_data` 标记和全 `FF` 尾部填充
- 紧凑、包含板型校验且仅写入固件区的 sysupgrade 镜像
- LAN/WAN、DHCP、DHCPv6、防火墙与 NAT
- 2.4 GHz Wi-Fi 与 MT7662 PCIe 5 GHz Wi-Fi
- 内含简体中文的 LuCI；Argon 为 ROM 默认主题，Bootstrap 为备用主题
- 只读的 `r18-healthcheck` 诊断工具
- 保留可手动启动、默认不自动运行的 `r18-net-rescue` 框架

## 硬件

| 组件 | 已支持硬件 |
| --- | --- |
| SoC | MediaTek MT7628AN |
| Flash | 16 MiB Spansion S25FL128S1 SPI NOR |
| 无线 | 集成 2.4 GHz + MT7662 PCIe 5 GHz |

## 网络

默认 LAN 地址：`192.168.1.1/24`。

| R18 交换机端口 | OpenWrt 角色 |
| --- | --- |
| P1 | LAN1 |
| P3 | LAN2 |
| P4 | WAN |
| P6 | CPU / `eth0` |

WAN 使用 DHCP 与 DHCPv6；防火墙 WAN zone 提供 NAT 和 LAN 到 WAN 转发。
WAN Internet 连通性已通过真实上游网络实机验证，RC5 未改动该网络路径。

## 无线

全新安装时两个无线均启用并桥接到 LAN。

| 频段 | SSID | 加密 |
| --- | --- | --- |
| 2.4 GHz | `R18-OpenWrt` | WPA2-PSK/CCMP |
| 5 GHz | `R18-OpenWrt-5G` | WPA2-PSK/CCMP |

公开的出厂 Wi-Fi 密码：`password`。

**首次登录后请立即修改无线密码。** 它不是 LuCI 或 root 密码；管理凭据需单独设置。

## LuCI 界面

- 全新安装默认主题：**Argon**
- 已安装的备用主题：**Bootstrap**
- 默认语言：简体中文

镜像包含 `/lib/upgrade/keep.d/r18-luci`，因此普通、保留配置的 sysupgrade 会保留
`/etc/config/luci`，包括用户选择的主题。清除配置升级使用 Argon ROM 默认主题，且
没有启动时主题强制覆盖脚本。

## Flash 布局

提供的镜像会保留 16 MiB SPI NOR 布局。

| 区域 | 物理范围 |
| --- | --- |
| Bootloader（引导程序） | `0x000000-0x030000` |
| Config（配置） | `0x030000-0x040000` |
| Factory（出厂校准数据） | `0x040000-0x050000` |
| Firmware（固件） | `0x050000-0xF50000` |
| Storage（存储） | `0xF50000-0x1000000` |

recovery 镜像精确为 `0xF00000` 字节，且只映射到 Firmware（固件）区。它在 SquashFS 后写入
`DE AD C0 DE` `rootfs_data` 标记，并将 Firmware 剩余空间填充为 `FF`；绝不覆盖
Bootloader、Config、Factory 或 Storage。

## 升级

- 首刷或 recovery：使用 `meizu_r18.bin`，遵循
  [WPS/TFTP recovery 流程](docs/RECOVERY.md)。
- 普通升级：使用 `*-squashfs-sysupgrade.bin`，写入前先校验：

  ```sh
  sysupgrade -T /tmp/openwrt-ramips-mt76x8-meizu_r18-squashfs-sysupgrade.bin
  sysupgrade /tmp/openwrt-ramips-mt76x8-meizu_r18-squashfs-sysupgrade.bin
  ```

- 清除配置升级：使用同一 sysupgrade 镜像执行 `sysupgrade -n`。

不要将 recovery 镜像作为 sysupgrade 镜像使用。安全说明见
[SYSUPGRADE.md](docs/SYSUPGRADE.md)。Stage 3.5 的保留配置及清除配置升级路径已实机
验证；RC5 额外包含 LuCI keep rule 与 Argon ROM 默认配置，供 RC5→RC5 验证使用。

## 硬件状态

### 已确认

- S25FL128S1 专用 256 字节 page-size 修复，以及干净的 JFFS2 首次/第二次启动
- recovery 格式、Firmware 边界保护、标记与 FF 填充
- LAN1/LAN2 映射、WAN P4 配置，以及真实上游 WAN 连通性
- 2.4 GHz 和 MT7662 5 GHz，包括 VHT80
- LuCI、简体中文、Argon/Bootstrap 主题及公开 Wi-Fi 默认配置
- `r18-net-rescue` 保留供手动使用，且已禁用自动启动

### 延后处理

- **LED：** GPIO 编号、电气极性和机身接线尚未全部确认。
- **Reset：** GPIO43 为候选，但电气极性未知。
- **WPS：** runtime GPIO 未知，尚未启用 OpenWrt runtime WPS。

在这些电气映射完成确认前，不会加入 `gpio-keys` 或 `gpio-leds` 节点。独立的
bootloader WPS/TFTP recovery 流程不受影响。

## 工具

可通过 SSH 或 LuCI 终端运行 `r18-healthcheck` 进行只读诊断。它检查 SPI NOR
身份与 page size、JFFS2 日志、网络、Wi-Fi 和 rescue 服务状态；不会写入 MTD、
修改 SPI NOR、重启网络或重启路由器。

## 构建

GitHub Actions 使用 OpenWrt 25.12.5 / Linux 6.12.94 构建，并验证 Stage 2.4
SPI NOR patch、sysupgrade metadata、最终 rootfs 默认配置、recovery 结构、校验和
和 artifact。编译器和下载缓存已启用，但不缓存构建输出目录。

## 发布

**v0.4.0-rc5** 为发布候选版本，其构建身份为：

- Stage 4 / 发布候选
- Argon ROM 默认主题；同时安装 Argon 和 Bootstrap
- S25FL128S1 page-size 修复：256 字节
- Network rescue 自动启动：已禁用

## 已知问题

- LED 适配需等待 GPIO、电气极性和接线确认。
- Reset 按钮适配需等待 GPIO43 极性确认。
- Runtime WPS 适配需等待 GPIO 确认。

## 路线图

Stage 5 重点：

- 完成电气确认后的 LED 适配
- Reset 按钮评估
- 增加附加软件包
- 启动时间优化

## Credits

- OpenWrt Project
- Linux Kernel
- MediaTek MT76 Driver
- Padavan Community

## License
本项目仅用于学习、研究和设备适配。
