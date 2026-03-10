import streamlit as st
import pandas as pd
import plotly.express as px
import re
import io
import os

# ==========================================
# ⚙️ 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="LOPY 트렌드 & 가격방어 봇", page_icon="📈", layout="wide")

DB_FILE = "lopy_trend_db.csv"

# ==========================================
# 🎨 커스텀 CSS
# ==========================================
st.markdown("""
<style>
    .big-font {font-size:20px !important; font-weight: bold;}
    .bad-text {color: #FF4B4B; font-weight: bold; font-size: 22px;}
    .bot-box {background-color: #F0F2F6; padding: 20px; border-radius: 10px; border-left: 5px solid #4C62F0; margin-bottom: 20px;}
    .preview-text {color: #64748B; font-size: 14px; margin-bottom: 5px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 💾 데이터베이스(DB) 로드 및 저장 함수
# ==========================================
def load_db():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'날짜': str}) # 날짜 앞의 0이 사라지지 않게 문자열로 읽기
    return pd.DataFrame(columns=['날짜', '업체명', '총 SKU', 'BEST PRICE 비중(%)', 'BEST PRICE 개수', 'BAD 개수'])

def save_db(df):
    df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

# ==========================================
# 🧹 사이드바: DB 및 메모리 관리 툴
# ==========================================
with st.sidebar:
    st.markdown("### 💾 자동 누적 데이터베이스")
    st.markdown("업로드하신 파일의 트렌드 기록이 이곳에 자동 저장됩니다. (오늘 파일만 올려도 과거 데이터가 유지됩니다!)")
    
    # 현재 DB 상태 읽기
    current_db = load_db()
    st.info(f"📊 현재 누적된 트렌드 데이터: **{len(current_db)}건**")

    if not current_db.empty:
        csv_backup = current_db.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="⬇️ 누적 DB 백업 다운로드",
            data=csv_backup,
            file_name="lopy_trend_db_backup.csv",
            mime="text/csv",
            help="서버 재부팅으로 데이터가 날아갈 경우를 대비해 가끔씩 백업해두세요!"
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
# 🚀 데이터 분석 함수 (메모리 최적화 유지)
# ==========================================
@st.cache_data(max_entries=30, ttl=3600, show_spinner=False)
def process_single_file(file_name, file_bytes):
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name='입찰트래킹', engine='openpyxl')
        
        v_name = df['업체명'].iloc[0] if '업체명' in df.columns else file_name.split('_')[0]
        matches = re.findall(r'(\d{4})', file_name)
        date_str = matches[-1] if matches else file_name

        total_sku = len(df)
        bad_df = df[df['가격현황'] == 'BAD'].copy()
        best_df = df[df['가격현황'] == 'BEST PRICE'].copy()

        bad_count = len(bad_df)
        best_count = len(best_df)
        best_ratio = (best_count / total_sku * 100) if total_sku > 0 else 0

        display_cols = ['상품ID', '옵션', '최저가', '판매입찰가', '희망조정가']
        actual_cols = [c for c in display_cols if c in bad_df.columns]
        bad_df_lite = bad_df[actual_cols].copy() 

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
        if "Worksheet named '입찰트래킹' not found" in err_msg:
            return None, {'type': 'warning', 'msg': f"⚠️ '{file_name}' 파일은 이전 양식이거나 '입찰트래킹' 시트가 없습니다."}
        else:
            return None, {'type': 'error', 'msg': f"❌ '{file_name}' 읽기 오류: {err_msg}"}


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
            # 트렌드 기록용 데이터 (bad_df 제외)
            trend_row = {k: v for k, v in data.items() if k != 'bad_df'}
            new_trend_data.append(trend_row)
            
            # 오늘자 업데이트 리스트용 데이터 (bad_df 포함)
            today_bad_data.append(data)
            
        if error:
            error_logs.append(error)
            
    progress_bar.empty()

    for log in error_logs:
        if log['type'] == 'warning':
            st.warning(log['msg'])
        else:
            st.error(log['msg'])

    # 🔥 새로 업로드된 데이터를 누적 DB에 병합하여 저장
    if new_trend_data:
        new_df = pd.DataFrame(new_trend_data)
        db_df = load_db()
        
        # 날짜와 업체명이 겹치면 최신 데이터(방금 올린 파일)로 덮어쓰기
        combined_df = pd.concat([db_df, new_df]).drop_duplicates(subset=['날짜', '업체명'], keep='last')
        combined_df = combined_df.sort_values(['날짜', '업체명'])
        
        save_db(combined_df) # DB 파일 갱신

# ==========================================
# 🗂️ 탭 화면 구성 (업로드 안 해도 트렌드는 보이게 처리)
# ==========================================
st.divider()
tab1, tab2 = st.tabs(["📈 누적 시계열 트렌드", "🚨 오늘의 BAD 상품 업데이트"])

# 최신 DB 데이터 다시 불러오기
final_db_df = load_db()

# --- 탭 1: 트렌드 대시보드 (DB 연동) ---
with tab1:
    st.subheader("🏢 업체별 BEST PRICE 점유율 변화 추이")
    
    if not final_db_df.empty:
        fig = px.line(
            final_db_df, x='날짜', y='BEST PRICE 비중(%)',
            color='업체명', text='BEST PRICE 비중(%)', markers=True
        )
        fig.update_traces(textposition="top center", texttemplate='%{text}%', marker=dict(size=10, line=dict(width=2, color='white')))
        fig.update_layout(
            yaxis_title="BEST PRICE 비중 (%)", xaxis_title="데이터 기준일", 
            height=500, plot_bgcolor='white', yaxis=dict(gridcolor='#eeeeee'),
            xaxis=dict(type='category', gridcolor='#eeeeee'), legend_title="업체명"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**📅 누적된 상세 수치 표**")
        st.dataframe(final_db_df, use_container_width=True, hide_index=True)
    else:
        st.info("💡 아직 누적된 데이터가 없습니다. 엑셀 파일을 업로드하면 이곳에 트렌드가 기록되기 시작합니다.")

# --- 탭 2: "방금 올린 파일" 기반 업체별 분리 화면 ---
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
                아래에서 <b>각 업체별로 분리된 리스트를 확인하고 개별 CSV를 다운로드</b> 하세요!
            </div>
            ''', unsafe_allow_html=True)

            for item in today_bad_data:
                vendor = item['업체명']
                v_bad_count = item['BAD 개수']
                v_bad_df = item['bad_df']
                latest_date = item['날짜']

                with st.expander(f"🏢 {vendor} (수정 필요: {v_bad_count:,}개)", expanded=(v_bad_count > 0)):
                    if v_bad_count > 0:
                        actual_cols = v_bad_df.columns.tolist()

                        st.markdown(f"<div class='preview-text'>👀 브라우저 속도를 위해 표에는 최대 100개까지만 미리보기로 표시됩니다. (전체 {v_bad_count:,}개는 아래 CSV로 다운로드)</div>", unsafe_allow_html=True)
                        st.dataframe(v_bad_df.head(100), use_container_width=True, hide_index=True)

                        csv_data = v_bad_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                        
                        st.download_button(
                            label=f"📥 [{vendor}] 전체 {v_bad_count:,}개 가격 업데이트 CSV 다운로드",
                            data=csv_data,
                            file_name=f"{vendor}_{latest_date}_업데이트.csv",
                            mime="text/csv",
                            type="primary",
                            key=f"btn_{vendor}_{latest_date}_{v_bad_count}"
                        )
                    else:
                        st.success("✨ 이 업체는 방금 올리신 데이터 기준으로 최저가 방어가 완벽합니다!")
        else:
            st.success("🎉 완벽합니다! 방금 올리신 파일 기준으로 모든 업체의 최저가 방어가 100%입니다.")
            st.balloons()
