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
    DATA_SID = st.secrets["spreadsheet_id"]
    MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
    ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
    
    data_sh = client.open_by_key(DATA_SID).get_worksheet(0)
    member_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
    order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
    
    return data_sh, member_sh, order_sh

st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# 데이터 로드 (승인 처리를 위해 시트 객체를 직접 가져옴)
try:
    data_sh, member_sh, order_sh = load_all_data_raw()
    records_df = pd.DataFrame(data_sh.get_all_records())
    members_df = pd.DataFrame(member_sh.get_all_records())
except Exception as e:
    st.error(f"데이터 연결 오류: {e}")
    st.stop()

# --- 2. 로그인 및 가입 신청 시스템 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    tab1, tab2 = st.tabs(["🔑 로그인", "📝 가입 신청"])
    
    with tab1:
        with st.form("login_form"):
            u_id = st.text_input("아이디 (i+번호)").strip()
            u_pw = st.text_input("비밀번호", type="password").strip()
            if st.form_submit_button("로그인", use_container_width=True):
                match = members_df[(members_df['아이디'] == u_id) & (members_df['비밀번호'].astype(str) == str(u_pw))]
                if not match.empty:
                    row = match.iloc[0]
                    if str(row['승인여부']).upper() == 'Y':
                        st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                        st.rerun()
                    else: st.warning("⏳ 승인 대기 중입니다.")
                else: st.error("❌ 정보를 다시 확인해 주세요.")
                
    with tab2:
        st.subheader("회원 가입 신청")
        with st.form("register_form"):
            new_id = st.text_input("아이디 (예: i002)").strip()
            new_pw = st.text_input("비밀번호", type="password").strip()
            new_name = st.text_input("성함/상호").strip()
            new_role = st.selectbox("등급 선택", ["중도매인", "회사관계자"])
            if st.form_submit_button("신청하기"):
                if new_id and new_pw and new_name:
                    member_sh.append_row([new_id, new_pw, new_role, "N", new_name])
                    st.success("✅ 신청 완료! 관리자 승인 후 로그인하세요.")
                else: st.warning("모든 항목을 입력해 주세요.")

# --- 3. 로그인 후 메인 화면 ---
else:
    u = st.session_state.user
    st.sidebar.title(f"👤 {u['id']}님")
    
    # 테스터/limwoojin85 모드 전환
    current_role = u['role']
    if u['id'] == 'limwoojin85' or u['role'] == '테스터':
        mode_toggle = st.sidebar.radio("🛠️ 모드 선택", ["회사관계자 모드", "중도매인 모드"])
        current_role = "관리자" if mode_toggle == "회사관계자 모드" else "중도매인"

    menu = ["📄 내역 조회", "✍️ 주문서 작성", "🛒 주문 신청", "⚙️ 가입 승인 관리"] if current_role == "관리자" else ["📄 내역 조회", "🛒 주문 신청"]
    choice = st.sidebar.radio("메뉴", menu)

    # --- 메뉴 1. 내역 조회 ---
    if choice == "📄 내역 조회":
        st.header(f"📊 {choice}")
        df = records_df.copy()
        df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
        df['중도매인번호'] = df['정산코드'].astype(str).str.zfill(3)
        c1, c2 = st.columns(2)
        with c1:
            search_idx = st.text_input("🔍 번호 색인", "").strip().zfill(3) if current_role == "관리자" else u['num'].zfill(3)
        with c2:
            period = st.date_input("📅 기간", [date.today() - timedelta(days=7), date.today()])
        
        if len(period) == 2:
            df = df[(df['경락일자'].dt.date >= period[0]) & (df['경락일자'].dt.date <= period[1])]
        if search_idx != "000":
            df = df[df['중도매인번호'] == search_idx]
        st.dataframe(df.sort_values('경락일자', ascending=False), use_container_width=True)

    # --- 메뉴 2. 주문서 작성 ---
    elif choice == "✍️ 주문서 작성":
        st.header("📝 새 주문서 발행")
        with st.form("new_order"):
            c1, c2 = st.columns(2)
            p_name, p_spec = c1.text_input("품목명"), c2.text_input("규격")
            p_price, p_qnty = c1.number_input("단가", min_value=0), c2.number_input("수량", min_value=1)
            if st.form_submit_button("🚀 발주"):
                order_sh.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), p_name, p_spec, p_price, p_qnty, "판매중"])
                st.success("발주 완료")

    # --- 메뉴 3. 주문 신청 ---
    elif choice == "🛒 주문 신청":
        st.header("🛒 구매 신청")
        order_data = pd.DataFrame(order_sh.get_all_records())
        if not order_data.empty:
            active = order_data[order_data['상태'] == '판매중']
            for idx, row in active.iterrows():
                with st.expander(f"📦 {row['품목명']} ({row['규격']})"):
                    q = st.number_input(f"수량", min_value=0, max_value=int(row['수량']), key=f"q_{idx}")
                    if st.button("신청", key=f"b_{idx}"):
                        st.success(f"{q}개 신청 완료")

    # --- 메뉴 4. 가입 승인 관리 (체크박스 일괄 승인 기능 추가) ---
    elif choice == "⚙️ 가입 승인 관리":
        st.header("⚙️ 가입 신청 승인 처리")
        
        # 승인 대기자(N)만 필터링
        wait_df = members_df[members_df['승인여부'] == 'N'].copy()
        
        if wait_df.empty:
            st.info("현재 승인 대기 중인 신청자가 없습니다.")
        else:
            st.write(f"총 {len(wait_df)}명의 대기자가 있습니다.")
            
            # 1. 전체 선택 체크박스
            all_selected = st.checkbox("전체 선택")
            
            # 2. 개별 체크박스를 포함한 리스트 생성
            selected_ids = []
            for idx, row in wait_df.iterrows():
                # 체크박스 상태 결정
                is_checked = st.checkbox(f"[{row['등급']}] {row['이름/상호']} (ID: {row['아이디']})", value=all_selected, key=f"chk_{row['아이디']}")
                if is_checked:
                    selected_ids.append(row['아이디'])
            
            # 3. 승인 버튼
            if st.button("✅ 선택한 사용자 일괄 승인", use_container_width=True):
                if not selected_ids:
                    st.warning("승인할 사용자를 선택해 주세요.")
                else:
                    # 구글 시트 업데이트 (속도 향상을 위해 행 번호 찾아서 직접 수정)
                    all_data = member_sh.get_all_values() # 헤더 포함 전체
                    for target_id in selected_ids:
                        for i, row in enumerate(all_data):
                            if row[0] == target_id: # 아이디가 일치하면
                                # D열(4번째 열)이 승인여부
                                member_sh.update_cell(i+1, 4, 'Y') 
                    
                    st.success(f"🎉 {len(selected_ids)}명의 가입 승인이 완료되었습니다!")
                    st.balloons()
                    st.rerun()

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
