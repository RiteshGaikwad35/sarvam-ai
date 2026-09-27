## Real time URL
https://callai-b5bq.onrender.com/

## Real time locally run
https://drive.google.com/file/d/1Y3pFYXakX2TyKGRk5IKy65mPjA4PQ25h/view?usp=sharing

## How It Works

This project enables **real-time, multilingual voice interaction between customers and an AI agent**. The system takes a customer's voice input, understands it in their native language, generates an intelligent response using **Sarvam 105B Conversations**, and converts the response back into natural speech.

The complete pipeline is designed to minimize latency and provide a conversational experience similar to talking to a human customer-support agent.

### System Flow

```text
Customer Voice
      │
      ▼
┌──────────────────┐
│  Voice Capture   │
│   Microphone     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Speech-to-Text    │
│  Multilingual STT│
└────────┬─────────┘
         │
         ▼
┌─────────────────────────┐
│   Sarvam 105B           │
│   Conversations Model   │
│                         │
│ • Understands context   │
│ • Detects intent        │
│ • Generates response    │
│ • Supports multilingual│
│   conversations         │
└────────┬────────────────┘
         │
         ▼
┌──────────────────┐
│  Text-to-Speech  │
│  Multilingual TTS│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Audio Response  │
│    to Customer   │
└──────────────────┘
```

### 1. Voice Input

The customer speaks naturally through a microphone.

The system captures the incoming audio stream and sends it through the speech-processing pipeline without requiring the customer to type anything.

For example:

```text
Customer:
"मुझे अपने ऑर्डर का स्टेटस जानना है।"
```

The customer can speak in their preferred language instead of having to switch to English.

### 2. Speech-to-Text

The incoming speech is converted into text using a multilingual Speech-to-Text layer.

The transcription preserves the customer's language so that the downstream AI model can understand the actual intent of the conversation.

```text
Audio
  ↓
Multilingual Speech Recognition
  ↓
"मुझे अपने ऑर्डर का स्टेटस जानना है।"
```

### 3. AI Conversation — Sarvam 105B

The transcribed text is passed to **Sarvam 105B Conversations**, which acts as the core conversational intelligence of the system.

The model processes:

* The customer's current message
* Previous conversation context
* Customer intent
* Relevant application or business context
* Language preferences

It then generates an appropriate response.

For example:

```text
User:
मुझे अपने ऑर्डर का स्टेटस जानना है।

        ↓

Sarvam 105B Conversations

        ↓

AI Response:
आपका ऑर्डर अभी डिलीवरी के लिए निकल चुका है
और जल्द ही आप तक पहुँच जाएगा।
```

Because the interaction is conversational, the AI can maintain context across multiple turns rather than treating every sentence as an isolated request.

### 4. Text-to-Speech

The generated response is passed to a multilingual Text-to-Speech system.

The response is converted back into audio in the appropriate language.

```text
AI-generated response
        ↓
Multilingual TTS
        ↓
Natural speech audio
```

This allows the customer to hear the answer instead of reading it.

### 5. Real-Time Interaction

The key goal of the system is **low-latency voice interaction**.

Instead of following a slow:

```text
Speak → Wait → Process → Wait → Response
```

workflow, the system is designed as a streaming pipeline:

```text
Customer speaks
      ↓
Audio is processed
      ↓
Speech is transcribed
      ↓
AI starts generating
      ↓
Response is synthesized
      ↓
Customer hears response
```

This reduces perceived waiting time and makes the interaction feel more natural.

### Multilingual Conversations

A major feature of the system is that customers can interact in multiple languages.

The architecture allows customers to communicate in their preferred language without requiring them to manually switch languages throughout the conversation.

```text
Customer
   │
   ├── Hindi ──────────┐
   ├── English ────────┤
   ├── Marathi ────────┤
   ├── Tamil ──────────┤
   └── Other supported │
       languages ──────┘
                       │
                       ▼
                AI Conversation
                       │
                       ▼
                Voice Response
```

This makes the system suitable for customer-facing applications where users have different language preferences.

### Overall Architecture

The complete system consists of five major layers:

| Layer           | Responsibility                              |
| --------------- | ------------------------------------------- |
| Voice Input     | Captures customer audio                     |
| Speech-to-Text  | Converts multilingual speech into text      |
| LLM             | Understands context and generates responses |
| Text-to-Speech  | Converts AI responses into speech           |
| Streaming Layer | Connects the components with low latency    |

The central idea is to combine **multilingual speech processing, a large conversational model, and real-time audio streaming** into a single voice interface.

### Why This Architecture?

Traditional customer-support interfaces require users to:

```text
Open application → Type message → Wait → Read response
```

This project changes that interaction to:

```text
Speak naturally → AI understands → AI responds → Listen
```

The result is a more natural interface for customers, particularly when typing is inconvenient or when users are more comfortable communicating in their native language.

### Core Technologies

* **Sarvam 105B Conversations** — Conversational intelligence
* **Multilingual Speech-to-Text** — Converts customer speech into text
* **Multilingual Text-to-Speech** — Converts AI responses into speech
* **Real-Time Audio Streaming** — Enables low-latency interaction
* **Conversation Context** — Maintains continuity across multiple turns

### Example Conversation

```text
Customer:
"मेरा ऑर्डर अभी तक नहीं आया है।"

        ↓ Speech-to-Text

Transcription:
"मेरा ऑर्डर अभी तक नहीं आया है।"

        ↓ Sarvam 105B Conversations

AI:
"मैं आपके ऑर्डर की स्थिति चेक करता हूँ। कृपया
अपना ऑर्डर आईडी बताइए।"

        ↓ Text-to-Speech

Customer hears:
"मैं आपके ऑर्डर की स्थिति चेक करता हूँ..."
```

The entire interaction happens through **voice**, allowing the customer to communicate naturally without typing.
