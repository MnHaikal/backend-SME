from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Legal"])

@router.get("/privacy-policy", response_class=HTMLResponse)
async def get_privacy_policy():
    html_content = """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Privacy Policy - Smart SME</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9fafb;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }
            h1 {
                color: #1f2937;
                border-bottom: 2px solid #e5e7eb;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }
            h2 {
                color: #4b5563;
                margin-top: 30px;
            }
            p {
                margin-bottom: 15px;
                color: #6b7280;
            }
            ul {
                color: #6b7280;
                margin-bottom: 15px;
            }
            .footer {
                margin-top: 40px;
                text-align: center;
                font-size: 0.9em;
                color: #9ca3af;
                border-top: 1px solid #e5e7eb;
                padding-top: 20px;
            }
            .highlight {
                color: #4f46e5;
                font-weight: 600;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Kebijakan Privasi (Privacy Policy)</h1>
            <p>Berlaku efektif sejak: <strong>1 Januari 2024</strong></p>

            <p>Selamat datang di <span class="highlight">Smart SME</span>. Kami sangat menghargai privasi Anda dan berkomitmen untuk melindungi informasi pribadi Anda. Kebijakan Privasi ini menjelaskan bagaimana kami mengumpulkan, menggunakan, dan menjaga data Anda saat menggunakan aplikasi kami.</p>

            <h2>1. Informasi yang Kami Kumpulkan</h2>
            <p>Kami dapat mengumpulkan informasi pribadi berikut saat Anda menggunakan layanan kami:</p>
            <ul>
                <li><strong>Informasi Profil:</strong> Nama, alamat email, dan foto profil (jika Anda memilih untuk mengunggahnya).</li>
                <li><strong>Data Inventaris:</strong> Data produk, stok, dan riwayat transaksi (Scan In / Scan Out) yang Anda masukkan.</li>
                <li><strong>Data Biometrik (Opsional):</strong> Jika Anda mengaktifkan Face ID atau verifikasi biometrik lainnya, data tersebut dikelola secara aman dan tidak pernah disebarluaskan.</li>
            </ul>

            <h2>2. Bagaimana Kami Menggunakan Informasi Anda</h2>
            <p>Informasi yang kami kumpulkan digunakan untuk tujuan berikut:</p>
            <ul>
                <li>Menyediakan, mengoperasikan, dan memelihara fitur-fitur aplikasi Smart SME.</li>
                <li>Meningkatkan pengalaman pengguna dengan analitik dan AI (seperti Potensial Profit dan Analisis Tren).</li>
                <li>Mengamankan akun Anda dan mendeteksi aktivitas yang mencurigakan (melalui Activity Log).</li>
            </ul>

            <h2>3. Keamanan Data</h2>
            <p>Keamanan data Anda adalah prioritas kami. Semua permintaan data dari aplikasi dilindungi menggunakan token enkripsi (JWT). Aktivitas log Anda juga dibatasi hanya dapat dilihat dan dihapus oleh akun Anda sendiri.</p>

            <h2>4. Berbagi Informasi Pihak Ketiga</h2>
            <p>Kami <strong>tidak pernah menjual</strong>, menyewakan, atau menukar informasi pribadi Anda kepada pihak ketiga. Data Anda disimpan secara terenkripsi menggunakan infrastruktur awan yang aman (misalnya Supabase dan Railway).</p>

            <h2>5. Penghapusan Data (Data Retention & Deletion)</h2>
            <p>Anda memiliki hak penuh atas data Anda. Anda dapat menghapus Riwayat Aktivitas (Activity Log) secara mandiri dari dalam aplikasi. Jika Anda ingin menghapus akun beserta seluruh data inventaris Anda secara permanen, silakan hubungi tim dukungan kami.</p>

            <h2>6. Hubungi Kami</h2>
            <p>Jika Anda memiliki pertanyaan lebih lanjut mengenai Kebijakan Privasi ini, silakan hubungi kami di <strong>support@smartsme.app</strong>.</p>

            <div class="footer">
                &copy; 2024 Smart SME. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
