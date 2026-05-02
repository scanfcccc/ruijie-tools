# interface-stats-parser.py — SSH 执行结果解析汇总

解析 SSH 批量执行的结果日志，提取每个接口的状态、VLAN、丢包、CRC 错误、光模块信息，汇总输出 CSV。

## 功能

- 自动扫描 `output/ssh_exec_results/` 下的日志
- 提取接口状态（up/down、VLAN、双工、速率、介质）
- 提取输入/输出丢包、CRC 错误
- 提取光模块 DDM（温度、偏置电流、收/发光功率）
- 输出 `output/接口统计.csv`

## 用法

```bash
python interface-stats-parser.py
```

## 依赖

无。Python 3 标准库。
