# -*- coding: utf-8 -*-
import re
import csv
import os
from collections import defaultdict

# ================== 配置项 ==================
INPUT_DIR = "ssh_exec_results"                  # 当前目录（放所有.log文件）
OUTPUT_CSV = "接口统计.csv"
ENCODING = "gbk"                 # GBK编码，Excel打开无乱码
# ===========================================

all_device_data = []

def extract_device_name(log_content):
    """精准提取设备名（适配DXY-B-2F-POE-2#格式）"""
    # 匹配日志中单独一行的 "设备名#" 格式
    match = re.search(r"^([A-Za-z0-9\-]+)#\s*$", log_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "未知设备"

def parse_single_log(log_path):
    """解析单个.log文件，适配最新日志格式"""
    try:
        # 读取日志（兼容UTF-8/GBK，忽略特殊字符）
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            log_content = f.read()
        
        # 提取设备名
        device_name = extract_device_name(log_content)
        print(f"📄 解析中：{os.path.basename(log_path)} → 设备：{device_name}")

        # 初始化数据存储（所有字段默认空字符串）
        data = defaultdict(lambda: {
            "设备": device_name,
            "接口": "",
            "状态": "",
            "Vlan": "",
            "双工": "",
            "速率": "",
            "介质": "",
            "输入丢包": "",
            "输出丢包": "",
            "CRC错误": "",
            "光模块状态": "",
            "光模块温度(℃)": "",
            "电压(V)": "",
            "偏置电流(mA)": "",
            "RX功率(dBm)": "",
            "TX功率(dBm)": ""
        })

        # -------------------------- 1. 解析接口状态（适配MTGigabitEthernet/admin-down） --------------------------
        for line in log_content.splitlines():
            line = line.strip()
            # 跳过命令前缀行（=== 执行命令：xxx ===）
            if "=== 执行命令：" in line:
                continue
            
            # 匹配接口行格式：
            # MTGigabitEthernet 0/1  up  13  Full  2500M  copper
            # TenGigabitEthernet 0/25  admin-down  1  Unknown  Unknown  fiber
            match = re.match(
                r"^(MTGigabitEthernet|GigabitEthernet|TenGigabitEthernet|Mgmt)\s+(\d+/\d+|\d+)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)",
                line
            )
            if match:
                iface = f"{match.group(1)} {match.group(2)}"
                data[iface]["接口"] = iface
                data[iface]["状态"] = match.group(3)       # 支持up/down/admin-down
                data[iface]["Vlan"] = match.group(4)
                data[iface]["双工"] = match.group(5)       # 支持Full/Unknown
                data[iface]["速率"] = match.group(6)       # 支持2500M/10G/Unknown
                data[iface]["介质"] = match.group(7)       # copper/fiber

        # -------------------------- 2. 解析丢包数据（适配MTGigabitEthernet） --------------------------
        current_if = None
        for line in log_content.splitlines():
            line = line.strip()
            # 匹配接口名行：Interface : MTGigabitEthernet 0/1
            if "Interface :" in line:
                if_match = re.search(r"Interface : (.+)", line)
                if if_match:
                    current_if = if_match.group(1).strip()
                    continue
            
            # 匹配输入丢包：Input dropped packets                   : 0
            if current_if and "Input dropped packets" in line:
                drop_match = re.search(r":\s*(\d+)", line)
                if drop_match:
                    data[current_if]["输入丢包"] = drop_match.group(1)
            
            # 匹配输出丢包：Output dropped packets                  : 18
            if current_if and "Output dropped packets" in line:
                drop_match = re.search(r":\s*(\d+)", line)
                if drop_match:
                    data[current_if]["输出丢包"] = drop_match.group(1)

        # -------------------------- 3. 解析CRC错误（适配MT0/1 → MTGigabitEthernet 0/1） --------------------------
        for line in log_content.splitlines():
            line = line.strip()
            # 匹配CRC行：MT0/1           0                    0                    0                    0
            crc_match = re.match(r"^(MT|Gi|Te)(\d+/\d+|\d+)\s+\d+\s+(\d+)\s+\d+\s+\d+", line)
            if crc_match:
                prefix = crc_match.group(1)
                num = crc_match.group(2)
                crc_err = crc_match.group(3)
                
                # 转换简写为完整接口名
                if prefix == "MT":
                    iface = f"MTGigabitEthernet {num}"
                elif prefix == "Gi":
                    iface = f"GigabitEthernet {num}"
                elif prefix == "Te":
                    iface = f"TenGigabitEthernet {num}"
                else:
                    continue
                
                data[iface]["CRC错误"] = crc_err

        # -------------------------- 4. 解析光模块数据（适配多空格/[AP]后缀） --------------------------
        current_sfp_if = None
        for line in log_content.splitlines():
            line = line.strip()
            # 跳过空行和阈值行
            if not line or "Low Alarm" in line or "Diagnostic parameters threshold" in line:
                continue
            
            # 匹配光模块接口头：========Interface TenGigabitEthernet 0/30========
            sfp_if_match = re.match(r"=+Interface (TenGigabitEthernet \d+/\d+)=+", line)
            if sfp_if_match:
                current_sfp_if = sfp_if_match.group(1)
                data[current_sfp_if]["光模块状态"] = "待检测"
                continue
            
            # 匹配无模块：Interface TenGigabitEthernet 0/25 : the transceiver is absent!
            if current_sfp_if and "the transceiver is absent" in line:
                data[current_sfp_if]["光模块状态"] = "无模块"
                current_sfp_if = None
                continue
            
            # 匹配光功率数据行（适配多空格/[AP]后缀）：
            # 31(OK)          3.27(OK)        29.05(OK)           -4.12(OK)[AP]               -2.75(OK)
            sfp_data_match = re.match(
                r"^(\d+)\(OK\)\s+([\d.]+)\(OK\)\s+([\d.]+)\(OK\)\s+([-\d.]+)\(OK\)(?:\[\w+\])?\s+([-\d.]+)\(OK\)",
                line
            )
            if current_sfp_if and sfp_data_match:
                data[current_sfp_if]["光模块状态"] = "正常"
                data[current_sfp_if]["光模块温度(℃)"] = sfp_data_match.group(1)    # 31
                data[current_sfp_if]["电压(V)"] = sfp_data_match.group(2)         # 3.27
                data[current_sfp_if]["偏置电流(mA)"] = sfp_data_match.group(3)    # 29.05
                data[current_sfp_if]["RX功率(dBm)"] = sfp_data_match.group(4)     # -4.12（自动去[AP]）
                data[current_sfp_if]["TX功率(dBm)"] = sfp_data_match.group(5)     # -2.75
                current_sfp_if = None  # 重置，准备下一个接口

        # -------------------------- 5. 补充光模块状态（未检测的接口） --------------------------
        for iface in data:
            if not data[iface]["光模块状态"]:
                if "TenGigabitEthernet" in iface:
                    data[iface]["光模块状态"] = "未检测"
                elif "MTGigabitEthernet" in iface or "GigabitEthernet" in iface:
                    data[iface]["光模块状态"] = "电口（无模块）"
                elif "Mgmt" in iface:
                    data[iface]["光模块状态"] = "管理口"

        # -------------------------- 6. 将数据加入全局列表 --------------------------
        # 按接口名排序（MT0/1 → MT0/30 → Te0/25...）
        sorted_ifaces = sorted(data.keys(), key=lambda x: (
            x.split()[0], 
            int(x.split()[1].split("/")[0]) if "/" in x.split()[1] else 0,
            int(x.split()[1].split("/")[1]) if "/" in x.split()[1] else int(x.split()[1]) if x.split()[1].isdigit() else 0
        ))
        for iface in sorted_ifaces:
            all_device_data.append(data[iface])

    except Exception as e:
        print(f"❌ 解析 {os.path.basename(log_path)} 失败：{str(e)[:80]}")

def main():
    """主函数：批量解析所有.log文件并生成CSV"""
    # 1. 获取所有.log文件
    log_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".log")]
    if not log_files:
        print("⚠️ 当前目录未找到任何.log文件")
        return
    
    print(f"🔍 找到 {len(log_files)} 个日志文件，开始解析...")
    print("-" * 60)

    # 2. 逐个解析日志
    for log_file in log_files:
        log_path = os.path.join(INPUT_DIR, log_file)
        parse_single_log(log_path)

    # 3. 写入CSV文件
    if all_device_data:
        # 定义表格字段顺序（重点字段前置）
        headers = [
            "设备", "接口", "状态", "Vlan", "双工", "速率", "介质",
            "输入丢包", "输出丢包", "CRC错误",
            "光模块状态", "光模块温度(℃)", "电压(V)", "偏置电流(mA)",
            "RX功率(dBm)", "TX功率(dBm)"
        ]
        with open(OUTPUT_CSV, "w", encoding=ENCODING, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_device_data)
        
        # 统计关键数据
        total_if = len(all_device_data)
        up_if = len([row for row in all_device_data if row["状态"] in ["up", "Admin-up"]])
        admin_down_if = len([row for row in all_device_data if row["状态"] == "admin-down"])
        sfp_normal = len([row for row in all_device_data if row["光模块状态"] == "正常"])
        
        print("\n" + "=" * 60)
        print(f"🎉 解析完成！")
        print(f"📊 统计汇总：")
        print(f"   • 总接口数：{total_if} 个")
        print(f"   • Up状态接口：{up_if} 个")
        print(f"   • Admin-down状态接口：{admin_down_if} 个")
        print(f"   • 正常光模块接口：{sfp_normal} 个")
        print(f"📁 输出文件：{os.path.abspath(OUTPUT_CSV)}")
        print(f"🔤 编码格式：{ENCODING}（Excel打开无乱码）")
    else:
        print("⚠️ 未解析到任何有效接口数据")

if __name__ == "__main__":
    main()