# Mesflit Archive

GitHub Releases tabanlı otomatik arşiv sitesi.

**Site:** https://mesflit.github.io/archive/

## Kurulum

1. GitHub'da `mesflit/archive` adında public bir repository oluştur.
2. Bu paketin içindeki dosyaları repository'nin kök dizinine yükle ve `main` branch'ine push et.
3. Repository → **Settings → Pages** bölümüne gir.
4. **Build and deployment → Source** ayarını **GitHub Actions** yap.
5. **Actions** sekmesinden `Build and Deploy Archive` workflow'unu bir kez `Run workflow` ile çalıştır.
6. Workflow tamamlandığında site `https://mesflit.github.io/archive/` adresinde yayınlanır.

## Yeni arşiv ekleme

1. Repository'de **Releases → Draft a new release** seç.
2. Bir tag oluştur (ör. `v1.0.0`).
3. Release title ve açıklamasını yaz.
4. İstediğin arşiv dosyalarını **Attach binaries** alanına ekle.
5. İstersen `icon.png` isimli bir görsel de ekle.
6. **Publish release** düğmesine bas.

Release yayınlanınca GitHub Actions otomatik çalışır.

## Davranış

- Her yayınlanmış Release için `site/releases/<tag>/index.html` sayfası oluşturulur.
- Release sayfası zaten varsa **üzerine yazılmaz**.
- Ana sayfa her çalışmada yeniden oluşturulur; arama ve arşiv listesi güncel kalır.
- Release ekleri indirme bağlantıları olarak listelenir.
- `icon.png` dosyası varsa arşiv kartında ve detay sayfasında kullanılır.
- `icon.png` ayrıca indirilebilir dosyalar arasında da görünür.
- `workflow_dispatch` ile Actions sekmesinden elle yeniden çalıştırılabilir.

## Notlar

- Release sayfalarının oluşturulmuş halleri `site/` altında Git deposuna commit edilir. Böylece sonraki Actions çalıştırmalarında eski sayfalar korunur.
- Var olan sayfanın içeriğini değiştirmek istersen ilgili `site/releases/<tag>/index.html` dosyasını elle düzenleyebilirsin. Otomasyon o dosyanın üzerine yazmaz.
- Bir Release'i GitHub'dan silmek, daha önce oluşturulmuş statik sayfayı otomatik silmez.
- GitHub Pages için repository'nin public olması en kolay seçenektir.
