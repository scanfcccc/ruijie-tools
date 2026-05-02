import csv
import time
import threading
import paramiko
from paramiko import AuthenticationException
from queue import Queue, Empty
from datetime import datetime
import os
import traceback

# ======================== 核心配置 =========================
CSV_FILE = "devices.csv"          # 设备信息CSV文件路径
# 命令列表：先禁用分页，再执行目标命令
COMMANDS = [                     
    "terminal length 0",         # 禁用分页（关键）
    "show interfaces status de",
    "show int counters drops",
    "show int counters errors | be CRC",
    "show int transceiver diagnosis",
    "sh version"
]
MAX_CONCURRENT = 10               # 最大并发数
SSH_TIMEOUT = 15                  # 超时时间
OUTPUT_DIR = "ssh_exec_results"   # 结果保存目录
# 交互式Shell配置
SHELL_PROMPT = ["#", ">", "$", "%", "]"]  # 设备提示符
READ_BUFFER_SIZE = 8192           # 增大缓冲区
COMMAND_DELAY = 0.8               # 命令等待时间
# ================================================================================

# 并发控制信号量
concurrent_semaphore = threading.Semaphore(MAX_CONCURRENT)

# 全局变量
device_queue = Queue()
total_devices = 0
completed_devices = 0
progress_lock = threading.Lock()

def create_output_dir():
    """创建结果保存目录"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"✅ 结果目录已创建：{OUTPUT_DIR}")

def wait_for_prompt(shell, timeout=SSH_TIMEOUT):
    """等待设备提示符"""
    shell.settimeout(timeout)
    output = ""
    start_time = time.time()
    try:
        while time.time() - start_time < timeout:
            if shell.recv_ready():
                chunk = shell.recv(READ_BUFFER_SIZE).decode('utf-8', errors='ignore')
                output += chunk
                if any(prompt in output for prompt in SHELL_PROMPT):
                    break
            time.sleep(0.1)
        if not any(prompt in output for prompt in SHELL_PROMPT):
            raise TimeoutError(f"等待提示符超时")
        return output
    except Exception as e:
        raise TimeoutError(f"等待提示符失败：{str(e)}")

def execute_command(shell, cmd):
    """执行命令并返回原始输出（不移除命令/提示符）"""
    try:
        # 清空缓冲区
        while shell.recv_ready():
            shell.recv(READ_BUFFER_SIZE)
            time.sleep(0.1)
        
        # 发送命令
        shell.send(cmd + "\n")
        time.sleep(COMMAND_DELAY)
        
        # 读取原始输出（保留所有内容）
        output = ""
        start_time = time.time()
        prompt_found = False
        
        while time.time() - start_time < SSH_TIMEOUT:
            if shell.recv_ready():
                chunk = shell.recv(READ_BUFFER_SIZE).decode('utf-8', errors='ignore')
                output += chunk
                if any(prompt in output for prompt in SHELL_PROMPT):
                    prompt_found = True
                    break
            time.sleep(0.1)
        
        # 超时补充读取
        if not prompt_found:
            while shell.recv_ready():
                output += shell.recv(READ_BUFFER_SIZE).decode('utf-8', errors='ignore')
                time.sleep(0.1)
        
        return output
    except Exception as e:
        raise Exception(f"执行命令[{cmd}]失败：{str(e)}")

def ssh_exec_device(device):
    """单设备处理逻辑（保留原始SSH输出）"""
    global completed_devices
    ip = device["ip"]
    username = device["username"]
    password = device["password"]
    port = int(device.get("port", 22))
    
    # 生成带时间戳的日志文件名：IP_年月日_时分秒_ssh.log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(OUTPUT_DIR, f"{ip}_{timestamp}_ssh.log")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    shell = None
    # 存储所有命令的原始输出
    all_output = ""
    
    try:
        concurrent_semaphore.acquire()
        print(f"🔌 开始处理：{ip}（当前并发数：{MAX_CONCURRENT - concurrent_semaphore._value}）")
        
        # 连接设备
        ssh.connect(
            hostname=ip,
            username=username,
            password=password,
            port=port,
            timeout=SSH_TIMEOUT,
            allow_agent=False,
            look_for_keys=False,
            banner_timeout=SSH_TIMEOUT
        )
        
        # 建立Shell并等待就绪
        shell = ssh.invoke_shell()
        shell.settimeout(SSH_TIMEOUT)
        # 读取登录欢迎信息并加入原始输出
        login_welcome = wait_for_prompt(shell)
        all_output += login_welcome + "\n"
        
        # 逐行执行命令，收集原始输出
        for cmd in COMMANDS:
            output = execute_command(shell, cmd)
            # 拼接原始输出（命令之间加分隔线，便于区分）
            all_output += f"\n=== 执行命令：{cmd} ===\n" + output + "\n"
        
        # 写入日志：保留所有原始输出
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(all_output)
        
        result_msg = f"✅ {ip} - 执行完成，日志已保存"
    
    except AuthenticationException:
        result_msg = f"❌ {ip} - 认证失败"
        # 失败日志记录错误信息
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"【执行失败】SSH认证失败：用户名/密码错误\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except paramiko.SSHException as e:
        result_msg = f"❌ {ip} - SSH异常：{str(e)[:50]}"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"【执行失败】SSH异常：{str(e)}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except TimeoutError as e:
        result_msg = f"❌ {ip} - 超时：{str(e)[:50]}"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"【执行失败】执行超时：{str(e)}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        result_msg = f"❌ {ip} - 未知错误：{str(e)[:50]}"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"【执行失败】未知错误：{str(e)}\n堆栈信息：\n{traceback.format_exc()}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    finally:
        # 释放资源
        try:
            if shell:
                shell.close()
        except:
            pass
        try:
            ssh.close()
        except:
            pass
        concurrent_semaphore.release()
        # 更新进度
        with progress_lock:
            completed_devices += 1
            progress = (completed_devices / total_devices) * 100
            print(f"\r📊 执行进度：{completed_devices}/{total_devices} ({progress:.1f}%) | {result_msg}", end="")

def load_devices():
    """加载设备信息"""
    global total_devices
    devices = []
    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_fields = ["IP", "用户名", "密码"]
            if reader.fieldnames is None or not all(f in reader.fieldnames for f in required_fields):
                raise ValueError(f"CSV必须包含字段：{required_fields}")
            for row in reader:
                devices.append({
                    "ip": row["IP"].strip(),
                    "username": row["用户名"].strip(),
                    "password": row["密码"].strip(),
                    "port": row.get("端口", "22").strip()
                })
        total_devices = len(devices)
        print(f"📥 成功加载 {total_devices} 台设备信息")
        for dev in devices:
            device_queue.put(dev)
    except FileNotFoundError:
        print(f"❌ 未找到CSV文件：{CSV_FILE}")
        exit(1)
    except Exception as e:
        print(f"❌ 加载设备失败：{str(e)}")
        exit(1)

def worker_thread():
    """工作线程"""
    while True:
        try:
            device = device_queue.get(block=True, timeout=2)
            ssh_exec_device(device)
            device_queue.task_done()
        except Empty:
            break
        except Exception as e:
            print(f"\n⚠️  线程异常：{str(e)}")
            continue

def main():
    """主函数"""
    print("🚀 开始批量执行SSH命令（原始输出日志模式）...")
    create_output_dir()
    load_devices()
    
    if total_devices == 0:
        print("❌ 无设备可执行，退出")
        exit(0)
    
    # 启动工作线程
    thread_num = 20
    print(f"🔄 启动 {thread_num} 个工作线程（最大并发：{MAX_CONCURRENT}）...")
    threads = []
    start_time = time.time()
    
    for _ in range(thread_num):
        t = threading.Thread(target=worker_thread)
        t.daemon = True
        t.start()
        threads.append(t)
    
    # 等待所有设备处理完成
    device_queue.join()
    
    # 等待线程退出
    for t in threads:
        t.join(timeout=3)
    
    # 统计结果
    end_time = time.time()
    total_time = end_time - start_time
    print(f"\n\n🎉 执行完成！")
    print(f"📈 总计执行：{total_devices} 台设备")
    print(f"⏱️  总耗时：{total_time:.2f} 秒（平均每台：{total_time/total_devices:.2f} 秒）")
    print(f"📁 日志目录：{os.path.abspath(OUTPUT_DIR)}（日志包含原始SSH输出，文件名带时间戳）")

if __name__ == "__main__":
    print("⚠️  依赖已安装可忽略：pip install paramiko")
    print("="*60)
    main()