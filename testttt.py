import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
import random

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

# 시트 ID 설정 (보안상 secrets 권장)
MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
DATA_SID = st.secrets.get("spreadsheet_id", "")

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
                match = members_df[members_df['아이디'] == u_id]
                if not match.empty and str(match.iloc[0]['비밀번호']) == u_pw:
                    row = match.iloc[0]
                    if str(row['승인여부']).upper() == 'Y':
                        st.session_state.user = {
                            "id": row['아이디'], 
                            "role": row['등급'], 
                            "num": str(row['아이디']).replace('i','')
                        }
                        st.rerun()
                    else: st.warning("승인 대기 중인 계정입니다.")
                else: st.error("계정 정보를 확인하세요.")
    
    with tab2:
        st.info("이메일 인증을 통한 가입 신청을 준비 중입니다.")
        with st.form("signup_form"):
            new_id = st.text_input("아이디 (중도매인 번호 포함 권장)")
            new_email = st.text_input("이메일 주소 (인증용)")
            if st.form_submit_button("인증번호 발송"):
                # 실제 smtplib 구현 시 로직 추가 구역
                st.success(f"{new_email}로 인증번호가 발송되었습니다. (테스트 모드)")
                st.session_state.auth_code = str(random.randint(1000, 9999))
            
            input_code = st.text_input("인증번호 입력")
            if st.form_submit_button("가입 신청 완료"):
                st.success("신청되었습니다. 관리자 승인 후 이용 가능합니다.")

# --- 3. 메인 화면 ---
else:
    u = st.session_state.user
    client = get_gspread_client()
    
    # [테스터/관리자 설정]
    current_role = u['role']
    test_num = u['num'].zfill(3)

    if u['id'] == 'limwoojin85' or u['role'] == '테스터':
        st.sidebar.markdown("### 🧪 테스터 설정")
        mode_select = st.sidebar.radio("작업 모드", ["관리자 모드", "중도매인 모드"])
        current_role = "관리자" if "관리자" in mode_select else "중도매인"
        if current_role == "중도매인":
            test_num = st.sidebar.text_input("📋 테스트 번호", u['num']).zfill(3)

    # 메뉴 구성
    if current_role == "관리자":
        menu = ["📄 통합 내역 조회", "✍️ 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 개인 내역 조회", "🛒 주문 신청"]
    
    choice = st.sidebar.selectbox("메뉴 선택", menu)

    # 데이터 로드
    records_df = load_data(DATA_SID)
    order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)

    # --- 기능 1. 내역 조회 (모바일 최적화 버전) ---
    if "내역 조회" in choice:
        st.subheader(f"📊 {choice}")
        if not records_df.empty:
            df = records_df.copy()
            # [날짜 최적화] 시분초 제거하고 날짜만 표시
            df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce').dt.strftime('%m/%d')
            
            # 필터링
            search_idx = test_num if current_role != "관리자" else st.text_input("🔍 번호 검색 (전체: 000)", "000").zfill(3)
            if search_idx != "000":
                df = df[df['정산코드'].astype(str).str.zfill(3) == search_idx]
            
            # [모바일 가독성 개선] 테이블 대신 카드형으로 노출
            st.write(f"**현재 검색 결과: {len(df)}건**")
            
            for i, row in df.sort_index(ascending=False).head(20).iterrows():
                with st.container():
                    # 폰에서 한 눈에 들어오도록 2열 배치
                    col1, col2 = st.columns([1, 2])
                    col1.caption(f"📅 {row['경락일자']}")
                    col2.markdown(f"**{row['품목명']}** | {row['금액']:,}원")
                    st.divider()
            
            st.metric("총 합계", f"{pd.to_numeric(df['금액'], errors='coerce').sum():,.0f} 원")
        else:
            st.warning("조회할 데이터가 없습니다.")

    # --- 기능 2. 주문서 작성 (관리자) ---
    elif choice == "✍️ 주문서 작성":
        st.header("📝 새 주문 발행")
        with st.form("order_write"):
            col1, col2 = st.columns(2)
            pn = col1.text_input("품목명")
            ps = col2.text_input("규격")
            pp = col1.number_input("단가", min_value=0)
            pq = col2.number_input("수량", min_value=0)
            if st.form_submit_button("공지 및 발행"):
                order_sh.append_row([datetime.now().strftime("%Y-%m-%d"), pn, ps, pp, pq, "판매중"])
                st.success("발주서가 성공적으로 등록되었습니다.")
                st.cache_data.clear()

    # --- 기능 3. 주문 신청 (중도매인) ---
    elif choice == "🛒 주문 신청":
        st.header("🛒 구매 신청")
        order_df = pd.DataFrame(order_sh.get_all_records())
        if not order_df.empty:
            active = order_df[order_df['상태'] == '판매중']
            for i, r in active.iterrows():
                # 모바일에서는 expander가 정보를 가리기 좋음
                with st.expander(f"📦 {r['품목명']} ({r['규격']}) - {r['단가']:,}원"):
                    q = st.number_input("신청 수량", min_value=0, key=f"q{i}")
                    if st.button("신청하기", key=f"b{i}"):
                        st.balloons()
                        st.success(f"{test_num}번 중도매인: {r['품목명']} {q}개 신청 완료")

    # --- 기능 4. 가입 승인 관리 (관리자) ---
    elif choice == "⚙️ 가입 승인 관리":
        st.header("⚙️ 신규 가입 승인")
        m_df = load_data(MEMBER_SID)
        wait_df = m_df[m_df['승인여부'] == 'N'].copy()
        if not wait_df.empty:
            for i, r in wait_df.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{r['닉네임']}** ({r['아이디']})")
                if c2.button("승인", key=f"app{i}"):
                    m_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                    # 실제 업데이트 로직 (id 기준 검색)
                    vals = m_sh.get_all_values()
                    for idx, row in enumerate(vals):
                        if row[0] == r['아이디']:
                            m_sh.update_cell(idx+1, 5, 'Y')
                            st.success(f"{r['아이디']} 승인 완료")
                            st.cache_data.clear()
                            st.rerun()
        else:
            st.info("대기 중인 신청자가 없습니다.")

    if st.sidebar.button("🚪 로그아웃"):
        del st.session_state.user
        st.rerun()
