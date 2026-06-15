# 💳 Dokumentasi Integrasi API KlikQRIS (Payment Gateway)

Proyek ini telah terintegrasi dengan **KlikQRIS** sebagai payment gateway otomatis 24 jam untuk menghasilkan barcode QRIS dinamis secara real-time.

---

## ⚙️ Logika Alur Pembayaran
1. Pengguna memilih paket di Mini App (Next.js) dan menekan tombol pemesanan.
2. Bot memicu helper di [src/payments.py](file:///d:/Bot%20Jaseb/src/payments.py) untuk membuat transaksi baru melalui API KlikQRIS.
3. KlikQRIS mengembalikan tautan QRIS dinamis beserta masa kedaluwarsanya.
4. Bot mengirimkan barcode QRIS langsung ke chat Telegram pengguna bersama tombol **"🔄 Cek Status Bayar"**.
5. Sistem memeriksa status transaksi secara berkala atau manual saat tombol ditekan untuk mengaktifkan paket pengguna secara otomatis.

---

## 🛠️ Referensi Endpoint API KlikQRIS

### 1. Membuat Transaksi Baru (Create QRIS Transaction)
Digunakan untuk menghasilkan gambar QRIS pembayaran dinamis.

* **HTTP Method:** `POST`
* **Endpoint:** `https://api.klikqris.com/v1/transaction/create`
* **Headers:**
  ```http
  Content-Type: application/json
  Authorization: Bearer YOUR_API_KEY
  ```
* **Request Body (JSON):**
  ```json
  {
    "amount": 25000,
    "description": "Jaseb Regular 30 LPM - 30 Hari",
    "reference_id": "TRX-UNIQUE-ID-12345",
    "callback_url": "https://geunid-bot.koyeb.app/api/callback/klikqris"
  }
  ```
* **Response Body (JSON Sukses):**
  ```json
  {
    "success": true,
    "data": {
      "transaction_id": "KQ-9948483",
      "reference_id": "TRX-UNIQUE-ID-12345",
      "total_amount": 25000,
      "qris_url": "https://api.klikqris.com/qris/render/KQ-9948483.png",
      "payment_url": "https://checkout.klikqris.com/pay/KQ-9948483",
      "expired_at": "2026-06-15 13:55:00",
      "status": "pending"
    }
  }
  ```

---

### 2. Memeriksa Status Transaksi (Check Status)
Digunakan untuk mengecek apakah pengguna sudah melakukan pembayaran ke QRIS tersebut.

* **HTTP Method:** `GET`
* **Endpoint:** `https://api.klikqris.com/v1/transaction/status/{transaction_id}`
* **Headers:**
  ```http
  Authorization: Bearer YOUR_API_KEY
  ```
* **Response Body (JSON Sukses Terbayar):**
  ```json
  {
    "success": true,
    "data": {
      "transaction_id": "KQ-9948483",
      "status": "success",
      "paid_at": "2026-06-15 12:45:10",
      "amount": 25000
    }
  }
  ```

---

## 🔒 Callback / Webhook Configuration
KlikQRIS akan mengirimkan notifikasi asinkron (callback) dalam format JSON ke server bot Anda segera setelah pembeli melakukan pembayaran. 
Pastikan server bot Anda mengekspos endpoint callback dan memproses datanya untuk langsung mengaktifkan masa tenggang langganan pengguna di database `subscriptions`.
