import os
import json
import inspect
from neo4j import GraphDatabase
from dotenv import load_dotenv
from typing import List, Callable, Dict, Any, Union
from openai import AsyncOpenAI
from tools import tools_to_openai_schema
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
import datetime

load_dotenv()


class FunctionCallingAgent:
    def __init__(self, model: str, tools: List[Callable]):
        self.model = model
        self.tool_functions = {
            tool.__name__: tool for tool in tools
        }  # Map tool names to functions

        # Convert callable functions to tool schema format for tools_to_openai_schema
        tool_schemas = []
        for tool in tools:
            sig = inspect.signature(tool)
            parameters = {"type": "object", "properties": {}, "required": []}

            # Extract parameters from function signature
            for param_name, param in sig.parameters.items():
                param_type = "string"  # Default type
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_type = "integer"
                    elif param.annotation == float:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                    elif param.annotation == list:
                        param_type = "array"
                    elif param.annotation == dict:
                        param_type = "object"

                parameters["properties"][param_name] = {"type": param_type}

                # Add to required if no default value
                if param.default == inspect.Parameter.empty:
                    parameters["required"].append(param_name)

            tool_schema = {
                "name": tool.__name__,
                "description": tool.__doc__ or f"Execute {tool.__name__}",
                "parameters": parameters,
            }
            tool_schemas.append(tool_schema)

        # Use existing tools_to_openai_schema function
        self.tools = tools_to_openai_schema(tool_schemas)
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL")
        )
        self.max_iterations = 10  # Prevent infinite loops

    async def _handle_tool_call(self, tool_call: Dict[str, Any]) -> str:
        """Execute a tool call and return the result"""
        try:
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])

            # Get the actual function
            if function_name not in self.tool_functions:
                return f"Error: Tool '{function_name}' not found"

            tool_function = self.tool_functions[function_name]

            # Execute the function
            if hasattr(tool_function, "__call__"):
                result = tool_function(**function_args)
                # Handle async functions if needed
                if hasattr(result, "__await__"):
                    result = await result
                return str(result)
            else:
                return f"Error: '{function_name}' is not callable"

        except Exception as e:
            return f"Error executing tool call: {str(e)}"

    async def run(self, messages: List[Dict[str, Any]]) -> str:
        """Run the agent with tool calling until a final answer is reached"""
        current_messages = messages.copy()
        iteration = 0

        while iteration < self.max_iterations:
            try:
                # Make API call to OpenAI
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=current_messages,
                    tools=self.tools,
                    tool_choice="auto",
                )

                assistant_message = response.choices[0].message

                # Add assistant message to conversation
                current_messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": assistant_message.tool_calls,
                    }
                )

                # Check if there are tool calls to execute
                if assistant_message.tool_calls:
                    # Execute each tool call
                    for tool_call in assistant_message.tool_calls:
                        tool_result = await self._handle_tool_call(
                            tool_call.model_dump()
                        )

                        # Add tool result to conversation
                        current_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_result,
                            }
                        )

                    # Continue the loop to let the model process tool results
                    iteration += 1
                    continue

                else:
                    # No tool calls, return the final response
                    return assistant_message.content or "No response generated"

            except Exception as e:
                return f"Error in agent execution: {str(e)}"

        return "Maximum iterations reached without final answer"


class Neo4jSchemaExtractor:
    """Neo4j Schema提取器"""
    
    def __init__(self, uri: str, database: str, username: str = "neo4j", password: str = "password", console: Console = None):
        self.uri = uri
        self.database = database
        self.username = username
        self.password = password
        self.console = console or Console()
        self.driver = None
        
    def connect(self) -> bool:
        """连接到Neo4j数据库"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
            
            # 测试连接
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            
            self.console.print(Panel(
                f"[green]✓[/green] 成功连接到Neo4j数据库！\n"
                f"[bold cyan]连接URI:[/bold cyan] {self.uri}\n"
                f"[bold cyan]数据库:[/bold cyan] {self.database}",
                title="[bold green]数据库连接",
                border_style="green"
            ))
            return True
            
        except Exception as e:
            self.console.print(Panel(
                f"[bold red]❌ 连接Neo4j数据库失败！[/bold red]\n"
                f"[yellow]错误信息:[/yellow] {str(e)}",
                title="[bold red]连接失败",
                border_style="red"
            ))
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
    
    def extract_node_labels_and_properties(self) -> Dict[str, Dict]:
        """提取节点标签和属性"""
        node_schema = {}
        
        try:
            with self.driver.session(database=self.database) as session:
                # 获取所有节点标签
                result = session.run("CALL db.labels()")
                labels = [record["label"] for record in result]
                
                for label in labels:
                    # 获取该标签的属性
                    query = f"""
                    MATCH (n:{label})
                    WITH keys(n) as props
                    UNWIND props as prop
                    RETURN DISTINCT prop, 
                           apoc.meta.type(prop) as type,
                           COUNT(*) as frequency
                    ORDER BY frequency DESC
                    """
                    
                    # 如果没有APOC插件，使用基础查询
                    basic_query = f"""
                    MATCH (n:{label})
                    WITH keys(n) as props
                    UNWIND props as prop
                    RETURN DISTINCT prop, COUNT(*) as frequency
                    ORDER BY frequency DESC
                    """
                    
                    try:
                        result = session.run(query)
                        properties = []
                        for record in result:
                            properties.append({
                                'name': record['prop'],
                                'type': record.get('type', 'unknown'),
                                'frequency': record['frequency']
                            })
                    except:
                        # fallback到基础查询
                        result = session.run(basic_query)
                        properties = []
                        for record in result:
                            properties.append({
                                'name': record['prop'],
                                'type': 'unknown',
                                'frequency': record['frequency']
                            })
                    
                    # 获取节点计数
                    count_result = session.run(f"MATCH (n:{label}) RETURN COUNT(n) as count")
                    node_count = count_result.single()['count']
                    
                    # 获取示例数据
                    sample_result = session.run(f"MATCH (n:{label}) RETURN n LIMIT 3")
                    samples = []
                    for record in sample_result:
                        node = record['n']
                        sample = dict(node)
                        # 转换值为字符串以便JSON序列化
                        for key, value in sample.items():
                            if isinstance(value, (int, float, str, bool)) or value is None:
                                continue
                            else:
                                sample[key] = str(value)
                        samples.append(sample)
                    
                    node_schema[label] = {
                        'count': node_count,
                        'properties': properties,
                        'samples': samples
                    }
                    
        except Exception as e:
            self.console.print(f"[bold red]❌ 提取节点schema失败: {e}[/bold red]")
        
        return node_schema
    
    def extract_relationship_types_and_properties(self) -> Dict[str, Dict]:
        """提取关系类型和属性"""
        relationship_schema = {}
        
        try:
            with self.driver.session(database=self.database) as session:
                # 获取所有关系类型
                result = session.run("CALL db.relationshipTypes()")
                rel_types = [record["relationshipType"] for record in result]
                
                for rel_type in rel_types:
                    # 获取关系属性
                    query = f"""
                    MATCH ()-[r:{rel_type}]-()
                    WITH keys(r) as props
                    UNWIND props as prop
                    RETURN DISTINCT prop, COUNT(*) as frequency
                    ORDER BY frequency DESC
                    """
                    
                    result = session.run(query)
                    properties = []
                    for record in result:
                        properties.append({
                            'name': record['prop'],
                            'frequency': record['frequency']
                        })
                    
                    # 获取关系计数
                    count_result = session.run(f"MATCH ()-[r:{rel_type}]-() RETURN COUNT(r) as count")
                    rel_count = count_result.single()['count']
                    
                    # 获取关系的源节点和目标节点类型
                    pattern_result = session.run(f"""
                    MATCH (source)-[r:{rel_type}]->(target)
                    RETURN DISTINCT labels(source) as source_labels, 
                           labels(target) as target_labels,
                           COUNT(*) as frequency
                    ORDER BY frequency DESC
                    LIMIT 10
                    """)
                    
                    patterns = []
                    for record in pattern_result:
                        patterns.append({
                            'source_labels': record['source_labels'],
                            'target_labels': record['target_labels'],
                            'frequency': record['frequency']
                        })
                    
                    # 获取示例关系
                    sample_result = session.run(f"""
                    MATCH (source)-[r:{rel_type}]->(target)
                    RETURN labels(source) as source_labels, 
                           labels(target) as target_labels,
                           r as relationship
                    LIMIT 3
                    """)
                    
                    samples = []
                    for record in sample_result:
                        rel_data = dict(record['relationship'])
                        # 转换值为字符串以便JSON序列化
                        for key, value in rel_data.items():
                            if isinstance(value, (int, float, str, bool)) or value is None:
                                continue
                            else:
                                rel_data[key] = str(value)
                        
                        samples.append({
                            'source_labels': record['source_labels'],
                            'target_labels': record['target_labels'],
                            'properties': rel_data
                        })
                    
                    relationship_schema[rel_type] = {
                        'count': rel_count,
                        'properties': properties,
                        'patterns': patterns,
                        'samples': samples
                    }
                    
        except Exception as e:
            self.console.print(f"[bold red]❌ 提取关系schema失败: {e}[/bold red]")
        
        return relationship_schema
    
    def extract_database_constraints_and_indexes(self) -> Dict[str, List]:
        """提取数据库约束和索引"""
        constraints_indexes = {
            'constraints': [],
            'indexes': []
        }
        
        try:
            with self.driver.session(database=self.database) as session:
                # 获取约束
                try:
                    result = session.run("SHOW CONSTRAINTS")
                    for record in result:
                        constraints_indexes['constraints'].append(dict(record))
                except:
                    # 旧版本Neo4j
                    try:
                        result = session.run("CALL db.constraints()")
                        for record in result:
                            constraints_indexes['constraints'].append(dict(record))
                    except:
                        pass
                
                # 获取索引
                try:
                    result = session.run("SHOW INDEXES")
                    for record in result:
                        constraints_indexes['indexes'].append(dict(record))
                except:
                    # 旧版本Neo4j
                    try:
                        result = session.run("CALL db.indexes()")
                        for record in result:
                            constraints_indexes['indexes'].append(dict(record))
                    except:
                        pass
                        
        except Exception as e:
            self.console.print(f"[bold yellow]⚠️ 提取约束和索引信息失败: {e}[/bold yellow]")
        
        return constraints_indexes
    
    def extract_full_schema(self, output_file: str = None) -> Dict:
        """提取完整的数据库schema"""
        self.console.print()
        self.console.rule("[bold green]🔍 Neo4j Schema提取", style="green")
        
        if not self.connect():
            return {}
        
        try:
            self.console.print("[bold cyan]正在提取节点schema...[/bold cyan]")
            nodes_schema = self.extract_node_labels_and_properties()
            
            self.console.print("[bold cyan]正在提取关系schema...[/bold cyan]")
            relationships_schema = self.extract_relationship_types_and_properties()
            
            self.console.print("[bold cyan]正在提取约束和索引...[/bold cyan]")
            constraints_indexes = self.extract_database_constraints_and_indexes()
            
            # 组合完整schema
            full_schema = {
                'database_info': {
                    'uri': self.uri,
                    'database': self.database,
                    'extraction_time': str(__import__('datetime').datetime.now())
                },
                'nodes': nodes_schema,
                'relationships': relationships_schema,
                'constraints': constraints_indexes['constraints'],
                'indexes': constraints_indexes['indexes']
            }
            
            # 显示摘要
            self.display_schema_summary(full_schema)
            
            # 生成LLM提示模板
            llm_template = self.generate_llm_prompt_template(full_schema)
            
            # 保存到文件
            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(exist_ok=True)
                
                # 保存JSON格式的schema
                json_file = output_path.with_suffix('.json')
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(full_schema, f, ensure_ascii=False, indent=2)
                
                # 保存LLM提示模板
                template_file = output_path.with_suffix('.md')
                with open(template_file, 'w', encoding='utf-8') as f:
                    f.write(llm_template)
                
                self.console.print(Panel(
                    f"[green]✓[/green] Schema提取完成！\n"
                    f"[bold cyan]JSON文件:[/bold cyan] {json_file}\n"
                    f"[bold cyan]LLM模板:[/bold cyan] {template_file}\n"
                    f"[bold cyan]节点类型:[/bold cyan] {len(nodes_schema)}\n"
                    f"[bold cyan]关系类型:[/bold cyan] {len(relationships_schema)}",
                    title="[bold green]提取完成",
                    border_style="green"
                ))
            
            return full_schema
            
        except Exception as e:
            self.console.print(f"[bold red]❌ Schema提取失败: {e}[/bold red]")
            return {}
        
        finally:
            self.close()

