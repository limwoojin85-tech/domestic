import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- [중요] 중도매인 계정 직접 정의 (여기에 계속 추가 가능) ---
# 형식: {"아이디": "비밀번호"}
USER_DATABASE = {
    "i002": "1234",
    "i003": "i003",
    "i254": "254",
    # 90명분을 이런 식으로 아래에 쭉 나열하면 시트 오류에서 완전히 해방됩니다.
}

# 90명분 자동 생성 (아이디와 비번을 동일하게 설정하는 예시)
for i in range(1, 401):
    id_str = f"i{str(i).zfill(3)}"
    if id_str not in USER_DATABASE:
        USER_DATABASE[id_str] = str(i).zfill(3) # 비번은 숫자 3자리

# --- 구글 API (데이터 조회용) ---
def get_data():
    try:
        creds_info = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        sh = client.open_by_key(st.secrets["spreadsheet_id"])
        # 첫 번째 시트(경락데이터)만 가져옴
        return pd.DataFrame(sh.sheet1.get_all_records())
    except Exception as e:
        st.error(f"데이터 조회 오류: {e}")
        return None

# --- UI 설정 ---
st.set_page_config(page_title="인천농산물 경락시스템", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🍎 중도매인 로그인 (내부인증)")
    input_id = st.text_input("아이디 (ID)").strip()
    input_pw = st.text_input("비밀번호 (PW)", type="password").strip()
    
    if st.button("로그인", use_container_width=True):
        # 시트 조회 없이 코드 내부의 USER_DATABASE에서 즉시 확인
        if input_id in USER_DATABASE and USER_DATABASE[input_id] == input_pw:
            st.session_state.logged_in = True
            st.session_state.user_id = input_id.replace('i', '')
            st.rerun()
        else:
            st.error("❌ 아이디 또는 비밀번호가 틀립니다.")
else:
    st.sidebar.title(f"👤 {st.session_state.user_id}번님")
    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False
        st.rerun()

    st.title(f"📄 {st.session_state.user_id}번 경락 내역")
    df = get_data()
    
    if df is not None:
        df['정산코드_str'] = df['정산코드'].astype(str).str.strip()
        target = str(st.session_state.user_id)
        try: target_int = str(int(target))
        except: target_int = target
        
        my_data = df[(df['정산코드_str'] == target) | (df['정산코드_str'] == target_int)]
        
        if not my_data.empty:
            st.success(f"오늘 총 {len(my_data)}건의 내역이 확인되었습니다.")
            st.dataframe(my_data[['품목명', '출하자', '중량', '등급', '단가', '수량', '금액']], use_container_width=True)
            total = pd.to_numeric(my_data['금액'], errors='coerce').sum()
            st.subheader(f"💰 총 낙찰 금액: {total:,.0f} 원")
        else:
            st.warning("오늘 낙찰된 내역이 없습니다.")
