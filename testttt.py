import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback

# --- 1. 구글 연결 함수 ---
def get_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

# --- 2. 데이터 시트(Sheet1)와 인증 시트(Sheet2) 로드 ---
def load_all_data():
    client = get_client()
    sh = client.open_by_key(st.secrets["spreadsheet_id"])
    
    # Sheet1: 경락 데이터 (974건 등)
    data_sheet = sh.get_worksheet(0) 
    # Sheet2: 계정 정보
    auth_sheet = sh.get_worksheet(1) 
    
    return data_sheet, auth_sheet

# --- 메인 화면 ---
st.set_page_config(page_title="인천농산물 경락조회시스템", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🍎 중도매인 로그인")
    input_id = st.text_input("아이디 (i+번호, 예: i002)").strip()
    input_pw = st.text_input("비밀번호", type="password").strip()
    
    if st.button("로그인", use_container_width=True):
        try:
            _, auth_sh = load_all_data()
            users = pd.DataFrame(auth_sh.get_all_values())
            users.columns = users.iloc[0]
            users = users[1:]
            
            match = users[(users['아이디'].astype(str).str.strip() == input_id) & 
                          (users['비밀번호'].astype(str).str.strip() == input_pw)]
            
            if not match.empty:
                st.session_state.logged_in = True
                st.session_state.full_id = input_id
                st.session_state.user_num = input_id.replace('i', '') # 순수 숫자 (002)
                st.rerun()
            else:
                st.error("❌ 정보를 확인하세요.")
        except Exception as e:
            st.error(f"오류 발생: {e}")
else:
    # 로그인 후 사이드바
    menu = st.sidebar.radio("메뉴", ["📄 내역 조회", "🔐 비밀번호 변경", "👋 로그아웃"])
    
    if menu == "📄 내역 조회":
        st.header(f"📊 {st.session_state.user_num}번님 경락 내역")
        
        with st.spinner('데이터를 불러오는 중...'):
            try:
                data_sh, _ = load_all_data()
                df = pd.DataFrame(data_sh.get_all_records())
                
                # [필터링 강화] 002와 2를 모두 찾아냄
                df['정산코드_str'] = df['정산코드'].astype(str).str.strip()
                target_num = str(st.session_state.user_num).strip()
                try: target_int = str(int(target_num))
                except: target_int = target_num
                
                # 본인 데이터만 필터링 [cite: 2025-07-31]
                my_data = df[(df['정산코드_str'] == target_num) | (df['정산코드_str'] == target_int)]
                
                if not my_data.empty:
                    st.success(f"오늘 총 {len(my_data)}건의 낙찰 내역이 있습니다.")
                    # 표시할 컬럼 설정
                    cols = ['품목명', '출하자', '중량', '등급', '단가', '수량', '금액']
                    st.dataframe(my_data[[c for c in cols if c in my_data.columns]], use_container_width=True)
                    
                    total = pd.to_numeric(my_data['금액'], errors='coerce').sum()
                    st.metric("💰 총 낙찰 금액", f"{total:,.0f} 원")
                else:
                    st.warning("조회된 내역이 없습니다.")
            except Exception:
                st.error("데이터 로드 중 오류가 발생했습니다.")
                st.code(traceback.format_exc())

    elif menu == "🔐 비밀번호 변경":
        st.header("비밀번호 수정")
        new_pw = st.text_input("새 비밀번호", type="password")
        if st.button("변경 저장"):
            try:
                _, auth_sh = load_all_data()
                cell = auth_sh.find(st.session_state.full_id)
                auth_sh.update_cell(cell.row, 2, new_pw)
                st.success("✅ 성공! 다음 로그인부터 적용됩니다.")
            except:
                st.error("수정 실패")

    elif menu == "👋 로그아웃":
        st.session_state.logged_in = False
        st.rerun()
