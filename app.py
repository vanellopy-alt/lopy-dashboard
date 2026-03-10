import streamlit as st
import pandas as pd
import plotly.express as px
import re
import io

# ==========================================
# ⚙️ 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="LOPY 트렌드 & 가격방어 봇", page_icon="📈", layout="wide")

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
# 🧹 사이드바: 메모리 관리 툴
# ==========================================
with st.sidebar:
    st.markdown("### 🛠️ 시스템 관리")
    st.markdown("서버가 느려지거나 에러가 나면 아래 버튼을 눌러주세요.")
    if st.button("🧹 메모리 초기화 (캐시 비우기)"):
        st.cache_data.clear()
        st.success("메모리가 쾌적하게 초기화되었습니다!")

# ==========================================
# 🚀 데이터 캐싱 함수 (메모리 최적화 적용!)
# ==========================================
# 메모리 초과 방지: 최대 30개까지만 기억, 1시간(3600초) 지나면 자동 삭제
@st.cache_data(max_entries=30, ttl=3600, show_spinner=False)
def process_single_file(file_name, file_bytes):
    try:
        # 바이트 데이터를 엑셀로 읽기
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name='입찰트래킹', engine='openpyxl')
        
        # 업체명 추출
        if '업체명' in df.columns:
            v_name = df['업체명'].iloc[0]
        else:
            v_name = file_name.split('_')[0]

        # 날짜 추출
        matches = re.findall(r'(\d{4})', file_name)
        date_str = matches[-1] if matches else file_name

        # 상태별 집계
        total_sku = len(df)
        bad_df = df[df['가격현황'] == 'BAD'].copy()
        best_df = df[df['가격현황'] == 'BEST PRICE'].copy()

        bad_count = len(bad_df)
        best_count = len(best_df)
        best_ratio = (best_count / total_sku * 100) if total_sku > 0 else 0

        # 🔥 메모리 다이어트 (Memory Optimization)
        # 50개가 넘는 전체 컬럼을 다 들고 있으면 메모리가 터집니다. 꼭 필요한 컬럼만 남기고 삭제합니다!
        display_cols = ['상품ID', '옵션', '최저가', '판매입찰가', '희망조정가']
        actual_cols = [c for c in display_cols if c in bad_df.columns]
        bad_df_lite = bad_df[actual_cols].copy() # 엑셀 출력용 필수 데이터만 가벼운 형태로 복사

        return {
            '날짜': str(date_str),
            '업체명': v_name,
            '총 SKU': total_sku,
            'BEST PRICE 비중(%)': round(best_ratio, 1),
            'BEST PRICE 개수': best_count,
            'BAD 개수': bad_count,
            'bad_df': bad_df_lite  # 무거운 전체 데이터 대신 가벼운 데이터만 저장
        }, None
    except Exception as e:
        err_msg = str(e)
        if "Worksheet named '입찰트래킹' not found" in err_msg:
            return None, {'type': 'warning', 'msg': f"⚠️ '{file_name}' 파일은 이전 버전 양식이거나 '입찰트래킹' 시트가 없어 제외되었습니다."}
        else:
            return None, {'type': 'error', 'msg': f"❌ '{file_name}' 읽기 오류: {err_msg}"}


# ==========================================
# 🤖 앱 헤더
# ==========================================
st.title("📈 LOPY 최저가 트렌드 & 가격방어 대시보드")
st.markdown("매일 생성되는 **여러 날짜, 여러 업체의 엑셀 파일들**을 한꺼번에 올려주세요. 업체별 분리된 데이터와 트렌드를 제공합니다!")

# ==========================================
# 📂 파일 업로드 컴포넌트
# ==========================================
uploaded_files = st.file_uploader("엑셀 파일 여러 개 동시 업로드 (.xlsx)", type=["xlsx"], accept_multiple_files=True)

if uploaded_files:
    # 🔥 UX 개선: 파일 로딩 상태를 보여주는 프로그레스 바 추가
    progress_bar = st.progress(0, text="데이터 분석 준비 중...")
    
    trend_data = []
    error_logs = []
    total_files = len(uploaded_files)

    for i, file in enumerate(uploaded_files):
        # 프로그레스 바 업데이트
        progress_bar.progress((i + 1) / total_files, text=f"[{i+1}/{total_files}] '{file.name}' 분석 중... ⏳ (최초 1회만 소요)")
        
        # 파일을 직접 넘기지 않고, 파일명과 바이트 데이터를 추출해서 캐싱 함수로 전달 (무한 로딩 방지)
        data, error = process_single_file(file.name, file.getvalue())
        if data:
            trend_data.append(data)
        if error:
            error_logs.append(error)
            
    # 로딩 완료 후 프로그레스 바 숨기기
    progress_bar.empty()

    # 에러 또는 경고 메시지 화면 출력
    for log in error_logs:
        if log['type'] == 'warning':
            st.warning(log['msg'])
        else:
            st.error(log['msg'])

    if trend_data:
        trend_df = pd.DataFrame(trend_data)
        trend_df = trend_df.sort_values(['날짜', '업체명'])

        st.divider()

        # ==========================================
        # 🗂️ 탭 화면 구성
        # ==========================================
        tab1, tab2 = st.tabs(["📈 시계열 트렌드 대시보드", "🚨 업체별 BAD 상품 개별 업데이트"])

        # --- 탭 1: 트렌드 대시보드 ---
        with tab1:
            st.subheader("🏢 업체별 BEST PRICE 점유율 변화 추이")
            
            fig = px.line(
                trend_df, x='날짜', y='BEST PRICE 비중(%)',
                color='업체명', text='BEST PRICE 비중(%)', markers=True
            )
            fig.update_traces(textposition="top center", texttemplate='%{text}%', marker=dict(size=10, line=dict(width=2, color='white')))
            fig.update_layout(
                yaxis_title="BEST PRICE 비중 (%)", xaxis_title="데이터 기준일", 
                height=500, plot_bgcolor='white', yaxis=dict(gridcolor='#eeeeee'),
                xaxis=dict(type='category', gridcolor='#eeeeee'), legend_title="업체명"
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("**📅 상세 수치 표**")
            display_trend_df = trend_df[['날짜', '업체명', '총 SKU', 'BEST PRICE 개수', 'BEST PRICE 비중(%)', 'BAD 개수']]
            st.dataframe(display_trend_df, use_container_width=True, hide_index=True)

        # --- 탭 2: "업체별" 분리 화면 ---
        with tab2:
            latest_date = trend_df['날짜'].max()
            latest_subset = trend_df[trend_df['날짜'] == latest_date]
            total_latest_bad = latest_subset['BAD 개수'].sum()
            
            st.subheader(f"가장 최근 날짜 ({latest_date}) 업체별 분리 리스트")

            if total_latest_bad > 0:
                st.markdown(f'''
                <div class="bot-box">
                    <span class="big-font">🤖 봇의 브리핑:</span><br>
                    가장 최근인 <b>{latest_date}</b> 기준으로 총 <span class="bad-text">{total_latest_bad:,}개</span>의 상품이 최저가를 뺏겼습니다.<br>
                    아래에서 <b>각 업체별로 분리된 리스트를 확인하고 개별 CSV를 다운로드</b> 하세요!
                </div>
                ''', unsafe_allow_html=True)

                # 각 업체별로 구역을 나누어 표시 (Expander 사용)
                for idx, row in latest_subset.iterrows():
                    vendor = row['업체명']
                    v_bad_count = row['BAD 개수']
                    v_bad_df = row['bad_df']

                    # 토글 형태로 업체별 블록 생성 (BAD가 있는 업체만 기본으로 펼쳐놓음)
                    with st.expander(f"🏢 {vendor} (수정 필요: {v_bad_count:,}개)", expanded=(v_bad_count > 0)):
                        if v_bad_count > 0:
                            # 이미 핵심 컬럼만 남겨둔 bad_df_lite 상태이므로 그대로 사용합니다
                            actual_cols = v_bad_df.columns.tolist()

                            # 🔥 핵심 속도 개선: 화면 표출은 무조건 상위 100개까지만! (브라우저 뻗음 방지)
                            st.markdown(f"<div class='preview-text'>👀 브라우저 속도를 위해 표에는 최대 100개까지만 미리보기로 표시됩니다. (전체 {v_bad_count:,}개는 아래 CSV로 다운로드)</div>", unsafe_allow_html=True)
                            st.dataframe(v_bad_df.head(100), use_container_width=True, hide_index=True)

                            # CSV에는 100개가 아니라 전체 데이터를 담아서 다운로드!
                            csv_data = v_bad_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                            
                            st.download_button(
                                label=f"📥 [{vendor}] 전체 {v_bad_count:,}개 가격 업데이트 CSV 다운로드",
                                data=csv_data,
                                file_name=f"{vendor}_{latest_date}_업데이트.csv",
                                mime="text/csv",
                                type="primary",
                                key=f"btn_{vendor}_{latest_date}"
                            )
                        else:
                            st.success("✨ 이 업체는 현재 최저가 방어가 완벽합니다! 수정할 상품이 없습니다.")
            else:
                st.success(f"🎉 완벽합니다! {latest_date} 기준으로 모든 업체의 최저가 방어가 100%입니다.")
                st.balloons()
