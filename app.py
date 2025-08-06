import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go
import json
import os
from datetime import datetime

def log_ai_insight(content, context="general"):
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"logs/{context}_{timestamp}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

# Load environment variables and keys
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=OPENAI_API_KEY)

# Set up page layout
st.set_page_config(layout="wide")

# --- Load Mizan Value Pool ---
with open("mizan_values_pool.json", "r") as f:
    MIZAN_VALUES_POOL = json.load(f)

MIZAN_LEVELS = {
    1: "Survival & Security",
    2: "Belonging & Connection",
    3: "Achievement & Status",
    4: "Growth & Innovation",
    5: "Purpose & Integrity",
    6: "Service & Contribution",
    7: "Legacy & Sustainability"
}

# Grouping helper for dashboard
@st.cache_data
def group_values(values):
    grouped = {i: {"positive": [], "negative": []} for i in range(1, 8)}
    for val in values:
        for v in MIZAN_VALUES_POOL:
            if v["name"] == val:
                grouped[v["level"]][v["type"]].append(val)
    return grouped

# Calculate Entropy (values)
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

# Dashboard
def draw_2d_mizan_dashboard(selected_values=None, mode="employee", selected_department=None):
    st.subheader("Mizan Value Distribution")
    if mode == "employee":
        data = selected_values or []
    else:
        df = pd.DataFrame(st.session_state["employee_responses"])
        if selected_department:
            df = df[df["department"] == selected_department]
        data = df["current_experience"].explode().tolist() + df["desired_values"].explode().tolist()
    grouped = group_values(data)

    fig = go.Figure()
    for level, level_name in MIZAN_LEVELS.items():
        pos_count = len(grouped[level]["positive"])
        neg_count = len(grouped[level]["negative"])

        fig.add_trace(go.Bar(
            x=[pos_count],
            y=[level_name],
            orientation="h",
            name="Positive",
            marker_color="green",
            hovertext=grouped[level]["positive"]
        ))

        fig.add_trace(go.Bar(
            x=[-neg_count],
            y=[level_name],
            orientation="h",
            name="Limiting",
            marker_color="red",
            hovertext=grouped[level]["negative"]
        ))
        
        fig.add_trace(go.Bar(
            x=[-neg_count],
            y=[MIZAN_LEVELS[level]],
            orientation="h",
            name="Limiting",
            marker_color="red",
            hovertext=grouped[level]["negative"]
        ))

    fig.update_layout(
        barmode="relative",
        height=500,
        title=f"Mizan 7-Level Dashboard - {selected_department if selected_department else 'Your Report'}",
        xaxis_title="Count",
        yaxis_title="Levels"
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Sidebar Navigation ---
st.sidebar.image("logo.png", width=150)
page = st.sidebar.radio("Navigation", ["Company", "Employee"])

# --- Company Page ---
if page == "Company":
    st.image("logo.png", width=100)
    st.markdown("<h1 style='color:#284B63;'>Mizan Culture Intelligence Platform</h1>", unsafe_allow_html=True)
    st.markdown("<hr style='border:1px solid #ccc;'>", unsafe_allow_html=True)
    st.title("Mizan Company Setup & Insights")

    st.markdown("### 1. Company Info")
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            company_name = st.text_input("Company Name")
            company_vision = st.text_area("Vision")
            company_strategy = st.text_area("Strategy")
        with col2:
            company_mission = st.text_area("Mission")
            company_values = st.text_area("Core Values (comma-separated)")

    if st.button("Save Company Info"):
        st.session_state["company_info"] = {
            "name": company_name,
            "vision": company_vision,
            "mission": company_mission,
            "strategy": company_strategy,
            "values": [v.strip() for v in company_values.split(",") if v.strip()]
        }
        st.success("Company info saved.")

    if "company_info" in st.session_state:
        st.header("2. Upload Company Structure")
        structure_file = st.file_uploader("Upload Structure CSV", type="csv")
        if structure_file:
            df = pd.read_csv(structure_file)
            if all(col in df.columns for col in ["Employee Name", "Employee Email", "Employee Department", "Supervisor Name"]):
                st.session_state["company_structure"] = df
                st.dataframe(df)
                st.success("Structure uploaded.")

                st.header("3. Organizational Design Analysis")
                preview = df.head(20).to_csv(index=False)
                prompt = f"""
You are an expert in organizational design. Given:
Company: {company_name}
Vision: {company_vision}
Mission: {company_mission}
Strategy: {company_strategy}
Values: {company_values}

Here is a preview of the company structure:
{preview}

Please:
- Assess alignment of structure with vision/strategy
- Identify structure type
- Recommend design improvements
- Include relevant recommendations rooted in organizational design best practices (e.g., clarity, span of control, role alignment, agility).
Be concise, practical, and format your response clearly.
"""
                response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
                )
                with st.spinner("Generating insights..."):
                    response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    org_insight = response.choices[0].message.content.strip()
                    st.markdown(org_insight)
                    log_ai_insight(org_insight, context="org_design_analysis")
            else:
                st.error("Missing required columns in CSV.")
    
    # --- Post-assessment Analysis ---
    if "employee_responses" in st.session_state:
        company_name = st.session_state["company_info"]["name"]
        filtered_entries = [
            e for e in st.session_state["employee_responses"]
            if isinstance(e, dict)
            and e.get("company") == company_name
            and "department" in e
            and "current_experience" in e
            and "desired_values" in e
            and "personal_values" in e
        ]

        if not filtered_entries:
            st.warning("No valid employee submissions found for this company.")
        else:
            df = pd.DataFrame(filtered_entries)
            
        st.header("4. Organizational Culture Analysis")

        st.subheader("Departmental Insights")
        for dept in df["department"].unique():
            dept_df = df[df["department"] == dept]
            st.subheader(f"Department: {dept}")
            
            current = dept_df["current_experience"].explode().tolist()
            desired = dept_df["desired_values"].explode().tolist()
            personal = dept_df["personal_values"].explode().tolist()
            
            dept_entropy = calculate_entropy(current + desired)
            st.markdown(f"**Department Entropy Score:** `{dept_entropy:.1f}%`")
            
            prompt = f"""
You are an AI trained on Mizan's 7-level framework, it's levels, the values and their definistions in each level and the ethical principles linked to each level.

Department: {dept}
Responses: {len(dept_df)}
Current: {current}
Desired: {desired}
Personal: {personal}

Please:
- Count and categorize values at each Mizan level
- Compare current vs desired values
- Detect limiting vs positive values
- Estimate cultural entropy (% limiting values)
- Assess alignment with company mission/strategy
- Provide insights and action steps for this department
Use clear, warm engaging language.
"""
            
    with st.spinner(f"Analyzing {dept}..."):
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        dept_insight = response.choices[0].message.content.strip()
        st.markdown(dept_insight)
        log_ai_insight(dept_insight, context=f"dept_{dept}_analysis")        
        
        st.subheader("Organizational Insight")
        all_current = df["current_experience"].explode().tolist()
        all_desired = df["desired_values"].explode().tolist()
        all_personal = df["personal_values"].explode().tolist()

        org_entropy = calculate_entropy(all_current + all_desired)
        st.markdown(f"### Organizational Entropy Score: `{org_entropy:.1f}%`")

        prompt = f"""
You are an AI trained on Mizan's 7-levels framework, it's levels, the values and their definistions in each level and the ethical principles linked to each level. Organization-wide summary:

Company: {company_name}
Total Responses: {len(df)}
Current: {all_current}
Desired: {all_desired}
Personal: {all_personal}

Please generate an org-level summary including:
- Cultural entropy (gap between current and desired)
- Overall level distribution (Mizan framework)
- Alignment with company mission, vision, and strategy
- Key risks or misalignments
- Actionable recommendations

Keep it concise but insightful and use engaging and supportive language.
"""
        with st.spinner("Analyzing org-level insight..."):
            org_culture = response.choices[0].message.content.strip()
            st.markdown(org_culture)
            log_ai_insight(org_culture, context="org_culture_analysis")

        st.subheader("Mizan Dashboard")
        draw_2d_mizan_dashboard(mode="admin")

# --- EMPLOYEE PAGE ---
elif page == "Employee":
    st.image("logo.png", width=100)
    st.markdown("<h1 style='color:#284B63;'>Mizan Culture Intelligence Platform</h1>", unsafe_allow_html=True)
    st.markdown("<hr style='border:1px solid #ccc;'>", unsafe_allow_html=True)
    st.title("Mizan Culture Assessment")

    if "company_info" not in st.session_state or "company_structure" not in st.session_state:
        st.warning("The company has not completed setup. Please try again later.")
    else:
        st.markdown("### Step 1: Your Information")
        with st.container():
            col1, col2 = st.columns(2)
            with col1:
                emp_name = st.text_input("Your Name")
            with col2:
                emp_email = st.text_input("Your Email")

        dept_list = st.session_state["company_structure"]["Employee Department"].unique()
        emp_dept = st.selectbox("Select Your Department", dept_list)

        def get_options():
            return [f"{v['name']}: {v['definition']}" for v in MIZAN_VALUES_POOL]

        def clean(values):
            return [v.split(":")[0].strip() for v in values]

        st.markdown("### Step 2: Your Personal Values")
        st.info("Please select **exactly 7** values that best represent you.")
        personal = st.multiselect("What values define you?", get_options())
        if len(personal) != 7:
            st.warning("You must select exactly 7 values.")
            st.stop()

        st.markdown("### Step 3: Current Culture")
        st.info("Select **7 values** that reflect your experience of the current company culture.")
        current = st.multiselect("How do you experience the culture now?", get_options())
        if len(current) != 7:
            st.warning("You must select exactly 7 values.")
            st.stop()

        st.markdown("### Step 4: Desired Culture")
        st.info("Choose **7 values** you'd like to see more of in the future.")
        desired = st.multiselect("What values should shape the future culture?", get_options())
        if len(desired) != 7:
            st.warning("You must select exactly 7 values.")
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
                "company": st.session_state["company_info"]["name"]
            }

            prompt = f"""
You are an AI trained on Mizan's 7-level values framework, it's levels, the values and their definistions in each level and the ethical principles linked to each level.

Personal: {entry['personal_values']}
Current: {entry['current_experience']}
Desired: {entry['desired_values']}
Engagement: {entry['engagement']}/5
Recognition: {entry['recognition']}/5

Company: {st.session_state['company_info']['name']}
Vision: {st.session_state['company_info']['vision']}
Mission: {st.session_state['company_info']['mission']}
Strategy: {st.session_state['company_info']['strategy']}

Please provide:
- Level distribution and alignment across the 3 sets of values
- Cultural entropy (gap between current and desired values)
- Integrity alignment between employee values and company mission/vision/strategy
- Opportunities for growth and development
- Recognition or engagement mismatch
Keep the tone supportive, insightful, and actionable.
"""
            with st.spinner("Analyzing your results..."):
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}]
                )
                report_text = response.choices[0].message.content.strip()

                log_ai_insight(report_text, context=f"employee_{emp_email}_report")
                entry["insight"] = report_text
                
                if "employee_responses" not in st.session_state:
                    st.session_state["employee_responses"] = []
                st.session_state["employee_responses"].append(entry)

                st.markdown("### Your Personalized Report")
                st.write(report_text)
                
                entropy = calculate_entropy(entry["current_experience"] + entry["desired_values"])

                st.markdown(f"### Cultural Entropy Score: `{entropy:.1f}%`")
                if entropy < 10:
                    st.success("🟢 Low cultural entropy. Strong alignment.")
                elif entropy < 20:
                    st.warning("🟠 Moderate cultural entropy. Some limiting values detected.")
                else:
                    st.error("🔴 High cultural entropy. Cultural friction likely.")

                st.subheader("Your Visual Dashboard")
                draw_2d_mizan_dashboard(selected_values=entry["personal_values"] + entry["current_experience"] + entry["desired_values"], mode="employee")