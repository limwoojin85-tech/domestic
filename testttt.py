import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import traceback
from datetime import datetime

# --- 1. 구글 시트 연결 (모든 시트 통합 로드) ---
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
        
        # 1. 경락데이터 (Sheet1), 2. 회원관리 (회원 시트), 3. 주문관리 (Sheet3)
        data_sh = client.open_by_key(st.secrets["spreadsheet_id"]).get_worksheet(0)
        member_sh = client.open_by_key("18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA").get_worksheet(0)
        # 주문용 시트가 없다면 수동으로 '주문관리' 탭을 만들어주세요.
        try: order_sh = client.open_by_key(st.secrets["spreadsheet_id"]).get_worksheet(2)
        except: order_sh = None
        
        return data_sh, member_sh, order_sh
    except Exception:
        st.error("구글 시트 연결 실패")
        st.code(traceback.format_exc())
        return None, None, None

# --- 메인 화면 설정 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    t1, t2 = st.tabs(["🔑 로그인", "🛡️ 가입 신청"])
    
    with t1:
        in_id = st.text_input("아이디 (i+번호)").strip()
        in_pw = st.text_input("비밀번호", type="password").strip()
        if st.button("로그인", use_container_width=True):
            _, member_sh, _ = load_all_data()
            all_vals = member_sh.get_all_values()
            headers = [h.strip() for h in all_vals[0]]
            users = pd.DataFrame(all_vals[1:], columns=headers)
            match = users[(users['아이디'] == in_id) & (users['비밀번호'] == in_pw)]
            
            if not match.empty:
                row = match.iloc[0]
                if row['승인여부'] == 'Y':
                    st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                    st.rerun()
                else: st.warning("⏳ 승인 대기 중입니다.")
            else: st.error("❌ 정보를 확인하세요.")
    # (가입 신청 탭 로직은 이전과 동일하게 유지)
else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님 ({u['role']})")
    
    menu = ["📄 내역 조회", "🛒 정가수의 주문"]
    if u['role'] == '관리자': menu.append("⚙️ 가입 승인 관리")
    choice = st.sidebar.radio("메뉴 이동", menu)

    # --- 기능 1: 내역 조회 (ValueError 수정 완료) ---
    if choice == "📄 내역 조회":
        st.header("📊 경락 내역 조회")
        data_sh, _, _ = load_all_data()
        df = pd.DataFrame(data_sh.get_all_records())
        
        if not df.empty:
            # 안전한 필터링 로직 [cite: 2025-07-31]
            df['정산코드_str'] = df['정산코드'].astype(str).str.strip().str.zfill(3)
            
            if u['role'] == '관리자':
                st.info("👨‍✈️ 관리자: 전체 중도매인 데이터를 열람합니다.")
                st.dataframe(df, use_container_width=True)
            else:
                target_num = u['num'].zfill(3)
                my_data = df[df['정산코드_str'] == target_num]
                st.dataframe(my_data, use_container_width=True)
                if not my_data.empty:
                    st.metric("💰 총 낙찰 합계", f"{pd.to_numeric(my_data['금액'], errors='coerce').sum():,.0f} 원")

    # --- 기능 2: 정가수의 주문 (관리자/중도매인 분리) ---
    elif choice == "🛒 정가수의 주문":
        st.header("🍎 정가수의 주문 플랫폼")
        _, _, order_sh = load_all_data()
        
        if u['role'] == '관리자':
            st.subheader("🛠️ [관리자] 판매 물품 등록")
            with st.form("물품등록"):
                p_name = st.text_input("품목명 (예: 사과 부사)")
                p_price = st.number_input("단가", min_value=0)
                p_stock = st.number_input("등록 수량", min_value=1)
                if st.form_submit_button("물품 등록하기"):
                    order_sh.append_row([p_name, p_price, p_stock, "판매중", datetime.now().strftime("%Y-%m-%d")])
                    st.success(f"{p_name} 등록 완료!")
        
        else:
            st.subheader("🛒 [중도매인] 물품 주문하기")
            if order_sh:
                items_df = pd.DataFrame(order_sh.get_all_records())
                if not items_df.empty:
                    sel_item = st.selectbox("품목 선택", items_df['품목명'])
                    order_qnty = st.number_input("주문 수량", min_value=1)
                    if st.button("🚀 주문 신청"):
                        st.balloons()
                        st.success(f"{sel_item} {order_qnty}개 주문이 완료되었습니다.")
                else:
                    st.warning("현재 등록된 판매 물품이 없습니다.")

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
