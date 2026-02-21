import chainlit as cl
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import orchestrate
from core.trace.event import TraceEvent, EventType
from core.config import get_llm_config

# Get available models from config
def get_available_models():
    try:
        config = get_llm_config()
        return list(config.keys())
    except Exception:
        return ["qwen3-30b"] # Fallback

class ChainlitTraceObserver:
    """Streams agent events to the Chainlit UI"""
    def __init__(self):
        self.current_step = None
        
    async def on_event(self, event: TraceEvent):
        # We need to run sync code in async loop, or use cl.run_sync
        # But wait, orchestrator is sync. This listener is called from sync code.
        # We need to dispatch to Chainlit's async loop if possible, or use cl.run_sync
        
        # Chainlit 1.0+ context handling is tricky from background threads/sync code.
        # However, if we run orchestrator in a thread (cl.make_async), we can use cl.run_sync inside?
        # Actually, simpler: We will run orchestrator in a separate thread, and use cl.run_sync to update UI.
        
        await self._process_event(event)

    async def _process_event(self, event: TraceEvent):
        if event.type == EventType.PLANNER_CALL:
            await cl.Message(content=f"🧠 **Planning**...").send()
            
        elif event.type == EventType.PLANNER_OUTPUT:
            action = event.data.get("action", {})
            mode = action.get("mode", "UNKNOWN")
            thought = action.get("thought", "")
            
            # Show thought process in an expander or step
            async with cl.Step(name="Planner") as step:
                step.output = f"**Mode**: {mode}\n**Thought**: {thought}"
            
        elif event.type == EventType.TOOL_CALL:
            tool = event.data.get("tool")
            args = event.data.get("args")
            async with cl.Step(name=f"Tool: {tool}") as step:
                step.input = str(args)
                
        elif event.type == EventType.TOOL_RESULT:
            # We don't have the step object from TOOL_CALL easily here unless we track state.
            # For MVP, just print result.
            result = str(event.data.get("result", ""))
            truncated = (result[:200] + "...") if len(result) > 200 else result
            await cl.Message(content=f"🔧 **Tool Result**: {truncated}").send()

        elif event.type == EventType.WRITER_OUTPUT:
            # The final answer is usually returned by orchestrate(), 
            # but we can also stream it here if we want partials.
            # Writer output is the final answer.
            pass
            
        elif event.type == EventType.ERROR:
            await cl.Message(content=f"❌ **Error**: {event.data.get('error')}").send()

@cl.set_chat_profiles
async def chat_profile():
    models = get_available_models()
    return [
        cl.ChatProfile(
            name=model,
            markdown_description=f"Use **{model}** model.",
            icon="https://picsum.photos/200",
        )
        for model in models
    ]

@cl.on_chat_start
async def start():
    # Get selected profile (model)
    chat_profile = cl.user_session.get("chat_profile")
    if not chat_profile:
        chat_profile = get_available_models()[0]
    
    # Store it for later use (redundant but explicit)
    cl.user_session.set("model", chat_profile)
    
    await cl.Message(content=f"**Memora Agent** is ready! Using model: **{chat_profile}**.\nUpload files or ask questions.").send()

@cl.on_message
async def main(message: cl.Message):
    # Handle files
    user_input = message.content
    uploaded_files = []
    
    # Get selected model
    model = cl.user_session.get("chat_profile")
    if not model:
        model = "qwen3-30b" # Fallback

    if message.elements:
        for element in message.elements:
            if isinstance(element, cl.File) or isinstance(element, cl.Image):
                # Save to a temp location or use the path provided by Chainlit
                # Chainlit stores temp files. We can get the path.
                path = element.path
                if path:
                    uploaded_files.append(path)
                    
    if uploaded_files:
        user_input += f"\n\n[System] User uploaded files: {', '.join(uploaded_files)}"

    # Run Agent
    # We need to run the blocking orchestrator in a thread
    # And we need a way to stream events back to the main loop.
    
    # Bridge:
    observer = ChainlitTraceObserver()
    
    # Wrapper for sync listener to call async chainlit methods
    def sync_listener(event: TraceEvent):
        cl.run_sync(observer.on_event(event))

    # Run blocking orchestrator
    response = await cl.make_async(orchestrate)(
        user_input=user_input, 
        model=model, # Pass the selected model
        on_trace=sync_listener
    )
    
    # Send Final Answer
    await cl.Message(content=response).send()
