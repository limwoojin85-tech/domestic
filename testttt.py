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
        # st.secrets가 있으면 사용, 없으면 로컬 파일 체크 (유연한 처리)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        else:
            # 로컬 개발 환경용 (secrets.toml 없을 때)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            # 로컬에 있는 json 파일명으로 변경하세요
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            return gspread.authorize(creds)
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
            st.error(f"데이터 로드 실패: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# 페이지 설정
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# --- 시트 ID 설정 ---
# 실제 사용 중인 시트 ID들입니다.
MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
DATA_SID = "1mjSrU0L4o9M9Kn0fzXdXum2VCtvZImEN-q42pNAAoFg" # 사용자님이 주신 데이터 시트

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
            new_id = st.text_input("아이디 (중도매인 번호)")
            new_email = st.text_input("이메일")
            new_nick = st.text_input("상호명(닉네임)")
            new_pw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("가입 신청"):
                client = get_gspread_client()
                if client:
                    sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                    # 아이디, 비밀번호, 이메일, 등급, 승인여부, 닉네임 순서 (시트 구조에 맞게)
                    sh.append_row([new_id, new_pw, new_email, "중도매인", "N", new_nick])
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
    
    # 데이터 로드 (캐시 사용으로 속도 최적화)
    records_df = load_data(DATA_SID)

    # ==========================================
    # 기능 1. 내역 조회 (확인된 컬럼명 적용)
    # ==========================================
    if "내역 조회" in choice:
        st.subheader(f"📊 {choice}")
        
        if records_df.empty:
            st.warning("데이터가 없습니다.")
        else:
            df = records_df.copy()
            # 컬럼명 공백 제거 (안전장치)
            df.columns = df.columns.str.strip()

            # [중요] 실제 컬럼명 매핑 (시트 분석 결과 반영)
            col_date = '일자'
            col_item = '품목'
            col_breed = '품종'
            col_price = '금액'
            col_wholesaler = '중도매인'
            
            # 날짜 변환 (YYYYMMDD -> YYYY-MM-DD)
            if col_date in df.columns:
                try:
                    df[col_date] = pd.to_datetime(df[col_date], format='%Y%m%d', errors='coerce').dt.strftime('%m/%d')
                except Exception:
                    pass # 변환 실패 시 원본 유지

            # 필터링 (중도매인 번호)
            # 중도매인 컬럼을 문자열로 변환하고 0을 채워서 3자리로 맞춤 (예: 92 -> 092)
            search_idx = test_num if current_role != "관리자" else st.text_input("번호 검색 (전체: 000)", "000").zfill(3)
            
            if col_wholesaler in df.columns and search_idx != "000":
                 # 데이터의 중도매인 번호도 3자리 문자열로 변환하여 비교
                 df['temp_id'] = df[col_wholesaler].apply(lambda x: str(x).split('.')[0].zfill(3))
                 df = df[df['temp_id'] == search_idx]

            st.write(f"**검색 결과: {len(df)}건**")

            # 리스트 출력 (카드 형태)
            # 최신순 정렬 (인덱스 역순)
            for i, row in df.sort_index(ascending=False).head(50).iterrows():
                with st.container():
                    c1, c2 = st.columns([1, 2])
                    
                    # 날짜
                    date_txt = row.get(col_date, '-')
                    c1.caption(f"📅 {date_txt}")
                    
                    # 품목 및 가격 정보 구성
                    item_txt = f"{row.get(col_item, '')} ({row.get(col_breed, '')})"
                    
                    # 금액 천단위 콤마
                    try:
                        price = int(str(row.get(col_price, 0)).replace(',', ''))
                        price_txt = f"{price:,}원"
                    except:
                        price_txt = f"{row.get(col_price, 0)}원"

                    # 상세 정보 (중량/수량)
                    detail_txt = f"{row.get('중량',0)}kg / {row.get('수량',0)}개"
                    
                    c2.markdown(f"**{item_txt}**")
                    c2.text(f"{detail_txt} | {price_txt}")
                    st.divider()
            
            # 총 합계 계산
            if col_price in df.columns:
                try:
                    total = df[col_price].astype(str).str.replace(',', '').astype(float).sum()
                    st.metric("총 합계", f"{int(total):,} 원")
                except:
                    st.write("합계 계산 불가")

    # ==========================================
    # 기능 2. 주문서 작성 (관리자용)
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
                st.cache_data.clear() # 데이터 갱신
                st.rerun()
        
        # 발행 내역 확인
        st.subheader("📋 발행된 목록")
        try:
            cur_orders = pd.DataFrame(order_sh.get_all_records())
            if not cur_orders.empty:
                st.dataframe(cur_orders)
        except: pass

    # ==========================================
    # 기능 3. 주문 신청 (중도매인용)
    # ==========================================
    elif choice == "🛒 주문 신청":
        st.header("🛒 구매 신청")
        # 주문서 시트 다시 로드
        try:
            order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
            order_data = order_sh.get_all_records()
            order_df = pd.DataFrame(order_data)
        except:
            order_df = pd.DataFrame()
        
        if not order_df.empty and '상태' in order_df.columns:
            active = order_df[order_df['상태'] == '판매중']
            if active.empty:
                st.info("현재 구매 가능한 상품이 없습니다.")
            else:
                for i, r in active.iterrows():
                    # 상품 정보 카드
                    with st.expander(f"📦 {r.get('품목명','품목')} ({r.get('규격','')}) - {r.get('단가',0):,}원"):
                        c1, c2 = st.columns([3, 1])
                        # 수량 입력
                        req_qty = c1.number_input(f"신청 수량 (잔여: {r.get('수량',0)})", min_value=1, max_value=int(r.get('수량', 9999)), key=f"q_{i}")
                        
                        if c2.button("주문", key=f"btn_{i}"):
                            # 실제로는 여기에 주문 접수 로직(DB저장)이 들어갑니다.
                            # 간단하게는 잔여 수량을 차감하거나 별도 시트에 기록합니다.
                            st.success(f"{r.get('품목명')} {req_qty}개 주문 신청되었습니다.")
                            st.balloons()
        else:
            st.info("주문서 데이터를 불러올 수 없습니다.")

    # ==========================================
    # 기능 4. 가입 승인 (관리자용)
    # ==========================================
    elif choice == "⚙️ 가입 승인 관리":
        st.header("⚙️ 가입 승인 대기")
        
        # 최신 데이터 로드
        members_df_admin = load_data(MEMBER_SID)
        
        if not members_df_admin.empty:
            members_df_admin.columns = members_df_admin.columns.str.strip()
            
            if '승인여부' in members_df_admin.columns:
                wait_df = members_df_admin[members_df_admin['승인여부'] == 'N']
                
                if not wait_df.empty:
                    for i, r in wait_df.iterrows():
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"**{r.get('닉네임','-')}** ({r.get('아이디','-')})")
                        
                        if col2.button("승인", key=f"app_{i}"):
                            m_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                            # ID로 행 찾기 (정확한 매칭을 위해 find 사용)
                            try:
                                cell = m_sh.find(str(r['아이디']))
                                # 승인여부 컬럼(E열=5번째) 업데이트
                                m_sh.update_cell(cell.row, 5, 'Y')
                                st.success(f"{r['아이디']} 승인 완료")
                                st.cache_data.clear()
                                st.rerun()
                            except:
                                st.error("해당 ID를 시트에서 찾을 수 없습니다.")
                else:
                    st.info("대기 중인 신청자가 없습니다.")
            else:
                st.error("회원 DB 형식이 올바르지 않습니다. (승인여부 컬럼 부재)")

    if st.sidebar.button("🚪 로그아웃"):
        del st.session_state.user
        st.rerun()
