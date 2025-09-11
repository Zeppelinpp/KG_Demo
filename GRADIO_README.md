# Knowledge Graph Chat Assistant - Gradio Web界面

这是一个基于Gradio构建的Web界面，用于与Neo4j知识图谱进行智能对话。

## 功能特性

- 🌐 **Web界面**: 友好的用户界面，支持Markdown渲染
- 🧠 **智能对话**: 支持自然语言查询知识图谱
- 🔄 **流式输出**: 实时显示AI回复
- 📊 **双模式**: 支持静态Schema和动态Schema模式
- 🎯 **纯净输出**: 只显示AI回复，不展示Cypher查询执行过程

## 快速开始

### 1. 安装依赖

```bash
# 安装Gradio依赖
pip install gradio>=5.0.0

# 或者使用uv安装项目依赖
uv sync
```

### 2. 配置环境变量

确保`.env`文件中包含以下配置：

```env
# Neo4j数据库配置
NEO4J_URI=bolt://localhost:7687
NEO4J_DATABASE=neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# OpenAI配置
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_base_url
```

### 3. 启动Web界面

```bash
# 方式1: 直接运行
python gradio_app.py

# 方式2: 使用启动脚本
python run_gradio.py

# 方式3: 自定义端口和主机
python run_gradio.py --host 127.0.0.1 --port 8080
```

### 4. 访问界面

打开浏览器访问 `http://localhost:7860`

## 界面说明

### 左侧控制面板

- **Schema模式选择**: 
  - `static`: 使用预加载的schema（推荐）
  - `dynamic`: 动态获取schema信息

- **系统控制**:
  - 🔄 重新初始化系统
  - 🗑️ 清空对话历史

- **系统状态**: 显示当前系统状态和初始化信息

### 右侧对话区域

- **聊天界面**: 支持Markdown渲染的对话区域
- **消息输入**: 支持多行输入和快捷键发送
- **实时响应**: 流式显示AI回复

## 使用技巧

1. **自然语言查询**: 直接用中文或英文提问
   - "查询所有客户信息"
   - "统计订单总金额"
   - "找出最活跃的用户"

2. **特殊命令**:
   - 输入 `clear` 清空对话历史

3. **复杂查询**: AI会自动处理多步查询和复杂业务逻辑

## 技术架构

- **前端**: Gradio Web界面
- **后端**: 基于现有的chat_session功能
- **AI模型**: 支持OpenAI兼容的LLM
- **数据库**: Neo4j图数据库
- **日志**: 后台日志记录，不干扰界面显示

## 与命令行版本的区别

| 功能 | 命令行版本 | Gradio Web版本 |
|------|-----------|----------------|
| 界面 | Rich终端界面 | Web浏览器界面 |
| Cypher显示 | 显示执行的Cypher | 隐藏Cypher执行过程 |
| 工具调用 | 显示详细过程 | 只显示最终结果 |
| 多用户 | 单用户 | 支持多用户访问 |
| 部署 | 本地终端 | 可部署到服务器 |

## 故障排除

### 常见问题

1. **初始化失败**
   - 检查Neo4j数据库连接
   - 确认环境变量配置正确
   - 查看后台日志文件

2. **端口被占用**
   - 使用 `--port` 参数指定其他端口
   - 或者停止占用7860端口的进程

3. **模型调用失败**
   - 检查OpenAI API配置
   - 确认网络连接正常

### 日志查看

系统日志保存在 `logs/kg_demo.log` 文件中，可以查看详细的错误信息和调试信息。

## 开发说明

如需修改界面或功能，主要文件：

- `gradio_app.py`: 主界面逻辑
- `run_gradio.py`: 启动脚本
- `src/core.py`: 核心Agent逻辑（已适配Web模式）
- `src/pipeline.py`: 管道和初始化逻辑
