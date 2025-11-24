import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Rekap Mandiri – Presisi v6", layout="wide")
st.title("📄 Rekap Rekening Koran Mandiri – Mode Presisi v6 (No-AI, No-Auto)")

# =========================
# Fungsi bantu
# =========================

tanggal_re = re.compile(r"(\d{2} \w{3} \d{4}),")
jam_re = re.compile(r"(\d{2}:\d{2}:\d{2})")

def extract_transactions(text):
    lines = text.split("\n")
    tx_list = []

    current = {
        "Tanggal": "",
        "Waktu": "",
        "Keterangan": "",
        "Reference": "",
        "Debit": "",
        "Kredit": "",
        "Saldo": ""
    }

    mode = "search_date"

    for line in lines:
        line = line.strip()

        # =========================
        # DETEKSI TANGGAL BARU
        # =========================
        m = tanggal_re.search(line)
        if m:
            # simpan transaksi sebelumnya
            if current["Tanggal"]:
                tx_list.append(current.copy())

            current = {
                "Tanggal": m.group(1),
                "Waktu": "",
                "Keterangan": "",
                "Reference": "",
                "Debit": "",
                "Kredit": "",
                "Saldo": ""
            }

            # ambil jam bila di baris yang sama
            jm = jam_re.search(line)
            if jm:
                current["Waktu"] = jm.group(1)

            continue

        # =========================
        # DETEKSI JAM (baris kedua)
        # =========================
        jm = jam_re.search(line)
        if jm and current["Waktu"] == "":
            current["Waktu"] = jm.group(1)
            continue

        # =========================
        # DETEKSI REFERENCE NUMBER
        # =========================
        if re.match(r"^\d{15,}$", line):
            current["Reference"] = line
            continue

        # =========================
        # DETEKSI ANGKA DEBIT/KREDIT/SALDO
        # Urutan Mandiri: "-", debit, kredit, saldo
        # =========================
        if re.search(r"\d{1,3}(,\d{3})*\.\d{2}$", line):
            nums = re.findall(r"[\d,]+\.\d{2}", line)
            if len(nums) == 3:
                current["Debit"], current["Kredit"], current["Saldo"] = nums
                continue

        # =========================
        # SISANYA = KETERANGAN
        # =========================
        if line not in ["-", "", "–"]:
            current["Keterangan"] += line + "\n"

    # terakhir push
    if current["Tanggal"]:
        tx_list.append(current)

    return tx_list


# =========================
# UI
# =========================

uploaded = st.file_uploader("Unggah PDF Rekening Mandiri", type=["pdf"])

if uploaded:
    pdf_bytes = uploaded.read()

    all_text = ""
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            all_text += page.extract_text() + "\n"

    transactions = extract_transactions(all_text)

    df = pd.DataFrame(transactions)
    df["Keterangan"] = df["Keterangan"].str.strip()

    st.success(f"Parsing selesai – Mode Presisi v6 (Total {len(df)} transaksi).")
    st.dataframe(df, use_container_width=True)

    # Download Excel
    output = BytesIO()
    df.to_excel(output, index=False)
    st.download_button(
        "⬇ Download Rekap Mandiri v6 (Excel)",
        data=output.getvalue(),
        file_name="Rekap_Mandiri_v6.xlsx"
    )
