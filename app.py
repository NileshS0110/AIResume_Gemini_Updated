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
    
    Job Requirements:
    {jd}
    
    Resume:
    {resume_text}
    
    Return as JSON with:
    - "score" (0-100)
    - "matches" (top 3 skills)
    - "gaps" (top 3 missing)
    - "summary" (3 bullet points)
    """
    try:
        response = model.generate_content(prompt)
        return eval(response.text)  # Convert JSON string to dict
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        return None

def generate_email(candidate, jd):
    prompt = f"""
    Write a professional outreach email for this candidate:
    Name: {candidate.get('name', 'Candidate')}
    Score: {candidate['score']}/100
    Matches: {', '.join(candidate['matches']}
    
    Job: {jd}
    """
    return model.generate_content(prompt).text

# --- UI Flow ---
st.set_page_config(layout="wide", page_title="RecruitAI Pro")
st.title("🚀 RecruitAI Pro - End-to-End Hiring Assistant")

# --- Step 1: Upload JD ---
with st.expander("📋 1. Upload Job Description", expanded=True):
    jd_file = st.file_uploader("Upload JD (PDF/DOCX)", type=["pdf","docx"], key="jd")
    if jd_file:
        jd_text = extract_text(jd_file)
        st.session_state.jd = jd_text
        with st.expander("View Parsed JD"):
            st.write(jd_text[:2000] + "...")

# --- Step 2: Batch Resume Processing ---
if 'jd' in st.session_state:
    with st.expander("📚 2. Upload Resumes (Batch)", expanded=True):
        resumes = st.file_uploader("Upload Multiple Resumes", 
                                 type=["pdf","docx","txt"], 
                                 accept_multiple_files=True)
        
        if resumes and st.button("Analyze Batch"):
            st.session_state.candidates = []
            with st.spinner(f"Processing {len(resumes)} resumes..."):
                for i, resume in enumerate(resumes):
                    with st.status(f"Analyzing {resume.name}..."):
                        text = extract_text(resume)
                        analysis = analyze_resume(st.session_state.jd, text)
                        if analysis:
                            analysis['name'] = resume.name.split('.')[0]
                            analysis['resume'] = text[:500] + "..."
                            st.session_state.candidates.append(analysis)
                            st.json(analysis)

# --- Step 3: Results Dashboard ---
if 'candidates' in st.session_state:
    st.divider()
    st.subheader("📊 3. Candidate Evaluation Dashboard")
    
    # Convert to DataFrame
    df = pd.DataFrame(st.session_state.candidates)
    df = df[['name','score','matches','gaps']]
    
    # Interactive table
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
    
    # Candidate drill-down
    selected = st.selectbox("View details", df['name'])
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
if 'candidates' in st.session_state:
    st.divider()
    with st.expander("📤 4. Export Results"):
        # Excel Export
        excel = df.to_excel(index=False)
        b64 = base64.b64encode(excel).decode()
        st.download_button(
            label="📥 Export to Excel",
            data=excel,
            file_name=f"candidate_report_{datetime.now().date()}.xlsx",
            mime="application/vnd.ms-excel"
        )
        
        # ATS Integration Placeholder
        st.markdown("### 🔗 ATS Integration")
        st.selectbox("Select ATS", ["Greenhouse", "Lever", "Workday"])
        st.button("Sync Selected Candidates")

# --- Debug Section ---
with st.expander("Debug"):
    st.write(st.session_state)
