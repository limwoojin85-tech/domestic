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

# --- 2. 데이터 통합 로드 (Sheet1:데이터, Sheet2:계정) ---
def load_all_sheets():
    client = get_client()
    sh = client.open_by_key(st.secrets["spreadsheet_id"])
    # 탭 이름을 못 찾을 경우를 대비해 순서(index)로 가져옵니다.
    data_sh = sh.get_worksheet(0)  # 첫 번째 탭
    auth_sh = sh.get_worksheet(1)  # 두 번째 탭
    return data_sh, auth_sh

# --- 메인 화면 구성 ---
st.set_page_config(page_title="인천농산물 경락조회시스템", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🍎 중도매인 로그인")
    st.info("💡 아이디 형식: i + 번호 (예: i002)")
    id_input = st.text_input("아이디 (ID)").strip()
    pw_input = st.text_input("비밀번호 (PW)", type="password").strip()
    
    if st.button("로그인", use_container_width=True):
        try:
            _, auth_sh = load_all_sheets()
            # 모든 데이터를 문자열로 읽어와서 비교 오류 차단
            users = pd.DataFrame(auth_sh.get_all_values())
            users.columns = users.iloc[0]
            users = users[1:]
            
            # 아이디/비번 매칭
            match = users[(users['아이디'].astype(str).str.strip() == id_input) & 
                          (users['비밀번호'].astype(str).str.strip() == pw_input)]
            
            if not match.empty:
                st.session_state.logged_in = True
                st.session_state.user_num = id_input.replace('i', '') # 순수 숫자 (002)
                st.session_state.full_id = id_input 
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 틀립니다.")
        except Exception as e:
            st.error(f"로그인 중 오류: {e}")
else:
    # --- 로그인 성공 후 화면 ---
    menu = st.sidebar.radio("메뉴 선택", ["📄 경락 내역 조회", "🔐 비밀번호 변경", "👋 로그아웃"])
    
    if menu == "📄 경락 내역 조회":
        st.header(f"📊 {st.session_state.user_num}번님 경락 내역")
        try:
            data_sh, _ = load_all_sheets()
            # 전체 데이터를 읽어옴
            df = pd.DataFrame(data_sh.get_all_records())
            
            # 필터링 로직 강화 (002와 2를 모두 찾음)
            df['정산코드_str'] = df['정산코드'].astype(str).str.strip()
            target = str(st.session_state.user_num).strip()
            try: target_int = str(int(target))
            except: target_int = target
            
            my_data = df[(df['정산코드_str'] == target) | (df['정산코드_str'] == target_int)]
            
            if not my_data.empty:
                st.success(f"오늘 총 {len(my_data)}건의 내역이 있습니다.")
                display_cols = ['품목명', '출하자', '중량', '등급', '단가', '수량', '금액']
                st.dataframe(my_data[[c for c in display_cols if c in my_data.columns]], use_container_width=True)
                
                total = pd.to_numeric(my_data['금액'], errors='coerce').sum()
                st.metric("💰 오늘 총 낙찰 금액", f"{total:,.0f} 원")
            else:
                st.warning("오늘 낙찰된 내역이 없습니다.")
        except Exception:
            st.error("데이터를 불러오는 중 문제가 발생했습니다.")
            st.code(traceback.format_exc())

    elif menu == "🔐 비밀번호 변경":
        st.header("비밀번호 수정")
        new_pw = st.text_input("새 비밀번호 입력", type="password")
        if st.button("변경 완료"):
            try:
                _, auth_sh = load_all_sheets()
                cell = auth_sh.find(st.session_state.full_id)
                auth_sh.update_cell(cell.row, 2, new_pw) # B열 업데이트
                st.success("✅ 비밀번호가 변경되었습니다.")
            except:
                st.error("수정에 실패했습니다. 시트 권한을 확인하세요.")

    elif menu == "👋 로그아웃":
        st.session_state.logged_in = False
        st.rerun()
