
import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="Extractor Mandiri - CorpRFL")

st.markdown("""
<style>
body { background-color: #0d1117; color: #ffffff; }
.stButton>button { background-color: #0070C0; color: white; border-radius: 8px; }
</style>
<h2>📘 Extractor Rekening Koran Mandiri</h2>
<p>By Reza Fahlevi Lubis BKP @zavibis</p>
""", unsafe_allow_html=True)

uploaded = st.file_uploader("Upload PDF Mandiri", type=["pdf"])
if uploaded:
    pages_text = []
    with pdfplumber.open(uploaded) as pdf:
        for page in pdf.pages:
            pages_text.append(page)

    rows = []
    nomor_rekening = ""
    currency = "IDR"
    saldo_awal = None

    for page in pages_text:
        chars = page.chars

        # Detect account number from header
        header_text = page.extract_text()
        m = re.search(r"(\d{10,16})", header_text)
        if m:
            nomor_rekening = m.group(1)

        # Group by y position
        lines = {}
        for c in chars:
            y = round(c["top"], 1)
            if y not in lines:
                lines[y] = []
            lines[y].append(c)

        sorted_lines = sorted(lines.items(), key=lambda x: x[0])

        buffer_ket = []
        for y, chars_line in sorted_lines:
            line = "".join([c["text"] for c in sorted(chars_line, key=lambda x: x["x0"])])

            nums = re.findall(r"[0-9][0-9.,]*", line)
            if len(nums) >= 3:
                debit = nums[-3]
                kredit = nums[-2]
                saldo = nums[-1]

                def fix(n):
                    return n.replace(".", "").replace(",", ".")

                debit = float(fix(debit)) if debit != "0.00" else 0
                kredit = float(fix(kredit)) if kredit != "0.00" else 0
                saldo = float(fix(saldo))

                if saldo_awal is None:
                    saldo_awal = saldo

                tanggal = re.findall(r"(\d{2} \w{3} \d{4})", line)
                tanggal = tanggal[0] if tanggal else ""

                rows.append([
                    nomor_rekening,
                    tanggal,
                    " ".join(buffer_ket).strip(),
                    debit,
                    kredit,
                    saldo,
                    currency,
                    saldo_awal
                ])
                buffer_ket = []
            else:
                buffer_ket.append(line)

    df = pd.DataFrame(rows, columns=[
        "Nomor Rekening", "Tanggal", "Keterangan",
        "Debit", "Kredit", "Saldo", "Currency", "Saldo Awal"
    ])

    st.dataframe(df)

    st.download_button(
        "Download Excel",
        df.to_excel(index=False, engine='openpyxl'),
        "mandiri_extracted.xlsx"
    )
