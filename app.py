import streamlit as st
st.caption("Build: 2025-08-09-02")
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go
import json
import os
from datetime import datetime

# -------------------------------
# Basics & Config
# -------------------------------
st.set_page_config(layout="wide")

# Load secrets
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------------
# Data & Utilities
# -------------------------------
with open("mizan_values_pool.json", "r") as f:
    MIZAN_VALUES_POOL = json.load(f)

MIZAN_LEVELS = {
    1: "Survival & Security",
    2: "Belonging & Connection",
    3: "Achievement & Status",
    4: "Growth & Innovation",
    5: "Purpose & Integrity",
    6: "Service & Contribution",
    7: "Legacy & Sustainability",
}

def log_ai_insight(content: str, context: str = "general"):
    os.makedirs("logs", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = f"logs/{context}_{ts}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def get_company() -> dict:
    """Return company dict from session_state or {}."""
    return st.session_state.get("company_info", {}) or {}

def get_employee_df_for_company(company_name: str) -> pd.DataFrame:
    """Return df of valid employee responses for a company."""
    rows = [
        e for e in st.session_state.get("employee_responses", [])
        if isinstance(e, dict)
        and e.get("company") == company_name
        and all(k in e for k in ("department", "current_experience", "desired_values", "personal_values"))
    ]
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def calculate_entropy(values):
    limiting = 0
    total = 0
    for val in values:
        for item in MIZAN_VALUES_POOL:
            if item["name"] == val:
                total += 1
                if item["type"] == "negative":
                    limiting += 1
    return (limiting / total) * 100 if total > 0 else 0

def group_values(values):
    grouped = {i: {"positive": [], "negative": []} for i in range(1, 8)}
    for val in values:
        for v in MIZAN_VALUES_POOL:
            if v["name"] == val:
                grouped[v["level"]][v["type"]].append(val)
    return grouped

def draw_2d_mizan_dashboard(selected_values=None, mode="employee", selected_department=None):
    st.subheader("Mizan Value Distribution")

    if mode == "employee":
        data = selected_values or []
        if not data:
            st.info("No values selected yet.")
            return
    else:
        entries = [e for e in st.session_state.get("employee_responses", []) if isinstance(e, dict)]
        if not entries:
            st.info("No employee data available yet.")
            return
        df = pd.DataFrame(entries)
        if selected_department and "department" in df.columns:
            df = df[df["department"] == selected_department]
        if df.empty:
            st.info("No data for the selected filter.")
            return
        data = (
            df.get("current_experience", pd.Series(dtype=object)).explode().dropna().tolist()
            + df.get("desired_values", pd.Series(dtype=object)).explode().dropna().tolist()
        )

    grouped = group_values(data)
    fig = go.Figure()
    for level, level_name in MIZAN_LEVELS.items():
        pos = len(grouped[level]["positive"])
        neg = len(grouped[level]["negative"])
        fig.add_trace(
            go.Bar(
                x=[pos], y=[level_name], orientation="h",
                name="Positive", marker_color="green",
                hovertext=grouped[level]["positive"]
            )
        )
        fig.add_trace(
            go.Bar(
                x=[-neg], y=[level_name], orientation="h",
                name="Limiting", marker_color="red",
                hovertext=grouped[level]["negative"]
            )
        )
    fig.update_layout(
        barmode="relative",
        height=500,
        title=f"Mizan Dashboard – {selected_department or 'You'}",
        xaxis_title="Count",
        yaxis_title="Levels",
    )
    st.plotly_chart(fig, use_container_width=True)

def run_dept_insight(dept_df: pd.DataFrame, dept: str) -> str:
    current = dept_df.get("current_experience", pd.Series(dtype=object)).explode().dropna().tolist()
    desired = dept_df.get("desired_values", pd.Series(dtype=object)).explode().dropna().tolist()
    dept_prompt = f"""
You are an AI trained on Mizan's 7-level framework (levels, value definitions, and ethics links).

Department: {dept}
Responses: {len(dept_df)}
Current values: {current}
Desired values: {desired}

Please:
- Count & categorize values by Mizan levels
- Compare current vs desired; call out the biggest gaps
- Estimate cultural entropy (% limiting values) and explain what it means
- Offer 3–6 crisp actions to reduce entropy and move toward the desired values
- Keep tone warm, supportive, and practical
"""
    with st.spinner(f"Analyzing {dept}..."):
        resp = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": dept_prompt}],
        )
    text = resp.choices[0].message.content.strip()
    log_ai_insight(text, context=f"dept_{dept}_analysis")
    return text

def run_org_insight(df: pd.DataFrame, company_name: str) -> str:
    all_current = df.get("current_experience", pd.Series(dtype=object)).explode().dropna().tolist()
    all_desired = df.get("desired_values", pd.Series(dtype=object)).explode().dropna().tolist()
    org_prompt = f"""
You are an AI trained on Mizan's 7-level framework (levels, value definitions, ethics links).

Company: {company_name}
Total responses: {len(df)}
Current (all): {all_current}
Desired (all): {all_desired}

Please provide an org-level summary:
- Overall level distribution (current vs desired)
- Cultural entropy and top drivers
- Alignment with mission, vision, strategy (if provided)
- Key risks / misalignments
- 5–8 actionable recommendations (quick wins → structural moves)
Use clear, warm, supportive language and bullet points.
"""
    with st.spinner("Analyzing organization..."):
        resp = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": org_prompt}],
        )
    text = resp.choices[0].message.content.strip()
    log_ai_insight(text, context="org_culture_analysis")
    return text

# -------------------------------
# Sidebar & Navigation
# -------------------------------
st.sidebar.image("logo.png", width=150)
page = st.sidebar.radio("Navigation", ["Company", "Employee"])

# -------------------------------
# Company Page
# -------------------------------
if page == "Company":
    st.image("logo.png", width=100)
    st.markdown("<h1 style='color:#284B63;'>Mizan Culture Intelligence Platform</h1>", unsafe_allow_html=True)
    st.markdown("<hr style='border:1px solid #ccc;'>", unsafe_allow_html=True)

    st.markdown("### 1. Company Info")
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            in_name = st.text_input("Company Name")
            in_vision = st.text_area("Vision")
            in_strategy = st.text_area("Strategy")
        with col2:
            in_mission = st.text_area("Mission")
            in_values = st.text_area("Core Values (comma-separated)")

    # Save without nuking previous non-empty fields
    if st.button("Save Company Info"):
        ci = st.session_state.setdefault("company_info", {})
        if in_name:    ci["name"] = in_name
        if in_vision:  ci["vision"] = in_vision
        if in_mission: ci["mission"] = in_mission
        if in_strategy: ci["strategy"] = in_strategy
        if in_values:
            ci["values"] = [v.strip() for v in in_values.split(",") if v.strip()]
        st.success("Company info saved.")

    # Sticky summary
    ci = get_company()
    if ci.get("name"):
        with st.expander(" Company profile (sticky)", expanded=True):
            st.markdown(f"**Name:** {ci.get('name','—')}")
            st.markdown(f"**Vision:** {ci.get('vision','—')}")
            st.markdown(f"**Mission:** {ci.get('mission','—')}")
            st.markdown(f"**Strategy:** {ci.get('strategy','—')}")
            st.markdown(f"**Values:** {', '.join(ci.get('values', [])) or '—'}")

    # Structure upload
    if ci.get("name"):
        st.header("2. Upload Company Structure")
        file = st.file_uploader("Upload Structure CSV", type="csv")
        if file:
            df_struct = pd.read_csv(file)
            needed = ["Employee Name", "Employee Email", "Employee Department", "Supervisor Name"]
            if all(col in df_struct.columns for col in needed):
                st.session_state["company_structure"] = df_struct
                st.dataframe(df_struct)
                st.success("Structure uploaded.")

                # On-demand org-design insight
                if st.button(" Generate Org-Design Insight"):
                    preview = df_struct.head(20).to_csv(index=False)
                    prompt = f"""
You are an expert in organizational design. Given:
Company: {ci.get('name','')}
Vision: {ci.get('vision','')}
Mission: {ci.get('mission','')}
Strategy: {ci.get('strategy','')}
Values: {ci.get('values','')}

Here is a preview of the company structure:
{preview}

Please:
- Assess alignment of structure with vision/strategy
- Identify structure type
- Recommend design improvements
- Include practical organizational design suggestions (clarity, span of control, role alignment, agility).
"""
                    with st.spinner("Generating insights..."):
                        response = client.chat.completions.create(
                            model="gpt-4",
                            messages=[{"role": "user", "content": prompt}],
                        )
                    org_insight = response.choices[0].message.content.strip()
                    st.markdown(org_insight)
                    log_ai_insight(org_insight, context="org_design_analysis")
            else:
                st.error("Missing required columns in CSV.")

    # Post-Assessment (button-driven)
    if ci.get("name"):
        df_emp = get_employee_df_for_company(ci["name"])
        st.header("4. Organizational Culture Analysis")

        if df_emp.empty:
            st.info("No employee submissions yet.")
        else:
            # Departmental Results
            st.subheader("Departmental Results")
            depts = sorted(
                df_emp.get("department", pd.Series(dtype=object))
                .dropna()
                .unique()
                .tolist()
            )
            if depts:
                sel_dept = st.selectbox("Choose department", depts, key="dept_select")
                if st.button(" Generate Department Result", key="btn_dept"):
                    dept_df = df_emp[df_emp["department"] == sel_dept]
                    cur = dept_df.get("current_experience", pd.Series(dtype=object)).explode().dropna().tolist()
                    des = dept_df.get("desired_values", pd.Series(dtype=object)).explode().dropna().tolist()
                    dept_entropy = calculate_entropy(cur + des)
                    st.caption(f"Entropy for {sel_dept}: **{dept_entropy:.1f}%**")
                    dept_text = run_dept_insight(dept_df, sel_dept)
                    st.markdown(dept_text)
            else:
                st.warning("No department data available.")

            # Org Result
            st.subheader("Organization-wide Result")
            if st.button(" Generate Org Result", key="btn_org"):
                org_text = run_org_insight(df_emp, ci["name"])
                st.markdown(org_text)

            # Visual dashboard (all data)
            st.subheader("Mizan Dashboard")
            draw_2d_mizan_dashboard(mode="admin")

# -------------------------------
# Employee Page
# -------------------------------
elif page == "Employee":
    st.image("logo.png", width=100)
    st.markdown("<h1 style='color:#284B63;'>Mizan Culture Intelligence Platform</h1>", unsafe_allow_html=True)
    st.markdown("<hr style='border:1px solid #ccc;'>", unsafe_allow_html=True)

    if "company_info" not in st.session_state or "company_structure" not in st.session_state:
        st.warning("The company has not completed setup.")
    else:
        st.markdown("### Step 1: Your Information")
        emp_name = st.text_input("Your Name")
        emp_email = st.text_input("Your Email")
        dept_list = st.session_state["company_structure"]["Employee Department"].unique()
        emp_dept = st.selectbox("Your Department", dept_list)

        def get_options():
            return [f"{v['name']}: {v['definition']}" for v in MIZAN_VALUES_POOL]

        def clean(vs):
            return [v.split(":")[0].strip() for v in vs]

        st.markdown("### Step 2: Your Values")
        personal = st.multiselect("Your Personal Values (select 7)", get_options())
        if len(personal) != 7:
            st.info("Please select exactly 7 values for Personal.")
            st.stop()

        st.markdown("### Step 3: Current Culture")
        current = st.multiselect("Current Company Values (select 7)", get_options())
        if len(current) != 7:
            st.info("Please select exactly 7 values for Current.")
            st.stop()

        st.markdown("### Step 4: Desired Culture")
        desired = st.multiselect("Desired Future Values (select 7)", get_options())
        if len(desired) != 7:
            st.info("Please select exactly 7 values for Desired.")
            st.stop()

        st.markdown("### Step 5: Experience Ratings")
        engagement = st.slider("How engaged do you feel at work?", 1, 5)
        recognition = st.slider("How often are you recognized?", 1, 5)

        if st.button("Generate My Report"):
            entry = {
                "name": emp_name,
                "email": emp_email,
                "department": emp_dept,
                "personal_values": clean(personal),
                "current_experience": clean(current),
                "desired_values": clean(desired),
                "engagement": engagement,
                "recognition": recognition,
                "company": get_company().get("name", ""),
            }

            prompt = f"""
You are an AI trained on Mizan's 7-level values framework (levels, value definitions, ethics links).

Personal: {entry['personal_values']}
Current: {entry['current_experience']}
Desired: {entry['desired_values']}
Engagement: {entry['engagement']}
Recognition: {entry['recognition']}

Company: {entry['company']}
Please provide:
- Level distribution and alignment across the 3 sets of values
- Cultural entropy (gap between current and desired values)
- Alignment between employee values and mission/vision/strategy
- Opportunities for growth and development
Keep the tone supportive, insightful, and actionable.
"""
            with st.spinner("Analyzing your results..."):
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                )
                report = response.choices[0].message.content.strip()

            st.markdown("### Your Personalized Report")
            st.write(report)
            log_ai_insight(report, context=f"employee_{emp_email}_report")

            # Entropy display
            entropy = calculate_entropy(entry["current_experience"] + entry["desired_values"])
            st.markdown(f"### Cultural Entropy Score: `{entropy:.1f}%`")
            if entropy < 10:
                st.success("🟢 Low cultural entropy. Strong alignment.")
            elif entropy < 20:
                st.warning("🟠 Moderate cultural entropy. Some limiting values detected.")
            else:
                st.error("🔴 High cultural entropy. Cultural friction likely.")

            # Persist
            if "employee_responses" not in st.session_state:
                st.session_state["employee_responses"] = []
            st.session_state["employee_responses"].append(entry)

            # Visual dashboard
            st.subheader("Your Visual Dashboard")
            draw_2d_mizan_dashboard(
                selected_values=entry["personal_values"] + entry["current_experience"] + entry["desired_values"],
                mode="employee",
            )