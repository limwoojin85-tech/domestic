import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 구글 API 연결 ---
def get_gspread_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

def load_auth_data():
    """Sheet2에서 계정 정보를 가져오고 에러를 상세히 보고함"""
    try:
        client = get_gspread_client()
        sh = client.open_by_key(st.secrets["spreadsheet_id"])
        
        # 탭 이름이 정확히 'Sheet2'인지 확인 (대소문자 구분 주의)
        try:
            user_sheet = sh.worksheet("Sheet2")
        except:
            st.error("❌ 구글 시트에 'Sheet2' 탭을 찾을 수 없습니다. 탭 이름을 확인해 주세요.")
            return None
            
        return pd.DataFrame(user_sheet.get_all_records())
    except Exception as e:
        st.error(f"❌ 계정 정보 로드 오류: {e}")
        return None

# --- 메인 화면 ---
st.set_page_config(page_title="인천농산물 경락조회", layout="centered")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🍎 중도매인 로그인")
    st.info("💡 아이디는 i+번호 형식입니다. (예: i002)")
    
    input_id = st.text_input("아이디 (ID)", placeholder="예: i002").strip()
    input_pw = st.text_input("비밀번호 (PW)", type="password").strip()
    
    if st.button("로그인", use_container_width=True):
        users_df = load_auth_data()
        
        if users_df is not None:
            # 시트의 데이터를 모두 문자열로 변환하고 양쪽 공백 제거
            users_df['아이디'] = users_df['아이디'].astype(str).str.strip()
            users_df['비밀번호'] = users_df['비밀번호'].astype(str).str.strip()
            
            # 매칭 확인
            match = users_df[(users_df['아이디'] == input_id) & 
                             (users_df['비밀번호'] == input_pw)]
            
            if not match.empty:
                st.session_state.logged_in = True
                # 'i002'에서 '002'만 추출하여 저장
                st.session_state.user_id = input_id.replace('i', '') 
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 틀립니다.")
else:
    # --- 조회 화면 (기존과 동일하되 시트 974건 필터링 유지) ---
    st.title(f"📄 {st.session_state.user_id}번 경락 내역")
    # ... (데이터 필터링 로직) ...
    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False
        st.rerun()
