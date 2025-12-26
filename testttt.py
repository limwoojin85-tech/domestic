import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime

# --- 1. 구글 시트 연결 (새로운 시트 ID 적용) ---
def get_gspread_client():
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

def load_member_sheet():
    client = get_gspread_client()
    # 사용자님이 주신 새로운 회원관리 시트 ID 
    sh = client.open_by_key("18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA")
    return sh.get_worksheet(0) # 첫 번째 탭

# --- 2. 메인 화면 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    t1, t2 = st.tabs(["🔑 로그인", "🛡️ 가입 신청"])
    
    with t1:
        st.subheader("로그인")
        in_id = st.text_input("아이디 (i+번호)").strip()
        in_pw = st.text_input("비밀번호", type="password").strip()
        
        if st.button("로그인 실행", use_container_width=True):
            member_sh = load_member_sheet()
            data = member_sh.get_all_values()
            df = pd.DataFrame(data[1:], columns=[c.strip() for c in data[0]]) # 헤더 공백 제거 [cite: 2025-07-31]
            
            match = df[(df['아이디'] == in_id) & (df['비밀번호'] == in_pw)]
            if not match.empty:
                row = match.iloc[0]
                if row['승인여부'] == 'Y':
                    st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                    st.rerun()
                else: st.warning("⏳ 승인 대기 중입니다. 관리자에게 문의하세요.")
            else: st.error("❌ 아이디/비밀번호를 확인하세요.")

    with t2:
        st.subheader("신규 가입 신청")
        # 직원/중도매인 선택 기능 [cite: 2025-07-31]
        user_type = st.radio("본인의 신분을 선택하세요", ["중도매인", "회사 직원/관계자"])
        
        new_name = st.text_input("성함 또는 상호명")
        
        if user_type == "중도매인":
            jm_num = st.text_input("중도매인 번호 (예: 005)").strip()
            # 중도매인은 번호를 기반으로 아이디/비번 자동 생성 [cite: 2025-07-31]
            final_id = f"i{jm_num.zfill(3)}"
            final_pw = jm_num.zfill(3)
            final_role = "중도매인"
        else:
            final_id = st.text_input("사용할 아이디")
            final_pw = st.text_input("사용할 비밀번호", type="password")
            final_role = st.selectbox("상세 직책", ["회사 관계자", "관리자", "관련종사자"])

        if st.button("가입 신청 완료", use_container_width=True):
            if not final_id or not final_pw or not new_name:
                st.error("모든 정보를 입력해주세요.")
            else:
                member_sh = load_member_sheet()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 시트 헤더 구조: 아이디, 비밀번호, 카카오id, 닉네임, 승인여부, 등급, 신청일시 
                member_sh.append_row([final_id, final_pw, "", new_name, "N", final_role, now])
                st.success(f"✅ 신청 완료! [아이디: {final_id}] 관리자 승인 후 로그인 가능합니다.")

else:
    # --- 로그인 성공 화면 ---
    u = st.session_state.user
    st.sidebar.success(f"{u['id']}님 접속 중")
    st.sidebar.info(f"권한: {u['role']}")
    
    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
    
    st.write(f"### 안녕하세요, {u['role']}님! 인천농산물 플랫폼에 오신 것을 환영합니다.")
