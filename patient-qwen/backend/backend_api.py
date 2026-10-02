import asyncio
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from iat_ws_python3 import get_res  # 语音识别
from pydantic import BaseModel


MODEL_PATH = os.environ.get(
    "QWEN_MODEL_PATH",
    "/data1/szeyu/.cache/Qwen/Qwen3-VL-8B-Instruct-FP8",
)
MAX_NEW_TOKENS = int(os.environ.get("QWEN_MAX_NEW_TOKENS", "512"))
TEMPERATURE = float(os.environ.get("QWEN_TEMPERATURE", "0.7"))
TOP_P = float(os.environ.get("QWEN_TOP_P", "0.9"))
PRELOAD_QWEN = os.environ.get("QWEN_PRELOAD", "1").lower() not in {"0", "false", "no"}

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
_generation_lock = threading.Lock()


class ChatTextRequest(BaseModel):
    text: str


class LocalQwenClient:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.processor = None
        self.model = None
        self.torch = None

    def load(self):
        if self.model is not None:
            return

        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except Exception as exc:
            raise RuntimeError(
                "无法导入本地 Qwen 推理依赖。请确认当前 Python 环境中已安装 "
                "torch 和支持 Qwen3-VL 的 transformers。"
            ) from exc

        model_dir = Path(self.model_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"本地模型目录不存在: {model_dir}")

        self.torch = torch
        print(f"正在加载本地 Qwen 模型: {model_dir}")
        self.processor = AutoProcessor.from_pretrained(
            model_dir,
            trust_remote_code=True,
            local_files_only=True,
        )
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_dir,
            dtype="auto",
            device_map="auto",
            trust_remote_code=True,
            local_files_only=True,
        )
        self.model.eval()
        print("本地 Qwen 模型加载完成")

    def chat(self, messages):
        self.load()

        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.processor(text=[text], return_tensors="pt")
        inputs = {
            key: value.to(self.model.device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }

        do_sample = TEMPERATURE > 0
        generate_kwargs = {
            "max_new_tokens": MAX_NEW_TOKENS,
            "do_sample": do_sample,
        }
        if do_sample:
            generate_kwargs.update({"temperature": TEMPERATURE, "top_p": TOP_P})

        with _generation_lock, self.torch.inference_mode():
            output_ids = self.model.generate(**inputs, **generate_kwargs)

        prompt_len = inputs["input_ids"].shape[-1]
        answer_ids = output_ids[:, prompt_len:]
        answer = self.processor.batch_decode(
            answer_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]
        return answer.strip()


qwen_client = LocalQwenClient(MODEL_PATH)


async def ask_qwen():
    return await asyncio.to_thread(qwen_client.chat, conversation_history)


def load_initial_prompt():
    with open("prompt.txt", "r", encoding="utf-8") as prompt_file:
        prompt_content = prompt_file.read()

    conversation_history.append({"role": "system", "content": prompt_content})
    print(conversation_history)


@app.on_event("startup")
async def startup_event():
    print("正在启动应用，加载初始 prompt...")
    load_initial_prompt()
    if PRELOAD_QWEN:
        print("正在启动应用，预加载本地 Qwen...")
        await asyncio.to_thread(qwen_client.load)
    else:
        print("跳过 Qwen 预加载，将在第一次问答时加载。")


@app.get("/health")
async def health():
    return {"status": "ok", "model_path": MODEL_PATH}


@app.post("/chat-text/")
async def chat_text(request: ChatTextRequest):
    try:
        user_content = request.text.strip()
        if not user_content:
            raise RuntimeError("文本不能为空。")

        conversation_history.append({"role": "user", "content": user_content})
        llm_start_time = time.time()
        ai_response = await ask_qwen()
        llm_end_time = time.time()
        print(f"llm_recognization_time: {llm_end_time - llm_start_time}")

        conversation_history.append({"role": "assistant", "content": ai_response})
        print(conversation_history)
        return JSONResponse(
            content={
                "user_content": user_content,
                "ai_response": ai_response,
            }
        )
    except Exception as exc:
        print(f"chat-text failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def recognize_uploaded_audio(file: UploadFile):
    audio_dir = Path("./audio_files")
    audio_dir.mkdir(parents=True, exist_ok=True)
    file_location = audio_dir / file.filename
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())

    if file_location.stat().st_size < 16000:
        raise RuntimeError("录音文件太短，请重新录音，建议至少说 1 秒以上。")

    speech_start_time = time.time()
    user_content = get_res(str(file_location))  # 语音识别
    speech_end_time = time.time()
    print(f"speech_recognization_time: {speech_end_time - speech_start_time}")

    if not user_content:
        raise RuntimeError("语音识别未返回文字，请检查录音内容、讯飞配置或网络连接。")

    return user_content


@app.post("/asr-test/")
async def asr_test(file: UploadFile = File(...)):
    try:
        user_content = await recognize_uploaded_audio(file)
        return JSONResponse(content={"user_content": user_content})
    except Exception as exc:
        print(f"asr-test failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/upload-audio/")
async def upload_audio(file: UploadFile = File(...)):
    try:
        user_content = await recognize_uploaded_audio(file)
        conversation_history.append({"role": "user", "content": user_content})
        llm_start_time = time.time()
        ai_response = await ask_qwen()
        llm_end_time = time.time()
        print(f"llm_recognization_time: {llm_end_time - llm_start_time}")

        conversation_history.append({"role": "assistant", "content": ai_response})
        print(conversation_history)
        return JSONResponse(
            content={
                "user_content": user_content,
                "ai_response": ai_response,
            }
        )
    except Exception as exc:
        print(f"upload-audio failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
