// Read-only DOM capture function for the host browser tool's playwright.evaluate.
// No network requests, cookies, browser storage, hidden application state or UI actions.
(options) => {
  const text = (root, selector) => root.querySelector(selector)?.innerText?.trim() || null;
  const records = [];
  const limit = Math.min(Math.max(options.limit || 20, 1), 40);
  if (options.platform === "douyin" && location.hostname === "www.douyin.com") {
    for (const card of document.querySelectorAll(".search-result-card")) {
      const caption = text(card, ".BjLsdJMi, .hu36PKCP");
      const duration = text(card, ".FnM1bbIQ, .ZYKiUg6O");
      const wrapper = card.closest('[id^="waterfall_item_"]');
      const id = wrapper?.id?.match(/^waterfall_item_(\d{15,22})$/)?.[1];
      // Search suggestions, ads and image-only cards lack this verified video-card shape.
      if (!id || !caption || !duration) continue;
      records.push({id, kind: "video", title: caption.split("#")[0].trim().slice(0, 220),
        url: "https://www.douyin.com/video/" + id,
        author: text(card, ".WldPmwm5, .vgw3V2Fj"), published_display: text(card, ".dO8W7uoF, .iOLHOuw4"),
        likes_display: text(card, ".pMq55q1M span, .g5BarT4O span"), duration_display: duration,
        identity_source: "rendered_wrapper_id"});
      if (records.length >= limit) break;
    }
  } else if (options.platform === "xiaohongshu" && location.hostname === "www.xiaohongshu.com") {
    for (const card of document.querySelectorAll("section.note-item")) {
      const id = card.getAttribute("data-note-id");
      const title = text(card, "a.title");
      if (!/^[a-f0-9]{24}$/.test(id || "") || !title) continue;
      records.push({id, kind: "note", title,
        url: "https://www.xiaohongshu.com/explore/" + id,
        author: text(card, ".name"), published_display: text(card, ".time"),
        likes_display: text(card, ".count"), duration_display: null,
        identity_source: "rendered_data_note_id"});
      if (records.length >= limit) break;
    }
  } else {
    throw new Error("platform and actual page hostname must match");
  }
  const body = document.body.innerText;
  const gated = /登录后查看搜索结果|请完成下方验证|访问频次异常|安全验证/.test(body);
  return {capture_version: 1, platform: options.platform, query: options.query,
    sort: options.sort, sample_scope: options.sample_scope,
    observed_at: new Date().toISOString(), page_title: document.title,
    source_url: location.origin + location.pathname,
    status: gated ? "blocked" : records.length ? "ok" : "empty",
    diagnostic: gated ? "visible login/security gate; stop and hand control to user" : records.length ? null : "no matching rendered cards; loading/empty/layout change unresolved",
    records: gated ? [] : records,
    limitations: ["limited rendered search sample; not the complete platform", "display dates retained without fabricated exact timestamps", "rounded counts are not exact metrics", "no per-video watch-time or competitor playback count inferred"]};
}
