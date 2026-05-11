import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.database import init_db
from backend.auth import register_user, login_user, create_token, decode_token
from agent.agent_react import ReactAgent

CHECKPOINT_DB = str(Path(__file__).parent.parent / "data" / "checkpoints.sqlite")

agent: ReactAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB) as checkpointer:
        init_db()
        agent = ReactAgent(checkpointer=checkpointer)
        yield


app = FastAPI(title="智扫通客服 API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer = HTTPBearer()


# ── 鉴权依赖 ─────────────────────────────────────────────────────────────────
def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    payload = decode_token(cred.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    return {"user_id": int(payload["sub"]), "username": payload["username"]}


# ── 请求模型 ─────────────────────────────────────────────────────────────────
class AuthBody(BaseModel):
    username: str
    password: str

class ChatBody(BaseModel):
    message: str


# ── 认证接口 ─────────────────────────────────────────────────────────────────
@app.post("/auth/register")
def api_register(body: AuthBody):
    if len(body.username) < 2 or len(body.password) < 6:
        raise HTTPException(400, "用户名至少2位，密码至少6位")
    result = register_user(body.username, body.password)
    if not result["ok"]:
        raise HTTPException(400, "用户名已存在")
    token = create_token(result["user_id"], result["username"])
    return {"token": token, "user_id": result["user_id"], "username": result["username"]}


@app.post("/auth/login")
def api_login(body: AuthBody):
    result = login_user(body.username, body.password)
    if not result["ok"]:
        raise HTTPException(401, result["error"])
    token = create_token(result["user_id"], result["username"])
    return {"token": token, "user_id": result["user_id"], "username": result["username"]}


# ── 清空会话（重置 checkpointer thread） ──────────────────────────────────────
@app.post("/chat/clear")
async def chat_clear(user: dict = Depends(current_user)):
    # checkpointer 按 thread_id 隔离，新对话只需前端切换到新 thread_id 即可。
    # 此处返回一个新 thread_id，前端存储并在后续请求中使用。
    import time
    new_thread = f"{user['user_id']}_{int(time.time())}"
    return {"ok": True, "thread_id": new_thread}


# ── 聊天 SSE 接口 ─────────────────────────────────────────────────────────────
def sse(data: dict) -> str:
    return f"data:{json.dumps(data, ensure_ascii=False)}\n\n"


class ChatStreamBody(BaseModel):
    message: str
    thread_id: str | None = None


@app.post("/chat/stream")
async def chat_stream(body: ChatStreamBody, user: dict = Depends(current_user)):
    user_id = str(user["user_id"])
    # 默认 thread_id = user_id（每个用户一条持久化主线程）
    thread_id = body.thread_id or user_id
    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}

    async def generate():
        try:
            async for chunk in agent.agent.astream(
                {"messages": [HumanMessage(content=body.message)]},
                config=config,
            ):
                for _, node_output in chunk.items():
                    if not isinstance(node_output, dict):
                        continue
                    for msg in node_output.get("messages", []):
                        if isinstance(msg, AIMessage):
                            if msg.tool_calls:
                                for tc in msg.tool_calls:
                                    yield sse({
                                        "type": "tool_call",
                                        "name": tc["name"],
                                        "args": tc["args"],
                                    })
                            if msg.content:
                                yield sse({"type": "token", "content": msg.content})
                        elif isinstance(msg, ToolMessage):
                            yield sse({
                                "type": "tool_result",
                                "name": msg.name or "",
                                "content": msg.content[:300],
                            })
        except Exception as e:
            yield sse({"type": "token", "content": f"[错误] {e}"})
        yield "data:[DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=False)
