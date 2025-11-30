# Architecture Diagram – Social Media Agent

```mermaid
flowchart TD

A[User Interface - Streamlit App] --> B[User Inputs: Email + Interests]
B[User Inputs: Email + Interests] --> C[Request Handler]
C[Request Handler] --> D[OpenRouter GPT API]
D[OpenRouter GPT API] --> E[AI Generated Content Plan]
E[AI Generated Content Plan] --> F[Streamlit Output Display]
F[Streamlit Output Display] --> G[Store Temp User Data]
G[Store Temp User Data] --> H[Daily Scheduler]
H[Daily Scheduler] --> I[SMTP Email Sender]
I[SMTP Email Sender] --> J[User Receives Email Daily at 7 AM IST]
```

---

### Explanation

* **Streamlit UI** collects user inputs
* **AI Model (GPT)** generates tailored content
* **Scheduler** automates daily email
* **SMTP** sends the email to the user
* No database is used; data is runtime-only
