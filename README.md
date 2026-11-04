<div align="center">
  <img src="assets/anime-girl.svg" alt="Anizium CLI için anime tarzı çizim" width="280">

  # Anizium CLI

  **Animeleri terminalden ara, izle ve indir.**

  [Kurulum](#kurulum) · [Kullanım](#kullanım) · [Tek dosyalı uygulama](#tek-dosyalı-uygulama)
</div>

---

Anizium CLI, animeleri terminalden aramanızı, bölümleri listelemenizi, video oynatmanızı ve indirmenizi sağlayan bir Python aracıdır. Etkileşimli menüde ok tuşlarıyla gezebilir, Enter ile seçim yapabilirsiniz.

## Özellikler

- Anime arama ve popüler animeleri listeleme
- Anime bilgilerini ve bölümlerini görüntüleme
- Son eklenen anime ve bölümleri görüntüleme
- Video kalitesini seçip mpv veya VLC ile izleme
- Mevcut altyazıyı indirip oynatıcıya ekleme
- Video indirme; HLS videolar için `ffmpeg` kullanma

## Kurulum ve işletim sistemlerinde çalıştırma

Python 3.10 veya üzeri gerekir. Proje dosyalarını indirin, ardından işletim sisteminize uygun terminali açıp proje klasörüne geçin.

### Windows

PowerShell veya Komut İstemi'nde proje klasörüne geçip çalıştırın:

```powershell
py -3 anizium.py
```

Python başlatıcısı (`py`) yoksa `python anizium.py` komutunu kullanın. Etkileşimli menü Windows Terminali ve PowerShell içinde ok tuşlarıyla kullanılabilir.

### Linux

Terminalde proje klasörüne geçip çalıştırın:

```bash
python3 anizium.py
```

İsterseniz betiği doğrudan çalıştırılabilir yapabilirsiniz:

```bash
chmod +x anizium.py
./anizium.py
```

### macOS

Terminal uygulamasında proje klasörüne geçip çalıştırın:

```bash
python3 anizium.py
```

Komut bulunamazsa Python 3.10 veya üzeri sürümü kurup Terminal'i yeniden açın.

### İsteğe bağlı oynatıcı ve indirme araçları

Video izlemek için işletim sisteminde **mpv** veya **VLC** kurulu olmalı ve terminalden çalıştırılabilmelidir. HLS (`.m3u8`) video indirmek için **ffmpeg** gerekir. Bunlar uygulamaya dahil değildir.

### Python paketleri

Anime arama, listeleme ve izleme özelliklerini Python'ın kendi standart kütüphanesiyle çalıştırır; günlük kullanım için `pip install` ile ek bir Python kütüphanesi indirmeniz gerekmez. `urllib` de Python ile birlikte gelir, ayrıca kurulmaz.

Yalnızca tek dosyalı uygulama oluşturacaksanız `requirements-build.txt` içindeki **PyInstaller** gerekir. Proje klasöründe sanal ortamı etkinleştirdikten sonra şu komutla kurabilirsiniz:

```bash
python -m pip install -r requirements-build.txt
```

Bu paket uygulamayı derlemek içindir; `mpv`, `VLC` ve `ffmpeg` gibi ayrı sistem programlarının yerini tutmaz.

## Kullanım

### Etkileşimli menü

Argümansız başlatıldığında ana menü açılır. Buradan **Anime izle**, **İndir** veya **Son eklenen animeler / bölümler** seçeneklerinden birini seçin. Anime adını yazıp listeden animeyi ve bölümü seçin; izleme veya indirme için ekrandaki adımları izleyin.

Masaüstü oynatıcısı kapatıldığında bölüm menüsüne dönersiniz. İsterseniz başka bir bölüm seçebilir veya sıradaki bölüme geçebilirsiniz.

### Komut satırı

```bash
python3 anizium.py search "jujutsu kaisen"  # Anime ara
python3 anizium.py search                    # Popüler animeleri listele
python3 anizium.py info 12345                # Anime bilgilerini göster
python3 anizium.py episodes 12345            # Bölümleri listele
python3 anizium.py streams 'https://anizium.co/watch/12345?season=1&episode=2'
python3 anizium.py watch 'https://anizium.co/watch/12345?season=1&episode=2'
```

`streams` bölümün video ve altyazı bağlantılarını listeler. `watch` video kaynağını seçmenizi ve oynatmanızı sağlar. İsterseniz oynatıcıyı ve altyazı klasörünü belirtebilirsiniz:

```bash
python3 anizium.py watch 'https://anizium.co/watch/12345?season=1&episode=2' --player mpv
python3 anizium.py watch 'https://anizium.co/watch/12345?season=1&episode=2' --player vlc --subtitle-dir ~/Videos/altyazilar
```

Komutların kısa Türkçe adları da kullanılabilir: `ara`, `bilgi`, `bolumler`, `link`, `izle`.

## Tek dosyalı uygulama

PyInstaller ile uygulamayı tek dosya halinde oluşturabilirsiniz. Her işletim sistemi için derlemeyi o işletim sisteminde yapın.

**Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
pyinstaller --clean --noconfirm anizium.spec
```

Uygulama `dist/anizium` konumunda oluşturulur.

**Windows PowerShell:**

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
pyinstaller --clean --noconfirm anizium.spec
```

Uygulama `dist\anizium.exe` konumunda oluşturulur. Çalışırken konsol penceresi açık kalmalıdır.

**macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
pyinstaller --clean --noconfirm anizium.spec
```

Uygulama `dist/anizium` konumunda oluşturulur. Betik veya uygulama çalışırken Terminal penceresi açık olmalıdır.
