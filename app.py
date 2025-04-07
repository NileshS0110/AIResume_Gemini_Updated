import streamlit as st
import google.generativeai as genai
import docx2txt
import PyPDF2
import pandas as pd
import base64
import json
from datetime import datetime
from io import BytesIO

# --- Gemini Setup ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("API key missing! Add it to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-pro-latest')

# --- Utility Functions ---
def extract_text(file):
    if file.type == "application/pdf":
        reader = PyPDF2.PdfReader(file)
        return " ".join(page.extract_text() for page in reader.pages if page.extract_text())
    elif file.type.endswith("document"):
        return docx2txt.process(file)
    return file.read().decode()

def analyze_resume(jd, resume_text):
    prompt = f"""
    Analyze this resume against the job description:

    Job Description:
    {jd}

    Resume:
    {resume_text}

    Return a JSON object with the following keys:
    - "score" (0-100)
    - "matches" (list of top 3 skills)
    - "gaps" (list of top 3 missing)
    - "summary" (3 bullet points)
    """
    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()

        # Remove markdown code formatting if any
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()

        result = json.loads(result_text)
        return result
    except Exception as e:
        st.error(f"Resume analysis failed: {e}")
        return None

def generate_email(candidate, jd):
    prompt = f"""
    Write a professional outreach email for this candidate:
    Name: {candidate.get('name', 'Candidate')}
    Score: {candidate.get('score', 'N/A')}/100
    Matches: {', '.join(candidate.get('matches', []))}

    Job: {jd}
    """
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"Email generation failed: {str(e)}"

# --- Streamlit UI ---
st.set_page_config(page_title="RecruitAI Pro", layout="wide")
st.title("🚀 RecruitAI Pro - End-to-End Hiring Assistant")

# --- Step 1: Upload Job Description ---
st.header("📋 Step 1: Upload Job Description")
jd_file = st.file_uploader("Upload JD (PDF or DOCX)", type=["pdf", "docx"], key="jd")
if jd_file:
    jd_text = extract_text(jd_file)
    if 'jd_text' not in st.session_state:
        st.session_state.jd_text = jd_text
    st.text_area("Parsed JD", jd_text[:2000] + "...", height=250)

# --- Step 2: Upload and Analyze Resumes ---
if 'jd_text' in st.session_state:
    st.header("📚 Step 2: Upload Resumes for Batch Analysis")
    resumes = st.file_uploader("Upload multiple resumes", type=["pdf", "docx", "txt"], accept_multiple_files=True)

    if resumes and st.button("Analyze Batch"):
        st.session_state.candidates = []
        with st.spinner("Analyzing resumes..."):
            for resume in resumes:
                resume_text = extract_text(resume)
                result = analyze_resume(st.session_state.jd_text, resume_text)
                if result:
                    result['name'] = resume.name.split('.')[0]
                    result['resume'] = resume_text[:500] + "..."
                    st.session_state.candidates.append(result)

# --- Step 3: Results Dashboard ---
if 'candidates' in st.session_state and st.session_state.candidates:
    st.header("📊 Step 3: Candidate Evaluation Dashboard")

    df = pd.DataFrame(st.session_state.candidates)

    # Only show required columns if present
    required_cols = ['name', 'score', 'matches', 'gaps']
    present_cols = [col for col in required_cols if col in df.columns]

    if present_cols:
        st.dataframe(df[present_cols].sort_values('score', ascending=False), 
                     use_container_width=True,
                     column_config={
                         "score": st.column_config.ProgressColumn(
                             "Match Score", help="JD match percentage", format="%d%%",
                             min_value=0, max_value=100)
                     })

    selected = st.selectbox("Select candidate to view details", df['name'])
    candidate = next(c for c in st.session_state.candidates if c['name'] == selected)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"{selected} - {candidate.get('score', 0)} / 100")
        st.markdown("**✅ Matches:** " + ", ".join(candidate.get('matches', [])))
        st.markdown("**⚠️ Gaps:** " + ", ".join(candidate.get('gaps', [])))
        st.text_area("Summary", candidate.get('summary', 'N/A'), height=150)

    with col2:
        st.subheader("✉️ Outreach Tools")
        if st.button("Generate Email Template"):
            st.session_state.email = generate_email(candidate, st.session_state.jd_text)
        if 'email' in st.session_state:
            st.text_area("Email Draft", st.session_state.email, height=200)
            st.download_button("Download Email", st.session_state.email, file_name=f"email_{selected}.txt")

# --- Step 4: Export Results ---
if 'candidates' in st.session_state:
    st.header("📤 Step 4: Export Results")

    df = pd.DataFrame(st.session_state.candidates)


    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False, engine='openpyxl')
    excel_buffer.seek(0)

    st.download_button(
        label="📥 Export to Excel",
        data=excel_buffer,
        file_name=f"candidate_report_{datetime.now().date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.subheader("🔗 ATS Integration (Mockup)")
    st.selectbox("Choose ATS", ["Greenhouse", "Lever", "Workday"])
    st.button("Sync Selected Candidates")

# --- Debug ---
with st.expander("🧪 Debug Info"):
    st.write(st.session_state)
