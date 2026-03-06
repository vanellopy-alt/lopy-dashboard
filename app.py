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
st.markdown("매일 생성되는 **여러 날짜의 엑셀 파일들**을 한꺼번에 드래그해서 올려주세요. 점유율 변화 추이와 최신 업데이트용 CSV를 동시에 뽑아드립니다!")

# ==========================================
# 📂 파일 다중 업로드 컴포넌트
# ==========================================
uploaded_files = st.file_uploader("엑셀 파일 여러 개 동시 업로드 (.xlsx)", type=["xlsx"], accept_multiple_files=True)

if uploaded_files:
    with st.spinner('여러 날짜의 데이터를 분석하여 트렌드를 그리는 중입니다... ⏳'):
        trend_data = []
        vendor_name = "알 수 없음"

        for file in uploaded_files:
            try:
                # 엑셀 파일에서 '입찰트래킹' 시트 읽어오기
                df = pd.read_excel(file, sheet_name='입찰트래킹', engine='openpyxl')
                
                # 업체명 추출
                if '업체명' in df.columns:
                    vendor_name = df['업체명'].iloc[0]
                else:
                    vendor_name = file.name.split('_')[0]

                # 파일명에서 날짜(숫자 4자리, 예: 0305) 추출 시도
                match = re.search(r'(\d{4})', file.name)
                date_str = match.group(1) if match else file.name

                # 상태별 개수 집계
                total_sku = len(df)
                bad_df = df[df['가격현황'] == 'BAD'].copy()
                best_df = df[df['가격현황'] == 'BEST PRICE'].copy()

                bad_count = len(bad_df)
                best_count = len(best_df)
                best_ratio = (best_count / total_sku * 100) if total_sku > 0 else 0

                # 트렌드 리스트에 데이터 추가
                trend_data.append({
                    '날짜': date_str,
                    '업체명': vendor_name,
                    '총 SKU': total_sku,
                    'BEST PRICE 비중(%)': round(best_ratio, 1),
                    'BEST PRICE 개수': best_count,
                    'BAD 개수': bad_count,
                    'bad_df': bad_df
                })
            except Exception as e:
                st.error(f"'{file.name}' 파일을 읽는 중 오류가 발생했습니다. LOPY 파일이 맞는지 확인해 주세요.")
                continue

        # 데이터를 날짜 순으로 정렬
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            trend_df = trend_df.sort_values('날짜')

            st.divider()

            # ==========================================
            # 🗂️ 탭(Tab) 화면 구성
            # ==========================================
            tab1, tab2 = st.tabs(["📈 시계열 트렌드 대시보드", "🚨 최신 BAD 상품 대량 업데이트"])

            # --- 탭 1: 트렌드 대시보드 ---
            with tab1:
                st.subheader(f"🏢 [{vendor_name}] BEST PRICE 점유율 변화 추이")
                
                if len(trend_df) > 1:
                    # Plotly 라이브러리를 사용한 인터랙티브 꺾은선 그래프
                    fig = px.line(
                        trend_df, x='날짜', y='BEST PRICE 비중(%)',
                        text='BEST PRICE 비중(%)',
                        markers=True,
                        color_discrete_sequence=['#2A9D8F']
                    )
                    fig.update_traces(textposition="top center", texttemplate='%{text}%', marker=dict(size=12, line=dict(width=2, color='white')))
                    fig.update_layout(
                        yaxis_title="BEST PRICE 비중 (%)", 
                        xaxis_title="데이터 기준일", 
                        height=450,
                        plot_bgcolor='white',
                        yaxis=dict(gridcolor='#eeeeee'),
                        xaxis=dict(gridcolor='#eeeeee')
                    )
                    
                    # 화면에 그래프 출력
                    st.plotly_chart(fig, use_container_width=True)

                    # 상세 수치 표
                    st.markdown("**📅 날짜별 상세 수치**")
                    display_trend_df = trend_df[['날짜', '총 SKU', 'BEST PRICE 개수', 'BEST PRICE 비중(%)', 'BAD 개수']]
                    st.dataframe(display_trend_df, use_container_width=True, hide_index=True)
                else:
                    st.info("💡 트렌드 그래프를 보시려면 최소 **2개 이상의 서로 다른 날짜 파일**을 올려주세요! (예: 0304 파일과 0305 파일 함께 업로드)")

            # --- 탭 2: 최신 일자 BAD 추출 ---
            with tab2:
                # 가장 최신(마지막) 날짜의 데이터만 가져옴
                latest_data = trend_df.iloc[-1]
                latest_date = latest_data['날짜']
                latest_bad_count = latest_data['BAD 개수']
                latest_bad_df = latest_data['bad_df']

                st.subheader(f"가장 최근 날짜 ({latest_date}) 가격 업데이트 리스트")

                if latest_bad_count > 0:
                    st.markdown(f'''
                    <div class="bot-box">
                        <span class="big-font">🤖 봇의 브리핑:</span><br>
                        올려주신 파일 중 가장 최근인 <b>{latest_date}</b> 기준으로 <span class="bad-text">{latest_bad_count:,}개</span>의 상품이 최저가를 뺏겼습니다.<br>
                        아래 버튼을 눌러 CSV를 다운로드하고 시스템에 바로 업로드하세요!
                    </div>
                    ''', unsafe_allow_html=True)

                    # 화면에 보여줄 핵심 컬럼 추리기
                    display_cols = ['상품ID', '옵션', '최저가', '판매입찰가', '희망조정가']
                    actual_cols = [c for c in display_cols if c in latest_bad_df.columns]

                    st.dataframe(latest_bad_df[actual_cols], use_container_width=True, hide_index=True)

                    # CSV 다운로드 버튼 생성
                    csv_data = latest_bad_df[actual_cols].to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    
                    st.download_button(
                        label=f"📥 {latest_date} 기준 BAD 상품 CSV 다운로드",
                        data=csv_data,
                        file_name=f"{vendor_name}_{latest_date}_가격업데이트양식.csv",
                        mime="text/csv",
                        type="primary"
                    )
                else:
                    st.success(f"🎉 완벽합니다! {latest_date} 기준으로 가격을 내려야 할 BAD 상품이 하나도 없습니다.")
                    st.balloons()
