import streamlit as st
import pandas as pd
import plotly.express as px
import re
import io
import os
import datetime
import json
import unicodedata
from google.cloud import firestore
from google.oauth2 import service_account

# ==========================================
# ⚙️ 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="LOPY 트렌드 & 가격방어 봇", page_icon="📈", layout="wide")

DB_FILE = "lopy_trend_db.csv"
APP_ID = "lopy-trend-dashboard" # 클라우드 데이터 구분용 ID

# 중국어 번역 매핑 딕셔너리
CN_HEADERS = {
    '상품ID': '商品ID',
    '옵션': '选项',
    '최저가': '最低价',
    '판매입찰가': '销售竞价',
    '희망조정가': '期望调整价',
    '비고': '备注'
}

# 영문 업체명 치환 매핑 사전
VENDOR_MAP = {
    '에이티밍 유한회사': 'ATIMING',
    '에이티밍': 'ATIMING',
    '리얼릭스 유한회사': 'Reallix',
    '리얼릭스': 'Reallix',
    '유한회사 도카이상사': 'Haiyun',
    '도카이상사': 'Haiyun',
    '도카이': 'Haiyun',
    '주식회사 클러치테크': 'Dingstock',
    '클러치테크': 'Dingstock',
    '클러치': 'Dingstock'
}

# ==========================================
# 🎨 커스텀 CSS
# ==========================================
st.markdown("""
<style>
    .big-font {font-size:20px !important; font-weight: bold;}
    .bad-text {color: #FF4B4B; font-weight: bold; font-size: 22px;}
    .bot-box {background-color: #F0F2F6; padding: 20px; border-radius: 10px; border-left: 5px solid #4C62F0; margin-bottom: 20px;}
    .preview-text {color: #64748B; font-size: 14px; margin-bottom: 5px;}
    .highlight-text {color: #FF8C00; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# ☁️ 클라우드 DB 연결 (Firestore)
# ==========================================
@st.cache_resource
def get_db_client():
    """Streamlit Secrets에 저장소 계정 정보가 있다면 안전하게 연결합니다."""
    if "gcp_service_account" in st.secrets:
        try:
            key_dict = dict(st.secrets["gcp_service_account"])
            # 프라이빗 키에 포함된 이스케이프 문자 복원
            if "private_key" in key_dict:
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            creds = service_account.Credentials.from_service_account_info(key_dict)
            return firestore.Client(credentials=creds, project=key_dict["project_id"])
        except Exception as e:
            st.sidebar.error(f"⚠️ 클라우드 데이터 연결 오류: {e}")
    return None

# ==========================================
# 💾 데이터베이스(DB) 로드 및 저장 함수
# ==========================================
def load_db():
    db = get_db_client()
    if db:
        try:
            docs = db.collection("artifacts").document(APP_ID).collection("public").document("data").collection("lopy_trend").stream()
            data = []
            for doc in docs:
                data.append(doc.to_dict())
            if data:
                df = pd.DataFrame(data)
                df['날짜'] = df['날짜'].astype(str)
                return df
        except Exception as e:
            st.sidebar.error(f"⚠️ 클라우드 로드 실패 (로컬 DB 대체): {e}")
            
    # 클라우드 비활성화 상태거나 연결 실패 시 로컬 CSV 파일로 작동
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'날짜': str})
    return pd.DataFrame(columns=['날짜', '업체명', '총 SKU', 'BEST PRICE 비중(%)', 'BEST PRICE 개수', 'BAD 개수'])

def save_db(df):
    db = get_db_client()
    if db:
        try:
            for _, row in df.iterrows():
                doc_id = f"{row['날짜']}_{row['업체명']}"
                doc_ref = db.collection("artifacts").document(APP_ID).collection("public").document("data").collection("lopy_trend").document(doc_id)
                doc_ref.set({
                    '날짜': str(row['날짜']),
                    '업체명': str(row['업체명']),
                    '총 SKU': int(row['총 SKU']),
                    'BEST PRICE 비중(%)': float(row['BEST PRICE 비중(%)']),
                    'BEST PRICE 개수': int(row['BEST PRICE 개수']),
                    'BAD 개수': int(row['BAD 개수'])
                })
            return
        except Exception as e:
            st.sidebar.error(f"⚠️ 클라우드 저장 실패: {e}")
            
    df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

def normalize_text(text):
    """맥과 윈도우 사이의 한글 자모 분리 및 문자열 정제를 처리합니다."""
    if not isinstance(text, str):
        return text
    return unicodedata.normalize('NFC', text).strip()

def get_week_info(date_str):
    """날짜 문자열(MMDD)을 기반으로 정렬용 ISO 주차 및 시각용 주차명을 구합니다."""
    try:
        date_str = str(date_str).strip()
        if len(date_str) == 4 and date_str.isdigit():
            month = int(date_str[:2])
            day = int(date_str[2:])
            # 2026년 기준 날짜 생성 (정밀 계산용)
            dt = datetime.date(2026, month, day)
            # 해당 월의 몇 번째 주인지 단순 수식 계산
            week_of_month = (day - 1) // 7 + 1
            iso_week = dt.isocalendar()[1]
            # 정렬 순서를 유지하기 위해 'W23 (6월 2주차)' 형태로 빌드
            return f"W{iso_week:02d} ({month}월 {week_of_month}주차)", iso_week
        return "기타", 999
    except:
        return "기타", 999

# ==========================================
# 🧹 사이드바: DB, 메모리 관리 및 확장 기능 툴
# ==========================================
with st.sidebar:
    # ☁️ 클라우드 연결 상태에 따른 사이드바 알림창
    db_client = get_db_client()
    if not db_client:
        with st.expander("☁️ 데이터 영구 저장소 활성화 방법", expanded=True):
            st.markdown("""
            현재 임시 로컬 DB 상태입니다. **서버가 재부팅되어도 월/수/금 데이터가 영구 보존**되도록 아래 가이드를 활성화하세요!
            
            **🛠️ 활성화 순서:**
            1. 구글이나 파이어베이스 콘솔에서 **Firestore Database**를 활성화합니다.
            2. 프로젝트 설정 -> [서비스 계정]에서 **새 비공개 키(JSON)**를 발급받습니다.
            3. Streamlit Cloud의 앱 세팅 화면 -> **Secrets** 영역에 아래 내용을 그대로 복사해 넣으면 끝!
            """)
            st.code("""
[gcp_service_account]
type = "service_account"
project_id = "본인 프로젝트ID"
private_key_id = "발급받은 키ID"
private_key = "-----BEGIN PRIVATE KEY-----\\n본인 개인키\\n-----END PRIVATE KEY-----\\n"
client_email = "서비스계정 이메일"
client_id = "고객ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "인증 주소"
            """, language="toml")
            st.info("💡 세팅이 완료되면 아래 초록색 아이콘으로 변하며 영구 저장이 개시됩니다.")
    else:
        st.success("☁️ 클라우드 실시간 동기화 완료 (데이터 영구 동기화 중)")

    st.markdown("---")
    st.markdown("### 🌐 다운로드 언어 설정")
    header_lang = st.radio("다운로드 파일의 열 제목 언어", ["중국어 (번역)", "한국어 (기본)"], help="중국어 선택 시 다운로드되는 엑셀 파일의 헤더가 자동으로 중국어로 변경됩니다.")

    st.markdown("---")
    st.markdown("### 🛠️ 시스템 관리")
    if st.button("🧹 메모리 초기화 (캐시 비우기)"):
        st.cache_data.clear()
        st.success("메모리가 쾌적하게 초기화되었습니다!")
        
    if st.button("🚨 누적 DB 전체 삭제"):
        if db_client:
            try:
                # 클라우드 내 컬렉션 문서 일괄 삭제
                docs = db_client.collection("artifacts").document(APP_ID).collection("public").document("data").collection("lopy_trend").stream()
                for doc in docs:
                    doc.reference.delete()
                st.success("클라우드 데이터베이스가 성공적으로 포맷되었습니다!")
            except Exception as e:
                st.error(f"클라우드 초기화 실패: {e}")
        else:
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            st.success("로컬 임시 DB가 초기화되었습니다! 새로고침 해주세요.")

    st.markdown("---")
    st.markdown("### 🔥 검색량 급등 매칭")
    surged_input = st.text_area("급등 상품ID 리스트 입력", help="엑셀에서 복사한 상품ID들을 여기에 붙여넣으세요. (줄바꿈, 띄어쓰기, 쉼표 모두 인식합니다.)", height=100)
    surged_ids = [sid.strip() for sid in re.split(r'[\s,]+', surged_input) if sid.strip()]
    if surged_ids:
        st.success(f"✅ {len(surged_ids)}개의 급등 상품ID 대기 중")

    st.markdown("---")
    st.markdown("### 🎁 프로모션 상품 매칭")
    promo_input = st.text_area("프로모션 상품ID 리스트 입력", help="이번 달 프로모션에 들어가는 상품ID들을 붙여넣으세요.", height=100)
    promo_ids = [sid.strip() for sid in re.split(r'[\s,]+', promo_input) if sid.strip()]
    if promo_ids:
        st.success(f"✅ {len(promo_ids)}개의 프로모션 상품ID 대기 중")

    st.markdown("---")
    current_db = load_db()
    st.info(f"📊 현재 누적된 트렌드 데이터: **{len(current_db)}건**")

    if not current_db.empty:
        csv_backup = current_db.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="⬇️ 누적 DB 백업 다운로드 (.csv)",
            data=csv_backup,
            file_name="lopy_trend_db_backup.csv",
            mime="text/csv",
            help="클라우드가 동기화되지 않을 경우를 대비해 수동으로 간직할 백업용 파일입니다!"
        )

# ==========================================
# 🚀 스마트 데이터 분석 함수 (유연한 시트명/열이름/업체명 감지)
# ==========================================
@st.cache_data(max_entries=30, ttl=3600, show_spinner=False)
def process_single_file(file_name, file_bytes):
    try:
        # ExcelFile 객체로 시트 목록 분석
        xls = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')
        
        # 1. 시트명 탐색 고도화 ('입찰트래킹' 또는 '트래킹', '입찰' 키워드 매칭)
        target_sheet = None
        for s in xls.sheet_names:
            s_norm = normalize_text(s)
            if s_norm == '입찰트래킹':
                target_sheet = s
                break
        
        if not target_sheet:
            for s in xls.sheet_names:
                s_norm = normalize_text(s)
                if '트래킹' in s_norm or '입찰' in s_norm:
                    target_sheet = s
                    break
                    
        # 그래도 못 찾으면 첫 번째 시트 사용 (바잉로그 등 기본 시트 호환)
        if not target_sheet and xls.sheet_names:
            target_sheet = xls.sheet_names[0]
            
        if not target_sheet:
            return None, {'type': 'error', 'msg': f"❌ '{file_name}' 파일에 시트가 존재하지 않습니다."}
            
        df = pd.read_excel(xls, sheet_name=target_sheet)
        df.columns = [normalize_text(str(c)) for c in df.columns]

        # 2. 업체명(v_name) 추출 기법 고도화
        v_name = None
        vendor_col = None
        for c in df.columns:
            if '업체명' in c:
                vendor_col = c
                break
                
        if vendor_col and len(df) > 0:
            val = str(df[vendor_col].iloc[0]).strip()
            if val and val.lower() != 'nan':
                v_name = normalize_text(val)

        # 추출한 업체명이 숫자로만 되어 있거나 길이가 1자 이하인 경우는 잘못 매핑된 것으로 간주하고 초기화
        if v_name and (v_name.isdigit() or len(v_name) <= 1):
            v_name = None

        # 업체명 열이 없거나 내용이 비어있다면 파일명에서 스마트 분석
        if not v_name or v_name == 'nan' or v_name == '':
            clean_file_name = normalize_text(os.path.splitext(file_name)[0])
            tokens = re.split(r'[\s_,\-\[\]\(\)]+', clean_file_name)
            for t in tokens:
                if t and not t.isdigit() and not any(k in t.upper() for k in ['KREAM', 'DAILY', 'REPORT', '트래킹', '입찰', '가격방어', '결과', '업데이트']):
                    v_name = t
                    break
            if not v_name:
                v_name = clean_file_name

        # 3. 날짜 추출 (가장 마지막의 4자리 숫자 확보)
        matches = re.findall(r'(\d{4})', file_name)
        date_str = matches[-1] if matches else None
        if not date_str:
            num_match = re.findall(r'\d+', file_name)
            date_str = "".join(num_match) if num_match else "오늘"

        # 4. 가격 현황 열 탐색 고도화
        status_col = None
        for c in df.columns:
            if any(k in c.replace(" ", "") for k in ['가격현황', '현황', '가격상태', '상태']):
                status_col = c
                break
                
        if not status_col:
            return None, {'type': 'warning', 'msg': f"⚠️ '{file_name}' 파일에 '가격현황' 상태 열이 존재하지 않습니다."}

        total_sku = len(df)
        
        # 'BAD'와 'BEST PRICE' 매칭 시 공백/대소문자 차이 제거
        status_series = df[status_col].astype(str).str.strip().str.upper()
        
        bad_df = df[status_series == 'BAD'].copy()
        best_df = df[status_series.isin(['BEST PRICE', 'BESTPRICE'])].copy()

        bad_count = len(bad_df)
        best_count = len(best_df)
        best_ratio = (best_count / total_sku * 100) if total_sku > 0 else 0

        # 5. 열 이름 유연성 보정
        col_keywords = {
            '상품ID': ['상품ID', '상품 ID', '아이디', 'ID'],
            '옵션': ['옵션', '옵션명', '사이즈', 'SIZE'],
            '최저가': ['최저가', '최저 가격', '최저', '최저가(원)'],
            '판매입찰가': ['판매입찰가', '판매 입찰가', '입찰가', '판매가'],
            '희망조정가': ['희망조정가', '희망 조정가', '희망가', '조정가']
        }
        
        bad_df_lite = pd.DataFrame()
        for target_key, keywords in col_keywords.items():
            actual_col = None
            for col in df.columns:
                if any(k.upper().replace(" ", "") in col.upper().replace(" ", "") for k in keywords):
                    actual_col = col
                    break
            
            if actual_col and actual_col in bad_df.columns:
                bad_df_lite[target_key] = bad_df[actual_col]
            else:
                bad_df_lite[target_key] = "" 

        return {
            '날짜': str(date_str),
            '업체명': v_name,
            '총 SKU': total_sku,
            'BEST PRICE 비중(%)': round(best_ratio, 1),
            'BEST PRICE 개수': best_count,
            'BAD 개수': bad_count,
            'bad_df': bad_df_lite 
        }, None
    except Exception as e:
        err_msg = str(e)
        return None, {'type': 'error', 'msg': f"❌ '{file_name}' 분석 중 뜻밖의 문제 발생: {err_msg}"}

# ==========================================
# 엑셀 변환 헬퍼 함수
# ==========================================
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()


# ==========================================
# 🤖 앱 헤더
# ==========================================
st.title("📈 LOPY 최저가 트렌드 & 가격방어 대시보드")
st.markdown("매일 **오늘 만들어진 엑셀 파일들만** 올려주세요. 과거 데이터는 시스템이 알아서 기억하여 트렌드를 이어 그려줍니다!")

# ==========================================
# 📂 파일 업로드 컴포넌트
# ==========================================
uploaded_files = st.file_uploader("오늘자 엑셀 파일 업로드 (.xlsx)", type=["xlsx"], accept_multiple_files=True)

# 화면 분리용 리스트
today_bad_data = []

if uploaded_files:
    progress_bar = st.progress(0, text="데이터 분석 및 DB 업데이트 중...")
    
    new_trend_data = []
    error_logs = []
    total_files = len(uploaded_files)

    for i, file in enumerate(uploaded_files):
        progress_bar.progress((i + 1) / total_files, text=f"[{i+1}/{total_files}] '{file.name}' 분석 중... ⏳")
        
        data, error = process_single_file(file.name, file.getvalue())
        if data:
            trend_row = {k: v for k, v in data.items() if k != 'bad_df'}
            new_trend_data.append(trend_row)
            today_bad_data.append(data)
            
        if error:
            error_logs.append(error)
            
    progress_bar.empty()

    for log in error_logs:
        if log['type'] == 'warning':
            st.warning(log['msg'])
        else:
            st.error(log['msg'])

    if new_trend_data:
        new_df = pd.DataFrame(new_trend_data)
        db_df = load_db()
        
        combined_df = pd.concat([db_df, new_df]).drop_duplicates(subset=['날짜', '업체명'], keep='last')
        combined_df = combined_df.sort_values(['날짜', '업체명'])
        
        save_db(combined_df)

# ==========================================
# 🗂️ 탭 화면 구성
# ==========================================
st.divider()
tab1, tab2 = st.tabs(["📈 누적 시계열 트렌드", "🚨 오늘의 BAD 상품 업데이트"])

final_db_df = load_db()

# --- 탭 1: 트렌드 대시보드 ---
with tab1:
    if not final_db_df.empty:
        # 일별 / 주차별 보기 방식 라디오 토글
        view_mode = st.radio(
            "📊 분석 보기 방식 선택", 
            ["일별 트렌드 (Daily)", "주차별 누적 트렌드 (Weekly)"], 
            horizontal=True,
            help="주차별 누적 트렌드를 선택하시면, 매일 올린 데이터들이 주차별로 누적 합산되어 정확한 가중평균 비중으로 시각화됩니다."
        )

        st.markdown("---")
        st.subheader("⚡ 실시간 가격방어 증감율 (Delta)")
        
        # 일별/주별 증감율 계산 영역
        if view_mode == "일별 트렌드 (Daily)":
            dates = sorted(final_db_df['날짜'].unique())
            if len(dates) >= 2:
                latest_date = dates[-1]
                prev_date = dates[-2]
                
                cols = st.columns(len(final_db_df['업체명'].unique()))
                for idx, vendor in enumerate(sorted(final_db_df['업체명'].unique())):
                    vendor_data = final_db_df[final_db_df['업체명'] == vendor]
                    latest_row = vendor_data[vendor_data['날짜'] == latest_date]
                    prev_row = vendor_data[vendor_data['날짜'] == prev_date]
                    
                    if not latest_row.empty and not prev_row.empty:
                        latest_val = latest_row.iloc[0]['BEST PRICE 비중(%)']
                        prev_val = prev_row.iloc[0]['BEST PRICE 비중(%)']
                        delta_val = round(latest_val - prev_val, 1)
                        
                        display_name = VENDOR_MAP.get(vendor, vendor)
                        cols[idx % len(cols)].metric(
                            label=f"{display_name} (전일대비)",
                            value=f"{latest_val}%",
                            delta=f"{delta_val:+}%"
                        )
            else:
                st.info("ℹ️ 일간 증감율(변동치)을 확인하려면 최소 2일 이상의 데이터가 업로드되어야 합니다.")
        else:
            weekly_df = final_db_df.copy()
            weeks = []
            iso_weeks = []
            for d in weekly_df['날짜']:
                w_name, iso_w = get_week_info(d)
                weeks.append(w_name)
                iso_weeks.append(iso_w)
                
            weekly_df['주차'] = weeks
            weekly_df['iso_week'] = iso_weeks
            
            grouped_weekly = weekly_df.groupby(['주차', 'iso_week', '업체명']).agg({
                '총 SKU': 'sum',
                'BEST PRICE 개수': 'sum',
                'BAD 개수': 'sum'
            }).reset_index()
            
            grouped_weekly['BEST PRICE 비중(%)'] = grouped_weekly.apply(
                lambda r: round((r['BEST PRICE 개수'] / r['총 SKU'] * 100), 1) if r['총 SKU'] > 0 else 0,
                axis=1
            )
            grouped_weekly = grouped_weekly.sort_values(by=['iso_week', '업체명'])
            
            # 주간 증감율 계산
            all_weeks = sorted(grouped_weekly['iso_week'].unique())
            if len(all_weeks) >= 2:
                latest_week = all_weeks[-1]
                prev_week = all_weeks[-2]
                
                cols = st.columns(len(grouped_weekly['업체명'].unique()))
                for idx, vendor in enumerate(sorted(grouped_weekly['업체명'].unique())):
                    vendor_data = grouped_weekly[grouped_weekly['업체명'] == vendor]
                    latest_row = vendor_data[vendor_data['iso_week'] == latest_week]
                    prev_row = vendor_data[vendor_data['iso_week'] == prev_week]
                    
                    if not latest_row.empty and not prev_row.empty:
                        latest_val = latest_row.iloc[0]['BEST PRICE 비중(%)']
                        prev_val = prev_row.iloc[0]['BEST PRICE 비중(%)']
                        delta_val = round(latest_val - prev_val, 1)
                        
                        display_name = VENDOR_MAP.get(vendor, vendor)
                        cols[idx % len(cols)].metric(
                            label=f"{display_name} (전주대비)",
                            value=f"{latest_val}%",
                            delta=f"{delta_val:+}%"
                        )
            else:
                st.info("ℹ️ 주간 증감율(변동치)을 확인하려면 최소 2주 이상의 데이터가 주별로 분석되어야 합니다.")

        st.markdown("---")
        st.subheader("🏢 업체별 BEST PRICE 점유율 트렌드 라인")

        # 꺾은선 차트 및 수치 표 표출
        if view_mode == "일별 트렌드 (Daily)":
            fig = px.line(
                final_db_df, x='날짜', y='BEST PRICE 비중(%)',
                color='업체명', text='BEST PRICE 비중(%)', markers=True
            )
            fig.update_traces(textposition="top center", texttemplate='%{text}%', marker=dict(size=10, line=dict(width=2, color='white')))
            fig.update_layout(
                yaxis_title="BEST PRICE 비중 (%)", xaxis_title="데이터 기준일 (일별)", 
                height=500, plot_bgcolor='white', yaxis=dict(gridcolor='#eeeeee'),
                xaxis=dict(type='category', gridcolor='#eeeeee'), legend_title="업체명"
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("**📅 누적된 상세 수치 표 (일별)**")
            st.dataframe(final_db_df, use_container_width=True, hide_index=True)
            
        else:
            fig = px.line(
                grouped_weekly, x='주차', y='BEST PRICE 비중(%)',
                color='업체명', text='BEST PRICE 비중(%)', markers=True
            )
            fig.update_traces(textposition="top center", texttemplate='%{text}%', marker=dict(size=10, line=dict(width=2, color='white')))
            fig.update_layout(
                yaxis_title="BEST PRICE 비중 (%)", xaxis_title="데이터 기준 주차 (주별)", 
                height=500, plot_bgcolor='white', yaxis=dict(gridcolor='#eeeeee'),
                xaxis=dict(type='category', gridcolor='#eeeeee'), legend_title="업체명"
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("**📅 주차별 누적 상세 수치 표**")
            display_weekly = grouped_weekly[['주차', '업체명', '총 SKU', 'BEST PRICE 비중(%)', 'BEST PRICE 개수', 'BAD 개수']]
            st.dataframe(display_weekly, use_container_width=True, hide_index=True)
            
    else:
        st.info("💡 아직 누적된 데이터가 없습니다. 엑셀 파일을 업로드하면 이곳에 트렌드가 기록되기 시작합니다.")

# --- 탭 2: 분리 및 확장 기능 화면 ---
with tab2:
    if not today_bad_data:
        st.info("💡 윗부분에 **오늘의 엑셀 파일**을 업로드하시면, 가격을 조정해야 할 BAD 상품 리스트와 다운로드 버튼이 여기에 나타납니다.")
    else:
        st.subheader("방금 업로드한 파일의 업체별 분리 리스트")
        
        total_today_bad = sum(item['BAD 개수'] for item in today_bad_data)
        
        if total_today_bad > 0:
            st.markdown(f'''
            <div class="bot-box">
                <span class="big-font">🤖 봇의 브리핑:</span><br>
                방금 업로드하신 파일 기준으로 총 <span class="bad-text">{total_today_bad:,}개</span>의 상품이 최저가를 뺏겼습니다.<br>
                아래에서 <b>각 업체별로 분리된 리스트를 확인하고 개별 엑셀 파일을 다운로드</b> 하세요!
            </div>
            ''', unsafe_allow_html=True)

            for item in today_bad_data:
                vendor = item['업체명']
                v_bad_count = item['BAD 개수']
                
                v_bad_df = item['bad_df'].copy() 
                latest_date = item['날짜']

                # 영문 업체명 매핑 처리 (사전에 일치하는 한글 키워드가 있으면 영문으로 전환)
                mapped_vendor = vendor
                for kr_key, eng_val in VENDOR_MAP.items():
                    if kr_key in vendor:
                        mapped_vendor = eng_val
                        break

                with st.expander(f"🏢 {vendor} (수정 필요: {v_bad_count:,}개)", expanded=(v_bad_count > 0)):
                    if v_bad_count > 0:
                        
                        surge_tag = '🔥KREAM 流量黑马' if header_lang == "중국어 (번역)" else '🔥급등'
                        promo_tag = '🎁促销活动商品' if header_lang == "중국어 (번역)" else '🎁프로모션 진행상품'

                        if surged_ids or promo_ids:
                            def get_remark(item_id):
                                remarks = []
                                item_str = str(item_id).strip()
                                if surged_ids and item_str in surged_ids:
                                    remarks.append(surge_tag)
                                if promo_ids and item_str in promo_ids:
                                    remarks.append(promo_tag)
                                return ' / '.join(remarks)
                                
                            v_bad_df['비고'] = v_bad_df['상품ID'].apply(get_remark)
                            
                            v_bad_df['sort_weight'] = v_bad_df['비고'].apply(lambda x: 1 if x != '' else 0)
                            v_bad_df.sort_values(by=['sort_weight', '비고'], ascending=[False, False], inplace=True)
                            v_bad_df.drop(columns=['sort_weight'], inplace=True)
                            
                            surge_match_count = len(v_bad_df[v_bad_df['비고'].str.contains(surge_tag, na=False)])
                            promo_match_count = len(v_bad_df[v_bad_df['비고'].str.contains(promo_tag, na=False)])
                            
                            if surge_match_count > 0 or promo_match_count > 0:
                                msg = "<span class='highlight-text'>💡 매칭 성공: "
                                if surge_match_count > 0:
                                    msg += f"급등 {surge_match_count}건 "
                                if promo_match_count > 0:
                                    msg += f"프로모션 {promo_match_count}건 "
                                msg += "발견! (목록 최상단으로 정렬됨)</span>"
                                st.markdown(msg, unsafe_allow_html=True)
                        else:
                            v_bad_df['비고'] = ''

                        st.markdown(f"<div class='preview-text'>👀 브라우저 속도를 위해 표에는 최대 100개까지만 미리보기로 표시됩니다. (전체 {v_bad_count:,}개는 아래 엑셀로 다운로드)</div>", unsafe_allow_html=True)
                        
                        display_df = v_bad_df.copy()
                        if header_lang == "중국어 (번역)":
                            display_df.rename(columns=CN_HEADERS, inplace=True)

                        st.dataframe(display_df.head(100), use_container_width=True, hide_index=True)

                        excel_data = to_excel(display_df)
                        
                        btn_label = f"📥 [{vendor}] 전체 {v_bad_count:,}개 다운로드 (.xlsx)"
                        if header_lang == "중국어 (번역)":
                            btn_label += " (🇨🇳중국어 양식)"

                        st.download_button(
                            label=btn_label,
                            data=excel_data,
                            file_name=f"{mapped_vendor}_{latest_date}_Bad Only.xlsx", 
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                            type="primary",
                            key=f"btn_{vendor}_{latest_date}_{v_bad_count}"
                        )
                    else:
                        st.success("✨ 이 업체는 방금 올리신 데이터 기준으로 최저가 방어가 완벽합니다!")
        else:
            st.success("🎉 완벽합니다! 방금 올리신 파일 기준으로 모든 업체의 최저가 방어가 100%입니다.")
            st.balloons()
