import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Rekening Mandiri", layout="wide")
st.title("📄 Extractor Rekening Koran Mandiri – FINAL FIX")

uploaded = st.file_uploader("Upload PDF Rekening Mandiri", type=["pdf"])


# =======================================================
# REGEX DEFINITIONS
# =======================================================
r_tanggal_jam  = re.compile(r"^(?P<tgl>\d{2} \w{3} \d{4}),\s*(?P<jam>\d{2}:\d{2}:\d{2})")
r_tanggal_only = re.compile(r"^(?P<tgl>\d{2} \w{3} \d{4}),?$")
r_jam          = re.compile(r"^(?P<jam>\d{2}:\d{2}:\d{2})$")
r_ref          = re.compile(r"^\d{10,}$")   # reference number
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
        to_float(m.group(3)),
    )


# =======================================================
# PARSER FINAL (SESUAI FORMAT KAMU)
# =======================================================
def parse(pdf_bytes):
    rows = []

    tgl = None
    jam = None
    remarks = []
    ref = ""            # angka panjang
    amount_line = ""   # baris amount

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

                # 1) Tanggal + jam (single-line)
                m = r_tanggal_jam.match(line)
                if m:
                    flush()

                    tgl = m.group("tgl")
                    jam = m.group("jam")
                    remarks = []
                    ref = ""
                    amount_line = ""

                    # single-line with amount
                    d, c, s = extract_amount(line)
                    if d is not None:
                        amount_line = line
                        flush()
                        tgl = None
                    i += 1
                    continue

                # 2) Tanggal saja
                m = r_tanggal_only.match(line)
                if m:
                    flush()

                    tgl = m.group("tgl")
                    remarks = []
                    ref = ""
                    amount_line = ""

                    # jam di baris berikutnya
                    if i + 1 < len(lines):
                        m2 = r_jam.match(lines[i+1].strip())
                        if m2:
                            jam = m2.group("jam")
                            i += 2
                            continue

                # 3) Reference number (angka panjang)
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

                # 5) Remark (hanya teks)
                if line and not line.isdigit():     # buang angka seperti "99102"
                    remarks.append(line)

                i += 1

    # FLUSH terakhir
    flush()

    df = pd.DataFrame(rows, columns=[
        "Tanggal", "Waktu", "Keterangan", "Reference",
        "Debit", "Kredit", "Saldo"
    ])
    return df


# =======================================================
# STREAMLIT EXECUTION
# =======================================================
if uploaded:
    st.info("📥 Membaca PDF...")
    pdf_bytes = BytesIO(uploaded.read())

    try:
        df = parse(pdf_bytes)
        st.success("Berhasil membaca data Mandiri!")

        st.dataframe(df, use_container_width=True)

        # EXCEL export
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)

        st.download_button(
            "⬇️ Download Excel",
            data=buffer,
            file_name="RekapMandiri.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error("❌ Error parsing: " + str(e))
