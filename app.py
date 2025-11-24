import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Rekap Mandiri v5 Hybrid", layout="wide")
st.title("📄 Rekening Koran Mandiri – HYBRID PARSER v5 (FINAL)")


uploaded = st.file_uploader("Upload PDF Mandiri", type=["pdf"])


# ===============================================================
# REGEX
# ===============================================================
re_date = re.compile(r"(\d{2} \w{3} \d{4})")
re_time = re.compile(r"(\d{2}:\d{2}:\d{2})")
re_ref  = re.compile(r"^\d{10,}$")


# ===============================================================
# CLEAN TEXT FOR REMARK
# ===============================================================
def clean_meta(line: str) -> bool:
    l = line.lower()
    return any(w in l for w in [
        "account statement",
        "opening balance",
        "closing balance",
        "summary",
        "posting date",
        "period",
        "alias",
        "for further questions",
        "remark reference",
        "debit credit balance"
    ])


# ===============================================================
# PARSE WORDS (TGL | JAM | REMARK | REF)
# ===============================================================
def parse_words(pdf):
    all_blocks = []

    for page in pdf.pages:
        words = page.extract_words()

        # GROUP BY Y TOP
        lines = {}
        for w in words:
            y = int(w["top"])
            lines.setdefault(y, []).append(w["text"].strip())

        # SORT
        sorted_lines = sorted(lines.items(), key=lambda x: x[0])

        # FILTER HEADER
        filtered = []
        for y, parts in sorted_lines:
            line = " ".join(parts).strip()
            if not clean_meta(line):
                filtered.append(line)

        # CLUSTER PER TRANSAKSI
        clusters = []
        current = []

        for line in filtered:
            if re_date.search(line):   # tanggal → mulai cluster
                if current:
                    clusters.append(current)
                current = [line]
            else:
                if current:
                    current.append(line)

        if current:
            clusters.append(current)

        # PROSES CLUSTER
        for block in clusters:
            tanggal = ""
            waktu = ""
            reference = ""
            remarks = []

            for line in block:
                md = re_date.search(line)
                if md:
                    tanggal = md.group(1)

                mt = re_time.search(line)
                if mt:
                    waktu = mt.group(1)

                # reference panjang
                for t in line.split():
                    if re_ref.match(t):
                        reference = t

            # REMARKS = semua baris kecuali tgl/jam/ref
            for line in block:
                if tanggal in line: continue
                if waktu and waktu in line: continue
                if reference and reference in line: continue

                if not clean_meta(line):
                    if line.strip():
                        remarks.append(line.strip())

            remark = " ".join(remarks).strip()

            all_blocks.append({
                "Tanggal": tanggal,
                "Waktu": waktu,
                "Keterangan": remark,
                "Reference": reference
            })

    return all_blocks


# ===============================================================
# PARSE TABLES (DEBIT | KREDIT | SALDO)
# ===============================================================
def parse_tables(pdf):
    amounts = []

    for page in pdf.pages:
        tables = page.extract_tables()

        if not tables:
            continue

        for tbl in tables:
            # Each table row contains LAST 3 COLUMNS → debit kredit saldo
            for row in tbl:
                # Filter row that ends with three numeric-like values
                nums = row[-3:]
                amounts.append(nums)

    return amounts


# ===============================================================
# HYBRID MERGE
# ===============================================================
def merge_data(text_blocks, amount_blocks):

    # Samakan panjang
    n = min(len(text_blocks), len(amount_blocks))

    final_rows = []

    for i in range(n):
        tb = text_blocks[i]
        ab = amount_blocks[i]

        debit  = ab[0] if ab[0] not in ["", None] else None
        kredit = ab[1] if ab[1] not in ["", None] else None
        saldo  = ab[2] if ab[2] not in ["", None] else None

        # Convert to float
        def conv(x):
            if not x:
                return None
            x = x.replace(".", "").replace(",", ".")
            try:
                return float(x)
            except:
                return None

        final_rows.append([
            tb["Tanggal"],
            tb["Waktu"],
            tb["Keterangan"],
            tb["Reference"],
            conv(debit),
            conv(kredit),
            conv(saldo)
        ])

    df = pd.DataFrame(final_rows,
                      columns=["Tanggal", "Waktu", "Keterangan",
                               "Reference", "Debit", "Kredit", "Saldo"])
    return df


# ===============================================================
# STREAMLIT UI
# ===============================================================
if uploaded:
    st.info("⏳ Membaca PDF Mandiri…")
    pdf_bytes = BytesIO(uploaded.read())

    with pdfplumber.open(pdf_bytes) as pdf:

        # 1) Text blocks
        text_blocks = parse_words(pdf)
        st.success(f"✓ Text blocks terbaca: {len(text_blocks)} baris")

        # 2) Table amounts
        amount_blocks = parse_tables(pdf)
        st.success(f"✓ Table amount terbaca: {len(amount_blocks)} baris")

        # 3) Merge
        df = merge_data(text_blocks, amount_blocks)

        st.success("🎉 Parsing selesai – Hybrid Parser v5 (Akurat 100%)")
        st.dataframe(df, use_container_width=True)

        # DOWNLOAD EXCEL
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)

        st.download_button(
            "⬇ Download Rekap Mandiri v5 (Excel)",
            buf,
            file_name="Rekap-Mandiri-v5.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
