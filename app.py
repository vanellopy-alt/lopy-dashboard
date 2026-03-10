import streamlit as st
import pandas as pd
import plotly.express as px
import re

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
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🚀 데이터 캐싱 함수 (속도 최적화의 핵심!)
# ==========================================
# @st.cache_data를 붙이면 한 번 읽은 파일은 메모리에 기억해두어 버튼을 누를 때마다 다시 읽지 않습니다.
@st.cache_data(show_spinner=False)
def process_uploaded_files(files):
    trend_data = []
    error_logs = []

    for file in files:
        try:
            # 엑셀 파일에서 '입찰트래킹' 시트 읽기
            df = pd.read_excel(file, sheet_name='입찰트래킹', engine='openpyxl')
            
            # 업체명 추출
            if '업체명' in df.columns:
                v_name = df['업체명'].iloc[0]
            else:
                v_name = file.name.split('_')[0]

            # 날짜 추출
            matches = re.findall(r'(\d{4})', file.name)
            date_str = matches[-1] if matches else file.name

            # 상태별 집계
            total_sku = len(df)
            bad_df = df[df['가격현황'] == 'BAD'].copy()
            best_df = df[df['가격현황'] == 'BEST PRICE'].copy()

            bad_count = len(bad_df)
            best_count = len(best_df)
            best_ratio = (best_count / total_sku * 100) if total_sku > 0 else 0

            trend_data.append({
                '날짜': str(date_str),
                '업체명': v_name,
                '총 SKU': total_sku,
                'BEST PRICE 비중(%)': round(best_ratio, 1),
                'BEST PRICE 개수': best_count,
                'BAD 개수': bad_count,
                'bad_df': bad_df
            })
        except Exception as e:
            err_msg = str(e)
            if "Worksheet named '입찰트래킹' not found" in err_msg:
                error_logs.append({'type': 'warning', 'msg': f"⚠️ '{file.name}' 파일은 이전 버전 양식이거나 '입찰트래킹' 시트가 없어 제외되었습니다."})
            else:
                error_logs.append({'type': 'error', 'msg': f"❌ '{file.name}' 읽기 오류: {err_msg}"})
            continue
            
    return trend_data, error_logs


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
    with st.spinner('데이터를 업체별로 예쁘게 분류하는 중입니다... (최초 1회만 소요) ⏳'):
        
        # 캐싱된 초고속 분석 함수 실행
        trend_data, error_logs = process_uploaded_files(uploaded_files)

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
                        with st.expander(f"🏢 {vendor} (수정 필요: {v_bad_count}개)", expanded=(v_bad_count > 0)):
                            if v_bad_count > 0:
                                display_cols = ['상품ID', '옵션', '최저가', '판매입찰가', '희망조정가']
                                actual_cols = [c for c in display_cols if c in v_bad_df.columns]

                                # 개별 업체의 표 렌더링
                                st.dataframe(v_bad_df[actual_cols], use_container_width=True, hide_index=True)

                                # 개별 업체 전용 CSV 다운로드 버튼
                                csv_data = v_bad_df[actual_cols].to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                                
                                st.download_button(
                                    label=f"📥 [{vendor}] 전용 가격 업데이트 CSV 다운로드",
                                    data=csv_data,
                                    file_name=f"{vendor}_{latest_date}_업데이트.csv",
                                    mime="text/csv",
                                    type="primary",
                                    key=f"btn_{vendor}_{latest_date}" # 버튼끼리 충돌하지 않게 고유 키 부여
                                )
                            else:
                                st.success("✨ 이 업체는 현재 최저가 방어가 완벽합니다! 수정할 상품이 없습니다.")
                else:
                    st.success(f"🎉 완벽합니다! {latest_date} 기준으로 모든 업체의 최저가 방어가 100%입니다.")
                    st.balloons()
