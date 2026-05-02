# ruijie-interface-legacy.py — 锐捷交换机日志解析（旧版）

从巡检日志中解析接口 VLAN 和光模块 DDM 信息。
VLAN 从 `show running-config` 的 `interface` 段提取，光功率从 `show interfaces transceiver` 提取。

## 与 ruijie-log-parser.py 的关系

这是旧版解析脚本。新版 `ruijie-log-parser.py` 基于 `show interfaces status` 和 `show vlan`，功能更完善。

| 特性 | 旧版 | 新版 |
|---|---|---|
| VLAN 来源 | running-config | show interfaces status |
| VLAN 名称 | 不支持 | 支持 |
| LLDP 邻居 | 不支持 | 支持 |
| 输出 | 每设备一个 CSV | 一个总 CSV |

## 用法

```bash
python ruijie-interface-legacy.py              # 处理当前目录
python ruijie-interface-legacy.py 日志目录
python ruijie-interface-legacy.py --test 文件
```

## 依赖

无。Python 3 标准库。
