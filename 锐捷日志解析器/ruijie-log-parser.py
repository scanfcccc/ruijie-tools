#!/usr/bin/env python3
"""
锐捷交换机巡检日志 → 设备接口VLAN明细CSV

提取：设备信息 / 每接口 VLAN 分配 / VLAN 名称映射 / LLDP 邻居 / 光模块光功率
输出：CSV 到输入目录
用法：python parse_logs.py [目录]   # 默认当前目录
"""

import os, re, json, csv, sys
from pathlib import Path


# 设备基本信息 
def parse_device_info(log_path):
    info = {"name": "", "model": "", "ip": "", "serial": "", "version": "", "uptime": ""}
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.lstrip("\ufeff").strip()
                if line.startswith("_deviceInfo_:"):
                    data = json.loads(line[len("_deviceInfo_:"):])
                    info["name"] = data.get("name", "")
                    info["model"] = data.get("model", "")
                    info["ip"] = data.get("ip", "")
                    info["serial"] = data.get("serialNumber", "")
                    info["version"] = data.get("softwareVersion", "")
                    info["uptime"] = data.get("upTime", "")
                    break
    except Exception:
        pass
    return info


# VLAN 名称映射 
def parse_vlan_names(log_path):
    vlan_map = {}
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        for m in re.finditer(r"#show vlan\n", content):
            section = content[m.end():]
            lines = section.split("\n")
            in_table = False
            for line in lines:
                s = line.rstrip()
                if s.startswith("VLAN Name") and "Status" in s:
                    in_table = True
                    continue
                if not in_table:
                    continue
                if s.startswith("---"):
                    continue
                if s.endswith("#") or "#!---cmd" in s:
                    break
                parts = s.split(None, 2)
                if len(parts) >= 2 and parts[0].isdigit():
                    vlan_map[int(parts[0])] = parts[1]
            if vlan_map:
                break
    except Exception:
        pass
    return vlan_map


# 接口 VLAN 状态 
def parse_interfaces_status(log_path):
    rows = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        pos = content.find("#show interfaces status\n")
        while pos >= 0:
            section = content[pos + len("#show interfaces status\n"):]
            lines = section.split("\n")
            found_header = False
            parsed = []
            for line in lines:
                s = line.rstrip()
                if s.startswith("Interface") and "Status" in s and "Vlan" in s:
                    found_header = True
                    continue
                if not found_header:
                    if "#" in s:
                        break
                    continue
                if s.startswith("---"):
                    continue
                if s.endswith("#") or "#!---cmd" in s:
                    break
                if not s:
                    break
                parts = re.split(r"\s{2,}", s)
                if len(parts) >= 5:
                    parsed.append({
                        "interface": parts[0].strip(),
                        "status": parts[1].strip(),
                        "vlan": parts[2].strip(),
                        "duplex": parts[3].strip(),
                        "speed": parts[4].strip(),
                        "type": parts[5].strip() if len(parts) > 5 else "",
                    })
            if parsed:
                rows = parsed
                break
            pos = content.find("#show interfaces status\n", pos + 1)
    except Exception:
        pass
    return rows


# 接口名标准化 
def _normalize_intf(name):
    name = name.replace(" ", "")
    m = {
        "TenGigabitEthernet": "Te", "GigabitEthernet": "Gi",
        "TFGigabitEthernet": "TF", "FortyGigabitEthernet": "Fo",
        "FastEthernet": "Fa", "AggregatePort": "AP",
    }
    for full, short in m.items():
        if name.startswith(full):
            return short + name[len(full):]
        if name.startswith(short):
            return short + name[len(short):]
    return name


#LLDP 邻居
def parse_lldp_neighbors(log_path):
    neighbors = {}
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        for marker in ["#show lldp neighbors\n", "#show lldp neighbors enhance\n"]:
            pos = content.find(marker)
            if pos < 0:
                continue
            section = content[pos + len(marker):]
            lines = section.split("\n")
            in_table = False
            for line in lines:
                s = line.rstrip()
                if "System Name" in s and "Local Intf" in s:
                    in_table = True
                    continue
                if not in_table:
                    continue
                if s.startswith("---"):
                    continue
                if s.endswith("#") or "#!---cmd" in s:
                    break
                if not s.strip():
                    break
                parts = s.split()
                if len(parts) >= 2:
                    local_if = ""
                    for p in parts[1:]:
                        if re.match(r"^[A-Z][A-Za-z]*\d+/\d+", p):
                            local_if = _normalize_intf(p)
                            break
                    if local_if:
                        neighbors[local_if] = parts[0]
    except Exception:
        pass
    return neighbors


# 光模块光功率 
def parse_transceiver_diag(log_path):
    """
    解析光模块 DDM 诊断信息
    返回 {normalized_intf: {"rx_power": "", "tx_power": "", "temp": "", "bias": ""}}

    匹配两种场景：
      - "the transceiver is absent!" → 留空
      - "This module doesn't support DDM!" → 标记 N/A
      - 有 DDM 数据：从数据行提取
    """
    diag = {}
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # 同时匹配 show interfaces transceiver 和
        # show interfaces transceiver diagnosis 的输出区域
        # 定位到任意一个命令后的内容
        for cmd_marker in ["#show interfaces transceiver\n",
                           "#show interfaces transceiver diagnosis\n"]:
            pos = content.find(cmd_marker)
            if pos >= 0:
                section = content[pos + len(cmd_marker):]
                lines = section.split("\n")
                current_intf = ""
                skip_until_separator = False

                for line in lines:
                    s = line.rstrip()

                    # 遇到下一个命令，结束
                    if s.endswith("#") or "#!---cmd" in s:
                        break

                    # 接口分隔线
                    m_intf = re.match(r"={8,}Interface\s+(.+?)={8,}", s)
                    if m_intf:
                        current_intf = _normalize_intf(m_intf.group(1))
                        # 初始化
                        if current_intf not in diag:
                            diag[current_intf] = {
                                "rx_power": "", "tx_power": "",
                                "temp": "", "bias": "", "status": ""
                            }
                        skip_until_separator = False
                        continue

                    if not current_intf:
                        continue

                    # transceiver absent
                    if "transceiver is absent" in s:
                        diag[current_intf]["status"] = "absent"
                        current_intf = ""
                        continue

                    # 不支持 DDM
                    if "doesn't support DDM" in s:
                        diag[current_intf]["status"] = "no_ddm"
                        current_intf = ""
                        continue

                    # DDM 数据行：Temp Voltage Bias RX TX
                    # 格式：44(OK) 3.26(OK) 42.09(OK) -3.72(OK)[AP] -3.38(OK)
                    if re.match(r"^-?\d+\.?\d*\(OK\).+", s) and not s.startswith("Temp"):
                        # 用空白分割，取第1、3、4、5个值
                        vals = s.split()
                        if len(vals) >= 5:
                            # 提取数字部分（去掉 (OK) 后缀）
                            def clean(v):
                                return re.sub(r"\(.*?\)|\[.*?\]", "", v).strip()
                            diag[current_intf]["temp"] = clean(vals[0])
                            diag[current_intf]["bias"] = clean(vals[2])
                            diag[current_intf]["rx_power"] = clean(vals[3])
                            diag[current_intf]["tx_power"] = clean(vals[4])
                            diag[current_intf]["status"] = "ok"

                # 只要找到了数据（无论多少），就退出
                if any(v.get("status") in ("ok", "no_ddm", "absent") for v in diag.values()):
                    break
    except Exception:
        pass
    return diag


#  主流程 
def main():
    if len(sys.argv) > 1:
        input_dir = Path(sys.argv[1])
    else:
        input_dir = Path.cwd()

    if not input_dir.is_dir():
        print(f"错误：目录不存在 {input_dir}")
        sys.exit(1)

    files = sorted(input_dir.glob("*.txt")) + sorted(input_dir.glob("*.log"))
    if not files:
        print(f"在 {input_dir} 中未找到 .txt 或 .log 文件")
        sys.exit(1)

    all_rows = []
    errors = []

    for fp in files:
        print(f"处理: {fp.name}", end=" ... ", flush=True)
        dev = parse_device_info(fp)
        vlan_map = parse_vlan_names(fp)
        interfaces = parse_interfaces_status(fp)
        neighbors = parse_lldp_neighbors(fp)
        transceivers = parse_transceiver_diag(fp)

        if not interfaces:
            errors.append(fp.name)
            print("无接口数据，跳过")
            continue

        for iface in interfaces:
            vlan = iface["vlan"]
            vlan_int = int(vlan) if vlan.isdigit() else 0
            norm_name = _normalize_intf(iface["interface"])
            tcvr = transceivers.get(norm_name, {})

            all_rows.append({
                "设备名": dev["name"],
                "设备型号": dev["model"],
                "设备IP": dev["ip"],
                "序列号": dev["serial"],
                "软件版本": dev["version"],
                "上线时间": dev["uptime"],
                "接口名": iface["interface"],
                "链路状态": iface["status"],
                "VLAN ID": vlan,
                "VLAN名称": vlan_map.get(vlan_int, ""),
                "速率": iface["speed"],
                "双工": iface["duplex"],
                "介质类型": iface["type"],
                "LLDP邻居": neighbors.get(norm_name, ""),
                "光模块状态": tcvr.get("status", ""),
                "温度(C)": tcvr.get("temp", ""),
                "偏置电流(mA)": tcvr.get("bias", ""),
                "收光功率(dBm)": tcvr.get("rx_power", ""),
                "发光功率(dBm)": tcvr.get("tx_power", ""),
            })

        print(f"{len(interfaces)} 个接口")

    csv_path = input_dir / "设备接口VLAN明细.csv"
    fields = [
        "设备名", "设备型号", "设备IP", "序列号", "软件版本", "上线时间",
        "接口名", "链路状态", "VLAN ID", "VLAN名称",
        "速率", "双工", "介质类型",
        "LLDP邻居",
        "光模块状态", "温度(C)", "偏置电流(mA)", "收光功率(dBm)", "发光功率(dBm)",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    print(f"\n====== 汇总 ======")
    print(f"文件数:   {len(files)}")
    print(f"成功:     {len(files) - len(errors)}")
    print(f"接口行数: {len(all_rows)}")
    print(f"失败:     {len(errors)}")
    print(f"输出:     {csv_path}")
    if errors:
        print(f"\n失败文件：")
        for e in errors:
            print(f"  {e}")


if __name__ == "__main__":
    main()
