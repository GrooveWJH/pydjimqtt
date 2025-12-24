#!/bin/bash
# IVAS Mock 系统快速启动脚本

echo "======================================"
echo "  IVAS Mock 测试系统启动器"
echo "======================================"
echo ""

# 检查 Mock Server 是否已运行
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✓ Mock Server 已在运行 (端口 5001)"
else
    echo "启动 Mock Server..."
    cd "$(dirname "$0")"
    python ivas/task_mock_server.py &
    MOCK_PID=$!
    sleep 2
    echo "✓ Mock Server 已启动 (PID: $MOCK_PID)"
fi

echo ""
echo "可用命令："
echo "  1. 启动键盘控制器:"
echo "     IVAS_MODE=mock python ivas/keyboard_commander.py"
echo ""
echo "  2. 启动 pure.py (Mock 模式):"
echo "     IVAS_MODE=mock python pure.py"
echo ""
echo "  3. 启动 pure.py (生产模式):"
echo "     IVAS_MODE=production python pure.py"
echo ""
echo "  4. 停止 Mock Server:"
echo "     lsof -ti:5001 | xargs kill"
echo ""
echo "======================================"
