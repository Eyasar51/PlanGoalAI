import os
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv
import uuid

load_dotenv()

app = Flask(__name__)

# Store conversations in memory (in production, use a database)
conversations = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        goal = request.form.get('goal')
        deadline = request.form.get('deadline')
        free_time = float(request.form.get('free_time', 0))
        
        # Calculate days remaining
        deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
        current_date = date.today()
        days_remaining = (deadline_date - current_date).days
        
        # Get current date and time for context
        current_datetime = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        
        # Create detailed prompt
        prompt = f"""
        Today is {current_datetime}.
        
        I need help creating a personalized goal achievement strategy with the following details:
        - Goal: {goal}
        - Deadline: {deadline}
        - Days remaining: {days_remaining}
        - Daily available time: {free_time} hours
        
        Please create a comprehensive strategy that includes:
        1. **Timeline & Milestones**: Break down the goal into weekly milestones
        2. **Daily Actions**: Specific daily tasks that fit within {free_time} hours
        3. **Potential Obstacles**: Common challenges and how to overcome them
        4. **Resources Needed**: Tools, materials, or support required
        5. **Progress Tracking**: How to measure success along the way
        
        Consider the current date ({current_datetime}) and the time constraint of {days_remaining} days.
        Format your response with clear headings and bullet points for easy reading.
        """
        
        try:
            strategy = call_openrouter_api(prompt)
            return render_template('index.html', goal=goal, deadline=deadline, 
                                 free_time=free_time, strategy=strategy)
        except Exception as e:
            error_message = f"Error generating strategy: {str(e)}"
            return render_template('index.html', error=error_message)
    
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message')
    session_id = data.get('session_id')
    strategy_context = data.get('strategy_context', '')
    goal = data.get('goal', '')
    deadline = data.get('deadline', '')
    free_time = data.get('free_time', '')
    
    if session_id not in conversations:
        conversations[session_id] = []
    
    # Add current date/time context to the conversation
    current_datetime = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    
    # Add user message to conversation
    conversations[session_id].append({
        "role": "user", 
        "content": f"[Current time: {current_datetime}] {message}"
    })
    
    try:
        # Get AI response with strategy context
        response = call_openrouter_api_chat(conversations[session_id], strategy_context, goal, deadline, free_time)
        
        # Add assistant response to conversation
        conversations[session_id].append({
            "role": "assistant", 
            "content": response
        })
        
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": f"Error: {str(e)}"}), 500

def call_openrouter_api(prompt):
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise Exception("OpenRouter API key not found. Please set OPENROUTER_API_KEY in your environment variables.")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://replit.com",
        "X-Title": "Goal Planner Assistant"
    }
    
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful goal planning assistant. Always consider the current date and time context provided. Provide detailed, actionable advice formatted with clear headings and bullet points."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            raise Exception("Invalid API key. Please check your OPENROUTER_API_KEY.")
        else:
            raise Exception(f"API request failed: {response.status_code} - {response.text}")
    except Exception as e:
        raise Exception(f"Request failed: {str(e)}")

def call_openrouter_api_chat(messages, strategy_context="", goal="", deadline="", free_time=""):
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise Exception("OpenRouter API key not found. Please set OPENROUTER_API_KEY in your environment variables.")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://replit.com",
        "X-Title": "Goal Planner Assistant"
    }
    
    # Build context-aware system message
    context_info = ""
    if strategy_context:
        context_info = f"\n\nUser's Current Goal Information:\n- Goal: {goal}\n- Deadline: {deadline}\n- Daily available time: {free_time} hours\n\nGenerated Strategy:\n{strategy_context}\n\nWhen answering questions, reference this strategy and goal information to provide personalized, relevant advice."
    
    # Add system message with current time awareness and strategy context
    system_message = {
        "role": "system",
        "content": f"You are a helpful goal planning assistant. Always be aware of the current date and time context provided in user messages. Provide practical, time-aware advice. Current session time: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}{context_info}"
    }
    
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [system_message] + messages
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            raise Exception("Invalid API key. Please check your OPENROUTER_API_KEY.")
        else:
            raise Exception(f"API request failed: {response.status_code} - {response.text}")
    except Exception as e:
        raise Exception(f"Request failed: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
