import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Rekening Mandiri", layout="wide")
st.title("📄 Extractor Rekening Koran Mandiri – FIXED PLACEMENT")

uploaded = st.file_uploader("Upload PDF Rekening Mandiri", type=["pdf"])

# ======= Regex =======
r_tanggal = re.compile(r"^(?P<tgl>\d{2} \w{3} \d{4}),?$")
r_jam     = re.compile(r"^(?P<jam>\d{2}:\d{2}:\d{2})$")
r_ref     = re.compile(r"^\d{10,}$")  # angka panjang
r_amount  = re.compile(r".*?(-?\d[\d.,]*)\s+(-?\d[\d.,]*)\s+(-?\d[\d.,]*)$")

def to_float(x):
    if not x: return None
    x = x.replace(".", "").replace(",", ".")
    try: return float(x)
    except: return None

def extract_amounts(line):
    m = r_amount.match(line)
    if not m:
        return None, None, None
    return to_float(m.group(1)), to_float(m.group(2)), to_float(m.group(3))

# ==========================
# PARSER MANDIRI FIX PLACEMENT
# ==========================
def parse(pdf_bytes):
    rows = []

    tgl = None
    jam = None
    remarks = []
    refs = []
    amount_line = ""

    def flush():
        if not tgl: return
        debit, credit, saldo = extract_amounts(amount_line)
        rows.append([
            tgl,
            jam,
            " ".join(remarks),
            " ".join(refs),
            debit,
            credit,
            saldo
        ])

    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            lines = text.splitlines()

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # ---- Ambil tanggal ----
                m = r_tanggal.match(line)
                if m:
                    flush()  # flush blok lama
                    tgl = m.group("tgl")
                    remarks = []
                    refs = []
                    amount_line = ""

                    # jam ada di baris berikutnya
                    if i+1 < len(lines):
                        m2 = r_jam.match(lines[i+1].strip())
                        if m2:
                            jam = m2.group("jam")
                            i += 2
                            continue

                # ---- Reference ----
                if r_ref.match(line):
                    refs.append(line)
                    i += 1
                    continue

                # ---- Amount ----
                d, c, s = extract_amounts(line)
                if d is not None:
                    amount_line = line
                    i += 1
                    continue

                # ---- Remark ----
                if line:
                    remarks.append(line)

                i += 1

    flush()  # flush terakhir
    return pd.DataFrame(rows, columns=[
        "Tanggal","Waktu","Keterangan","Reference","Debit","Kredit","Saldo"
    ])

# ==========================
# Streamlit Execution
# ==========================
if uploaded:
    st.info("📥 Membaca dan memproses PDF...")
    pdf_bytes = BytesIO(uploaded.read())

    try:
        df = parse(pdf_bytes)
        st.success("Berhasil membaca data Mandiri!")
        st.dataframe(df, use_container_width=True)

        # download
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        out.seek(0)

        st.download_button(
            "⬇️ Download Excel Rekening Mandiri",
            data=out,
            file_name="RekapMandiri.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Error: {e}")
