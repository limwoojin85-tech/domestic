import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
import time

# --- 1. 구글 시트 연결 및 캐싱 설정 ---
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

# 데이터를 60초 동안 캐싱하여 API 호출 횟수를 줄입니다.
@st.cache_data(ttl=60)
def load_sheet_data(sheet_key, gid=0):
    try:
        client = get_gspread_client()
        sh = client.open_by_key(sheet_key).get_worksheet(gid)
        return pd.DataFrame(sh.get_all_records())
    except Exception as e:
        if "429" in str(e):
            st.error("⚠️ 구글 API 호출 한도 초과! 1분 뒤에 자동으로 다시 시도합니다.")
            time.sleep(5) # 잠시 대기 후 리트라이 유도
        return pd.DataFrame()

# 시트 객체만 가져오는 함수 (쓰기 작업용)
def get_sheet_object(sheet_key, gid=0):
    client = get_gspread_client()
    return client.open_by_key(sheet_key).get_worksheet(gid)

# --- 2. 앱 설정 및 데이터 로드 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
DATA_SID = st.secrets["spreadsheet_id"]

# 데이터 로딩 (캐시 적용)
members_df = load_sheet_data(MEMBER_SID)
order_df = load_sheet_data(ORDER_SID)
records_df = load_sheet_data(DATA_SID)

if records_df.empty and not members_df.empty: # 데이터 로드 실패 시 대응
    st.warning("데이터를 불러오는 중입니다. 잠시만 기다려주세요...")
    st.button("🔄 새로고침")

# --- [이후 로직은 이전과 동일하되, 쓰기 발생 시 캐시 삭제 추가] ---
# ... (로그인 로직 생략) ...

if 'user' in st.session_state:
    # (메뉴 선택 로직 생략)
    choice = st.sidebar.radio("메뉴", ["📄 내역 조회", "✍️ 주문서 작성", "🛒 주문 신청", "⚙️ 가입 승인 관리"])

    if choice == "✍️ 주문서 작성":
        st.header("📝 새 주문서 발행")
        with st.form("order_create"):
            pn = st.text_input("품목명")
            ps = st.text_input("규격")
            pp = st.number_input("단가", min_value=0)
            pq = st.number_input("총 수량", min_value=1)
            if st.form_submit_button("🚀 발주하기"):
                try:
                    order_sh = get_sheet_object(ORDER_SID)
                    order_sh.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), pn, ps, pp, pq, "판매중"])
                    st.success("발주 완료!")
                    st.cache_data.clear() # 쓰기 작업 후 캐시를 비워 최신 데이터를 불러오게 함
                except Exception as e:
                    st.error(f"저장 실패: {e}")

    # ... (내역 조회 및 다른 기능들) ...
