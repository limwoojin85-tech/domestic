import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import traceback
from datetime import datetime

# --- 1. 구글 시트 연결 ---
def get_gspread_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = {
            "type": st.secrets["gcp_service_account"]["type"],
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            "private_key": st.secrets["gcp_service_account"]["private_key"].replace("\\n", "\n"),
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
            "token_uri": st.secrets["gcp_service_account"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
        }
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception:
        st.error("🔥 구글 인증 설정 오류")
        st.code(traceback.format_exc())
        return None

def load_all_sheets():
    client = get_gspread_client()
    if not client: return None, None
    sh = client.open_by_key(st.secrets["spreadsheet_id"])
    return sh.get_worksheet(0), sh.get_worksheet(1)

# --- 2. 카카오 인증 ---
KAKAO_KEY = st.secrets["kakao"]["rest_api_key"]
REDIRECT_URI = st.secrets["kakao"]["redirect_uri"].strip()

def get_kakao_login_url():
    return f"https://kauth.kakao.com/oauth/authorize?client_id={KAKAO_KEY}&redirect_uri={REDIRECT_URI}&response_type=code"

def get_kakao_user_info(code):
    try:
        token_url = "https://kauth.kakao.com/oauth/token"
        data = {"grant_type": "authorization_code", "client_id": KAKAO_KEY, "redirect_uri": REDIRECT_URI, "code": code}
        token_res = requests.post(token_url, data=data).json()
        user_url = "https://kapi.kakao.com/v2/user/me"
        user_res = requests.get(user_url, headers={"Authorization": f"Bearer {token_res['access_token']}"}).json()
        return str(user_res.get("id")), user_res.get("properties", {}).get("nickname")
    except:
        return None, None

# --- 3. 메인 로직 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")
query_params = st.query_params
auth_code = query_params.get("code")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    t1, t2 = st.tabs(["🔑 로그인", "🛡️ 가입 신청"])
    
    with t1:
        in_id = st.text_input("아이디 (i+번호)").strip()
        in_pw = st.text_input("비밀번호", type="password").strip()
        if st.button("로그인", use_container_width=True):
            _, auth_sh = load_all_sheets()
            users = pd.DataFrame(auth_sh.get_all_values())
            users.columns = [c.strip() for c in users.iloc[0]] # [에러 해결] 공백 제거
            users = users[1:]
            
            match = users[(users['아이디'] == in_id) & (users['비밀번호'] == in_pw)]
            if not match.empty:
                row = match.iloc[0]
                if row['승인여부'] == 'Y':
                    st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                    st.rerun()
                else: st.warning("⏳ 승인 대기 중입니다.")
            else: st.error("❌ 정보를 확인하세요.")

    with t2:
        st.link_button("카카오로 본인인증 신청", get_kakao_login_url(), use_container_width=True)
        if auth_code:
            kid, knick = get_kakao_user_info(auth_code)
            if kid:
                target = st.text_input("중도매인 번호 (예: 002)")
                if st.button("신청"):
                    _, auth_sh = load_all_sheets()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # 등급 기본값은 '중도매인'으로 저장 [cite: 2025-07-31]
                    auth_sh.append_row([f"i{target.zfill(3)}", target.zfill(3), kid, knick, "N", "중도매인", now])
                    st.success("신청 완료! 관리자 승인을 기다리세요.")
else:
    # --- 로그인 후 등급별 메뉴 ---
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}")
    st.sidebar.info(f"등급: {u['role']}")
    
    # 등급에 따른 메뉴 필터링 [cite: 2025-07-31]
    menu = ["내역 조회"]
    if u['role'] in ['중도매인', '관리자', '회사 관계자']: menu.append("주문하기")
    if u['role'] == '관리자': menu.append("사용자 관리")
    
    choice = st.sidebar.radio("메뉴", menu)
    
    if choice == "내역 조회":
        st.header(f"📊 {u['num']}번 경락 내역 (2025)")
        dat_sh, _ = load_all_sheets()
        df = pd.DataFrame(dat_sh.get_all_records())
        if '경락일자' in df.columns:
            dates = sorted(df['경락일자'].astype(str).unique(), reverse=True)
            sel_date = st.selectbox("날짜 선택", dates)
            df = df[df['경락일자'].astype(str) == sel_date]
        
        df['코드_str'] = df['정산코드'].astype(str).str.strip()
        my_data = df[df['코드_str'].isin([u['num'], str(int(u['num']))])]
        st.dataframe(my_data, use_container_width=True)
        if not my_data.empty:
            total = pd.to_numeric(my_data['금액'], errors='coerce').sum()
            st.metric("💰 총 낙찰액", f"{total:,.0f} 원")

    elif choice == "주문하기":
        st.header("🛒 중도매인 주문 플랫폼")
        st.write("주문 기능은 카카오톡 채널과 연동 준비 중입니다.")

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
