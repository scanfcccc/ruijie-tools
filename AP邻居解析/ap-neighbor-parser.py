import os
import re
import csv

def parse_switch_logs():
    current_dir = "."
    results = []

    # 获取当前目录下所有的 txt 或 log 文件
    files = [f for f in os.listdir(current_dir) if f.endswith('.txt') or f.endswith('.log')]

    if not files:
        print("当前目录下未找到 .txt 或 .log 文件！")
        return

    print(f"正在处理 {len(files)} 个日志文件...\n")

    for filename in files:
        # 提取交换机名称 (兼容日志文件名中的下划线时间戳，例如把 PJX..._2026-04... 截断)
        switch_name = filename.split('_')[0] if '_' in filename else filename.rsplit('.', 1)[0]
        
        filepath = os.path.join(current_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"读取文件 {filename} 失败: {e}")
            continue

        # 1. 提取接口 VLAN (解析 show interfaces status)
        vlan_map = {}
        # 匹配诸如: GigabitEthernet 0/17    up      248    Full
        int_sta_pattern = re.compile(
            r"(GigabitEthernet\s*\d+/\d+|TenGigabitEthernet\s*\d+/\d+|FastEthernet\s*\d+/\d+)\s+(?:up|down)\s+(\d+)", 
            re.IGNORECASE
        )
        for match in int_sta_pattern.finditer(content):
            port = match.group(1).strip()
            port = re.sub(r'\s+', ' ', port) # 规范化空格，确保 "GigabitEthernet 0/17" 格式统一
            vlan = match.group(2)
            vlan_map[port] = vlan

        # 2. 提取 AP 邻居信息 (解析 show lldp neighbors detail)
        # 根据 LLDP 端口分隔符切分文本块
        lldp_blocks = content.split("LLDP neighbor-information of port [")
        
        for block in lldp_blocks[1:]:
            lines = block.splitlines()
            if not lines: continue
            
            # 提取端口名称 (例如 GigabitEthernet 0/17)
            port_match = re.search(r"^(.*?)\]", lines[0])
            if not port_match: continue
            port_name = port_match.group(1).strip()
            port_name = re.sub(r'\s+', ' ', port_name)

            mac = "Unknown"
            is_ap = False

            # 在单个端口的 LLDP 信息中提取所需字段
            for line in lines:
                line_upper = line.upper()
                
                # 匹配 Chassis ID 获取 MAC 地址 (规避 "Chassis ID type" 行)
                if "CHASSIS ID" in line_upper and "MAC" not in line_upper:
                    mac_match = re.search(r"Chassis ID\s+:\s+([a-fA-F0-9\.\-]+)", line)
                    if mac_match:
                        mac = mac_match.group(1)
                        
                # 通过系统能力(WLAN Access Point)或描述字段精准判断是否为 AP
                if "WLAN ACCESS POINT" in line_upper:
                    is_ap = True
                elif "SYSTEM DESCRIPTION" in line_upper and " AP" in line_upper:
                    is_ap = True

            # 如果确认是对接的 AP，则将收集到的信息组装
            if is_ap:
                vlan = vlan_map.get(port_name, "Unknown")
                results.append({
                    "交换机名称": switch_name,
                    "AP接口": port_name,
                    "AP MAC地址": mac,
                    "接口VLAN": vlan
                })

    # 3. 输出为 CSV 文件
    output_file = "AP_Info_Summary.csv"
    if results:
        # 使用 utf-8-sig 编码，确保直接双击用 Excel 打开时中文不乱码
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=["交换机名称", "AP接口", "AP MAC地址", "接口VLAN"])
            writer.writeheader()
            writer.writerows(results)
        print(f"✅ 统计完成！共提取到 {len(results)} 个 AP 的信息。")
        print(f"📁 结果已自动保存为当前目录下的表单: {output_file}")
    else:
        print("⚠️ 未在日志文件中发现任何 AP 邻居信息，请检查日志中是否包含完整的 sh lldp nei de 信息。")

if __name__ == "__main__":
    parse_switch_logs()