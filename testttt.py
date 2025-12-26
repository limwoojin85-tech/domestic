import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import traceback
from datetime import datetime

# --- 1. 구글 및 카카오 설정 로드 (Secrets 연동) ---
def get_gspread_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Secrets의 private_key 내 줄바꿈(\n) 처리
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
        st.error("🔥 구글 서비스 계정 인증 오류")
        st.code(traceback.format_exc())
        return None

def load_all_sheets():
    try:
        client = get_gspread_client()
        if not client: return None, None
        sh = client.open_by_key(st.secrets["spreadsheet_id"])
        # index 기반: 0은 첫 번째 탭, 1은 두 번째 탭
        return sh.get_worksheet(0), sh.get_worksheet(1)
    except Exception:
        st.error("🔥 구글 시트 로드 실패")
        st.code(traceback.format_exc())
        return None, None

# --- 2. 카카오 인증 설정 및 로직 ---
KAKAO_KEY = st.secrets["kakao"]["rest_api_key"]
REDIRECT_URI = st.secrets["kakao"]["redirect_uri"].strip()

def get_kakao_login_url():
    # KOE006 에러 방지를 위해 REDIRECT_URI를 정확히 인코딩하여 전달
    return f"https://kauth.kakao.com/oauth/authorize?client_id={KAKAO_KEY}&redirect_uri={REDIRECT_URI}&response_type=code"

def get_kakao_user_info(code):
    try:
        # 액세스 토큰 받기
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

        # 사용자 정보 받기
        user_url = "https://kapi.kakao.com/v2/user/me"
        user_headers = {"Authorization": f"Bearer {token_res['access_token']}"}
        user_res = requests.get(user_url, headers=user_headers).json()
        return str(user_res.get("id")), user_res.get("properties", {}).get("nickname")
    except Exception:
        st.error("🔥 카카오 정보 획득 중 시스템 오류")
        st.code(traceback.format_exc())
        return None, None

# --- 3. 웹 서비스 메인 화면 ---
st.set_page_config(page_title="인천농산물 경락조회시스템", layout="wide")

# 카카오 인가 코드 처리 (Redirect 후 실행됨)
query_params = st.query_params
auth_code = query_params.get("code")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🍎 인천농산물 본인 확인")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("기존 로그인")
        id_input = st.text_input("아이디 (i+번호, 예: i002)").strip()
        pw_input = st.text_input("비밀번호", type="password").strip()
        if st.button("로그인", use_container_width=True):
            _, auth_sh = load_all_sheets()
            if auth_sh:
                users = pd.DataFrame(auth_sh.get_all_values())
                users.columns = users.iloc[0]
                users = users[1:]
                match = users[(users['아이디'].astype(str).str.strip() == id_input) & 
                              (users['비밀번호'].astype(str).str.strip() == pw_input)]
                if not match.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_num = id_input.replace('i', '')
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 틀립니다.")

    with col2:
        st.subheader("신규 가입 및 승인 신청")
        st.link_button("카카오로 본인인증 신청하기", get_kakao_login_url(), use_container_width=True)
        
        # 카카오에서 돌아온 경우 처리
        if auth_code:
            k_id, k_nick = get_kakao_user_info(auth_code)
            if k_id:
                st.success(f"✅ 인증 성공: {k_nick}님")
                target_num = st.text_input("본인의 중도매인 번호 입력 (예: 002)")
                if st.button("최종 가입 신청"):
                    _, auth_sh = load_all_sheets()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Sheet2에 저장: 아이디, 비밀번호(초기), 카카오ID, 닉네임, 승인여부(N), 신청일
                    auth_sh.append_row([f"i{target_num.zfill(3)}", target_num.zfill(3), k_id, k_nick, "N", now])
                    st.balloons()
                    st.info("신청이 완료되었습니다! 관리자 승인 후 조회가 가능합니다.")

else:
    # --- 로그인 성공: 데이터 필터링 화면 ---
    st.sidebar.title(f"👤 {st.session_state.user_num}번님")
    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False
        st.rerun()

    st.title(f"📊 오늘 경락 내역 현황")
    data_sh, _ = load_all_sheets()
    if data_sh:
        try:
            df = pd.DataFrame(data_sh.get_all_records())
            df['정산코드_str'] = df['정산코드'].astype(str).str.strip()
            target = st.session_state.user_num.strip()
            try: target_int = str(int(target))
            except: target_int = target
            
            my_data = df[(df['정산코드_str'] == target) | (df['정산코드_str'] == target_int)]
            
            if not my_data.empty:
                st.success(f"총 {len(my_data)}건의 내역이 조회되었습니다.")
                st.dataframe(my_data[['품목명', '출하자', '중량', '단가', '수량', '금액']], use_container_width=True)
                total = pd.to_numeric(my_data['금액'], errors='coerce').sum()
                st.metric("💰 총 낙찰 금액", f"{total:,.0f} 원")
            else:
                st.warning("오늘 낙찰된 경락 내역이 없습니다.")
        except Exception:
            st.error("데이터 필터링 중 오류 발생")
            st.code(traceback.format_exc())
