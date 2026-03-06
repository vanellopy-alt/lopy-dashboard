import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ==========================================
# ⚙️ 페이지 기본 설정 (넓은 화면, 아이콘 설정)
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
# 🤖 앱 헤더 및 타이틀
# ==========================================
st.title("📈 LOPY 최저가 트렌드 & 가격방어 대시보드")
st.markdown("매일 생성되는 **여러 날짜, 여러 업체의 엑셀 파일들**을 한꺼번에 올려주세요. 업체별 트렌드와 통합 업데이트 리스트를 제공합니다!")

# ==========================================
# 📂 파일 다중 업로드 컴포넌트
# ==========================================
uploaded_files = st.file_uploader("엑셀 파일 여러 개 동시 업로드 (.xlsx)", type=["xlsx"], accept_multiple_files=True)

if uploaded_files:
    with st.spinner('데이터를 분석하여 트렌드를 그리는 중입니다... ⏳'):
        trend_data = []

        for file in uploaded_files:
            try:
                # 엑셀 파일에서 '입찰트래킹' 시트 읽어오기
                df = pd.read_excel(file, sheet_name='입찰트래킹', engine='openpyxl')
                
                # 업체명 추출 (각 파일마다 고유하게 추출)
                if '업체명' in df.columns:
                    v_name = df['업체명'].iloc[0]
                else:
                    v_name = file.name.split('_')[0]

                # 파일명에서 날짜(숫자 4자리, 예: 0305) 추출 시도
                matches = re.findall(r'(\d{4})', file.name)
                date_str = matches[-1] if matches else file.name

                # 상태별 개수 집계
                total_sku = len(df)
                bad_df = df[df['가격현황'] == 'BAD'].copy()
                best_df = df[df['가격현황'] == 'BEST PRICE'].copy()

                bad_count = len(bad_df)
                best_count = len(best_df)
                best_ratio = (best_count / total_sku * 100) if total_sku > 0 else 0

                # 트렌드 리스트에 데이터 추가
                trend_data.append({
                    '날짜': str(date_str), # 숫자로 인식하지 않게 문자로 강제 변환
                    '업체명': v_name,
                    '총 SKU': total_sku,
                    'BEST PRICE 비중(%)': round(best_ratio, 1),
                    'BEST PRICE 개수': best_count,
                    'BAD 개수': bad_count,
                    'bad_df': bad_df
                })
            except Exception as e:
                err_msg = str(e)
                # 과거 파일이라 입찰트래킹 시트가 없는 경우
                if "Worksheet named '입찰트래킹' not found" in err_msg:
                    st.warning(f"⚠️ '{file.name}' 파일은 이전 버전 양식이거나 '입찰트래킹' 시트가 없어 제외되었습니다. (최근 파일만 올려주세요!)")
                else:
                    st.error(f"❌ '{file.name}' 읽기 오류: {err_msg}")
                continue

        # 데이터를 날짜 및 업체 순으로 정렬
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            trend_df = trend_df.sort_values(['날짜', '업체명'])

            st.divider()

            # ==========================================
            # 🗂️ 탭(Tab) 화면 구성
            # ==========================================
            tab1, tab2 = st.tabs(["📈 시계열 트렌드 대시보드", "🚨 최신 BAD 상품 통합 업데이트"])

            # --- 탭 1: 트렌드 대시보드 ---
            with tab1:
                st.subheader("🏢 업체별 BEST PRICE 점유율 변화 추이")
                
                # Plotly: x축을 카테고리로 강제 지정하고, 업체별로 색상을 다르게 그려줍니다.
                fig = px.line(
                    trend_df, x='날짜', y='BEST PRICE 비중(%)',
                    color='업체명', # 여러 업체 선 색상 분리
                    text='BEST PRICE 비중(%)',
                    markers=True
                )
                fig.update_traces(textposition="top center", texttemplate='%{text}%', marker=dict(size=10, line=dict(width=2, color='white')))
                fig.update_layout(
                    yaxis_title="BEST PRICE 비중 (%)", 
                    xaxis_title="데이터 기준일", 
                    height=500,
                    plot_bgcolor='white',
                    yaxis=dict(gridcolor='#eeeeee'),
                    xaxis=dict(type='category', gridcolor='#eeeeee'), # 305.5 같은 소수점 방지
                    legend_title="업체명"
                )
                
                # 화면에 그래프 출력
                st.plotly_chart(fig, use_container_width=True)

                # 상세 수치 표
                st.markdown("**📅 상세 수치 표**")
                display_trend_df = trend_df[['날짜', '업체명', '총 SKU', 'BEST PRICE 개수', 'BEST PRICE 비중(%)', 'BAD 개수']]
                st.dataframe(display_trend_df, use_container_width=True, hide_index=True)

            # --- 탭 2: 최신 일자 BAD 통합 추출 ---
            with tab2:
                # 가장 최신 날짜 찾기
                latest_date = trend_df['날짜'].max()
                latest_subset = trend_df[trend_df['날짜'] == latest_date]
                total_latest_bad = latest_subset['BAD 개수'].sum()
                
                st.subheader(f"가장 최근 날짜 ({latest_date}) 통합 가격 업데이트 리스트")

                if total_latest_bad > 0:
                    st.markdown(f'''
                    <div class="bot-box">
                        <span class="big-font">🤖 봇의 브리핑:</span><br>
                        가장 최근인 <b>{latest_date}</b> 기준으로 총 <span class="bad-text">{total_latest_bad:,}개</span>의 상품이 최저가를 뺏겼습니다.<br>
                        아래 리스트는 업로드하신 <b>모든 업체의 BAD 상품을 하나로 합친 것</b>입니다. 버튼을 눌러 통합 CSV를 다운로드하세요!
                    </div>
                    ''', unsafe_allow_html=True)

                    # 각 업체의 BAD 데이터프레임을 하나로 합치기
                    latest_bad_dfs = latest_subset['bad_df'].tolist()
                    combined_bad_df = pd.concat(latest_bad_dfs, ignore_index=True) if latest_bad_dfs else pd.DataFrame()

                    # 화면에 보여줄 핵심 컬럼
                    display_cols = ['업체명', '상품ID', '옵션', '최저가', '판매입찰가', '희망조정가']
                    actual_cols = [c for c in display_cols if c in combined_bad_df.columns]

                    st.dataframe(combined_bad_df[actual_cols], use_container_width=True, hide_index=True)

                    # 통합 CSV 다운로드 버튼
                    csv_data = combined_bad_df[actual_cols].to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    
                    st.download_button(
                        label=f"📥 {latest_date} 통합 BAD 상품 CSV 다운로드",
                        data=csv_data,
                        file_name=f"전체업체통합_{latest_date}_가격업데이트양식.csv",
                        mime="text/csv",
                        type="primary"
                    )
                else:
                    st.success(f"🎉 완벽합니다! {latest_date} 기준으로 가격을 내려야 할 BAD 상품이 하나도 없습니다.")
                    st.balloons()
