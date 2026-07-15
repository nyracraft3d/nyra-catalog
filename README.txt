NYRA CRAFT KATALOG V3

1. ZIP'i çıkar.
2. Terminalde:
   python build_catalog.py
3. Program sorunca ana output klasörünün yolunu yapıştır.
4. Katalog oluşturulunca:
   python -m http.server 8000 -d site
5. Tarayıcı:
   http://localhost:8000

V3 KURALI
İçinde doğrudan JPG, PNG, WEBP vb. görsel bulunan her klasör figür kabul edilir.
Klasör derinliği sınırsızdır.

Oluşturulan raporlar:
- envanter.csv: Kataloğa giren bütün figürleri listeler.
- tarama_raporu.txt: Toplam klasör, figür ve görsel sayısını gösterir.
