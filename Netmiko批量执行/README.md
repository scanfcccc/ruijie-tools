# netmiko-executor.py — Netmiko SSH 批量命令执行

基于 Netmiko 的 SSH 批量设备管理工具。从 CSV 读取设备列表，从 `cmd.txt` 读取命令，并发执行并保存结果。

## 用法

```bash
pip install netmiko pandas
python netmiko-executor.py
```

## 输入文件

| 文件 | 说明 |
|---|---|
| `data/devices.csv` | 设备清单：IP、用户名、密码、设备类型 |
| `cmd.txt` | 每行一条命令，`#` 开头为注释 |

## 输出

`output/ssh_exec_results/` — 逐设备保存执行结果。

## 依赖

- `netmiko` — SSH 网络设备连接
- `pandas` — CSV 读取
