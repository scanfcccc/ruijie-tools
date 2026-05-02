# ruijie-log-parser.py — 锐捷交换机巡检日志解析

批量解析锐捷交换机巡检日志（.txt/.log），输出逐接口 VLAN 明细 CSV。

## 功能

- 提取设备信息（名称、型号、IP、序列号、版本、上线时间）
- 每个接口的 VLAN ID + VLAN 名称（从 `show vlan` 映射）
- 链路状态、速率、双工、介质类型
- LLDP 邻居
- 光模块 DDM（温度、偏置电流、收/发光功率）

## 用法

```bash
python ruijie-log-parser.py                    # 处理当前目录
python ruijie-log-parser.py 路径/到/日志文件夹
```

CSV 输出到输入目录，文件名：`设备接口VLAN明细.csv`

## 依赖

无。Python 3 标准库。

## 支持设备

锐捷 S5000 / S5300 / S6100 / S6120 系列。
