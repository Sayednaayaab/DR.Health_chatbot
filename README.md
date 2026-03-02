# 🩺⚡ Dr. HealthBot  
## AI Medical Assistant with Intelligent Triage, Emergency Detection & Cyberpunk UI  

<p align="center">
  <img src="https://img.shields.io/badge/AI-Powered-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Backend-Flask-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/LLM-Integrated-purple?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Database-SQLite-lightgrey?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Status-Production--Ready-brightgreen?style=for-the-badge" />
</p>

---

## 🚀 Overview

**Dr. HealthBot** is a production-ready AI-powered medical assistant that simulates structured clinical reasoning, performs intelligent symptom triage, detects emergencies, and maintains persistent multi-session conversations — all inside a futuristic cyberpunk interface.

This is not just a chatbot.  
It’s a mini AI-powered clinical consultation system.

---

## 🌟 Why This Project Stands Out

- 🧠 Structured medical reasoning engine  
- 🚨 Real-time emergency detection system  
- 📊 Priority-based symptom triage logic  
- 🔐 Secure authentication (Manual + Google OAuth)  
- 💾 Persistent multi-session conversations  
- 🎛 Customizable AI persona  
- 🎨 Neon cyberpunk glassmorphism UI  

---

## 🧠 Core Features

### 1️⃣ Structured Medical Response Engine

Powered by:

```
Qwen/Qwen2.5-VL-7B-Instruct (via HuggingFace Router)
```

Each AI response includes:

- Severity Assessment  
- Differential Diagnosis  
- Immediate Management  
- Pharmacotherapy (India-specific)  
- Preventive Measures  
- Red Flags – Seek Urgent Care  

Low temperature (0.25) ensures consistent clinical tone.

---

### 2️⃣ Intelligent Follow-Up System

Symptom priority logic:

```
Chest Pain > Fever > Cough > Headache > Stomach Pain > Cold
```

- Tracks follow-up states  
- Avoids repetitive questioning  
- Provides structured multiple-choice responses  
- Uses context-aware system prompts  

---

### 3️⃣ 🚨 Emergency Detection Layer

Automatically detects high-risk keywords:

- Chest pain  
- Stroke indicators  
- Difficulty breathing  
- Severe bleeding  
- Loss of consciousness  

Triggers urgent care recommendation instantly.

---

### 4️⃣ Authentication & Security

- Email/Password login (Werkzeug hashing)  
- Google OAuth (Authlib)  
- Flask-Login session protection  
- Environment-based secret configuration  
- Secure database persistence  

---

## 🏗 Tech Stack

### Backend
- Flask 2.3.3  
- SQLAlchemy  
- SQLite  
- Flask-Login  
- Authlib  
- OpenAI SDK  
- HuggingFace Router  
- python-dotenv  

### Frontend
- Custom Cyberpunk Glassmorphism UI  
- Orbitron + Roboto fonts  
- Vanilla JavaScript  
- Dark/Light Mode  
- Card-based structured responses  
- Animated transitions  

---

## 📂 Project Structure

```bash
chatbot/
├── app.py
├── auth.py
├── models.py
├── requirements.txt
├── instance/
│   └── chatbot.db
├── static/
│   ├── css/styles.css
│   └── js/chat.js
└── templates/
    ├── index.html
    ├── login.html
    ├── register.html
    └── settings.html
```

---

## 🗃 Database Schema

### User
- id  
- name  
- email (unique)  
- password_hash  
- custom_prompt  

### Conversation
- id  
- user_id (FK)  
- title  
- created_at  
- updated_at  

### Message
- id  
- conversation_id (FK)  
- role (user/assistant)  
- content  
- created_at  

---

## ⚙ Environment Configuration

Create a `.env` file:

```env
SECRET_KEY=your_secret_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
HUGGINGFACE_API_KEY=your_api_key

MODEL=Qwen/Qwen2.5-VL-7B-Instruct:hyperbolic
TEMPERATURE=0.25
MAX_TOKENS=300
```

---

## 🛠 Installation

```bash
git clone https://github.com/yourusername/dr-healthbot.git
cd dr-healthbot

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
flask run
```

---

## 🔥 Advanced Architecture Highlights

- Context-aware dynamic system prompts  
- Follow-up state dictionary tracking  
- Multi-conversation persistence  
- Modular Flask blueprints  
- Clean ORM relationships  
- Emergency-priority override logic  

---

## 📈 Future Enhancements

- Voice input (Speech-to-Text)  
- Conversation export (PDF/JSON)  
- Multi-language support  
- Analytics dashboard  
- HIPAA-compliant architecture  
- Medication database integration  
- Appointment booking system  

---

## ⚠ Medical Disclaimer

Dr. HealthBot is an AI-powered assistant and does not replace professional medical advice.  
In case of emergency, contact local emergency services immediately.

---

## ⭐ Support the Project

If you find this project useful:

- Star ⭐ the repository  
- Fork 🍴 it  
- Open Issues 🐛  
- Submit Pull Requests 🚀  

---

## 🩺 “AI Meets Clinical Logic.”

Dr. HealthBot — Structured. Intelligent. Always Available.
