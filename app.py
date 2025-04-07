import streamlit as st
import google.generativeai as genai
import docx2txt
import PyPDF2
import pandas as pd
from io import BytesIO
from datetime import datetime
import base64
import json

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
    elif file.type.endswith('document') or file.type.endswith('wordprocessingml.document'):
        return docx2txt.process(file)
    return file.read().decode()

def analyze_resume(jd, resume_text):
    prompt = f"""
    Analyze this resume against the job description below.

    JOB DESCRIPTION:
    {jd}

    RESUME:
    {resume_text}

    Respond ONLY in valid JSON with the following structure:
    {{
      "score": integer (0-100),
      "matches": ["skill1", "skill2", "skill3"],
      "gaps": ["gap1", "gap2", "gap3"],
      "summary": ["point1", "point2", "point3"]
    }}
    """
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except json.JSONDecodeError:
        st.error("Gemini returned invalid JSON. Try again or rephrase the JD/resume.")
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
    return None
    
def generate_email(candidate, jd):
    prompt = f"""
    Write a professional recruiter outreach email for:
    Candidate Name: {candidate.get('name', 'Candidate')}
    Score: {candidate['score']}/100
    Matching Skills: {', '.join(candidate['matches'])}
    Job Description: {jd}
    """
    return model.generate_content(prompt).text

# --- UI ---
st.set_page_config(page_title="RecruitAI Pro", layout="wide")
st.title("🚀 RecruitAI Pro – AI-Powered Hiring Assistant")

# --- Upload JD ---
jd_file = st.file_uploader("📋 Upload Job Description (PDF/DOCX)", type=["pdf", "docx"])
if jd_file:
    jd_text = extract_text(jd_file)
    st.session_state['jd'] = jd_text
    st.text_area("📄 Parsed JD", jd_text[:2000] + "...", height=200)

# --- Upload Resumes ---
if 'jd' in st.session_state:
    resumes = st.file_uploader("📚 Upload Resumes (Multiple)", type=["pdf", "docx", "txt"], accept_multiple_files=True)
    
    if resumes and st.button("Analyze Resumes"):
        st.session_state['candidates'] = []
        with st.spinner("🔍 Analyzing resumes..."):
            for resume in resumes:
                resume_text = extract_text(resume)
                result = analyze_resume(st.session_state['jd'], resume_text)
                if result:
                    result['name'] = resume.name.rsplit(".", 1)[0]
                    result['resume'] = resume_text[:500] + "..."
                    st.session_state['candidates'].append(result)
        st.success("✅ Resume analysis complete!")

# --- Dashboard ---
if 'candidates' in st.session_state and st.session_state['candidates']:
    st.subheader("📊 Candidate Evaluation Dashboard")
    
    df = pd.DataFrame(st.session_state['candidates'])
    required_cols = ['name', 'score', 'matches', 'gaps']
    if all(col in df.columns for col in required_cols):
        st.dataframe(
            df[required_cols].sort_values('score', ascending=False),
            use_container_width=True,
            column_config={
                "score": st.column_config.ProgressColumn("Match Score", format="%d%%", min_value=0, max_value=100)
            }
        )

        selected = st.selectbox("📌 Select candidate to view details", df['name'])
        candidate = next(c for c in st.session_state['candidates'] if c['name'] == selected)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"### {selected} ({candidate['score']}/100)")
            st.markdown("**✅ Matches:** " + ", ".join(candidate['matches']))
            st.markdown("**⚠️ Gaps:** " + ", ".join(candidate['gaps']))
            st.text_area("Summary", candidate['summary'], height=150)
        
        with col2:
            st.markdown("### ✉️ Outreach Tools")
            if st.button("Generate Email Template"):
                st.session_state['email'] = generate_email(candidate, st.session_state['jd'])
            if 'email' in st.session_state:
                st.text_area("Email Draft", st.session_state['email'], height=200)
                st.download_button("📥 Download Email", st.session_state['email'], file_name=f"email_{selected}.txt")

# --- Export Section ---
if 'candidates' in st.session_state:
    st.divider()
    with st.expander("📤 Export Candidate Report"):
        export_df = pd.DataFrame(st.session_state['candidates'])
        excel_buffer = BytesIO()
        export_df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        st.download_button(
            label="📥 Export to Excel",
            data=excel_buffer,
            file_name=f"candidate_report_{datetime.now().date()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.selectbox("Select ATS for Sync", ["Greenhouse", "Lever", "Workday"])
        st.button("🚀 Sync Selected Candidates")

# --- Debug ---
with st.expander("🛠 Debug"):
    st.write(st.session_state)
