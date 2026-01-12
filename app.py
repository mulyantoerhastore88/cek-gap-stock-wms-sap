import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")

st.title("📊 Dashboard Analisa Stock & Transfer")
st.markdown("""
**Stock Opname Analysis Center**
Mengintegrasikan data: **WMS (Opname)**, **SAP (Gudang & Cabang)**, dan **Shopee**.
""")

# --- 1. File Uploader ---
uploaded_file = st.file_uploader("Upload File Excel Stock (xlsx)", type=['xlsx'])

if uploaded_file is not None:
    try:
        # --- 2. Load Data ---
        with st.spinner('Membaca semua sheet data...'):
            # Load Data Utama
            df_recap = pd.read_excel(uploaded_file, sheet_name='Recap_GAP')
            df_sap_sum = pd.read_excel(uploaded_file, sheet_name='Stock_SAP_SUM', header=3)
            
            # Load Data Detail Batch (Optional)
            try:
                df_sap_detail = pd.read_excel(uploaded_file, sheet_name='Stock_SAP_Detail')
            except:
                df_sap_detail = pd.DataFrame()
                st.warning("Sheet 'Stock_SAP_Detail' tidak ditemukan. Info batch akan kosong.")

            # Load Data Shopee (Optional/Baru)
            try:
                df_shopee = pd.read_excel(uploaded_file, sheet_name='SHOPEE_STOCK')
            except:
                df_shopee = pd.DataFrame()
                st.warning("Sheet 'SHOPEE_STOCK' tidak ditemukan. Info stock Shopee akan kosong.")

        st.success("Data berhasil dimuat!")

        # --- 3. Data Cleaning & Processing ---
        
        # A. Standardisasi Key Column (SAP_CODE / CODE)
        df_recap['SAP_CODE'] = df_recap['SAP_CODE'].astype(str)
        df_sap_sum['SAP_CODE'] = df_sap_sum['SAP_CODE'].astype(str)
        
        # Cleaning Header
        df_recap.columns = [c.strip() for c in df_recap.columns]
        df_sap_sum.columns = [c.strip() for c in df_sap_sum.columns]

        # B. Process SAP Data
        # Stock F211 (Gudang Utama)
        sap_f211 = df_sap_sum[df_sap_sum['Storage_Location'] == 'F211'][['SAP_CODE', 'Total']].rename(columns={'Total': 'SAP_F211_Stock'})
        
        # Stock Cabang (Total)
        sap_branches = df_sap_sum[df_sap_sum['Storage_Location'] != 'F211']
        sap_branches_agg = sap_branches.groupby('SAP_CODE')['Total'].sum().reset_index().rename(columns={'Total': 'Total_Branch_Stock'})

        # C. Process Shopee Data
        if not df_shopee.empty:
            # Pastikan kolom sesuai dengan request: CODE & Stok_Tersedia
            # Kita rename CODE jadi SAP_CODE agar bisa di-merge
            df_shopee = df_shopee.rename(columns={'CODE': 'SAP_CODE', 'Stok_Tersedia': 'Shopee_Stock'})
            df_shopee['SAP_CODE'] = df_shopee['SAP_CODE'].astype(str)
            # Groupby jaga-jaga jika ada duplikasi kode
            df_shopee_agg = df_shopee.groupby('SAP_CODE')['Shopee_Stock'].sum().reset_index()
        else:
            # Dummy empty dataframe jika sheet tidak ada
            df_shopee_agg = pd.DataFrame(columns=['SAP_CODE', 'Shopee_Stock'])

        # D. MERGE ALL DATA (Master Table)
        # Base: Recap GAP
        merged_df = df_recap.merge(sap_f211, on='SAP_CODE', how='left')
        merged_df = merged_df.merge(sap_branches_agg, on='SAP_CODE', how='left')
        merged_df = merged_df.merge(df_shopee_agg, on='SAP_CODE', how='left')
        
        # Fill NaN
        merged_df['SAP_F211_Stock'] = merged_df['SAP_F211_Stock'].fillna(0)
        merged_df['Total_Branch_Stock'] = merged_df['Total_Branch_Stock'].fillna(0)
        merged_df['Shopee_Stock'] = merged_df['Shopee_Stock'].fillna(0)
        
        # --- 4. DETAIL SKU SECTION ---
        st.divider()
        st.header("🔎 Cek Detail Stock per SKU")
        
        sku_list = merged_df['SAP_CODE'].unique().tolist()
        selected_sku = st.selectbox("Pilih SKU (SAP CODE):", sku_list)
        
        if selected_sku:
            item_data = merged_df[merged_df['SAP_CODE'] == selected_sku].iloc[0]
            
            # Info Header
            st.subheader(f"{item_data['Product_Description']}")
            st.caption(f"SAP CODE: {selected_sku}")
            
            # --- METRICS DISPLAY (Updated Layout) ---
            # Baris 1: Stock Internal & GAP
            m1, m2, m3 = st.columns(3)
            m1.metric("WMS Stock (System)", f"{item_data['WMS_STOCK']:,.0f}")
            m2.metric("Stock Fisik (Opname)", f"{item_data['Stock_Fisik_08JAN']:,.0f}")
            m3.metric("GAP (Fisik - WMS)", f"{item_data['GAP_QTY']:,.0f}", delta_color="inverse")
            
            st.markdown("---")
            
            # Baris 2: Sebaran Stock (SAP & Shopee)
            m4, m5, m6 = st.columns(3)
            # SAP F211
            delta_sap = item_data['SAP_F211_Stock'] - item_data['WMS_STOCK']
            m4.metric("SAP F211 (Gudang)", f"{item_data['SAP_F211_Stock']:,.0f}", 
                      delta=f"{delta_sap:.0f} vs WMS" if delta_sap != 0 else None)
            
            # Cabang
            m5.metric("Total Stock Cabang (Store)", f"{item_data['Total_Branch_Stock']:,.0f}")
            
            # Shopee (New)
            m6.metric("Stock Shopee (Marketplace)", f"{item_data['Shopee_Stock']:,.0f}", border=True)

            # --- TABEL DETAIL BATCH & LOKASI ---
            st.markdown("#### 📦 Detail Batch & Lokasi (SAP)")
            
            if not df_sap_detail.empty:
                df_sap_detail['SAP_CODE'] = df_sap_detail['SAP_CODE'].astype(str)
                detail_sku = df_sap_detail[df_sap_detail['SAP_CODE'] == selected_sku].copy()
                
                if not detail_sku.empty:
                    cols_to_show = ['Storage_Location', 'Desc_Storage_Loc', 'Batch', 'Unrestricted']
                    available_cols = [c for c in cols_to_show if c in detail_sku.columns]
                    display_table = detail_sku[available_cols]
                    
                    # Sort: F211 top
                    display_table['is_f211'] = display_table['Storage_Location'] == 'F211'
                    display_table = display_table.sort_values(by=['is_f211', 'Unrestricted'], ascending=[False, False]).drop(columns=['is_f211'])
                    
                    st.dataframe(
                        display_table,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Unrestricted": st.column_config.NumberColumn("Qty Stock", format="%d")
                        }
                    )
                else:
                    st.info("Tidak ada data detail batch di SAP untuk item ini.")
            else:
                st.write("Data detail batch tidak tersedia.")

        # --- 5. GLOBAL ANALYSIS ---
        st.divider()
        st.header("📈 Analisa Global (Top GAP Items)")
        
        # Filter GAP
        gap_data = merged_df[merged_df['GAP_QTY'] != 0].copy()
        
        top_n = st.slider("Jumlah Top Item", 5, 50, 10)
        gap_data['Abs_GAP'] = gap_data['GAP_QTY'].abs()
        top_gap_items = gap_data.sort_values(by='Abs_GAP', ascending=False).head(top_n)

        # Chart Comparison
        fig = go.Figure()
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['WMS_STOCK'], name='WMS System', marker_color='gray'))
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['Stock_Fisik_08JAN'], name='Stock Fisik', marker_color='blue'))
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['Total_Branch_Stock'], name='Total Cabang', marker_color='orange'))
        # Tambahkan Bar Shopee di Grafik
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['Shopee_Stock'], name='Stock Shopee', marker_color='green'))
        fig.add_trace(go.Bar(x=top_gap_items['SAP_CODE'], y=top_gap_items['GAP_QTY'], name='GAP Qty', marker_color='red'))
        
        fig.update_layout(barmode='group', xaxis_title="SAP CODE", yaxis_title="Qty", title=f"Top {top_n} Item Comparison")
        st.plotly_chart(fig, use_container_width=True)
        
        # Download
        csv = merged_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Data Analisa Lengkap (CSV)", csv, "Analisa_Stock_Final.csv", "text/csv")

    except Exception as e:
        st.error(f"Terjadi error: {e}")
        st.warning("Pastikan file Excel memiliki sheet: Recap_GAP, Stock_SAP_SUM, Stock_SAP_Detail, dan SHOPEE_STOCK.")

else:
    st.info("Silakan upload file Excel yang berisi data stock.")
