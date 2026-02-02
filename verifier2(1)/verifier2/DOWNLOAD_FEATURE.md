# 标准文件下载功能 - v2.2.0

## 功能说明

自动从详情页下载标准文件（通常为 PDF 格式），保存到 `report/` 目录。

## 使用方法

### 默认启用（推荐）
```bash
python mcp_tavily_demo.py
```
程序会自动下载每个标准的文件到 `report/` 目录。

### 禁用下载
```bash
python mcp_tavily_demo.py --no-download
```

### 自定义下载目录
```bash
python mcp_tavily_demo.py --download-dir my_reports
```

## 实现细节

### 技术路线
1. 从详情页 HTML 中提取下载链接：`https://down.foodmate.net/standard/down.php?auth={itemid}`
2. 使用 `urllib` 发起 HTTP GET 请求
3. 从响应头 `Content-Disposition` 获取文件名
4. 如果没有文件名，根据 `Content-Type` 推断文件扩展名（默认 .pdf）
5. 保存文件到指定目录

### 文件命名
- 优先使用服务器返回的原始文件名
- 如果无法获取，使用格式：`GB_{编号}.pdf`

### 超时设置
- 默认 300 秒（5 分钟）
- 适用于大文件下载

## 输出示例

在 `output.txt` 中会显示：

```
标准信息（来源：standard_info.json）：
  - 国标号：GB 2760-2024
  - 标准状态：现行有效
  - 发布日期：2024-02-08
  - 实施日期：2025-02-08
  - 废止日期：未知/未提供
  - 详情页：https://down.foodmate.net/standard/sort/3/151263.html
  - 详情截图：screenshot\gb_2760-2024_detail.png
  - 标准文件：report\GB_2760-2024.pdf  ← 新增
```

## 错误处理

下载失败不会中断主流程：
- 如果下载失败，会在输出中显示提示信息
- 继续执行其他流程（截图、校验等）
- 报告中不显示下载路径

常见错误：
- `HTTP错误 404`：文件不存在或链接失效
- `网络错误`：网络连接问题
- `下载失败`：其他未知错误

## 新增/修改的文件

### 新增
- `verifier2/download.py` - 下载核心模块

### 修改
- `verifier2/cli.py` - 集成下载功能，添加命令行参数
- `verifier2/validate.py` - 报告中添加下载路径
- `verifier2/runner.py` - 返回 HTML 内容供下载使用
- `README.md` - 更新文档

## 与截图功能的关系

下载和截图功能完全独立，可以：
- 同时启用（默认）
- 只启用截图：`--no-download`
- 只启用下载：`--no-screenshot`
- 全部禁用：`--no-screenshot --no-download`

## 性能影响

- 每个标准增加 5-30 秒下载时间（取决于文件大小和网络速度）
- 建议大批量处理时评估是否需要下载功能

## 示例命令

```bash
# 完整功能（截图+下载）
python mcp_tavily_demo.py

# 只下载，不截图
python mcp_tavily_demo.py --no-screenshot

# 只截图，不下载
python mcp_tavily_demo.py --no-download

# 自定义目录
python mcp_tavily_demo.py --download-dir standards --screenshot-dir images
```

## 向后兼容性

✅ 完全向后兼容：
- 不影响现有功能
- 如果禁用下载，行为与 v2.1.0 完全一致
- 输出格式仅新增一行下载路径（可选）

