import json
import time

import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from iat_ws_python3 import get_res  # 语音识别

# load_dotenv('.env.example')

app = FastAPI()

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conversation_history = []  # 储存多轮对话的历史消息

url = 'http://localhost:11434/api/chat'


# 读取 prompt 文件并发送到 AI（DeepSeek）
async def send_prompt_to_ai():
    with open("prompt.txt", "r", encoding="utf-8") as prompt_file:
        prompt_content = prompt_file.read()

    # 添加用户的消息
    conversation_history.append({"role": "user", "content": prompt_content})
    print(conversation_history)

    response = requests.post(url, json={
        "model": "qwen2.5:1.5b-instruct",
        "messages": conversation_history,
        'stream': False
    })

    # 添加 AI 的响应到对话历史
    json_data = json.loads(response.text)
    conversation_history.append(json_data['message'])
    print(f"Messages Round 1: {conversation_history}")

# 启动时调用 send_prompt_to_ai
@app.on_event("startup")
async def startup_event():
    print("正在启动应用，准备发送 prompt 到 AI...")
    await send_prompt_to_ai()

@app.post("/upload-audio/")
async def upload_audio(file: UploadFile = File(...)):
    file_location = f"./audio_files/{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
    # 语音识别开始时间
    speech_start_time = time.time()
    user_content = get_res(file_location)  # 语音识别
    speech_end_time = time.time()
    print(f'speech_recognization_time: {speech_end_time - speech_start_time}')

    # 添加用户的消息到对话历史
    conversation_history.append({"role": "user", "content": user_content})
    llm_start_time = time.time()

    response = requests.post(url, json={
        "model": "qwen2.5:1.5b-instruct",
        "messages": conversation_history,
        'stream': False
    })
    llm_end_time = time.time()
    print(f'llm_recognization_time: {llm_end_time - llm_start_time}')

    # 添加 AI 的响应到对话历史
    json_data = json.loads(response.text)
    conversation_history.append(json_data['message'])
    ai_response = json_data['message']['content']
    print(conversation_history)
    return JSONResponse(content={
        "user_content": user_content,  # 返回用户语音识别的内容
        "ai_response": ai_response  # 返回 AI 的响应
    })

