import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

load_dotenv()


def query_neo4j(cypher_query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute Cypher query and return results
    
    Args:
        cypher_query: Cypher query
        parameters: Query parameters (optional)
    
    Returns:
        Query results list
    """
    driver = None
    try:
        # 连接Neo4j数据库
        driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))
        
        with driver.session(database="kggraph") as session:
            result = session.run(cypher_query, parameters or {})
            
            # 将结果转换为字典列表
            records = []
            for record in result:
                records.append(dict(record))
            
            return records
            
    except Exception as e:
        return [{"error": f"查询失败: {str(e)}"}]
    
    finally:
        if driver:
            driver.close()


def tools_to_openai_schema(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert tool schema to OpenAI function call format
    
    Args:
        tools: Tool definition list, each tool contains name, description, parameters, etc.
    
    Returns:
        Tool list in OpenAI function call format
    """
    openai_functions = []
    
    for tool in tools:
        function_def = {
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {
                    "type": "object",
                    "properties": {},
                    "required": []
                })
            }
        }
        openai_functions.append(function_def)
    
    return openai_functions
