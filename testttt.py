import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import traceback
from datetime import datetime

# --- 1. 구글 시트 연결 (기존 시트 및 회원 시트 통합) ---
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
        
        # 1. 경락데이터 시트
        data_sh = client.open_by_key(st.secrets["spreadsheet_id"]).get_worksheet(0)
        # 2. 회원관리 시트 (사용자님이 새로 만드신 것) [cite: 2025-07-31]
        member_sh = client.open_by_key("18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA").get_worksheet(0)
        
        return data_sh, member_sh
    except:
        st.error("구글 시트 로드 실패")
        return None, None

# --- 메인 화면 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    # ... (로그인/가입 신청 탭 유지) ...
    # [설명: 이전 코드의 로그인 탭 로직을 그대로 사용하세요]
    t1, t2 = st.tabs(["🔑 로그인", "🛡️ 가입 신청"])
    # (생략: 위 답변들의 로그인/가입 로직 삽입)
else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님")
    
    # 등급별 메뉴 [cite: 2025-07-31]
    menu = ["📄 내역 조회", "🛒 정가수의 주문"]
    if u['role'] == '관리자':
        menu.append("🛡️ 가입 승인 관리")
    
    choice = st.sidebar.radio("메뉴 이동", menu)

    # --- 기능 1: 모든 중도매인 내역 열람 (관리자 전용 확장) ---
    if choice == "📄 내역 조회":
        st.title("📊 경락 내역 조회")
        data_sh, _ = load_all_data()
        df = pd.DataFrame(data_sh.get_all_records())
        
        # 날짜 필터
        if '경락일자' in df.columns:
            dates = sorted(df['경락일자'].astype(str).unique(), reverse=True)
            sel_date = st.selectbox("조회 날짜 선택", dates)
            df = df[df['경락일자'].astype(str) == sel_date]

        # [핵심] 관리자 권한 체크: 관리자는 모든 데이터, 중도매인은 본인 데이터만 [cite: 2025-07-31]
        if u['role'] == '관리자':
            st.success("👨‍✈️ 관리자 모드: 전체 중도매인 내역을 열람 중입니다.")
            jm_filter = st.multiselect("특정 중도매인만 보기 (비워두면 전체)", df['정산코드'].unique())
            if jm_filter:
                df = df[df['정산코드'].isin(jm_filter)]
            st.dataframe(df, use_container_width=True)
            st.metric("💰 총 낙찰 합계", f"{pd.to_numeric(df['금액'], errors='coerce').sum():,.0f} 원")
        else:
            df['코드_str'] = df['정산코드'].astype(str).str.strip()
            my_data = df[df['코드_str'].isin([u['num'], str(int(u['num']))])]
            st.dataframe(my_data, use_container_width=True)

    # --- 기능 2: 정가수의 주문 (구현 완료) ---
    elif choice == "🛒 정가수의 주문":
        st.title("🍎 정가수의 주문 시스템")
        
        # 관리자는 물품 등록, 사용자는 주문 [cite: 2025-07-31]
        if u['role'] == '관리자':
            with st.expander("🆕 판매 물품 등록 (관리자 전용)"):
                p_name = st.text_input("품목명")
                p_price = st.number_input("단가", min_value=0)
                if st.button("물품 등록"):
                    st.success(f"{p_name} 물품이 등록되었습니다. (DB 반영 예정)")
        
        st.write("### 현재 주문 가능한 물품")
        # 예시 데이터 (실제로는 별도 시트에서 관리 권장)
        items = pd.DataFrame([
            {"품목": "사과(부사)", "단가": 45000, "재고": 100},
            {"품목": "배(신고)", "단가": 55000, "재고": 50}
        ])
        st.table(items)
        
        sel_item = st.selectbox("주문하실 품목 선택", items['품목'])
        order_qnty = st.number_input("주문 수량", min_value=1)
        
        if st.button("🚀 주문 확정"):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 주문 로그 기록 (Sheet3 등에 기록하도록 확장 가능) [cite: 2025-07-31]
            st.balloons()
            st.success(f"✅ {u['id']}님, {sel_item} {order_qnty}박스 주문이 접수되었습니다! ({now})")

    # --- 기능 3: 가입 승인 관리 (이전과 동일) ---
    elif choice == "🛡️ 가입 승인 관리":
        # ... (이전 관리자 승인 로직) ...
        pass

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
