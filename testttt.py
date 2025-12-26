import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback  # 상세 로그 출력을 위해 추가

# --- 에러를 화면에 직접 표시하는 함수 ---
def show_error_details():
    st.error("❗ 앱 실행 중 내부 오류가 발생했습니다.")
    with st.expander("개발자용 상세 로그 보기 (클릭)"):
        st.code(traceback.format_exc())

# --- 구글 API 인증 ---
def get_gspread_client():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("❌ Streamlit Secrets 설정이 되어있지 않습니다. (gcp_service_account 누락)")
            return None
            
        creds_info = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Secrets의 private_key에서 줄바꿈(\n)이 정상인지 체크하는 로직 포함
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception:
        show_error_details()
        return None

def load_data_from_google():
    try:
        client = get_gspread_client()
        if client is None: return None
        
        if "spreadsheet_id" not in st.secrets:
            st.error("❌ spreadsheet_id가 Secrets에 설정되어 있지 않습니다.")
            return None
            
        sh = client.open_by_key(st.secrets["spreadsheet_id"])
        data = sh.sheet1.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        show_error_details()
        return None

# --- 메인 화면 로직 ---
try:
    st.set_page_config(page_title="인천농산물 경락조회", layout="centered")

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🍎 중도매인 로그인")
        input_id = st.text_input("정산코드 (ID)").strip()
        input_pw = st.text_input("비밀번호 (PW)", type="password").strip()
        
        if st.button("로그인", use_container_width=True):
            if input_id and input_pw == input_id: 
                st.session_state.logged_in = True
                st.session_state.user_id = input_id
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 틀립니다.")
    else:
        user_id = st.session_state.user_id
        st.title(f"📄 {user_id}번 경락 내역서")
        
        df = load_data_from_google()
        if df is not None:
            # 002 vs 2 매칭 로직
            df['정산코드_str'] = df['정산코드'].astype(str).str.strip()
            target_id = str(user_id).strip()
            try: target_id_int = str(int(target_id))
            except: target_id_int = target_id

            my_data = df[(df['정산코드_str'] == target_id) | (df['정산코드_str'] == target_id_int)]
            
            if not my_data.empty:
                st.success(f"오늘 총 {len(my_data)}건의 내역이 있습니다.")
                st.dataframe(my_data[['품목명', '출하자', '중량', '등급', '과수', '단가', '수량', '금액']], use_container_width=True)
            else:
                st.warning("오늘 낙찰된 내역이 없습니다.")
                
        if st.button("로그아웃"):
            st.session_state.logged_in = False
            st.rerun()

except Exception:
    show_error_details()
