import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback

# --- 1. 구글 시트 연결 설정 ---
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
    except Exception:
        st.error("🔥 구글 인증 오류")
        st.code(traceback.format_exc())
        return None

def load_data():
    client = get_gspread_client()
    sh = client.open_by_key(st.secrets["spreadsheet_id"])
    return sh.get_worksheet(0), sh.get_worksheet(1) # Sheet1(데이터), Sheet2(회원)

# --- 메인 화면 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 로그인")
    input_id = st.text_input("아이디 (i+번호)").strip()
    input_pw = st.text_input("비밀번호", type="password").strip()
    
    if st.button("로그인", use_container_width=True):
        _, auth_sh = load_data()
        users = pd.DataFrame(auth_sh.get_all_records())
        # 필드: 아이디, 비밀번호, 등급(관리자/중도매인/관계자), 승인여부(Y/N)
        match = users[(users['아이디'] == input_id) & (users['비밀번호'] == input_pw)]
        
        if not match.empty:
            row = match.iloc[0]
            if row['승인여부'] == 'Y':
                st.session_state.user = {
                    "id": row['아이디'],
                    "role": row['등급'],
                    "num": row['아이디'].replace('i', '')
                }
                st.rerun()
            else:
                st.warning("⏳ 아직 승인되지 않은 계정입니다. 관리자에게 문의하세요.")
        else:
            st.error("❌ 정보가 올바르지 않습니다.")
else:
    user = st.session_state.user
    st.sidebar.title(f"👤 {user['id']} ({user['role']})")
    
    # 등급별 메뉴 구성 [cite: 2025-07-31]
    menu_options = ["🏠 홈", "📄 경락 내역 조회"]
    if user['role'] in ['중도매인', '관리자']:
        menu_options.append("🛒 물품 주문하기")
    if user['role'] == '관리자':
        menu_options.append("⚙️ 시스템 관리")
    
    choice = st.sidebar.radio("메뉴 이동", menu_options)

    if choice == "📄 경락 내역 조회":
        st.header("🔍 경락 내역 조회 (과거 내역 포함)")
        data_sh, _ = load_data()
        df = pd.DataFrame(data_sh.get_all_records())
        
        # [과거 내역 확장] 날짜 필터 추가
        if '경락일자' in df.columns:
            target_date = st.date_input("조회할 날짜 선택")
            df = df[df['경락일자'].astype(str) == target_date.strftime("%Y%m%d")]

        # 본인 데이터 필터링
        df['코드_str'] = df['정산코드'].astype(str).str.strip()
        my_data = df[df['코드_str'].isin([user['num'], str(int(user['num']))])]
        st.dataframe(my_data, use_container_width=True)

    elif choice == "🛒 물품 주문하기":
        st.header("🍎 신선 물품 주문")
        st.info("카카오톡 주문하기와 연동될 예정입니다.")
        # 주문 폼 구현 예정 영역

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
