import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta

# --- 1. 구글 시트 연결 설정 ---
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
        st.error(f"인증 오류: {e}")
        return None

# 데이터 로드 함수 (캐싱 적용)
@st.cache_data(ttl=30)
def load_data(sheet_key, gid=0):
    client = get_gspread_client()
    if client:
        try:
            sh = client.open_by_key(sheet_key).get_worksheet(gid)
            return pd.DataFrame(sh.get_all_records())
        except: return pd.DataFrame()
    return pd.DataFrame()

st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
DATA_SID = st.secrets.get("spreadsheet_id", "")

# --- 2. 로그인 로직 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    members_df = load_data(MEMBER_SID)
    t1, t2 = st.tabs(["🔑 로그인", "📝 가입 신청"])
    
    with t1:
        with st.form("login"):
            u_id = st.text_input("아이디").strip()
            u_pw = st.text_input("비밀번호", type="password").strip()
            if st.form_submit_button("로그인", use_container_width=True):
                match = members_df[members_df['아이디'] == u_id]
                if not match.empty and str(match.iloc[0]['비밀번호']) == u_pw:
                    row = match.iloc[0]
                    if str(row['승인여부']).upper() == 'Y':
                        st.session_state.user = {"id": row['아이디'], "role": row['등급'], "num": row['아이디'].replace('i','')}
                        st.rerun()
                    else: st.warning("승인 대기 중입니다.")
                else: st.error("계정 정보를 확인하세요.")
    # (가입 신청 탭 로직은 기존과 동일)

# --- 3. 로그인 후 메인 화면 ---
else:
    u = st.session_state.user
    client = get_gspread_client()
    
    # [A. 권한 및 모드 설정]
    current_role = u['role']
    test_num = u['num'].zfill(3)

    if u['id'] == 'limwoojin85' or u['role'] == '테스터':
        st.sidebar.markdown("### 🧪 테스터 설정")
        mode_select = st.sidebar.radio("작업 모드", ["회사관계자(관리자)", "중도매인"])
        current_role = "관리자" if "회사관계자" in mode_select else "중도매인"
        if current_role == "중도매인":
            test_num = st.sidebar.text_input("📋 테스트할 번호 입력", u['num']).zfill(3)

    # [B. 모드에 따른 메뉴 리스트 생성 - 실시간 전환 핵심]
    if current_role == "관리자":
        menu = ["📄 통합 내역 조회", "✍️ 주문서 작성 및 관리", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 개인 내역 조회", "🛒 주문 신청"]
    
    choice = st.sidebar.radio("메뉴 이동", menu)

    # 데이터 로드 (주문 데이터는 항상 필요)
    order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
    order_df = pd.DataFrame(order_sh.get_all_records())

    # --- 메뉴 1. 내역 조회 ---
    if "내역 조회" in choice:
        st.header(f"📊 {choice}")
        records_df = load_data(DATA_SID)
        if not records_df.empty:
            df = records_df.copy()
            df['경락일자'] = pd.to_datetime(df['경락일자'], format='%Y%m%d', errors='coerce')
            
            c1, c2 = st.columns(2)
            view_mode = c1.radio("조회 방식", ["당일", "기간"], horizontal=True)
            if view_mode == "당일":
                d = c2.date_input("날짜", date.today())
                df = df[df['경락일자'].dt.date == d]
            else:
                p = c2.date_input("기간", [date.today() - timedelta(days=7), date.today()])
                if len(p) == 2: df = df[(df['경락일자'].dt.date >= p[0]) & (df['경락일자'].dt.date <= p[1])]
            
            search_idx = st.text_input("🔍 번호 색인", "000").zfill(3) if current_role == "관리자" else test_num
            if search_idx != "000":
                df = df[df['정산코드'].astype(str).str.zfill(3) == search_idx]
            
            st.dataframe(df.sort_values('경락일자', ascending=False), use_container_width=True)

    # --- 메뉴 2. 주문서 작성 및 관리 (관리자 전용) ---
    elif choice == "✍️ 주문서 작성 및 관리":
        st.header("📝 주문서 발행 및 발주 내역 관리")
        
        # [신규 주문 작성 창]
        with st.expander("➕ 새 주문서 작성하기", expanded=True):
            with st.form("new_order"):
                c1, c2 = st.columns(2)
                pn, ps = c1.text_input("🍎 품목명"), c2.text_input("📦 규격")
                pp, pq = c1.number_input("💵 단가", min_value=0), c2.number_input("🔢 총 수량", min_value=1)
                if st.form_submit_button("🚀 주문서 발행"):
                    if pn and ps:
                        order_sh.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), pn, ps, pp, pq, "판매중"])
                        st.success("✅ 새로운 주문서가 등록되었습니다.")
                        st.rerun() # 내역 업데이트를 위해 재실행

        # [발주 내역 리스트 및 수정 창]
        st.markdown("---")
        st.subheader("📋 현재 발행된 주문서 내역")
        if not order_df.empty:
            # 엑셀처럼 직접 수정 가능한 데이터 에디터
            edited_df = st.data_editor(order_df, use_container_width=True, num_rows="dynamic")
            
            if st.button("💾 변경사항 시트 저장"):
                # 시트 전체 덮어쓰기 (헤더 포함)
                order_sh.clear()
                order_sh.update([order_df.columns.values.tolist()] + edited_df.values.tolist())
                st.success("🎉 시트에 변경사항이 저장되었습니다!")
                st.cache_data.clear()
        else:
            st.info("등록된 주문서 내역이 없습니다.")

    # --- 메뉴 3. 주문 신청 (중도매인 전용) ---
    elif choice == "🛒 주문 신청":
        st.header("🛒 진행 중인 주문서 목록")
        if not order_df.empty:
            active = order_df[order_df['상태'] == '판매중']
            if active.empty:
                st.info("현재 구매 가능한 품목이 없습니다.")
            else:
                for idx, row in active.iterrows():
                    with st.expander(f"📦 {row['품목명']} ({row['규격']}) - 단가: {row['단가']:,}원"):
                        col_q, col_b = st.columns([3, 1])
                        req_qty = col_q.number_input("신청 수량", min_value=0, max_value=int(row['수량']), key=f"req_{idx}")
                        if col_b.button("구매 확정", key=f"btn_{idx}"):
                            st.balloons()
                            st.success(f"{test_num}번 중도매인님, {row['품목명']} {req_qty}개 신청 완료!")
        else:
            st.info("발행된 주문서가 없습니다.")

    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
