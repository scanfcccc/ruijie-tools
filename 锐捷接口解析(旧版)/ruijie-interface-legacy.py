#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
锐捷交换机日志解析脚本 v5 增强版
增加：自动生成总汇总 ALL_interface_summary.csv
默认：无参数=当前目录所有log，输出到./summary/
"""
import os
import re
import csv
import glob
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class InterfaceInfo:
    interface: str
    vlan: str
    rx_power: str
    tx_power: str
    has_optical: bool
    device_ip: str = ""
    device_name: str = ""
    serial: str = ""
    inspect_time: str = ""

def extract_device_info(filename: str) -> dict:
    info = {'ip': '', 'device_name': '', 'serial': '', 'time': ''}
    ip_match = re.search(r'地址\((\d+\.\d+\.\d+\.\d+)\)', filename)
    if ip_match:
        info['ip'] = ip_match.group(1)
    dev_match = re.search(r'设备名\(([^)]+)\)', filename)
    if dev_match:
        info['device_name'] = dev_match.group(1)
    sn_match = re.search(r'SN\(([^)]+)\)', filename)
    if sn_match:
        info['serial'] = sn_match.group(1)
    time_match = re.search(r'巡检时间\(([^)]+)\)', filename)
    if time_match:
        info['time'] = time_match.group(1)
    return info

def parse_interface_vlan(content: str) -> Dict[str, str]:
    interface_vlan = {}
    iface_start_pattern = r'interface ((?:\d+GigabitEthernet|TenGigabitEthernet|GigabitEthernet|Ethernet)\s+\d+/\d+(?:/\d+)?)'
    for match in re.finditer(iface_start_pattern, content):
        iface_name = match.group(1).strip()
        start_pos = match.end()
        next_iface = re.search(r'\ninterface\s|^\s*!\s*$', content[start_pos:], re.MULTILINE)
        if next_iface:
            config = content[start_pos:start_pos + next_iface.start()]
        else:
            config = content[start_pos:start_pos + 500]
        iface_name = re.sub(r'\s+', ' ', iface_name)
        vlan_match = re.search(r'switchport access vlan (\d+)', config)
        if vlan_match:
            interface_vlan[iface_name] = vlan_match.group(1)
        else:
            trunk_match = re.search(r'switchport mode trunk', config)
            interface_vlan[iface_name] = 'trunk' if trunk_match else 'N/A'
    return interface_vlan

def parse_optical_power(content: str) -> Dict[str, Tuple[str, str]]:
    optical = {}
    iface_pattern = r'========Interface\s+((?:\d+GigabitEthernet|TenGigabitEthernet|GigabitEthernet|Ethernet)\s+\d+/\d+(?:/\d+)?)========\s*(.*?)(?========Interface|PJXRMYY-|\!-{3}cmd|$)'
    for match in re.finditer(iface_pattern, content, re.DOTALL):
        iface_name = match.group(1).strip()
        block = match.group(2)
        iface_name = re.sub(r'\s+', ' ', iface_name)
        if 'transceiver is absent' in block:
            continue
        if "doesn't support DDM" in block:
            continue
        diag_match = re.search(
            r'Temp\(Celsius\)\s+Voltage\(V\)\s+Bias\(mA\)\s+RX\s+power\(dBm\)\s+TX\s+power\(dBm\)\s*\n\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)',
            block
        )
        if diag_match:
            rx_val = diag_match.group(4)
            tx_val = diag_match.group(5)
            rx_clean = re.sub(r'\(.*?\)', '', rx_val).replace('[OMA]', '').replace('[AP]', '').strip()
            tx_clean = re.sub(r'\(.*?\)', '', tx_val).replace('[OMA]', '').replace('[AP]', '').strip()
            try:
                rx_float = float(rx_clean)
                tx_float = float(tx_clean)
                if -50 <= rx_float <= 10 and -50 <= tx_float <= 10:
                    optical[iface_name] = (f'{rx_clean} dBm', f'{tx_clean} dBm')
            except:
                pass
    return optical

def parse_log_file(filepath: str) -> List[InterfaceInfo]:
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    dev_info = extract_device_info(os.path.basename(filepath))
    vlan_map = parse_interface_vlan(content)
    optical = parse_optical_power(content)
    results = []
    for iface, vlan in vlan_map.items():
        if iface in optical:
            rx, tx = optical[iface]
            has_optical = True
        else:
            rx, tx = 'N/A', 'N/A'
            has_optical = False
        info = InterfaceInfo(
            interface=iface,
            vlan=vlan,
            rx_power=rx,
            tx_power=tx,
            has_optical=has_optical,
            device_ip=dev_info.get('ip', 'N/A'),
            device_name=dev_info.get('device_name', 'N/A'),
            serial=dev_info.get('serial', 'N/A'),
            inspect_time=dev_info.get('time', 'N/A')
        )
        results.append(info)
    return results

def write_total_summary(all_interfaces: List[InterfaceInfo], output_dir: str):
    """生成总汇总表 ALL_interface_summary.csv"""
    total_path = os.path.join(output_dir, 'ALL_interface_summary.csv')
    fieldnames = [
        '设备IP', '设备名', '序列号', '巡检时间',
        '接口', 'VLAN', 'RX光功率(dBm)', 'TX光功率(dBm)', '是否有光功率'
    ]
    with open(total_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in all_interfaces:
            writer.writerow({
                '设备IP': item.device_ip,
                '设备名': item.device_name,
                '序列号': item.serial,
                '巡检时间': item.inspect_time,
                '接口': item.interface,
                'VLAN': item.vlan,
                'RX光功率(dBm)': item.rx_power,
                'TX光功率(dBm)': item.tx_power,
                '是否有光功率': '是' if item.has_optical else '否'
            })
    print(f"\n✅ 总汇总表已生成：{total_path}")

def process_directory(input_dir: str, output_dir: str = None):
    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), 'summary')
    os.makedirs(output_dir, exist_ok=True)
    log_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(('.log', '.txt'))]
    if not log_files:
        print(f"在 {input_dir} 中未找到日志文件")
        return
    print(f"找到 {len(log_files)} 个日志文件")
    print("=" * 80)
    total_interfaces = 0
    files_processed = 0
    optical_count_total = 0
    all_interface_list = []  # 用于总汇总

    for filepath in log_files:
        filename = os.path.basename(filepath)
        print(f"\n处理：{filename[:70]}...")
        try:
            interfaces = parse_log_file(filepath)
        except Exception as e:
            print(f"  解析失败：{e}")
            continue
        if not interfaces:
            print(f"  未找到接口信息")
            continue
        files_processed += 1
        total_interfaces += len(interfaces)
        optical_count = sum(1 for i in interfaces if i.has_optical)
        optical_count_total += optical_count
        all_interface_list.extend(interfaces)  # 加入总列表

        dev_info = extract_device_info(filename)
        if dev_info['ip']:
            output_name = f"{dev_info['ip']}_interface_summary.csv"
        else:
            output_name = filename[:80] + '_summary.csv'
        output_path = os.path.join(output_dir, output_name)

        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['设备 IP', dev_info.get('ip', 'N/A')])
            writer.writerow(['设备名', dev_info.get('device_name', 'N/A')])
            writer.writerow(['序列号', dev_info.get('serial', 'N/A')])
            writer.writerow(['巡检时间', dev_info.get('time', 'N/A')])
            writer.writerow([])
            writer.writerow(['接口', 'VLAN', 'RX 光功率 (dBm)', 'TX 光功率 (dBm)', '是否有光功率'])
            def sort_key(iface):
                match = re.search(r'((?:\d+Gigabit)?Ethernet)\s+(\d+)/(\d+)(?:/(\d+))?', iface.interface)
                if match:
                    iface_type = match.group(1)
                    slot = int(match.group(2))
                    port = int(match.group(3))
                    subport = int(match.group(4)) if match.group(4) else 0
                    type_order = {'GigabitEthernet': 0, 'TenGigabitEthernet': 1, '25GigabitEthernet': 2}
                    return (type_order.get(iface_type, 5), slot, subport, port)
                return (99, 0, 0, 0)
            sorted_ifaces = sorted(interfaces, key=sort_key)
            for iface in sorted_ifaces:
                writer.writerow([
                    iface.interface, iface.vlan, iface.rx_power, iface.tx_power,
                    '是' if iface.has_optical else '否'
                ])
        print(f"  接口数：{len(interfaces)} | 光功率：{optical_count}")
        print(f"  已保存：{output_path}")

    # 生成总汇总
    if all_interface_list:
        write_total_summary(all_interface_list, output_dir)

    print("\n" + "=" * 80)
    print(f"处理完成：{files_processed} 个文件，共 {total_interfaces} 个接口")
    print(f"有光功率数据的接口总数：{optical_count_total}")

def test_with_sample(filepath: str):
    print(f"测试文件：{filepath}")
    print("=" * 80)
    dev_info = extract_device_info(os.path.basename(filepath))
    print(f"设备信息:")
    print(f"  IP: {dev_info.get('ip', 'N/A')}")
    print(f"  设备名：{dev_info.get('device_name', 'N/A')}")
    print(f"  SN: {dev_info.get('serial', 'N/A')}")
    print(f"  时间：{dev_info.get('time', 'N/A')}")
    print()
    interfaces = parse_log_file(filepath)
    optical_ifaces = [i for i in interfaces if i.has_optical]
    other_ifaces = [i for i in interfaces if not i.has_optical]
    if optical_ifaces:
        print(f"【光功率数据】({len(optical_ifaces)} 个接口):")
        print(f"{'接口':<35} {'VLAN':<10} {'RX':<18} {'TX':<18}")
        print("-" * 81)
        for iface in optical_ifaces:
            print(f"{iface.interface:<35} {iface.vlan:<10} {iface.rx_power:<18} {iface.tx_power:<18}")
        print()
    if other_ifaces:
        print(f"【无光功率数据】({len(other_ifaces)} 个接口):")
        print(f"{'接口':<35} {'VLAN':<10}")
        print("-" * 45)
        for iface in other_ifaces[:15]:
            print(f"{iface.interface:<35} {iface.vlan:<10}")
        if len(other_ifaces) > 15:
            print(f"... 还有 {len(other_ifaces) - 15} 个")
        print()
    print(f"总接口数：{len(interfaces)}")
    print(f"  - 有光功率：{len(optical_ifaces)}")
    print(f"  - 无光功率：{len(other_ifaces)}")

if __name__ == '__main__':
    import sys
    input_path = os.getcwd()
    output_dir = os.path.join(os.getcwd(), 'summary')
    is_test = False
    test_file = ""

    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            is_test = True
            if len(sys.argv) >= 3:
                test_file = sys.argv[2]
            else:
                print("错误：--test 需要指定文件")
                sys.exit(1)
        else:
            input_path = sys.argv[1]
            if '-o' in sys.argv:
                o_idx = sys.argv.index('-o')
                if o_idx + 1 < len(sys.argv):
                    output_dir = sys.argv[o_idx + 1]

    if is_test:
        if os.path.isfile(test_file):
            test_with_sample(test_file)
        else:
            print(f"文件不存在：{test_file}")
            sys.exit(1)
    else:
        if os.path.isfile(input_path):
            test_with_sample(input_path)
        else:
            process_directory(input_path, output_dir)

    if len(sys.argv) == 1:
        print("\n提示：默认处理当前目录所有log，输出到 ./summary/")
        print("用法：python parse.py")
        print("指定目录：python parse.py logs")
        print("测试单文件：python parse.py --test xxx.log")