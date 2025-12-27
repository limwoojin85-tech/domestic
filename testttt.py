import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- 1. 기본 설정 및 인증 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼 (커스텀 모드)", layout="wide")

# 시트 ID
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

# --- 2. 로그인 로직 ---
if 'user' not in st.session_state:
    st.title("🔧 화면 최적화 설정 모드")
    members_df = load_data(MEMBER_SID)
    
    with st.form("login_form"):
        u_id = st.text_input("아이디").strip()
        u_pw = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            if members_df.empty:
                st.error("DB 접속 실패")
            else:
                members_df.columns = members_df.columns.str.strip()
                match = members_df[members_df['아이디'] == u_id]
                if not match.empty and str(match.iloc[0]['비밀번호']) == u_pw:
                    row = match.iloc[0]
                    st.session_state.user = {
                        "id": row['아이디'], "role": row['등급'], 
                        "num": str(row['아이디']).replace('i','') 
                    }
                    st.rerun()
                else: st.error("정보 불일치")

# --- 3. 메인 화면 (커스터마이징) ---
else:
    u = st.session_state.user
    
    # 사이드바: 뷰 설정 도구
    st.sidebar.header("🛠️ 뷰 커스터마이징")
    st.sidebar.info("여기서 원하는 컬럼을 선택해서 최적의 화면을 만드세요.")

    # 데이터 로드
    records_df = load_data(DATA_SID)
    
    if records_df.empty:
        st.warning("데이터가 없습니다.")
    else:
        df = records_df.copy()
        df.columns = df.columns.str.strip() # 공백 제거

        # 모든 컬럼 리스트 확보
        all_columns = list(df.columns)
        
        # --- [1] 프리셋 선택 (빠른 설정) ---
        preset_mode = st.sidebar.radio("📱 디바이스 모드 선택", ["PC (상세)", "모바일 (요약)"])
        
        # 기본값 정의 (제가 임의로 잡은 초기값, 여기서 수정하시면 됩니다)
        default_pc = all_columns # PC는 전체 다 보여주기
        # 모바일에 꼭 필요한 것들 추측 (일자, 품목, 금액 등)
        default_mobile = [c for c in all_columns if c in ['일자', '품목', '품종', '중량', '수량', '금액']]

        # 현재 모드에 따른 기본 선택값
        current_defaults = default_pc if preset_mode == "PC (상세)" else default_mobile
        
        # --- [2] 컬럼 상세 제어 (Multiselect) ---
        selected_columns = st.sidebar.multiselect(
            "표시할 항목 선택 (순서 변경 가능)",
            options=all_columns,
            default=[c for c in current_defaults if c in all_columns] # 존재하는 컬럼만
        )

        # --- 메인 컨텐츠 ---
        st.subheader(f"📊 {preset_mode} 뷰 미리보기")
        
        if not selected_columns:
            st.warning("선택된 항목이 없습니다. 사이드바에서 항목을 선택해주세요.")
        else:
            # 1. 데이터 가공 (보여주기용)
            view_df = df[selected_columns].copy()
            
            # 숫자 천단위 콤마 등 포맷팅 (여기서도 적용 가능)
            # 금액 컬럼이 있다면 포맷팅 시도
            if '금액' in view_df.columns:
                try:
                    view_df['금액'] = pd.to_numeric(view_df['금액'].astype(str).str.replace(',',''), errors='coerce')
                except: pass

            # 2. 화면 출력 (반응형 테이블)
            # st.dataframe은 컬럼별 정렬, 너비 조절이 가능해서 탐색에 유리
            st.dataframe(
                view_df, 
                use_container_width=True, # 화면 꽉 차게
                hide_index=True,
                column_config={
                    "금액": st.column_config.NumberColumn(format="%d원"),
                    "단가": st.column_config.NumberColumn(format="%d원"),
                }
            )

            # 3. [개발자용] 설정값 추출기
            st.divider()
            st.markdown("### 💾 설정 저장용 코드")
            st.markdown("현재 화면 구성이 마음에 드시면, 아래 코드를 복사해서 저에게(AI) 알려주세요. **'이 리스트를 모바일 기본값으로 해줘'** 라고 하시면 됩니다.")
            
            # 리스트를 문자열로 변환해서 출력
            code_snippet = str(selected_columns)
            st.code(code_snippet, language='python')

    # 기타 기능 (주문서 등은 잠시 숨김 처리하거나 하단에 배치)
    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()
