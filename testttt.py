import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta

# --- 1. 구글 시트 연결 및 데이터 로드 ---
@st.cache_resource
def get_gspread_client():
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

@st.cache_data(ttl=60)
def load_all_data():
    client = get_gspread_client()
    DATA_SID = st.secrets["spreadsheet_id"]
    MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
    ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
    
    data_sh = client.open_by_key(DATA_SID).get_worksheet(0)
    member_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
    order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
    
    return (
        pd.DataFrame(data_sh.get_all_records()), 
        pd.DataFrame(member_sh.get_all_records()), 
        member_sh, # 회원 시트 객체 (가입 신청용)
        order_sh   # 주문 시트 객체 (주문 발행용)
    )

st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# 데이터 로드
try:
    records_df, members_df, member_obj, order_obj = load_all_data()
except Exception as e:
    st.error(f"데이터 연결 오류: {e}")
    st.stop()

# --- 2. 로그인 및 가입 신청 시스템 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    
    tab1, tab2 = st.tabs(["🔑 로그인", "📝 가입 신청"])
    
    with tab1:
        with st.form("login_form"):
            u_id = st.text_input("아이디 (i+번호)").strip()
            u_pw = st.text_input("비밀번호", type="password").strip()
            if st.form_submit_button("로그인", use_container_width=True):
                match = members_df[(members_df['아이디'] == u_id) & (members_df['비밀번호'].astype(str) == str(u_pw))]
                if not match.empty:
                    row = match.iloc[0]
                    if str(row['승인여부']).upper() == 'Y':
                        st.session_state.user = {
                            "id": row['아이디'], 
                            "role": row['등급'], 
                            "num": row['아이디'].replace('i','')
                        }
                        st.rerun()
                    else: st.warning("⏳ 승인 대기 중입니다. 관리자에게 문의하세요.")
                else: st.error("❌ 정보를 다시 확인해 주세요.")
                
    with tab2:
        st.subheader("회원 가입 신청")
        with st.form("register_form"):
            new_id = st.text_input("아이디 (예: i002)").strip()
            new_pw = st.text_input("비밀번호", type="password").strip()
            new_name = st.text_input("성함/상호").strip()
            new_role = st.selectbox("등급 선택", ["중도매인", "회사관계자"])
            
            if st.form_submit_button("신청하기"):
                if new_id and new_pw and new_name:
                    # 중복 체크
                    if new_id in members_df['아이디'].values:
                        st.error("이미 존재하는 아이디입니다.")
                    else:
                        member_obj.append_row([new_id, new_pw, new_role, "N", new_name])
                        st.success("✅ 가입 신청이 완료되었습니다! 관리자 승인 후 로그인 가능합니다.")
                        st.cache_data.clear()
                else:
                    st.warning("모든 항목을 입력해 주세요.")

# --- 3. 로그인 후 메인 화면 ---
else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님")
    
    # 테스터(limwoojin85) 모드 전환 스위치
    current_role = u['role']
    if u['id'] == 'limwoojin85' or u['role'] == '테스터':
        st.sidebar.info("🧪 테스터 권한 활성화")
        mode_toggle = st.sidebar.radio("작업 모드 선택", ["회사관계자 모드", "중도매인 모드"])
        current_role = "관리자" if mode_toggle == "회사관계자 모드" else "중도매인"

    menu = ["📄 내역 조회", "✍️ 주문서 작성", "🛒 주문 신청", "⚙️ 가입 승인 관리"] if current_role == "관리자" else ["📄 내역 조회", "🛒 주문 신청"]
    choice = st.sidebar.radio("메뉴", menu)

    # --- 1) 내역 조회 (필터 포함) ---
    if choice == "📄 내역 조회":
        st.header(f"📊 {choice}")
        df = records_df.copy()
        df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
        df['중도매인번호'] = df['정산코드'].astype(str).str.zfill(3)

        c1, c2 = st.columns(2)
        with c1:
            if current_role == '관리자':
                search_idx = st.text_input("🔍 중도매인 번호 입력 (공백 시 전체)", "").strip().zfill(3)
            else:
                search_idx = u['num'].zfill(3)
                st.write(f"내 중도매인 번호: **{search_idx}**")
        
        with c2:
            period = st.date_input("📅 기간 설정", [date.today() - timedelta(days=7), date.today()])

        if len(period) == 2:
            df = df[(df['경락일자'].dt.date >= period[0]) & (df['경락일자'].dt.date <= period[1])]
        
        if current_role == '관리자' and search_idx != "000":
            df = df[df['중도매인번호'] == search_idx]
        elif current_role != '관리자':
            df = df[df['중도매인번호'] == search_idx]

        st.dataframe(df.sort_values('경락일자', ascending=False), use_container_width=True)
        st.metric("총액", f"{pd.to_numeric(df['금액'], errors='coerce').sum():,.0f} 원")

    # --- 2) 주문서 작성 (관리자 전용) ---
    elif choice == "✍️ 주문서 작성":
        st.header("📝 새 주문서 발행 (발주)")
        with st.form("new_order"):
            c1, c2 = st.columns(2)
            p_name = c1.text_input("품목명")
            p_spec = c2.text_input("규격")
            p_price = c1.number_input("단가", min_value=0)
            p_qnty = c2.number_input("수량", min_value=1)
            if st.form_submit_button("🚀 발주"):
                order_obj.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), p_name, p_spec, p_price, p_qnty, "판매중"])
                st.success("주문서가 발행되었습니다.")
                st.cache_data.clear()

    # --- 3) 주문 신청 (중도매인/테스터 전용) ---
    elif choice == "🛒 주문 신청":
        st.header("🛒 구매 신청")
        order_data = pd.DataFrame(order_obj.get_all_records())
        if not order_data.empty:
            active = order_data[order_data['상태'] == '판매중']
            for idx, row in active.iterrows():
                with st.expander(f"📦 {row['품목명']} ({row['규격']})"):
                    q = st.number_input(f"신청 수량 (잔여: {row['수량']})", min_value=0, max_value=int(row['수량']), key=f"q_{idx}")
                    if st.button("신청", key=f"b_{idx}"):
                        st.success(f"{u['id']}님, {row['품목명']} {q}개 신청 완료!")

    # --- 4) 가입 승인 관리 (관리자 전용) ---
    elif choice == "⚙️ 가입 승인 관리":
        st.header("⚙️ 가입 신청 명단")
        st.write("승인 처리는 구글 시트에서 '승인여부'를 Y로 직접 변경해 주세요.")
        st.dataframe(members_df[members_df['승인여부'] == 'N'])

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
