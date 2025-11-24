import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Mandiri", layout="wide")
st.title("📄 Extractor Rekening Koran Mandiri – FINAL FIX (2 Pola)")

uploaded = st.file_uploader("Upload PDF Rekening Mandiri", type=["pdf"])

# ============================================================
# REGEX
# ============================================================
r_tanggal_only = re.compile(r"^(?P<tgl>\d{2} \w{3} \d{4}),?$")
r_tanggal_jam  = re.compile(r"^(?P<tgl>\d{2} \w{3} \d{4}),\s*(?P<jam>\d{2}:\d{2}:\d{2})")
r_jam          = re.compile(r"^(?P<jam>\d{2}:\d{2}:\d{2})$")
r_ref          = re.compile(r"^\d{10,}$")
r_amount       = re.compile(r".*?(-?\d[\d.,]*)\s+(-?\d[\d.,]*)\s+(-?\d[\d.,]*)$")


def to_float(x):
    if not x: 
        return None
    x = x.replace(".", "").replace(",", ".")
    try:
        return float(x)
    except:
        return None


def extract_amounts(line):
    m = r_amount.match(line)
    if not m:
        return None, None, None
    return (
        to_float(m.group(1)),
        to_float(m.group(2)),
        to_float(m.group(3))
    )


# ============================================================
# PARSER
# ============================================================
def parse(pdf_bytes):
    rows = []

    tgl = None
    jam = None
    remarks = []
    refs = []
    amount_line = ""

    def flush():
        if not tgl:
            return
        debit, credit, saldo = extract_amounts(amount_line)
        rows.append([
            tgl,
            jam,
            " ".join(remarks).strip(),
            " ".join(refs).strip(),
            debit,
            credit,
            saldo
        ])

    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.splitlines()

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # ===========================
                # CASE 1: Tanggal + jam satu baris
                # ===========================
                m = r_tanggal_jam.match(line)
                if m:
                    flush()
                    tgl = m.group("tgl")
                    jam = m.group("jam")
                    remarks = []
                    refs = []
                    amount_line = ""

                    # jika baris itu sendiri mengandung amount → langsung selesai
                    d, c, s = extract_amounts(line)
                    if d is not None:
                        amount_line = line
                        flush()
                        tgl = None
                    i += 1
                    continue

                # ===========================
                # CASE 2: Tanggal saja
                # ===========================
                m = r_tanggal_only.match(line)
                if m:
                    flush()
                    tgl = m.group("tgl")
                    remarks = []
                    refs = []
                    amount_line = ""

                    # jam pada baris berikutnya
                    if i + 1 < len(lines):
                        m2 = r_jam.match(lines[i+1].strip())
                        if m2:
                            jam = m2.group("jam")
                            i += 2
                            continue

                # ===========================
                # CASE 3: Reference
                # ===========================
                if r_ref.match(line):
                    refs.append(line)
                    i += 1
                    continue

                # ===========================
                # CASE 4: Amount (3 angka terakhir)
                # ===========================
                d, c, s = extract_amounts(line)
                if d is not None:
                    amount_line = line
                    i += 1
                    continue

                # ===========================
                # CASE 5: Remark
                # ===========================
                if line:
                    remarks.append(line)

                i += 1

    flush()
    return pd.DataFrame(rows, columns=[
        "Tanggal","Waktu","Keterangan","Reference","Debit","Kredit","Saldo"
    ])


# ============================================================
# Streamlit Execution
# ============================================================
if uploaded:
    st.info("📥 Membaca PDF...")
    pdf_bytes = BytesIO(uploaded.read())

    try:
        df = parse(pdf_bytes)
        st.success("Berhasil membaca data Mandiri!")
        st.dataframe(df, use_container_width=True)

        # download excel
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
        st.error(f"❌ Error parsing: {e}")
