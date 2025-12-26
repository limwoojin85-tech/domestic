import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 보안 설정 (Streamlit Secrets 사용) ---
def get_gspread_client():
    # [수정] 파일 대신 Streamlit Secrets에 저장된 정보를 딕셔너리로 가져옴
    creds_dict = st.secrets["gcp_service_account"]
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# --- 나머지 로직은 이전과 동일 (데이터 로드 부분만 수정) ---
def load_data_from_google():
    try:
        client = get_gspread_client()
        SPREADSHEET_ID = st.secrets["spreadsheet_id"] # 시트 ID도 보안 처리
        sh = client.open_by_key(SPREADSHEET_ID)
        worksheet = sh.sheet1
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return None

# ... (이하 로그인 및 필터링 로직은 기존과 동일) ...