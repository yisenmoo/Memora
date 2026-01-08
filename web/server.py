import json
import logging
from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from llm.router import list_models, get_llm
from core.protocol.request import LLMRequest, Message
from core.orchestrator import orchestrate

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="web/static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("web/static/index.html")

@app.get("/api/models")
async def get_models():
    """List available models from config"""
    models = list_models()
    # Move default model to top if exists
    default_id = "qwen3-30b"
    models.sort(key=lambda x: 0 if x["id"] == default_id else 1)
    return models

class ChatRequest(BaseModel):
    model: str
    messages: List[dict] # [{"role": "user", "content": "..."}]
    temperature: float = 0.7
    stream: bool = True

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    logger.info(f"Chat request for model: {req.model}")
    
    # 目前我们只是简单的调用 orchestrate，它不是 stream 的。
    # 为了支持 Web 的流式效果，我们暂时只能让 orchestrate 返回完整结果，然后伪装成 stream 推送。
    # 或者，我们需要重构 orchestrator 使其支持 yield。
    # 鉴于任务要求 "Planner -> Tool -> Orchestrator -> Writer 闭环"，且 "不引入复杂模块"，
    # 我们先实现非流式的 Orchestrator 调用，然后前端一次性展示结果。
    
    # 注意：Orchestrator 内部目前是 print 过程，web 端看不到过程。
    # 这是一个妥协。真正的 Agent Stream 需要更复杂的 Event Bus。
    
    try:
        # 获取用户最新的输入
        user_input = req.messages[-1]["content"] if req.messages else ""
        
        # 调用 Orchestrator
        # 注意：这里我们简化了，没有传历史 Context 给 Orchestrator，
        # 因为 Orchestrator 内部维护了自己的 Context (ReAct Loop)。
        # 如果需要多轮对话，需要把 history 传进去。
        
        # 但 Orchestrator 目前设计是单次任务闭环 (Loop 5 次)。
        
        final_answer = orchestrate(user_input, model=req.model)
        
        # 伪装成流式响应，为了兼容前端代码
        return StreamingResponse(
            fake_stream_generator(final_answer),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        return {"error": str(e)}

def fake_stream_generator(text):
    """Yields the full text as a single chunk (or split it)"""
    import time
    # Simulate thinking time
    yield f"data: {json.dumps({'type': 'thinking', 'text': 'Orchestrating tools...'})}\n\n"
    
    # Output result
    data = {
        "type": "output",
        "text": text,
        "source": "orchestrator",
        "ts": time.time()
    }
    yield f"data: {json.dumps(data)}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
