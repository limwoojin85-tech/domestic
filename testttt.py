import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta

# --- 1. 구글 시트 연결 및 데이터 로드 ---
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

def load_all_data_raw():
    client = get_gspread_client()
    MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
    member_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
    # 다른 시트들은 기존 secrets 설정 유지
    data_sh = client.open_by_key(st.secrets["spreadsheet_id"]).get_worksheet(0)
    order_sh = client.open_by_key("1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU").get_worksheet(0)
    return data_sh, member_sh, order_sh

st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

try:
    data_sh, member_sh, order_sh = load_all_data_raw()
    members_df = pd.DataFrame(member_sh.get_all_records())
except Exception as e:
    st.error(f"데이터 로드 오류: {e}")
    st.stop()

# --- 2. 로그인 및 가입 신청 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    t1, t2 = st.tabs(["🔑 로그인", "📝 가입 신청"])
    
    with t1:
        with st.form("login_form"):
            u_id = st.text_input("아이디 (i+번호)").strip()
            u_pw = st.text_input("비밀번호", type="password").strip()
            if st.form_submit_button("로그인", use_container_width=True):
                # 시트 구조: 아이디(0), 비밀번호(1), 승인여부(4), 등급(5)
                match = members_df[members_df['아이디'] == u_id]
                if not match.empty:
                    row = match.iloc[0]
                    if str(row['비밀번호']) == str(u_pw):
                        if str(row['승인여부']).upper() == 'Y':
                            st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                            st.rerun()
                        else: st.warning("⏳ 승인 대기 중입니다.")
                    else: st.error("❌ 비밀번호가 틀렸습니다.")
                else: st.error("❌ 아이디를 찾을 수 없습니다.")

    with t2:
        with st.form("reg_form"):
            ni = st.text_input("아이디 (예: i005)")
            npw = st.text_input("비밀번호", type="password")
            nn = st.text_input("닉네임/상호")
            nr = st.selectbox("등급", ["중도매인", "회사 관계자"])
            if st.form_submit_button("신청하기"):
                # 시트 구조에 맞게 7개 컬럼 맞춰서 입력
                member_sh.append_row([ni, npw, "", nn, "N", nr, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                st.success("✅ 신청 완료! 관리자 승인 후 로그인 가능합니다.")

# --- 3. 메인 화면 ---
else:
    u = st.session_state.user
    role = u['role']
    if u['id'] == 'limwoojin85':
        m = st.sidebar.radio("🧪 테스터 모드", ["관리자", "중도매인"])
        role = "관리자" if m == "관리자" else "중도매인"

    menu = ["📄 내역 조회", "✍️ 주문서 작성", "🛒 주문 신청", "⚙️ 가입 승인 관리"] if role == "관리자" else ["📄 내역 조회", "🛒 주문 신청"]
    choice = st.sidebar.radio("메뉴", menu)

    # --- 가입 승인 관리 (시트 구조 최적화) ---
    if choice == "⚙️ 가입 승인 관리":
        st.header("⚙️ 가입 신청 승인")
        # 승인여부(4번째 인덱스)가 'N'인 데이터만 추출
        wait_df = members_df[members_df['승인여부'] == 'N'].copy()
        
        if wait_df.empty:
            st.info("현재 대기자가 없습니다.")
        else:
            all_sel = st.checkbox("전체 선택")
            sel_ids = []
            for i, r in wait_df.iterrows():
                # 닉네임과 아이디 표시
                is_chk = st.checkbox(f"{r['닉네임']} ({r['아이디']}) - 등급: {r['등급']}", value=all_sel, key=f"c_{r['아이디']}")
                if is_chk: sel_ids.append(r['아이디'])
            
            if st.button("✅ 선택한 사용자 일괄 승인"):
                if sel_ids:
                    all_vals = member_sh.get_all_values()
                    for tid in sel_ids:
                        for idx, row in enumerate(all_vals):
                            if row[0] == tid:
                                # 승인여부는 5번째 열 (index 5, 1-based index이므로 5)
                                member_sh.update_cell(idx+1, 5, 'Y')
                    st.success(f"🎉 {len(sel_ids)}명 승인 완료!")
                    st.rerun()
                else:
                    st.warning("승인할 대상을 선택하세요.")

    # (기존 내역 조회, 주문서 작성 로직 유지...)
    # ...
