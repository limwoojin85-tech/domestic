import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import random

# --- 1. 구글 시트 연결 설정 ---
@st.cache_resource
def get_gspread_client():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        else:
            st.error("secrets.toml 파일 설정이 필요합니다.")
            return None
    except Exception as e:
        st.error(f"인증 오류: {e}")
        return None

def load_data(sheet_key, gid=0):
    client = get_gspread_client()
    if client:
        try:
            sh = client.open_by_key(sheet_key).get_worksheet(gid)
            data = sh.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            return pd.DataFrame()
    return pd.DataFrame()

# 페이지 설정
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# --- 시트 ID 설정 ---
MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
DATA_SID = st.secrets.get("spreadsheet_id", "1mjSrU0L4o9M9Kn0fzXdXum2VCtvZImEN-q42pNAAoFg")

# --- 2. 로그인 및 회원가입 로직 ---
if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리")
    members_df = load_data(MEMBER_SID)
    
    tab1, tab2 = st.tabs(["🔑 로그인", "📝 가입 신청"])
    
    with tab1:
        with st.form("login_form"):
            u_id = st.text_input("아이디").strip()
            u_pw = st.text_input("비밀번호", type="password").strip()
            if st.form_submit_button("로그인"):
                if members_df.empty:
                    st.error("회원 DB 접속 실패")
                else:
                    # 컬럼 공백 제거
                    members_df.columns = members_df.columns.str.strip()
                    match = members_df[members_df['아이디'] == u_id]
                    
                    if not match.empty and str(match.iloc[0]['비밀번호']) == u_pw:
                        row = match.iloc[0]
                        if str(row['승인여부']).upper() == 'Y':
                            st.session_state.user = {
                                "id": row['아이디'], 
                                "role": row['등급'], 
                                "num": str(row['아이디']).replace('i','') 
                            }
                            st.rerun()
                        else: st.warning("승인 대기 중입니다.")
                    else: st.error("정보가 일치하지 않습니다.")
    
    with tab2:
        st.info("신규 회원가입")
        with st.form("signup_form"):
            new_id = st.text_input("아이디 (숫자 권장)")
            new_email = st.text_input("이메일")
            new_nick = st.text_input("상호명(닉네임)")
            if st.form_submit_button("가입 신청"):
                client = get_gspread_client()
                if client:
                    sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                    sh.append_row([new_id, "0000", new_email, "테스터", "N", new_nick])
                    st.success("신청되었습니다. 관리자 승인을 기다리세요.")

# --- 3. 메인 화면 ---
else:
    u = st.session_state.user
    client = get_gspread_client()
    
    # [권한 설정]
    current_role = u['role']
    test_num = u.get('num', '000').zfill(3)

    if u['id'] == 'limwoojin85' or u['role'] == '테스터':
        st.sidebar.markdown("### 🧪 관리자 메뉴")
        mode_select = st.sidebar.radio("모드 전환", ["관리자 모드", "중도매인 모드"])
        current_role = "관리자" if "관리자" in mode_select else "중도매인"
        if current_role == "중도매인":
            test_num = st.sidebar.text_input("테스트 중도매인 번호", test_num).zfill(3)

    # 메뉴 구성
    if current_role == "관리자":
        menu = ["📄 통합 내역 조회", "✍️ 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 개인 내역 조회", "🛒 주문 신청"]
    
    choice = st.sidebar.selectbox("메뉴 선택", menu)
    records_df = load_data(DATA_SID)

    # ==========================================
    # 기능 1. 내역 조회 (수정됨: 컬럼 자동 찾기)
    # ==========================================
    if "내역 조회" in choice:
        st.subheader(f"📊 {choice}")
        
        if records_df.empty:
            st.warning("데이터가 없습니다.")
        else:
            df = records_df.copy()
            df.columns = df.columns.str.strip() # 공백 제거

            # [핵심 수정] 컬럼명 자동 찾기 로직
            def find_col(candidates):
                for c in candidates:
                    if c in df.columns: return c
                return None

            col_date = find_col(['경락일자', '일자', 'date', 'Date', 'PAHSPADT'])
            col_item = find_col(['품목', '품목명', 'PRODNAME', 'ITEMNAME'])
            col_price = find_col(['금액', '낙찰금액', 'price', 'PAHSAMNT'])
            col_code = find_col(['중도매인', '정산코드', '중도매인코드', 'PAHSJMCD'])

            # 필수 컬럼 없으면 경고
            if not (col_date and col_item and col_price):
                st.error("필수 컬럼(일자, 품목, 금액)을 찾을 수 없습니다.")
                st.write("현재 컬럼:", list(df.columns))
            else:
                # 날짜 변환
                try:
                    df[col_date] = pd.to_datetime(df[col_date], format='%Y%m%d', errors='coerce').dt.strftime('%m/%d')
                except: pass

                # 필터링
                search_idx = test_num if current_role != "관리자" else st.text_input("번호 검색 (전체: 000)", "000").zfill(3)
                
                if col_code and search_idx != "000":
                     df = df[df[col_code].astype(str).str.zfill(3) == search_idx]

                st.write(f"**검색 결과: {len(df)}건**")

                # 리스트 출력
                for i, row in df.sort_index(ascending=False).head(20).iterrows():
                    with st.container():
                        c1, c2 = st.columns([1, 2])
                        c1.caption(f"📅 {row[col_date]}")
                        
                        # [수정] 천단위 콤마 처리 안전하게
                        price_val = row[col_price]
                        try:
                            price_fmt = f"{int(float(str(price_val).replace(',',''))):,}원"
                        except:
                            price_fmt = f"{price_val}원"

                        c2.markdown(f"**{row[col_item]}** | {price_fmt}")
                        st.divider()
                
                # 합계
                try:
                    total = pd.to_numeric(df[col_price].astype(str).str.replace(',',''), errors='coerce').sum()
                    st.metric("총 합계", f"{total:,.0f} 원")
                except: pass

    # ==========================================
    # 기능 2. 주문서 작성 (복구됨)
    # ==========================================
    elif choice == "✍️ 주문서 작성":
        st.header("📝 오늘의 주문서 발행")
        order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
        
        with st.form("order_write"):
            col1, col2 = st.columns(2)
            pn = col1.text_input("품목명 (예: 사과)")
            ps = col2.text_input("규격 (예: 10kg)")
            pp = col1.number_input("단가", min_value=0, step=100)
            pq = col2.number_input("가능 수량", min_value=0)
            
            if st.form_submit_button("발행하기"):
                # 날짜, 품목, 규격, 단가, 수량, 상태
                order_sh.append_row([datetime.now().strftime("%Y-%m-%d"), pn, ps, pp, pq, "판매중"])
                st.success(f"{pn} 주문서가 등록되었습니다.")
                st.rerun()
        
        # 현재 등록된 주문서 확인
        st.markdown("---")
        st.subheader("📋 현재 판매 중인 목록")
        try:
            cur_orders = order_sh.get_all_records()
            if cur_orders:
                st.dataframe(pd.DataFrame(cur_orders))
        except: pass

    # ==========================================
    # 기능 3. 주문 신청 (유지)
    # ==========================================
    elif choice == "🛒 주문 신청":
        st.header("🛒 구매 신청")
        order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
        order_data = order_sh.get_all_records()
        order_df = pd.DataFrame(order_data)
        
        if not order_df.empty and '상태' in order_df.columns:
            active = order_df[order_df['상태'] == '판매중']
            if active.empty:
                st.info("현재 구매 가능한 상품이 없습니다.")
            else:
                for i, r in active.iterrows():
                    with st.expander(f"📦 {r.get('품목명','품목')} ({r.get('규격','규격')}) - {r.get('단가',0):,}원"):
                        c1, c2 = st.columns([3, 1])
                        req_qty = c1.number_input(f"수량 (잔여: {r.get('수량',0)})", min_value=0, key=f"q_{i}")
                        if c2.button("주문", key=f"btn_{i}"):
                            st.success(f"{r.get('품목명')} {req_qty}개 주문 신청되었습니다.")
                            # 실제로는 여기에 '주문내역 시트'에 append_row 하는 로직이 들어감
        else:
            st.info("주문서 데이터를 불러올 수 없습니다.")

    # ==========================================
    # 기능 4. 가입 승인 (수정됨: NameError 해결)
    # ==========================================
    elif choice == "⚙️ 가입 승인 관리":
        st.header("⚙️ 신규 가입 승인")
        # [수정] 변수 다시 로드해서 NameError 방지
        members_df_admin = load_data(MEMBER_SID) 
        
        if not members_df_admin.empty:
            members_df_admin.columns = members_df_admin.columns.str.strip()
            # 승인여부 컬럼이 있는지 확인
            if '승인여부' in members_df_admin.columns:
                wait_df = members_df_admin[members_df_admin['승인여부'] == 'N']
                
                if not wait_df.empty:
                    for i, r in wait_df.iterrows():
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"**{r.get('닉네임','이름없음')}** ({r['아이디']}) - {r.get('이메일','-')}")
                        if col2.button("승인 처리", key=f"app_{i}"):
                            m_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                            # 시트에서 해당 아이디 행 찾기 (헤더 제외하므로 +2 보정 필요할 수 있음)
                            cell = m_sh.find(str(r['아이디']))
                            if cell:
                                # 승인여부 컬럼(E열=5번째 라고 가정)을 Y로 변경
                                m_sh.update_cell(cell.row, 5, 'Y') 
                                st.success(f"{r['아이디']} 승인 완료")
                                st.rerun()
                            else:
                                st.error("시트에서 행을 찾을 수 없습니다.")
                else:
                    st.info("대기 중인 신청자가 없습니다.")
            else:
                st.error("회원 DB에 '승인여부' 컬럼이 없습니다.")
        else:
            st.error("회원 정보를 불러오지 못했습니다.")

    if st.sidebar.button("🚪 로그아웃"):
        del st.session_state.user
        st.rerun()
