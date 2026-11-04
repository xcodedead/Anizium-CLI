#!/usr/bin/env python3
"""Terminal client for the Anizium anime API."""

from __future__ import annotations

import argparse
import builtins
import json
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_HOST = os.environ.get("ANIZIUM_API_HOST", "https://api.anizium.co").rstrip("/")
# Override this value with ANIZIUM_TOKEN_KEY if the API rotates its signature key.
TOKEN_KEY = os.environ.get("ANIZIUM_TOKEN_KEY", "hlxjl1c2w281ax473rt1ofgrvhyjvi")
DAY_NAMES = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
NEON_RED = "\033[1;38;2;255;35;70m"
RESET_COLOR = "\033[0m"


def neon(text: str, stream=None) -> str:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") is not None or not getattr(stream, "isatty", lambda: False)():
        return text
    return NEON_RED + text + RESET_COLOR


def print(*args, sep=" ", end="\n", file=None, flush=False):
    """Print CLI-owned text in neon red when the output is an interactive terminal."""
    stream = file or sys.stdout
    message = sep.join(str(arg) for arg in args)
    builtins.print(neon(message, stream), end=end, file=file, flush=flush)


def make_token() -> str:
    baku_now = datetime.now(timezone.utc) + timedelta(hours=3)
    key = f"{TOKEN_KEY}_{DAY_NAMES[(baku_now.weekday() + 1) % 7]}"
    rnd = "".join(random.choice("0123456789abcdefghijklmnopqrstuvwxyz") for _ in range(6))
    payload = json.dumps({str(i): c for i, c in enumerate(rnd)}, separators=(",", ":"))
    return bytes(ord(ch) ^ ord(key[i % len(key)]) for i, ch in enumerate(payload)).hex()


def api_get(path: str) -> dict:
    req = urllib.request.Request(
        API_HOST + path,
        headers={
            "Accept": "application/json",
            "Cf-Control": make_token(),
            "User-Agent": "Mozilla/5.0 AniziumCLI/1.0",
            "device": "browser",
            "language": "tr",
            "site": "main",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"API HTTP {exc.code}: {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"API bağlantı/yanıt hatası: {exc}") from exc


def parse_id(value: str) -> str:
    match = re.search(r"/(?:anime|watch)/(\d+)", value or "")
    return match.group(1) if match else (value or "").strip("/")


def anime_data(value: str) -> dict:
    anime_id = parse_id(value)
    if not anime_id:
        raise RuntimeError("Anime ID veya URL gerekli.")
    result = api_get("/anime/get?" + urllib.parse.urlencode({"id": anime_id}))
    if not result.get("success") or not result.get("data"):
        raise RuntimeError("Anime bulunamadı.")
    return result["data"]


def search(query: str, limit: int = 20) -> list[dict]:
    if not query.strip():
        urls = [f"/page/top?platform=favorite&page={page}" for page in (1, 2, 3)]
    else:
        urls = ["/page/search?" + urllib.parse.urlencode({"value": query.strip(), "page": page}) for page in (1, 2)]
    found, seen = [], set()
    for path in urls:
        try:
            data = api_get(path)
        except RuntimeError:
            continue
        items = data.get("page", {}).get("data", []) if query.strip() else data.get("page", {}).get("data", [])
        for item in items or []:
            if not item:
                continue
            anime_id = item.get("ID") or item.get("id")
            if not anime_id or anime_id in seen:
                continue
            seen.add(anime_id)
            found.append({
                "id": anime_id,
                "title": item.get("name") or str(anime_id),
                "image": item.get("poster") or item.get("banner") or "",
                "url": f"https://anizium.co/anime/{anime_id}",
            })
            if len(found) >= limit:
                return found
    return found


def episodes(value: str) -> list[dict]:
    anime_id = parse_id(value)
    anime = anime_data(anime_id)
    result = []
    for index, season in enumerate(anime.get("seasons") or [], 1):
        season_no = season.get("number") or index
        for ep_index, episode in enumerate(season.get("episodes") or [], 1):
            ep_no = episode.get("number") or ep_index
            display_no = (season_no - 1) * 1000 + ep_no if season_no > 1 else ep_no
            result.append({"season": season_no, "episode": ep_no, "number": display_no,
                           "url": f"https://anizium.co/watch/{anime_id}?season={season_no}&episode={ep_no}"})
    if not result:
        result.append({"season": 1, "episode": 1, "number": 1, "url": f"https://anizium.co/watch/{anime_id}"})
    return result


def sources(value: str) -> dict:
    anime_id = parse_id(value)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(value).query)
    path = "/anime/source?" + urllib.parse.urlencode({"id": anime_id, "site": "main", "plan": "", "server": 1})
    season, episode = query.get("season", [None])[0], query.get("episode", [None])[0]
    if season and episode:
        path += "&" + urllib.parse.urlencode({"season": season, "episode": episode})
    data = api_get(path)
    streams = []
    for group in data.get("groups", []) or []:
        for item in group.get("items", []) or []:
            if item.get("link"):
                quality = f"{item['quality']}p" if item.get("quality") else "Video"
                streams.append({"title": f"{group.get('name')} - {quality}" if group.get("name") else quality,
                                "url": item["link"]})
    subtitles = data.get("subtitles", []) or []
    subtitle = next((s["link"] for s in subtitles if s.get("link") and s.get("group") == "tr"), "")
    if not subtitle:
        subtitle = next((s["link"] for s in subtitles if s.get("link")), "")
    return {"streams": streams, "subtitle": subtitle}


def save_subtitle(url: str, directory: str, filename: str = "anizium-subtitle") -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext not in (".srt", ".vtt", ".ass", ".ssa", ".sub"):
        ext = ".srt"
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, safe_filename(filename) + ext)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AniziumCLI/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response, open(path, "wb") as output:
            shutil.copyfileobj(response, output)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Altyazı indirilemedi: {exc}") from exc
    return path


def watch(value: str, player: str = "auto", subtitle_dir: str = ".") -> None:
    data = sources(value)
    streams = data["streams"]
    if not streams:
        raise RuntimeError("Bu bölüm için video kaynağı bulunamadı.")
    print("Video kaynakları:")
    for index, stream in enumerate(streams, 1):
        print(f"  {index}. {stream['title']} — {stream['url']}")
    while True:
        choice = input(f"Kaynak seç (1-{len(streams)}): ").strip()
        try:
            stream = streams[int(choice) - 1]
            break
        except (ValueError, IndexError):
            print("Geçerli bir numara girin.")

    try:
        subtitle_path = save_subtitle(data["subtitle"], subtitle_dir)
    except RuntimeError as exc:
        subtitle_path = ""
        print(str(exc), file=sys.stderr)
    if subtitle_path:
        print(f"Altyazı kaydedildi: {os.path.abspath(subtitle_path)}")
    elif data["subtitle"]:
        print("Altyazı bağlantısı var, ancak indirme başarısız oldu.", file=sys.stderr)

    players = [player] if player != "auto" else ["mpv", "vlc"]
    selected = next((name for name in players if shutil.which(name)), None)
    if selected == "mpv":
        # These are direct media URLs; bypass mpv's yt-dlp hook and let FFmpeg
        # request them with the same page referrer used by the site.
        command = [shutil.which("mpv"), "--ytdl=no", "--referrer=" + value,
                   "--user-agent=Mozilla/5.0", "--http-header-fields=Origin: https://anizium.co", stream["url"]]
        if subtitle_path:
            command.append("--sub-file=" + os.path.abspath(subtitle_path))
    elif selected == "vlc":
        command = [shutil.which("vlc"), "--http-referrer=" + value,
                   "--http-user-agent=Mozilla/5.0", stream["url"]]
        if subtitle_path:
            command.append("--sub-file=" + os.path.abspath(subtitle_path))
    else:
        raise RuntimeError("mpv veya VLC bulunamadı. Birini kurun ya da --player ile seçin.")
    print(f"{stream['title']} oynatıcıda açılıyor…")
    try:
        subprocess.run(command, check=False)
    except OSError as exc:
        raise RuntimeError(f"Oynatıcı başlatılamadı: {exc}") from exc
    finally:
        if subtitle_path.lower().endswith(".vtt"):
            try:
                os.remove(subtitle_path)
            except FileNotFoundError:
                pass


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def read_key() -> str:
    if os.name == "nt":
        import msvcrt
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            return {"H": "up", "P": "down"}.get(msvcrt.getwch(), "")
        return {"\r": "enter", "\x1b": "escape"}.get(key, key)
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        key = sys.stdin.read(1)
        if key == "\x1b":
            tail = sys.stdin.read(2)
            return {"[A": "up", "[B": "down"}.get(tail, "escape")
        return {"\r": "enter", "\n": "enter", "\x03": "escape"}.get(key, key)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def menu(title: str, choices: list[str]) -> int:
    selected = 0
    while True:
        print("\033[2J\033[H" + title + "\n" + "↑/↓ gezin  Enter seç  Esc geri\n", end="")
        for index, choice in enumerate(choices):
            print(("❯ " if index == selected else "  ") + choice)
        key = read_key()
        if key == "up":
            selected = (selected - 1) % len(choices)
        elif key == "down":
            selected = (selected + 1) % len(choices)
        elif key == "enter":
            return selected
        elif key == "escape":
            return -1


def wait_key() -> None:
    print("\nDevam etmek için Enter basın.", end="", flush=True)
    input()


def latest_added_episodes(minimum: int = 30) -> list[dict]:
    rows, seen, page_number = [], set(), 1
    while len(rows) < minimum:
        result = api_get("/page/last-added-episodes?" + urllib.parse.urlencode({"page": page_number}))
        page = result.get("page") or {}
        for item in page.get("data") or []:
            if not item:
                continue
            key = (item.get("ID"), item.get("season"), item.get("episode"))
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
        next_page = page.get("next_page")
        if not next_page:
            break
        page_number = next_page
    return rows


def play_added_episode(row: dict) -> None:
    anime_id = str(row.get("ID") or "")
    season = row.get("season") or 1
    episode = row.get("episode") or 1
    if not anime_id:
        raise RuntimeError("Anime ID bulunamadı.")
    episode_url = f"https://anizium.co/watch/{anime_id}?season={season}&episode={episode}"
    data = sources(episode_url)
    if not data["streams"]:
        raise RuntimeError("Bu bölüm için video kaynağı bulunamadı.")
    source_index = menu("Video kalitesini seçin:", [s["title"] for s in data["streams"]] + ["Geri"])
    if source_index < 0 or source_index == len(data["streams"]):
        return
    stream = data["streams"][source_index]
    subtitle_path = ""
    if data["subtitle"]:
        subtitle_name = f"{row.get('name')}-s{season}-b{episode}-altyazi"
        try:
            subtitle_path = save_subtitle(data["subtitle"], ".", subtitle_name)
            print(f"Altyazı dosyası kaydedildi: {os.path.abspath(subtitle_path)}")
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
    players = [name for name in ("mpv", "vlc") if shutil.which(name)]
    if not players:
        raise RuntimeError("İzlemek için sisteme mpv veya VLC kurun.")
    player_index = menu("Oynatıcı seçin:", players)
    if player_index < 0:
        return
    player = players[player_index]
    if player == "mpv":
        command = [shutil.which("mpv"), "--ytdl=no", "--referrer=" + episode_url,
                   "--user-agent=Mozilla/5.0", "--http-header-fields=Origin: https://anizium.co",
                   stream["url"]]
        if subtitle_path:
            command.append("--sub-file=" + os.path.abspath(subtitle_path))
    else:
        command = [shutil.which("vlc"), "--http-referrer=" + episode_url,
                   "--http-user-agent=Mozilla/5.0", stream["url"]]
        if subtitle_path:
            command.append("--sub-file=" + os.path.abspath(subtitle_path))
    print("Video açılıyor; kapatınca son eklenenler listesine dönülecek.")
    subprocess.run(command, check=False)


def browse_latest_added() -> None:
    rows = latest_added_episodes(30)
    if not rows:
        print("Son eklenen anime/bölüm listesi boş.")
        wait_key()
        return
    if len(rows) < 30:
        print(f"API şu anda {len(rows)} son eklenen kayıt döndürdü.")
        wait_key()
    page_size = 8
    page_index = 0
    while True:
        start = page_index * page_size
        visible = rows[start:start + page_size]
        choices = [f"{row.get('name') or row.get('ID')} — S{row.get('season', 1)} B{row.get('episode', '?')}" for row in visible]
        previous_index = None
        next_index = None
        if page_index > 0:
            previous_index = len(choices)
            choices.append("Önceki sayfa")
        if start + page_size < len(rows):
            next_index = len(choices)
            choices.append("Sonraki sayfa")
        back_index = len(choices)
        choices.append("Geri")
        selected = menu(f"Son eklenen animeler ve bölümler ({page_index + 1}/{(len(rows) + page_size - 1) // page_size})", choices)
        if selected < 0 or selected == back_index:
            return
        if selected == previous_index:
            page_index -= 1
            continue
        if selected == next_index:
            page_index += 1
            continue
        row = visible[selected]
        added = row.get("created")
        if added:
            added_text = datetime.fromtimestamp(added / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        else:
            added_text = "Tarih bilgisi yok"
        anime_name = row.get("name") or row.get("ID")
        detail_title = (f"{anime_name} — Sezon {row.get('season', 1)}, "
                        f"Bölüm {row.get('episode', '?')} — {added_text}")
        while True:
            detail_choice = menu(detail_title, ["Bu bölümü izle", "Bölüm bilgisini göster", "Geri"])
            if detail_choice < 0 or detail_choice == 2:
                break
            if detail_choice == 0:
                try:
                    play_added_episode(row)
                except (RuntimeError, KeyError, ValueError, subprocess.SubprocessError) as exc:
                    print(f"Hata: {exc}", file=sys.stderr)
                    wait_key()
            else:
                print(f"\nAnime: {anime_name}")
                print(f"Eklenen bölüm: Sezon {row.get('season', 1)}, Bölüm {row.get('episode', '?')}")
                print(f"Eklenme zamanı: {added_text}")
                if row.get("overview"):
                    print(f"\n{row['overview']}")
                wait_key()


def safe_filename(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value).strip(" .")
    return value[:150] or "anizium-video"


def download_video(url: str, filename: str, referer: str = "https://anizium.co/") -> None:
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    if ".m3u8" in urllib.parse.urlparse(url).path.lower():
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("Bu video HLS yayınıdır. İndirmek için ffmpeg kurup PATH'e ekleyin.")
        subprocess.run([ffmpeg, "-y", "-user_agent", "Mozilla/5.0", "-referer", referer,
                        "-headers", "Origin: https://anizium.co\r\n",
                        "-i", url, "-c", "copy", filename], check=True)
        return
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": referer,
        "Origin": "https://anizium.co",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response, open(filename, "wb") as output:
            total = int(response.headers.get("Content-Length", 0))
            done = 0
            while True:
                block = response.read(1024 * 256)
                if not block:
                    break
                output.write(block)
                done += len(block)
                if total:
                    print(f"\rYüklənir: {done * 100 // total}%", end="", flush=True)
                else:
                    print(f"\rYüklənir: {done // (1024 * 1024)} MB", end="", flush=True)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        try:
            os.remove(filename)
        except OSError:
            pass
        raise RuntimeError(f"Video yüklənmədi: {exc}") from exc
    print("\nYükləmə tamamlandı.")


def interactive() -> int:
    if not sys.stdin.isatty():
        print("Etkileşimli menüyü terminalden başlatın.", file=sys.stderr)
        return 2
    print("Anizium CLI — hoş geldiniz")
    while True:
        action = menu("Ne yapmak istiyorsunuz?", ["Anime izle", "İndir", "Son eklenen animeler / bölümler", "Çıkış"])
        if action in (-1, 3):
            return 0
        if action == 2:
            try:
                browse_latest_added()
            except (RuntimeError, KeyError, ValueError) as exc:
                print(f"Hata: {exc}", file=sys.stderr)
                wait_key()
            continue
        print("\nAnime adını yazın:")
        keyword = input(neon("> ")).strip()
        if not keyword:
            continue
        try:
            results = search(keyword, 30)
            if not results:
                print("Anime bulunamadı.")
                wait_key()
                continue
            anime_index = menu("Anime seçin:", [item["title"] for item in results] + ["Geri"])
            if anime_index < 0 or anime_index == len(results):
                continue
            anime = results[anime_index]
            eps = episodes(str(anime["id"]))
            current_ep_index = -1
            while True:
                next_exists = current_ep_index + 1 < len(eps)
                choices = [f"Bölüm {e['number']}" for e in eps]
                if next_exists:
                    next_number = eps[max(0, current_ep_index + 1)]["number"]
                    choices.append(f"Sonraki bölüme geç (Bölüm {next_number})")
                choices.append("Anime seçimine dön")
                ep_choice = menu("Bölüm seçin — " + anime["title"], choices)
                if ep_choice < 0 or ep_choice == len(choices) - 1:
                    break
                if next_exists and ep_choice == len(eps):
                    ep_index = max(0, current_ep_index + 1)
                else:
                    ep_index = ep_choice
                current_ep_index = ep_index
                episode = eps[ep_index]
                episode_url = episode["url"]
                data = sources(episode_url)
                if not data["streams"]:
                    print("Bu bölüm için video kaynağı bulunamadı.")
                    wait_key()
                    continue
                source_index = menu("Video kalitesini seçin:", [s["title"] for s in data["streams"]] + ["Geri"])
                if source_index < 0 or source_index == len(data["streams"]):
                    continue
                stream = data["streams"][source_index]
                subtitle_path = ""
                if data["subtitle"]:
                    try:
                        subtitle_path = save_subtitle(data["subtitle"], ".", f"{anime['title']}-bolum-{episode['number']}-altyazi")
                        print(f"Altyazı dosyası kaydedildi: {os.path.abspath(subtitle_path)}")
                    except RuntimeError as exc:
                        print(str(exc), file=sys.stderr)
                if action == 0:
                    available = [p for p in ("mpv", "vlc") if shutil.which(p)]
                    if not available:
                        raise RuntimeError("İzlemek için sisteme mpv veya VLC kurun.")
                    player_index = menu("Oynatıcı seçin:", available)
                    if player_index < 0:
                        continue
                    player = available[player_index]
                    if player == "mpv":
                        command = [shutil.which("mpv"), "--ytdl=no", "--referrer=" + episode_url,
                                   "--user-agent=Mozilla/5.0", "--http-header-fields=Origin: https://anizium.co",
                                   stream["url"]]
                        if subtitle_path:
                            command.append("--sub-file=" + os.path.abspath(subtitle_path))
                    else:
                        command = [shutil.which("vlc"), "--http-referrer=" + episode_url,
                                   "--http-user-agent=Mozilla/5.0", stream["url"]]
                        if subtitle_path:
                            command.append("--sub-file=" + os.path.abspath(subtitle_path))
                    print("Video açılıyor; kapatınca bölüm menüsüne dönülecek.")
                    try:
                        subprocess.run(command, check=False)
                    finally:
                        if subtitle_path.lower().endswith(".vtt"):
                            try:
                                os.remove(subtitle_path)
                            except FileNotFoundError:
                                pass
                else:
                    ext = ".mkv" if ".m3u8" in stream["url"].lower() else ".mp4"
                    base = safe_filename(f"{anime['title']} - bolum-{episode['number']}")
                    path = base + ext
                    download_video(stream["url"], path, episode_url)
                    print(f"Video kaydedildi: {os.path.abspath(path)}")
                    wait_key()
        except (RuntimeError, KeyError, ValueError, subprocess.SubprocessError) as exc:
            print(f"Hata: {exc}", file=sys.stderr)
            wait_key()


def main() -> int:
    parser = argparse.ArgumentParser(description="Anizium anime arama ve bölüm/stream bilgisi CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    p_search = sub.add_parser("search", aliases=["ara"], help="Anime ara; sorgu yoksa popülerleri göster")
    p_search.add_argument("query", nargs="?", default="")
    p_search.add_argument("--limit", type=int, default=20)
    p_info = sub.add_parser("info", aliases=["bilgi"], help="Anime detaylarını göster")
    p_info.add_argument("anime")
    p_eps = sub.add_parser("episodes", aliases=["bolumler"], help="Bölümleri listele")
    p_eps.add_argument("anime")
    p_stream = sub.add_parser("streams", aliases=["link"], help="Video ve altyazı kaynaklarını göster")
    p_stream.add_argument("episode_url", help="/watch/ID?season=1&episode=1 URL'si")
    p_watch = sub.add_parser("watch", aliases=["izle"], help="Video kaynağını seçip oynat, altyazıyı dosya olarak indir")
    p_watch.add_argument("episode_url", help="/watch/ID?season=1&episode=1 URL'si")
    p_watch.add_argument("--player", choices=["auto", "mpv", "vlc"], default="auto")
    p_watch.add_argument("--subtitle-dir", default=".", help="Altyazı dosyasının kaydedileceği klasör")
    args = parser.parse_args()
    try:
        if args.command in ("search", "ara"):
            print_json(search(args.query, max(1, min(args.limit, 100))))
        elif args.command in ("info", "bilgi"):
            a = anime_data(args.anime)
            print_json({"id": a.get("ID"), "title": a.get("name"), "turkish_title": a.get("name_tr"),
                        "japanese_title": a.get("name_jp"), "description": a.get("overview") or a.get("overview_short") or "",
                        "year": a.get("release_year"), "url": f"https://anizium.co/anime/{parse_id(args.anime)}"})
        elif args.command in ("episodes", "bolumler"):
            print_json(episodes(args.anime))
        elif args.command in ("streams", "link"):
            print_json(sources(args.episode_url))
        else:
            watch(args.episode_url, args.player, args.subtitle_dir)
        return 0
    except (RuntimeError, KeyError, ValueError) as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if len(sys.argv) == 1:
        raise SystemExit(interactive())
    raise SystemExit(main())
