# switch-renamer.py — 锐捷交换机批量改名

Paramiko 驱动的交换机批量改名工具。从 CSV 读取设备与新名称对照表，SSH 登录后逐台执行改名。

## 功能

- 自动检测设备型号
- 智能组装名称：`基名-型号-IP尾号-POE`
- 并发执行
- 运行日志记录

## 名称组装规则

```
原始名：PJXRMYY-ACC-WW-ZY-8F-01
  → WW 替换为 NW
  → 追加型号
  → 追加 IP 尾号
  → 追加 POE（如适用）
结果：PJXRMYY-ACC-NW-ZY-8F-01-S5000-24GT4SFP-P-130.37-POE
```

## 用法

```bash
pip install pandas paramiko
python switch-renamer.py
```

## 依赖

- `paramiko` — SSH 连接
- `pandas` — CSV 读取
