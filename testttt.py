import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback
from datetime import datetime, date, timedelta

# --- 1. 구글 시트 연결 및 캐싱 (429 에러 방지) ---
# ttl=600은 10분 동안 시트를 다시 읽지 않고 메모리에서 가져온다는 뜻입니다. [cite: 2025-07-31]
@st.cache_data(ttl=600)
def load_all_data_cached(spreadsheet_id, member_sheet_id):
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
        client = gspread.authorize(creds)
        
        # 각 시트 로드
        data_sh = client.open_by_key(spreadsheet_id).get_worksheet(0)
        member_sh = client.open_by_key(member_sheet_id).get_worksheet(0)
        
        # 주문관리 시트 (Sheet3)
        try: order_sh = client.open_by_key(spreadsheet_id).get_worksheet(2)
        except: order_sh = None
            
        return data_sh.get_all_records(), member_sh.get_all_records(), order_sh
    except Exception as e:
        return None, None, None

# --- 2. 메인 화면 설정 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# 데이터 로드 (캐싱 적용)
data_records, member_records, order_sheet_obj = load_all_data_cached(
    st.secrets["spreadsheet_id"], "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
)

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    
    # [수정] 엔터키 로그인을 위한 st.form 적용 [cite: 2025-07-31]
    with st.form("login_form_v2"):
        st.subheader("🔑 로그인")
        in_id = st.text_input("아이디 (i+번호)").strip()
        in_pw = st.text_input("비밀번호", type="password").strip()
        login_btn = st.form_submit_button("로그인 실행 (Enter 가능)", use_container_width=True)
        
        if login_btn:
            if member_records:
                users = pd.DataFrame(member_records)
                match = users[(users['아이디'] == in_id) & (users['비밀번호'].astype(str) == str(in_pw))]
                if not match.empty:
                    row = match.iloc[0]
                    if str(row['승인여부']).upper() == 'Y':
                        st.session_state.user = {
                            "id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')
                        }
                        st.rerun()
                    else: st.warning("⏳ 승인 대기 중입니다.")
                else: st.error("❌ 정보 불일치")
            else: st.error("회원 데이터를 불러올 수 없습니다.")

else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님")
    st.sidebar.info(f"등급: {u['role']}")
    
    # [수정] 요구하신 메뉴 명칭으로 고정 [cite: 2025-07-31]
    if u['role'] == '관리자':
        menu = ["📄 관리자 내역 조회", "✍️ 정가수의 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 내역 조회", "🛒 정가수의 주문 신청"]
    
    choice = st.sidebar.radio("메뉴 이동", menu)

    # --- 1. 관리자 전용 내역 조회 (색인 및 기간 설정) ---
    if "내역 조회" in choice:
        st.header(f"📊 {choice}")
        if data_records:
            df = pd.DataFrame(data_records)
            df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
            df['정산코드_str'] = df['정산코드'].astype(str).str.strip().str.zfill(3)

            if u['role'] == '관리자':
                col1, col2 = st.columns(2)
                with col1:
                    target_jm = st.text_input("🔍 중도매인 번호 색인 (예: 005)", "").strip().zfill(3)
                with col2:
                    d_range = st.date_input("📅 조회 기간 설정", [date.today() - timedelta(days=7), date.today()])
                
                # 필터링 적용 [cite: 2025-07-31]
                if len(d_range) == 2:
                    mask = (df['경락일자'].dt.date >= d_range[0]) & (df['경락일자'].dt.date <= d_range[1])
                    df = df[mask]
                if target_jm != "000":
                    df = df[df['정산코드_str'] == target_jm]
                
                st.dataframe(df, use_container_width=True)
                st.metric("💰 검색 총액", f"{pd.to_numeric(df['금액'], errors='coerce').sum():,.0f} 원")
            else:
                my_data = df[df['정산코드_str'] == u['num'].zfill(3)]
                st.dataframe(my_data, use_container_width=True)
        else: st.warning("데이터가 비어있습니다.")

    # --- 2. 정가수의 주문서 작성 (관리자 전용) ---
    elif choice == "✍️ 정가수의 주문서 작성":
        st.header("📝 신규 정가수의 주문서 발행")
        with st.form("admin_order_create"):
            col1, col2 = st.columns(2)
            p_name = col1.text_input("품목명")
            p_sub = col2.text_input("과수/규격")
            p_price = col1.number_input("단가(가격)", min_value=0)
            p_qnty = col2.number_input("총 판매 수량", min_value=1)
            
            if st.form_submit_button("🚀 주문서 게시하기"):
                if order_sheet_obj:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    order_sheet_obj.append_row([p_name, p_sub, p_price, p_qnty, "판매중", now])
                    st.success(f"✅ {p_name} 주문서가 성공적으로 게시되었습니다.")
                    st.cache_data.clear() # 새 데이터 입력을 위해 캐시 삭제
                else: st.error("Sheet3(주문관리)가 없습니다. 시트를 생성해 주세요.")

    # --- 3. 정가수의 주문 신청 (중도매인 전용) ---
    elif choice == "🛒 정가수의 주문 신청":
        st.header("🛒 물품 주문 신청")
        if order_sheet_obj:
            order_data = pd.DataFrame(order_sheet_obj.get_all_records())
            if not order_data.empty:
                st.dataframe(order_data[order_data['상태'] == '판매중'], use_container_width=True)
            else: st.info("현재 구매 가능한 물품이 없습니다.")
        else: st.error("주문 데이터 시트를 찾을 수 없습니다.")

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
