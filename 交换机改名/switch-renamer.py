import pandas as pd
import logging
import time
import re
import paramiko

# 日志设置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("rename设备网1.log", encoding='utf-8'), logging.StreamHandler()]
)
def build_final_name(base_name, real_model, is_poe, ip_address):
    """智能组装名称逻辑（包含型号、IP尾号、POE判断）"""
    # 0. 提取 IP 尾号
    ip_str = str(ip_address).strip()
    ip_parts = ip_str.split('.')
    
    # 【修复130网段问题】判断第三段是否为 130
    if len(ip_parts) == 4 and ip_parts[2] == '130':
        ip_tail = f"130.{ip_parts[3]}"  # 提取为 130.158
    else:
        ip_tail = ip_parts[-1]          # 常规 IP 只提取最后一位

    # 1. 强制将 WW 替换为 NW
    name = base_name.replace("-WW-", "-NW-")
    
    # 2. 插入或替换设备型号
    if re.search(r'S\d{4}', name):
        name = re.sub(r'S\d{4}', real_model, name)
    else:
        name = f"{name}-{real_model}"

    # 3. 拼接 IP 尾号 (防呆设计：如果结尾已经带了IP尾号，就不重复添加)
    if not name.endswith(f"-{ip_tail}"):
        name = f"{name}-{ip_tail}"

    # 4. 拼接 POE 后缀
    if is_poe and not name.endswith("-POE"):
        name = f"{name}-POE"
        
    return name

def read_until(shell, expected_strings, timeout=10):
    """自定义的读取缓冲函数，一直读到出现预期的字符串为止"""
    output = ""
    end_time = time.time() + timeout
    while time.time() < end_time:
        if shell.recv_ready():
            output += shell.recv(65535).decode('utf-8', errors='ignore')
            for s in expected_strings:
                if s in output:
                    time.sleep(0.2) 
                    if shell.recv_ready():
                         output += shell.recv(65535).decode('utf-8', errors='ignore')
                    return output
        time.sleep(0.1)
    return output

def process_switches_paramiko(csv_path):
    df = pd.read_csv(csv_path, encoding='gbk')

    # 请修改为实际的账密
    DEFAULT_USER = 'PJXrmyy'
    DEFAULT_PASS = 'PJXrmyy1718@^@'
    DEFAULT_SECRET = 'PJXrmyy1718@^@' 

    for index, row in df.iterrows():
        ip = str(row['IP地址']).strip()
        base_name = str(row['新名称']).strip()
        
        if not ip or ip == 'nan': continue

        logging.info(f"===> [Paramiko] 正在连接: {ip}")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(hostname=ip, port=22, username=DEFAULT_USER, password=DEFAULT_PASS, timeout=10, look_for_keys=False)
            shell = ssh.invoke_shell()
            
            # 1. 读初始提示符，判断是否需要 enable
            out = read_until(shell, ['>', '#'])
            if out.strip().endswith('>'):
                shell.send("en\n")
                out = read_until(shell, ['Password:', 'password:', '#'])
                if 'assword' in out:
                    shell.send(DEFAULT_SECRET + "\n")
                    out = read_until(shell, ['#'])
            
            # 2. 关闭分屏显示
            shell.send("terminal length 0\n")
            read_until(shell, ['#'])
            
            # 3. 获取设备信息
            shell.send("show version | in description\n")
            version_out = read_until(shell, ['#'])
            
            # 提取型号和POE
            real_model = "S5000"
            m = re.search(r'(S\d{4})', version_out)
            if m: real_model = m.group(1)
            is_poe = "-P" in version_out
            
            # 传入 IP 地址以拼接尾号
            final_name = build_final_name(base_name, real_model, is_poe, ip)
            logging.info(f"[{ip}] 识别型号: {real_model} | POE: {is_poe} | 最终名称: {final_name}")

            # 4. 进入配置模式并改名
            shell.send("conf t\n")
            read_until(shell, ['(config)#', '#']) 
            
            shell.send(f"hostname {final_name}\n")
            read_until(shell, ['#']) 
            
            # 5. 退回特权模式并保存
            shell.send("end\n")
            read_until(shell, ['#'])
            
            shell.send("write\n")
            out = read_until(shell, ['[Y/N]', 'y/n', '#'], timeout=15)
            if 'Y/N' in out or 'y/n' in out.lower():
                shell.send("y\n")
                read_until(shell, ['#'], timeout=15)
                
            logging.info(f"[{ip}] 改名与保存全部完成！")

        except paramiko.AuthenticationException:
            logging.error(f"[{ip}] 登录失败: 账号或密码错误")
        except Exception as e:
            logging.error(f"[{ip}] 处理异常: {str(e)}")
        finally:
            ssh.close()

if __name__ == "__main__":
    process_switches_paramiko('C:\\Users\\happy\\Desktop\\project\\python\\netmiko-exec\\设备登录信息表 - 设备网.csv')