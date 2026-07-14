import sys
import asyncio
import httpx
import chainlit as cl

# --- WINDOWS + PYTHON 3.14 FIX ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
# ---------------------------------

# This tells the Frontend exactly where to find your FastAPI Backend
FASTAPI_URL = "http://127.0.0.1:8000/chat"

@cl.on_chat_start
async def start_chat():
    await cl.Message(content="Hello! I am connected to the FastAPI backend. How can I help you?").send()

@cl.on_message
async def handle_user_prompt(message: cl.Message):
    user_prompt = message.content
    
    # Create a loading spinner in the UI while we wait for FastAPI
    msg = cl.Message(content="*Thinking...*")
    await msg.send()
    
    try:
        # HERE IS HTTPX IN ACTION!
        # It takes what you typed in the UI, and shoots it over the internet 
        # to your FastAPI backend.
        async with httpx.AsyncClient() as client:
            response = await client.post(
                FASTAPI_URL, 
                json={"prompt": user_prompt},
                timeout=30.0 
            )
            
            if response.status_code == 200:
                # Extract the answer from the FastAPI JSON
                data = response.json()
                msg.content = data["response"]
            else:
                msg.content = f"⚠️ Backend Error: {response.status_code}"
                
    except Exception as e:
        msg.content = f"⚠️ Could not connect to FastAPI server. Is it running? (Error: {str(e)})"
        
    # Update the UI with the final answer
    await msg.update()