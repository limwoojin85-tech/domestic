import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# --- 1. 기본 설정 및 인증 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# 시트 ID (사용자 환경에 맞게 유지)
MEMBER_SID = "18j4vlva8sqbmP0h5Dgmjm06d1A83dgvcm239etoMalA"
ORDER_SID = "1jUwyFR3lge51ko8OGidbSrlN0gsjprssl4pYG-X4ITU"
DATA_SID = "1mjSrU0L4o9M9Kn0fzXdXum2VCtvZImEN-q42pNAAoFg"

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
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            return gspread.authorize(creds)
    except Exception as e:
        st.error(f"인증 오류: {e}")
        return None

# 데이터 로드 함수 (캐시 사용하되, 필요시 클리어 가능하게 ttl 설정)
@st.cache_data(ttl=60) 
def load_data(sheet_key, gid=0):
    client = get_gspread_client()
    if client:
        try:
            sh = client.open_by_key(sheet_key).get_worksheet(gid)
            data = sh.get_all_records()
            return pd.DataFrame(data)
        except: return pd.DataFrame()
    return pd.DataFrame()

# --- 2. 로그인 및 회원가입 ---
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
                                "id": row['아이디'], "role": row['등급'], 
                                "num": str(row['아이디']).replace('i','') 
                            }
                            st.rerun()
                        else: st.warning("승인 대기 중입니다.")
                    else: st.error("정보 불일치")
    
    with tab2:
        with st.form("signup_form"):
            new_id = st.text_input("아이디 (중도매인 번호)")
            new_email = st.text_input("이메일")
            new_nick = st.text_input("상호명(닉네임)")
            new_pw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("가입 신청"):
                client = get_gspread_client()
                if client:
                    sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                    sh.append_row([new_id, new_pw, new_email, "중도매인", "N", new_nick])
                    st.success("신청 완료. 승인 대기.")

# --- 3. 메인 화면 ---
else:
    u = st.session_state.user
    client = get_gspread_client()
    
    # 권한 및 테스트 모드 설정
    current_role = u['role']
    test_num = u.get('num', '000').zfill(3)

    if u['id'] == 'limwoojin85' or u['role'] == '테스터':
        with st.sidebar.expander("🛠️ 관리자/테스터 설정", expanded=True):
            mode_select = st.radio("모드 전환", ["관리자 모드", "중도매인 모드"])
            current_role = "관리자" if "관리자" in mode_select else "중도매인"
            if current_role == "중도매인":
                test_num = st.text_input("테스트 번호", test_num).zfill(3)

    # 메뉴 구성
    if current_role == "관리자":
        menu = ["📄 통합 내역 조회", "✍️ 주문서 작성", "⚙️ 가입 승인 관리"]
    else:
        menu = ["📄 개인 내역 조회", "🛒 주문 신청"]
    
    choice = st.sidebar.selectbox("메뉴 선택", menu)
    
    # ==========================================
    # 기능 1. 내역 조회 (UI 최적화 + 기간 설정 복구)
    # ==========================================
    if "내역 조회" in choice:
        st.subheader(f"📊 {choice}")
        
        # 1. 기간 설정 UI (당일 우선)
        col_t1, col_t2 = st.columns([1, 3])
        date_mode = col_t1.radio("조회 기간", ["오늘", "기간 설정"], label_visibility="collapsed", horizontal=True)
        
        today_str = datetime.now().strftime("%Y%m%d")
        search_date_start = today_str
        search_date_end = today_str

        if date_mode == "기간 설정":
            d_range = col_t2.date_input("날짜 선택", [datetime.now(), datetime.now()], label_visibility="collapsed")
            if len(d_range) == 2:
                search_date_start = d_range[0].strftime("%Y%m%d")
                search_date_end = d_range[1].strftime("%Y%m%d")
        
        # 2. 데이터 로드 및 전처리
        records_df = load_data(DATA_SID)
        
        if records_df.empty:
            st.info("데이터가 없습니다.")
        else:
            df = records_df.copy()
            df.columns = df.columns.str.strip()

            # 컬럼 매핑
            c_date = '일자'
            c_item = '품목'
            c_breed = '품종'
            c_price = '금액'
            c_qty = '수량'
            c_weight = '중량'
            c_code = '중도매인'

            # 날짜 필터링 (문자열 비교)
            if c_date in df.columns:
                df[c_date] = df[c_date].astype(str)
                df = df[(df[c_date] >= search_date_start) & (df[c_date] <= search_date_end)]

            # 중도매인 필터링
            search_idx = test_num if current_role != "관리자" else st.text_input("번호 검색 (전체: 000)", "000").zfill(3)
            if c_code in df.columns and search_idx != "000":
                 df['temp_id'] = df[c_code].apply(lambda x: str(x).split('.')[0].zfill(3))
                 df = df[df['temp_id'] == search_idx]

            # 3. UI 최적화 (Dataframe 사용)
            # 불필요한 카드 나열 대신 깔끔한 표로 정리
            st.write(f"**조회 결과: {len(df)}건**")
            
            if not df.empty:
                # 보여줄 컬럼만 추출 및 이름 변경
                display_df = df.copy()
                
                # 날짜 포맷 예쁘게
                display_df['날짜'] = pd.to_datetime(display_df[c_date], format='%Y%m%d', errors='coerce').dt.strftime('%m/%d')
                
                # 품목+품종 합치기
                display_df['상품명'] = display_df[c_item].astype(str) + " (" + display_df[c_breed].astype(str) + ")"
                
                # 규격 합치기
                display_df['규격'] = display_df[c_weight].astype(str) + "kg / " + display_df[c_qty].astype(str) + "개"
                
                # 금액 숫자형
                display_df['금액'] = pd.to_numeric(display_df[c_price].astype(str).str.replace(',',''), errors='coerce')

                # 최종 출력용 컬럼
                final_cols = ['날짜', '상품명', '규격', '금액']
                
                st.dataframe(
                    display_df[final_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "날짜": st.column_config.TextColumn("일자", width="small"),
                        "상품명": st.column_config.TextColumn("품목", width="large"),
                        "규격": st.column_config.TextColumn("규격", width="medium"),
                        "금액": st.column_config.NumberColumn("낙찰가", format="%d원")
                    }
                )
                
                total = display_df['금액'].sum()
                st.info(f"💰 총 합계: {int(total):,}원")
            else:
                st.warning("해당 기간에 데이터가 없습니다.")

    # ==========================================
    # 기능 2. 주문서 작성 (관리자)
    # ==========================================
    elif choice == "✍️ 주문서 작성":
        st.header("📝 오늘의 주문서 발행")
        order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
        
        with st.form("order_write"):
            c1, c2, c3, c4 = st.columns(4)
            pn = c1.text_input("품목명")
            ps = c2.text_input("규격")
            pp = c3.number_input("단가", min_value=0, step=100)
            pq = c4.number_input("수량", min_value=0)
            
            if st.form_submit_button("발행하기"):
                order_sh.append_row([datetime.now().strftime("%Y-%m-%d"), pn, ps, pp, pq, "판매중"])
                st.success("등록되었습니다.")
                st.cache_data.clear() # 캐시 삭제하여 즉시 반영
                time.sleep(0.5)
                st.rerun()

        # 목록 확인
        try:
            cur_orders = pd.DataFrame(order_sh.get_all_records())
            if not cur_orders.empty:
                st.dataframe(cur_orders, use_container_width=True, hide_index=True)
        except: pass

    # ==========================================
    # 기능 3. 주문 신청 (중도매인) - 갱신 문제 해결
    # ==========================================
    elif choice == "🛒 주문 신청":
        col_h1, col_h2 = st.columns([4,1])
        col_h1.header("🛒 구매 신청")
        if col_h2.button("🔄 목록 갱신"):
            st.cache_data.clear()
            st.rerun()

        # 데이터 즉시 로드 (캐시 무시 옵션 고려하거나, 위 버튼으로 해결)
        try:
            # 주문서 시트 로드
            order_sh = client.open_by_key(ORDER_SID).get_worksheet(0)
            order_data = order_sh.get_all_records()
            order_df = pd.DataFrame(order_data)
        except: order_df = pd.DataFrame()
        
        if not order_df.empty and '상태' in order_df.columns:
            active = order_df[order_df['상태'] == '판매중']
            if active.empty:
                st.info("현재 판매 중인 상품이 없습니다.")
            else:
                # 카드형 UI 유지하되 컴팩트하게
                for i, r in active.iterrows():
                    with st.container(): # expander 대신 깔끔한 컨테이너
                        c1, c2, c3 = st.columns([3, 1, 1])
                        # 상품 정보
                        info_txt = f"**{r.get('품목명','')}** | {r.get('규격','')} | {r.get('단가',0):,}원"
                        c1.markdown(info_txt)
                        
                        # 수량 입력
                        max_q = int(r.get('수량', 999))
                        req_qty = c2.number_input("수량", min_value=1, max_value=max_q, key=f"q_{i}", label_visibility="collapsed")
                        
                        # 버튼
                        if c3.button("주문", key=f"btn_{i}"):
                            # [여기서 실제 주문 처리 로직 추가 가능]
                            st.success(f"{r.get('품목명')} {req_qty}개 주문 완료!")
                            st.balloons()
                        st.divider()
        else:
            st.warning("주문서 목록을 불러올 수 없습니다. 관리자에게 문의하세요.")

    # ==========================================
    # 기능 4. 가입 승인 (깔끔한 처리)
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
                        with st.container():
                            c1, c2 = st.columns([4, 1])
                            c1.markdown(f"👤 **{r.get('닉네임','-')}** (ID: {r.get('아이디')}) | {r.get('이메일')}")
                            
                            if c2.button("승인", key=f"app_{i}"):
                                try:
                                    m_sh = client.open_by_key(MEMBER_SID).get_worksheet(0)
                                    cell = m_sh.find(str(r['아이디']))
                                    m_sh.update_cell(cell.row, 5, 'Y') # 승인여부 컬럼 업데이트
                                    
                                    st.success(f"{r['아이디']} 승인 완료!")
                                    st.cache_data.clear() # 데이터 갱신
                                    time.sleep(0.5) # 잠시 보여주고
                                    st.rerun() # 즉시 새로고침 (화면에서 사라지게)
                                except Exception as e:
                                    st.error(f"오류 발생: {e}")
                else:
                    st.info("✅ 대기 중인 신청자가 없습니다.")
            else:
                st.error("DB 오류: 승인여부 컬럼 없음")

    if st.sidebar.button("🚪 로그아웃"):
        del st.session_state.user
        st.rerun()
