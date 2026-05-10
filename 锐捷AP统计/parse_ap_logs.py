#!/usr/bin/env python3
"""
锐捷AC日志解析脚本
提取所有日志中的产品统计和离线AP明细，汇总为两个 CSV。

用法:
    python parse_ap_logs.py [日志目录]

输出:
    产品统计.csv  — 设备名, offline_count, product_id, hw_version, count, used_wtp
    离线AP明细.csv — 设备名, AP名, IP, Mac, State
"""

import re
import sys
import os
import csv
import argparse


def extract_device_name(text: str) -> str:
    """从日志中提取设备名 (CLI 提示符，含中文)。"""
    # 找 # 前的非空内容（去掉时间戳前缀 [HH:MM:SS]）
    m = re.search(r'(?:^|]|\n)([^\n\[\]#]+)#', text)
    if m:
        name = m.group(1).strip()
        # 去掉行首可能残留的控制字符/空格
        name = re.sub(r'^[\s\[\]]+', '', name)
        if name:
            return name
    return 'unknown'


def parse_product_table(text: str, device_name: str):
    """提取 show ap-config product 表格，返回行记录列表。"""
    rows = []
    in_table = False
    for line in text.splitlines():
        content = re.sub(r'^\[\d{2}:\d{2}:\d{2}\]', '', line).strip()

        if 'Product ID' in content and 'Hardware Version' in content:
            in_table = True
            continue

        if in_table:
            # 跳过分隔线
            if re.match(r'^[- ]+$', content):
                continue
            # 表结束
            if not content or content.startswith(device_name + '#'):
                in_table = False
                continue

            fields = re.split(r'\s{2,}', content)
            if len(fields) >= 4:
                rows.append({
                    'product_id': fields[0].strip(),
                    'hw_version': fields[1].strip(),
                    'count': fields[2].strip(),
                    'used_wtp': fields[3].strip(),
                })
    return rows


def parse_offline_aps(text: str, device_name: str):
    """提取 show ap-config summary 中的离线 AP 明细，返回行记录列表。

    格式 (固定列宽，字段间 2+ 空格分隔):
        AP Name  IP  Mac  Radio1...  Radio2...  Time  State
    """
    rows = []
    in_table = False
    headers_passed = False

    for line in text.splitlines():
        # 去掉时间戳，保留原始空格用于列位置判断
        raw = re.sub(r'^\[\d{2}:\d{2}:\d{2}\]', '', line)
        content = raw.strip()

        if 'AP Name' in content and 'IP Address' in content and 'Mac Address' in content:
            in_table = True
            headers_passed = False
            continue

        if in_table:
            # 分隔线
            if re.match(r'^[- ]+$', content):
                headers_passed = True
                continue

            # 表结束
            if not content or content.startswith(device_name + '#'):
                in_table = False
                continue

            if not headers_passed:
                continue

            # 跳过 AP 名列 (前40字符) 为空的行
            if not raw[:40].strip():
                continue

            # 用 2+ 空格切分主列
            fields = re.split(r'\s{2,}', content)
            if len(fields) < 3:
                continue

            ap_name = fields[0].strip()
            ip_raw = fields[1].strip()
            ip = ip_raw if ip_raw != '-' else ''

            # MAC 字段可能附带 Radio ID (e.g. "e05d.543f.2fe6 1")
            # 去掉末尾的 Radio ID
            mac_raw = fields[2].strip()
            mac = re.sub(r'\s+\S+$', '', mac_raw)

            # State 是整行最后一个单词
            state = content.split()[-1] if content.split() else ''

            if ap_name:
                rows.append({
                    '设备名': device_name,
                    'AP名': ap_name,
                    'IP': ip,
                    'Mac': mac,
                    'State': state,
                })
    return rows


def parse_log(filepath: str):
    """解析单个日志文件，返回 (product_rows, offline_rows)。"""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    device_name = extract_device_name(text)

    # Offline AP count
    offline_match = re.search(r'Offline AP number:\s*(\d+)', text)
    offline_count = int(offline_match.group(1)) if offline_match else None

    # 解析产品表
    product_rows = parse_product_table(text, device_name)
    for r in product_rows:
        r['设备名'] = device_name
        r['offline_count'] = offline_count

    if not product_rows and offline_count is not None:
        product_rows.append({
            '设备名': device_name,
            'offline_count': offline_count,
            'product_id': '',
            'hw_version': '',
            'count': '',
            'used_wtp': '',
        })

    # 解析离线AP明细表
    offline_rows = parse_offline_aps(text, device_name)

    return product_rows, offline_rows


def main():
    parser = argparse.ArgumentParser(description='解析锐捷AC日志，导出产品统计和离线AP明细')
    parser.add_argument('log_dir', nargs='?', default='.', help='日志文件所在目录 (默认当前目录)')
    parser.add_argument('-o', '--output', default='产品统计.csv', help='产品统计 CSV 输出路径')
    parser.add_argument('--offline', default='离线AP明细.csv', help='离线AP明细 CSV 输出路径')
    parser.add_argument('--glob', default='*.log', help='日志文件匹配模式 (默认 *.log)')
    args = parser.parse_args()

    if not os.path.isdir(args.log_dir):
        print(f"错误: 目录不存在 - {args.log_dir}", file=sys.stderr)
        sys.exit(1)

    import glob
    pattern = os.path.join(args.log_dir, args.glob)
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"未找到匹配 {pattern} 的文件", file=sys.stderr)
        sys.exit(1)

    print(f"找到 {len(files)} 个日志文件，开始解析...")

    all_products = []
    all_offline = []
    errors = []

    for i, fpath in enumerate(files, 1):
        try:
            prod_rows, off_rows = parse_log(fpath)
            all_products.extend(prod_rows)
            all_offline.extend(off_rows)
            basename = os.path.basename(fpath)
            device = prod_rows[0]['设备名'] if prod_rows else (off_rows[0]['设备名'] if off_rows else '?')
            offline = prod_rows[0]['offline_count'] if prod_rows else '?'
            # 截断长文件名显示
            short_name = basename[:50] + '...' if len(basename) > 50 else basename
            print(f"  [{i:4d}/{len(files)}] {short_name} -> {device}, offline={offline}, "
                  f"products={len(prod_rows)}, offline_aps={len(off_rows)}")
        except Exception as e:
            errors.append((os.path.basename(fpath), str(e)))
            print(f"  [{i:4d}/{len(files)}] {os.path.basename(fpath)[:50]}... -> 错误: {e}")

    # 写入产品统计 CSV
    prod_fields = ['设备名', 'offline_count', 'product_id', 'hw_version', 'count', 'used_wtp']
    with open(args.output, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=prod_fields)
        writer.writeheader()
        writer.writerows(all_products)
    print(f"\n产品统计: {len(all_products)} 行 -> {args.output}")

    # 写入离线AP明细 CSV
    off_fields = ['设备名', 'AP名', 'IP', 'Mac', 'State']
    with open(args.offline, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=off_fields)
        writer.writeheader()
        writer.writerows(all_offline)
    print(f"离线AP明细: {len(all_offline)} 行 -> {args.offline}")

    if errors:
        print(f"\n警告: {len(errors)} 个文件解析失败:")
        for fpath, err in errors:
            print(f"  {fpath}: {err}")


if __name__ == '__main__':
    main()
