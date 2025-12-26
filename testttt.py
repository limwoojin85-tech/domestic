import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import traceback
from datetime import datetime

# --- 1. 구글 시트 및 API 연결 설정 ---
def get_gspread_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Secrets에서 가져온 Private Key의 줄바꿈 문자 정제 [cite: 2025-07-31]
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
        st.error("🔥 [시스템 오류] 구글 인증에 실패했습니다. Secrets를 확인하세요.")
        st.code(traceback.format_exc())
        return None

def load_all_sheets():
    try:
        client = get_gspread_client()
        if not client: return None, None
        sh = client.open_by_key(st.secrets["spreadsheet_id"])
        # Sheet1: 경락 데이터(조회용), Sheet2: 회원 정보(로그인/권한용) [cite: 2025-07-31]
        return sh.get_worksheet(0), sh.get_worksheet(1)
    except Exception:
        st.error("🔥 [시스템 오류] 시트를 불러오지 못했습니다.")
        st.code(traceback.format_exc())
        return None, None

# --- 2. 카카오 인증 로직 (인가 코드 처리) ---
KAKAO_KEY = st.secrets["kakao"]["rest_api_key"]
REDIRECT_URI = st.secrets["kakao"]["redirect_uri"].strip()

def get_kakao_login_url():
    # KOE006 에러 방지를 위해 REDIRECT_URI 일치 확인 필수 [cite: 2025-07-31]
    return f"https://kauth.kakao.com/oauth/authorize?client_id={KAKAO_KEY}&redirect_uri={REDIRECT_URI}&response_type=code"

def get_kakao_user_info(code):
    try:
        token_url = "https://kauth.kakao.com/oauth/token"
        headers = {"Content-type": "application/x-www-form-urlencoded;charset=utf-8"}
        data = {
            "grant_type": "authorization_code",
            "client_id": KAKAO_KEY,
            "redirect_uri": REDIRECT_URI,
            "code": code
        }
        token_res = requests.post(token_url, headers=headers, data=data).json()
        
        if "access_token" not in token_res:
            st.error(f"❌ 카카오 토큰 획득 실패: {token_res}")
            return None, None

        user_url = "https://kapi.kakao.com/v2/user/me"
        user_headers = {"Authorization": f"Bearer {token_res['access_token']}"}
        user_res = requests.get(user_url, headers=user_headers).json()
        return str(user_res.get("id")), user_res.get("properties", {}).get("nickname")
    except Exception:
        st.error("🔥 카카오 정보 획득 중 오류 발생")
        st.code(traceback.format_exc())
        return None, None

# --- 3. 메인 인터페이스 및 등급 권한 로직 ---
st.set_page_config(page_title="인천농산물 통합 플랫폼", layout="wide")

# URL 파라미터에서 카카오 인증 코드 확인
query_params = st.query_params
auth_code = query_params.get("code")

if 'user' not in st.session_state:
    st.title("🍎 인천농산물 통합 관리 시스템")
    
    tab1, tab2 = st.tabs(["🔑 기존 로그인", "🛡️ 카카오 가입 신청"])
    
    with tab1:
        st.subheader("로그인")
        id_input = st.text_input("아이디 (i+번호, 예: i002)").strip()
        pw_input = st.text_input("비밀번호", type="password").strip()
        
        if st.button("로그인 실행", use_container_width=True):
            _, auth_sh = load_all_sheets()
            if auth_sh:
                # Sheet2에서 회원 정보 조회 [cite: 2025-07-31]
                users = pd.DataFrame(auth_sh.get_all_values())
                users.columns = users.iloc[0]
                users = users[1:]
                
                # 매칭 로직 (아이디, 비밀번호 확인) [cite: 2025-07-31]
                match = users[(users['아이디'].astype(str).str.strip() == id_input) & 
                              (users['비밀번호'].astype(str).str.strip() == pw_input)]
                
                if not match.empty:
                    row = match.iloc[0]
                    # 승인 여부 확인 (Y인 경우만 통과) [cite: 2025-07-31]
                    if row['승인여부'] == 'Y':
                        st.session_state.user = {
                            "id": row['아이디'],
                            "role": row['등급'], # 관리자, 중도매인, 관련종사자 등 [cite: 2025-07-31]
                            "num": row['아이디'].replace('i', '')
                        }
                        st.rerun()
                    else:
                        st.warning("⏳ 아직 승인 대기 중입니다. 관리자 승인 후 이용 가능합니다.")
                else:
                    st.error("❌ 아이디 또는 비밀번호가 올바르지 않습니다.")

    with tab2:
        st.subheader("카카오 본인 인증 및 신청")
        st.write("카카오 계정으로 본인 확인 후 가입을 신청합니다.")
        st.link_button("카카오로 1초 만에 신청하기", get_kakao_login_url(), use_container_width=True)
        
        if auth_code:
            k_id, k_nick = get_kakao_user_info(auth_code)
            if k_id:
                st.success(f"✅ 인증 성공: {k_nick}님")
                target_num = st.text_input("본인의 중도매인 번호 입력 (예: 002)")
                if st.button("가입 신청 완료"):
                    _, auth_sh = load_all_sheets()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Sheet2에 로그 저장: 아이디, 비번(임시), 카카오ID, 닉네임, 승인(N), 등급(미정), 날짜 [cite: 2025-07-31]
                    auth_sh.append_row([f"i{target_num.zfill(3)}", target_num.zfill(3), k_id, k_nick, "N", "중도매인", now])
                    st.balloons()
                    st.info("신청이 기록되었습니다. 관리자가 확인 후 승인해 드립니다.")

else:
    # --- 로그인 성공 시: 등급별 대시보드 ---
    user = st.session_state.user
    st.sidebar.title(f"👤 {user['id']}")
    st.sidebar.info(f"등급: {user['role']}")
    
    # 등급별 사이드바 메뉴 구성 [cite: 2025-07-31]
    menu = ["📄 내역 조회"]
    if user['role'] in ['중도매인', '관리자']:
        menu.append("🛒 물품 주문하기")
    if user['role'] == '관리자':
        menu.append("⚙️ 시스템 관리")
    
    choice = st.sidebar.radio("메뉴 이동", menu)
    
    if st.sidebar.button("로그아웃"):
        del st.session_state.user
        st.rerun()

    # --- 기능 1: 경락 내역 조회 (과거 내역 포함) ---
    if choice == "📄 내역 조회":
        st.title(f"📊 {user['num']}번 중도매인 경락 내역")
        data_sh, _ = load_all_sheets()
        if data_sh:
            try:
                # 2025년 전체 데이터가 담긴 시트 로드 [cite: 2025-07-31]
                df = pd.DataFrame(data_sh.get_all_records())
                
                # 날짜 선택 필터 (과거 내역 조회 기능) [cite: 2025-07-31]
                if '경락일자' in df.columns:
                    dates = sorted(df['경락일자'].astype(str).unique(), reverse=True)
                    selected_date = st.selectbox("조회 날짜 선택", dates)
                    df = df[df['경락일자'].astype(str) == selected_date]

                # 정산코드 필터링 (002, 2 모두 대응)
                df['정산코드_str'] = df['정산코드'].astype(str).str.strip()
                target = user['num'].strip()
                try: target_int = str(int(target))
                except: target_int = target
                
                my_data = df[(df['정산코드_str'] == target) | (df['정산코드_str'] == target_int)]
                
                if not my_data.empty:
                    st.success(f"조회 성공: 총 {len(my_data)}건")
                    st.dataframe(my_data[['품목명', '출하자', '중량', '등급', '단가', '수량', '금액']], use_container_width=True)
                    total = pd.to_numeric(my_data['금액'], errors='coerce').sum()
                    st.metric("💰 총 낙찰 금액", f"{total:,.0f} 원")
                else:
                    st.warning("선택한 날짜에 해당 중도매인의 내역이 없습니다.")
            except Exception:
                st.error("데이터 조회 중 오류 발생")
                st.code(traceback.format_exc())

    # --- 기능 2: 물품 주문하기 (주문 플랫폼 확장) ---
    elif choice == "🛒 물품 주문하기":
        st.title("🍎 신선 물품 주문하기")
        st.write("중도매인 전용 물품 주문 페이지입니다. (준비 중)")
        st.info("카카오톡 비즈니스 채널 주문하기 기능과 연동될 예정입니다.")
        # [ Image of a fruit and vegetable ordering interface on a mobile phone screen ]
        item_list = ["사과", "배", "포도", "딸기"] # 예시 품목
        selected_item = st.selectbox("주문 품목 선택", item_list)
        qnty = st.number_input("주문 수량", min_value=1, value=1)
        if st.button("주문 신청"):
            st.success(f"{selected_item} {qnty}건 주문 신청이 완료되었습니다.")

    # --- 기능 3: 시스템 관리 (관리자 전용) ---
    elif choice == "⚙️ 시스템 관리":
        st.title("⚙️ 관리자 제어판")
        st.write("가입 승인 및 회원 등급을 관리합니다.")
        _, auth_sh = load_all_sheets()
        if auth_sh:
            users_df = pd.DataFrame(auth_sh.get_all_values())
            st.write("### 현재 회원 및 승인 대기 목록")
            st.dataframe(users_df)
            st.info("💡 위 목록에서 승인여부를 Y로, 등급을 관리자/중도매인 등으로 시트에서 직접 수정하세요.")
