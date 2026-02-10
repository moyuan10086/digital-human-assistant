#!/bin/bash

# 获取脚本所在目录
CDIR="$(cd "$(dirname "$0")" && pwd)"
cd "$CDIR"

echo "========================================================"
echo "              数字人助手 (Digital Human)"
echo "========================================================"
echo ""

# 0. 检查并安装系统依赖 (curl, chromium-browser)
echo "[信息] 正在检查系统依赖..."
DEPENDENCIES_MISSING=0

# 检查 curl
if ! command -v curl &> /dev/null; then
    echo "[警告] 未找到 curl，尝试自动安装..."
    if sudo apt-get update && sudo apt-get install -y curl; then
        echo "[信息] curl 安装成功。"
    else
        echo "[错误] curl 安装失败！请手动安装: sudo apt-get install -y curl"
        DEPENDENCIES_MISSING=1
    fi
else
    echo "[信息] 检测到 curl 已安装。"
fi

# 检查 chromium-browser
if ! command -v chromium-browser &> /dev/null; then
    echo "[警告] 未找到 chromium-browser，尝试自动安装..."
    if sudo -E apt install -y chromium-browser; then
        echo "[信息] chromium-browser 安装成功。"
    else
        echo "[错误] chromium-browser 安装失败！请手动安装: sudo -E apt install chromium-browser"
        # chromium 非核心阻塞，仅警告
    fi
else
    echo "[信息] 检测到 chromium-browser 已安装。"
fi

if [ $DEPENDENCIES_MISSING -eq 1 ]; then
    read -p "按回车键退出..."
    exit 1
fi

# 1. 检查前端构建
if [ ! -d "dist" ]; then
    echo "[错误] 未找到 dist 目录！"
    echo "请先执行 npm run build 构建前端资源。"
    read -p "按回车键退出..."
    exit 1
fi

# 2. 代理配置 (Proxy)
if [ -z "$http_proxy" ]; then
    # 定义端口检测函数
    check_port() {
        local ip=$1
        local port=$2
        # 优先使用 nc 检测端口 (速度快)
        if command -v nc &> /dev/null; then
            if nc -z -w 1 "$ip" "$port" 2>/dev/null; then
                return 0
            fi
        fi
        # 回退到 curl 尝试连接
        if command -v curl &> /dev/null; then
            if curl --connect-timeout 0.2 -s "http://$ip:$port" > /dev/null; then
                return 0
            fi
        elif command -v wget &> /dev/null; then
            if wget -q --spider --timeout=1 "http://$ip:$port" > /dev/null 2>&1; then
                return 0
            fi
        fi
        return 1
    }

    # 扫描 IP 列表的常用代理端口
    find_proxy() {
        local ips=("$@")
        local ports=(7890 10809 7897) # 常见代理端口: Clash, v2ray等
        for ip in "${ips[@]}"; do
             if [ -z "$ip" ]; then continue; fi
             for port in "${ports[@]}"; do
                 if check_port "$ip" "$port"; then
                     echo "http://$ip:$port"
                     return 0
                 fi
             done
        done
        return 1
    }

    echo "[信息] 正在检查网络代理配置..."
    
    # 1. 准备候选 IP 列表: 本机 -> 网关
    GATEWAY_IP=$(ip route show | grep default | awk '{print $3}' | head -n 1)
    CANDIDATE_IPS=("127.0.0.1" "localhost")
    if [ -n "$GATEWAY_IP" ]; then
        CANDIDATE_IPS+=("$GATEWAY_IP")
    fi
    
    # 2. 自动检测 (本机和网关)
    AUTO_PROXY=$(find_proxy "${CANDIDATE_IPS[@]}")
    
    if [ -n "$AUTO_PROXY" ]; then
        export http_proxy="$AUTO_PROXY"
        export https_proxy="$AUTO_PROXY"
        echo "[信息] 自动检测并设置代理: $AUTO_PROXY"
    else
        # 3. 未自动检测到
        # 检查是否是首次运行 (通过判断环境是否存在)
        IS_INSTALLED=0
        if [ -d ".venv" ] && [ -f "uv.lock" ]; then
            IS_INSTALLED=1
        fi
        
        # 只有在首次安装时，才询问用户 (避免每次启动都问)
        if [ $IS_INSTALLED -eq 0 ]; then
             echo "[提示] 未自动检测到本机或网关代理。"
             echo "      请输入代理 IP (例如 10.0.0.5) 或完整地址。"
             echo "      如果不输入端口，脚本将自动检测该 IP 的常用端口 (7890, 10809)。"
             read -e -r -p "请输入代理 IP (直接回车跳过): " USER_INPUT
             
             if [ -n "$USER_INPUT" ]; then
                 if [[ "$USER_INPUT" == *:* ]]; then
                      # 用户输入了端口 (例如 10.0.0.5:1234)，直接使用
                      FINAL_PROXY="$USER_INPUT"
                 else
                      # 用户只输入了 IP，扫描常用端口
                      echo "[信息] 正在扫描 IP $USER_INPUT 的常用端口..."
                      SCANNED_PROXY=$(find_proxy "$USER_INPUT")
                      if [ -n "$SCANNED_PROXY" ]; then
                           FINAL_PROXY="$SCANNED_PROXY"
                           echo "[信息] 成功检测到代理: $FINAL_PROXY"
                      else
                           # 没扫描到，默认兜底使用 7890
                           FINAL_PROXY="http://$USER_INPUT:7890"
                           echo "[警告] 未检测到开放端口，默认使用: $FINAL_PROXY"
                      fi
                 fi
                 
                 # 补全 http 前缀
                 if [[ "$FINAL_PROXY" != http* ]]; then
                     FINAL_PROXY="http://$FINAL_PROXY"
                 fi
                 
                 export http_proxy="$FINAL_PROXY"
                 export https_proxy="$FINAL_PROXY"
                 echo "[信息] 已设置手动代理: $FINAL_PROXY"
             else
                 # 用户跳过，使用阿里源
                 echo "[信息] 未设置代理。已启用阿里云镜像源加速下载。"
                 unset http_proxy
                 unset https_proxy
                 export UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple"
             fi
        fi
    fi
else
    echo "[信息] 使用现有代理: $http_proxy"
fi

# 3. 检查 uv
if ! uv --version &> /dev/null; then
    # 尝试加载用户目录下的 uv
    if [ -f "$HOME/.local/bin/env" ]; then
         source "$HOME/.local/bin/env"
    elif [ -f "$HOME/桌面/bin/uv" ]; then
         # 如果是自定义安装路径
         export PATH="$HOME/桌面/bin:$PATH"
    fi
fi

if ! uv --version &> /dev/null; then
    echo "[警告] 未检测到可用的 uv 工具 (或版本不兼容)。"
    echo "正在尝试自动安装 uv..."
    # 优先尝试国内源或预编译包
    mkdir -p "$HOME/桌面/bin"
    
    # 自动检测架构
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        UV_FILENAME="uv-x86_64-unknown-linux-gnu.tar.gz"
        UV_URL="https://github.com/astral-sh/uv/releases/download/0.9.27/uv-x86_64-unknown-linux-gnu.tar.gz"
    elif [ "$ARCH" = "aarch64" ]; then
        UV_FILENAME="uv-aarch64-unknown-linux-gnu.tar.gz"
        UV_URL="https://github.com/astral-sh/uv/releases/download/0.9.27/uv-aarch64-unknown-linux-gnu.tar.gz"
    else
        echo "[错误] 不支持的架构: $ARCH"
        exit 1
    fi

    if command -v curl &> /dev/null; then
        curl -k -L -O "$UV_URL"
    elif command -v wget &> /dev/null; then
        wget --no-check-certificate -O "$UV_FILENAME" "$UV_URL"
    else
        echo "[错误] 未找到 curl 或 wget，无法下载 uv。"
        exit 1
    fi
    if [ $? -eq 0 ]; then
        tar -xzf "$UV_FILENAME"
        # 提取目录名 (去掉 .tar.gz)
        UV_DIR="${UV_FILENAME%.tar.gz}"
        mv "$UV_DIR/uv" "$HOME/桌面/bin/"
        mv "$UV_DIR/uvx" "$HOME/桌面/bin/"
        rm -rf "$UV_DIR"*
        export PATH="$HOME/桌面/bin:$PATH"
    else
        echo "[错误] uv 安装失败！请检查网络或配置代理。"
        exit 1
    fi
fi

# 3. 同步环境
echo "[信息] 正在检查并同步 Python 环境..."
# 强制指定 Python 版本为 3.10 以确保最佳兼容性 (避免使用过新版本导致编译失败)
echo "3.10" > .python-version

uv sync
if [ $? -ne 0 ]; then
    echo "[错误] 环境同步失败！请检查网络。"
    read -p "按回车键退出..."
    exit 1
fi

# 3.5 检查端口占用
PORT=8004
# 尝试使用 lsof 查找占用端口的 PID
if command -v lsof &> /dev/null; then
    PID=$(lsof -t -i:$PORT)
elif command -v netstat &> /dev/null; then
    # netstat 输出格式处理
    PID=$(netstat -nlp | grep ":$PORT " | awk '{print $7}' | cut -d'/' -f1)
fi

if [ -n "$PID" ]; then
    echo "[警告] 端口 $PORT 被占用 (PID: $PID)，正在尝试释放..."
    kill -9 $PID 2>/dev/null
    sleep 1
    echo "[信息] 端口已释放。"
fi

# 4. 启动服务
echo ""
echo "[信息] 服务启动中..."
echo "[提示] 浏览器将自动打开 http://localhost:8004"
echo "[提示] 关闭终端窗口将停止服务。"
echo ""

# 延迟 3 秒打开浏览器 (后台运行)
(sleep 3 && chromium-browser --start-fullscreen http://localhost:8004) &

# 启动后端
uv run backend/main.py
