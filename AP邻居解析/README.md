# ap-neighbor-parser.py — AP 邻居信息提取

从交换机巡检日志的 LLDP 输出中提取 AP 设备信息，定位 AP 连接的交换机接口和 VLAN。

## 功能

- 解析 `show interfaces status` 获取接口 VLAN
- 解析 `show lldp neighbors detail` 识别 AP 设备
- 输出结果到终端

## 用法

```bash
python ap-neighbor-parser.py
```

## 依赖

无。Python 3 标准库。
