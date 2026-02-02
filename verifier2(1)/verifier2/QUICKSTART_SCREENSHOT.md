# 快速开始 - 截图功能

## 1. 安装依赖（首次使用）

```bash
pip install playwright
python -m playwright install chromium
```

## 2. 运行程序

```bash
python mcp_tavily_demo.py
```

程序会自动：
- 检索标准信息
- 截取详情页关键区域
- 保存截图到 `screenshot/` 目录
- 在 `output.txt` 中显示截图路径
- 显示总运行时长

## 3. 查看结果

### 文本报告
查看 `output.txt`，每个标准的报告末尾会显示：
```
  - 详情截图：screenshot\gb_2760-2024_detail.png
```

### 截图文件
在 `screenshot/` 目录中查看生成的 PNG 文件。

### 运行时长
程序结束时会显示：
```
总运行时长：1 分 23.45 秒
```

## 4. 常用选项

### 禁用截图（提高速度）
```bash
python mcp_tavily_demo.py --no-screenshot
```

### 自定义截图目录
```bash
python mcp_tavily_demo.py --screenshot-dir my_screenshots
```

## 5. 故障排查

### 如果遇到网络超时
使用 `--no-screenshot` 跳过截图：
```bash
python mcp_tavily_demo.py --no-screenshot
```

### 如果 Playwright 未安装
程序会显示提示信息，按提示安装即可。

## 6. 注意事项

- 截图功能会增加每个标准 5-15 秒的处理时间
- 如果网络不稳定，建议使用 `--no-screenshot`
- 截图失败不会影响其他功能（校验、信息提取等）

## 完整示例

```bash
# 1. 确保配置正确
cat config.local.json

# 2. 检查输入文件
cat input.json

# 3. 运行程序（启用截图）
python mcp_tavily_demo.py

# 4. 查看结果
cat output.txt
dir screenshot
```

## 测试文件说明

- `screenshot_test.py`：单页测试脚本，已集成到主流程中
- 可以保留用于独立测试，也可以删除

