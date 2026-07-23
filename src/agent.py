import os
import asyncio
import nest_asyncio
from typing import Annotated, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient

nest_asyncio.apply()
os.environ["OPENAI_API_KEY"] = "sk-your-real-api-key-here"

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

llm = ChatOpenAI(model="gpt-4o-mini")
mcp_client = MultiServerMCPClient({
    "VectorDB_Server": {
        "command": "python",
        "args": ["mcp_db.py"],
        "transport": "stdio"
    }
})
tools = asyncio.run(mcp_client.get_tools())
llm_with_tools = llm.bind_tools(tools)

# FIXED: Made the thinker node fully asynchronous
async def thinker_node(state: AgentState):
    print("[LangGraph] AI is thinking...")
    # FIXED: using ainvoke instead of invoke
    ans = await llm_with_tools.ainvoke(state["messages"])
    return {"messages": [ans]}

executor_node = ToolNode(tools) # FIXED: spelling matched below

workflow = StateGraph(AgentState)

workflow.add_node("thinker", thinker_node)
workflow.add_node("executor", executor_node)

workflow.add_edge(START, "thinker")

# FIXED: Pluralized add_conditional_edges
workflow.add_conditional_edges(
    "thinker",
    tools_condition,
    {
        "tools": "executor",
        END: END
    }
)
workflow.add_edge("executor", "thinker")

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)