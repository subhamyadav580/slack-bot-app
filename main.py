import slack
import os
import requests
from collections import deque
from fastapi import FastAPI, Request, BackgroundTasks
from starlette.responses import JSONResponse
from dotenv import load_dotenv
load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_TOKEN")
SIGNING_SECRET = os.getenv("SIGNING_SECRET")
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "smollm:135m"


app = FastAPI()
client = slack.WebClient(token=SLACK_TOKEN)

message_history = deque(maxlen=5) # Store last 5 (user_query, llm_response) pairs
processed_events = set() # Track processed events to prevent duplicates

def is_duplicate_event(event_key: str) -> bool:
    """
    Check if an event has already been processed to avoid duplicates.
    """
    if event_key in processed_events:
        return True
    processed_events.add(event_key)
    return False

async def get_ollama_response(messages: list, current_query: str) -> str:
    """
    Send messages to Ollama API and return a response.
    """
    try:
        base_prompt = "You are a helpful Slack AI assistant. Keep responses short and relevant.\n"
        # Include conversation history only if available
        if messages:
            history_context = "\n".join([f"User: {q}\nAssistant: {r}" for q, r in messages])
            prompt = f"{base_prompt}\n{history_context}\nUser: {current_query}\nAssistant:"
        else:
            # If no previous conversation
            prompt = f"{base_prompt}\nUser: {current_query}\nAssistant:"

        payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}
        response = requests.post(OLLAMA_API_URL, json=payload)
        llm_response = response.json().get("response", "No response from AI.") # Extract response text
        message_history.append((current_query, llm_response)) # Store query-response pair in history
        return llm_response

    except Exception as e:
        return f"Error: {str(e)}"

async def process_slack_event(event: dict):
    """
    Processes Slack message event and responds with Ollama output.
    """
    user_id = event.get("user")
    text = event.get("text", "").strip()
    channel = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")
    bot_user_id = client.auth_test().get("user_id", "") # Get bot user ID
    # Check if bot was mentioned
    if f"<@{bot_user_id}>" in text:
        text = text.replace(f"<@{bot_user_id}>", "").strip()
        response = await get_ollama_response(list(message_history), text)

        # Send response in the same thread
        client.chat_postMessage(channel=channel, text=response, thread_ts=thread_ts)

@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Handles incoming Slack events and prevents duplicate processing.
    """
    payload = await request.json()
    # Handle Slack verification challenge
    if "challenge" in payload:
        return JSONResponse(content={"challenge": payload["challenge"]})

    event = payload.get("event", {})
    ts = event.get("ts")
    team_id = payload.get("authorizations", [{}])[0].get("team_id")
    user_id = event.get("user")
    # Create a unique event key
    event_key = f"{team_id}:{user_id}:{ts}"
    # Avoid duplicate processing
    if ts and team_id and user_id and is_duplicate_event(event_key):
        return JSONResponse(content={"status": "duplicate"}, status_code=200)
    # Process only new user messages
    if event.get("type") == "message" and "subtype" not in event:
        background_tasks.add_task(process_slack_event, event)
    return JSONResponse(content={"status": "ok"}, status_code=200)
