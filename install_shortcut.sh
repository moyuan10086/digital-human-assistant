#!/bin/bash

# 获取当前项目绝对路径
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

# 自动检测桌面路径
if [ -d "$HOME/Desktop" ]; then
    DESKTOP_DIR="$HOME/Desktop"
elif [ -d "$HOME/桌面" ]; then
    DESKTOP_DIR="$HOME/桌面"
else
    # 如果是 root 用户，且脚本在 /home/xxx 下，尝试推断用户桌面
    if [ "$EUID" -eq 0 ] && [[ "$APP_DIR" == /home/* ]]; then
         USER_NAME=$(echo "$APP_DIR" | cut -d/ -f3)
         if [ -d "/home/$USER_NAME/桌面" ]; then
             DESKTOP_DIR="/home/$USER_NAME/桌面"
         elif [ -d "/home/$USER_NAME/Desktop" ]; then
             DESKTOP_DIR="/home/$USER_NAME/Desktop"
         fi
    fi
fi

# 如果仍未找到，默认创建到当前用户的桌面目录（如果不存在则创建）
if [ -z "$DESKTOP_DIR" ]; then
    DESKTOP_DIR="$HOME/Desktop"
    mkdir -p "$DESKTOP_DIR"
fi

DESKTOP_FILE="$DESKTOP_DIR/DigitalHuman.desktop"
ICON_PATH="$APP_DIR/public/favicon.ico" # 假设有个图标，或者用系统图标

echo "正在创建桌面快捷方式..."

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=数字人助手
Comment=Digital Human Assistant
Exec=bash -c "cd \"$APP_DIR\" && ./start_kylin.sh; exec bash"
Icon=utilities-terminal
Path=$APP_DIR
Terminal=true
StartupNotify=true
Categories=Utility;Application;
EOF

# 赋予执行权限
chmod +x "$DESKTOP_FILE"
chmod +x "$APP_DIR/start_kylin.sh"

# 如果是 root 运行，尝试修复文件所有权给普通用户
if [ "$EUID" -eq 0 ] && [[ "$DESKTOP_DIR" == /home/* ]]; then
    TARGET_USER=$(echo "$DESKTOP_DIR" | cut -d/ -f3)
    if [ -n "$TARGET_USER" ]; then
        chown "$TARGET_USER:$TARGET_USER" "$DESKTOP_FILE"
        echo "[信息] 已将快捷方式所有权归还给用户: $TARGET_USER"
    fi
fi

echo "成功！快捷方式已创建在桌面：$DESKTOP_FILE"
echo "请双击桌面图标运行。"
read -p "按回车键退出..."
