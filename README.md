# QuestIDE Backend ⚙️

Backend infrastructure powering QuestIDE — an AI-native coding workspace for intelligent coding interviews, execution workflows, and AI-assisted problem solving.

The backend orchestrates:

* AI parsing
* testcase generation
* execution pipelines
* verdict evaluation
* hidden testcase validation
* contextual AI workflows
* multi-language execution handling

---

# ✨ Core Features

* ⚡ FastAPI-based backend architecture
* 🧠 AI-powered problem parsing engine
* 🧪 Public + hidden testcase orchestration
* 💻 Multi-language execution pipeline
* 📊 Submission verdict evaluation
* 🛠 Custom input execution system
* 🤖 NVIDIA NIM API integration
* 🔄 Structured testcase serialization
* 🔗 Piston execution engine integration
* 📦 Modular backend architecture

---

# 🧠 Backend Responsibilities

QuestIDE backend handles:

* transforming natural-language prompts into structured coding problems
* execution orchestration
* testcase lifecycle management
* AI response generation
* verdict generation
* runtime/error handling
* execution metadata processing

---

# 🏗️ System Architecture

```txt id="bkx1"
Frontend (Next.js + Monaco)
            ↓
Backend (FastAPI)
            ↓
Piston Execution Engine
            ↓
Multi-language Runtime Execution
```

---

# 🛠️ Tech Stack

## Backend Framework

* FastAPI
* Python

## AI Infrastructure

* NVIDIA NIM APIs
* Qwen3 Coder 480B

## Execution Infrastructure

* Piston Execution Engine
* Docker

## APIs & Utilities

* HTTPX
* Pydantic
* Async execution pipelines

---

# ⚙️ Environment Setup

Create:

```txt id="bkx2"
.env
```

Add:

```env id="bkx3"
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

# Piston execution engine
PISTON_URL=http://localhost:2000
```

---

# 🚀 Local Development

## Create virtual environment

```bash id="bkx4"
python -m venv venv
```

## Activate environment

### Windows

```bash id="bkx5"
venv\Scripts\activate
```

---

## Install dependencies

```bash id="bkx6"
pip install -r requirements.txt
```

---

## Start backend server

```bash id="bkx7"
uvicorn app.main:app --reload
```

Backend runs at:

```txt id="bkx8"
http://localhost:8000
```

---

# 🧪 Execution Workflow

## Run Code

Used for:

* visible testcase execution
* debugging
* rapid iteration

---

## Submit Solution

Used for:

* hidden testcase validation
* final verdict evaluation
* acceptance/rejection workflow

---

# 🤖 AI Parsing Pipeline

The AI parsing engine converts raw coding prompts into:

* structured statements
* constraints
* difficulty metadata
* execution templates
* public testcases
* hidden testcases
* language starter templates

---

# 🔗 Related Repositories

Frontend Workspace:
[QuestIDE Frontend Repository](https://github.com/jiviteshh/Quest_IDE_Frontend?utm_source=chatgpt.com)

Piston Infrastructure:
[QuestIDE Piston Infrastructure](https://github.com/jiviteshh/questide-piston?utm_source=chatgpt.com)

---

# 🐳 Piston Infrastructure

QuestIDE uses Piston for:

* secure runtime orchestration
* multi-language execution
* sandboxed compilation/execution workflows

Infrastructure Repository:
[QuestIDE Piston Infrastructure](https://github.com/jiviteshh/questide-piston?utm_source=chatgpt.com)

---

# 📸 Recommended Demonstrations

Add:

* execution flow screenshots
* parser outputs
* hidden testcase validation
* accepted submission screenshots
* API examples
* architecture diagrams

---

# 👨‍💻 Developed By

Jivitesh Naragam

LinkedIn:
[Naragam Jivitesh LinkedIn](https://www.linkedin.com/in/naragam-jivitesh-71a4b8313/?utm_source=chatgpt.com)

Feedback & Contact:
[jivinaragam@gmail.com](mailto:jivinaragam@gmail.com)

---

# 📄 License & Copyright

© 2026 QuestIDE. All rights reserved.

This backend infrastructure and associated execution orchestration logic are protected under copyright law.

Unauthorized redistribution, commercial reuse, or replication of substantial portions of this project without explicit permission is prohibited.

QuestIDE is an independently developed AI-native coding platform project.
