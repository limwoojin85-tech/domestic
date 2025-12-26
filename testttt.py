import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback

# --- 구글 API 연결 함수 ---
def get_gspread_client():
    try:
        creds_info = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception:
        st.error("구글 인증 오류가 발생했습니다. Secrets 설정을 확인하세요.")
        return None

# --- 데이터 로드 및 업데이트 함수 ---
def get_user_sheet():
    client = get_gspread_client()
    sh = client.open_by_key(st.secrets["spreadsheet_id"])
    return sh.worksheet("Sheet2") # 계정 정보 탭

def load_data():
    client = get_gspread_client()
    sh = client.open_by_key(st.secrets["spreadsheet_id"])
    return pd.DataFrame(sh.sheet1.get_all_records())

# --- 메인 로직 ---
st.set_page_config(page_title="인천농산물 경락시스템", layout="centered")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🍎 중도매인 로그인")
    input_id = st.text_input("정산코드 (ID)").strip()
    input_pw = st.text_input("비밀번호 (PW)", type="password").strip()
    
    if st.button("로그인", use_container_width=True):
        try:
            user_sheet = get_user_sheet()
            users_df = pd.DataFrame(user_sheet.get_all_records())
            
            # 아이디/비번 매칭 (문자열로 통일하여 비교)
            user_found = users_df[(users_df['아이디'].astype(str) == input_id) & 
                                  (users_df['비밀번호'].astype(str) == input_pw)]
            
            if not user_found.empty:
                st.session_state.logged_in = True
                st.session_state.user_id = input_id
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 일치하지 않습니다.")
        except Exception as e:
            st.error(f"로그인 처리 중 오류 발생: {e}")
else:
    # --- 로그인 후 화면 ---
    user_id = st.session_state.user_id
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox("메뉴 선택", ["경락 내역 조회", "비밀번호 변경", "로그아웃"])
    
    if menu == "경락 내역 조회":
        st.title(f"📄 {user_id}번 경락 내역")
        df = load_data()
        # 002 vs 2 매칭 로직 적용
        df['정산코드_str'] = df['정산코드'].astype(str).str.strip()
        target_id = str(user_id).strip()
        try: target_id_int = str(int(target_id))
        except: target_id_int = target_id
        
        my_data = df[(df['정산코드_str'] == target_id) | (df['정산코드_str'] == target_id_int)]
        
        if not my_data.empty:
            st.success(f"오늘 총 {len(my_data)}건의 내역이 있습니다.")
            st.dataframe(my_data[['품목명', '출하자', '중량', '등급', '단가', '수량', '금액']], use_container_width=True)
        else:
            st.warning("오늘 낙찰된 내역이 없습니다.")

    elif menu == "비밀번호 변경":
        st.title("🔐 비밀번호 변경")
        new_pw = st.text_input("새 비밀번호 입력", type="password")
        confirm_pw = st.text_input("새 비밀번호 확인", type="password")
        
        if st.button("변경하기"):
            if new_pw == confirm_pw and len(new_pw) > 0:
                try:
                    user_sheet = get_user_sheet()
                    cell = user_sheet.find(str(user_id)) # 아이디로 행 찾기
                    user_sheet.update_cell(cell.row, 2, new_pw) # 2번째 컬럼(비밀번호) 업데이트
                    st.success("✅ 비밀번호가 변경되었습니다. 다음 로그인부터 적용됩니다.")
                except Exception as e:
                    st.error(f"변경 실패: {e}")
            else:
                st.warning("비밀번호가 일치하지 않거나 비어있습니다.")

    elif menu == "로그아웃":
        st.session_state.logged_in = False
        st.rerun()
