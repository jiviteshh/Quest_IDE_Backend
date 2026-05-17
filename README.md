# QuestIDE Backend ⚙️

Backend infrastructure powering QuestIDE — an AI-native coding workspace.

Handles:

* AI problem parsing
* testcase generation
* code execution orchestration
* verdict evaluation
* hidden testcase execution
* AI assistant workflows

---

## ✨ Features

* ⚡ FastAPI backend architecture
* 🧠 AI-powered problem parsing
* 🧪 Public + Hidden testcase support
* 💻 Multi-language execution pipeline
* 📊 Verdict evaluation engine
* 🛠 Custom input execution
* 🤖 NVIDIA AI integration
* 🔗 Piston execution engine integration

---

## 🏗 Tech Stack

* FastAPI
* Python
* NVIDIA NIM APIs
* Qwen3 Coder 480B
* Docker
* Piston Execution Engine

---

## ⚙️ Environment Setup

Create `.env`

```env id="bk1"
# NVIDIA API Key
# Generate from:
# https://build.nvidia.com/settings/api-keys

NVIDIA_API_KEY=your_api_key_here

NVIDIA_API_BASE_URL=https://integrate.api.nvidia.com/v1

NVIDIA_MODEL=qwen/qwen3-coder-480b-a35b-instruct

NVIDIA_TEMPERATURE=0
NVIDIA_TOP_P=1
NVIDIA_MAX_TOKENS=2048

LLM_TIMEOUT_SECONDS=30

# Local piston endpoint
PISTON_URL=http://localhost:2000
```

---

## 🚀 Run Locally

Create virtual environment:

```bash id="bk2"
python -m venv venv
```

Activate environment:

### Windows

```bash id="bk3"
venv\Scripts\activate
```

Install dependencies:

```bash id="bk4"
pip install -r requirements.txt
```

Run backend:

```bash id="bk5"
uvicorn app.main:app --reload
```

---

## 🔗 Related Repositories

Frontend:
[QuestIDE Frontend](https://github.com/jiviteshh/Quest_IDE_Frontend?utm_source=chatgpt.com)

Piston Infrastructure:
[QuestIDE Piston Infrastructure](https://github.com/jiviteshh/questide-piston?utm_source=chatgpt.com)

---

## 🐳 Piston Infrastructure

QuestIDE uses Piston for secure multi-language code execution.

Infrastructure Repository:
[QuestIDE Piston Infrastructure](https://github.com/jiviteshh/questide-piston?utm_source=chatgpt.com)

---

## 👨‍💻 Developed By

Jivitesh Naragam

LinkedIn:
[Naragam Jivitesh LinkedIn](https://www.linkedin.com/in/naragam-jivitesh-71a4b8313/?utm_source=chatgpt.com)

Feedback:
[jivinaragam@gmail.com](mailto:jivinaragam@gmail.com)

---

## © Copyright

© 2026 QuestIDE. All rights reserved.

Unauthorized copying, redistribution, or commercial usage without permission is prohibited.
