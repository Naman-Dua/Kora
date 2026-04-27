# 💠 Kora: The Autonomous AI Assistant

Kora (Jarvis 2.0) is a next-generation, local-first AI assistant designed for Windows. She combines a stunning 3D glassmorphic dashboard with autonomous agency, self-healing capabilities, and a proactive vision system.

---

## 🌟 Core Features

### 🧠 1. Neural Intelligence (Local LLM)

- **Brain**: Powered by **Llama 3.1:8b** via Ollama. 100% private and offline.
- **Emotional Synchrony**: The 3D dashboard reacts to the conversation's sentiment (Calm Blue, Energetic Orange, Warning Red, Positive Pink).
- **Fact Extraction**: Kora autonomously "overhears" and remembers facts about you (names, likes, goals) without manual input.

### 👁️ 2. Live Eye (Proactive Vision)

- **Model**: Uses **Moondream** to analyze your screen.
- **Proactivity**: She monitors your screen for errors, interesting news, or stalled tasks and proactively offers help or summaries.

### 📅 3. Digital Life Manager

- **Autonomous Scheduling**: Mention an appointment in chat, and she will automatically queue a reminder.
- **Morning Briefing**: A single command (`"Start my day"`) generates a synthesized report of weather, news, todos, and your schedule.

### 🛠️ 4. The Plugin Architect (Self-Evolution)

- **Autonomous Coding**: Tell Kora to "create a plugin for X," and she will write the Python code, save it, and register the new skill instantly.
- **Full OS Control**: Native modules for File management, Window control, Media (Spotify/Volume), and Clipboard.

### 📱 5. Telegram / Mobile Bridge

- **Remote Control**: Control your PC from anywhere in the world via Telegram.
- **Remote Vision**: Ask for a screenshot on your phone to see what's happening on your desktop.

---

## 🚀 Setup & Installation

### 1. Prerequisites

Download and install the following:

- **Python 3.10+**
- **Ollama**: [Download from ollama.com](https://ollama.com)

### 2. Download Models

Run these commands in your terminal to pull the necessary intelligence:

```bash
ollama pull llama3.1:8b   # Core Brain
ollama pull moondream     # Vision System
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configuration

Edit `settings.json` (or use voice commands) to configure:

- `telegram_token`: Your BotFather token for mobile control.
- `telegram_chat_id`: Your personal Telegram ID for security.

---

## 🎙️ Command Guide

| Category      | Voice/Text Command Examples                                            |
| :------------ | :--------------------------------------------------------------------- |
| **System**    | "Shutdown", "Go to sleep", "Recalibrate mic"                           |
| **Daily**     | "Give me my morning briefing", "What's on my schedule?"                |
| **Action**    | "Open Chrome", "Close Notepad", "Search for 'Deep Learning'"           |
| **Memory**    | "Forget everything", "What do you know about me?"                      |
| **Evolution** | "Create a plugin for crypto prices", "Build a skill for science facts" |
| **Remote**    | (Via Telegram) "Take a screenshot", "Is my PC running?"                |

---

## 🛡️ Self-Healing

If a command fails (e.g., an app isn't where it used to be), Kora's **Self-Healing Module** will analyze the error, search for the correct path, and offer a fix automatically.

---

## 🎨 UI Aesthetics

The dashboard uses hardware-accelerated 3D rendering (PyQt6 + OpenGL) to create a premium, glassmorphic sphere that vibrates and ripples in sync with Kora's voice.

**Developed with ❤️ by Naman Dua**
