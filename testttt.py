import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import traceback
from datetime import datetime, date, timedelta

# --- 1. 구글 시트 데이터 로드 (함수명 통일) ---
def load_all_data():
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
        
        # 시트 ID 확인 (Sheet1: 경락데이터, 회원관리: 사용자 시트) [cite: 2025-07-31]
        data_sh = client.open_by_key(st.secrets["spreadsheet_id"]).get_worksheet(0)
        member_sh = client.open_by_key("18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA").get_worksheet(0)
        
        # 주문관리용 Sheet3 (없으면 새로 만드시거나 인덱스 확인 필요)
        try: order_sh = client.open_by_key(st.secrets["spreadsheet_id"]).get_worksheet(2)
        except: order_sh = None
            
        return data_sh, member_sh, order_sh
    except Exception as e:
        st.error(f"🔥 데이터 연결 오류: {e}")
        return None, None, None

# --- 2. 메인 화면 설정 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    
    # [수정] st.form을 사용하여 비밀번호 입력 후 엔터키 로그인 구현 [cite: 2025-07-31]
    with st.form("main_login_form"):
        st.subheader("🔑 로그인")
        in_id = st.text_input("아이디 (i+번호)").strip()
        in_pw = st.text_input("비밀번호", type="password").strip()
        login_submit = st.form_submit_button("로그인 실행", use_container_width=True)
        
        if login_submit:
            _, member_sh, _ = load_all_data()
            if member_sh:
                # 시트의 전체 데이터 로드 후 비교
                users = pd.DataFrame(member_sh.get_all_records())
                match = users[(users['아이디'] == in_id) & (users['비밀번호'].astype(str) == str(in_pw))]
                if not match.empty:
                    row = match.iloc[0]
                    if str(row['승인여부']).upper() == 'Y':
                        st.session_state.user = {
                            "id": row['아이디'], 
                            "role": row['등급'], 
                            "num": row['아이디'].replace('i','')
                        }
                        st.rerun()
                    else: st.warning("⏳ 아직 승인 대기 중입니다.")
                else: st.error("❌ 아이디 또는 비밀번호가 틀립니다.")

else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님")
    st.sidebar.info(f"등급: {u['role']}")
    
    # [수정] 관리자 메뉴명 '정가수의 주문서 작성'으로 변경 [cite: 2025-07-31]
    if u['role'] == '관리자':
        menu = ["📄 관리자 내역 조회", "✍️ 정가수의 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 내역 조회", "🛒 물품 주문하기"]
    
    choice = st.sidebar.radio("메뉴 이동", menu)

    # --- 기능 1: 내역 조회 (색인 및 기간/날짜 지정 설정) ---
    if "내역 조회" in choice:
        st.header(f"📊 {choice}")
        data_sh, _, _ = load_all_data()
        if data_sh:
            df = pd.DataFrame(data_sh.get_all_records())
            # 경락일자 정규화 (%Y%m%d -> datetime) [cite: 2025-07-31]
            df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
            df['정산코드_str'] = df['정산코드'].astype(str).str.strip().str.zfill(3)

            if u['role'] == '관리자':
                # [수정] 관리자용 색인 및 기간 설정 UI 추가 [cite: 2025-07-31]
                col1, col2 = st.columns(2)
                with col1:
                    search_num = st.text_input("🔍 조회할 중도매인 번호 색인 (예: 002, 비워두면 전체)", "").strip().zfill(3)
                with col2:
                    # 날짜 지정 및 기간 설정 (기본값: 오늘부터 일주일 전까지) [cite: 2025-07-31]
                    d_range = st.date_input("📅 조회 날짜/기간 지정", [date.today() - timedelta(days=7), date.today()])
                
                # 필터링 적용
                if len(d_range) == 2:
                    mask = (df['경락일자'].dt.date >= d_range[0]) & (df['경락일자'].dt.date <= d_range[1])
                    df = df[mask]
                if search_num != "000":
                    df = df[df['정산코드_str'] == search_num]
                
                st.dataframe(df, use_container_width=True)
                st.metric("💰 검색 결과 총액", f"{pd.to_numeric(df['금액'], errors='coerce').sum():,.0f} 원")
            else:
                # 중도매인: 본인 내역만 출력
                my_data = df[df['정산코드_str'] == u['num'].zfill(3)]
                st.dataframe(my_data, use_container_width=True)

    # --- 기능 2: 주문서 작성(관리자) / 주문하기(중도매인) ---
    elif "주문" in choice:
        st.header(f"🍎 {choice}")
        _, _, order_sh = load_all_data()
        
        if u['role'] == '관리자':
            st.subheader("📝 신규 정가수의 주문서 작성")
            with st.form("admin_order_form"):
                col1, col2 = st.columns(2)
                p_name = col1.text_input("품목명 (예: 사과 부사)")
                p_sub = col2.text_input("과수/규격 (예: 12과)")
                p_price = col1.number_input("가격(단가)", min_value=0)
                p_qnty = col2.number_input("발행 총 수량", min_value=1)
                
                if st.form_submit_button("🚀 주문서 발행 및 게시"):
                    if order_sh:
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        order_sh.append_row([p_name, p_sub, p_price, p_qnty, "판매중", now])
                        st.success(f"✅ {p_name} 주문서가 중도매인에게 발행되었습니다.")
                    else: st.error("주문관리 시트 연결 실패")
        else:
            st.subheader("🛒 주문 가능한 물품")
            # 중도매인 주문 로직 (생략 방지 위해 구조 유지)
            if order_sh:
                items = pd.DataFrame(order_sh.get_all_records())
                st.dataframe(items[items['상태'] == '판매중'], use_container_width=True)

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
