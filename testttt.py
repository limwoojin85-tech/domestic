import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import traceback
from datetime import datetime

# --- 1. 구글 시트 연결 함수 ---
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
        st.error("❌ 구글 인증 오류! Secrets 설정을 확인하세요.")
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

# --- 3. 메인 화면 시작 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    t1, t2 = st.tabs(["🔑 로그인", "🛡️ 신규 가입 신청"])
    
    with t1:
        st.subheader("기존 회원 로그인")
        in_id = st.text_input("아이디 (i+중도매인번호)").strip()
        in_pw = st.text_input("비밀번호", type="password").strip()
        if st.button("로그인", use_container_width=True):
            _, auth_sh = load_all_sheets()
            all_vals = auth_sh.get_all_values()
            headers = [h.strip() for h in all_vals[0]]
            users = pd.DataFrame(all_vals[1:], columns=headers)
            
            match = users[(users['아이디'] == in_id) & (users['비밀번호'] == in_pw)]
            if not match.empty:
                row = match.iloc[0]
                if row['승인여부'] == 'Y':
                    st.session_state.user = {"id": row['아이디'], "role": row.get('등급', '중도매인'), "num": row['아이디'].replace('i','')}
                    st.rerun()
                else: st.warning("⏳ 아직 승인되지 않았습니다. 관리자에게 문의하세요.")
            else: st.error("❌ 아이디 또는 비밀번호가 틀립니다.")

    with t2:
        st.subheader("회원가입 방식 선택")
        choice = st.radio("가입 방식을 선택하세요", ["수동 아이디 생성", "카카오 본인인증 신청"])
        
        if choice == "수동 아이디 생성":
            new_id = st.text_input("희망 아이디 (예: i005)")
            new_pw = st.text_input("희망 비밀번호", type="password")
            new_name = st.text_input("이름(상호)")
            new_role = st.selectbox("가입 등급", ["중도매인", "회사 관계자", "관련종사자"])
            
            if st.button("가입 신청하기"):
                _, auth_sh = load_all_sheets()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                auth_sh.append_row([new_id, new_pw, "", new_name, "N", new_role, now])
                st.success("✅ 신청 완료! 관리자 승인 후 로그인이 가능합니다.")
        
        else:
            st.info("카카오 계정 정보를 사용하여 간편하게 신청합니다.")
            st.link_button("카카오 신청 페이지로 이동", get_kakao_login_url(), use_container_width=True)

else:
    # 로그인 성공 후 화면 (기존과 동일)
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님")
    st.sidebar.info(f"등급: {u['role']}")
    
    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()

    st.header(f"📊 경락 내역 조회 ({u['role']} 권한)")
    # ... (데이터 조회 로직 실행) ...
