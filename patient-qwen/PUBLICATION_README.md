# 旧工程发布副本

本目录来源于原 `patient-qwen`，保留本地 Qwen 后端、Streamlit 前端、提示词、依赖清单及原 UI 图片。原 README 中的模型路径和启动说明属于旧工程配置；本次没有加载旧 8B 模型，也没有验证完整服务运行。

上传整理仅做以下处理：

- `backend/iat_ws_python3.py` 的硬编码 APPID/APIKey/APISecret 改为读取 `XFYUN_APP_ID`、`XFYUN_API_KEY`、`XFYUN_API_SECRET`，没有设置时为空字符串。
- `backend/.env.example` 中的凭据字段清空。这是示例文件；当前云 ASR 脚本读取进程环境变量，未增加 `.env` 自动加载。
- 排除历史 WAV/PCM/MP3、IDE/类型检查/Python 缓存，以及原有 Linux FFmpeg 二进制目录。

若使用旧云 ASR，在启动前自行设置上述环境变量。服务仍会访问云端；旧脚本的 TLS 设置、全局状态和上传边界问题未在本次发布中改造，详细盘点见 [旧工程业务盘点](../workspaces/C/quality/audit/旧工程业务盘点.md)。新的离线语音候选在 `workspaces/C/voice_C`，旧应用没有自动切换到它。

历史 FFmpeg 路径仍指向原 Linux 目录；需要实际部署时单独配置相应环境。这份源码整理不是旧应用部署验收。原凭据建议由持有人作废并重新生成；本次没有调用、验证或轮换这些凭据。
