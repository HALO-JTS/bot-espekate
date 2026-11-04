import os
import re
from datetime import datetime, date, timedelta, timezone
import requests
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("POSKO_EMAIL", "").strip()
PASSWORD = os.environ.get("POSKO_PASSWORD", "").strip()
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

DEFAULT_LINK = "https://drive.google.com/file/d/17KmVFmPU-OZk0dBdbVgF7AZ6ayhGWPyl/view?usp=drivesdk"

# Lokasi standar Mako Polsek Jatisrono
LOKASI_SPKT = "MAKO POLSEK JATISRONO, KEC. JATISRONO"
KOORDINAT_SPKT = "(-7.8273937, 111.1285440)"

# ==========================================================
# 1. KONFIGURASI 3 REGU PIKET SPKT & LINK FOLDER
# Patokan mulai: 28 Oktober 2026 = Regu 1 (AIPTU SUTARMAN)
# ==========================================================
TANGGAL_PATOKAN = date(2026, 10, 28)

DAFTAR_REGU_SPKT = [
    {
        "regu": 1,
        "nama": "AIPTU SUTARMAN",
        "folder_url": "https://drive.google.com/drive/folders/1aNKfkXJ7TBBQNvJNUcRcNshy_oLeT8jf"
    },
    {
        "regu": 2,
        "nama": "AIPTU DIDIK SUBAGYO",
        "folder_url": "https://drive.google.com/drive/folders/1HrneM25AB_t1YctvCWEiRq-ap2sKvL9j"
    },
    {
        "regu": 3,
        "nama": "AIPTU SUHANDOKO",
        "folder_url": "https://drive.google.com/drive/folders/11fsqOzZFotnDS5vkPf8rQR1f9qQ_ukA5"
    },
]

# 6 Kegiatan Harian Ka SPKT sesuai urutan di web Posko PBM
DAFTAR_KEGIATAN_SPKT = [
    {
        "kode": "QW3.2",
        "tab": "Bersih Judi Daring dan Penipuan Digital",
        "nama": "Layanan aduan korban penipuan daring"
    },
    {
        "kode": "QW4.1",
        "tab": "110 Respons Cepat, SPKT Ramah Korban",
        "nama": "Pamapta hadir dan penanganan ke TKP"
    },
    {
        "kode": "QW4.2",
        "tab": "110 Respons Cepat, SPKT Ramah Korban",
        "nama": "Petugas Yanmas menerima laporan dan aduan di SPKT"
    },
    {
        "kode": "QW4.3",
        "tab": "110 Respons Cepat, SPKT Ramah Korban",
        "nama": "Respons cepat panggilan 110"
    },
    {
        "kode": "QW4.4",
        "tab": "110 Respons Cepat, SPKT Ramah Korban",
        "nama": "Layanan ramah perempuan dan anak"
    },
    {
        "kode": "QW5.2",
        "tab": "Perkara Terlacak, SP2HP Pasti",
        "nama": "Layanan informasi perkara"
    },
]

def hitung_jadwal_regu_hari_ini():
    wib_sekarang = datetime.now(timezone(timedelta(hours=7))).date()
    selisih_hari = max(0, (wib_sekarang - TANGGAL_PATOKAN).days)
    indeks_regu = selisih_hari % len(DAFTAR_REGU_SPKT)
    putaran_piket_regu = selisih_hari // len(DAFTAR_REGU_SPKT)
    return DAFTAR_REGU_SPKT[indeks_regu], putaran_piket_regu

def kirim_notif_telegram(pesan, foto_path=None):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    daftar_chat_id = [cid.strip() for cid in TG_CHAT_ID.split(",") if cid.strip()]
    for cid in daftar_chat_id:
        try:
            if foto_path and os.path.exists(foto_path):
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
                with open(foto_path, "rb") as f:
                    requests.post(url, data={"chat_id": cid, "caption": pesan[:1000]}, files={"photo": f}, timeout=20)
            else:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                requests.post(url, data={"chat_id": cid, "text": pesan[:4000]}, timeout=20)
        except Exception as e:
            print(f"Gagal kirim ke Telegram ({cid}):", e)

def ambil_6_foto_harian_regu(page, folder_url, putaran_piket):
    jumlah_giat = len(DAFTAR_KEGIATAN_SPKT)
    kode_utama = folder_url.rstrip("/").split("/")[-1].split("?")[0]
    embed_url = f"https://drive.google.com/embeddedfolderview?id={kode_utama}#list"

    file_links = []
    seen = set()
    try:
        res = requests.get(embed_url, timeout=20)
        ids = re.findall(r"/file/d/([a-zA-Z0-9_-]{25,})/", res.text)
        if not ids:
            ids = re.findall(r'id="entry-([a-zA-Z0-9_-]{25,})"', res.text)

        for item_id in ids:
            if item_id != kode_utama and item_id not in seen:
                seen.add(item_id)
                file_links.append(f"https://drive.google.com/file/d/{item_id}/view?usp=drivesdk")

        if not file_links:
            page.goto(embed_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            html = page.content()
            ids2 = re.findall(r"/file/d/([a-zA-Z0-9_-]{25,})/", html)
            if not ids2:
                ids2 = re.findall(r'id="entry-([a-zA-Z0-9_-]{25,})"', html)
            for item_id in ids2:
                if item_id != kode_utama and item_id not in seen:
                    seen.add(item_id)
                    file_links.append(f"https://drive.google.com/file/d/{item_id}/view?usp=drivesdk")
    except Exception as e:
        print("Gagal memindai folder Google Drive:", e)

    if file_links:
        total_foto = len(file_links)
        base_idx = putaran_piket * jumlah_giat
        hasil_foto = []
        for i in range(jumlah_giat):
            idx_terpilih = (base_idx + i) % total_foto
            hasil_foto.append((file_links[idx_terpilih], idx_terpilih + 1, total_foto))
        return hasil_foto

    return [(DEFAULT_LINK, i + 1, 1) for i in range(jumlah_giat)]

def tutup_saran_jika_ada(page):
    """Menutup kotak Saran atau keluhan 1 (tombol ×) tanpa menutup kotak Jenis laporan 1 / Layanan 1."""
    try:
        tombol_x = page.locator("xpath=//*[contains(text(), 'Saran atau keluhan')]/following::button[normalize-space()='×'][1]")
        if tombol_x.count() > 0 and tombol_x.first.is_visible():
            tombol_x.first.scroll_into_view_if_needed()
            tombol_x.first.click()
            page.wait_for_timeout(500)
    except Exception:
        pass

def isi_lokasi_dan_koordinat(page):
    try:
        inp_tempat = page.locator("input[placeholder*='Nama tempat']")
        for i in range(inp_tempat.count()):
            if inp_tempat.nth(i).is_visible():
                inp_tempat.nth(i).scroll_into_view_if_needed()
                inp_tempat.nth(i).fill(LOKASI_SPKT)

        inp_koord = page.locator("input[placeholder*='Tempel koordinat']")
        for i in range(inp_koord.count()):
            if inp_koord.nth(i).is_visible():
                inp_koord.nth(i).scroll_into_view_if_needed()
                inp_koord.nth(i).fill(KOORDINAT_SPKT)
    except Exception:
        pass

def klik_jam_sekarang(page):
    try:
        btn_jam = page.get_by_role("button", name="Isi jam sekarang")
        for i in range(btn_jam.count()):
            if btn_jam.nth(i).is_visible():
                btn_jam.nth(i).scroll_into_view_if_needed()
                btn_jam.nth(i).click()
                page.wait_for_timeout(500)
    except Exception:
        pass

def pilih_dropdown_kedua_jika_ada(page):
    """Memilih opsi pertama pada dropdown di dalam form (seperti Jenis laporan atau Sumber data panggilan 110)."""
    try:
        selects = page.locator("select")
        for i in range(1, selects.count()):
            if selects.nth(i).is_visible():
                selects.nth(i).scroll_into_view_if_needed()
                selects.nth(i).select_option(index=1)
                page.wait_for_timeout(500)
    except Exception:
        pass

def isi_angka_kosong_dengan_nol(page):
    """Mengisi semua kotak angka yang masih kosong dengan '0' tanpa mengubah angka '1' pada Kegiatan judi daring."""
    try:
        num_inputs = page.locator("input[type='number']")
        for i in range(num_inputs.count()):
            el = num_inputs.nth(i)
            if el.is_visible():
                val = (el.input_value() or "").strip()
                if val == "":
                    el.scroll_into_view_if_needed()
                    el.fill("0")
    except Exception:
        pass

def klik_tombol_ya_atau_ada(page):
    """Mengklik tombol 'Ya' atau 'Ada' pada pertanyaan wajib di bagian c."""
    try:
        btn_ya = page.get_by_role("button", name="Ya", exact=True)
        if btn_ya.count() > 0 and btn_ya.first.is_visible():
            btn_ya.first.scroll_into_view_if_needed()
            btn_ya.first.click()
            page.wait_for_timeout(400)
            return

        btn_ada = page.get_by_role("button", name="Ada", exact=True)
        if btn_ada.count() > 0 and btn_ada.first.is_visible():
            btn_ada.first.scroll_into_view_if_needed()
            btn_ada.first.click()
            page.wait_for_timeout(400)
    except Exception:
        pass

def isi_link_foto_drive(page, link_foto):
    try:
        inputs_drive = page.locator("input[placeholder*='Google Drive'], input[placeholder*='drive.google.com']")
        for i in range(inputs_drive.count()):
            if inputs_drive.nth(i).is_visible():
                inputs_drive.nth(i).scroll_into_view_if_needed()
                inputs_drive.nth(i).fill(link_foto)
    except Exception:
        pass

def klik_tetap_kirim_jika_ada(page):
    try:
        btn_tetap = page.get_by_role("button", name="Tetap kirim")
        if btn_tetap.count() > 0 and btn_tetap.first.is_visible():
            btn_tetap.first.scroll_into_view_if_needed()
            btn_tetap.first.click()
            page.wait_for_timeout(3000)
    except Exception:
        pass

def jalankan_robot_spkt():
    data_regu, putaran_piket = hitung_jadwal_regu_hari_ini()
    nomor_regu = data_regu["regu"]
    nama_petugas = data_regu["nama"]
    folder_url = data_regu["folder_url"]

    kirim_notif_telegram(
        f"🤖 Robot SPKT Polsek Jatisrono mulai berjalan...\n"
        f"👮 Piket Hari Ini: Regu {nomor_regu} ({nama_petugas})\n"
        f"🔄 Putaran Piket ke-{putaran_piket + 1} (Mengambil 6 foto berurutan)"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            viewport={"width": 412, "height": 915},
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()

        try:
            enam_foto = ambil_6_foto_harian_regu(page, folder_url, putaran_piket)

            page.goto("https://poskopbm.polri.go.id/input", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # 1. Login jika diminta
            if page.locator("input[type='password']").count() > 0:
                page.locator("input[type='email'], input[type='text']").first.fill(EMAIL)
                page.locator("input[type='password']").first.fill(PASSWORD)
                page.get_by_role("button", name="Masuk").click()
                page.wait_for_timeout(5000)

            # 2. Isi Nama Pelapor & Pilih Jabatan Ka SPKT (6 kegiatan)
            page.get_by_label("Nama dan pangkat pelapor").fill(nama_petugas)
            select_jabatan = page.locator("select").first
            opsi_spkt = select_jabatan.locator("option", has_text="SPKT").first
            teks_jabatan = (opsi_spkt.text_content() or "").strip()
            select_jabatan.select_option(label=teks_jabatan)
            page.wait_for_timeout(2500)

            # 3. Eksekusi Berurutan 6 Kegiatan Ka SPKT
            for idx, item in enumerate(DAFTAR_KEGIATAN_SPKT):
                kode = item["kode"]
                nama_tab = item["tab"]
                nama_giat = item["nama"]
                link_foto, no_foto, tot_foto = enam_foto[idx]

                # Pastikan Nama Pelapor di atas tetap terisi
                inp_pelapor = page.get_by_label("Nama dan pangkat pelapor")
                if (inp_pelapor.input_value() or "").strip() == "":
                    inp_pelapor.fill(nama_petugas)

                # Buka tab Quick Wins jika sub-kegiatan belum tampil di layar
                if not page.get_by_text(kode).first.is_visible():
                    tab_el = page.locator("button", has_text=nama_tab).last
                    tab_el.scroll_into_view_if_needed()
                    tab_el.click()
                    page.wait_for_timeout(1500)

                # Klik sub-kegiatan berdasarkan kodenya (QW3.2, QW4.1, dst.)
                giat_el = page.get_by_text(kode).last
                giat_el.scroll_into_view_if_needed()
                giat_el.click()
                page.wait_for_timeout(2500)

                # Khusus QW3.2: Klik tombol '+' pada 'Kegiatan judi daring' agar kotak isian terbuka
                if kode == "QW3.2":
                    if page.get_by_text("KEGIATAN JUDI DARING 1").count() == 0:
                        btn_plus = page.locator("xpath=//*[contains(text(), 'Kegiatan judi daring')]/following::button[normalize-space()='+'][1]")
                        if btn_plus.count() > 0:
                            btn_plus.first.scroll_into_view_if_needed()
                            btn_plus.first.click()
                            page.wait_for_timeout(1500)

                # Khusus QW4.1, QW4.3, QW4.4, QW5.2: Klik tombol 'Ya' / 'Ada' pada pertanyaan poin c
                if kode in ["QW4.1", "QW4.3", "QW4.4", "QW5.2"]:
                    klik_tombol_ya_atau_ada(page)

                # Tutup kotak Saran atau keluhan 1 (×) terlebih dahulu
                tutup_saran_jika_ada(page)

                # Isi Lokasi Kegiatan & Titik Koordinat
                isi_lokasi_dan_koordinat(page)

                # Klik tombol 'Isi jam sekarang' (jika ada pada form tersebut)
                klik_jam_sekarang(page)

                # Pilih dropdown tambahan di dalam form (Jenis laporan di QW4.2 / Sumber data di QW4.3)
                pilih_dropdown_kedua_jika_ada(page)

                # Isi semua kotak angka yang masih kosong dengan "0"
                isi_angka_kosong_dengan_nol(page)

                # Isi Link Foto Google Drive
                isi_link_foto_drive(page, link_foto)

                # Klik Kirim laporan
                page.wait_for_timeout(1000)
                btn_kirim = page.get_by_role("button", name="Kirim laporan")
                btn_kirim.scroll_into_view_if_needed()
                btn_kirim.click()
                page.wait_for_timeout(2000)

                # Klik 'Tetap kirim' jika muncul konfirmasi laporan serupa
                klik_tetap_kirim_jika_ada(page)
                page.wait_for_timeout(4000)

                btn_kirim.scroll_into_view_if_needed()
                ss_path = f"bukti_{kode.replace('.', '_')}.png"
                page.screenshot(path=ss_path)
                kirim_notif_telegram(
                    f"✅ Laporan SPKT {kode} berhasil dikirim!\n\n"
                    f"📌 Kegiatan: {nama_giat}\n"
                    f"👮 Pelapor: {nama_petugas} (Regu {nomor_regu})\n"
                    f"📸 Foto ke-{no_foto} dari {tot_foto} (Folder Regu {nomor_regu})\n"
                    f"🔗 Link: {link_foto}",
                    ss_path
                )

        except Exception as e:
            err_ss = "error_spkt.png"
            try:
                page.screenshot(path=err_ss)
                kirim_notif_telegram(f"⚠️ Gagal mengirim laporan SPKT ({nama_petugas}):\n{str(e)}", err_ss)
            except Exception:
                kirim_notif_telegram(f"⚠️ Gagal membuka web SPKT ({nama_petugas}):\n{str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    jalankan_robot_spkt()
