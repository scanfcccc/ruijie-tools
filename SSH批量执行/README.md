# paramiko-executor.py — Paramiko 并发 SSH 批量执行

基于 Paramiko 的 SSH 批量命令执行工具。并发登录多台设备执行预定义命令，结果逐设备保存。

## 功能

- 从 `data/devices.csv` 读取设备列表
- 执行预定义命令（接口状态、丢包、CRC、光模块等）
- 并发控制（默认最多 10 台）
- 结果保存到 `output/ssh_exec_results/`

## 用法

```bash
pip install paramiko
python paramiko-executor.py
```

## 依赖

- `paramiko` — SSH 连接
