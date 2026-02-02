# verifier2 - 食品安全国标自动校验工具

基于 Tavily MCP 的食品安全国家标准自动检索与校验系统。通过食品伙伴网（foodmate.net）检索国标信息，自动校验生产日期与标准实施日期的合规性。

## 功能特性

- ✅ 自动检索食品安全国家标准（GB 标准）信息
- ✅ 从食品伙伴网获取标准状态、发布日期、实施日期、废止日期
- ✅ 自动校验生产日期与标准实施日期的合规性
- ✅ 支持批量处理多个国标编号
- ✅ 生成详细的溯源链接和校验报告
- ✅ 自动截取详情页关键信息截图（标题+日期表）
- ✅ 自动下载标准文件（PDF等格式）
- ✅ 显示程序运行时长统计

## 快速开始

### 1. 配置 Tavily API

三种配置方式任选其一：

#### 方式 A：PowerShell 环境变量（推荐）

```powershell
$env:TAVILY_MCP_URL="https://mcp.tavily.com/mcp/?tavilyApiKey=YOUR_KEY"
python mcp_tavily_demo.py
```

> **注意**：PowerShell 中使用 `set` 命令无法设置进程环境变量，必须使用 `$env:` 语法。

#### 方式 B：命令行参数

```bash
python mcp_tavily_demo.py --mcp-url "https://mcp.tavily.com/mcp/?tavilyApiKey=YOUR_KEY"
```

#### 方式 C：本地配置文件（推荐用于持久化配置）

1. 复制配置模板：
   ```bash
   copy config.local.example.json config.local.json
   ```

2. 编辑 `config.local.json`，填入你的 API Key：
   ```json
   {
     "TAVILY_MCP_URL": "https://mcp.tavily.com/mcp/?tavilyApiKey=YOUR_KEY"
   }
   ```

3. 直接运行（无需设置环境变量）：
   ```bash
   python mcp_tavily_demo.py
   ```

> **说明**：`config.local.json` 已添加到 `.gitignore`，不会被提交到版本控制。

### 2. 准备输入文件

创建 `input.json` 文件（参考 `input.json` 示例）：

```json
{
  "summary": {
    "food_name": "有机蔬菜",
    "production_date": "2025-10-25",
    "gb_codes": [
      "GB 19302-2025",
      "GB 2763-2016"
    ]
  }
}
```

**必需字段说明**：
- `food_name`：食品名称
- `production_date`：生产日期（格式：YYYY-MM-DD）
- `gb_codes`：国标编号数组（支持多个）

### 3. 运行校验

```bash
python mcp_tavily_demo.py
```

或指定自定义路径：

```bash
python mcp_tavily_demo.py --input-json input.json --output-txt output.txt
```

## 输出说明

### 主要输出

1. **`output.txt`** 
   - 食品名称和生产日期
   - 每个国标的详细校验结果
   - 校验通过/不通过的原因
   - 标准状态、发布日期、实施日期、废止日期
   - 食品伙伴网溯源链接

2. **`artifacts/`** 目录 - 结构化数据
   - `tavily_mcp_smoke_{gb_number}.json` - 每个国标的完整检索数据
   - `standard_info_{gb_number}.json` - 每个国标的结构化标准信息

### 输出示例

```
食品名称：有机蔬菜
生产日期：2025-10-25
待校验国标数量：2
================================================================================

【1/2】校验国标：GB 19302-2025 (GB 19302-2025)
--------------------------------------------------------------------------------
校验结论：通过
生产日期：2025-10-25

标准信息（来源：standard_info.json）：
  - 国标号：GB 19302-2025
  - 标准状态：现行有效
  - 发布日期：2025-03-15
  - 实施日期：2025-09-15
  - 废止日期：未知/未提供
  - 详情页：https://down.foodmate.net/standard/sort/3/50617.html

【2/2】校验国标：GB 2763-2016 (GB 2763-2016)
--------------------------------------------------------------------------------
校验结论：不通过
生产日期：2025-10-25
不通过原因：
  1. 标准状态不是现行有效（当前为：已废止）
...
```

## 校验逻辑

系统按以下顺序进行校验：

1. **标准状态检查**
   - 标准状态必须为"现行有效"
   - 如果标准已废止、作废或停止使用，则校验失败

2. **实施日期检查**
   - 生产日期必须 >= 标准实施日期
   - 如果生产日期早于实施日期，则校验失败

3. **数据完整性检查**
   - 检查是否缺少实施日期等关键信息
   - 检查日期格式是否正确

## 项目结构

```
verifier2/
├── verifier2/              # 主代码包
│   ├── cli.py             # 命令行入口和主流程
│   ├── config.py          # 配置管理
│   ├── runner.py          # MCP 调用和数据处理
│   ├── mcp_client.py      # MCP 客户端封装
│   ├── http_client.py     # HTTP 请求封装
│   ├── test_input.py      # 输入数据解析
│   ├── validate.py        # 校验逻辑
│   ├── screenshot.py      # 详情页截图
│   ├── download.py        # 标准文件下载
│   ├── html_extractor.py  # HTML 信息提取
│   └── foodmate_extract.py # 食品伙伴网数据提取
├── artifacts/             # 输出目录（自动创建）
├── screenshot/            # 截图目录（自动创建）
├── report/                # 标准文件下载目录（自动创建）
├── mcp_tavily_demo.py     # 启动入口
├── input.json             # 输入文件示例
├── output.txt             # 校验报告输出
└── config.local.json      # 本地配置（需自行创建）
```

## 命令行参数

```bash
python mcp_tavily_demo.py [选项]

选项：
  --mcp-url URL            Tavily MCP URL（包含 API Key）
  --config PATH            配置文件路径（默认：config.local.json）
  --input-json PATH        输入 JSON 文件路径（默认：input.json）
  --output-txt PATH        输出文本文件路径（默认：output.txt）
  --artifacts-dir PATH     artifacts 目录路径（默认：artifacts）
  --screenshot-dir PATH    截图保存目录路径（默认：screenshot）
  --no-screenshot          禁用详情页截图功能
  --download-dir PATH      标准文件下载目录路径（默认：report）
  --no-download            禁用标准文件下载功能
```

## 详情页截图功能

系统会自动截取每个标准详情页的关键信息（标题、日期表等），保存到 `screenshot/` 目录。

### 前置要求

截图功能需要安装 Playwright 及其浏览器内核：

```bash
pip install playwright
python -m playwright install chromium
```

### 使用说明

- 默认启用截图功能，自动保存到 `screenshot/` 目录
- 截图路径会显示在输出报告中
- 如需禁用截图，使用 `--no-screenshot` 参数
- 自定义截图目录：`--screenshot-dir your_path`

### 截图示例

截图文件命名格式：`gb_{编号}_detail.png`，例如：
- `gb_2763-2021_detail.png`
- `gb_2760-2024_detail.png`

## 独立校验工具

如果已有 `standard_info.json`，可以使用独立校验脚本：

```bash
python validate_standard.py \
  --production-date "2025-10-25" \
  --standard-info "artifacts/standard_info_2763-2016.json"
```

## 故障排查

### SSL 连接错误

如果遇到 `ssl.SSLEOFError` 错误：
- 检查网络连接是否稳定
- 尝试重新运行（可能是临时网络问题）
- 如果使用代理，检查代理配置

### 找不到输入文件

```
找不到输入文件：input.json
```

确保 `input.json` 文件存在于当前目录，或使用 `--input-json` 参数指定路径。

### JSON 解析错误

检查 `input.json` 格式是否正确，特别注意：
- 使用双引号（不是单引号）
- 日期格式为 `YYYY-MM-DD`
- `gb_codes` 必须是数组

### 截图功能相关问题

**Playwright 未安装**
```
Playwright 未安装，请运行: pip install playwright && python -m playwright install chromium
```
解决：按提示安装 Playwright 及浏览器内核。

**页面加载超时或连接关闭**
```
页面加载超时：Timeout 30000ms exceeded
net::ERR_CONNECTION_CLOSED
```
解决：
- 检查网络连接是否能访问 foodmate.net
- 使用 `--no-screenshot` 参数禁用截图功能继续其他流程
- 检查防火墙/代理设置

## 数据来源

本工具从 [食品伙伴网标准下载中心](https://down.foodmate.net/standard/) 检索标准信息。感谢食品伙伴网提供的公开数据。

## 许可证

本项目仅供学习和研究使用。使用本工具获取的标准信息仅供参考，请以官方发布为准。

## 更新日志

### v2.2.0
- 新增标准文件自动下载功能
- 支持从详情页下载 PDF/DOC 等格式标准文件
- 输出报告中显示下载文件相对路径
- 支持命令行控制下载开关和目录

### v2.1.0
- 新增详情页自动截图功能（基于 Playwright）
- 添加程序运行时长统计
- 输出报告中显示截图相对路径
- 支持命令行控制截图开关和目录

### v2.0.0
- 支持 JSON 格式输入
- 支持批量处理多个国标编号
- 优化输出格式，生成人类友好的报告
- 每个国标的 artifacts 独立保存
- 精简 JSON 输出，只保留核心数据

### v1.0.0
- 初始版本
- 支持单个国标检索和校验
- 基于 test.txt 文本输入
