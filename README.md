# Mack and Addie's Lime Tree at Porch

Interactive Streamlit app for tracking care of a 3-foot Bearss lime tree in Santa Clara, California (Zone 9b).

## Features

- Log daily watering and notes
- Log fertilizer events
- View a monthly watering calendar
- Follow an interactive Year-1 care checklist
- See scheduled care guidance based on planting date
- Store data locally in SQLite (`lime_tree.db`)
- Optional email reminders and notifications (can be turned off)

## Setup

### 1) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Run the app

```bash
streamlit run app.py --server.port 8502
```

### 4) One-click launcher on Mac

You can also double-click:

`Start Lime Tree Website.command`

## Optional Email Setup (Gmail SMTP)

If you want reminder/notification emails:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your_email@gmail.com"
export SMTP_PASSWORD="your_16_char_google_app_password"
export SMTP_FROM="your_email@gmail.com"
```

Restart Streamlit and enable **Email features** in the sidebar.

## Notes

- If SMTP variables are not set, the app still works fully for tracking and scheduling.
- SQLite tables are auto-created on first run.
- Keep these out of GitHub: `.venv`, `lime_tree.db`, `__pycache__`, `.DS_Store`.
