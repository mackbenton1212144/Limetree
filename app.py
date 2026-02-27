import calendar
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from typing import Optional

import smtplib
import streamlit as st

DB_PATH = "lime_tree.db"
APP_TITLE = "Mack and Addie's Lime Tree at Porch"
DEFAULT_REMINDER_EMAIL = "awhitehouse@scu.edu"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watering_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watered_on TEXT NOT NULL UNIQUE,
                amount_liters REAL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fertilizer_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fertilized_on TEXT NOT NULL UNIQUE,
                fertilizer_type TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminder_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_date TEXT NOT NULL UNIQUE,
                sent_to TEXT NOT NULL,
                sent_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def get_setting(key: str, default: str) -> str:
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?;", (key,)).fetchone()
    if row:
        return row["value"]
    return default


def set_setting(key: str, value: str) -> None:
    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """,
            (key, value),
        )
        conn.commit()


def save_watering_log(watered_on: date, amount_liters: float, notes: str) -> bool:
    now_iso = datetime.now().isoformat(timespec="seconds")
    with closing(get_connection()) as conn:
        existing = conn.execute(
            "SELECT id FROM watering_logs WHERE watered_on = ?;",
            (watered_on.isoformat(),),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE watering_logs
                SET amount_liters = ?, notes = ?, created_at = ?
                WHERE watered_on = ?;
                """,
                (amount_liters, notes, now_iso, watered_on.isoformat()),
            )
            conn.commit()
            return False

        conn.execute(
            """
            INSERT INTO watering_logs (watered_on, amount_liters, notes, created_at)
            VALUES (?, ?, ?, ?);
            """,
            (watered_on.isoformat(), amount_liters, notes, now_iso),
        )
        conn.commit()
        return True


def save_fertilizer_log(fertilized_on: date, fertilizer_type: str, notes: str) -> bool:
    now_iso = datetime.now().isoformat(timespec="seconds")
    with closing(get_connection()) as conn:
        existing = conn.execute(
            "SELECT id FROM fertilizer_logs WHERE fertilized_on = ?;",
            (fertilized_on.isoformat(),),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE fertilizer_logs
                SET fertilizer_type = ?, notes = ?, created_at = ?
                WHERE fertilized_on = ?;
                """,
                (fertilizer_type, notes, now_iso, fertilized_on.isoformat()),
            )
            conn.commit()
            return False

        conn.execute(
            """
            INSERT INTO fertilizer_logs (fertilized_on, fertilizer_type, notes, created_at)
            VALUES (?, ?, ?, ?);
            """,
            (fertilized_on.isoformat(), fertilizer_type, notes, now_iso),
        )
        conn.commit()
        return True


def get_watering_dates(year: int, month: int) -> set[str]:
    start = date(year, month, 1).isoformat()
    _, days_in_month = calendar.monthrange(year, month)
    end = date(year, month, days_in_month).isoformat()
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT watered_on
            FROM watering_logs
            WHERE watered_on BETWEEN ? AND ?;
            """,
            (start, end),
        ).fetchall()
    return {row["watered_on"] for row in rows}


def get_last_fertilized_date() -> Optional[date]:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT fertilized_on
            FROM fertilizer_logs
            ORDER BY fertilized_on DESC
            LIMIT 1;
            """
        ).fetchone()
    if not row:
        return None
    return datetime.strptime(row["fertilized_on"], "%Y-%m-%d").date()


def get_recent_logs(table_name: str, date_col: str) -> list[sqlite3.Row]:
    query = f"""
        SELECT *
        FROM {table_name}
        ORDER BY {date_col} DESC
        LIMIT 10;
    """
    with closing(get_connection()) as conn:
        rows = conn.execute(query).fetchall()
    return rows


def get_watering_recommendation(planting_date: date, today: date) -> tuple[str, str]:
    days_since_planting = (today - planting_date).days
    season = "winter" if today.month in {11, 12, 1, 2} else "summer_or_shoulder"

    if days_since_planting <= 30:
        return (
            "Weeks 1-4",
            "Water every 2-3 days, 5-10 gallons each time. Keep soil moist, not soggy.",
        )
    if days_since_planting <= 180:
        return (
            "Months 2-6",
            "Water 2 times per week, 10-15 gallons each time. Water slowly for deep penetration.",
        )
    if season == "winter":
        return ("After 6 months (winter)", "Water every 10-14 days if no rain.")
    return ("After 6 months (warm season)", "Water 1-2 times per week depending on heat.")


def get_fertilizer_schedule_for_year(year: int) -> list[date]:
    return [date(year, 3, 1), date(year, 5, 1), date(year, 7, 1), date(year, 9, 1)]


def get_due_and_upcoming_tasks(planting_date: date, today: date) -> tuple[list[str], list[tuple[date, str]]]:
    due: list[str] = []
    upcoming: list[tuple[date, str]] = []

    phase, watering_text = get_watering_recommendation(planting_date, today)
    due.append(f"Watering plan ({phase}): {watering_text}")

    year_dates = get_fertilizer_schedule_for_year(today.year)
    for fert_day in year_dates:
        if fert_day == today:
            due.append("Fertilize today: ~1/2 cup citrus fertilizer under canopy, then deep water.")
        elif today < fert_day <= today + timedelta(days=21):
            upcoming.append((fert_day, "Fertilizer window"))

    if today.month in {11, 12, 1, 2}:
        due.append("Do not fertilize in winter (Nov-Feb).")

    if today.month in {12, 1, 2}:
        due.append("Watch forecast: if below 30F, cover tree overnight with frost cloth.")

    return due, sorted(upcoming, key=lambda x: x[0])


def reminder_sent_today(today: date) -> bool:
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT id FROM reminder_logs WHERE reminder_date = ?;",
            (today.isoformat(),),
        ).fetchone()
    return row is not None


def mark_reminder_sent(today: date, sent_to: str) -> None:
    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO reminder_logs (id, reminder_date, sent_to, sent_at)
            VALUES (
                (SELECT id FROM reminder_logs WHERE reminder_date = ?),
                ?, ?, ?
            );
            """,
            (today.isoformat(), today.isoformat(), sent_to, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()


def send_watering_email(
    watered_on: date,
    amount_liters: float,
    notes: str,
    recipient_email: str,
) -> tuple[bool, str]:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "")

    if not all([smtp_host, smtp_user, smtp_password, smtp_from, recipient_email]):
        return (
            False,
            "Email skipped: set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, and recipient email.",
        )

    msg = EmailMessage()
    msg["Subject"] = f"Mack and Addie's Lime Tree Watered - {watered_on.isoformat()}"
    msg["From"] = smtp_from
    msg["To"] = recipient_email
    msg.set_content(
        "\n".join(
            [
                "Mack and Addie's Bearss lime tree watering at Porch has been logged.",
                "",
                f"Date: {watered_on.isoformat()}",
                f"Amount: {amount_liters:.1f} L",
                f"Notes: {notes or 'None'}",
                "",
                "Location: Porch, Santa Clara, California",
            ]
        )
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True, f"Email sent to {recipient_email}."
    except Exception as exc:  # noqa: BLE001
        return False, f"Email failed: {exc}"


def smtp_ready() -> bool:
    return all(
        [
            os.getenv("SMTP_HOST"),
            os.getenv("SMTP_USER"),
            os.getenv("SMTP_PASSWORD"),
            os.getenv("SMTP_FROM"),
        ]
    )


def send_reminder_email(
    recipient_email: str,
    today: date,
    due_tasks: list[str],
    upcoming_tasks: list[tuple[date, str]],
) -> tuple[bool, str]:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "")

    if not all([smtp_host, smtp_user, smtp_password, smtp_from, recipient_email]):
        return (
            False,
            "Reminder email skipped: set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, and recipient email.",
        )

    upcoming_lines = [
        f"- {task_date.isoformat()}: {task_name}" for task_date, task_name in upcoming_tasks[:5]
    ] or ["- No upcoming scheduled events in next 3 weeks."]

    msg = EmailMessage()
    msg["Subject"] = f"Lime Tree Care Reminder - {today.isoformat()}"
    msg["From"] = smtp_from
    msg["To"] = recipient_email
    msg.set_content(
        "\n".join(
            [
                "Mack and Addie's Bearss lime tree reminder (Porch, Santa Clara):",
                "",
                "Due today:",
                *[f"- {task}" for task in due_tasks],
                "",
                "Upcoming:",
                *upcoming_lines,
            ]
        )
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True, f"Reminder email sent to {recipient_email}."
    except Exception as exc:  # noqa: BLE001
        return False, f"Reminder email failed: {exc}"


def render_calendar(year: int, month: int, watered_dates: set[str]) -> str:
    month_name = calendar.month_name[month]
    cal = calendar.monthcalendar(year, month)
    cells: list[str] = []
    cells.append(
        "<div style='border:1px solid #d9f99d;border-radius:14px;background:#ffffff;padding:14px;"
        "box-shadow:0 1px 2px rgba(0,0,0,0.04);'>"
        f"<h3 style='margin:0 0 10px 0;color:#365314;font-size:22px;font-weight:700;'>{month_name} {year}</h3>"
        "<table style='width:100%;table-layout:fixed;border-collapse:separate;border-spacing:6px;'>"
        "<thead><tr>"
    )

    for weekday in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        cells.append(
            f"<th style='padding:6px 2px;color:#4d7c0f;font-size:12px;text-transform:uppercase;"
            f"letter-spacing:0.4px;'>{weekday}</th>"
        )
    cells.append("</tr></thead><tbody>")

    for week in cal:
        cells.append("<tr>")
        for day in week:
            if day == 0:
                cells.append(
                    "<td style='height:44px;border:1px dashed #e2e8f0;border-radius:8px;background:#f8fafc;'></td>"
                )
                continue
            day_iso = date(year, month, day).isoformat()
            if day_iso in watered_dates:
                cells.append(
                    "<td style='height:44px;text-align:center;border-radius:8px;background:#65a30d;"
                    "color:white;font-weight:700;'>"
                    f"{day}</td>"
                )
            else:
                cells.append(
                    "<td style='height:44px;text-align:center;border:1px solid #d9f99d;border-radius:8px;"
                    "background:#f7fee7;color:#3f6212;font-weight:600;'>"
                    f"{day}</td>"
                )
        cells.append("</tr>")

    cells.append("</tbody></table>")
    cells.append(
        "<div style='display:flex;gap:14px;align-items:center;margin-top:10px;font-size:12px;color:#475569;'>"
        "<span><span style='display:inline-block;width:10px;height:10px;background:#65a30d;border-radius:99px;"
        "margin-right:6px;'></span>Watered</span>"
        "<span><span style='display:inline-block;width:10px;height:10px;background:#f7fee7;border:1px solid #d9f99d;"
        "border-radius:99px;margin-right:6px;'></span>Not logged</span>"
        "</div></div>"
    )
    return "".join(cells)


def render_care_card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="rounded-2xl border border-lime-200 bg-white p-4 shadow-sm">
            <h4 class="text-md font-semibold text-lime-900">{title}</h4>
            <p class="mt-2 text-sm leading-6 text-slate-700">{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🍋",
        layout="wide",
    )
    init_db()
    saved_planting = get_setting("planting_date", date.today().isoformat())
    saved_reminder_email = get_setting("reminder_email", DEFAULT_REMINDER_EMAIL)
    email_enabled = get_setting("email_enabled", "0") == "1"

    st.markdown(
        """
        <script src="https://cdn.tailwindcss.com"></script>
        <div class="rounded-2xl bg-gradient-to-r from-lime-600 to-emerald-600 p-6 text-white shadow-lg">
            <h1 class="text-3xl font-bold">Mack and Addie's Lime Tree at Porch</h1>
            <p class="mt-2 text-sm md:text-base">
                Track watering, fertilizer, and care for Mack and Addie's 3-foot Bearss lime tree at Porch in Santa Clara, California.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.subheader("Tree Settings")
        planting_date = st.date_input(
            "Planting date",
            value=datetime.strptime(saved_planting, "%Y-%m-%d").date(),
            help="Used to generate year-1 care schedule.",
        )
        reminder_email = st.text_input(
            "Scheduled reminder email",
            value=saved_reminder_email,
            help="Daily care reminder recipient.",
        )
        auto_send = st.checkbox("Auto-send one reminder per day", value=True)
        email_enabled = st.checkbox(
            "Enable email features",
            value=email_enabled,
            help="Turn this on only when SMTP is configured.",
        )

        if st.button("Save Settings"):
            set_setting("planting_date", planting_date.isoformat())
            set_setting("reminder_email", reminder_email.strip() or DEFAULT_REMINDER_EMAIL)
            set_setting("email_enabled", "1" if email_enabled else "0")
            st.success("Settings saved.")

    today = date.today()
    due_tasks, upcoming_tasks = get_due_and_upcoming_tasks(planting_date, today)

    st.subheader("Today's Scheduled Care")
    for task in due_tasks:
        st.markdown(f"- {task}")

    st.subheader("Upcoming Schedule (next 3 weeks)")
    if upcoming_tasks:
        for task_date, task_name in upcoming_tasks:
            st.markdown(f"- {task_date.isoformat()}: {task_name}")
    else:
        st.caption("No fixed schedule items due in the next 3 weeks.")

    auto_target = reminder_email.strip() or DEFAULT_REMINDER_EMAIL
    if email_enabled and auto_send and not reminder_sent_today(today):
        sent, message = send_reminder_email(auto_target, today, due_tasks, upcoming_tasks)
        if sent:
            mark_reminder_sent(today, auto_target)
            st.success(message)
        else:
            st.warning(message)

    if st.button("Send Today's Reminder Email Now"):
        if not email_enabled:
            st.info("Email features are OFF. Turn on 'Enable email features' in the sidebar first.")
        elif not smtp_ready():
            st.info("SMTP not configured yet. Email is disabled until SMTP environment variables are set.")
        else:
            sent, message = send_reminder_email(auto_target, today, due_tasks, upcoming_tasks)
            if sent:
                mark_reminder_sent(today, auto_target)
                st.success(message)
            else:
                st.warning(message)

    st.write("")
    left, right = st.columns([1, 1])

    with left:
        st.subheader("Log Watering")
        watered_on = st.date_input("Watered on", value=date.today(), key="water_date")
        amount = st.number_input("Amount (liters)", min_value=0.0, max_value=20.0, value=2.0, step=0.1)
        water_notes = st.text_area("Watering notes", placeholder="Example: Soil dry 2 inches down.")

        recipient_email = st.text_input(
            "Notification email",
            value=auto_target,
            help="You will get an email when watering is logged.",
        )

        if st.button("Save Watering Log", type="primary"):
            is_new_log = save_watering_log(watered_on, amount, water_notes)

            if is_new_log:
                st.success(f"Watering logged for {watered_on.isoformat()}.")
            else:
                st.info(f"Updated watering entry for {watered_on.isoformat()}.")

            if not email_enabled:
                st.info("Watering saved. Email notifications are OFF in sidebar settings.")
            elif not smtp_ready():
                st.info("Watering saved. SMTP is not configured, so no email was sent.")
            else:
                success, message = send_watering_email(
                    watered_on,
                    amount,
                    water_notes,
                    recipient_email.strip(),
                )
                if success:
                    st.success(message)
                else:
                    st.warning(message)

    with right:
        st.subheader("Log Fertilizer")
        fertilized_on = st.date_input("Fertilized on", value=date.today(), key="fert_date")
        fert_type = st.selectbox(
            "Fertilizer type",
            [
                "Citrus fertilizer (balanced)",
                "Slow-release citrus blend",
                "Fish emulsion",
                "Compost top-dress",
            ],
        )
        fert_notes = st.text_area("Fertilizer notes", placeholder="Example: Half-strength due to young tree.")

        if st.button("Save Fertilizer Log"):
            is_new_log = save_fertilizer_log(fertilized_on, fert_type, fert_notes)
            if is_new_log:
                st.success(f"Fertilizer logged for {fertilized_on.isoformat()}.")
            else:
                st.info(f"Updated fertilizer entry for {fertilized_on.isoformat()}.")

    st.write("")
    cal_col, schedule_col = st.columns([1.2, 0.8])

    with cal_col:
        st.subheader("Watering Calendar")
        cal_nav_col1, cal_nav_col2 = st.columns(2)
        with cal_nav_col1:
            selected_year = st.selectbox("Year", options=list(range(date.today().year - 1, date.today().year + 3)))
        with cal_nav_col2:
            selected_month = st.selectbox("Month", options=list(range(1, 13)), format_func=lambda m: calendar.month_name[m])

        watered_dates = get_watering_dates(selected_year, selected_month)
        calendar_html = render_calendar(selected_year, selected_month, watered_dates)
        st.markdown(calendar_html, unsafe_allow_html=True)

    with schedule_col:
        st.subheader("Care Guidance")
        last_fertilized = get_last_fertilized_date()
        if last_fertilized:
            days_since = (today - last_fertilized).days
            if days_since >= 90:
                fert_msg = "Fertilizer is due now (about every 3 months in warm season)."
            else:
                fert_msg = f"Next fertilizer window in about {90 - days_since} days."
        else:
            fert_msg = "No fertilizer logged yet. Start in spring with light citrus fertilizer."

        render_care_card(
            "Watering (Santa Clara climate)",
            (
                "Deep, infrequent watering is best. Build a 2-3 foot watering basin and keep mulch 6 inches away "
                "from trunk. Check top 2 inches of soil before watering and avoid soggy roots."
            ),
        )
        render_care_card(
            "Fertilizing",
            (
                "Use citrus fertilizer (6-4-6, 8-3-9, or similar) in March, May, July, and September only. "
                "For a 2-3 foot tree use ~1/2 cup granular fertilizer under canopy, then water deeply. "
                f"{fert_msg}"
            ),
        )
        render_care_card(
            "Sun and protection",
            (
                "Bearss lime trees need 8+ hours of sun. If temperatures drop below 30F, cover tree overnight "
                "with frost cloth and remove cover during daytime."
            ),
        )

    st.subheader("Interactive Year-1 Checklist")
    col_a, col_b = st.columns(2)
    with col_a:
        st.checkbox("Watered deeply today (not shallow surface watering).", key="c1")
        st.checkbox("Mulch is 2-3 inches deep and 6 inches away from trunk.", key="c2")
        st.checkbox("Checked for overwatering signs (yellowing leaves, mushy soil, fungal smell).", key="c3")
        st.checkbox("Checked for underwatering signs (curling leaves, dull color, leaf drop).", key="c4")
    with col_b:
        st.checkbox("Removed dead/damaged branches only (minimal year-1 pruning).", key="c5")
        st.checkbox("Removed suckers below graft union if present.", key="c6")
        st.checkbox("Removed most first-year fruit (keep at most 1-2 limes).", key="c7")
        st.checkbox("Reviewed forecast for frost-risk nights.", key="c8")

    with st.expander("Full Bearss Lime Care Instructions (Santa Clara Zone 9b)"):
        st.markdown(
            """
            **Success priorities**
            - Deep, infrequent watering
            - Consistent nitrogen feeding
            - Good mulch management
            - Light pruning in early years
            - Year 1 focus: root establishment, not fruit production

            **Watering plan (year 1)**
            - Immediately after planting: deep soak, 2-3 ft basin, 2-3 in mulch, keep mulch 6 in from trunk
            - Weeks 1-4: every 2-3 days, 5-10 gallons
            - Months 2-6: 2x/week, 10-15 gallons
            - After 6 months summer: 1-2x/week based on heat
            - After 6 months winter: every 10-14 days if no rain

            **Fertilizer plan (year 1)**
            - Feed 4x/year: March, May, July, September
            - Use citrus fertilizer (6-4-6, 8-3-9, or similar)
            - Do not fertilize November-February
            - Apply under canopy (not trunk), then deep water

            **Fruit, mulch, frost, and pruning**
            - Year 1: remove most fruit, keep at most 1-2 limes
            - Maintain 2-3 in mulch year-round, replenish each spring
            - Frost below 30F: cover overnight, uncover daytime
            - Year 1 pruning: minimal (dead/damaged only); Year 2+ light shaping

            **Production timeline**
            - Year 1: root development
            - Year 2: light fruiting
            - Year 3: heavier production
            """
        )

    st.write("")
    history_col1, history_col2 = st.columns(2)
    with history_col1:
        st.subheader("Recent Watering")
        water_rows = get_recent_logs("watering_logs", "watered_on")
        if water_rows:
            st.dataframe(water_rows, use_container_width=True)
        else:
            st.caption("No watering logs yet.")

    with history_col2:
        st.subheader("Recent Fertilizer")
        fert_rows = get_recent_logs("fertilizer_logs", "fertilized_on")
        if fert_rows:
            st.dataframe(fert_rows, use_container_width=True)
        else:
            st.caption("No fertilizer logs yet.")


if __name__ == "__main__":
    main()
