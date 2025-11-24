import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Rekening Mandiri", layout="wide")
st.title("📄 Extractor Rekening Koran Mandiri")

uploaded = st.file_uploader("Upload PDF Rekening Mandiri", type=["pdf"])

def extract_numbers(line):
    nums = re.findall(r"\d[\d.,]*", line)
    clean = [n.replace(".", "").replace(",", ".") for n in nums]
    return [float(x) for x in clean]

def parse_mandiri(pdf_bytes):
    rows = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.splitlines()

            buffer_ket = []
            tanggal = jam = ref = None

            for line in lines:
                # Deteksi tanggal
                m = re.match(r"(\d{2} \w{3} \d{4}),\s*(\d{2}:\d{2}:\d{2})", line)
                if m:
                    # Simpan transaksi lama
                    if buffer_ket and tanggal:
                        ket = " ".join(buffer_ket)
                        nums = extract_numbers(line_prev)
                        if len(nums) >= 3:
                            debit, credit, saldo = nums[-3], nums[-2], nums[-1]
                        else:
                            debit = credit = saldo = None

                        rows.append([tanggal, jam, ket, ref, debit, credit, saldo])

                    # Reset nilai baru
                    tanggal = m.group(1)
                    jam = m.group(2)
                    buffer_ket = []
                    ref = ""
                    continue

                # Deteksi reference (biasanya kode 15–20 digit)
                if re.search(r"\d{10,}", line):
                    ref = line.strip()

                # Deteksi akhir transaksi (mengandung 3 angka)
                nums = extract_numbers(line)
                if len(nums) >= 3:
                    line_prev = line  # Pegang untuk debit/kredit/saldo
                else:
                    # Masukkan ke remark
                    buffer_ket.append(line.strip())

    # Tambahkan transaksi terakhir
    if buffer_ket and tanggal:
        ket = " ".join(buffer_ket)
        nums = extract_numbers(line_prev)
        if len(nums) >= 3:
            debit, credit, saldo = nums[-3], nums[-2], nums[-1]
        else:
            debit = credit = saldo = None

        rows.append([tanggal, jam, ket, ref, debit, credit, saldo])

    df = pd.DataFrame(rows, columns=[
        "Tanggal", "Waktu", "Keterangan", "Reference",
        "Debit", "Kredit", "Saldo"
    ])

    return df


if uploaded:
    st.info("Membaca PDF...")
    
    pdf_bytes = BytesIO(uploaded.read())
    try:
        df = parse_mandiri(pdf_bytes)
        st.success("Berhasil membaca data!")
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Error parsing: {e}")
