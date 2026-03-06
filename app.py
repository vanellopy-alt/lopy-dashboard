import streamlit as st
import pandas as pd

# ==========================================
# ⚙️ 페이지 기본 설정 (넓은 화면, 아이콘 설정)
# ==========================================
st.set_page_config(page_title="LOPY 가격방어 봇", page_icon="🤖", layout="wide")

# ==========================================
# 🎨 커스텀 CSS (예쁜 UI를 위한 스타일링)
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
st.title("🤖 LOPY 최저가 방어 요약 봇")
st.markdown("앞서 자동화 프로그램으로 쪼개진 **업체별 최종 엑셀 파일**을 올려주세요. 1초 만에 분석해 드립니다!")

# ==========================================
# 📂 파일 업로드 컴포넌트
# ==========================================
uploaded_file = st.file_uploader("엑셀 파일 업로드 (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        # 엑셀 파일에서 '입찰트래킹' 시트 읽어오기
        with st.spinner('데이터를 씹고 뜯고 맛보는 중입니다... ⏳'):
            df = pd.read_excel(uploaded_file, sheet_name='입찰트래킹', engine='openpyxl')
        
        # 기본 정보 추출
        vendor_name = df['업체명'].iloc[0] if '업체명' in df.columns else uploaded_file.name.split('_')[0]
        total_sku = len(df)
        
        # 상태별 개수 집계
        bad_df = df[df['가격현황'] == 'BAD'].copy()
        bad_count = len(bad_df)
        best_count = len(df[df['가격현황'] == 'BEST PRICE'])
        good_count = len(df[df['가격현황'] == 'GOOD'])
        single_count = len(df[df['가격현황'] == 'Single BID'])
        
        st.divider()
        
        # ==========================================
        # 📊 요약 리포트 (메트릭 카드)
        # ==========================================
        st.subheader(f"🏢 [{vendor_name}] 요약 리포트")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📦 총 SKU 개수", f"{total_sku:,}개")
        col2.metric("🚨 BAD (최저가 뺏김)", f"{bad_count:,}개", f"{(bad_count/total_sku)*100:.1f}%", delta_color="inverse")
        col3.metric("🟢 BEST PRICE", f"{best_count:,}개")
        col4.metric("🟡 GOOD / Single BID", f"{good_count + single_count:,}개")
        
        # ==========================================
        # 💬 챗봇 브리핑
        # ==========================================
        if bad_count > 0:
            st.markdown(f"""
            <div class="bot-box">
                <span class="big-font">🤖 봇의 브리핑:</span><br>
                현재 <b>{vendor_name}</b>의 전체 {total_sku:,}개 상품 중, <span class="bad-text">{bad_count:,}개</span>의 상품이 최저가를 뺏겼습니다!<br>
                아래 리스트를 확인하고 즉시 가격을 <span style='color:blue;'>[희망조정가]</span>로 수정하여 최저가를 탈환하세요!
            </div>
            """, unsafe_allow_html=True)
            
            # 화면에 보여줄 핵심 컬럼만 추려내기
            display_cols = ['상품ID', '옵션', '최저가', '판매입찰가', '희망조정가']
            actual_cols = [c for c in display_cols if c in bad_df.columns]
            
            # 데이터프레임 시각화
            st.dataframe(bad_df[actual_cols], use_container_width=True, hide_index=True)
            
            # CSV 다운로드 버튼
            csv_data = bad_df[actual_cols].to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            
            col_blank, col_btn = st.columns([3, 1])
            with col_btn:
                st.download_button(
                    label="📥 BAD 상품만 CSV 다운로드",
                    data=csv_data,
                    file_name=f"{vendor_name}_BAD리스트_업데이트용.csv",
                    mime="text/csv",
                    type="primary"
                )
        else:
            st.success("🎉 완벽합니다! 현재 가격을 내려야 할 BAD 상품이 하나도 없습니다. 최저가 방어 100% 성공!")
            st.balloons() # 축하 애니메이션
            
    except Exception as e:
        st.error(f"파일을 읽는 중 문제가 발생했습니다. (LOPY 스플리터로 생성된 파일인지 확인해주세요!) 에러 상세: {e}")