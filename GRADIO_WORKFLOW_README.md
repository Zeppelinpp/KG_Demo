# Gradio Workflow Interface for Knowledge Graph Assistant

## 🚀 Overview

This is an enhanced Gradio interface that integrates with LlamaIndex Workflows to provide a beautiful, interactive chat experience with real-time streaming, collapsible metadata display, and parallel query execution.

## ✨ Features

### 1. **Streaming Workflow Events**
- Real-time updates as the workflow progresses through different stages
- Uses `ctx.write_event_to_stream()` from LlamaIndex for event streaming
- Visual feedback for each step: Analysis → Execution → Report

### 2. **Collapsible Metadata Display**
- Tool calls and intermediate results shown in expandable sections
- Uses Gradio's ChatMessage metadata feature for clean UI
- Click to expand/collapse detailed information without cluttering the main chat

### 3. **Parallel Query Execution**
- Main query and insight queries execute simultaneously using `ProcessPoolExecutor`
- Significant performance improvement over sequential execution
- Results collected and displayed as they complete

### 4. **Beautiful UI Design**
- Modern, clean interface with gradient styling
- Smooth animations and transitions
- Responsive layout with helpful tips and examples
- Custom CSS for enhanced visual appeal

## 📁 File Structure

```
KG_Demo/
├── gradio_workflow_app.py      # Main Gradio interface
├── src/
│   ├── workflow_v2.py          # Enhanced workflow with streaming events
│   └── workflow.py              # Original workflow (preserved)
└── test_workflow_gradio.py     # Test script
```

## 🛠️ Implementation Details

### Workflow Changes (`workflow_v2.py`)

1. **Event Types**:
   - `StreamMessageEvent`: For status updates with metadata
   - `ReportChunkEvent`: For streaming report content
   - `ToolCallEvent`: For tool execution details

2. **Streaming Integration**:
   ```python
   ctx.write_event_to_stream(
       StreamMessageEvent(
           message="Status update",
           metadata={"key": "value"}
       )
   )
   ```

3. **Parallel Execution**:
   - Uses `ProcessPoolExecutor` instead of `ThreadPoolExecutor`
   - Better performance for CPU-intensive tasks
   - Synchronous wrapper for async functions in multiprocessing

### Gradio Interface (`gradio_workflow_app.py`)

1. **Event Processing**:
   ```python
   async for event in handler.stream_events():
       if isinstance(event, StreamMessageEvent):
           # Handle status updates
       elif isinstance(event, ReportChunkEvent):
           # Stream report content
   ```

2. **Metadata Formatting**:
   - Converts metadata dict to collapsible HTML
   - Automatic formatting for lists, dicts, and strings
   - Clean presentation with syntax highlighting

3. **Message Post-processing**:
   - Appends formatted metadata to message content
   - Maintains chat history with rich formatting

## 🚀 Running the Application

### Prerequisites

1. Ensure all dependencies are installed:
   ```bash
   pip install gradio llama-index openai pydantic rich
   ```

2. Set up environment variables in `.env`:
   ```
   OPENAI_API_KEY=your_key
   OPENAI_BASE_URL=your_base_url
   ```

3. Ensure Neo4j and Milvus are running and configured

### Launch the Interface

```bash
python gradio_workflow_app.py
```

The interface will be available at `http://localhost:7860`

### Test the Workflow

```bash
python test_workflow_gradio.py
```

## 📊 Usage Examples

### Simple Query
```
"分析苹果公司的财务状况"
```

### Complex Analysis
```
"比较腾讯、阿里巴巴和字节跳动的市场表现和竞争优势"
```

### Trend Analysis
```
"分析半导体行业的供应链关系和技术发展趋势"
```

## 🎨 UI Features

### Chat Interface
- **Streaming responses**: See the report being generated in real-time
- **Progress indicators**: Visual feedback for each workflow stage
- **Copy button**: Easy copying of responses

### Metadata Display
- **Collapsible sections**: Click to expand/collapse
- **Formatted content**: JSON, lists, and text properly formatted
- **Color coding**: Different colors for different types of information

### Interactive Elements
- **Example queries**: Quick-start templates
- **Clear button**: Reset conversation
- **Responsive design**: Works on different screen sizes

## 🔧 Customization

### Modify Workflow Steps

Edit `src/workflow_v2.py` to customize:
- Analysis logic
- Query execution strategy
- Report generation format

### Adjust UI Styling

Edit `gradio_workflow_app.py` custom CSS:
- Colors and gradients
- Animations
- Layout and spacing

### Add New Event Types

1. Define new event class in `workflow_v2.py`:
   ```python
   class CustomEvent(Event):
       data: Any
   ```

2. Emit event in workflow:
   ```python
   ctx.write_event_to_stream(CustomEvent(data=...))
   ```

3. Handle in Gradio interface:
   ```python
   if isinstance(event, CustomEvent):
       # Process custom event
   ```

## 📝 Notes

- The parallel execution uses multiprocessing for better performance
- Metadata is automatically formatted and made collapsible
- The report streams character by character for better UX
- Tool calls are not displayed in detail to keep the interface clean
- All intermediate results are shown in collapsible metadata sections

## 🐛 Troubleshooting

### Issue: Workflow timeout
**Solution**: Increase timeout in workflow initialization:
```python
workflow = KGWorkflow(timeout=1000)  # Increase as needed
```

### Issue: Memory issues with large queries
**Solution**: Reduce parallel workers or use smaller batch sizes

### Issue: Gradio not updating
**Solution**: Ensure `queue=True` is set in event handlers

## 📚 References

- [LlamaIndex Workflows Documentation](https://docs.llamaindex.ai/en/stable/understanding/workflows/)
- [Gradio ChatInterface Guide](https://www.gradio.app/guides/creating-a-chatbot-fast)
- [Python Multiprocessing](https://docs.python.org/3/library/multiprocessing.html)
