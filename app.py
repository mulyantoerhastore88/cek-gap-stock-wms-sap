import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")

st.title("📊 Dashboard Analisa Stock & Transfer")
st.markdown("""
Aplikasi ini membandingkan data **Stock Opname (WMS)** dengan **Data SAP (F211 vs Cabang)**.
Fitur baru: **Pencarian Detail per SKU** untuk melihat sebaran stock di semua lokasi.
""")

# --- 1. File Uploader ---
uploaded_file = st.file_uploader("Upload File Excel Stock (xlsx)", type=['xlsx'])

if uploaded_file is not None:
    try:
        # --- 2. Load Data ---
        with st.spinner('Membaca data...'):
            df_recap = pd.read_excel(uploaded_file, sheet_name='Recap_GAP')
            df_sap = pd.read_excel(uploaded_file, sheet_name='Stock_SAP_SUM', header=3) # Header di baris 4

        st.success("Data berhasil dimuat!")

        # --- 3. Data Cleaning & Processing ---
        
        # Standardisasi Kolom SAP_CODE
        df_recap['SAP_CODE'] = df_recap['SAP_CODE'].astype(str)
        df_sap['SAP_CODE'] = df_sap['SAP_CODE'].astype(str)
        
        # Bersihkan nama kolom
        df_recap.columns = [c.strip() for c in df_recap.columns]
        df_sap.columns = [c.strip() for c in df_sap.columns]

        # --- Pre-processing Data Utama ---
        # A. Stock F211 (Gudang Utama)
        sap_f211 = df_sap[df_sap['Storage_Location'] == 'F211'][['SAP_CODE', 'Total']].rename(columns={'Total': 'SAP_F211_Stock'})
        
        # B. Stock Cabang (Total)
        sap_branches = df_sap[df_sap['Storage_Location'] != 'F211']
        sap_branches_agg = sap_branches.groupby('SAP_CODE')['Total'].sum().reset_index().rename(columns={'Total': 'Total_Branch_Stock'})

        # C. Gabungkan Data (Master Table untuk Analisa Global)
        merged_df = df_recap.merge(sap_f211, on='SAP_CODE', how='left')
        merged_df = merged_df.merge(sap_branches_agg, on='SAP_CODE', how='left')
        
        merged_df['SAP_F211_Stock'] = merged_df['SAP_F211_Stock'].fillna(0)
        merged_df['Total_Branch_Stock'] = merged_df['Total_Branch_Stock'].fillna(0)
        
        # --- 4. NEW FEATURE: FILTER BY SKU ---
        st.divider()
        st.header("🔎 Cek Detail Stock per SKU")
        
        # Buat list unik SKU untuk dropdown, tambahkan deskripsi agar mudah dicari
        sku_list = merged_df['SAP_CODE'].unique().tolist()
        selected_sku = st.selectbox("Pilih atau Ketik SKU (SAP CODE):", sku_list)
        
        if selected_sku:
            # Ambil data spesifik item tersebut
            item_data = merged_df[merged_df['SAP_CODE'] == selected_sku].iloc[0]
            
            # Tampilkan Info Dasar
            col_info1, col_info2 = st.columns([2, 1])
            with col_info1:
                st.subheader(f"{item_data['Product_Description']}")
                st.caption(f"SAP CODE: {selected_sku}")
            
            # Metric Card Sederhana
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Stock Fisik (WMS)", f"{item_data['Stock_Fisik_08JAN']:,.0f}")
            m2.metric("Stock SAP F211", f"{item_data['SAP_F211_Stock']:,.0f}")
            m3.metric("GAP (Fisik - WMS)", f"{item_data['GAP_QTY']:,.0f}", delta_color="inverse")
            m4.metric("Total Stock di Cabang", f"{item_data['Total_Branch_Stock']:,.0f}")

            # --- TAMPILKAN STOCK DI SEMUA LOKASI (DETAIL) ---
            st.markdown("##### 📍 Sebaran Stock di Semua Lokasi (SAP)")
            
            # Filter df_sap (raw data) berdasarkan SKU yang dipilih
            stock_detail_sap = df_sap[df_sap['SAP_CODE'] == selected_sku][['Storage_Location', 'Desc_Storage_Loc', 'Total']]
            
            # Urutkan: F211 paling atas, sisanya berdasarkan jumlah stock terbesar
            stock_detail_sap['is_f211'] = stock_detail_sap['Storage_Location'] == 'F211'
            stock_detail_sap = stock_detail_sap.sort_values(by=['is_f211', 'Total'], ascending=[False, False]).drop(columns=['is_f211'])
            
            # Tampilkan Tabel
            st.dataframe(
                stock_detail_sap, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Storage_Location": "Kode Lokasi",
                    "Desc_Storage_Loc": "Nama Lokasi / Cabang",
                    "Total": "Stock SAP"
                }
            )
            
            if item_data['GAP_QTY'] < 0:
                st.warning(f"⚠️ **Rekomendasi:** Terdapat kekurangan stock fisik sebesar {abs(item_data['GAP_QTY'])}. Cek tabel di atas, apakah ada stock berlebih di cabang yang bisa ditransfer ke F211?")
            elif item_data['GAP_QTY'] > 0:
                 st.success(f"✅ **Rekomendasi:** Terdapat kelebihan stock fisik. Cek tabel di atas, cabang mana yang stock-nya sedikit dan membutuhkan supply.")

        # --- 5. DASHBOARD VISUALISASI GLOBAL (Kode Sebelumnya) ---
        st.divider()
        st.header("📈 Analisa Global (Top GAP)")
        
        # ... (Kode visualisasi sama seperti sebelumnya) ...
        gap_data = merged_df[merged_df['GAP_QTY'] != 0].copy()
        top_n = st.slider("Jumlah Top Item ditampilkan", 5, 50, 10)
        gap_data['Abs_GAP'] = gap_data['GAP_QTY'].abs()
        top_gap_items = gap_data.sort_values(by='Abs_GAP', ascending=False).head(top_n)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['WMS_STOCK'], name='WMS Stock', marker_color='blue'))
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['Total_Branch_Stock'], name='Total Cabang', marker_color='orange'))
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['GAP_QTY'], name='GAP Qty', marker_color='red'))
        
        fig.update_layout(barmode='group', xaxis_title="SAP CODE", yaxis_title="Qty", title=f"Top {top_n} Item dengan GAP Terbesar")
        st.plotly_chart(fig, use_container_width=True)
        
        # Download Button
        csv = merged_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Data Analisa (CSV)", csv, "Analisa_Stock_Lengkap.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")

else:
    st.info("Silakan upload file Excel.")
