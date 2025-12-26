import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta

# --- 1. 구글 시트 연결 설정 ---
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

client = get_gspread_client()

# 시트 ID 설정 (실제 시트에 맞게 수정 확인)
DATA_SID = st.secrets["spreadsheet_id"]
MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"

st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# --- 2. 로그인 로직 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    with st.form("login_form"):
        u_id = st.text_input("아이디 (i+번호)").strip()
        u_pw = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인", use_container_width=True):
            member_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
            members = pd.DataFrame(member_sh.get_all_records())
            match = members[(members['아이디'] == u_id) & (members['비밀번호'].astype(str) == str(u_pw))]
            
            if not match.empty:
                row = match.iloc[0]
                if str(row['승인여부']).upper() == 'Y':
                    st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                    st.rerun()
                else: st.warning("⏳ 승인 대기 중입니다.")
            else: st.error("❌ 정보를 다시 확인해 주세요.")
else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님 ({u['role']})")
    
    if u['role'] == '관리자':
        menu = ["📄 통합 내역 조회", "✍️ 정가수의 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 개인 내역 조회", "🛒 주문 신청 (중도매인)"]
    
    choice = st.sidebar.radio("메뉴 이동", menu)

    # --- 3. [관리자/중도매인] 내역 조회 (번호색인, 기간설정 포함) ---
    if "내역 조회" in choice:
        st.header(f"📊 {choice}")
        data_sh = client.open_by_key(DATA_SID).get_worksheet(0)
        df = pd.DataFrame(data_sh.get_all_records())
        
        # 전처리
        df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
        df['중도매인번호'] = df['정산코드'].astype(str).str.zfill(3)

        # 필터 UI
        col1, col2 = st.columns(2)
        with col1:
            if u['role'] == '관리자':
                search_num = st.text_input("🔍 중도매인 번호 입력 (전체는 공백)", "").strip().zfill(3)
            else:
                search_num = u['num'].zfill(3)
                st.info(f"내 번호({search_num})로 자동 필터링됩니다.")
        
        with col2:
            today = date.today()
            date_range = st.date_input("📅 조회 기간 선택", [today - timedelta(days=7), today])

        # 필터링 적용
        if len(date_range) == 2:
            df = df[(df['경락일자'].dt.date >= date_range[0]) & (df['경락일자'].dt.date <= date_range[1])]
        
        if u['role'] == '관리자' and search_num != "000":
            df = df[df['중도매인번호'] == search_num]
        elif u['role'] != '관리자':
            df = df[df['중도매인번호'] == search_num]

        st.dataframe(df.sort_values('경락일자', ascending=False), use_container_width=True)
        
        # 합계 계산
        total_amt = pd.to_numeric(df['금액'], errors='coerce').sum()
        st.metric("총 거래 금액", f"{total_amt:,.0f} 원")

    # --- 4. [관리자] 주문서 작성 ---
    elif "주문서 작성" in choice:
        st.header("✍️ 관리자 발주용 주문서 생성")
        order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
        
        with st.form("admin_order_form"):
            col1, col2 = st.columns(2)
            p_name = col1.text_input("🍎 품목명 (예: 부사)")
            p_spec = col2.text_input("📦 규격 (예: 10kg/24과)")
            p_price = col1.number_input("💵 단가", min_value=0, step=100)
            p_total_q = col2.number_input("🔢 전체 준비 수량", min_value=1)
            
            if st.form_submit_button("🚀 주문서 리스트에 올리기"):
                # 구글 시트에 주문 정보 저장 (작성시간 포함)
                order_sh.append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    p_name, p_spec, p_price, p_total_q, "진행중"
                ])
                st.success(f"✅ {p_name} 주문서가 발행되었습니다!")

    # --- 5. [중도매인] 주문 신청 ---
    elif "주문 신청" in choice:
        st.header("🛒 주문 신청하기")
        order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
        orders_df = pd.DataFrame(order_sh.get_all_records())
        
        if not orders_df.empty:
            # '진행중'인 주문만 표시
            active_orders = orders_df[orders_df['상태'] == '진행중']
            for idx, row in active_orders.iterrows():
                with st.expander(f"📦 {row['품목명']} ({row['규격']}) - 단가: {row['단가']:,}원"):
                    order_qty = st.number_input(f"신청 수량 (최대 {row['수량']}개 가능)", 
                                              min_value=0, max_value=int(row['수량']), key=f"q_{idx}")
                    if st.button(f"신청 확정", key=f"btn_{idx}"):
                        if order_qty > 0:
                            # 별도의 신청 내역 시트가 있다면 기록 (여기서는 예시로 성공 메시지만)
                            st.balloons()
                            st.success(f"[{row['품목명']}] {order_qty}개 신청 완료! (중도매인 번호: {u['num']})")
                        else:
                            st.error("수량을 입력해주세요.")
        else:
            st.info("현재 등록된 주문서가 없습니다.")

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
