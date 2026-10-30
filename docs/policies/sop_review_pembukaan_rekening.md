# SOP Review Fraud Pembukaan Rekening · Bank Nusa Digital

> **Dokumen fiktif** untuk proyek portofolio SIGAP. Bank Nusa Digital tidak ada. Isi SOP ini disusun dari
> praktik umum dan prinsip POJK 12/2024 tentang Penerapan Strategi Anti Fraud, bukan dari dokumen internal bank
> mana pun. Versi 1.0, 29 Oktober 2026. Pemilik: Kepala Fraud Operations.

## Ruang lingkup

SOP ini berlaku untuk setiap pengajuan pembukaan rekening digital yang diberi keputusan **review** oleh sistem
SIGAP. Pengajuan dengan keputusan **approve** diproses otomatis. Pengajuan dengan keputusan **decline** ditolak
otomatis dan hanya ditinjau ulang lewat keluhan nasabah. Tujuan review adalah memastikan rekening tidak dibuka
untuk pelaku fraud atau rekening penampung (mule account), tanpa menolak nasabah yang sah tanpa alasan.

## Antrean dan prioritas

Kasus review dibagikan setiap hari kerja pukul 08.30 WIB, diurutkan dari skor risiko tertinggi. Kapasitas tim
adalah 10 analis dengan target 30 kasus per analis per hari. Kasus yang melebihi kapasitas masuk backlog dan
dikerjakan lebih dulu pada hari kerja berikutnya. Jika antrean melebihi kapasitas lebih dari 10 persen selama 3
hari kerja berturut-turut, Lead Fraud Operations wajib meminta tambahan analis atau mengusulkan penyesuaian band
review kepada tim Data Science.

## Pemeriksaan yang wajib dilakukan analis

Untuk setiap kasus, analis memeriksa paling sedikit hal berikut dan mencatat hasilnya di formulir keputusan:

1. **Alasan skor.** Baca tiga reason code dari SIGAP. Reason code menunjukkan sinyal yang paling mendorong skor,
   bukan bukti fraud.
2. **Kecocokan identitas.** Bandingkan nama pada e-KTP dengan nama di alamat email dan data Dukcapil. Email yang
   tidak mengandung unsur nama pemohon adalah sinyal, bukan alasan penolakan.
3. **Perangkat dan sesi.** Periksa apakah perangkat yang sama dipakai untuk banyak email dalam 8 minggu terakhir
   dan apakah sesi pengajuan sangat singkat atau sangat panjang.
4. **Kecepatan pengajuan.** Lonjakan pengajuan dari wilayah atau perangkat yang sama dalam 6 jam terakhir
   dibandingkan rata-rata 4 minggu.
5. **Verifikasi langsung.** Jika dua atau lebih sinyal di atas muncul, lakukan panggilan balik atau video call ke
   nomor yang terverifikasi. Analis tidak boleh meminta OTP, PIN, atau kata sandi nasabah.

## Keputusan dan SLA

Analis memilih satu dari tiga keputusan: **legit** (rekening dibuka), **confirmed_fraud** (pengajuan ditolak dan
data perangkat masuk daftar pantau), atau **need_info** (nasabah diminta melengkapi dokumen). Status need_info
hanya boleh dipakai satu kali per kasus.

SLA penyelesaian: kasus review diputuskan paling lambat **1 hari kerja** sejak dibagikan. Kasus need_info diberi
waktu **3 hari kerja** bagi nasabah untuk merespons; jika tidak ada respons, kasus ditutup sebagai pengajuan
tidak lengkap. Setiap keputusan dicatat dengan identitas analis dan waktu, dan tidak dapat diubah setelah kasus
ditutup.

## Eskalasi ke tim investigasi

Kasus wajib dieskalasi ke Tim Investigasi Fraud pada hari yang sama jika salah satu kondisi berikut terpenuhi:

- terdapat indikasi sindikat: perangkat atau email yang sama muncul pada **3 atau lebih** pengajuan dalam 7 hari;
- dokumen identitas terindikasi palsu atau hasil manipulasi;
- nasabah atau pihak lain mencoba memengaruhi analis (menawarkan imbalan, menekan, atau mengaku sebagai pegawai);
- rekening terkait muncul dalam laporan Indonesia Anti-Scam Centre.

Tim Investigasi menindaklanjuti sesuai pilar investigasi, pelaporan, dan sanksi dalam strategi anti-fraud bank,
termasuk pelaporan kepada OJK bila memenuhi kriteria pelaporan fraud.

## Penggunaan copilot SIGAP

Copilot SIGAP adalah alat bantu baca. Copilot boleh merangkum data aplikasi, membandingkan dengan kasus serupa,
menampilkan status monitoring, dan mengutip kebijakan. Copilot **tidak boleh** menyetujui, menolak, atau mengubah
keputusan, dan jawabannya bukan dasar tunggal keputusan. Analis tidak boleh menempelkan NIK, nomor telepon, atau
email nasabah ke copilot; sistem tetap menyamarkan data tersebut sebelum dikirim ke model. Setiap angka dari
copilot harus dapat ditelusuri ke output tool.

## Pemantauan dan evaluasi SOP

Lead Fraud Operations meninjau SOP ini setiap 6 bulan atau setelah perubahan model besar, menggunakan metrik:
waktu penyelesaian kasus, persentase kasus need_info, tingkat fraud yang lolos dari review (setelah label
datang), dan keluhan nasabah sah yang ditolak.
