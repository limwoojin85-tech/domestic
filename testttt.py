import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
import time

# --- 1. 구글 시트 연결 설정 (오류 방지 강화) ---
@st.cache_resource
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
    except Exception as e:
        st.error(f"⚠️ Secrets 설정 또는 인증 오류: {e}")
        return None

@st.cache_data(ttl=60)
def load_data(sheet_key, gid=0):
    client = get_gspread_client()
    if client:
        try:
            sh = client.open_by_key(sheet_key).get_worksheet(gid)
            data = sh.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"⚠️ 데이터 읽기 오류 (ID: {sheet_key[:5]}...): {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# --- 2. 초기 앱 설정 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
DATA_SID = st.secrets.get("spreadsheet_id", "")

if not DATA_SID:
    st.error("❌ 'spreadsheet_id'가 Secrets에 설정되지 않았습니다.")
    st.stop()

# 데이터 로드 진행 바
with st.spinner('데이터를 불러오는 중입니다...'):
    members_df = load_data(MEMBER_SID)
    records_df = load_data(DATA_SID)
    # 주문 시트는 자주 업데이트되므로 별도 관리
    client = get_gspread_client()
    order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
    order_df = pd.DataFrame(order_sh.get_all_records())

# --- 3. 로그인 로직 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    t1, t2 = st.tabs(["🔑 로그인", "📝 가입 신청"])
    
    with t1:
        with st.form("login"):
            u_id = st.text_input("아이디").strip()
            u_pw = st.text_input("비밀번호", type="password").strip()
            if st.form_submit_button("로그인"):
                if not members_df.empty:
                    match = members_df[members_df['아이디'] == u_id]
                    if not match.empty:
                        row = match.iloc[0]
                        if str(row['비밀번호']) == u_pw:
                            if str(row['승인여부']).upper() == 'Y':
                                st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                                st.rerun()
                            else: st.warning("승인 대기 중")
                        else: st.error("비번 오류")
                    else: st.error("아이디 없음")

    with t2:
        with st.form("reg"):
            ni, npw, nn, nr = st.text_input("아이디"), st.text_input("비번"), st.text_input("닉네임"), st.selectbox("등급", ["중도매인", "회사 관계자"])
            if st.form_submit_button("신청하기"):
                member_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                member_sh.append_row([ni, npw, "", nn, "N", nr, datetime.now().strftime("%Y-%m-%d")])
                st.success("신청 완료")

# --- 4. 메인 화면 (로그인 후) ---
else:
    u = st.session_state.user
    role = u['role']
    if u['id'] == 'limwoojin85':
        m = st.sidebar.radio("🧪 모드 전환", ["관리자 모드", "중도매인 모드"])
        role = "관리자" if "관리자" in m else "중도매인"

    choice = st.sidebar.radio("메뉴", ["📄 내역 조회", "✍️ 주문서 작성", "🛒 주문 신청", "⚙️ 가입 승인 관리"])

    if choice == "📄 내역 조회":
        st.header("📊 내역 조회")
        df = records_df.copy()
        if not df.empty:
            df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
            mode = st.radio("조회 방식", ["당일", "기간"])
            if mode == "당일":
                d = st.date_input("날짜", date.today())
                df = df[df['경락일자'].dt.date == d]
            else:
                p = st.date_input("기간", [date.today() - timedelta(days=7), date.today()])
                if len(p) == 2: df = df[(df['경락일자'].dt.date >= p[0]) & (df['경락일자'].dt.date <= p[1])]
            
            s_idx = st.text_input("번호 색인", "").zfill(3) if role == "관리자" else u['num'].zfill(3)
            if s_idx != "000": df = df[df['정산코드'].astype(str).str.zfill(3) == s_idx]
            st.dataframe(df)
        else: st.info("데이터가 없습니다.")

    elif choice == "✍️ 주문서 작성":
        with st.form("w"):
            pn, ps, pp, pq = st.text_input("품목"), st.text_input("규격"), st.number_input("단가"), st.number_input("수량")
            if st.form_submit_button("발주"):
                order_sh.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), pn, ps, pp, pq, "판매중"])
                st.success("발주 완료")
                st.cache_data.clear()

    elif choice == "⚙️ 가입 승인 관리":
        wait_df = members_df[members_df['승인여부'] == 'N'].copy()
        if not wait_df.empty:
            all_s = st.checkbox("전체")
            sel = [r['아이디'] for i, r in wait_df.iterrows() if st.checkbox(f"{r['닉네임']}({r['아이디']})", value=all_s)]
            if st.button("승인"):
                m_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                all_v = m_sh.get_all_values()
                for tid in sel:
                    for idx, rv in enumerate(all_v):
                        if rv[0] == tid: m_sh.update_cell(idx+1, 5, 'Y')
                st.success("완료")
                st.cache_data.clear()
                st.rerun()

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
