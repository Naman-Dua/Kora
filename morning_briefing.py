import os
import datetime
from weather import handle_weather_command
from news_feed import handle_news_command
from storage import load_scheduled_items
from brain import KoraBrain

def generate_morning_briefing():
    """Generates a high-value summary of the user's day."""
    
    # 1. Weather
    weather = handle_weather_command("weather")
    weather_text = weather.get("reply", "Weather data unavailable.")

    # 2. News
    news = handle_news_command("latest news")
    news_text = news.get("reply", "News data unavailable.")

    # 3. Schedule
    items = load_scheduled_items()
    today_str = datetime.date.today().isoformat()
    todays_tasks = [i for i in items if i.get("due_at", "").startswith(today_str)]
    
    schedule_text = "No meetings scheduled for today."
    if todays_tasks:
        schedule_text = "Your schedule for today: " + "; ".join([f"{t['task']} at {t['due_at']}" for t in todays_tasks])

    # 4. Todo List (from notes.txt)
    todo_text = "Your todo list is empty."
    if os.path.exists("notes.txt"):
        with open("notes.txt", "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            if lines:
                todo_text = "Pending todos: " + ", ".join(lines[:5])

    # 5. Synthesize with LLM
    brain = KoraBrain()
    prompt = (
        "You are Kora giving a professional morning briefing. "
        "Synthesize the following info into a concise, upbeat 3-sentence summary. "
        f"Weather: {weather_text} | News: {news_text} | Schedule: {schedule_text} | Todos: {todo_text}"
    )
    
    briefing = brain.generate_reply(prompt)
    if isinstance(briefing, dict):
        briefing = briefing["text"]
        
    return {
        "action": "morning_briefing",
        "reply": briefing
    }

def is_briefing_request(query):
    q = query.lower()
    return "morning briefing" in q or "start my day" in q or "daily report" in q
