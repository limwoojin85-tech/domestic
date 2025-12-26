import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta

# --- 1. 구글 시트 데이터 로드 및 연결 설정 ---
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

# 시트 데이터 불러오기 함수
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
        order_sh
    )

st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# 데이터 로드
try:
    records_df, members_df, order_obj = load_all_data()
except Exception as e:
    st.error(f"데이터 로드 중 오류 발생: {e}")
    st.stop()

# --- 2. 로그인 시스템 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    with st.form("login_center"):
        u_id = st.text_input("아이디 (i+번호)").strip()
        u_pw = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인", use_container_width=True):
            match = members_df[(members_df['아이디'] == u_id) & (members_df['비밀번호'].astype(str) == str(u_pw))]
            if not match.empty:
                row = match.iloc[0]
                if str(row['승인여부']).upper() == 'Y':
                    # 세션 정보 저장
                    st.session_state.user = {
                        "id": row['아이디'], 
                        "role": row['등급'], 
                        "num": row['아이디'].replace('i','')
                    }
                    st.rerun()
                else: st.warning("⏳ 승인 대기 중입니다.")
            else: st.error("❌ 정보를 다시 확인해 주세요.")

# --- 3. 로그인 성공 후 메인 화면 ---
else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님")
    
    # [핵심] 테스터 및 limwoojin85 전용 모드 전환 스위치
    current_role = u['role']
    if u['role'] == '테스터' or u['id'] == 'limwoojin85':
        st.sidebar.info("🧪 현재 테스터 권한으로 접속 중")
        mode_toggle = st.sidebar.radio("작업 모드 선택", ["회사관계자 모드", "중도매인 모드"])
        current_role = "관리자" if mode_toggle == "회사관계자 모드" else "중도매인"

    # 권한별 메뉴 구성
    if current_role == '관리자':
        menu = ["📄 통합 내역 조회", "✍️ 정가수의 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 개인 내역 조회", "🛒 주문 신청 (중도매인)"]
    
    choice = st.sidebar.radio("메뉴", menu)

    # --- 메뉴 1. 내역 조회 (번호 필터, 기간 필터 포함) ---
    if "내역 조회" in choice:
        st.header(f"📊 {choice}")
        df = records_df.copy()
        
        # 날짜 및 번호 전처리
        df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
        df['중도매인번호'] = df['정산코드'].astype(str).str.zfill(3)

        c1, c2 = st.columns(2)
        with c1:
            if current_role == '관리자':
                search_idx = st.text_input("🔍 중도매인 번호 입력 색인 (전체는 공백)", "").strip().zfill(3)
            else:
                search_idx = u['num'].zfill(3)
                st.write(f"나의 번호: **{search_idx}**")
        
        with c2:
            period = st.date_input("📅 조회 기간 설정", [date.today() - timedelta(days=7), date.today()])

        # 데이터 필터링 실행
        if len(period) == 2:
            df = df[(df['경락일자'].dt.date >= period[0]) & (df['경락일자'].dt.date <= period[1])]
        
        if current_role == '관리자':
            if search_idx != "000":
                df = df[df['중도매인번호'] == search_idx]
        else:
            df = df[df['중도매인번호'] == search_idx]

        st.dataframe(df.sort_values('경락일자', ascending=False), use_container_width=True)
        
        total_val = pd.to_numeric(df['금액'], errors='coerce').sum()
        st.metric("💰 조회 결과 합계", f"{total_val:,.0f} 원")

    # --- 메뉴 2. 주문서 작성 (관리자 전용 입력창) ---
    elif choice == "✍️ 정가수의 주문서 작성":
        st.header("📝 정가수의 주문서 발행 (발주)")
        st.write("항목별로 입력 후 발주 버튼을 누르면 중도매인에게 공개됩니다.")
        
        with st.form("new_order_form"):
            col1, col2 = st.columns(2)
            p_name = col1.text_input("🍎 품목명 (예: 캠벨포도)")
            p_spec = col2.text_input("📦 규격 (예: 5kg/박스)")
            p_price = col1.number_input("💵 단가", min_value=0, step=100)
            p_qnty = col2.number_input("🔢 총 발주 수량", min_value=1)
            
            if st.form_submit_button("🚀 발주 및 주문서 생성"):
                if p_name and p_spec:
                    order_obj.append_row([
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        p_name, p_spec, p_price, p_qnty, "판매중"
                    ])
                    st.success(f"✅ {p_name} 주문서가 생성되었습니다!")
                    st.cache_data.clear() # 데이터 갱신
                else:
                    st.warning("품목명과 규격을 입력해주세요.")

    # --- 메뉴 3. 주문 신청 (중도매인 전용 입력창) ---
    elif choice == "🛒 주문 신청 (중도매인)":
        st.header("🛒 진행 중인 주문서 목록")
        order_data = pd.DataFrame(order_obj.get_all_records())
        
        if not order_data.empty:
            active_orders = order_data[order_data['상태'] == '판매중']
            if active_orders.empty:
                st.info("현재 구매 가능한 주문서가 없습니다.")
            else:
                for idx, row in active_orders.iterrows():
                    with st.expander(f"📦 {row['품목명']} | {row['규격']} | 단가: {row['단가']:,}원"):
                        c_q, c_b = st.columns([3, 1])
                        req_q = c_q.number_input(f"구매 수량 입력 (최대 {row['수량']}개)", 
                                                 min_value=0, max_value=int(row['수량']), key=f"req_{idx}")
                        if c_b.button("구매 신청", key=f"btn_{idx}"):
                            if req_q > 0:
                                st.balloons()
                                st.success(f"[{row['품목명']}] {req_q}개 신청 완료! 관리자가 확인 후 정산됩니다.")
                            else:
                                st.error("수량을 입력하세요.")
        else:
            st.info("등록된 주문서가 없습니다.")

    # --- 메뉴 4. 가입 승인 관리 ---
    elif choice == "⚙️ 가입 승인 관리":
        st.header("⚙️ 사용자 가입 승인")
        st.dataframe(members_df)
        st.info("승인 처리는 구글 시트에서 직접 'Y'로 변경해 주세요.")

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
