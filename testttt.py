import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta

# --- 1. 구글 시트 데이터 로드 (캐싱 적용으로 429 에러 방지) ---
@st.cache_data(ttl=60) # 1분간 캐시 유지
def get_data_from_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = {
        "type": st.secrets["gcp_service_account"]["type"],
        "project_id": st.secrets["gcp_service_account"]["project_id"],
        "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
        "private_key": st.secrets["gcp_service_account"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["gcp_service_account"]["client_email"],
        "client_id": st.secrets["gcp_service_account"]["client_id"],
        "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
        "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # [설정] 시트 ID들
    DATA_SID = st.secrets["spreadsheet_id"] # 경락데이터
    MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA" # 회원관리
    ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU" # [신규] 주문관리 시트 

    data_sh = client.open_by_key(DATA_SID).get_worksheet(0)
    member_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
    order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
    
    return data_sh.get_all_records(), member_sh.get_all_records(), order_sh

st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# 데이터 미리 불러오기
records, members, order_obj = get_data_from_sheets()

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    # [수정] 엔터키 지원 로그인 폼 [cite: 2025-07-31]
    with st.form("login_center"):
        u_id = st.text_input("아이디 (i+번호)").strip()
        u_pw = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인", use_container_width=True):
            users_df = pd.DataFrame(members)
            match = users_df[(users_df['아이디'] == u_id) & (users_df['비밀번호'].astype(str) == str(u_pw))]
            if not match.empty:
                row = match.iloc[0]
                if str(row['승인여부']).upper() == 'Y':
                    st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                    st.rerun()
                else: st.warning("⏳ 승인 대기 중입니다.")
            else: st.error("❌ 정보를 다시 확인해 주세요.")
else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님")
    
    # [수정] 요구하신 메뉴 명칭으로 고정 [cite: 2025-07-31]
    if u['role'] == '관리자':
        menu = ["📄 관리자 내역 조회", "✍️ 정가수의 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 내역 조회", "🛒 정가수의 주문 신청"]
    
    choice = st.sidebar.radio("메뉴", menu)

    # --- 1. 관리자 내역 조회 (색인 및 기간 설정 완벽 구현) ---
    if "내역 조회" in choice:
        st.header(f"📊 {choice}")
        df = pd.DataFrame(records)
        df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
        df['코드_str'] = df['정산코드'].astype(str).str.strip().str.zfill(3)

        if u['role'] == '관리자':
            c1, c2 = st.columns(2)
            with c1: # [중요] 번호 색인 기능 [cite: 2025-07-31]
                search_idx = st.text_input("🔍 중도매인 번호 입력 색인 (예: 002, 공백 시 전체)", "").strip().zfill(3)
            with c2: # [중요] 기간 설정 기능 [cite: 2025-07-31]
                period = st.date_input("📅 기간 설정", [date.today() - timedelta(days=7), date.today()])
            
            # 필터링
            if len(period) == 2:
                df = df[(df['경락일자'].dt.date >= period[0]) & (df['경락일자'].dt.date <= period[1])]
            if search_idx != "000":
                df = df[df['코드_str'] == search_idx]
            
            st.dataframe(df, use_container_width=True)
            st.metric("💰 검색 결과 총액", f"{pd.to_numeric(df['금액'], errors='coerce').sum():,.0f} 원")
        else:
            st.dataframe(df[df['코드_str'] == u['num'].zfill(3)], use_container_width=True)

    # --- 2. 정가수의 주문서 작성 (관리자 전용) ---
    elif "주문서 작성" in choice:
        st.header("📝 정가수의 주문서 작성")
        with st.form("new_order"):
            col1, col2 = st.columns(2)
            p_name = col1.text_input("품목명")
            p_sub = col2.text_input("과수/규격")
            p_price = col1.number_input("단가", min_value=0)
            p_qnty = col2.number_input("수량", min_value=1)
            if st.form_submit_button("🚀 주문서 발행"):
                order_obj.append_row([p_name, p_sub, p_price, p_qnty, "판매중", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                st.success("✅ 주문서가 Sheet3에 발행되었습니다.")
                st.cache_data.clear()

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
