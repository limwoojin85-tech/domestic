import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback

# --- 1. 구글 API 접속 함수 ---
def get_client():
    try:
        creds_info = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception:
        st.error("🔥 [인증 오류] Streamlit Secrets 설정을 확인하세요.")
        st.code(traceback.format_exc())
        return None

# --- 2. 시트 데이터 로드 (탭 이름: Sheet2 고정) ---
def get_sheets():
    try:
        client = get_client()
        if not client: return None, None
        
        sh = client.open_by_key(st.secrets["spreadsheet_id"])
        
        # [수정] 보내주신 링크의 실제 탭 이름인 'Sheet2'를 사용합니다.
        try:
            auth_sheet = sh.worksheet("Sheet2")
        except:
            # 만약 Sheet2가 없다면 현재 탭 목록을 화면에 뿌려줍니다.
            all_tabs = [s.title for s in sh.worksheets()]
            st.error(f"❌ 'Sheet2' 탭을 찾을 수 없습니다. (현재 탭 목록: {all_tabs})")
            return None, None
            
        data_sheet = sh.sheet1 # 첫 번째 탭 (경락데이터)
        return data_sheet, auth_sheet
    except Exception:
        st.error("🔥 [연결 오류] 구글 시트에 접근할 수 없습니다.")
        st.code(traceback.format_exc())
        return None, None

# --- UI 설정 ---
st.set_page_config(page_title="인천농산물 경락시스템", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🍎 중도매인 로그인")
    st.info("💡 아이디 형식: i + 번호 (예: i002)")
    
    id_input = st.text_input("아이디 (ID)").strip()
    pw_input = st.text_input("비밀번호 (PW)", type="password").strip()
    
    if st.button("로그인", use_container_width=True):
        _, auth_sh = get_sheets()
        if auth_sh:
            # 모든 데이터를 문자열로 읽어와서 서식 오염 방지
            users = pd.DataFrame(auth_sh.get_all_records())
            
            # [핵심] 비교를 위해 모든 값을 문자열로 강제 변환 및 공백 제거
            users['아이디'] = users['아이디'].astype(str).str.strip()
            users['비밀번호'] = users['비밀번호'].astype(str).str.strip()
            
            # 입력값과 매칭 (대소문자 무시하지 않음)
            match = users[(users['아이디'] == id_input) & (users['비밀번호'] == pw_input)]
            
            if not match.empty:
                st.session_state.logged_in = True
                st.session_state.user_id = id_input.replace('i', '') 
                st.session_state.full_id = id_input
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 틀립니다. (Sheet2 내용을 확인하세요)")
else:
    # [로그인 성공 후 화면]
    menu = st.sidebar.radio("메뉴", ["내역 조회", "비밀번호 수정", "로그아웃"])
    data_sh, auth_sh = get_sheets()

    if menu == "내역 조회":
        st.title(f"📊 {st.session_state.user_id}번 경락 내역")
        if data_sh:
            df = pd.DataFrame(data_sh.get_all_records())
            df['정산코드_str'] = df['정산코드'].astype(str).str.strip()
            target = str(st.session_state.user_id)
            
            # 002와 2를 모두 매칭
            try: target_int = str(int(target))
            except: target_int = target
            
            my_data = df[(df['정산코드_str'] == target) | (df['정산코드_str'] == target_int)]
            
            if not my_data.empty:
                st.success(f"오늘 총 {len(my_data)}건의 내역이 있습니다.")
                # 필요한 컬럼만 출력
                cols = ['품목명', '출하자', '중량', '등급', '단가', '수량', '금액']
                st.dataframe(my_data[[c for c in cols if c in my_data.columns]], use_container_width=True)
                total = pd.to_numeric(my_data['금액'], errors='coerce').sum()
                st.metric("💰 총 낙찰 금액", f"{total:,.0f} 원")
            else:
                st.warning("오늘 낙찰된 내역이 없습니다.")

    elif menu == "비밀번호 수정":
        st.title("🔐 내 비밀번호 수정")
        new_pw = st.text_input("새 비밀번호 입력", type="password")
        confirm_pw = st.text_input("비밀번호 확인", type="password")
        
        if st.button("수정 완료"):
            if new_pw == confirm_pw and len(new_pw) > 0:
                try:
                    cell = auth_sh.find(st.session_state.full_id)
                    auth_sh.update_cell(cell.row, 2, new_pw)
                    st.success("✅ 비밀번호가 변경되었습니다.")
                except Exception:
                    st.error("🔥 수정 중 오류가 발생했습니다.")
                    st.code(traceback.format_exc())
            else:
                st.warning("비밀번호가 일치하지 않습니다.")

    elif menu == "로그아웃":
        st.session_state.logged_in = False
        st.rerun()
