/* Anizium provider for Hibiki's scripted source runtime. */
var BASE_API = "https://api.anizium.co";
var SITE = "https://anizium.co";
var TOKEN_KEY = "hlxjl1c2w281ax473rt1ofgrvhyjvi";
var DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

function token() {
    var now = new Date(new Date().getTime() + 3 * 60 * 60 * 1000);
    var key = TOKEN_KEY + "_" + DAYS[now.getUTCDay()];
    var chars = "0123456789abcdefghijklmnopqrstuvwxyz";
    var random = "";
    for (var i = 0; i < 6; i++) random += chars.charAt(Math.floor(Math.random() * chars.length));
    var payload = "{";
    for (var j = 0; j < random.length; j++) {
        if (j) payload += ",";
        payload += "\"" + j + "\":\"" + random.charAt(j) + "\"";
    }
    payload += "}";
    var hex = "";
    for (var k = 0; k < payload.length; k++) {
        var code = payload.charCodeAt(k) ^ key.charCodeAt(k % key.length);
        hex += (code < 16 ? "0" : "") + code.toString(16);
    }
    return hex;
}

function api(path) {
    var response = fetch(BASE_API + path, {
        headers: {
            "Accept": "application/json",
            "Cf-Control": token(),
            "User-Agent": "Mozilla/5.0 Hibiki/1.0",
            "device": "browser",
            "language": "tr",
            "site": "main"
        }
    });
    // Hibiki's embedded fetch returns a plain response object with a `body`
    // string (not the browser Fetch Response API with a text() method).
    var body = response.body;
    return JSON.parse(String(body));
}

function enc(value) {
    return encodeURIComponent(String(value));
}

function animeId(value) {
    var match = String(value).match(/(?:anime|watch)\/(\d+)/);
    return match ? match[1] : String(value).replace(/^\/+|\/+$/g, "");
}

function poster(item) {
    var value = item.posterUrl || item.poster || item.Poster || item.banner || item.Banner ||
        item.cover || item.Cover || item.image || item.Image || item.thumbnail || "";
    value = String(value);
    if (value.indexOf("//") === 0) return "https:" + value;
    if (value && value.charAt(0) === "/") return SITE + value;
    return value;
}

function animeTitle(item, fallback) {
    return String(item.name || item.Name || item.title || item.Title || item.russianName ||
        item.englishName || item.originalName || item.AnimeName || fallback || "");
}

function card(item) {
    var id = String(item.ID || item.id || item.Id || "");
    var name = animeTitle(item, id);
    var image = poster(item);
    var page = String(item.pageUrl || item.url || (SITE + "/anime/" + id));
    return {
        id: id,
        name: name,
        title: name,
        russianName: name,
        englishName: String(item.englishName || name),
        japaneseName: String(item.japaneseName || item.originalName || name),
        originalName: String(item.originalName || item.japaneseName || name),
        poster: image || null,
        cover: image || null,
        image: image || null,
        imageUrl: image || null,
        posterUrl: image || null,
        posterFallbackUrl: image || null,
        pageUrl: page,
        url: page,
        description: String(item.description || item.Description || item.synopsis || item.summary || item.about || item.story || item.overview || ""),
        genres: item.genres || [],
        year: item.year || null,
        type: item.type || null,
        status: item.status || null
    };
}

function titleInfo(id) {
    var result = api("/anime/get?id=" + enc(animeId(id)));
    if (!result.success || !result.data) throw new Error("Anime not found");
    var item = result.data;
    var info = card({
        ID: item.ID || item.id || item.Id || animeId(id),
        name: item.name || item.Name || item.title || item.Title,
        englishName: item.englishName,
        originalName: item.originalName,
        japaneseName: item.japaneseName,
        poster: item.poster || item.Poster,
        posterUrl: item.posterUrl || item.PosterUrl,
        banner: item.banner || item.Banner,
        image: item.image || item.Image,
        description: item.description || item.Description || item.synopsis || item.summary || item.about || item.story || item.overview,
        genres: item.genres,
        year: item.year,
        type: item.type,
        status: item.status
    });
    var episodeCount = 0;
    var seasons = item.seasons || [];
    for (var i = 0; i < seasons.length; i++) episodeCount += (seasons[i].episodes || []).length;
    info.episodeCount = item.episodeCount || episodeCount || null;
    return info;
}

function searchAnime(query, page) {
    var req = JSON.parse(String(query));
    var q = String(req.query || req.searchQuery || "").trim();
    var wanted = Number(req.limit || req.pageSize || 20);
    if (!wanted || wanted < 1) wanted = 20;
    if (wanted < 30) wanted = 30;
    if (wanted > 100) wanted = 100;
    var items = [];
    var seen = {};
    var pageNo = 1;
    while (items.length < wanted && pageNo <= 20) {
        var path = q ? "/page/search?value=" + enc(q) + "&page=" + pageNo : "/page/top?platform=favorite&page=" + pageNo;
        var result = api(path);
        var pageData = result.page || {};
        var rows = pageData.data || [];
        if (!rows.length) break;
        for (var i = 0; i < rows.length && items.length < wanted; i++) {
            if (!rows[i]) continue;
            var itemId = String(rows[i].ID || rows[i].id || rows[i].Id || "");
            if (!itemId || seen[itemId]) continue;
            seen[itemId] = true;
            items.push(card(rows[i]));
        }
        pageNo = pageData.next_page ? Number(pageData.next_page) : pageNo + 1;
    }
    return items;
}

function playbackGroups(id) {
    var info = titleInfo(id);
    var result = api("/anime/get?id=" + enc(animeId(id)));
    var seasons = result.data.seasons || [];
    var eps = [];
    for (var s = 0; s < seasons.length; s++) {
        var season = seasons[s];
        var seasonNo = Number(season.number || (s + 1));
        var seasonEps = season.episodes || [];
        for (var e = 0; e < seasonEps.length; e++) {
            var epNo = Number(seasonEps[e].number || (e + 1));
            var epId = seasonNo + "_" + epNo;
            eps.push({id: epId, number: epNo, title: String(seasonEps[e].name || "Episode " + epNo), url: SITE + "/watch/" + animeId(id) + "?season=" + seasonNo + "&episode=" + epNo});
        }
    }
    if (!eps.length) eps.push({id: "1_1", number: 1, title: "Episode 1", url: SITE + "/watch/" + animeId(id) + "?season=1&episode=1"});
    return [{id: "main", name: "Episodes", episodes: eps}];
}

function playerLinks(id, groupId, episodeId) {
    var parts = String(episodeId).split("_");
    var season = parts.length > 1 ? parts[0] : "1";
    var episode = parts.length > 1 ? parts[1] : parts[0];
    var path = "/anime/source?id=" + enc(animeId(id)) + "&site=main&plan=&server=1&season=" + enc(season) + "&episode=" + enc(episode);
    var result = api(path);
    var groups = result.groups || [];
    var links = [];
    for (var i = 0; i < groups.length; i++) {
        var entries = groups[i].items || [];
        for (var j = 0; j < entries.length; j++) {
            var item = entries[j];
            if (!item.link) continue;
            var url = String(item.link);
            var lower = url.toLowerCase();
            var type = lower.indexOf(".m3u8") >= 0 ? "DIRECT_HLS" : (lower.indexOf(".mp4") >= 0 ? "DIRECT_MP4" : "EMBED");
            var label = (groups[i].name ? String(groups[i].name) + " - " : "") + (item.quality ? String(item.quality) + "p" : "Video");
            links.push({url: url, type: type, quality: label, headers: {Referer: SITE + "/", Origin: SITE}});
        }
    }
    var subtitles = result.subtitles || [];
    for (var k = 0; k < subtitles.length; k++) {
        if (subtitles[k].link && String(subtitles[k].group || "").toLowerCase() === "tr") {
            for (var n = 0; n < links.length; n++) links[n].subtitles = [{url: String(subtitles[k].link), label: "Türkçe", language: "tr"}];
            break;
        }
    }
    if (!links.length) throw new Error("No playable streams found");
    return links;
}

var Provider = {
    search: searchAnime,
    latest: function (limit) {
        var count = Number(limit || 20);
        var items = [];
        var seen = {};
        var pageNo = 1;
        while (items.length < count && pageNo <= 20) {
            var result = api("/page/last-added-episodes?page=" + pageNo);
            var pageData = result.page || {};
            var rows = pageData.data || [];
            if (!rows.length) break;
            for (var i = 0; i < rows.length && items.length < count; i++) {
                var item = rows[i];
                var id = String(item.ID || item.id || item.Id || "");
                if (!id || seen[id]) continue;
                seen[id] = true;
                items.push(card(item));
            }
            pageNo = pageData.next_page ? Number(pageData.next_page) : pageNo + 1;
        }
        return items;
    },
    getById: function (id) { return titleInfo(id); },
    getSettings: function () { return {filters: [], sortOptions: []}; },
    getPlaybackGroups: playbackGroups,
    getPlayerLinks: playerLinks
};
