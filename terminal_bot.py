from flask import Flask, request, Response, jsonify
from twilio.rest import Client
import requests as http_requests
import time
import threading
import json
import os
import re
import random
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape

account_sid = 'AC2cab426b2d3b5a4ed62fca2b00d247e7'
auth_token = 'f4b535264f814365cc8a4901b824fd65'
twilio_number = '+18168193359'

client = Client(account_sid, auth_token)

sarvam_api_url = 'https://api.sarvam.ai/v1/chat/completions'
sarvam_api_key = 'sk_fqjol2xn_WN7Yf3yerwcfcHCbYV7Hte85'
sarvam_model = 'sarvam-105b-conversations'

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=5)

state = {
    "conversation_memory": [],
    "system_prompt": "",
    "current_call_number": "",
    "call_message": "",
    "user_name": "",
    "silence_count": 0,
    "conversation_started": False,
    "sentiment_score": 0,
    "response_count": 0,
    "call_status": "idle",
    "call_sid": "",
    "call_start_time": None,
}
state_lock = threading.Lock()

data_file = "call_data.json"

COLOR = {
    "reset": "\033[0m", "dim": "\033[2m", "bold": "\033[1m",
    "cyan": "\033[36m", "green": "\033[32m", "yellow": "\033[33m",
    "red": "\033[31m", "blue": "\033[34m", "magenta": "\033[35m",
}

def c(text, color):
    return f"{COLOR.get(color,'')}{text}{COLOR['reset']}"

def print_event(event_type, data):
    t = time.strftime("%H:%M:%S")
    prefix = c(f"[{t}]", "dim")
    if event_type == "call_initiated":
        print(f"{prefix} {c('CALL INITIATED','cyan')} -> {data.get('number')} (sid={data.get('sid')})")
    elif event_type == "call_answered":
        print(f"{prefix} {c('CALL ANSWERED','green')} -> {data.get('number')}")
    elif event_type == "user_speech":
        print(f"{prefix} {c('USER','blue')} ({data.get('name')}): {data.get('text')}")
        print(f"{prefix}   {c('intent','dim')}={data.get('intent')} {c('emotion','dim')}={data.get('emotion')} "
              f"{c('sentiment','dim')}={data.get('sentiment')} {c('confidence','dim')}={data.get('confidence')}")
    elif event_type == "bot_response":
        print(f"{prefix} {c('BOT','magenta')} (#{data.get('count')}): {data.get('text')}")
    elif event_type == "silence":
        print(f"{prefix} {c('SILENCE','yellow')} count={data.get('count')}")
    elif event_type == "name_detected":
        print(f"{prefix} {c('NAME DETECTED','green')}: {data.get('name')}")
    elif event_type == "call_ended":
        print(f"{prefix} {c('CALL ENDED','red')} reason={data.get('reason')} "
              f"sentiment={data.get('sentiment')} duration={data.get('duration')}")
    elif event_type == "recording_saved":
        print(f"{prefix} {c('RECORDING SAVED','green')}: {data.get('filename')}")
    elif event_type == "error":
        print(f"{prefix} {c('ERROR','red')}: {data.get('message')}")
    else:
        print(f"{prefix} {event_type}: {data}")

def get_sarvam_session():
    s = http_requests.Session()
    s.headers.update({
        'api-subscription-key': sarvam_api_key,
        'Content-Type': 'application/json',
    })
    return s

sarvam_session = None

def _sarvam():
    global sarvam_session
    if sarvam_session is None:
        sarvam_session = get_sarvam_session()
    return sarvam_session

FILLER_WORDS = {
    'positive': ['Great!', 'Perfect!', 'Awesome!', 'I see,', 'Got it,', 'Absolutely,', 'That makes sense,'],
    'negative': ['I understand,', 'I hear you,', 'No worries,', 'That is okay,', 'Fair enough,'],
    'question': ['Good question!', 'Let me think,', 'Well,', 'Hmm,', 'You know,'],
    'neutral':  ['Okay,', 'Alright,', 'Sure,', 'Right,'],
}
ACKNOWLEDGMENTS = ['Mm-hmm,', 'I see,', 'Got it,', 'Okay,', 'Right,', 'Yeah,']

def xml_safe(text):
    if not text:
        return ""
    text = escape(str(text))
    text = re.sub(r'[^\x20-\x7E\s]', '', text)
    return text.strip()

def detect_intent(text):
    if not text:
        return 'neutral'
    t = text.lower()
    if any(x in t for x in ['bye', 'goodbye', 'hang up', 'not interested', 'stop calling', 'dont call']):
        return 'exit'
    if any(x in t for x in ['yes', 'yeah', 'sure', 'okay', 'sounds good', 'interested', 'tell me more', 'go ahead', 'absolutely']):
        return 'positive'
    if any(x in t for x in ['no', 'nope', 'not now', 'busy', 'later', 'maybe', 'not sure']):
        return 'negative'
    if any(x in t for x in ['what', 'huh', 'pardon', 'sorry', 'repeat', 'didnt catch', 'understand']):
        return 'confused'
    if any(x in t for x in ['how', 'when', 'where', 'why', 'who', 'which', 'can you', 'could you', 'would you']):
        return 'question'
    if any(x in t for x in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
        return 'greeting'
    return 'neutral'

def detect_emotion(text):
    if not text:
        return 'neutral'
    t = text.lower()
    if any(x in t for x in ['frustrated', 'annoyed', 'angry', 'upset']):
        return 'frustrated'
    if any(x in t for x in ['excited', 'great', 'amazing', 'wonderful', 'love']):
        return 'excited'
    if any(x in t for x in ['worried', 'concerned', 'nervous', 'scared']):
        return 'worried'
    if any(x in t for x in ['happy', 'glad', 'pleased', 'satisfied']):
        return 'happy'
    return 'neutral'

def extract_name(text):
    if not text or len(text) < 5:
        return None
    patterns = [
        r"(?:my name is|im|i am|this is|call me)\s+([a-zA-Z]+)",
        r"^([a-zA-Z]+)\s+(?:here|speaking)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            name = m.group(1).capitalize()
            if name.lower() not in ['yes', 'no', 'okay', 'sure', 'hello', 'hi', 'this', 'here']:
                return name
    return None

def update_sentiment(intent):
    delta = {'positive': 2, 'negative': -2, 'exit': -3, 'question': 1, 'greeting': 1}
    with state_lock:
        state["sentiment_score"] += delta.get(intent, 0)
        state["sentiment_score"] = max(-10, min(10, state["sentiment_score"]))
    return state["sentiment_score"]

def add_human_touch(response, intent, emotion):
    if len(response) < 20:
        return response
    if random.random() < 0.5 and intent in FILLER_WORDS:
        response = f"{random.choice(FILLER_WORDS[intent])} {response}"
    elif random.random() < 0.3 and state["response_count"] > 1:
        response = f"{random.choice(ACKNOWLEDGMENTS)} {response}"
    return response

def calculate_pause(text, intent):
    p = 0.5
    if '?' in text:      p = 0.8
    if intent == 'negative': p = 0.7
    if any(w in text.lower() for w in ['okay', 'sure', 'right', 'yeah']): p = 0.3
    return min(1.5, p)

def save_conversation_async():
    phone     = state["current_call_number"]
    prompt    = state["system_prompt"]
    memory    = state["conversation_memory"][:]
    sentiment = state["sentiment_score"]
    name      = state["user_name"]
    def _save():
        try:
            record = {
                "phone_number": phone,
                "user_name": name or "Unknown",
                "system_prompt": prompt,
                "conversation": memory,
                "sentiment_score": sentiment,
                "total_exchanges": len(memory) // 2,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            data = []
            if os.path.exists(data_file):
                with open(data_file, 'r') as f:
                    data = json.load(f)
            data.append(record)
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(c(f"[SAVED] {name or phone} | sentiment={sentiment}", "dim"))
        except Exception as e:
            print(c(f"[SAVE ERROR] {e}", "red"))
    executor.submit(_save)

def get_sarvam_response(user_message, intent, emotion):
    if not user_message or not user_message.strip():
        return random.choice(["Sorry, could you say that again?",
                              "I did not catch that. Could you repeat?"])
    try:
        with state_lock:
            state["conversation_memory"].append({"role": "user", "content": user_message})

        enhanced = state["system_prompt"]
        if emotion == 'frustrated': enhanced += "\n\nUSER SEEMS FRUSTRATED. Be extra empathetic."
        elif emotion == 'excited':  enhanced += "\n\nUSER SEEMS EXCITED. Match their enthusiasm!"
        elif emotion == 'worried':  enhanced += "\n\nUSER SEEMS WORRIED. Be reassuring."
        if intent == 'confused':    enhanced += "\n\nUSER IS CONFUSED. Explain clearly."
        elif intent == 'question':  enhanced += "\n\nUSER ASKED A QUESTION. Answer directly first."
        elif intent == 'negative':  enhanced += "\n\nUSER SEEMS HESITANT. Be understanding, don't push."
        elif intent == 'positive':  enhanced += "\n\nUSER IS ENGAGED. Build momentum!"
        if state["user_name"]:      enhanced += f"\n\nUSER NAME: {state['user_name']}. Use naturally."

        messages = [{"role": "system", "content": enhanced}] + state["conversation_memory"][-6:]
        payload = {
            "model": sarvam_model,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 100,
            "top_p": 0.9,
            "stream": False,
        }

        resp = _sarvam().post(sarvam_api_url, json=payload, timeout=8)
        if resp.status_code == 200:
            reply = resp.json()['choices'][0]['message']['content'].strip()
            reply = re.sub(r'\*\*?([^*]+)\*\*?', r'\1', reply)
            reply = reply.replace('[', '').replace(']', '').strip()
            if reply and reply[-1] not in '.!?':
                reply += '.'
            reply = add_human_touch(reply, intent, emotion)
            with state_lock:
                state["conversation_memory"].append({"role": "assistant", "content": reply})
                state["response_count"] += 1
            return reply
        else:
            print(c(f"[SARVAM ERROR] status={resp.status_code} body={resp.text[:200]}", "red"))
            return "Could you say that again? I want to make sure I understand."
    except http_requests.Timeout:
        print(c("[SARVAM TIMEOUT]", "red"))
        return "Sorry, could you repeat that?"
    except Exception as e:
        print(c(f"[SARVAM EXCEPTION] {e}", "red"))
        return "I did not catch that. Could you say it again?"

@app.route("/voice", methods=['GET', 'POST'])
def voice():
    try:
        user_input = (request.values.get('SpeechResult') or '').strip()
        confidence = request.values.get('Confidence', '0')

        if not state["conversation_started"]:
            with state_lock:
                state["conversation_started"] = True
                state["call_status"] = "connected"
            print_event("call_answered", {"number": state["current_call_number"]})
            msg = xml_safe(state["call_message"]) or "Hello! How can I help you today?"
            return Response(f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" timeout="4" speechTimeout="2" actionOnEmptyResult="true"
          bargeIn="true" profanityFilter="false" action="/voice" method="POST">
    <Say voice="Polly.Joanna" language="en-US">{msg}</Say>
  </Gather>
  <Redirect>/handle_silence</Redirect>
</Response>''', mimetype="text/xml")

        if not user_input:
            return Response('''<?xml version="1.0" encoding="UTF-8"?>
<Response><Redirect>/handle_silence</Redirect></Response>''', mimetype="text/xml")

        intent  = detect_intent(user_input)
        emotion = detect_emotion(user_input)

        update_sentiment(intent)
        with state_lock:
            state["silence_count"] = 0

        if not state["user_name"]:
            name = extract_name(user_input)
            if name:
                with state_lock:
                    state["user_name"] = name
                print_event("name_detected", {"name": name})

        print_event("user_speech", {
            "text":       user_input,
            "intent":     intent,
            "emotion":    emotion,
            "confidence": confidence,
            "sentiment":  state["sentiment_score"],
            "exchanges":  len(state["conversation_memory"]) // 2,
            "silences":   state["silence_count"],
            "name":       state["user_name"] or "Unknown",
        })

        if intent == 'exit':
            save_conversation_async()
            s = state["sentiment_score"]
            n = state["user_name"]
            if s > 5:  fare = f"It was great talking with you{', '+n if n else ''}! Have an amazing day. Bye!"
            elif s < -3: fare = f"I understand{', '+n if n else ''}. Sorry to bother you. Take care!"
            else:        fare = f"Thanks for your time{', '+n if n else ''}. Have a good one. Goodbye!"
            print_event("call_ended", {"reason": "user exit", "sentiment": s, "duration": "—"})
            return Response(f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna" language="en-US">{xml_safe(fare)}</Say>
  <Hangup/>
</Response>''', mimetype="text/xml")

        reply = get_sarvam_response(user_input, intent, emotion)
        reply_safe = xml_safe(reply)
        print_event("bot_response", {"text": reply, "count": state["response_count"]})

        pause = calculate_pause(reply, intent)
        return Response(f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" timeout="4" speechTimeout="2" actionOnEmptyResult="true"
          bargeIn="true" profanityFilter="false" action="/voice" method="POST">
    <Say voice="Polly.Joanna" language="en-US">{reply_safe}</Say>
    <Pause length="{pause}"/>
  </Gather>
  <Redirect>/handle_silence</Redirect>
</Response>''', mimetype="text/xml")

    except Exception as e:
        print_event("error", {"message": str(e)})
        return Response('''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna" language="en-US">Sorry, there was a technical issue. Please try again.</Say>
  <Hangup/>
</Response>''', mimetype="text/xml")

@app.route("/handle_silence", methods=['GET', 'POST'])
def handle_silence():
    try:
        with state_lock:
            state["silence_count"] += 1
            cnt = state["silence_count"]
        print_event("silence", {"count": cnt})

        if cnt >= 3:
            save_conversation_async()
            n = state["user_name"]
            fare = xml_safe(f"Okay{', '+n if n else ''}, I will let you go. Thanks for your time. Bye!")
            print_event("call_ended", {"reason": "silence timeout",
                                       "sentiment": state["sentiment_score"], "duration": "—"})
            return Response(f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna" language="en-US">{fare}</Say>
  <Hangup/>
</Response>''', mimetype="text/xml")

        n = state["user_name"]
        if cnt == 1:
            prompts = [f"{'Hey '+n+', ' if n else ''}you still there?",
                       "Hello? Can you hear me?", "Are you still with me?"]
        else:
            prompts = [f"{'Alright '+n+', ' if n else ''}I am not hearing anything. Should we continue?",
                       "I think we might have a bad connection. Can you hear me?",
                       "Let me know if you would like to keep talking."]

        p = xml_safe(random.choice(prompts))
        print_event("bot_response", {"text": p, "count": state["response_count"]})
        return Response(f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" timeout="5" speechTimeout="2" actionOnEmptyResult="true"
          bargeIn="true" profanityFilter="false" action="/voice" method="POST">
    <Say voice="Polly.Joanna" language="en-US">{p}</Say>
  </Gather>
  <Redirect>/handle_silence</Redirect>
</Response>''', mimetype="text/xml")

    except Exception as e:
        print(c(f"[SILENCE ERROR] {e}", "red"))
        return Response('''<?xml version="1.0" encoding="UTF-8"?>
<Response><Say voice="Polly.Joanna" language="en-US">Goodbye!</Say><Hangup/></Response>''',
                        mimetype="text/xml")

@app.route("/status", methods=['GET', 'POST'])
def status():
    try:
        cs  = request.values.get('CallStatus', '')
        dur = request.values.get('CallDuration', '0')
        if cs in ("completed", "no-answer", "busy", "failed"):
            with state_lock:
                state["call_status"] = cs
            save_conversation_async()
            print_event("call_ended", {
                "reason": cs, "duration": dur,
                "sentiment": state["sentiment_score"],
                "exchanges": len(state["conversation_memory"]) // 2,
            })
    except Exception as e:
        print(c(f"[STATUS ERROR] {e}", "red"))
    return ("", 204)

@app.route("/recording", methods=['GET', 'POST'])
def recording():
    try:
        rec_url = request.values.get('RecordingUrl')
        def _dl():
            if not rec_url: return
            try:
                r = http_requests.get(rec_url+".mp3",
                                      auth=(account_sid, auth_token), timeout=20)
                if r.status_code == 200:
                    n = state["user_name"] or state["current_call_number"].replace('+','')
                    fn = f"rec_{n}_{int(time.time())}.mp3"
                    with open(fn,'wb') as f: f.write(r.content)
                    print_event("recording_saved", {"filename": fn})
            except Exception as e:
                print(c(f"[REC ERROR] {e}", "red"))
        executor.submit(_dl)
    except Exception as e:
        print(c(f"[RECORDING ERROR] {e}", "red"))
    return ("", 204)

@app.route("/api/hangup", methods=['POST'])
def api_hangup():
    sid = state.get("call_sid") or ""
    if not sid:
        return jsonify({"ok": False, "error": "no active call"}), 400
    try:
        twilio_client = Client(account_sid, auth_token)
        twilio_client.calls(sid).update(status='completed')
        print_event("call_ended", {"reason": "manual hangup", "sentiment": state["sentiment_score"], "duration": "—"})
        with state_lock:
            state["call_status"] = "ended"
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def start_call(number, message, prompt, webhook_base):
    global sarvam_session
    number = number.strip()
    webhook_base = webhook_base.strip().rstrip("/")
    message = (message or "Hello! How can I help you today?").strip()
    prompt = (prompt or "You are a helpful AI assistant.").strip()

    if not number or not webhook_base:
        print(c("[ERROR] phone number and webhook base URL are required", "red"))
        return None

    full_prompt = prompt + """

HUMAN-LIKE CONVERSATION RULES:
- Talk like a real person, not a robot
- Use natural language with occasional filler words
- Show empathy and emotional intelligence
- Listen actively and acknowledge what they say
- Ask follow-up questions based on their responses
- Use contractions (I'm, you're, don't, can't)
- Be conversational, warm, and genuine
- Keep responses brief (1-2 sentences) but natural"""

    with state_lock:
        state["conversation_memory"] = []
        state["system_prompt"]       = full_prompt
        state["current_call_number"] = number
        state["call_message"]        = message
        state["user_name"]           = ""
        state["silence_count"]       = 0
        state["conversation_started"] = False
        state["sentiment_score"]     = 0
        state["response_count"]      = 0
        state["call_status"]         = "initiating"
        state["call_sid"]            = ""

    sarvam_session = get_sarvam_session()

    try:
        twilio_client = Client(account_sid, auth_token)
        call = twilio_client.calls.create(
            to=number,
            from_=twilio_number,
            url=f"{webhook_base}/voice",
            status_callback=f"{webhook_base}/status",
            status_callback_event=['completed'],
            record=True,
            recording_status_callback=f"{webhook_base}/recording",
            machine_detection='DetectMessageEnd',
            async_amd='true',
        )
        with state_lock:
            state["call_sid"]    = call.sid
            state["call_status"] = "ringing"
            state["call_start_time"] = time.time()
        print_event("call_initiated", {"number": number, "sid": call.sid})
        return call.sid
    except Exception as e:
        with state_lock:
            state["call_status"] = "idle"
        print_event("error", {"message": str(e)})
        return None

def cli_loop():
    print("\n" + "="*60)
    print(" TERMINAL AI VOICE BOT")
    print("="*60)
    print(" No dashboard, no UI — everything runs and prints here.\n")

    while True:
        number = input(" Phone number (e.g., +911234567890), or 'q' to quit: ").strip()
        if number.lower() == 'q':
            break

        print("\n  First message (Enter twice to finish):\n")
        lines = []
        while True:
            line = input()
            if not line: break
            lines.append(line)
        message = " ".join(lines).strip()

        print("\n System prompt (Enter twice to finish):\n")
        lines = []
        while True:
            line = input()
            if not line: break
            lines.append(line)
        prompt = " ".join(lines).strip()

        print("\n Webhook base URL (your cloudflare/ngrok tunnel, no trailing slash):")
        webhook_base = input(" URL: ").strip().rstrip("/")

        sid = start_call(number, message, prompt, webhook_base)
        if not sid:
            continue

        print("\n Call in progress — live events will print below.")
        print(" Press Ctrl+C to hang up early.\n")

        try:
            while state["call_status"] not in ("ended", "completed", "no-answer", "busy", "failed"):
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n Hanging up...")
            try:
                Client(account_sid, auth_token).calls(sid).update(status='completed')
            except Exception as e:
                print(c(f"[HANGUP ERROR] {e}", "red"))

        print("\n" + "-"*60 + "\n")

if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=5000, threaded=True, debug=False),
        daemon=True
    ).start()
    time.sleep(1.5)
    print(c(" Webhook server ready on http://localhost:5000", "dim"))
    try:
        cli_loop()
    except KeyboardInterrupt:
        pass
    print("\nShutting down...")
    executor.shutdown(wait=False)
