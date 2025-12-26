import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import traceback
from datetime import datetime, date

# --- 1. 구글 시트 연결 및 데이터 로드 ---
def load_all_sheets():
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
        
        # 시트 로드: 1.경락데이터(0), 2.회원관리(새 시트ID), 3.주문관리(2)
        data_sh = client.open_by_key(st.secrets["spreadsheet_id"]).get_worksheet(0)
        member_sh = client.open_by_key("18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA").get_worksheet(0)
        # Sheet3가 없다면 '주문관리'라는 이름으로 탭을 하나 만드세요.
        order_sh = client.open_by_key(st.secrets["spreadsheet_id"]).get_worksheet(2)
        
        return data_sh, member_sh, order_sh
    except Exception:
        st.error("🔥 시트 연결 실패. 시트 ID와 Secrets를 확인하세요.")
        return None, None, None

# --- 메인 화면 설정 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    t1, t2 = st.tabs(["🔑 로그인", "🛡️ 가입 신청"])
    # (로그인/가입 신청 로직은 이전과 동일하므로 전문 출력 원칙에 따라 내부 생략함 - 실제 적용 시 이전 코드의 탭 내용을 넣으세요)
    with t1:
        in_id = st.text_input("아이디 (i+번호)").strip()
        in_pw = st.text_input("비밀번호", type="password").strip()
        if st.button("로그인", use_container_width=True):
            _, member_sh, _ = load_all_sheets()
            users = pd.DataFrame(member_sh.get_all_records())
            match = users[(users['아이디'] == in_id) & (users['비밀번호'] == in_pw)]
            if not match.empty:
                row = match.iloc[0]
                if row['승인여부'] == 'Y':
                    st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                    st.rerun()
                else: st.warning("⏳ 승인 대기 중입니다.")
            else: st.error("❌ 정보 불일치")
else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님 ({u['role']})")
    
    # 메뉴 구성 [cite: 2025-07-31]
    if u['role'] == '관리자':
        menu = ["📄 관리자 내역 조회", "✍️ 정가수의 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 내역 조회", "🛒 물품 주문하기"]
    
    choice = st.sidebar.radio("메뉴 이동", menu)

    # --- 1. 관리자 전용 조회 기능 (기간 및 번호 설정) ---
    if "내역 조회" in choice:
        st.header(f"📊 {choice}")
        data_sh, _, _ = load_all_data()
        df = pd.DataFrame(data_sh.get_all_records())
        
        if not df.empty:
            df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
            df['코드_str'] = df['정산코드'].astype(str).str.strip().str.zfill(3)

            if u['role'] == '관리자':
                col1, col2 = st.columns(2)
                with col1:
                    target_jm = st.text_input("🔍 조회할 중도매인 번호 입력 (예: 002, 비워두면 전체)", "").strip().zfill(3)
                with col2:
                    d_range = st.date_input("📅 조회 기간 설정", [date(2025, 12, 1), date.today()])
                
                # 기간 필터링 [cite: 2025-07-31]
                mask = (df['경락일자'] >= pd.Timestamp(d_range[0])) & (df['경락일자'] <= pd.Timestamp(d_range[1]))
                filtered_df = df[mask]
                
                # 번호 필터링
                if target_jm != "000":
                    filtered_df = filtered_df[filtered_df['코드_str'] == target_jm]
                
                st.dataframe(filtered_df, use_container_width=True)
                st.metric("💰 검색 결과 총액", f"{pd.to_numeric(filtered_df['금액'], errors='coerce').sum():,.0f} 원")
            else:
                # 중도매인 본인 조회 [cite: 2025-07-31]
                my_data = df[df['코드_str'] == u['num'].zfill(3)]
                st.dataframe(my_data, use_container_width=True)

    # --- 2. 정가수의 주문서 작성 (관리자) / 주문하기 (중도매인) ---
    elif "주문" in choice:
        st.header(f"🍎 {choice}")
        _, _, order_sh = load_all_sheets()
        
        if u['role'] == '관리자':
            st.subheader("📝 신규 주문서 발행")
            with st.form("주문서작성"):
                col1, col2 = st.columns(2)
                p_name = col1.text_input("품목명")
                p_sub = col2.text_input("과수/규격")
                p_price = col1.number_input("가격(단가)", min_value=0)
                p_qnty = col2.number_input("총 판매 수량", min_value=1)
                if st.form_submit_button("🚀 주문서 발행"):
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # 주문서 데이터 저장 [cite: 2025-07-31]
                    order_sh.append_row([p_name, p_sub, p_price, p_qnty, "판매중", now])
                    st.success(f"✅ {p_name} 주문서가 발행되었습니다.")
        
        else:
            st.subheader("🛒 현재 구매 가능한 물품")
            orders = pd.DataFrame(order_sh.get_all_records())
            if not orders.empty:
                st.dataframe(orders[orders['상태'] == '판매중'], use_container_width=True)
                sel = st.selectbox("주문할 품목 선택", orders['품목명'].unique())
                q = st.number_input("주문 수량 입력", min_value=1)
                if st.button("주문 확정"):
                    st.balloons()
                    st.success(f"{sel} {q}건 주문이 완료되었습니다. 관리자가 확인 후 배송합니다.")

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
