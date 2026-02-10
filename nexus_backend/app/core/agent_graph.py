"""
P0 Enhancement: LangGraph Agent Core
Implements a ReAct-style agent using LangGraph for multi-step reasoning and tool execution.
Replaces the manual loop in chat_service.py with a robust state machine.
"""
from typing import TypedDict, Annotated, List, Union, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.prebuilt import ToolExecutor, ToolInvocation
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# 1. Define Agent State
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], "The conversation history"]
    user_id: str
    org_id: str
    tools: List[Any] # Actual tool instances or definitions

# 2. Define Nodes

async def agent_node(state: AgentState):
    """
    The main agent node that calls the LLM.
    """
    messages = state["messages"]
    # We assume the model is initialized outside or here.
    # For now, let's create a ChatOpenAI instance with the tools bound.
    
    # Initialize Model (Could be cached or passed in state if serializable)
    model = ChatOpenAI(
        model=settings.OPENAI_API_MODEL or "gpt-4-turbo-preview",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.7,
        streaming=True
    )
    
    # Bind tools if available
    tools = state.get("tools", [])
    if tools:
        # Convert tools to OpenAI format if they are not already
        # Note: If tools are custom classes, we need a way to convert them.
        # Assuming tools are LangChain tools or compatible dicts.
        # If they are our custom tools (BaseTool), we need a wrapper.
        # For this prototype, we'll assume they are converted before passing to state["tools"]
        model = model.bind_tools(tools)
        
    response = await model.ainvoke(messages)
    return {"messages": [response]}

async def tool_node(state: AgentState):
    """
    The node that executes tool calls.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        # This shouldn't happen if edge logic is correct
        return {"messages": []}
    
    results = []
    # robust tool execution would typically involve a tool mapping.
    # Since our 'boss_tools' are custom, we need a way to execute them here.
    # We will assume a 'tool_executor' is available or we implement a simple one.
    
    # Placeholder for actual tool execution logic.
    # In a real integration, we'd pass a ToolExecutor in the state or context.
    # For now, we will mark this as "To Be Implemented" or use a mock response 
    # if we can't access the actual tool instances easily here.
    
    # We will invoke the tools manually for now to show the pattern
    formatted_tool_calls = last_message.tool_calls
    
    for tool_call in formatted_tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        # Here we would lookup the tool implementation
        # result = execute_tool(tool_name, tool_args, state["user_id"])
        
        # For now, return a placeholder to verify graph flow
        result = f"Tool {tool_name} executed with {tool_args}" 
        
        results.append(ToolMessage(
            tool_call_id=tool_id,
            name=tool_name,
            content=str(result)
        ))
        
    return {"messages": results}

# 3. Define Edges

def should_continue(state: AgentState) -> str:
    """
    Determine whether to continue to tools or end.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END

# 4. Build Graph
def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    workflow.set_entry_point("agent")
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()

# Global compiled graph
agent_app = build_agent_graph()

