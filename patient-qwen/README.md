# patient-qwen

这是基于 `/data1/szeyu/patient_project_1029` 复制出的本地 Qwen 版本。

## 运行

如果当前环境缺少依赖，先补齐:

```bash
python -m pip install -r backend/requirements.txt
python -m pip install -r frontend/requirements.txt
```

```bash
cd /data1/szeyu/patient-qwen
python run.py
```

后端默认使用:

```text
/data1/szeyu/.cache/Qwen/Qwen3-VL-8B-Instruct-FP8
```

如需临时切换模型路径:

```bash
QWEN_MODEL_PATH=/path/to/model python run.py
```

## 单独启动

后端:

```bash
cd /data1/szeyu/patient-qwen/backend
python -m uvicorn backend_api:app
```

前端:

```bash
cd /data1/szeyu/patient-qwen/frontend
python -m streamlit run frontend.py --server.port=8501
```

## 说明

- DeepSeek API 已替换为本地 Hugging Face Transformers 推理。
- 默认不使用 `uvicorn --reload`，避免本地 8B 模型重复加载。
- 首次启动会读取 `backend/prompt.txt` 并生成第一轮回答，模型加载和首次生成会比较慢。
- 可以通过环境变量调整生成参数: `QWEN_MAX_NEW_TOKENS`、`QWEN_TEMPERATURE`、`QWEN_TOP_P`。
