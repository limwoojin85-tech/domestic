import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback

# --- 1. 구글 API 접속 (로그 강화 버전) ---
def get_client():
    try:
        creds_info = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception:
        st.error("🔥 [인증 에러] Secrets 설정 내용을 확인하세요.")
        st.code(traceback.format_exc())
        return None

# --- 2. 시트 데이터 로드 (한글 탭 이름 반영) ---
def get_sheets():
    try:
        client = get_client()
        if not client: return None, None
        
        sh = client.open_by_key(st.secrets["spreadsheet_id"])
        
        # [수정] 탭 이름을 한글 '시트2'로 매칭
        try:
            auth_sheet = sh.worksheet("시트2")
        except:
            all_sheets = [s.title for s in sh.worksheets()]
            st.error(f"❌ '시트2' 탭을 찾을 수 없습니다. (현재 탭 목록: {all_sheets})")
            return None, None
            
        data_sheet = sh.sheet1 # 첫 번째 탭 (경락데이터)
        return data_sheet, auth_sheet
    except Exception:
        st.error("🔥 [연결 에러] 구글 시트 접근 중 오류 발생")
        st.code(traceback.format_exc())
        return None, None

# --- UI 설정 ---
st.set_page_config(page_title="인천농산물 경락시스템", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # [로그인 화면]
    st.title("🍎 중도매인 로그인")
    st.info("💡 아이디 형식: i + 번호 (예: i002)")
    
    id_input = st.text_input("아이디 (ID)").strip()
    pw_input = st.text_input("비밀번호 (PW)", type="password").strip()
    
    if st.button("로그인", use_container_width=True):
        _, auth_sh = get_sheets()
        if auth_sh:
            users = pd.DataFrame(auth_sh.get_all_records())
            # 데이터 정규화
            users['아이디'] = users['아이디'].astype(str).str.strip()
            users['비밀번호'] = users['비밀번호'].astype(str).str.strip()
            
            match = users[(users['아이디'] == id_input) & (users['비밀번호'] == pw_input)]
            
            if not match.empty:
                st.session_state.logged_in = True
                st.session_state.user_id = id_input.replace('i', '') # 순수 번호 (예: 002)
                st.session_state.full_id = id_input # i 포함 아이디
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 틀립니다.")
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
            
            # '002'와 '2'를 모두 매칭
            try: target_int = str(int(target))
            except: target_int = target
            
            my_data = df[(df['정산코드_str'] == target) | (df['정산코드_str'] == target_int)]
            
            if not my_data.empty:
                st.success(f"오늘 총 {len(my_data)}건의 내역이 있습니다.")
                st.dataframe(my_data[['품목명', '출하자', '중량', '등급', '단가', '수량', '금액']], use_container_width=True)
                total = pd.to_numeric(my_data['금액']).sum()
                st.metric("💰 총 낙찰 금액", f"{total:,.0f} 원")
            else:
                st.warning("조회된 내역이 없습니다.")

    elif menu == "비밀번호 수정":
        st.title("🔐 내 비밀번호 수정")
        new_pw = st.text_input("새 비밀번호 입력", type="password")
        confirm_pw = st.text_input("비밀번호 확인", type="password")
        
        if st.button("수정 완료"):
            if new_pw == confirm_pw and len(new_pw) > 0:
                try:
                    # '시트2'에서 본인 행을 찾아 비밀번호 열(2번째) 업데이트
                    cell = auth_sh.find(st.session_state.full_id)
                    auth_sh.update_cell(cell.row, 2, new_pw)
                    st.success("✅ 비밀번호가 변경되었습니다.")
                except Exception:
                    st.error("🔥 수정 중 오류가 발생했습니다.")
                    st.code(traceback.format_exc())
            else:
                st.warning("비밀번호가 일치하지 않거나 입력되지 않았습니다.")

    elif menu == "로그아웃":
        st.session_state.logged_in = False
        st.rerun()
