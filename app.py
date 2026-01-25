import streamlit as st
import pandas as pd
from google_play_scraper import Sort, reviews, app
import google.generativeai as genai
import re
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="ProductIQ | Competitor Analysis", page_icon="📈", layout="wide")

# --- SIDEBAR & NAVIGATION ---
with st.sidebar:
    st.header("⚙️ ProductIQ Config")
    
    # NAVIGATION (The Labels You Requested)
    app_mode = st.radio("Select Module", ["Product Health Check", "Head-to-Head Evaluation"])
    
    st.divider()
    
    # API KEY INPUT
    try:
        if "GEMINI_API_KEY" in st.secrets:
            st.success("✅ AI Engine Connected")
            user_api_key = st.secrets["GEMINI_API_KEY"]
        else:
            user_api_key = st.text_input("🔑 Google Gemini API Key", type="password")
    except:
        user_api_key = st.text_input("🔑 Google Gemini API Key", type="password")
    
    st.divider()
    
    # TARGET MARKET (Your Label)
    region_map = {"India": "in", "United States": "us", "United Kingdom": "uk"}
    selected_region = st.selectbox("Target Market", list(region_map.keys()), index=0)
    country_code = region_map[selected_region]
    
    # DATA SAMPLE SIZE (Your Label)
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

# --- AI ENGINE (Self-Healing) ---
def run_ai_loop(prompt, api_key):
    if not api_key: return "⚠️ API Key missing."
    clean_key = api_key.strip()
    genai.configure(api_key=clean_key)
    
    # Exact Models from your list
    model_options = [
        'gemini-2.0-flash',       
        'gemini-2.0-flash-lite-preview-02-05',
        'gemini-2.5-flash',       
        'gemini-pro-latest'      
    ]
    
    errors = []
    for model_name in model_options:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            errors.append(f"{model_name}: {str(e)}")
            time.sleep(0.3)
            continue
    return f"⚠️ Analysis Failed. Debug: {errors}"

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
            with st.spinner("Connecting to App Store..."):
                st.session_state.single_app = None 
                data, err = fetch_app_data(link, country_code)
                if data:
                    st.session_state.single_app = data
                    st.rerun()
                else:
                    st.error(err)

    st.divider()

    if st.session_state.single_app:
        data = st.session_state.single_app
        c1, c2 = st.columns([1, 10])
        with c1: st.image(data['icon'], width=70)
        with c2: st.subheader(data['name'])

        with st.spinner(f"Fetching {review_count} recent reviews..."):
            df = fetch_reviews(data['id'], country_code, review_count)
        
        if df.empty:
            st.warning("No review data available for this audit.")
        else:
            neg_df = df[df['score'] <= 2]
            pos_df = df[df['score'] == 5]
            
            t1, t2, t3 = st.tabs(["📉 Critical Flaws", "❤️ Core Strengths", "📈 Retention Trends"])
            
            # 1. FLAWS
            with t1:
                if not neg_df.empty:
                    if user_api_key:
                        txt = "\n".join(neg_df['content'].head(15).tolist())
                        prompt = f"Conduct a product friction analysis for {data['name']}. List 3 critical flaws causing churn:\n{txt}"
                        
                        with st.spinner("AI is identifying critical flaws..."):
                            st.markdown(run_ai_loop(prompt, user_api_key))
                            
                    st.divider()
                    st.caption("Friction Points Distribution")
                    st.bar_chart(neg_df['content'].apply(categorize_issue).value_counts())
                else: st.info("No critical flaws detected in sample.")

            # 2. STRENGTHS
            with t2:
                if not pos_df.empty and user_api_key:
                    txt = "\n".join(pos_df['content'].head(15).tolist())
                    prompt = f"Identify the 'Value Proposition' of {data['name']} based on these 5-star reviews. What makes users loyal?:\n{txt}"
                    
                    with st.spinner("AI is analyzing core strengths..."):
                        st.markdown(run_ai_loop(prompt, user_api_key))
                else: st.info("No positive data available.")

            # 3. TRENDS
            with t3:
                if not df.empty:
                    try:
                        trend = df.set_index('at').resample('M')['score'].mean()
                        st.line_chart(trend)
                        st.metric("Current CSAT Score", f"{df['score'].mean():.2f} / 5.0")
                    except: st.warning("Insufficient data for trend analysis.")

# ==========================================
# MODE 2: HEAD-TO-HEAD EVALUATION
# ==========================================
elif app_mode == "Head-to-Head Evaluation":
    st.title("⚖️ Head-to-Head Evaluation")
    st.markdown("Compare market leaders to identify the superior product strategy.")

    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Competitor A")
        link_a = st.text_input("Link A")
        
    with col_b:
        st.subheader("Competitor B")
        link_b = st.text_input("Link B")
        
    if st.button("📊 Run Comparison", use_container_width=True):
        if not link_a or not link_b:
            st.error("Input required for both competitors.")
        else:
            with st.spinner("Aggregating market data..."):
                data_a, err_a = fetch_app_data(link_a, country_code)
                data_b, err_b = fetch_app_data(link_b, country_code)
                
                if not data_a or not data_b:
                    st.error(f"Error: {err_a or ''} {err_b or ''}")
                else:
                    df_a = fetch_reviews(data_a['id'], country_code, review_count)
                    df_b = fetch_reviews(data_b['id'], country_code, review_count)
                    
                    # METRICS
                    st.divider()
                    st.subheader("Performance Metrics")
                    
                    h1, h2, h3 = st.columns([1, 0.2, 1])
                    with h1: 
                        st.image(data_a['icon'], width=80)
                        st.markdown(f"**{data_a['name']}**")
                    with h2:
                        st.markdown("### VS")
                    with h3: 
                        st.image(data_b['icon'], width=80)
                        st.markdown(f"**{data_b['name']}**")
                    
                    avg_a = df_a['score'].mean() if not df_a.empty else 0
                    avg_b = df_b['score'].mean() if not df_b.empty else 0
                    
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        st.metric("CSAT Score", f"{avg_a:.2f}", delta=f"{avg_a - avg_b:.2f}")
                    with col_m2:
                        st.metric("CSAT Score", f"{avg_b:.2f}", delta=f"{avg_b - avg_a:.2f}")

                    # AI VERDICT
                    if user_api_key and not df_a.empty and not df_b.empty:
                        st.divider()
                        st.subheader("🧠 Strategic Verdict")
                        
                        txt_a = "\n".join(df_a.sample(min(20, len(df_a)))['content'].tolist())
                        txt_b = "\n".join(df_b.sample(min(20, len(df_b)))['content'].tolist())
                        
                        prompt = f"""
                        Act as a Senior Product Consultant. Compare these two apps.
                        
                        App A ({data_a['name']}): {txt_a}
                        App B ({data_b['name']}): {txt_b}
                        
                        Deliverable:
                        1. **Stability Winner**: Which is less buggy?
                        2. **Feature Winner**: Which delivers better value?
                        3. **Final Recommendation**: Which product is winning the market and why?
                        """
                        
                        with st.spinner("AI is synthesizing strategic verdict..."):
                            st.info(run_ai_loop(prompt, user_api_key))
                            
                    # FRICTION ANALYSIS
                    st.divider()
                    st.subheader("📉 Friction Analysis")
                    
                    w_col1, w_col2 = st.columns(2)
                    with w_col1:
                        st.caption(f"{data_a['name']} Issues")
                        if not df_a.empty:
                            neg_a = df_a[df_a['score'] <= 2]
                            if not neg_a.empty:
                                st.bar_chart(neg_a['content'].apply(categorize_issue).value_counts())
                            
                    with w_col2:
                        st.caption(f"{data_b['name']} Issues")
                        if not df_b.empty:
                            neg_b = df_b[df_b['score'] <= 2]
                            if not neg_b.empty:
                                st.bar_chart(neg_b['content'].apply(categorize_issue).value_counts())