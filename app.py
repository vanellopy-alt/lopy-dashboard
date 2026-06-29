import streamlit as st
import pandas as pd
import re
import io
import os
import unicodedata

# ==========================================
# ⚙️ 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="LOPY 업체별 최저가 모니터링", page_icon="📈", layout="wide")

DB_FILE = "lopy_trend_db.csv"

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
    '클러치': 'Dingstock',
    '유한회사 모바이트레이드': 'STEP DREAM',
    '모바이트레이드': 'STEP DREAM'
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
# 💾 데이터베이스(DB) 로드 및 저장 함수
# ==========================================
def load_db():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'날짜': str})
    return pd.DataFrame(columns=['날짜', '업체명', '총 SKU', 'BEST PRICE 비중(%)', 'BEST PRICE 개수', 'BAD 개수'])

def save_db(df):
    df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

def normalize_text(text):
    """맥과 윈도우 사이의 한글 자모 분리 및 문자열 정제를 처리합니다."""
    if not isinstance(text, str):
        return text
    return unicodedata.normalize('NFC', text).strip()

# ==========================================
# 🧹 사이드바: DB, 메모리 관리 및 확장 기능 툴
# ==========================================
with st.sidebar:
    st.markdown("### 🌐 다운로드 언어 설정")
    header_lang = st.radio("다운로드 파일의 열 제목 언어", ["중국어 (번역)", "한국어 (기본)"], help="중국어 선택 시 다운로드되는 엑셀 파일의 헤더가 자동으로 중국어로 변경됩니다.")

    st.markdown("---")
    st.markdown("### 🔥 검색량 급등 매칭")
    surged_input = st.text_area("급등 상품ID 리스트 입력", help="엑셀에서 복사한 상품ID들을 여기에 붙여넣으세요.", height=100)
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
    st.markdown("### 💾 자동 누적 데이터베이스")
    current_db = load_db()
    st.info(f"📊 현재 누적된 데이터 건수: **{len(current_db)}건**")

    if not current_db.empty:
        csv_backup = current_db.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="⬇️ 누적 DB 백업 다운로드 (.csv)",
            data=csv_backup,
            file_name="lopy_trend_db_backup.csv",
            mime="text/csv",
            help="서버 재부팅으로 데이터가 날아갈 경우를 대비해 백업해두세요!"
        )

    st.markdown("---")
    st.markdown("**⬆️ 백업된 DB 파일 복구**")
    db_upload = st.file_uploader("다운받아둔 백업 CSV 업로드", type=['csv'])
    if db_upload:
        restored_df = pd.read_csv(db_upload, dtype={'날짜': str})
        save_db(restored_df)
        st.success("✅ DB 복구 완료! 화면을 새로고침 해주세요.")

    st.markdown("---")
    st.markdown("### 🛠️ 시스템 관리")
    if st.button("🧹 메모리 초기화 (캐시 비우기)"):
        st.cache_data.clear()
        st.success("메모리가 쾌적하게 초기화되었습니다!")
        
    if st.button("🚨 누적 DB 전체 삭제"):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        st.success("DB가 초기화되었습니다! 새로고침 해주세요.")

# ==========================================
# 🚀 스마트 데이터 분석 함수 (유연한 시트명/열이름/업체명 감지)
# ==========================================
@st.cache_data(max_entries=30, ttl=3600, show_spinner=False)
def process_single_file(file_name, file_bytes):
    try:
        xls = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')
        
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
                    
        if not target_sheet and xls.sheet_names:
            target_sheet = xls.sheet_names[0]
            
        if not target_sheet:
            return None, {'type': 'error', 'msg': f"❌ '{file_name}' 파일에 시트가 존재하지 않습니다."}
            
        df = pd.read_excel(xls, sheet_name=target_sheet)
        df.columns = [normalize_text(str(c)) for c in df.columns]

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

        if v_name and (v_name.isdigit() or len(v_name) <= 1):
            v_name = None

        # STEP DREAM 치환
        user_id = None
        for c in df.columns:
            if '유저' in c and '아이디' in c:
                user_id = str(df[c].iloc[0]).strip()
                break
        if user_id == '10843431':
            v_name = 'STEP DREAM'

        if not v_name or v_name == 'nan' or v_name == '':
            clean_file_name = normalize_text(os.path.splitext(file_name)[0])
            tokens = re.split(r'[\s_,\-\[\]\(\)]+', clean_file_name)
            for t in tokens:
                if t and not t.isdigit() and not any(k in t.upper() for k in ['KREAM', 'DAILY', 'REPORT', '트래킹', '입찰', '가격방어', '결과', '업데이트']):
                    v_name = t
                    break
            if not v_name:
                v_name = clean_file_name

        matches = re.findall(r'(\d{4})', file_name)
        date_str = matches[-1] if matches else None
        if not date_str:
            num_match = re.findall(r'\d+', file_name)
            date_str = "".join(num_match) if num_match else "오늘"

        status_col = None
        for c in df.columns:
            if any(k in c.replace(" ", "") for k in ['가격현황', '현황', '가격상태', '상태']):
                status_col = c
                break
                
        if not status_col:
            return None, {'type': 'warning', 'msg': f"⚠️ '{file_name}' 파일에 '가격현황' 상태 열이 존재하지 않습니다."}

        total_sku = len(df)
        status_series = df[status_col].astype(str).str.strip().str.upper()
        
        bad_df = df[status_series == 'BAD'].copy()
        best_df = df[status_series.isin(['BEST PRICE', 'BESTPRICE'])].copy()

        bad_count = len(bad_df)
        best_count = len(best_df)
        best_ratio = (best_count / total_sku * 100) if total_sku > 0 else 0

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

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# ==========================================
# 🤖 앱 레이아웃 및 업로드
# ==========================================
st.title("📈 LOPY 업체별 최저가 모니터링")
st.markdown("매일 **오늘 만들어진 최저가 매칭 파일들만** 올려주세요. 업체별로 자동 분리되어 수정 다운로드 양식을 즉시 생성합니다.")

uploaded_files = st.file_uploader("오늘자 엑셀 파일 업로드 (.xlsx)", type=["xlsx"], accept_multiple_files=True)

today_bad_data = []

if uploaded_files:
    progress_bar = st.progress(0, text="데이터 분석 및 매칭 중...")
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
# 🚨 오늘의 BAD 상품 업데이트 화면 (단일 통합 화면)
# ==========================================
st.divider()

if not today_bad_data:
    st.info("💡 윗부분에 **오늘의 최저가 대조 엑셀 파일**을 업로드하시면, 가격을 수정해야 할 업체별 BAD 상품 리스트와 다운로드 단추가 이곳에 표출됩니다.")
else:
    st.subheader("📋 방금 업로드한 파일의 업체별 분리 리스트")
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
