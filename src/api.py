from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 1. This tells Python to look in the same folder for "agent.py", 
# execute it, and grab the "app" variable from it.
from agent import app as ai_brain 

# 2. Initialize the FastAPI Interface
server = FastAPI(title="Agentic Support API")

class ChatRequest(BaseModel):
    prompt:str
    thread_id:str="1"
@server.post("/chat")
async def chat_getendpoint(chatmessage:ChatRequest):
    try:
        print(f"\n[FastAPI] Received prompt from UI: {chatmessage.prompt}")
        initial_state = {"messages": [("user", chatmessage.prompt)]}
        config = {"configurable": {"thread_id": chatmessage.thread_id}}
        
        final_state = await ai_brain.ainvoke(initial_state, config=config)
        final_answer=final_state["messages"][-1].content
        return {"status": "success", "response": final_answer}
    except Exception as e:
        print(f"[FastAPI Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))