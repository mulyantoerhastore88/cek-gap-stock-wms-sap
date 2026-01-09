import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")

st.title("📊 Dashboard Analisa Stock & Transfer")
st.markdown("""
Aplikasi ini membandingkan data **Stock Opname (WMS)** dengan **Data SAP**.
Fitur baru: **Detail Batch Number** (dari sheet `Stock_SAP_Detail`).
""")

# --- 1. File Uploader ---
uploaded_file = st.file_uploader("Upload File Excel Stock (xlsx)", type=['xlsx'])

if uploaded_file is not None:
    try:
        # --- 2. Load Data ---
        with st.spinner('Membaca data... (Mungkin butuh waktu sedikit lebih lama karena memuat detail batch)'):
            # Load Summary Data
            df_recap = pd.read_excel(uploaded_file, sheet_name='Recap_GAP')
            df_sap_sum = pd.read_excel(uploaded_file, sheet_name='Stock_SAP_SUM', header=3)
            
            # Load Detail Data (Untuk Info Batch)
            # Pastikan nama sheet sesuai dengan file asli
            try:
                df_sap_detail = pd.read_excel(uploaded_file, sheet_name='Stock_SAP_Detail')
                # Bersihkan header detail jika perlu (kadang file SAP detail headernya langsung di row 1)
                # Asumsi header detail normal (row 1), jika tidak nanti disesuaikan
            except:
                st.warning("Sheet 'Stock_SAP_Detail' tidak ditemukan. Info batch tidak dapat ditampilkan.")
                df_sap_detail = pd.DataFrame()

        st.success("Data berhasil dimuat!")

        # --- 3. Data Cleaning & Processing ---
        
        # Standardisasi Kolom Key
        df_recap['SAP_CODE'] = df_recap['SAP_CODE'].astype(str)
        df_sap_sum['SAP_CODE'] = df_sap_sum['SAP_CODE'].astype(str)
        if not df_sap_detail.empty:
            df_sap_detail['SAP_CODE'] = df_sap_detail['SAP_CODE'].astype(str)
            df_sap_detail['Batch'] = df_sap_detail['Batch'].astype(str)

        # Bersihkan nama kolom
        df_recap.columns = [c.strip() for c in df_recap.columns]
        df_sap_sum.columns = [c.strip() for c in df_sap_sum.columns]

        # --- Pre-processing Data Utama (Summary) ---
        # A. Stock F211
        sap_f211 = df_sap_sum[df_sap_sum['Storage_Location'] == 'F211'][['SAP_CODE', 'Total']].rename(columns={'Total': 'SAP_F211_Stock'})
        
        # B. Stock Cabang
        sap_branches = df_sap_sum[df_sap_sum['Storage_Location'] != 'F211']
        sap_branches_agg = sap_branches.groupby('SAP_CODE')['Total'].sum().reset_index().rename(columns={'Total': 'Total_Branch_Stock'})

        # C. Merge Summary
        merged_df = df_recap.merge(sap_f211, on='SAP_CODE', how='left')
        merged_df = merged_df.merge(sap_branches_agg, on='SAP_CODE', how='left')
        
        merged_df['SAP_F211_Stock'] = merged_df['SAP_F211_Stock'].fillna(0)
        merged_df['Total_Branch_Stock'] = merged_df['Total_Branch_Stock'].fillna(0)
        
        # --- 4. DETAIL SKU SECTION ---
        st.divider()
        st.header("🔎 Cek Detail Stock (Level Batch)")
        
        sku_list = merged_df['SAP_CODE'].unique().tolist()
        selected_sku = st.selectbox("Pilih SKU (SAP CODE):", sku_list)
        
        if selected_sku:
            item_data = merged_df[merged_df['SAP_CODE'] == selected_sku].iloc[0]
            
            # --- Header Info ---
            st.subheader(f"{item_data['Product_Description']}")
            st.caption(f"SAP CODE: {selected_sku}")
            
            # --- Metrics ---
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("WMS Stock (System)", f"{item_data['WMS_STOCK']:,.0f}")
            m2.metric("Stock Fisik (Opname)", f"{item_data['Stock_Fisik_08JAN']:,.0f}")
            m3.metric("Stock SAP F211", f"{item_data['SAP_F211_Stock']:,.0f}", 
                      delta=f"{item_data['SAP_F211_Stock'] - item_data['WMS_STOCK']:.0f} vs WMS" if item_data['SAP_F211_Stock'] != item_data['WMS_STOCK'] else None)
            m4.metric("GAP (Fisik - WMS)", f"{item_data['GAP_QTY']:,.0f}", delta_color="inverse")
            m5.metric("Total Stock Cabang", f"{item_data['Total_Branch_Stock']:,.0f}")

            # --- TABEL DETAIL BATCH ---
            st.markdown("---")
            st.markdown("#### 📦 Detail Stock per Lokasi & Batch (SAP)")
            
            if not df_sap_detail.empty:
                # Filter detail SAP
                detail_sku = df_sap_detail[df_sap_detail['SAP_CODE'] == selected_sku].copy()
                
                if not detail_sku.empty:
                    # Pilih kolom yang relevan
                    # Sesuaikan nama kolom dengan file asli: 'Storage_Location', 'Batch', 'Unrestricted'
                    cols_to_show = ['Storage_Location', 'Desc_Storage_Loc', 'Batch', 'Unrestricted']
                    
                    # Pastikan kolom ada (error handling jika nama kolom beda dikit)
                    available_cols = [c for c in cols_to_show if c in detail_sku.columns]
                    display_table = detail_sku[available_cols]
                    
                    # Sorting: F211 duluan, lalu Quantity terbesar
                    display_table['is_f211'] = display_table['Storage_Location'] == 'F211'
                    display_table = display_table.sort_values(by=['is_f211', 'Unrestricted'], ascending=[False, False])
                    display_table = display_table.drop(columns=['is_f211'])
                    
                    # Tampilkan
                    st.dataframe(
                        display_table,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Storage_Location": "Lokasi",
                            "Desc_Storage_Loc": "Nama Cabang/Gudang",
                            "Batch": "Batch Number",
                            "Unrestricted": st.column_config.NumberColumn("Qty Stock", format="%d")
                        }
                    )
                else:
                    st.info("Tidak ada data detail batch di SAP untuk item ini.")
            else:
                st.warning("Data Stock_SAP_Detail tidak tersedia.")

        # --- 5. GLOBAL ANALYSIS ---
        st.divider()
        st.header("📈 Analisa Global GAP")
        
        # Filter & Sort
        gap_data = merged_df[merged_df['GAP_QTY'] != 0].copy()
        top_n = st.slider("Jumlah Top Item", 5, 50, 10)
        gap_data['Abs_GAP'] = gap_data['GAP_QTY'].abs()
        top_gap_items = gap_data.sort_values(by='Abs_GAP', ascending=False).head(top_n)

        # Chart
        fig = go.Figure()
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['WMS_STOCK'], name='WMS System', marker_color='gray'))
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['Stock_Fisik_08JAN'], name='Stock Fisik', marker_color='blue'))
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['Total_Branch_Stock'], name='Total Cabang', marker_color='orange'))
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['GAP_QTY'], name='GAP Qty', marker_color='red'))
        
        fig.update_layout(barmode='group', xaxis_title="SAP CODE", yaxis_title="Qty", title=f"Top {top_n} Item Comparison")
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Terjadi error: {e}")
        st.info("Tips: Pastikan file Excel memiliki sheet 'Recap_GAP', 'Stock_SAP_SUM', dan 'Stock_SAP_Detail'.")

else:
    st.info("Silakan upload file Excel.")
