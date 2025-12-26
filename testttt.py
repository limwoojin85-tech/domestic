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
    except:
        st.error("구글 인증 오류")
        return None

def load_all_sheets():
    client = get_gspread_client()
    if not client: return None, None
    sh = client.open_by_key(st.secrets["spreadsheet_id"])
    return sh.get_worksheet(0), sh.get_worksheet(1)

# --- 2. 카카오 로그인 설정 ---
KAKAO_KEY = st.secrets["kakao"]["rest_api_key"]
REDIRECT_URI = st.secrets["kakao"]["redirect_uri"].strip()

def get_kakao_login_url():
    return f"https://kauth.kakao.com/oauth/authorize?client_id={KAKAO_KEY}&redirect_uri={REDIRECT_URI}&response_type=code"

# --- 3. 메인 화면 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    t1, t2 = st.tabs(["🔑 로그인", "🛡️ 가입 신청"])
    
    with t1:
        in_id = st.text_input("아이디 (i+번호)").strip()
        in_pw = st.text_input("비밀번호", type="password").strip()
        if st.button("로그인 실행", use_container_width=True):
            _, auth_sh = load_all_sheets()
            # [핵심 수정] 컬럼명 공백 제거 및 대조 [cite: 2025-07-31]
            all_vals = auth_sh.get_all_values()
            headers = [h.strip() for h in all_vals[0]]
            users = pd.DataFrame(all_vals[1:], columns=headers)
            
            if '승인여부' not in users.columns:
                st.error("❌ 시트(Sheet2) 헤더에 '승인여부' 컬럼이 없습니다. 확인해 주세요.")
            else:
                match = users[(users['아이디'] == in_id) & (users['비밀번호'] == in_pw)]
                if not match.empty:
                    row = match.iloc[0]
                    if row['승인여부'] == 'Y':
                        st.session_state.user = {"id": row['아이디'], "role": row.get('등급', '중도매인'), "num": row['아이디'].replace('i','')}
                        st.rerun()
                    else: st.warning("⏳ 승인 대기 중입니다.")
                else: st.error("❌ 아이디/비번이 틀립니다.")

    with t2:
        st.link_button("카카오로 본인인증 신청", get_kakao_login_url(), use_container_width=True)

else:
    # --- 로그인 성공: 데이터 조회 화면 ---
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}")
    
    menu = ["내역 조회"]
    if u['role'] == '관리자': menu.append("시스템 관리")
    choice = st.sidebar.radio("메뉴", menu)
    
    if choice == "내역 조회":
        st.header(f"📊 {u['num']}번 경락 내역 (2025년 12월)")
        dat_sh, _ = load_all_sheets()
        df = pd.DataFrame(dat_sh.get_all_records())
        
        if not df.empty:
            df['코드_str'] = df['정산코드'].astype(str).str.strip()
            my_data = df[df['코드_str'].isin([u['num'], str(int(u['num']))])]
            st.dataframe(my_data, use_container_width=True)
        else:
            st.warning("현재 조회 가능한 데이터가 없습니다.")

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
