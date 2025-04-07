import streamlit as st
import google.generativeai as genai
import docx2txt
import PyPDF2
import pandas as pd
import base64
from datetime import datetime
import re

# --- Gemini Setup ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("API key missing! Add to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-pro-latest')

# --- Utility Functions ---
def extract_text(file):
    if file.type == "application/pdf":
        reader = PyPDF2.PdfReader(file)
        return " ".join(page.extract_text() for page in reader.pages if page.extract_text())
    elif file.type.endswith('document'):
        return docx2txt.process(file)
    return file.read().decode()

def analyze_resume(jd, resume_text):
    prompt = f"""
    Analyze this resume against the job description:

    Job Description:
    {jd}

    Resume:
    {resume_text}

    Return a JSON with keys:
    - "score" (0-100)
    - "matches" (list of top 3 skills)
    - "gaps" (list of top 3 missing)
    - "summary" (3 bullet points)
    """
    try:
        response = model.generate_content(prompt)
        return eval(response.text)
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        return None

def generate_email(candidate, jd):
    prompt = f"""
    Write a professional outreach email for this candidate:
    Name: {candidate.get('name', 'Candidate')}
    Score: {candidate['score']}/100
    Matches: {', '.join(candidate['matches'])}

    Job: {jd}
    """
    return model.generate_content(prompt).text

# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="RecruitAI Pro")
st.title("🚀 RecruitAI Pro - End-to-End Hiring Assistant")

# --- Step 1: Upload Job Description ---
st.subheader("📋 1. Upload Job Description")
jd_file = st.file_uploader("Upload JD (PDF/DOCX)", type=["pdf", "docx"], key="jd")
if jd_file:
    jd_text = extract_text(jd_file)
    if 'jd' not in st.session_state:
        st.session_state.jd = jd_text

    st.text_area("Parsed JD", jd_text[:2000] + "...", height=200)

# --- Step 2: Resume Upload & Analysis ---
if 'jd' in st.session_state:
    st.subheader("📚 2. Upload Resumes for Analysis")
    resumes = st.file_uploader("Upload Multiple Resumes", type=["pdf", "docx", "txt"], accept_multiple_files=True)

    if resumes and st.button("Analyze Resumes"):
        st.session_state.candidates = []
        with st.spinner(f"Analyzing {len(resumes)} resumes..."):
            for resume in resumes:
                text = extract_text(resume)
                analysis = analyze_resume(st.session_state.jd, text)

                if analysis and isinstance(analysis, dict):
                    candidate_data = {
                        'name': resume.name.split('.')[0],
                        'score': analysis.get('score', 0),
                        'matches': analysis.get('matches', []),
                        'gaps': analysis.get('gaps', []),
                        'summary': analysis.get('summary', ''),
                        'resume': text[:500] + "..."
                    }
                    st.session_state.candidates.append(candidate_data)
                    st.success(f"{resume.name} analyzed.")
                else:
                    st.warning(f"Invalid response for {resume.name}")
                    st.json(analysis)

# --- Step 3: Results Dashboard ---
if 'candidates' in st.session_state and st.session_state.candidates:
    st.subheader("📊 3. Candidate Evaluation Dashboard")

    df = pd.DataFrame(st.session_state.candidates)
    try:
        df = df[['name', 'score', 'matches', 'gaps']]
        st.dataframe(df.sort_values('score', ascending=False),
                     use_container_width=True,
                     column_config={
                         "score": st.column_config.ProgressColumn(
                             "Match Score",
                             help="JD match percentage",
                             format="%d%%",
                             min_value=0,
                             max_value=100,
                         )
                     })
    except KeyError as e:
        st.error(f"Dataframe column error: {e}")
        st.write(df)

    selected = st.selectbox("🔍 View Candidate Details", df['name'])
    candidate = next(c for c in st.session_state.candidates if c['name'] == selected)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### {selected} ({candidate['score']}/100)")
        st.markdown("**✅ Matches:** " + ", ".join(candidate['matches']))
        st.markdown("**⚠️ Gaps:** " + ", ".join(candidate['gaps']))
        st.text_area("Summary", candidate['summary'], height=150)

    with col2:
        st.markdown("### ✉️ Outreach Tools")
        if st.button("Generate Email Template"):
            st.session_state.email = generate_email(candidate, st.session_state.jd)
        if 'email' in st.session_state:
            st.text_area("Email Draft", st.session_state.email, height=200)
            st.download_button("Download Email", st.session_state.email, file_name=f"email_{selected}.txt")

# --- Step 4: Export ---
if 'candidates' in st.session_state and st.session_state.candidates:
    st.subheader("📤 4. Export Results")

    df_export = pd.DataFrame(st.session_state.candidates)
    excel = df_export.to_excel(index=False)
    b64 = base64.b64encode(excel).decode()

    st.download_button(
        label="📥 Export to Excel",
        data=excel,
        file_name=f"candidate_report_{datetime.now().date()}.xlsx",
        mime="application/vnd.ms-excel"
    )

    st.markdown("### 🔗 ATS Integration (Coming Soon)")
    st.selectbox("Select ATS", ["Greenhouse", "Lever", "Workday"])
    st.button("Sync Selected Candidates")

# --- Debugging ---
with st.expander("🔧 Debug (Dev Only)"):
    st.write(st.session_state)
