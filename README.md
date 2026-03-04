# InspeX - 食品检测报告智能验证系统

> 一个基于 AI 的食品检测报告自动化验证平台，提供国标合规性检查、检测项目核对、方法验证等全方位智能分析服务。

## 📋 项目简介

InspeX 通过 OCR 技术提取 PDF 检测报告信息，结合 RAGFlow 知识库和国标数据库，自动完成多维度合规性验证与风险识别。前端采用 **Vite + React**，后端为 **Flask 纯 REST API**。

### 核心功能

- 🔍 **智能 PDF 解析** — 基于 PaddleOCR 的高精度表格识别与数据提取
- 📊 **多维度验证**
  - 国标有效性验证（GB 标准状态、发布/实施日期，支持截图与下载）
  - 检验项目合规性（基于食品安全监督抽检实施细则 RAGFlow 匹配）
  - 检测方法合规性
  - 标准指标合理性
  - 评价依据合理性
- 🤖 **RAGFlow 智能检索** — 向量数据库驱动的细则文档匹配
- 📝 **附加信息管理** — 委托单、标签图片上传与核对
- 📈 **可视化结果展示** — 7 个 Tab 的结构化报告 + PDF 内嵌预览

---

## 🏗️ 项目结构

```
extractionSystem/
├── frontend/                     # React 前端（Vite + React 18）
│   ├── src/
│   │   ├── pages/
│   │   │   ├── UploadPage.jsx    # 文件上传页
│   │   │   └── ResultPage.jsx    # 验证结果页（7 个 Tab）
│   │   ├── components/
│   │   │   └── DropZone.jsx      # 拖拽上传组件
│   │   ├── App.jsx               # 路由配置
│   │   └── style.css             # 全局样式
│   └── vite.config.js            # Vite 配置（含 /api 代理）
│
└── backend/                      # Flask 后端（纯 REST API）
    ├── src/
    │   ├── app.py                # Flask 主程序 & API 路由
    │   ├── field_extractor.py    # 字段提取
    │   ├── html_table_parser.py  # HTML 表格解析
    │   ├── table_merger.py       # 表格合并
    │   ├── cell_parser.py        # 单元格解析
    │   ├── item_name_matcher.py  # 项目名称匹配
    │   ├── paddleocr_enhanced.py # OCR 增强
    │   ├── pdf_reader.py         # PDF 读取
    │   ├── ocr_engine.py         # OCR 接口
    │   ├── business_logic_filter.py
    │   ├── profile_inspection.py # 委托单处理
    │   ├── package_image_processor.py
    │   ├── ragflow_client.py     # RAGFlow API 客户端
    │   ├── ragflow_verifier.py   # RAGFlow 核查逻辑
    │   ├── gb_verifier/          # 国标验证模块
    │   │   ├── __init__.py       # 批量验证入口（并行+缓存）
    │   │   ├── runner.py         # Tavily 搜索 & 详情页解析
    │   │   ├── validate.py       # 有效性判定逻辑
    │   │   ├── screenshot.py     # Playwright 截图
    │   │   ├── download.py       # 标准文件下载
    │   │   └── html_extractor.py # HTML 数据提取
    │   └── verifier2/            # 深度核查模块（CLI）
    ├── static/                   # 运行时文件目录
    │   ├── files/                # 参考 PDF（细则、国标）
    │   ├── uploads/              # 上传的检测报告
    │   ├── screenshots/          # 国标详情页截图
    │   ├── downloads/            # 下载的国标文件
    │   └── cache/                # 验证结果缓存
    ├── requirements.txt
    ├── requirements.production.txt
    ├── gunicorn_config.py
    ├── config.local.example.json
    └── config.local.json         # 本地配置（含密钥，gitignored）
```

---

## 🚀 快速开始

### 环境要求

| 环境 | 版本 |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| 磁盘空间 | 约 2GB（含 OCR 模型） |

### 1. 安装后端依赖

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 配置环境

```bash
cp config.local.example.json config.local.json
```

编辑 `config.local.json`：

```json
{
    "RAGFLOW_API_URL": "你的 RAGFlow API 地址",
    "RAGFLOW_API_KEY": "你的 RAGFlow API 密钥",
    "RAGFLOW_KB_ID":   "细则知识库 ID",
    "RAGFLOW_KB_ID_GB":"国标知识库 ID"
}
```

### 3. 准备参考文件

将以下文件放入 `static/files/`：
- `2025年食品安全监督抽检实施细则.pdf`
- 需要参考的 GB 国标 PDF（如 `GB 2763-2021.pdf`）

### 4. 安装前端依赖

```powershell
cd ../frontend
npm install
```

### 5. 启动开发环境

**需要同时开两个终端：**

```powershell
# 终端 1 — Flask 后端（端口 5000）
cd backend
.\.venv\Scripts\python.exe -m flask --app src/app.py run --port 5000

# 终端 2 — Vite 前端（端口 5173）
cd frontend
npm run dev
```

浏览器访问：**`http://localhost:5173`**

---

## 🔑 配置说明

| 配置项 | 说明 | 必填 |
|---|---|---|
| `RAGFLOW_API_URL` | RAGFlow API 服务地址 | ✅ |
| `RAGFLOW_API_KEY` | RAGFlow API 密钥 | ✅ |
| `RAGFLOW_KB_ID` | 细则知识库 ID | ✅ |
| `RAGFLOW_KB_ID_GB` | 国标知识库 ID | ✅ |
| `MCP_URL` | Tavily MCP 服务地址（国标验证）| 否 |

---

## 📡 API 文档

所有接口均以 `/api/` 为前缀，返回 JSON。

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/upload` | 上传 PDF 并执行全量分析 |
| `POST` | `/api/process_pdf` | 处理单个 PDF（结果页追加）|
| `POST` | `/api/check_gb_validity` | 手动触发国标有效性验证 |
| `POST` | `/api/query_standards` | 查询细则检验项目 |
| `POST` | `/api/upload_protocol` | 上传委托单 |
| `POST` | `/api/upload_label_info` | 上传标签信息 |
| `GET`  | `/api/ragflow/*` | RAGFlow 代理接口 |

### 上传报告示例

```http
POST /api/upload
Content-Type: multipart/form-data

pdfs: <PDF文件>
```

**响应：**
```json
{
  "success": true,
  "results": [
    {
      "filename": "SP202501824 黄瓜.pdf",
      "status": "success",
      "issue_count": 0,
      "pdf_url": "/static/uploads/xxx.pdf",
      "summary": {
        "food_name": "黄瓜",
        "production_date": "2025-01-01",
        "gb_codes": ["GB 2763-2021"],
        "gb_validation": { ... },
        "ragflow_verification": { ... }
      },
      "items": [ ... ],
      "issues": []
    }
  ]
}
```

---

## 📦 生产部署

### 构建前端

```powershell
cd frontend
npm run build
# 产物输出到 frontend/dist/，部署时由 Nginx 提供静态资源服务
```

### 启动 Flask（Gunicorn）

```bash
cd backend
gunicorn -c gunicorn_config.py src.app:app
```

### Nginx 反向代理示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态资源
    root /path/to/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Flask 静态文件（截图/下载等）
    location /static/ {
        proxy_pass http://127.0.0.1:5000;
    }
}
```

---

## ⚠️ 常见问题

**Q: OCR 识别准确率不高？**
确保 PDF 清晰度足够，避免扫描件模糊。可调整 `paddleocr_enhanced.py` 中参数。

**Q: RAGFlow 连接失败？**
检查 `config.local.json` 中的地址和密钥，确认 RAGFlow 服务正常运行。

**Q: 国标验证截图功能不可用？**
需要安装 Playwright：`playwright install chromium`

**Q: 清理缓存？**
删除 `static/cache/` 目录下的 JSON 文件即可，验证结果会在下次请求时重新获取。

---

## 📈 更新日志

### v2.0.0 (2026-03)
- 🚀 前端迁移至 **Vite + React 18**，全面组件化
- 🔌 Flask 重构为纯 REST API（去除 Jinja2 模板渲染）
- ✨ 结果页重建：三栏布局 + 7 个 Tab + PDF 预览
- 🗑️ 移除 FastGPT 集成，统一使用 RAGFlow
- ⚡ verifier2 性能优化：跳过冗余 Tavily 调用

### v1.0.0 (2026-02)
- ✅ 核心验证功能发布
- ✅ 集成 RAGFlow 智能检索
- ✅ 国标验证（截图 + 下载 + 缓存）

---

## 🙏 致谢

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — OCR 引擎
- [RAGFlow](https://github.com/infiniflow/ragflow) — 检索增强生成框架
- [Flask](https://flask.palletsprojects.com/) — Python Web 框架
- [Vite](https://vitejs.dev/) + [React](https://react.dev/) — 现代前端工具链
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF 处理
