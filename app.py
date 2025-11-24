import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO
import re

st.set_page_config(page_title="Extractor Mandiri XY", layout="wide")
st.title("📄 Extractor Rekening Koran Mandiri – XY Mode (FINAL)")

uploaded = st.file_uploader("Upload PDF Rekening Mandiri", type=["pdf"])


# =========================================================
# HELPERS
# =========================================================

ref_pattern = re.compile(r"^\d{10,}$")

amount_pattern = re.compile(
    r"(-?\s?\d[\d.,]*)\s+(-?\s?\d[\d.,]*)\s+(-?\s?\d[\d.,]*)$"
)

def to_float(x):
    if not x:
        return None
    x = x.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(x)
    except:
        return None


# =========================================================
# XY PARSER — MANDIRI BANK LAYOUT
# =========================================================

def parse(pdf_bytes):
    rows = []

    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:

            # ambil semua word + koordinat
            words = page.extract_words()

            # group per baris vertikal
            lines = {}
            for w in words:
                top = round(w["top"])  # normalisasi
                text = w["text"]

                if top not in lines:
                    lines[top] = []
                lines[top].append(w)

            # sort baris dari atas → bawah
            sorted_lines = sorted(lines.items(), key=lambda x: x[0])

            # state transaksi
            tgl = None
            jam = None
            remarks = []
            ref = ""
            debit = None
            credit = None
            saldo = None

            def flush():
                nonlocal tgl, jam, remarks, ref, debit, credit, saldo
                if not tgl:
                    return
                rows.append([
                    tgl,
                    jam,
                    " ".join(remarks).strip(),
                    ref,
                    debit,
                    credit,
                    saldo
                ])
                # reset
                tgl = None
                jam = None
                remarks = []
                ref = ""
                debit = credit = saldo = None

            # ----------------------------------------------------
            # PARSE TIAP BARIS
            # ----------------------------------------------------
            for top, wordlist in sorted_lines:
                # sort per posisi x (kolom)
                wordlist = sorted(wordlist, key=lambda w: w["x0"])
                line_text = " ".join([w["text"] for w in wordlist])

                # 1) TANGGAL + JAM (satu baris)
                m = re.match(r"(\d{2} \w{3} \d{4}),\s*(\d{2}:\d{2}:\d{2})", line_text)
                if m:
                    flush()
                    tgl = m.group(1)
                    jam = m.group(2)
                    continue

                # 2) TANGGAL SAJA (baris berikutnya jam)
                m = re.match(r"(\d{2} \w{3} \d{4}),$", line_text)
                if m:
                    flush()
                    tgl = m.group(1)
                    continue

                # 3) JAM SAJA (setelah tanggal)
                m = re.match(r"(\d{2}:\d{2}:\d{2})$", line_text)
                if m and tgl and jam is None:
                    jam = m.group(1)
                    continue

                # 4) AMOUNT LINE
                m = amount_pattern.search(line_text)
                if m:
                    debit = to_float(m.group(1))
                    credit = to_float(m.group(2))
                    saldo = to_float(m.group(3))
                    continue

                # 5) REFERENCE (angka panjang)
                if ref_pattern.match(line_text):
                    ref = line_text
                    continue

                # 6) BUANG 99102
                if line_text == "99102":
                    continue

                # 7) REMARK
                # syarat: bukan amount, bukan reference, bukan jam, bukan tanggal
                if not re.match(r"^\d{2} \w{3} \d{4}", line_text) \
                   and not re.match(r"^\d{2}:\d{2}:\d{2}$", line_text) \
                   and not ref_pattern.match(line_text):

                    remarks.append(line_text)

            flush()

    df = pd.DataFrame(rows, columns=[
        "Tanggal","Waktu","Keterangan","Reference","Debit","Kredit","Saldo"
    ])
    return df


# =========================================================
# STREAMLIT EXECUTION
# =========================================================

if uploaded:
    st.info("📥 Membaca PDF (XY Mode)...")

    pdf_bytes = BytesIO(uploaded.read())

    try:
        df = parse(pdf_bytes)
        st.success("Berhasil membaca data Mandiri!")
        st.dataframe(df, use_container_width=True)

        # EXCEL
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)

        st.download_button(
            "⬇️ Download Excel",
            data=buffer,
            file_name="RekapMandiri_XY.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error("❌ Error parsing: " + str(e))
