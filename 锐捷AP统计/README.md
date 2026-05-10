# 锐捷AC离线报告生成器

批量解析锐捷 AC 巡检日志，提取产品型号统计和离线 AP 明细，汇总为两个 CSV。

## 功能

- **产品统计** — `show ap-config product` 输出的型号、版本、数量
- **离线AP明细** — `show ap-config summary | ex Run` 输出的离线 AP 名称、IP、MAC、状态
- 自动识别设备名（从 CLI 提示符提取）
- 支持有无时间戳前缀的日志格式
- 支持中英文设备名
- 零外部依赖

## 使用方法

```bash
# 在日志目录下直接跑
python parse_ap_logs.py

# 指定日志目录
python parse_ap_logs.py /path/to/logs

# 自定义输出文件名
python parse_ap_logs.py /path/to/logs -o 产品统计.csv --offline 离线AP明细.csv
```

## 输出

| 文件 | 列说明 |
|------|--------|
| `产品统计.csv` | 设备名, offline_count, product_id, hw_version, count, used_wtp |
| `离线AP明细.csv` | 设备名, AP名, IP, Mac, State |

## 依赖

零外部依赖，仅需 Python 3 标准库。

## 文件清单

| 文件 | 说明 |
|------|------|
| `parse_ap_logs.py` | 主脚本 |
