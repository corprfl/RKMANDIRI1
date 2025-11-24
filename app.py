import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Mandiri FINAL", layout="wide")
st.title("📄 Extractor Rekening Koran Mandiri (Salin Benar 100%)")

uploaded = st.file_uploader("Upload PDF Rekening Mandiri", type=["pdf"])

# =======================================================
# REGEX DEFINITIONS
# =======================================================
r_tanggal_only = re.compile(r"^(?P<tgl>\d{2} \w{3} \d{4}),?$")
r_tanggal_jam  = re.compile(r"^(?P<tgl>\d{2} \w{3} \d{4}),\s*(?P<jam>\d{2}:\d{2}:\d{2})")
r_jam          = re.compile(r"^(?P<jam>\d{2}:\d{2}:\d{2})$")
r_ref          = re.compile(r"^\d{10,}$")   # angka panjang
r_amount       = re.compile(r".*?(-?\s?\d[\d.,]*)\s+(-?\s?\d[\d.,]*)\s+(-?\s?\d[\d.,]*)$")


def to_float(x):
    if not x: 
        return None
    x = x.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(x)
    except:
        return None


def extract_amount(line):
    m = r_amount.match(line)
    if not m:
        return None, None, None
    return (
        to_float(m.group(1)),
        to_float(m.group(2)),
        to_float(m.group(3))
    )


# =======================================================
# PARSER FINAL
# =======================================================
def parse(pdf_bytes):
    rows = []
    tgl = None
    jam = None
    remarks = []
    ref = ""
    amount_line = ""

    def flush():
        if not tgl:
            return
        debit, credit, saldo = extract_amount(amount_line)
        rows.append([
            tgl,
            jam,
            " ".join(remarks).strip(),
            ref.strip(),
            debit,
            credit,
            saldo
        ])

    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            lines = page.extract_text().splitlines()

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # 1) CASE: tanggal + jam satu baris
                m = r_tanggal_jam.match(line)
                if m:
                    flush()
                    tgl = m.group("tgl")
                    jam = m.group("jam")
                    remarks = []
                    ref = ""
                    amount_line = ""

                    # single-line langsung ada amount
                    d, c, s = extract_amount(line)
                    if d is not None:
                        amount_line = line
                        flush()
                        tgl = None
                    i += 1
                    continue

                # 2) CASE: tanggal sendiri (jam di baris bawah)
                m = r_tanggal_only.match(line)
                if m:
                    flush()
                    tgl = m.group("tgl")
                    remarks = []
                    ref = ""
                    amount_line = ""

                    if i + 1 < len(lines):
                        m2 = r_jam.match(lines[i+1].strip())
                        if m2:
                            jam = m2.group("jam")
                            i += 2
                            continue

                # 3) Reference
                if r_ref.match(line):
                    ref = line
                    i += 1
                    continue

                # 4) Amount
                d, c, s = extract_amount(line)
                if d is not None:
                    amount_line = line
                    i += 1
                    continue

                # 5) Remark
                if line:
                    remarks.append(line)

                i += 1

    flush()
    return pd.DataFrame(rows, columns=[
        "Tanggal","Waktu","Keterangan","Reference","Debit","Kredit","Saldo"
    ])


# =======================================================
# STREAMLIT EXEC
# =======================================================
if uploaded:
    st.info("📥 Membaca PDF...")
    pdf_bytes = BytesIO(uploaded.read())

    try:
        df = parse(pdf_bytes)
        st.success("Berhasil membaca data Mandiri!")
        st.dataframe(df, use_container_width=True)

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)

        st.download_button(
            "⬇️ Download Excel",
            data=buffer,
            file_name="RekapMandiri.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(str(e))
