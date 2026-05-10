# 锐捷网络工具集

网络设备运维日常脚本集合，适配锐捷设备。

## 脚本清单

| 脚本 | 功能 |
|------|------|
| `锐捷日志解析器/ruijie-log-parser.py` | 巡检日志→接口VLAN+光功率 |
| `Netmiko批量执行/netmiko-executor.py` | Netmiko SSH批量执行 |
| `SSH批量执行/paramiko-executor.py` | Paramiko SSH批量执行 |
| `交换机改名/switch-renamer.py` | 设备批量改名 |
| `接口统计解析/interface-stats-parser.py` | 执行结果解析 |
| `锐捷接口解析(旧版)/ruijie-interface-legacy.py` | 旧版接口解析 |
| `BookStack导入/bookstack-importer.py` | 结果上传BookStack |
| `AP邻居解析/ap-neighbor-parser.py` | AP邻居识别 |
| `锐捷AP信息/ruijie-ap-info.py` | AP信息提取 |
| `锐捷AP统计/parse_ap_logs.py` | AC离线报告生成（产品统计+离线AP明细） |

## 使用方法

各脚本独立运行，依赖见各自目录下的 README.md。

```bash
python 锐捷日志解析器/ruijie-log-parser.py 日志文件.log
```
