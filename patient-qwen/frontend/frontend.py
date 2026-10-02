import os
import streamlit as st
import requests
import io
import subprocess
from audio_recorder_streamlit import audio_recorder
import pyttsx3
import base64
import time

st.title("医患问诊系统")

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# 检查是否已有引擎对象，避免重复创建
def init_tts_engine():
    try:
        return pyttsx3.init()
    except Exception as exc:
        print(f"TTS disabled: {exc}")
        return None


def speak_ai_response(text):
    engine = st.session_state.get("engine")
    if engine is None:
        return

    try:
        engine.say(text)
        audio_file = "ai_response.mp3"
        engine.save_to_file(text, audio_file)
        engine.runAndWait()
    except Exception as exc:
        print(f"TTS failed: {exc}")
        st.session_state.engine = None


def post_audio(files):
    try:
        session = requests.Session()
        session.trust_env = False
        return session.post(
            "http://localhost:8000/upload-audio/",
            files=files,
            timeout=600,
        )
    except requests.RequestException as exc:
        st.error(f"无法连接后端服务 http://localhost:8000：{exc}")
        return None


def post_text(text):
    try:
        session = requests.Session()
        session.trust_env = False
        return session.post(
            "http://localhost:8000/chat-text/",
            json={"text": text},
            timeout=600,
        )
    except requests.RequestException as exc:
        st.error(f"无法连接后端服务 http://localhost:8000：{exc}")
        return None


def show_request_error(response, label="请求失败"):
    if response is None:
        return

    detail = response.text or "<empty response body>"
    try:
        data = response.json()
        detail = data.get("detail", data)
    except ValueError:
        pass
    st.error(f"{label}，HTTP {response.status_code}。详细信息: {detail}")


def append_chat_result(response):
    user_text = response.json().get("user_content", "无识别结果")
    ai_response = response.json().get("ai_response", "无回应")
    st.session_state.chat_history.append(f"用户: {user_text}")
    st.session_state.chat_history.append(f"AI: {ai_response}")
    st.success(f"用户: {user_text}")
    st.success(f"AI: {ai_response}")
    toggle_gif_patient(True)
    speak_ai_response(ai_response)


if "engine" not in st.session_state:
    st.session_state.engine = init_tts_engine()


# st.session_state.engine.setProperty('voice', 'zh')

# 侧边栏用于上传文件
st.sidebar.subheader("上传语音文件")
uploaded_file = st.sidebar.file_uploader("上传您的语音文件", type=["pcm"])

# 使用 container 组织页面布局
chat_container = st.container()  # 历史对话区
audio_container = st.container()  # 录音区
gif_container_doctor = st.empty()  # 用于动态显示 GIF
gif_container_patient = st.empty()  # 用于动态显示 GIF

# 定义医生和病人的GIF和PNG路径
doctor_gif = "doctor.gif"
patient_gif = "patient.gif" 

# 将 GIF 文件转为 Base64 编码
def load_gif_as_base64(gif_path):
    with open(gif_path, "rb") as gif_file:
        return base64.b64encode(gif_file.read()).decode()
    
# 初始化医生和病人的GIF状态
doctor_gif_base64 = load_gif_as_base64(doctor_gif)
patient_gif_base64 = load_gif_as_base64(patient_gif)

def toggle_gif_doctor(show):
    if show:
        gif_container_doctor.markdown(f"""
        <div style='position: fixed; bottom: 20px; left: 340px; width: 350px; height: 350px;'>
            <img src="data:image/gif;base64,{doctor_gif_base64}" />
        </div>
        """, unsafe_allow_html=True)
        print("显示 doctor_gif!")
    else:
        gif_container_doctor.empty()  # 隐藏 GIF
        print("隐藏 doctor_gif!")

def toggle_gif_patient(show):
    if show:
        gif_container_patient.markdown(f"""
        <div style='position: fixed; bottom: 20px; right: 30px; width: 350px; height: 350px;'>
            <img src="data:image/gif;base64,{patient_gif_base64}" />
        </div>
        """, unsafe_allow_html=True)
        print("显示 patient_gif!")
    else:
        gif_container_patient.empty()  # 隐藏 GIF
        print("隐藏 patient_gif!")


st.sidebar.subheader("文本测试")
test_text = st.sidebar.text_area("直接输入问诊问题", value="你现在胸痛是什么感觉？")
if st.sidebar.button("发送文本测试"):
    with st.spinner("模型处理中，请稍等..."):
        response = post_text(test_text)
    if response is not None and response.status_code == 200:
        append_chat_result(response)
    else:
        show_request_error(response, "文本测试失败")


# 显示历史对话
with chat_container:
    if st.session_state.chat_history:
        for entry in st.session_state.chat_history:
            # 判断用户和AI的消息并对齐
            if entry.startswith("用户:"):
                st.markdown(f"<div style='text-align: right;'>{entry}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align: left;'>{entry}</div>", unsafe_allow_html=True)

# 自定义 CSS 将录音按钮放在页面的底部
with audio_container:
    st.markdown("""
        <style>
        .stApp {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100vh;
        }
        .audio-recorder-component {
            min-height: 196px !important;
            height: auto !important;
        }
        </style>
        """, unsafe_allow_html=True)

    toggle_gif_doctor(True)  # 显示 doctor.gif

    # 调用 audio_recorder() 组件录音
    audio_bytes = audio_recorder()

    # 检查是否有录音数据
    if audio_bytes:

        # 自动将录音转换为 PCM 格式并上传到后端
        def wav2pcm_ffmpeg(audio_bytes):
            # 创建临时 WAV 文件
            with open("temp.wav", "wb") as temp_wav:
                temp_wav.write(audio_bytes)

            # 使用 FFmpeg 将 WAV 转换为 PCM
            pcm_output = "output.pcm"
            command = [
                "../ffmpeg-master-latest-linux64-gpl/bin/ffmpeg", "-y", "-i", "temp.wav",
                "-acodec", "pcm_s16le", "-f", "s16le",
                "-ac", "1", "-ar", "16000",
                pcm_output
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr or "ffmpeg 转换音频失败")

            # 读取生成的 PCM 文件
            with open(pcm_output, "rb") as pcm_file:
                return pcm_file.read()

        # 记录转换pcm开始时间
        convert_start_time = time.time()
        # 调用函数将录音转换为 PCM
        try:
            pcm_data = wav2pcm_ffmpeg(audio_bytes)
        except Exception as exc:
            st.error(f"音频转换失败: {exc}")
            st.stop()
        if len(pcm_data) < 16000:
            st.error("录音时间太短，请重新录音，建议至少说 1 秒以上。")
            st.stop()
        convert_end_time = time.time()
        print(f'convert time:{convert_end_time - convert_start_time}')

        # 使用 st.spinner 显示后台处理中的状态
        with st.spinner('处理中，请稍等...'):
            # 上传 PCM 格式的音频文件到 FastAPI 后端
            files = {"file": ("audio.pcm", pcm_data, "audio/x-pcm")}
            response = post_audio(files)

        toggle_gif_doctor(False)  # 隐藏 doctor.gif

        if response is not None and response.status_code == 200:
            append_chat_result(response)

        else:
            show_request_error(response, "上传失败")
    toggle_gif_doctor(True)  # 显示 doctor.gif


# 处理上传的语音文件
if uploaded_file is not None:
    st.sidebar.audio(uploaded_file, format='audio/wav')

    with st.spinner('处理中，请稍等...'):
        # 上传文件到 FastAPI 后端并自动处理
        response = post_audio({"file": uploaded_file})

    if response is not None and response.status_code == 200:
        append_chat_result(response)

    else:
        show_request_error(response, "上传失败")
