import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")

st.title("📊 Dashboard Analisa Stock & Transfer")
st.markdown("""
Aplikasi ini membandingkan data **Stock Opname (WMS)** dengan **Data SAP (F211 vs Cabang)**.
Tujuannya adalah mengidentifikasi GAP dan melihat distribusi stock di cabang lain untuk keputusan transfer.
""")

# --- 1. File Uploader ---
uploaded_file = st.file_uploader("Upload File Excel Stock (xlsx)", type=['xlsx'])

if uploaded_file is not None:
    try:
        # --- 2. Load Data ---
        # Menggunakan header=3 karena di file asli header Stock_SAP_SUM ada di baris ke-4
        with st.spinner('Membaca data...'):
            df_recap = pd.read_excel(uploaded_file, sheet_name='Recap_GAP')
            df_sap = pd.read_excel(uploaded_file, sheet_name='Stock_SAP_SUM', header=3)

        st.success("Data berhasil dimuat!")

        # --- 3. Data Cleaning & Processing ---
        
        # Pastikan SAP_CODE bertipe string agar bisa di-merge
        df_recap['SAP_CODE'] = df_recap['SAP_CODE'].astype(str)
        df_sap['SAP_CODE'] = df_sap['SAP_CODE'].astype(str)
        
        # Bersihkan nama kolom jika ada spasi berlebih
        df_recap.columns = [c.strip() for c in df_recap.columns]
        df_sap.columns = [c.strip() for c in df_sap.columns]

        # A. Proses Data SAP
        # Ambil Stock F211 (Gudang Utama SAP)
        sap_f211 = df_sap[df_sap['Storage_Location'] == 'F211'][['SAP_CODE', 'Total']]
        sap_f211 = sap_f211.rename(columns={'Total': 'SAP_F211_Stock'})

        # Ambil Stock Cabang (Selain F211) dan jumlahkan per produk
        sap_branches = df_sap[df_sap['Storage_Location'] != 'F211']
        sap_branches_agg = sap_branches.groupby('SAP_CODE')['Total'].sum().reset_index()
        sap_branches_agg = sap_branches_agg.rename(columns={'Total': 'Total_Branch_Stock'})

        # B. Gabungkan (Merge) dengan Recap_GAP
        # Left join ke Recap_GAP karena itu acuan analisa kita
        merged_df = df_recap.merge(sap_f211, on='SAP_CODE', how='left')
        merged_df = merged_df.merge(sap_branches_agg, on='SAP_CODE', how='left')

        # Isi NaN dengan 0 (artinya tidak ada record stock di SAP untuk item tersebut)
        merged_df['SAP_F211_Stock'] = merged_df['SAP_F211_Stock'].fillna(0)
        merged_df['Total_Branch_Stock'] = merged_df['Total_Branch_Stock'].fillna(0)

        # Hitung Selisih WMS vs SAP F211 (Validasi Data)
        merged_df['Diff_WMS_vs_SAP_F211'] = merged_df['WMS_STOCK'] - merged_df['SAP_F211_Stock']

        # --- 4. Dashboard Metrics ---
        
        # Filter Data yang memiliki GAP
        gap_data = merged_df[merged_df['GAP_QTY'] != 0].copy()
        
        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total SKU", f"{len(merged_df)}")
        col2.metric("SKU dengan GAP (Fisik vs WMS)", f"{len(gap_data)}")
        col3.metric("Total Qty GAP (Mutlak)", f"{gap_data['GAP_QTY'].abs().sum():,.0f}")

        # --- 5. Visualisasi & Analisa ---

        st.subheader("🔍 Analisa Distribusi Stock untuk Item GAP")
        st.info("Grafik di bawah menampilkan Item yang memiliki GAP terbesar. Gunakan ini untuk melihat apakah stock menumpuk di Cabang (Branch) atau di Gudang Utama (F211).")

        # Slider untuk memfilter top item
        top_n = st.slider("Tampilkan Top N Item dengan GAP Terbesar", 5, 50, 10)
        
        # Urutkan berdasarkan GAP mutlak terbesar
        gap_data['Abs_GAP'] = gap_data['GAP_QTY'].abs()
        top_gap_items = gap_data.sort_values(by='Abs_GAP', ascending=False).head(top_n)

        # Bar Chart Comparison
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=top_gap_items['SAP_CODE'], 
            y=top_gap_items['WMS_STOCK'], 
            name='WMS Stock (Recap)',
            marker_color='blue'
        ))
        fig.add_trace(go.Bar(
            x=top_gap_items['SAP_CODE'], 
            y=top_gap_items['Total_Branch_Stock'], 
            name='Total Stock Cabang (SAP)',
            marker_color='orange'
        ))
        fig.add_trace(go.Bar(
            x=top_gap_items['SAP_CODE'], 
            y=top_gap_items['GAP_QTY'], 
            name='GAP Qty (Fisik - WMS)',
            marker_color='red'
        ))
        
        fig.update_layout(
            title=f"Perbandingan Stock: WMS vs Cabang (Top {top_n} GAP)",
            xaxis_title="Kode Produk (SAP CODE)",
            yaxis_title="Quantity",
            barmode='group'
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- 6. Tabel Detail & Rekomendasi ---
        st.subheader("📋 Detail Data & Potensi Transfer")
        
        # Opsi Filter
        filter_type = st.radio(
            "Filter Tampilan:",
            ("Semua Item GAP", "Minus GAP (Kurang Fisik)", "Plus GAP (Lebih Fisik)"),
            horizontal=True
        )

        if filter_type == "Minus GAP (Kurang Fisik)":
            display_df = gap_data[gap_data['GAP_QTY'] < 0]
        elif filter_type == "Plus GAP (Lebih Fisik)":
            display_df = gap_data[gap_data['GAP_QTY'] > 0]
        else:
            display_df = gap_data

        # Kolom yang ditampilkan
        show_cols = [
            'SAP_CODE', 'Product_Description', 
            'WMS_STOCK', 'Stock_Fisik_08JAN', 'GAP_QTY',
            'SAP_F211_Stock', 'Total_Branch_Stock'
        ]
        
        st.dataframe(
            display_df[show_cols].sort_values('GAP_QTY'),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("""
        **Panduan Analisa Transfer:**
        * **Jika GAP Minus (Kurang):** Cek kolom `Total_Branch_Stock`. Jika stock cabang tinggi, pertimbangkan tarik stock dari cabang ke pusat.
        * **Jika GAP Plus (Lebih):** Cek kolom `Total_Branch_Stock`. Jika stock cabang rendah, ini kesempatan untuk push stock ke cabang.
        """)

        # --- 7. Download Data Hasil Olahan ---
        st.subheader("📥 Download Hasil Analisa")
        csv = merged_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Data Lengkap (CSV)",
            data=csv,
            file_name='Analisa_Stock_Gabungan.csv',
            mime='text/csv',
        )

    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses file: {e}")
        st.warning("Pastikan file Excel memiliki sheet 'Recap_GAP' dan 'Stock_SAP_SUM'. Cek juga apakah format headernya sesuai.")

else:
    st.info("Silakan upload file Excel untuk memulai analisa.")
