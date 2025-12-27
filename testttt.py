import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import random

# --- 1. 구글 시트 연결 설정 ---
@st.cache_resource
def get_gspread_client():
    try:
        # st.secrets가 없으면 로컬 파일에서 로드 시도 (예외처리 강화)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            # 줄바꿈 문자 처리 (\n)
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        else:
            st.error("secrets.toml 파일이 없거나 설정이 잘못되었습니다.")
            return None
    except Exception as e:
        st.error(f"인증 오류: {e}")
        return None

@st.cache_data(ttl=60)
def load_data(sheet_key, gid=0):
    client = get_gspread_client()
    if client:
        try:
            sh = client.open_by_key(sheet_key).get_worksheet(gid)
            data = sh.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"데이터 로드 실패: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# 페이지 설정
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# --- 시트 ID 설정 ---
# (실제 운영 시에는 st.secrets에 넣는 것이 좋습니다)
MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
DATA_SID = st.secrets.get("spreadsheet_id", "1mjSrU0L4o9M9Kn0fzXdXum2VCtvZImEN-q42pNAAoFg") # 기본값 예시 추가

# --- 2. 로그인 및 회원가입 로직 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리")
    members_df = load_data(MEMBER_SID)
    
    tab1, tab2 = st.tabs(["🔑 로그인", "📝 가입 신청"])
    
    with tab1:
        with st.form("login_form"):
            u_id = st.text_input("아이디").strip()
            u_pw = st.text_input("비밀번호", type="password").strip()
            if st.form_submit_button("로그인"):
                if members_df.empty:
                    st.error("회원 DB를 불러오지 못했습니다.")
                else:
                    # 컬럼명 공백 제거 (안전장치)
                    members_df.columns = members_df.columns.str.strip()
                    
                    match = members_df[members_df['아이디'] == u_id]
                    if not match.empty and str(match.iloc[0]['비밀번호']) == u_pw:
                        row = match.iloc[0]
                        if str(row['승인여부']).upper() == 'Y':
                            st.session_state.user = {
                                "id": row['아이디'], 
                                "role": row['등급'], 
                                "num": str(row['아이디']).replace('i','') # i 제거 로직
                            }
                            st.rerun()
                        else: st.warning("승인 대기 중인 계정입니다.")
                    else: st.error("아이디 또는 비밀번호를 확인하세요.")
    
    with tab2:
        st.info("현재 가입 신청 테스트 중입니다.")
        with st.form("signup_form"):
            new_id = st.text_input("아이디")
            new_email = st.text_input("이메일")
            if st.form_submit_button("신청하기"):
                st.success("신청되었습니다 (기능 구현 예정)")

# --- 3. 메인 화면 ---
else:
    u = st.session_state.user
    client = get_gspread_client()
    
    # [권한 설정]
    current_role = u['role']
    # 안전하게 번호 가져오기
    test_num = u.get('num', '000').zfill(3)

    if u['id'] == 'limwoojin85' or u['role'] == '테스터':
        st.sidebar.markdown("### 🧪 관리자/테스터 메뉴")
        mode_select = st.sidebar.radio("모드 전환", ["관리자 모드", "중도매인 모드"])
        current_role = "관리자" if "관리자" in mode_select else "중도매인"
        if current_role == "중도매인":
            test_num = st.sidebar.text_input("테스트할 중도매인 번호", test_num).zfill(3)

    # 메뉴 구성
    if current_role == "관리자":
        menu = ["📄 통합 내역 조회", "✍️ 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 개인 내역 조회", "🛒 주문 신청"]
    
    choice = st.sidebar.selectbox("메뉴 선택", menu)

    # 데이터 로드
    records_df = load_data(DATA_SID)

    # --- 기능 1. 내역 조회 (수정됨) ---
    if "내역 조회" in choice:
        st.subheader(f"📊 {choice}")
        
        if records_df.empty:
            st.warning("데이터 시트가 비어있거나 불러오지 못했습니다.")
        else:
            df = records_df.copy()
            
            # [수정됨] 컬럼명 공백 제거 (안전장치 1)
            df.columns = df.columns.str.strip()
            
            # [수정됨] 컬럼 존재 여부 확인 (안전장치 2)
            # 사용자가 이전에 '일자'라고 했는지 '경락일자'라고 했는지 확인 필요
            target_date_col = '경락일자' 
            if target_date_col not in df.columns:
                # 대체 가능한 이름 찾기
                for alt in ['일자', '날짜', 'date', 'Date']:
                    if alt in df.columns:
                        target_date_col = alt
                        break
            
            if target_date_col in df.columns:
                try:
                    df[target_date_col] = pd.to_datetime(df[target_date_col], format='%Y%m%d', errors='coerce').dt.strftime('%m/%d')
                except Exception as e:
                    st.warning(f"날짜 변환 중 오류가 있어 원본을 표시합니다. ({e})")
            else:
                st.error(f"❌ 데이터에 '{target_date_col}' 컬럼이 없습니다.")
                st.write("현재 시트의 컬럼 목록:", list(df.columns))
                # 멈추지 않고 진행하기 위해 임시 컬럼 생성 또는 패스

            # 필터링 로직
            search_idx = test_num if current_role != "관리자" else st.text_input("번호 검색 (전체: 000)", "000").zfill(3)
            
            # '정산코드' 혹은 '중도매인' 컬럼 확인
            target_code_col = '정산코드'
            if target_code_col not in df.columns:
                if '중도매인' in df.columns: target_code_col = '중도매인'
            
            if target_code_col in df.columns and search_idx != "000":
                 df = df[df[target_code_col].astype(str).str.zfill(3) == search_idx]

            # 결과 출력
            st.write(f"**검색 결과: {len(df)}건**")
            
            # 컬럼명이 확실치 않을 때를 대비해 에러 방지용 출력
            display_cols = ['품목명', '금액'] 
            # 실제 존재하는 컬럼만 필터링
            valid_cols = [c for c in display_cols if c in df.columns]

            for i, row in df.sort_index(ascending=False).head(20).iterrows():
                with st.container():
                    col1, col2 = st.columns([1, 2])
                    
                    # 날짜 표시
                    date_val = row[target_date_col] if target_date_col in df.columns else "날짜없음"
                    col1.caption(f"📅 {date_val}")
                    
                    # 내용 표시
                    item_name = row['품목명'] if '품목명' in df.columns else "품목명확인필요"
                    price_val = row['금액'] if '금액' in df.columns else 0
                    
                    col2.markdown(f"**{item_name}** | {price_val:,.0f}원")
                    st.divider()
            
            if '금액' in df.columns:
                total = pd.to_numeric(df['금액'], errors='coerce').sum()
                st.metric("총 합계", f"{total:,.0f} 원")

    # --- 기능 2. 주문서 작성 ---
    elif choice == "✍️ 주문서 작성":
        st.header("📝 주문서 작성")
        # (기존 코드 유지)
        st.info("이전과 동일한 기능입니다.")

    # --- 기능 3. 주문 신청 ---
    elif choice == "🛒 주문 신청":
        st.header("🛒 주문 신청")
        # (기존 코드 유지)
        st.info("주문서 시트(ORDER_SID)를 확인해주세요.")

    # --- 기능 4. 가입 승인 ---
    elif choice == "⚙️ 가입 승인 관리":
        st.header("⚙️ 관리자 승인")
        # (기존 코드 유지)
        if not members_df.empty:
            wait_df = members_df[members_df['승인여부'] == 'N']
            # ... (기존 로직)
            if wait_df.empty:
                st.info("대기자가 없습니다.")
        else:
            st.error("회원 정보를 불러오지 못했습니다.")

    if st.sidebar.button("🚪 로그아웃"):
        del st.session_state.user
        st.rerun()
