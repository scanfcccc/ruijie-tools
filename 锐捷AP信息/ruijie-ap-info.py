#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
锐捷交换机日志解析脚本
从 LLDP 日志中提取 AP 信息：交换机接口、AP MAC、接口 VLAN
VLAN 信息来自 "sh int sta" 命令输出
"""

import re
import os
import glob
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class APInfo:
    """AP 信息数据类"""
    switch_name: str      # 交换机名称
    interface: str        # 交换机接口 (如 GigabitEthernet 0/11)
    ap_mac: str          # AP MAC 地址 (Chassis ID)
    ap_name: str         # AP 名称 (System name)
    vlan_id: str         # 接口 VLAN ID (来自 sh int sta)
    is_ap: bool          # 是否为 AP 设备


def detect_encoding(filepath: str) -> str:
    """检测文件编码"""
    with open(filepath, 'rb') as f:
        header = f.read(4)
        # UTF-16 LE BOM
        if header.startswith(b'\xff\xfe'):
            return 'utf-16-le'
        # UTF-16 BE BOM
        if header.startswith(b'\xfe\xff'):
            return 'utf-16-be'
        # UTF-8 BOM
        if header.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
    return 'utf-8'


def parse_interface_status(content: str) -> Dict[str, str]:
    """
    解析 'sh int sta' 命令输出，返回接口到 VLAN 的映射
    格式示例:
    Interface                                Status    Vlan   Duplex   Speed     Type  
    ---------------------------------------- --------  ----   -------  --------- ------
    GigabitEthernet 0/11                     up        248    Full     1000M     copper
    """
    interface_vlan = {}
    
    # 匹配接口状态行
    # 接口名 + 空格 + 状态 + 空格 + VLAN
    pattern = r'^(GigabitEthernet\s+\d+/\d+)\s+\S+\s+(\d+)\s+'
    
    for line in content.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            interface = match.group(1)
            vlan = match.group(2)
            interface_vlan[interface] = vlan
    
    return interface_vlan


def parse_log_file(filepath: str) -> List[APInfo]:
    """解析单个日志文件，返回 AP 信息列表"""
    ap_list = []
    
    # 从文件名提取交换机名称
    filename = os.path.basename(filepath)
    switch_name = filename.replace('.log', '')
    
    # 检测并读取文件
    try:
        encoding = detect_encoding(filepath)
        with open(filepath, 'r', encoding=encoding, errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"读取文件失败 {filepath}: {e}")
        return ap_list
    
    # 先解析接口 VLAN 映射
    interface_vlan_map = parse_interface_status(content)
    print(f"  解析到 {len(interface_vlan_map)} 个接口的 VLAN 信息")
    
    # 提取所有 LLDP 邻居信息块
    lldp_pattern = r'LLDP neighbor-information of port \[(.*?)\](.*?)(?=LLDP neighbor-information|PJXRMYY|Connection closed|\[END\]|$)'
    lldp_blocks = re.findall(lldp_pattern, content, re.DOTALL)
    
    for interface, block in lldp_blocks:
        # 提取 Chassis ID (AP 的 MAC 地址)
        chassis_match = re.search(r'Chassis ID\s*:\s*(\S+)', block)
        ap_mac = chassis_match.group(1) if chassis_match else ''
        
        # 提取 System name (AP 名称)
        sysname_match = re.search(r'System name\s*:\s*(\S+)', block)
        ap_name = sysname_match.group(1) if sysname_match else ''
        
        # 判断是否为 AP 设备 (System description 包含 "AP" 或 "WLAN Access Point")
        is_ap = bool(re.search(r'(AP\d|WLAN Access Point|Ruijie AP)', block, re.IGNORECASE))
        
        # 从接口状态映射中获取 VLAN ID
        vlan_id = interface_vlan_map.get(interface, '')
        
        # 只保留 AP 设备的信息
        if is_ap and ap_mac:
            ap_info = APInfo(
                switch_name=switch_name,
                interface=interface,
                ap_mac=ap_mac,
                ap_name=ap_name,
                vlan_id=vlan_id,
                is_ap=True
            )
            ap_list.append(ap_info)
    
    return ap_list


def parse_all_logs(directory: str) -> List[APInfo]:
    """解析目录下所有 .log 文件"""
    all_ap_info = []
    
    log_files = glob.glob(os.path.join(directory, '*.log'))
    
    if not log_files:
        print(f"在目录 {directory} 中未找到 .log 文件")
        return all_ap_info
    
    print(f"找到 {len(log_files)} 个日志文件:")
    for lf in log_files:
        print(f"  - {os.path.basename(lf)}")
    print()
    
    for log_file in log_files:
        print(f"正在解析：{os.path.basename(log_file)}")
        ap_list = parse_log_file(log_file)
        print(f"  发现 {len(ap_list)} 个 AP")
        all_ap_info.extend(ap_list)
    
    return all_ap_info


def print_table(ap_list: List[APInfo]):
    """以表格形式打印 AP 信息"""
    if not ap_list:
        print("\n未找到 AP 信息")
        return
    
    print("\n" + "=" * 120)
    print("AP 信息统计表")
    print("=" * 120)
    
    # 表头
    header = f"{'交换机名称':<50} {'接口':<25} {'AP MAC':<20} {'AP 名称':<25} {'VLAN':<10}"
    print(header)
    print("-" * 120)
    
    # 数据行
    for ap in ap_list:
        row = f"{ap.switch_name:<50} {ap.interface:<25} {ap.ap_mac:<20} {ap.ap_name:<25} {ap.vlan_id:<10}"
        print(row)
    
    print("-" * 120)
    print(f"总计：{len(ap_list)} 个 AP")
    print("=" * 120)


def save_to_csv(ap_list: List[APInfo], output_path: str):
    """保存为 CSV 文件"""
    import csv
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        # 表头
        writer.writerow(['交换机名称', '接口', 'AP MAC', 'AP 名称', 'VLAN ID'])
        # 数据
        for ap in ap_list:
            writer.writerow([ap.switch_name, ap.interface, ap.ap_mac, ap.ap_name, ap.vlan_id])
    
    print(f"\nCSV 文件已保存：{output_path}")


def main():
    """主函数"""
    # 默认搜索 Downloads 目录
    search_dirs = [
        '/home/admin/Downloads',
        '/home/admin/openclaw/workspace',
        '.'
    ]
    
    # 查找包含 .log 文件的目录
    target_dir = None
    for dir_path in search_dirs:
        if os.path.exists(dir_path):
            log_files = glob.glob(os.path.join(dir_path, '*.log'))
            if log_files:
                target_dir = dir_path
                break
    
    if not target_dir:
        print("未找到包含 .log 文件的目录")
        print("请将日志文件放在以下目录之一:")
        for d in search_dirs:
            print(f"  - {d}")
        return
    
    print(f"\n搜索目录：{target_dir}\n")
    
    # 解析所有日志
    ap_list = parse_all_logs(target_dir)
    
    # 打印表格
    print_table(ap_list)
    
    # 保存为 CSV
    if ap_list:
        csv_path = os.path.join(target_dir, 'ap_info_summary.csv')
        save_to_csv(ap_list, csv_path)


if __name__ == '__main__':
    main()
