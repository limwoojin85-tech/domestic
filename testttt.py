import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Streamlit Secrets에서 보안 정보 로드 ---
def get_gspread_client():
    # 설정창에 입력한 [gcp_service_account]를 가져옴
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

def load_data_from_google():
    try:
        client = get_gspread_client()
        # 설정창에 입력한 spreadsheet_id를 가져옴
        sh = client.open_by_key(st.secrets["spreadsheet_id"])
        data = sh.sheet1.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"⚠️ 데이터 로드 실패: {e}")
        return None

# --- UI 및 필터링 로직 ---
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
            st.error("❌ 아이디 또는 비밀번호가 틀립니다.")
else:
    user_id = st.session_state.user_id
    st.title(f"📄 {user_id}번 경락 내역서")
    
    df = load_data_from_google()
    if df is not None:
        # '002'와 '2'를 모두 인식하도록 처리
        df['정산코드_str'] = df['정산코드'].astype(str).str.strip()
        target_id = str(user_id).strip()
        try: target_id_int = str(int(target_id))
        except: target_id_int = target_id

        my_data = df[(df['정산코드_str'] == target_id) | (df['정산코드_str'] == target_id_int)]
        
        if not my_data.empty:
            st.success(f"오늘 총 {len(my_data)}건의 내역이 있습니다.")
            st.dataframe(my_data[['품목명', '출하자', '중량', '등급', '과수', '단가', '수량', '금액']], use_container_width=True)
            total = pd.to_numeric(my_data['금액']).sum()
            st.subheader(f"💰 총 낙찰 금액: {total:,.0f} 원")
        else:
            st.warning("오늘 낙찰된 내역이 없습니다.")
            
    if st.button("로그아웃"):
        st.session_state.logged_in = False
        st.rerun()
