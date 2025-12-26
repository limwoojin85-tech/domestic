import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime

# --- 1. 구글 및 카카오 설정 로드 ---
def get_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

def get_auth_sheet():
    sh = get_client().open_by_key(st.secrets["spreadsheet_id"])
    return sh.get_worksheet(1) # Sheet2 (계정 및 로그 관리)

# --- 2. 카카오 로그인 API 로직 ---
KAKAO_KEY = st.secrets["kakao"]["rest_api_key"]
REDIRECT_URI = st.secrets["kakao"]["redirect_uri"]

def get_kakao_login_url():
    return f"https://kauth.kakao.com/oauth/authorize?client_id={KAKAO_KEY}&redirect_uri={REDIRECT_URI}&response_type=code"

def get_kakao_user_info(code):
    # 1. 토큰 요청
    token_url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_KEY,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }
    res = requests.post(token_url, data=data).json()
    access_token = res.get("access_token")
    
    # 2. 사용자 정보(고유 ID) 요청
    user_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    user_res = requests.get(user_url, headers=headers).json()
    return str(user_res.get("id")), user_res.get("properties", {}).get("nickname")

# --- 메인 화면 ---
st.set_page_config(page_title="인천농산물 승인 시스템")

# URL 파라미터에서 카카오 인증 코드 확인
query_params = st.query_params
auth_code = query_params.get("code")

if 'user_id' not in st.session_state:
    st.title("🍎 중도매인 스마트 인증")
    st.write("카카오 로그인 후 가입 신청을 완료해 주세요.")
    
    login_url = get_kakao_login_url()
    st.markdown(f'<a href="{login_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FEE500;color:#000000;padding:12px;border-radius:8px;text-align:center;font-weight:bold;cursor:pointer;">카카오로 가입 신청하기</div></a>', unsafe_allow_html=True)

    if auth_code:
        with st.spinner("신원 확인 중..."):
            kakao_id, nickname = get_kakao_user_info(auth_code)
            auth_sh = get_auth_sheet()
            users_df = pd.DataFrame(auth_sh.get_all_records())
            
            # 이미 등록된 사용자인지 확인
            existing_user = users_df[users_df['카카오ID'].astype(str) == kakao_id]
            
            if existing_user.empty:
                st.warning(f"안녕하세요, {nickname}님! 가입 신청을 위해 정산코드를 입력해 주세요.")
                user_num = st.text_input("정산코드 (예: 002)")
                if st.button("신청 완료"):
                    # Sheet2에 로그 기록 (카카오ID, 닉네임, 정산코드, 신청일시, 승인여부)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    auth_sh.append_row([kakao_id, nickname, user_num, now, "N"])
                    st.success("✅ 신청이 완료되었습니다! 관리자 승인 후 조회가 가능합니다.")
            else:
                status = existing_user.iloc[0]['승인여부']
                if status == "Y":
                    st.session_state.user_id = existing_user.iloc[0]['정산코드']
                    st.rerun()
                else:
                    st.error("⏳ 아직 관리자의 승인을 기다리는 중입니다.")
else:
    # --- 승인된 사용자 데이터 조회 화면 ---
    st.title(f"📊 {st.session_state.user_id}번 경락 내역")
    # (기존 데이터 필터링 로직 실행)
    if st.button("로그아웃"):
        del st.session_state.user_id
        st.rerun()
