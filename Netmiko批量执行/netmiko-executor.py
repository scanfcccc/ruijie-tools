# 安装：pip install netmiko pandas
from netmiko import ConnectHandler
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import time
from datetime import datetime
import os

# 1. 加载CSV设备列表（兼容原有devices.csv格式）
def load_devices(csv_path="devices.csv"):
    """加载并转换设备列表为Netmiko兼容格式"""
    try:
        devices = pd.read_csv(csv_path).to_dict("records")
    except FileNotFoundError:
        print(f"❌ 错误：未找到设备列表文件 {csv_path}")
        return []
    
    netmiko_devices = []
    for dev in devices:
        # 兼容CSV中可能的空值/默认值
        netmiko_dev = {
            "device_type": dev.get("设备类型", "cisco_ios"),  # 支持自定义设备类型
            "ip": dev.get("IP", ""),
            "username": dev.get("用户名", ""),
            "password": dev.get("密码", ""),
            "port": int(dev.get("端口", 22)),
            "timeout": 15,
            "global_delay_factor": 0.5,  # 优化长输出延迟
        }
        # 校验必填字段
        if all([netmiko_dev["ip"], netmiko_dev["username"], netmiko_dev["password"]]):
            netmiko_devices.append(netmiko_dev)
        else:
            print(f"⚠️  设备 {dev.get('IP', '未知')} 缺少必填信息，已跳过")
    return netmiko_devices

# 新增：从cmd.txt读取执行命令
def load_commands(txt_path="cmd.txt"):
    """从txt文件读取命令，过滤空行和注释（#开头）"""
    commands = []
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                # 去除首尾空格/换行
                cmd = line.strip()
                # 跳过空行和注释行（#开头）
                if not cmd or cmd.startswith("#"):
                    continue
                commands.append(cmd)
        if not commands:
            print(f"⚠️  警告：{txt_path} 中无有效命令（空行/注释已过滤）")
        else:
            print(f"🔧 从 {txt_path} 加载 {len(commands)} 条命令：{commands}")
    except FileNotFoundError:
        print(f"❌ 错误：未找到命令文件 {txt_path}")
    except Exception as e:
        print(f"❌ 读取 {txt_path} 失败：{str(e)}")
    return commands

# 2. 定义设备执行函数（改用从文件读取命令）
def exec_device(device, commands):
    """执行指定命令到单个设备"""
    ip = device["ip"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f"ssh_exec_results/{ip}_{timestamp}.log"
    
    # 无有效命令时直接返回失败
    if not commands:
        error_msg = f"设备IP：{ip}\n执行时间：{timestamp}\n执行失败：无有效命令可执行"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(error_msg)
        return f"❌ {ip} 失败：无有效命令可执行"
    
    try:
        # 建立SSH连接（with语句自动关闭连接）
        with ConnectHandler(**device) as conn:
            # 循环执行从文件读取的命令（替代原硬编码）
            output = ""
            for cmd in commands:
                cmd_output = conn.send_command(
                    cmd,
                    read_timeout=20,  # 长输出超时时间
                    strip_prompt=False,  # 保留提示符（便于排查）
                    strip_command=False   # 保留命令本身（便于阅读）
                )
                # 拼接命令输出（加分隔符便于区分）
                output += f"\n=== 执行命令：{cmd} ===\n{cmd_output}\n"
        
        # 保存执行结果
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"设备IP：{ip}\n执行时间：{timestamp}\n{output}")
        
        return f"✅ {ip} 执行完成，日志已保存至 {log_path}"
    
    except Exception as e:
        # 保存错误日志
        error_msg = f"设备IP：{ip}\n执行时间：{timestamp}\n执行失败：{str(e)}"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(error_msg)
        return f"❌ {ip} 失败：{str(e)[:80]}"

# 3. 主函数：并发执行
if __name__ == "__main__":
    # 创建日志目录
    if not os.path.exists("ssh_exec_results"):
        os.makedirs("ssh_exec_results")
        print("📁 已创建日志目录：ssh_exec_results")
    
    # 加载命令列表（核心修改：从cmd.txt读取）
    commands = load_commands("cmd.txt")
    if not commands:
        print("❌ 无有效命令，程序退出")
        exit(1)
    
    # 加载设备列表
    netmiko_devices = load_devices("devices.csv")
    if not netmiko_devices:
        print("❌ 无可用设备，程序退出")
        exit(1)
    print(f"🔍 共加载 {len(netmiko_devices)} 台可用设备")
    
    # 并发执行（控制10个线程，传入命令列表）
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        # 用lambda传递额外的commands参数给exec_device
        results = list(executor.map(lambda dev: exec_device(dev, commands), netmiko_devices))
    
    # 打印执行结果
    print("\n" + "="*50)
    print("执行结果汇总：")
    print("="*50)
    for res in results:
        print(res)
    
    # 打印耗时统计
    total_time = round(time.time() - start_time, 2)
    print(f"\n⏱️  总执行时间：{total_time} 秒")