# 食安智审 - 食品报告智能核查平台

> 食安智审 是一个专为食品安全领域打造的 **一体化报告自动化验证平台**。系统通过对 PDF 检测报告进行深度智能 OCR 解析，并结合 RAG（Retrieval-Augmented Generation）大语言模型与实时国标数据库，自动完成从**数据提取、标准核对到合规性验证**的全链路数据分析服务。

## ✨ 核心特性

- **📄 智能文档解析 (PaddleOCR + 启发式表格还原)**
  - 高精度重构复杂 PDF 表格结构，自动解决跨行单元格、化学物质微小下标等传统解析痛点。
- **🧠 知识库智能检索 (RAGFlow 集成)**
  - 内置监督抽检实施细则的专属向量库。
  - 通过大语言模型智能提取食品限量指标、检测单位及判定标准，消除“名称格式差异”导致的误判。
- **⚖️ 全方位合规性评判**
  - **国标生命周期检查**：自动检索国标 (GB) 现行状态、发布与实施日期，并支持旧版/作废国标溯源扫描，保留原生网页截图与源文件供下载。
  - **动态指标判定**：精准判别“指标超标”与“标准不符”的差异化业务场景（支持企标严于国标的合理性校验）。
  - **检测方法核对**：宽容度极高的文本防抖动匹配引擎，适配例如“方法号与子方法切分”等复杂业务场景。
- **� 现代化交互体验 (React 18 + Vite)**
  - 支持批量文件并行上传与验证。
  - **7 维交互展示** + **同步 PDF 内联联动预览**，一键掌握检测项目、评价依据、标准判定等各项业务明细。
- **📑 委托单与包装标签审定**
  - 支持辅助上传企业产品委托单、包装图片，通过比对进一步核验源头合规性。

---

## 🏗️ 平台技术栈

- **前端架构**：Vite + React 18 构建响应式界面，组件化渲染。
- **后端服务**：Flask 驱动的纯 RESTful API 设计架构，高度解耦。
- **OCR 引擎**：PaddleOCR + PyMuPDF。
- **大模型核心**：RAGFlow (负责业务指标的 RAG 知识检索)。
- **网页自动化**：Playwright (执行官网资料拉取与自动网页快照)。

---

## 🚀 部署指南与快速启动

### 🛠 环境要求

| 依赖模块 | 推荐版本 | 说明 |
|----------|----------|------|
| Python | 3.10+ | 后端核心服务支撑 |
| Node.js | 18+ | 前端界面编译与运行 |
| 存储空间 | ≥ 2 GB | 包含 PaddleOCR 预训练模型及本地缓存库 |

### 1️⃣ 后端服务部署

1. **环境准备与依赖安装**
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   playwright install chromium  # 安装国标截图所依赖的浏览器内核
   ```

2. **环境变量与配置**
   复制示例配置并修改你的私密密钥：
   ```bash
   cp config.local.example.json config.local.json
   ```
   **`config.local.json` 示例参考：**
   ```json
   {
       "RAGFLOW_API_URL": "http://你的_RAGFlow_IP_或_域名/v1",
       "RAGFLOW_API_KEY": "RagFlow生成的专属API-KEY",
       "RAGFLOW_KB_ID":   "实施细则知识库 ID",
       "RAGFLOW_KB_ID_GB":"国标知识库 ID"
   }
   ```

3. **导入必要的离线参考文件**
   将业务相关的基础文件（如实施细则 PDF、国标 PDF 等）放入 `backend/static/files/` 目录。（例如：`2025年食品安全监督抽检实施细则.pdf`）

4. **启动 Flask 服务**
   ```powershell
   .\.venv\Scripts\python.exe -m flask --app src/app.py run --port 5000
   ```

### 2️⃣ 前端服务部署

开辟一个全新的独立终端：

1. **安装前端包依赖**
   ```powershell
   cd frontend
   npm install
   ```

2. **启动开发服务器**
   ```powershell
   npm run dev
   ```
   启动成功后浏览器访问： 👉 **`http://localhost:5173`** 即可进入系统主界面。

---

## � 核心目录结构

```text
extractionSystem/
├── frontend/                     # React 前端工程
│   ├── src/
│   │   ├── pages/
│   │   │   ├── UploadPage.jsx    # 工作台：文件上传与批量控制中心
│   │   │   └── ResultPage.jsx    # 面板中心：7 大板块验证结果及 PDF 原卷关联预览
│   │   ├── components/           # 复用组件库
│   │   └── App.jsx               # 前端顶级路由拦截与页面分发
│   └── vite.config.js            # 构建工具配置（含本机连调 /api 跨域代发）
│
└── backend/                      # Flask 纯 API 后段工程
    ├── src/
    │   ├── app.py                # Flask 初始化、中间件绑定与路由分流
    │   ├── html_table_parser.py  # 启发式表格算法 (处理多行异常/拆分容错)
    │   ├── item_name_matcher.py  # 项目实体与字面名称抗抖动匹配
    │   ├── paddleocr_enhanced.py # PaddleOCR 的二次封装与特定领域增强
    │   ├── ragflow_client.py     # RAG 代理访问集成
    │   ├── ragflow_verifier.py   # AI 大模型核心知识验证业务层
    │   └── gb_verifier/          # 国标网络校验服务核心
    │       ├── validate.py       # 状态验证策略执行
    │       └── screenshot.py     # Playwright 网页抓取快照
    ├── static/                   # 静态系统运行时 IO 目录 (日志/快照/下载/系统缓存)
    └── config.local.json         # 加密配置环境
```

---

## 📡 核心 API 与接口规范

系统严格遵循前后端分离，以统一定义的 `/api/` 路由进行 JSON 协议握手。

| 通信谓词 | 访问路径 | 功能描述 |
|---|---|---|
| `POST` | `/api/upload` | 单/多文档分析核心口（解析、RAG 验证与判决报告生成） |
| `POST` | `/api/check_gb_validity` | 按需式触发国标官网检查与状态强验证 |
| `POST` | `/api/upload_protocol` | 处理用户委托单图文解析对接 |
| `POST` | `/api/upload_label_info` | 校验包装标签，图谱匹配抽检标准 |
| `GET`  | `/api/ragflow/*` | 系统级 RAG 数据库状态代理管道 |

**返回规范 (针对核心的 `/upload`)：**
```json
{
  "success": true,
  "results": [
    {
       "status": "success",
       "filename": "样例报告.pdf",
       "summary": { "food_name": "...", "gb_validation": {} },
       "items": [], 
       "issues": []     // 全局警告、错误和不合规指控池
    }
  ]
}
```

---

## 📈 版本迭代亮点

### 最新版本 (v2.1.0)
- 🔬 **解析引擎巅峰升级**：彻底攻克 PDF 复杂表格墙（多行多列表格穿梭、微小化学式下标等）的大幅度脱框遗漏和提取缺陷。
- 🤖 **RAG 调度与映射优化**：基于全新配置的抽取策略，实现国标限量数值、单位的精准逻辑纠错提取，从根本上解决系统“虚假数据缺失”漏查问题。
- ⚖️ **更智能的合规裁决系统**：前端与后端的判读算法均进行了升级，目前能完美区分“指标超标（违法）”与“标准不符（严于国标的合理性校验）”的不同安全边界。
- 📑 **国标数据完整度增强**：全生命周期的状态追踪！可以准确提取并缓存全量年代（包括已作废/即将实施）国标生命数据及源快照。
- 🧩 **高容错核查模式**：对“检测方法命名法”、“段落分隔落差”、“子方法切分法”启用全新的文字抗抖动引擎匹配算法。

### 初始架构化 (v2.0.0)
- 🚀 前端工程架构进化为 **Vite + React 18**。
- 🔌 Flask 核心瘦身重构为纯粹 REST API 后端，抹除模板渲染包袱。
- ✨ 审查展示平台迭代：引入侧边三栏智能布局 + 高度集成的 7 大分类验证结果池。
- 🗑️ 组件下架：剔除冗余和过时的 FastGPT 模块，将平台大模型驱动池独家锁定至更加专注的 RAGFlow。

---

> _**食安智审** 结合了现代化的 OCR 技术和最新的大语言模型 RAG 工具，致力于成为检测行业标准的数字化守门员。_
