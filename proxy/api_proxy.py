from fastapi import FastAPI, Request, HTTPException
import httpx
import os
from pydantic import BaseModel

app = FastAPI(title="LLM API 统一代理")

# 从环境变量读取 API Key，不用硬编码
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
GPT_BASE_URL = "https://api.openai.com"

# 限流计数器（简易版，防止滥用）
request_count = 0
MAX_REQUESTS = 1000  # 演示期限制，可按需调整

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    global request_count
    request_count += 1
    if request_count > MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="请求次数已达上限，请联系管理员")
    response = await call_next(request)
    return response

@app.post("/deepseek/{path:path}")
async def proxy_deepseek(path: str, request: Request):
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=500, detail="DeepSeek API Key 未配置")
    
    url = f"{DEEPSEEK_BASE_URL}/{path}"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    body = await request.json()
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(url, headers=headers, json=body)
            return resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="API 请求超时")

@app.post("/gpt/{path:path}")
async def proxy_gpt(path: str, request: Request):
    # 同理实现 GPT 转发，这里省略，和上面 DeepSeek 逻辑一致
    pass

@app.get("/health")
async def health_check():
    return {"status": "ok", "request_count": request_count}