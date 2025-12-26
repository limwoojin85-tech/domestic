import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. 구글 연결 (가장 안정적인 방식) ---
def get_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

def get_auth_sheet():
    client = get_client()
    sh = client.open_by_key(st.secrets["spreadsheet_id"])
    # 탭 이름이 'Sheet2'든 '시트2'든 상관없이 두 번째 탭을 가져오도록 설정
    return sh.get_worksheet(1) 

# --- 2. 메인 로직 ---
st.set_page_config(page_title="인천농산물 관리시스템")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🍎 중도매인 로그인")
    input_id = st.text_input("아이디 (i+번호, 예: i002)").strip()
    input_pw = st.text_input("비밀번호", type="password").strip()
    
    if st.button("로그인"):
        auth_sh = get_auth_sheet()
        # 모든 데이터를 '문자열'로 읽어와서 숫자 변환 오류 차단
        users = pd.DataFrame(auth_sh.get_all_values()) 
        users.columns = users.iloc[0] # 첫 줄을 제목으로
        users = users[1:] # 데이터만 남김
        
        # 공백 제거 및 문자열 비교
        match = users[(users['아이디'].astype(str).str.strip() == input_id) & 
                      (users['비밀번호'].astype(str).str.strip() == input_pw)]
        
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.full_id = input_id
            st.session_state.user_id = input_id.replace('i', '')
            st.rerun()
        else:
            st.error("❌ 아이디/비밀번호를 다시 확인하세요.")
else:
    # 로그인 후 메뉴
    menu = st.sidebar.radio("이동", ["경락 내역 조회", "비밀번호 직접 수정", "로그아웃"])
    
    if menu == "경락 내역 조회":
        st.header(f"📊 {st.session_state.user_id}번님 내역")
        # (기본 조회 로직 실행)
        
    elif menu == "비밀번호 직접 수정":
        st.header("🔐 비밀번호 변경")
        st.write("사용자가 직접 수정하면 구글 시트에 즉시 반영됩니다.")
        new_pw = st.text_input("새 비밀번호", type="password")
        if st.button("변경 저장"):
            auth_sh = get_auth_sheet()
            cell = auth_sh.find(st.session_state.full_id)
            auth_sh.update_cell(cell.row, 2, new_pw) # B열(2번) 업데이트
            st.success("✅ 변경 완료! 다음 로그인부터 새 비밀번호를 사용하세요.")
