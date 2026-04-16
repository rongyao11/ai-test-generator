# AI 测试用例生成器

基于 RAG（检索增强生成）的智能测试用例生成工具。传入需求文档（PDF/DOCX/MD/TXT），由 AI 自动分析并结合知识库中的历史文档生成更完善的测试用例。

---

## 快速启动

双击运行 `start.bat`，自动启动后端 API 和 Streamlit UI：

```
后端:   http://127.0.0.1:8000
API:    http://127.0.0.1:8000/docs
UI:     http://localhost:8501
```

关闭所有服务：`stop.bat`

---

## 功能流程

```
上传需求文档  →  AI 分析文档
                      ↓
              存入知识库（SQLite + ChromaDB 向量库）
                      ↓
              生成测试用例（结合历史知识库上下文）
                      ↓
              查看 / 导出测试用例（JSON / CSV）
```

---

## 项目结构

```
ai-test-generator/
├── main.py                  # FastAPI 后端入口
├── config.py                # 配置管理（Pydantic Settings）
├── api/
│   └── routes.py            # API 路由定义
├── models/
│   └── schemas.py           # Pydantic 数据模型
├── services/
│   ├── ai_client.py         # AI 客户端（支持 OpenAI / Anthropic）
│   ├── document_ingestion.py # 文档解析（PDF/DOCX/MD/TXT）
│   ├── analysis_service.py  # AI 需求分析
│   ├── embedding_service.py  # 文本向量化（sentence-transformers）
│   ├── retrieval_service.py  # ChromaDB 向量检索
│   └── test_generation.py    # 测试用例生成
├── storage/
│   ├── chroma_client.py      # ChromaDB 向量数据库
│   └── sqlite_store.py       # SQLite 关系数据库
├── prompts/
│   └── generation_prompt.py  # AI 生成提示词模板
├── ui/
│   └── app.py               # Streamlit 前端界面
└── data/                    # 数据存储目录
    ├── app.db               # SQLite 数据库
    └── chroma/              # ChromaDB 向量数据
```

---

## 配置说明

编辑 `.env` 文件：

```env
# AI Provider: openai（支持 MiniMax、DeepSeek 等 OpenAI 兼容接口）
AI_PROVIDER=openai

# OpenAI 兼容配置（MiniMax 示例）
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.minimaxi.com/v1
OPENAI_MODEL=MiniMax-M2.5

# 向量模型（本地运行，无需 API Key）
EMBEDDING_MODEL=all-MiniLM-L6-v2

# 存储路径
CHROMA_PERSIST_DIR=./data/chroma
SQLITE_DB_URL=sqlite:///./data/app.db
```

---

## 知识库说明

知识库由两部分组成，协同实现 RAG 检索增强：

| 存储 | 数据 | 说明 |
|------|------|------|
| **SQLite** | 文档记录、分析结果、测试用例 | 结构化持久化 |
| **ChromaDB** | 需求块向量、分析摘要向量 | 语义相似度检索 |

生成新用例时，系统会先从 ChromaDB 检索与当前文档相似的历史分析，作为上下文补充给 AI，从而生成更全面、更符合项目风格的测试用例。

---

## 测试用例格式

生成的测试用例包含以下字段（与模板一致）：

| 字段 | 说明 |
|------|------|
| 编号 | 用例唯一编号（TC-XXX） |
| 标题 | 测试用例标题 |
| 目录 | 模块/功能分组 |
| 负责人 | 留空或手动填写 |
| 前置条件 | 测试前需要满足的条件 |
| 步骤描述 | 详细的测试操作步骤 |
| 预期结果 | 期望的系统行为 |
| 优先级 | P0 / P1 / P2 |
| 类型 | 功能测试 / 边界测试 / 异常测试 / 安全测试 / 性能测试 |
| 来源 | 需求来源标记（用于追溯） |

---

## 依赖

```
pip install -r requirements.txt
```

主要依赖：FastAPI、Streamlit、SQLAlchemy、ChromaDB、sentence-transformers、openpyxl（用于导出 Excel 兼容格式）
