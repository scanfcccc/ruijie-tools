# ruijie-ap-info.py — 锐捷 AP 信息解析

从交换机巡检日志的 LLDP 输出中提取 AP 信息：交换机接口、AP MAC、AP 名称、VLAN。

## 功能

- 自动检测文件编码（UTF-8/UTF-16/GBK）
- 解析 `show interfaces status` 获取 VLAN
- 解析 `show lldp neighbors detail` 提取 AP 信息
- 输出 CSV 格式结果

## 用法

```bash
python ruijie-ap-info.py
```

## 依赖

无。Python 3 标准库。
