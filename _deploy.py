"""部署脚本：上传 ZIP 到服务器并重启 Streamlit"""
import paramiko
import os
import sys

HOST = "111.229.102.178"
USER = "ubuntu"
PASS = "Huachacha123"
ZIP_FILE = "KaoyanRAG-v4.2.zip"
REMOTE_DIR = "/home/ubuntu"
APP_DIR = "/home/ubuntu/kaoyan"

def run_cmd(ssh, cmd, desc=""):
    if desc:
        print(f"  [{desc}]")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out.strip())
    if err:
        print(err.strip(), file=sys.stderr)
    return out, err

print(f"Connecting to {HOST}...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS)
print("Connected.")

# 1. 上传 ZIP
print(f"\n[1/4] Uploading {ZIP_FILE}...")
sftp = ssh.open_sftp()
sftp.put(ZIP_FILE, f"{REMOTE_DIR}/{ZIP_FILE}", callback=lambda x, y: print(f"  {x}/{y} bytes", end="\r"))
sftp.close()
print(f"\n  Upload complete.")

# 2. 停止旧服务
print("\n[2/4] Stopping old Streamlit...")
run_cmd(ssh, "pkill -f 'streamlit run' || true", "kill streamlit")
run_cmd(ssh, "sleep 2", "wait")

# 3. 解压并替换
print("\n[3/4] Extracting and replacing...")
run_cmd(ssh, f"cd {REMOTE_DIR} && python3 -c \"import zipfile; z=zipfile.ZipFile('{ZIP_FILE}'); z.extractall('{APP_DIR}'); print(f'Extracted {{len(z.namelist())}} files')\"", "unzip")
run_cmd(ssh, f"rm -f {REMOTE_DIR}/{ZIP_FILE}", "cleanup zip")

# 检查并安装依赖
print("\n  Checking Python deps...")
deps_out, _ = run_cmd(ssh, f"cd {APP_DIR} && source /home/ubuntu/kaoyan/venv/bin/activate && pip install python-docx lxml -q 2>&1 || true")

# 检查 Pandoc
print("\n  Checking Pandoc...")
pandoc_out, _ = run_cmd(ssh, "which pandoc || (sudo apt-get update -qq && sudo apt-get install -y pandoc 2>&1)")
print(f"  Pandoc: {pandoc_out.strip() if pandoc_out else 'not found'}")

# 4. 启动服务
print("\n[4/4] Starting Streamlit...")
start_cmd = (
    f"cd {APP_DIR} && "
    "source /home/ubuntu/kaoyan/venv/bin/activate && "
    "nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 "
    "--server.headless true --browser.serverAddress 111.229.102.178 "
    "> /home/ubuntu/streamlit.log 2>&1 &"
)
run_cmd(ssh, start_cmd, "start streamlit")
run_cmd(ssh, "sleep 3", "wait for startup")

# 验证
print("\n  Checking service...")
status, _ = run_cmd(ssh, "ps aux | grep 'streamlit run' | grep -v grep")
if "streamlit run" in status:
    print("  ✅ Streamlit is running")
else:
    print("  ⚠️  Streamlit may not have started. Check /home/ubuntu/streamlit.log")

ssh.close()
print("\nDone. Visit: http://111.229.102.178:8501")
