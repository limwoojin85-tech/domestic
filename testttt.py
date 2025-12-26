import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta

# --- 1. 구글 시트 연결 설정 ---
@st.cache_resource
def get_gspread_client():
    try:
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
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"인증 오류: {e}")
        return None

@st.cache_data(ttl=60)
def load_data(sheet_key, gid=0):
    client = get_gspread_client()
    if client:
        try:
            sh = client.open_by_key(sheet_key).get_worksheet(gid)
            return pd.DataFrame(sh.get_all_records())
        except: return pd.DataFrame()
    return pd.DataFrame()

st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
DATA_SID = st.secrets.get("spreadsheet_id", "")

# --- 2. 로그인 로직 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    members_df = load_data(MEMBER_SID)
    t1, t2 = st.tabs(["🔑 로그인", "📝 가입 신청"])
    
    with t1:
        with st.form("login"):
            u_id = st.text_input("아이디").strip()
            u_pw = st.text_input("비밀번호", type="password").strip()
            if st.form_submit_button("로그인"):
                match = members_df[members_df['아이디'] == u_id]
                if not match.empty and str(match.iloc[0]['비밀번호']) == u_pw:
                    row = match.iloc[0]
                    if str(row['승인여부']).upper() == 'Y':
                        st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                        st.rerun()
                    else: st.warning("승인 대기 중")
                else: st.error("계정 정보를 확인하세요.")
    # (가입 신청 탭 로직 생략 - 이전과 동일)

# --- 3. 메인 화면 (핵심 수정 구역) ---
else:
    u = st.session_state.user
    client = get_gspread_client()
    
    # [테스터 전용 사이드바]
    current_role = u['role']
    test_num = u['num'].zfill(3) # 기본값은 본인 번호

    if u['id'] == 'limwoojin85' or u['role'] == '테스터':
        st.sidebar.markdown("### 🧪 테스터 설정")
        mode_select = st.sidebar.radio("작업 모드", ["회사관계자(관리자)", "중도매인"])
        current_role = "관리자" if "회사관계자" in mode_select else "중도매인"
        
        if current_role == "중도매인":
            test_num = st.sidebar.text_input("📋 테스트할 번호 입력", u['num']).zfill(3)
            st.sidebar.caption(f"현재 {test_num}번 중도매인으로 빙의 중")

    # [역할에 따른 실시간 메뉴 전환]
    if current_role == "관리자":
        menu = ["📄 통합 내역 조회", "✍️ 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 개인 내역 조회", "🛒 주문 신청"]
    
    choice = st.sidebar.radio("메뉴", menu)

    # 데이터 로드
    records_df = load_data(DATA_SID)
    order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)

    # --- 기능 1. 내역 조회 ---
    if "내역 조회" in choice:
        st.header(f"📊 {choice}")
        if not records_df.empty:
            df = records_df.copy()
            df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
            
            c1, c2 = st.columns(2)
            view_mode = c1.radio("조회 방식", ["당일", "기간"], horizontal=True)
            if view_mode == "당일":
                d = c2.date_input("날짜", date.today())
                df = df[df['경락일자'].dt.date == d]
            else:
                p = c2.date_input("기간", [date.today() - timedelta(days=7), date.today()])
                if len(p) == 2: df = df[(df['경락일자'].dt.date >= p[0]) & (df['경락일자'].dt.date <= p[1])]
            
            # [번호 필터링] 관리자면 입력받고, 중도매인이면 지정된 test_num 사용
            if current_role == "관리자":
                search_idx = st.text_input("🔍 중도매인 번호 색인 (전체는 000)", "000").zfill(3)
            else:
                search_idx = test_num
                st.info(f"현재 **{search_idx}**번 중도매인 내역을 조회 중입니다.")

            if search_idx != "000":
                df = df[df['정산코드'].astype(str).str.zfill(3) == search_idx]
            
            st.dataframe(df.sort_values('경락일자', ascending=False), use_container_width=True)
            st.metric("합계", f"{pd.to_numeric(df['금액'], errors='coerce').sum():,.0f} 원")

    # --- 기능 2. 주문서 작성 (관리자 모드일 때만 노출/작동) ---
    elif choice == "✍️ 주문서 작성":
        st.header("📝 주문서 발행")
        with st.form("w"):
            pn, ps, pp, pq = st.text_input("품목"), st.text_input("규격"), st.number_input("단가"), st.number_input("수량")
            if st.form_submit_button("발주"):
                order_sh.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), pn, ps, pp, pq, "판매중"])
                st.success("발주 성공")
                st.cache_data.clear()

    # --- 기능 3. 주문 신청 (중도매인 모드일 때만 노출/작동) ---
    elif choice == "🛒 주문 신청":
        st.header("🛒 구매 신청")
        order_df = pd.DataFrame(order_sh.get_all_records())
        if not order_df.empty:
            active = order_df[order_df['상태'] == '판매중']
            for i, r in active.iterrows():
                with st.expander(f"📦 {r['품목명']} ({r['규격']})"):
                    q = st.number_input("신청 수량", min_value=0, key=f"q{i}")
                    if st.button("신청하기", key=f"b{i}"):
                        st.success(f"{test_num}번 중도매인 이름으로 {q}개 신청되었습니다.")

    # --- 기능 4. 가입 승인 관리 ---
    elif choice == "⚙️ 가입 승인 관리":
        st.header("⚙️ 신규 가입 승인")
        members_df = load_data(MEMBER_SID)
        wait_df = members_df[members_df['승인여부'] == 'N'].copy()
        if not wait_df.empty:
            all_s = st.checkbox("전체 선택")
            sel = [r['아이디'] for i, r in wait_df.iterrows() if st.checkbox(f"{r['닉네임']}({r['아이디']})", value=all_s)]
            if st.button("일괄 승인"):
                m_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                for tid in sel:
                    for idx, rv in enumerate(m_sh.get_all_values()):
                        if rv[0] == tid: m_sh.update_cell(idx+1, 5, 'Y')
                st.success("승인 완료")
                st.cache_data.clear()
                st.rerun()

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
