import streamlit as st
import pandas as pd
from google_play_scraper import Sort, reviews, app
import google.generativeai as genai
import re
import time
import posthog

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="ProductIQ | Login", page_icon="🔐", layout="centered")

# --- 1. LOAD SYSTEM API KEY ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        SYSTEM_API_KEY = st.secrets["GEMINI_API_KEY"]
    else:
        st.error("🚨 Admin Alert: GEMINI_API_KEY is missing.")
        st.stop()
except:
    st.error("🚨 Admin Alert: Secrets file not found.")
    st.stop()

# --- 2. ANALYTICS (USER TRACKING) ---
# CHANGE THIS IMPORT
from posthog import Posthog  # <--- Notice the capital 'P'

# ... (keep your other imports like pandas, genai, etc.)

# --- 2. ANALYTICS SETUP (New Client Method) ---
if "POSTHOG_API_KEY" in st.secrets:
    # Create a dedicated client connection
    ph_client = Posthog(
        project_api_key=st.secrets["POSTHOG_API_KEY"],
        host="https://us.i.posthog.com"
    )
else:
    ph_client = None
# --- IMPROVED ANALYTICS FUNCTION ---
def track_event(event_name, properties={}):
    """Robust Logging with Client Check"""
    try:
        # Only try to track if we have a valid client
        if ph_client:
            user_id = st.session_state.get("user_email", "anonymous_visitor")
            
            if user_id != "anonymous_visitor":
                ph_client.identify(user_id)  # Works on the client instance!
            
            ph_client.capture(user_id, event_name, properties)
            # ph_client.flush() is automatic usually, but strictly speaking rarely needed here
            
            # VISUAL SUCCESS
            st.success(f"✅ Data sent: {event_name}")
            time.sleep(1) # Short pause to see it
            
    except Exception as e:
        # If it fails, print why but DON'T crash the app
        st.warning(f"⚠️ Analytics skipped: {e}")
# --- 3. LOGIN GATEKEEPER ---
if "user_email" not in st.session_state:
    # --- LOGIN SCREEN UI ---
    st.title("🔐 ProductIQ Access")
    st.markdown("Enter your professional email to access the Competitor Intelligence Suite.")
    
    with st.container(border=True):
        email_input = st.text_input("Work Email Address", placeholder="name@company.com")
        
        if st.button("🚀 Enter Dashboard", use_container_width=True):
            if "@" in email_input and "." in email_input:
                st.session_state.user_email = email_input
                track_event("user_login", {"email": email_input})
                st.rerun()
            else:
                st.error("Please enter a valid email address.")
    
    st.divider()
    st.caption("🔒 Secure Access | Powered by Gemini AI")
    st.stop()  # STOPS THE REST OF THE APP FROM LOADING

# --- MAIN APP (ONLY RUNS AFTER LOGIN) ---
# Switch layout to wide for the dashboard
st.empty() # Clear previous elements

# --- SIDEBAR & NAVIGATION ---
with st.sidebar:
    st.header(f"👤 {st.session_state.user_email}")
    st.caption("Active Session")
    if st.button("Log Out"):
        st.session_state.pop("user_email")
        st.rerun()
        
    st.divider()
    
    st.header("⚙️ ProductIQ Config")
    app_mode = st.radio("Select Module", ["Product Health Check", "Head-to-Head Evaluation"])
    st.divider()
    
    region_map = {"India": "in", "United States": "us", "United Kingdom": "uk"}
    selected_region = st.selectbox("Target Market", list(region_map.keys()), index=0)
    country_code = region_map[selected_region]
    
    review_count = st.slider("Data Sample Size", 50, 1000, 200)

# --- HELPER FUNCTIONS ---
def extract_id_from_url(text):
    match = re.search(r'id=([a-zA-Z0-9_.]+)', text)
    if match: return match.group(1)
    return None

def categorize_issue(text):
    text = str(text).lower()
    if any(k in text for k in ['price', 'cost', 'expensive', 'money']): return 'Pricing Strategy'
    if any(k in text for k in ['crash', 'bug', 'lag', 'slow', 'error']): return 'Technical Stability'
    if any(k in text for k in ['support', 'service', 'rude', 'reply']): return 'Customer Service'
    if any(k in text for k in ['ad', 'ads', 'advert']): return 'Monetization Aggression'
    return 'Other'

# --- AI ENGINE ---
def run_ai_loop(prompt):
    genai.configure(api_key=SYSTEM_API_KEY)
    model_options = ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-pro-latest']
    
    for model_name in model_options:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except:
            time.sleep(0.3)
            continue
    return "⚠️ Analysis Failed."

def fetch_app_data(link, region):
    app_id = extract_id_from_url(link)
    if not app_id: return None, "Invalid Link"
    try:
        d = app(app_id, lang='en', country=region)
        return {'id': app_id, 'name': d['title'], 'icon': d['icon'], 'obj': d}, None
    except:
        return None, "App Not Found in Market"

def fetch_reviews(app_id, region, count):
    try:
        res, _ = reviews(app_id, lang='en', country=region, sort=Sort.NEWEST, count=count)
        df = pd.DataFrame(res)
        if not df.empty:
            if 'at' in df.columns:
                df['at'] = pd.to_datetime(df['at'], errors='coerce')
                df = df.dropna(subset=['at'])
            df['score'] = pd.to_numeric(df['score'], errors='coerce')
        return df
    except:
        return pd.DataFrame()

# ==========================================
# MODE 1: PRODUCT HEALTH CHECK
# ==========================================
if app_mode == "Product Health Check":
    st.title("🏥 Product Health Check")
    st.markdown("Deep dive audit into a single competitor's performance.")
    
    if 'single_app' not in st.session_state: st.session_state.single_app = None

    col1, col2 = st.columns([4, 1])
    with col1:
        link = st.text_input("Competitor Play Store Link", placeholder="https://play.google.com/store/apps/details?id=...")
    with col2:
        st.write("")
        st.write("")
        if st.button("🚀 Audit Product"):
            track_event("audit_clicked", {"link": link, "region": selected_region, "user": st.session_state.user_email})
            with st.spinner("Connecting to App Store..."):
                st.session_state.single_app = None 
                data, err = fetch_app_data(link, country_code)
                if data:
                    st.session_state.single_app = data
                    track_event("audit_success", {"app": data['name'], "user": st.session_state.user_email})
                    st.rerun()
                else:
                    st.error(err)

    st.divider()

    if st.session_state.single_app:
        data = st.session_state.single_app
        c1, c2 = st.columns([1, 10])
        with c1: st.image(data['icon'], width=70)
        with c2: st.subheader(data['name'])

        with st.spinner(f"Fetching reviews..."):
            df = fetch_reviews(data['id'], country_code, review_count)
        
        if df.empty:
            st.warning("No review data available.")
        else:
            neg_df = df[df['score'] <= 2]
            pos_df = df[df['score'] == 5]
            
            t1, t2, t3 = st.tabs(["📉 Critical Flaws", "❤️ Core Strengths", "📈 Retention Trends"])
            
            with t1:
                if not neg_df.empty:
                    txt = "\n".join(neg_df['content'].head(15).tolist())
                    prompt = f"Conduct a product friction analysis for {data['name']}. List 3 critical flaws causing churn:\n{txt}"
                    with st.spinner("AI Identifying Flaws..."):
                        st.markdown(run_ai_loop(prompt))
                    st.bar_chart(neg_df['content'].apply(categorize_issue).value_counts())
                else: st.info("No critical flaws detected.")

            with t2:
                if not pos_df.empty:
                    txt = "\n".join(pos_df['content'].head(15).tolist())
                    prompt = f"Identify the 'Value Proposition' of {data['name']}. Why are users loyal?:\n{txt}"
                    with st.spinner("AI Analyzing Value..."):
                        st.markdown(run_ai_loop(prompt))

            with t3:
                if not df.empty:
                    try:
                        trend = df.set_index('at').resample('M')['score'].mean()
                        st.line_chart(trend)
                    except: pass

# ==========================================
# MODE 2: HEAD-TO-HEAD
# ==========================================
elif app_mode == "Head-to-Head Evaluation":
    st.title("⚖️ Head-to-Head Evaluation")
    
    col_a, col_b = st.columns(2)
    with col_a: link_a = st.text_input("Competitor A Link")
    with col_b: link_b = st.text_input("Competitor B Link")
        
    if st.button("📊 Run Comparison", use_container_width=True):
        track_event("battle_clicked", {"user": st.session_state.user_email})
        
        if link_a and link_b:
            with st.spinner("Analyzing Market Data..."):
                data_a, _ = fetch_app_data(link_a, country_code)
                data_b, _ = fetch_app_data(link_b, country_code)
                
                if data_a and data_b:
                    track_event("battle_success", {"app_a": data_a['name'], "app_b": data_b['name'], "user": st.session_state.user_email})
                    
                    df_a = fetch_reviews(data_a['id'], country_code, review_count)
                    df_b = fetch_reviews(data_b['id'], country_code, review_count)
                    
                    st.subheader("Performance Metrics")
                    c1, c2 = st.columns(2)
                    with c1: st.metric(f"{data_a['name']} CSAT", f"{df_a['score'].mean():.2f}")
                    with c2: st.metric(f"{data_b['name']} CSAT", f"{df_b['score'].mean():.2f}")
                    
                    if not df_a.empty and not df_b.empty:
                        st.divider()
                        st.subheader("🧠 Strategic Verdict")
                        txt_a = "\n".join(df_a.sample(min(20, len(df_a)))['content'].tolist())
                        txt_b = "\n".join(df_b.sample(min(20, len(df_b)))['content'].tolist())
                        prompt = f"Compare {data_a['name']} vs {data_b['name']}. Who wins on stability and features? Reviews A: {txt_a} Reviews B: {txt_b}"
                        st.info(run_ai_loop(prompt))