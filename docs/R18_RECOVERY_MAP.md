# Meizu R18 Recovery map — Stage 2.5

| 项目 | 状态 | 结论 / 边界 |
|---|---|---|
| 菜单 1 TFTP | CONFIRMED | 模式 1 进入共同下载入口；当前分支未见 Flash writer。最终 RAM 地址未复原。 |
| 菜单 2 TFTP | CONFIRMED | 模式 2 下载后调用 `0xbc008218(source, 0x50000, length)`。 |
| 菜单 2 写入性质 | CONFIRMED | 对齐擦除、写入、读回比较。 |
| 菜单 2 最大长度 | CONFIRMED | 当前 16 MiB SPI 为 `0xfb0000`。 |
| 菜单 2 范围 | CONFIRMED | 从 `0x50000` 至按擦除块向上取整后的结束位置，最大可到 `0x1000000`。 |
| Bootloader / Config / Factory | CONFIRMED（菜单 2） | 位于 `0x50000` 前，菜单 2 固定起点不会触及。 |
| Storage | CONFIRMED（菜单 2 无保护） | 大于 `0xf00000` 的下载会越过 firmware 区并触及 `0xf50000–0xffffff`。 |
| CLI `erase linux` | PARTIAL | `erase` 命令及文本已定位；参数范围未完整复原，不能与菜单 2 判为等价。 |
| CLI `cp.linux` | PARTIAL | 私有命令文本已定位；处理器/范围未完成。 |
| 默认 router/server/file | CONFIRMED（编译默认） | `10.10.10.123` / `10.10.10.3` / `meizu_r18.bin`；不等同保存后的运行时环境。 |
| 默认 `loadaddr` | CONFIRMED（编译默认） | `0x80a00000`，不是菜单 1/2/WPS RAM 地址证明。 |
| 正常启动 Flash 地址 | STRONG CODE EVIDENCE | 菜单 3 执行链使用 `0xbc050000`；标准 `bootm` 已注册。 |
| WPS GPIO / 极性 /路径 | UNVERIFIED | 没有 WPS 字符串或已还原的 GPIO 分支；不得从 `pin_reset` 推断。 |
| WPS 是否写 Flash | UNVERIFIED — treat as YES-risk | 外部说明称自动升级，但本 dump 未把 WPS 分支接至菜单 2。禁止实测。 |
| WPS RAM-only OpenWrt | NO（安全决策） | 未找到 WPS 的已证实非写入分支。 |

`NO` 是当前操作许可结论，不是声称不存在尚未发现的代码路径。
