from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Candidate paths for the drop-in API client shipped by the Blink backend repo.
# First match wins. Add more paths if the file moves.
_API_CLIENT_CANDIDATES = [
    Path(__file__).parent / "blink" / "frontend" / "blink_api_client.js",
    Path("/home/mac/blink/frontend/blink_api_client.js"),
    Path(__file__).parent / "blink_api_client.js",
]


def _find_api_client() -> Path | None:
    for p in _API_CLIENT_CANDIDATES:
        if p.exists():
            return p
    return None

HTML = r"""<!doctype html>
<html lang="da">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blink</title>
<style>
  :root {
    /* ==== BLINK "Warm Signal" — canonical palette ==== */
    /* Primary coral is the brand/action color. Blue is a small accent only. */
    /* Mint is reserved for online/success. Don't introduce new hues in UI chrome. */
    --coral: #FF6B4A;            /* primary */
    --coral-deep: #D94D33;       /* primary dark */
    --coral-soft: #FFE1D8;       /* primary soft */
    --coral-bg: #FFF2EC;         /* primary wash (derived — lighter than soft) */
    --sand: #EFE6DA;             /* surface soft */
    --cream: #FFFDF8;            /* surface */
    --page-bg: #F7F1E8;          /* app background */
    --ink: #24211F;              /* text */
    --ink-soft: #4A4340;         /* text secondary (derived) */
    --muted: #8A8178;            /* muted text */
    --muted-soft: #E1D6C8;       /* border / divider */
    --border: #E1D6C8;           /* alias of muted-soft for semantic use */
    --accent-blue: #3C7DFF;      /* small signal only — not a surface color */
    --accent-mint: #7BCFA6;      /* success / online */
    --online: #7BCFA6;           /* alias of accent-mint */
    --bubble: #FFFFFF;
    --shadow-soft: 0 1px 2px rgba(60,30,15,.06), 0 2px 10px rgba(60,30,15,.04);
    --shadow-float: 0 10px 30px rgba(60,30,15,.12);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, "SF Pro Text", "Inter", "Segoe UI", Helvetica, Arial, sans-serif; }
  html, body { height: 100%; }
  body { background: var(--page-bg); display: flex; justify-content: center; align-items: center; min-height: 100vh; color: var(--ink); -webkit-font-smoothing: antialiased; padding: 20px; }

  .phone { position: relative; width: 400px; height: min(820px, calc(100vh - 40px)); background: var(--sand); display: flex; flex-direction: column; border-radius: 36px; overflow: hidden; box-shadow: 0 30px 80px rgba(80,40,20,.18); }

  /* View system */
  .view { display: flex; flex-direction: column; flex: 1; min-height: 0; }
  .view.hidden { display: none; }
  .hidden { display: none !important; }

  /* Chat header */
  header { padding: 14px 16px; display: flex; align-items: center; gap: 12px; background: var(--cream); border-bottom: 1px solid rgba(0,0,0,.03); }
  .brand { display: flex; align-items: center; gap: 8px; }
  .brand-mark { width: 22px; height: 22px; border-radius: 8px; background: linear-gradient(135deg, var(--coral), var(--coral-deep)); position: relative; display: flex; align-items: center; justify-content: center; animation: blink 2.6s ease-in-out infinite; }
  .brand-mark::after { content: ""; width: 6px; height: 6px; border-radius: 50%; background: #fff; }
  @keyframes blink { 0%, 100% { box-shadow: 0 0 0 0 rgba(255,122,89,.45); } 50% { box-shadow: 0 0 0 7px rgba(255,122,89,0); } }
  .brand h1 { font-size: 15.5px; font-weight: 700; letter-spacing: -0.2px; color: var(--ink); }
  .peer { display: flex; align-items: center; gap: 10px; flex: 1; }
  .avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--coral-soft); color: var(--coral-deep); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13.5px; position: relative; flex-shrink: 0; }
  .avatar::after { content: ""; position: absolute; right: -1px; bottom: -1px; width: 10px; height: 10px; border-radius: 50%; background: var(--online); border: 2px solid var(--cream); }
  .avatar.group { background: var(--sand); color: var(--ink-soft); }
  .avatar.group::after { display: none; }
  .peer-info .name { font-size: 14px; font-weight: 600; line-height: 1.2; }
  .peer-info .status { font-size: 11.5px; color: var(--muted); margin-top: 1px; }
  .header-icon { width: 34px; height: 34px; border-radius: 50%; background: var(--coral-bg); color: var(--coral-deep); display: flex; align-items: center; justify-content: center; cursor: pointer; transition: background 160ms ease; border: none; font-family: inherit; }
  .header-icon:hover { background: var(--coral-soft); }
  .header-icon svg { width: 15px; height: 15px; }
  .header-icon.pill { width: auto; padding: 0 11px; height: 30px; border-radius: 999px; gap: 6px; font-size: 11.5px; font-weight: 700; letter-spacing: .1px; color: var(--coral-deep); }
  .header-icon.pill svg { width: 12px; height: 12px; }

  .chat-back-btn { width: 32px; height: 32px; border-radius: 50%; background: var(--coral-bg); color: var(--coral-deep); border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 160ms ease; flex-shrink: 0; }
  .chat-back-btn:hover { background: var(--coral-soft); }
  .chat-back-btn svg { width: 14px; height: 14px; }

  /* Messages */
  #messages { flex: 1; overflow-y: auto; padding: 22px 14px 10px; display: flex; flex-direction: column; gap: 10px; }
  #messages::-webkit-scrollbar { width: 4px; }
  #messages::-webkit-scrollbar-thumb { background: var(--muted-soft); border-radius: 2px; }

  .row { display: flex; flex-direction: column; max-width: 78%; animation: rowIn 320ms cubic-bezier(.2,.8,.2,1); }
  .row.mine { align-self: flex-end; align-items: flex-end; }
  .row.theirs { align-self: flex-start; align-items: flex-start; }
  @keyframes rowIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

  .bubble { padding: 11px 15px; border-radius: 20px; font-size: 14.5px; line-height: 1.45; box-shadow: var(--shadow-soft); position: relative; transition: opacity 380ms ease, transform 380ms ease, filter 380ms ease; }
  .mine .bubble { background: var(--coral); color: #fff; border-bottom-right-radius: 6px; }
  .theirs .bubble { background: var(--bubble); color: var(--ink); border-bottom-left-radius: 6px; }
  .gone-anim { opacity: 0 !important; transform: scale(.96); filter: blur(2px); }

  /* Progress bar */
  .progress { height: 2px; background: rgba(0,0,0,.06); border-radius: 2px; margin-top: 7px; overflow: hidden; width: 160px; max-width: 100%; }
  .mine .progress { margin-left: auto; }
  .progress-fill { height: 100%; background: var(--coral); border-radius: 2px; width: 100%; transform-origin: left center; }
  .progress-fill.running { animation: drain var(--lifetime, 60000ms) linear forwards; animation-delay: var(--lifetime-delay, 0ms); }
  @keyframes drain { from { transform: scaleX(1); } to { transform: scaleX(0); } }

  /* Meta line */
  .meta { font-size: 10.5px; color: var(--muted); margin-top: 5px; padding: 0 8px; display: flex; align-items: center; gap: 5px; }
  .mine .meta { justify-content: flex-end; }
  .meta .ico { width: 11px; height: 11px; opacity: .75; }
  .meta.seen-label { color: var(--coral-deep); font-weight: 500; }

  /* Opened chip (photo aftermath) */
  .photo-opened { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px; background: var(--coral-bg); color: var(--coral-deep); font-size: 11.5px; font-weight: 600; transition: opacity 380ms ease, transform 380ms ease; opacity: 0; animation: fadeIn 320ms ease forwards; }
  .photo-opened svg { width: 11px; height: 11px; opacity: .85; }
  @keyframes fadeIn { to { opacity: 1; } }

  /* Photo message */
  .photo-card { width: 200px; border-radius: 22px; overflow: hidden; box-shadow: var(--shadow-soft); cursor: default; position: relative; transition: transform 200ms ease, box-shadow 200ms ease; background: var(--bubble); }
  .photo-card.clickable { cursor: pointer; }
  .photo-card.clickable:hover { transform: translateY(-2px); box-shadow: var(--shadow-float); }
  .photo-thumb { aspect-ratio: 4/5; position: relative; display: flex; align-items: center; justify-content: center; overflow: hidden; }
  .photo-thumb.preview { background: linear-gradient(140deg, #FFD5C2 0%, #FF9B7A 55%, #F2785C 100%); }
  .photo-thumb.preview::after { content: "🌳"; position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 64px; filter: drop-shadow(0 4px 14px rgba(0,0,0,.2)); }
  .photo-thumb.unopened {
    background:
      radial-gradient(circle at 30% 25%, rgba(255,255,255,.35), transparent 55%),
      radial-gradient(circle at 75% 80%, rgba(242,106,72,.55), transparent 60%),
      linear-gradient(140deg, #FFB99D 0%, #FF8566 55%, #F26A48 100%);
  }
  .photo-thumb.unopened::before { content: ""; position: absolute; inset: 0; background: radial-gradient(circle at center, transparent 40%, rgba(30,20,15,.08) 100%); }
  .blink-ico { width: 54px; height: 54px; border-radius: 50%; display: flex; align-items: center; justify-content: center; z-index: 2; position: relative; }
  .blink-ico::before, .blink-ico::after { content: ""; position: absolute; inset: 0; border-radius: 50%; border: 1.5px solid rgba(255,255,255,.7); }
  .blink-ico::before { animation: blinkPulse 2.2s ease-out infinite; }
  .blink-ico::after { animation: blinkPulse 2.2s ease-out infinite .9s; }
  .blink-ico .core { width: 22px; height: 22px; border-radius: 50%; background: #fff; box-shadow: 0 2px 10px rgba(0,0,0,.15); position: relative; z-index: 2; }
  .blink-ico .core::after { content: ""; position: absolute; inset: 6px; border-radius: 50%; background: var(--coral-deep); }
  @keyframes blinkPulse { 0% { transform: scale(.7); opacity: .9; } 100% { transform: scale(1.6); opacity: 0; } }
  .photo-badge { position: absolute; top: 10px; left: 10px; background: rgba(30,20,15,.42); color: #fff; font-size: 10.5px; padding: 4px 9px 4px 7px; border-radius: 999px; display: flex; align-items: center; gap: 4px; backdrop-filter: blur(10px); z-index: 3; font-weight: 600; letter-spacing: .2px; }
  .photo-badge svg { width: 10px; height: 10px; }
  .photo-cta { position: absolute; left: 0; right: 0; bottom: 0; padding: 10px 12px; font-size: 12px; color: #fff; text-align: center; font-weight: 600; background: linear-gradient(to top, rgba(30,20,15,.45), transparent); letter-spacing: .1px; z-index: 3; }

  /* Input area */
  .input-area { padding: 10px 14px 16px; background: var(--sand); }
  .lifetime-chips { display: flex; gap: 6px; padding: 0 4px 10px; }
  .chip { padding: 7px 13px; border-radius: 999px; background: transparent; border: 1px solid var(--muted-soft); color: var(--ink-soft); font-size: 12.5px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 180ms ease; font-family: inherit; }
  .chip:hover { background: var(--cream); }
  .chip.active { background: var(--coral); color: #fff; border-color: var(--coral); box-shadow: 0 3px 10px rgba(255,122,89,.28); }
  .chip svg { width: 12px; height: 12px; }

  form { display: flex; gap: 10px; align-items: center; }
  input[type=text] { flex: 1; padding: 14px 18px; border: none; border-radius: 999px; background: var(--cream); font-size: 14.5px; outline: none; color: var(--ink); box-shadow: inset 0 0 0 1px rgba(0,0,0,.04); transition: box-shadow 180ms ease; font-family: inherit; }
  input[type=text]:focus { box-shadow: inset 0 0 0 1.5px var(--coral); }
  input[type=text]::placeholder { color: var(--muted); }
  button.send { width: 46px; height: 46px; border: none; border-radius: 50%; background: var(--coral); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 14px rgba(255,122,89,.35); transition: transform 140ms ease, box-shadow 180ms ease; flex-shrink: 0; }
  button.send:hover { box-shadow: 0 6px 20px rgba(255,122,89,.42); }
  button.send:active { transform: scale(.92); }
  button.send.pulse { animation: sendPulse 260ms ease; }
  button.send svg { width: 18px; height: 18px; }
  @keyframes sendPulse { 0% { transform: scale(1); } 45% { transform: scale(.88); } 100% { transform: scale(1); } }

  /* Photo overlay */
  .overlay { position: absolute; inset: 0; background: rgba(30,20,15,.96); display: none; flex-direction: column; align-items: center; justify-content: center; z-index: 10; padding: 24px; }
  .overlay.open { display: flex; animation: overlayIn 280ms ease; }
  @keyframes overlayIn { from { opacity: 0; transform: scale(.98); } to { opacity: 1; transform: scale(1); } }
  .overlay-bar { position: absolute; top: 0; left: 0; right: 0; height: 3px; background: rgba(255,255,255,.15); }
  .overlay-bar-fill { height: 100%; background: var(--coral); width: 100%; transform-origin: left; }
  .overlay-img { width: 100%; aspect-ratio: 4/5; border-radius: 22px; background: linear-gradient(140deg, #FFD5C2 0%, #FF9B7A 55%, #F2785C 100%); box-shadow: 0 24px 60px rgba(0,0,0,.45); position: relative; overflow: hidden; animation: imgIn 360ms cubic-bezier(.2,.8,.2,1); }
  .overlay-img::after { content: "🌳"; position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 110px; filter: drop-shadow(0 6px 20px rgba(0,0,0,.3)); }
  @keyframes imgIn { from { opacity: 0; transform: scale(.94); } to { opacity: 1; transform: scale(1); } }
  .overlay-meta { color: #fff; margin-top: 18px; font-size: 12.5px; opacity: .82; display: flex; align-items: center; gap: 6px; }
  .overlay-meta svg { width: 12px; height: 12px; }
  .overlay-close { position: absolute; top: 16px; right: 16px; width: 34px; height: 34px; border-radius: 50%; background: rgba(255,255,255,.14); color: #fff; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 160ms ease; }
  .overlay-close:hover { background: rgba(255,255,255,.24); }
  .overlay-close svg { width: 13px; height: 13px; }

  /* ============ CHILD HOME ============ */
  .home-header { padding: 14px 16px; display: flex; align-items: center; gap: 10px; background: var(--cream); border-bottom: 1px solid rgba(0,0,0,.03); }
  .home-header .brand h1 { font-size: 17px; }
  .home-header .hi { font-size: 12px; color: var(--muted); font-weight: 500; margin-left: 2px; }
  .home-header .spacer { flex: 1; }

  .home-body { flex: 1; overflow-y: auto; padding: 14px 14px 16px; background: linear-gradient(180deg, var(--coral-bg) 0%, transparent 180px); }
  .home-body::-webkit-scrollbar { width: 4px; }
  .home-body::-webkit-scrollbar-thumb { background: var(--muted-soft); border-radius: 2px; }
  .child-section { display: none; animation: rowIn 240ms cubic-bezier(.2,.8,.2,1); }
  .child-section.active { display: block; }

  .section-title-row { display: flex; align-items: center; justify-content: space-between; padding: 2px 4px 10px; }
  .section-title-row .ttl { font-size: 11px; font-weight: 700; color: var(--muted); letter-spacing: .5px; text-transform: uppercase; }
  .section-title-row.spaced { margin-top: 18px; }
  /* Home view: warmer, less corporate section headings */
  #viewChildHome .section-title-row .ttl { font-size: 13.5px; font-weight: 800; color: var(--ink); letter-spacing: -.2px; text-transform: none; display: inline-flex; align-items: center; gap: 7px; }
  #viewChildHome .section-title-row .ttl .count { font-size: 11px; font-weight: 700; color: var(--muted); background: var(--cream); padding: 2px 8px; border-radius: 999px; box-shadow: inset 0 0 0 1px rgba(0,0,0,.04); }

  /* Group CTAs */
  .group-ctas { display: grid; grid-template-columns: 1.05fr .95fr; gap: 10px; margin-bottom: 16px; }
  .group-cta { position: relative; background: var(--cream); border-radius: 20px; padding: 14px 14px 13px; cursor: pointer; border: none; font-family: inherit; box-shadow: var(--shadow-soft); text-align: left; transition: transform 180ms ease, box-shadow 180ms ease; display: flex; flex-direction: column; gap: 10px; color: var(--ink); overflow: hidden; }
  .group-cta:hover { transform: translateY(-2px); box-shadow: var(--shadow-float); }
  .group-cta .ic { position: relative; width: 36px; height: 36px; border-radius: 12px; background: var(--coral-bg); color: var(--coral-deep); display: flex; align-items: center; justify-content: center; }
  .group-cta .ic svg { width: 18px; height: 18px; }
  .group-cta .ttl { font-size: 13.5px; font-weight: 800; line-height: 1.2; letter-spacing: -.1px; }
  .group-cta .sub { font-size: 11px; opacity: .65; margin-top: 2px; font-weight: 500; }

  /* Secondary CTA: warm, not flat */
  .group-cta:not(.primary) { background: linear-gradient(140deg, var(--cream) 0%, var(--coral-bg) 140%); }
  .group-cta:not(.primary) .ic { background: #fff; box-shadow: inset 0 0 0 1.5px var(--coral-soft); }

  /* Primary CTA: gradient + soft inner glow + blink-dot */
  .group-cta.primary { background: linear-gradient(135deg, var(--coral) 0%, var(--coral-deep) 100%); color: #fff; box-shadow: 0 8px 22px rgba(255,122,89,.32); }
  .group-cta.primary::before { content: ""; position: absolute; inset: 0; background: radial-gradient(circle at 88% 12%, rgba(255,255,255,.28), transparent 55%); pointer-events: none; }
  .group-cta.primary .ic { background: rgba(255,255,255,.22); color: #fff; }
  .group-cta.primary .ic::after { content: ""; position: absolute; top: -3px; right: -3px; width: 9px; height: 9px; border-radius: 50%; background: #fff; box-shadow: 0 0 0 2px rgba(255,122,89,.45); animation: ctaDot 2.4s ease-in-out infinite; }
  .group-cta.primary:hover { box-shadow: 0 10px 28px rgba(255,122,89,.42); }
  .group-cta.primary .sub { opacity: .9; }
  @keyframes ctaDot { 0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255,255,255,.55); } 55% { transform: scale(1.18); box-shadow: 0 0 0 7px rgba(255,255,255,0); } }

  /* Group list */
  .group-list { background: var(--cream); border-radius: 22px; box-shadow: var(--shadow-soft); overflow: hidden; }
  .group-item { display: flex; align-items: center; gap: 13px; padding: 13px 14px; cursor: pointer; transition: background 160ms ease; border: none; background: transparent; width: 100%; text-align: left; font-family: inherit; border-bottom: 1px solid rgba(0,0,0,.04); }
  .group-item:last-child { border-bottom: none; }
  .group-item:hover { background: linear-gradient(90deg, var(--coral-bg) 0%, var(--cream) 85%); }
  .group-avatars { position: relative; width: 54px; height: 46px; flex-shrink: 0; }
  .group-avatars .mini { position: absolute; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; border: 2.5px solid var(--cream); box-shadow: 0 1px 3px rgba(80,40,20,.09); }
  .group-avatars .mini.a1 { top: 0; left: 0; background: var(--coral-soft); color: var(--coral-deep); z-index: 3; }
  .group-avatars .mini.a2 { top: 6px; left: 13px; background: var(--sand); color: var(--ink-soft); z-index: 2; }
  .group-avatars .mini.a3 { top: 14px; left: 24px; background: var(--coral-bg); color: var(--coral-deep); z-index: 1; }
  .group-avatars .more { position: absolute; top: 20px; left: 32px; min-width: 22px; height: 22px; padding: 0 5px; border-radius: 999px; background: var(--cream); color: var(--ink-soft); font-size: 9.5px; font-weight: 800; display: flex; align-items: center; justify-content: center; border: 2px solid var(--cream); box-shadow: inset 0 0 0 1.5px var(--muted-soft); z-index: 4; }
  .group-item .chat-meta { flex: 1; min-width: 0; }
  .group-item .top { display: flex; align-items: center; gap: 6px; }
  .group-item .name { font-size: 14.5px; font-weight: 800; color: var(--ink); letter-spacing: -.1px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .group-item .live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--coral); flex-shrink: 0; animation: livePulse 2s ease-in-out infinite; }
  @keyframes livePulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(255,122,89,.55); } 60% { box-shadow: 0 0 0 6px rgba(255,122,89,0); } }
  .group-item .time { font-size: 10.5px; color: var(--muted); margin-left: auto; flex-shrink: 0; font-weight: 600; }
  .group-item .sub { font-size: 11px; color: var(--muted); font-weight: 600; margin-top: 1px; }
  .group-item .last { font-size: 12.5px; color: var(--ink-soft); margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.35; }
  .group-item .last .who { color: var(--coral-deep); font-weight: 700; }
  .group-item .unread { width: 20px; height: 20px; border-radius: 50%; background: var(--coral); color: #fff; font-size: 10.5px; font-weight: 800; display: flex; align-items: center; justify-content: center; margin-left: 8px; flex-shrink: 0; box-shadow: 0 2px 6px rgba(255,122,89,.35); }

  /* Chat list (direct chats — compact variant used under groups) */
  .chat-list { background: var(--cream); border-radius: 22px; box-shadow: var(--shadow-soft); overflow: hidden; }
  .chat-list.compact .chat-item { padding: 10px 14px; }
  .chat-list.compact .chat-item .avatar { width: 38px; height: 38px; font-size: 13.5px; }
  .chat-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; cursor: pointer; transition: background 140ms ease; border: none; background: transparent; width: 100%; text-align: left; font-family: inherit; border-bottom: 1px solid rgba(0,0,0,.04); }
  .chat-item:last-child { border-bottom: none; }
  .chat-item:hover { background: var(--coral-bg); }
  .chat-item .avatar { width: 46px; height: 46px; font-size: 15.5px; }
  .chat-item .avatar::after { display: none; }
  .chat-item .avatar.online::after { display: block; width: 10px; height: 10px; }
  .chat-item .chat-meta { flex: 1; min-width: 0; }
  .chat-item .top { display: flex; align-items: baseline; gap: 6px; }
  .chat-item .name { font-size: 14px; font-weight: 700; color: var(--ink); }
  .chat-item .time { font-size: 10.5px; color: var(--muted); margin-left: auto; flex-shrink: 0; font-weight: 600; }
  .chat-item .last { font-size: 12.5px; color: var(--muted); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.35; display: flex; align-items: center; gap: 5px; }
  .chat-item .last.blink-active { color: var(--coral-deep); font-weight: 600; }
  .chat-item .last svg { width: 11px; height: 11px; flex-shrink: 0; }
  .chat-item .unread { width: 20px; height: 20px; border-radius: 50%; background: var(--coral); color: #fff; font-size: 10.5px; font-weight: 800; display: flex; align-items: center; justify-content: center; margin-left: 8px; flex-shrink: 0; box-shadow: 0 2px 6px rgba(255,122,89,.35); }

  /* Friends grid */
  .friends-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .friend-tile { background: var(--cream); border-radius: 18px; padding: 14px 8px 12px; text-align: center; box-shadow: var(--shadow-soft); cursor: pointer; border: none; font-family: inherit; transition: all 180ms ease; }
  .friend-tile:hover { transform: translateY(-2px); box-shadow: var(--shadow-float); }
  .friend-tile .avatar { margin: 0 auto 8px; width: 44px; height: 44px; font-size: 15px; }
  .friend-tile .avatar::after { display: none; }
  .friend-tile .name { font-size: 12.5px; font-weight: 700; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .btn-add-friend { display: inline-flex; align-items: center; gap: 6px; padding: 7px 13px; border-radius: 999px; background: var(--coral); color: #fff; font-size: 12px; font-weight: 700; border: none; cursor: pointer; font-family: inherit; box-shadow: 0 3px 10px rgba(255,122,89,.3); transition: all 160ms ease; }
  .btn-add-friend.ghost { background: transparent; color: var(--coral-deep); box-shadow: none; border: 1px solid var(--coral-soft); }
  .btn-add-friend.ghost:hover { background: var(--coral-bg); }
  .btn-add-friend:hover { transform: translateY(-1px); box-shadow: 0 5px 14px rgba(255,122,89,.38); }
  .btn-add-friend svg { width: 12px; height: 12px; }

  /* My code view */
  .code-card { background: var(--cream); border-radius: 22px; box-shadow: var(--shadow-soft); padding: 20px 20px 18px; text-align: center; margin-bottom: 14px; }
  .code-card .greet { font-size: 12.5px; color: var(--muted); margin-bottom: 2px; font-weight: 500; }
  .code-card .who-me { font-size: 16px; font-weight: 800; color: var(--ink); margin-bottom: 14px; }
  .qr-wrap { background: #fff; border-radius: 20px; padding: 14px; display: inline-block; box-shadow: 0 6px 18px rgba(80,40,20,.10); margin: 0 auto 14px; position: relative; }
  .qr-grid { display: block; width: 196px; height: 196px; }
  .qr-grid rect { fill: var(--ink); }
  .qr-logo { position: absolute; inset: 50% auto auto 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border-radius: 12px; background: linear-gradient(135deg, var(--coral), var(--coral-deep)); display: flex; align-items: center; justify-content: center; box-shadow: 0 0 0 5px #fff; }
  .qr-logo::after { content: ""; width: 9px; height: 9px; border-radius: 50%; background: #fff; }

  .code-text { font-size: 22px; font-weight: 800; color: var(--ink); letter-spacing: 2px; font-feature-settings: "tnum"; }
  .code-label { font-size: 10.5px; color: var(--muted); font-weight: 700; letter-spacing: .5px; text-transform: uppercase; margin-top: 4px; }

  .code-foot { font-size: 11.5px; color: var(--ink-soft); background: var(--coral-bg); padding: 12px 14px; border-radius: 16px; line-height: 1.55; display: flex; gap: 10px; align-items: flex-start; text-align: left; }
  .code-foot svg { width: 14px; height: 14px; color: var(--coral-deep); flex-shrink: 0; margin-top: 1px; }

  /* Add flow shared */
  .add-header { padding: 14px 16px; display: flex; align-items: center; gap: 12px; background: var(--cream); border-bottom: 1px solid rgba(0,0,0,.03); }
  .add-header .ttl { font-size: 15px; font-weight: 700; color: var(--ink); flex: 1; }

  .add-body { flex: 1; overflow-y: auto; padding: 18px 16px 18px; }
  .add-step { display: none; animation: rowIn 260ms cubic-bezier(.2,.8,.2,1); }
  .add-step.active { display: block; }

  .add-intro { text-align: center; margin: 4px 8px 18px; }
  .add-intro h2 { font-size: 19px; font-weight: 800; margin-bottom: 6px; color: var(--ink); letter-spacing: -.3px; }
  .add-intro p { font-size: 13px; color: var(--muted); line-height: 1.5; }

  .add-choice { background: var(--cream); border-radius: 20px; padding: 16px; cursor: pointer; border: none; font-family: inherit; box-shadow: var(--shadow-soft); transition: all 180ms ease; display: flex; align-items: center; gap: 14px; width: 100%; margin-bottom: 12px; text-align: left; }
  .add-choice:hover { transform: translateY(-1px); box-shadow: var(--shadow-float); }
  .add-choice .ic { width: 50px; height: 50px; border-radius: 14px; background: var(--coral-bg); color: var(--coral-deep); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .add-choice .ic svg { width: 22px; height: 22px; }
  .add-choice .txt { flex: 1; }
  .add-choice .ttl { font-size: 15px; font-weight: 800; color: var(--ink); margin-bottom: 2px; }
  .add-choice .sub { font-size: 12px; color: var(--muted); line-height: 1.4; }
  .add-choice .arr { color: var(--muted); display: flex; }
  .add-choice .arr svg { width: 14px; height: 14px; }

  /* Scanner mock */
  .scanner { aspect-ratio: 1; border-radius: 24px; background: linear-gradient(135deg, #2B2B2B 0%, #1a1a1a 100%); position: relative; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,.25); margin-bottom: 14px; display: flex; align-items: center; justify-content: center; }
  .scanner .frame { width: 64%; aspect-ratio: 1; position: relative; }
  .scanner .corner { position: absolute; width: 26px; height: 26px; border: 3px solid var(--coral); }
  .scanner .corner.tl { top: 0; left: 0; border-right: none; border-bottom: none; border-top-left-radius: 10px; }
  .scanner .corner.tr { top: 0; right: 0; border-left: none; border-bottom: none; border-top-right-radius: 10px; }
  .scanner .corner.bl { bottom: 0; left: 0; border-right: none; border-top: none; border-bottom-left-radius: 10px; }
  .scanner .corner.br { bottom: 0; right: 0; border-left: none; border-top: none; border-bottom-right-radius: 10px; }
  .scanner .laser { position: absolute; left: 6%; right: 6%; height: 2px; background: linear-gradient(90deg, transparent, var(--coral), transparent); box-shadow: 0 0 18px var(--coral); animation: laser 1.8s ease-in-out infinite; }
  @keyframes laser { 0%, 100% { top: 12%; } 50% { top: 88%; } }
  .scanner .scan-hint { position: absolute; bottom: 16px; left: 0; right: 0; text-align: center; color: rgba(255,255,255,.7); font-size: 12px; font-weight: 500; letter-spacing: .2px; }

  /* Code entry (shared) */
  .code-entry { background: var(--cream); border-radius: 22px; padding: 18px; margin-bottom: 14px; box-shadow: var(--shadow-soft); }
  .code-entry label { display: block; font-size: 11px; font-weight: 700; color: var(--muted); letter-spacing: .4px; text-transform: uppercase; margin-bottom: 10px; text-align: center; }
  .code-entry input { width: 100%; padding: 15px 16px; border: none; border-radius: 14px; background: #fff; font-size: 18px; font-weight: 700; letter-spacing: 2px; color: var(--ink); outline: none; box-shadow: inset 0 0 0 1.5px var(--muted-soft); transition: box-shadow 180ms ease; font-family: inherit; text-transform: uppercase; text-align: center; }
  .code-entry input:focus { box-shadow: inset 0 0 0 2px var(--coral); }
  .code-entry .example { font-size: 11.5px; color: var(--muted); text-align: center; margin-top: 10px; }
  .code-entry input.group-name { letter-spacing: 0; text-transform: none; font-size: 16px; font-weight: 600; text-align: left; }

  /* Found preview */
  .found-card { background: var(--cream); border-radius: 22px; padding: 24px 18px; text-align: center; box-shadow: var(--shadow-soft); margin-bottom: 14px; animation: popIn 280ms cubic-bezier(.2,1.2,.4,1); }
  .found-card .avatar { width: 72px; height: 72px; font-size: 26px; margin: 0 auto 12px; }
  .found-card .avatar::after { display: none; }
  .found-card .name { font-size: 18px; font-weight: 800; color: var(--ink); }
  .found-card .meta { font-size: 12px; color: var(--muted); margin-top: 4px; display: flex; align-items: center; justify-content: center; gap: 6px; }
  .found-card .meta svg { width: 11px; height: 11px; }

  @keyframes popIn { 0% { transform: scale(.92); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }

  .btn-primary-big { width: 100%; padding: 14px; border-radius: 16px; background: var(--coral); color: #fff; border: none; font-family: inherit; font-size: 14.5px; font-weight: 700; cursor: pointer; box-shadow: 0 6px 16px rgba(255,122,89,.35); transition: all 180ms ease; }
  .btn-primary-big:hover { transform: translateY(-1px); box-shadow: 0 8px 22px rgba(255,122,89,.42); }
  .btn-primary-big:disabled { opacity: .5; cursor: not-allowed; transform: none; box-shadow: none; }
  .btn-secondary-big { width: 100%; padding: 13px; border-radius: 16px; background: transparent; color: var(--ink-soft); border: 1.5px solid var(--muted-soft); font-family: inherit; font-size: 13.5px; font-weight: 600; cursor: pointer; margin-top: 10px; }
  .btn-secondary-big:hover { background: var(--cream); }

  /* Success card */
  .success-card { text-align: center; padding: 30px 20px; background: var(--cream); border-radius: 22px; box-shadow: var(--shadow-soft); margin-bottom: 14px; }
  .success-card .check { width: 72px; height: 72px; border-radius: 50%; background: var(--coral); color: #fff; display: flex; align-items: center; justify-content: center; margin: 0 auto 14px; animation: popIn 360ms cubic-bezier(.2,1.2,.4,1); box-shadow: 0 8px 22px rgba(255,122,89,.35); }
  .success-card .check svg { width: 32px; height: 32px; }
  .success-card h3 { font-size: 18px; font-weight: 800; color: var(--ink); margin-bottom: 6px; }
  .success-card p { font-size: 13px; color: var(--ink-soft); line-height: 1.5; }
  .success-card .parent-note { font-size: 11.5px; color: var(--muted); margin-top: 12px; background: var(--coral-bg); padding: 10px 12px; border-radius: 12px; display: flex; gap: 8px; align-items: flex-start; text-align: left; }
  .success-card .parent-note svg { width: 13px; height: 13px; color: var(--coral-deep); flex-shrink: 0; margin-top: 1px; }

  /* Friend picker (group create) */
  .picker-list { background: var(--cream); border-radius: 20px; box-shadow: var(--shadow-soft); overflow: hidden; margin-bottom: 14px; max-height: 240px; overflow-y: auto; }
  .picker-list::-webkit-scrollbar { width: 4px; }
  .picker-list::-webkit-scrollbar-thumb { background: var(--muted-soft); border-radius: 2px; }
  .picker-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border: none; background: transparent; width: 100%; text-align: left; cursor: pointer; font-family: inherit; border-bottom: 1px solid rgba(0,0,0,.04); transition: background 140ms ease; }
  .picker-item:last-child { border-bottom: none; }
  .picker-item:hover { background: var(--coral-bg); }
  .picker-item .avatar { width: 36px; height: 36px; font-size: 13.5px; }
  .picker-item .avatar::after { display: none; }
  .picker-item .name { flex: 1; font-size: 13.5px; font-weight: 600; color: var(--ink); }
  .picker-check { width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--muted-soft); flex-shrink: 0; display: flex; align-items: center; justify-content: center; transition: all 160ms ease; color: transparent; }
  .picker-check svg { width: 12px; height: 12px; opacity: 0; transition: opacity 160ms ease; }
  .picker-item.picked .picker-check { background: var(--coral); border-color: var(--coral); color: #fff; }
  .picker-item.picked .picker-check svg { opacity: 1; }
  .picked-hint { font-size: 11.5px; color: var(--coral-deep); font-weight: 700; }

  /* Empty states (warm) */
  .empty-warm { text-align: center; padding: 30px 22px; }
  .empty-warm .big-circle { width: 68px; height: 68px; border-radius: 50%; background: linear-gradient(135deg, var(--coral-bg), var(--coral-soft)); color: var(--coral-deep); display: flex; align-items: center; justify-content: center; margin: 0 auto 14px; box-shadow: 0 6px 20px rgba(255,122,89,.15); }
  .empty-warm .big-circle svg { width: 28px; height: 28px; }
  .empty-warm h3 { font-size: 16px; font-weight: 800; color: var(--ink); margin-bottom: 6px; }
  .empty-warm p { font-size: 12.5px; color: var(--muted); line-height: 1.55; margin-bottom: 16px; }
  .empty-warm .empty-cta { display: inline-flex; align-items: center; gap: 6px; padding: 10px 16px; border-radius: 999px; background: var(--coral); color: #fff; font-size: 13px; font-weight: 700; border: none; cursor: pointer; font-family: inherit; box-shadow: 0 4px 14px rgba(255,122,89,.32); transition: all 160ms ease; }
  .empty-warm .empty-cta:hover { transform: translateY(-1px); box-shadow: 0 6px 18px rgba(255,122,89,.4); }
  .empty-warm .empty-cta svg { width: 13px; height: 13px; }

  .empty-compact { text-align: center; padding: 18px 14px; background: var(--cream); border-radius: 20px; box-shadow: var(--shadow-soft); }
  .empty-compact .msg { font-size: 13px; font-weight: 600; color: var(--ink-soft); }
  .empty-compact .sub { font-size: 11.5px; color: var(--muted); margin-top: 3px; }

  /* Bottom nav (shared) */
  .bottom-nav { display: flex; background: var(--cream); border-top: 1px solid rgba(0,0,0,.05); padding: 6px 4px 10px; }
  .nav-btn { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 6px 2px; background: transparent; border: none; font-family: inherit; cursor: pointer; color: var(--muted); transition: color 160ms ease; position: relative; }
  .nav-btn svg { width: 18px; height: 18px; }
  .nav-btn .lbl { font-size: 10.5px; font-weight: 600; letter-spacing: .1px; }
  .nav-btn.active { color: var(--coral-deep); }
  .nav-btn .badge { position: absolute; top: 2px; right: calc(50% - 18px); min-width: 16px; height: 16px; border-radius: 999px; background: var(--coral); color: #fff; font-size: 9.5px; font-weight: 800; display: flex; align-items: center; justify-content: center; padding: 0 4px; box-shadow: 0 2px 6px rgba(255,122,89,.4); border: 2px solid var(--cream); }

  /* Group pending state — friendly, not bureaucratic */
  .group-item.pending { opacity: .96; }
  .group-item.pending .group-avatars .mini { filter: grayscale(.35); }
  .group-item.pending .name { color: var(--ink-soft); }
  .group-item.pending .last { margin-top: 5px; padding: 0; background: transparent; color: var(--ink-soft); font-weight: 600; font-size: 11.5px; letter-spacing: 0; text-transform: none; display: inline-flex; align-items: center; gap: 6px; }
  .group-item.pending .pending-pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px 3px 8px; border-radius: 999px; background: var(--coral-bg); color: var(--coral-deep); font-size: 11px; font-weight: 700; letter-spacing: 0; }
  .group-item.pending .pending-pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--coral-deep); animation: pulseDot 1.6s ease-in-out infinite; }
  @keyframes pulseDot { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: .4; transform: scale(.85); } }

  /* Group badge (member count chip on card top row) */
  .group-badge { display: inline-flex; align-items: center; gap: 3px; padding: 2px 7px; border-radius: 999px; background: var(--coral-bg); color: var(--coral-deep); font-size: 10px; font-weight: 800; letter-spacing: .1px; }
  .group-badge svg { width: 9px; height: 9px; }
  .group-item.pending .group-badge { background: var(--sand); color: var(--muted); }

  /* Stepper (used in parent settings for max members) */
  .stepper { display: inline-flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .step-btn { width: 28px; height: 28px; border-radius: 8px; background: var(--coral-bg); color: var(--coral-deep); border: none; cursor: pointer; font-family: inherit; font-size: 16px; font-weight: 800; line-height: 1; display: flex; align-items: center; justify-content: center; transition: background 140ms ease; }
  .step-btn:hover { background: var(--coral-soft); }
  .step-val { min-width: 26px; text-align: center; font-weight: 800; font-size: 14px; color: var(--ink); font-feature-settings: "tnum"; }

  /* Composite mini-avatars used in group request list-items */
  .list-item .mini-stack { position: relative; width: 44px; height: 36px; flex-shrink: 0; }
  .list-item .mini-stack .mini { position: absolute; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 700; border: 2px solid var(--cream); }
  .list-item .mini-stack .mini.a1 { top: 0; left: 0; background: var(--coral-soft); color: var(--coral-deep); z-index: 3; }
  .list-item .mini-stack .mini.a2 { top: 4px; left: 10px; background: var(--sand); color: var(--ink-soft); z-index: 2; }
  .list-item .mini-stack .mini.a3 { top: 10px; left: 20px; background: var(--coral-bg); color: var(--coral-deep); z-index: 1; }

  /* Chat header — tappable peer (group info) */
  .peer.peer-tappable { cursor: pointer; border-radius: 12px; padding: 4px 6px; margin: -4px -6px; transition: background 140ms ease; }
  .peer.peer-tappable:hover { background: var(--coral-bg); }
  header .header-icon.group-menu { flex-shrink: 0; }

  /* Chat header composite avatars (small variant) */
  .group-avatars.sm { width: 42px; height: 34px; flex-shrink: 0; }
  .group-avatars.sm .mini { width: 22px; height: 22px; font-size: 10px; border-width: 2px; }
  .group-avatars.sm .mini.a1 { top: 0; left: 0; }
  .group-avatars.sm .mini.a2 { top: 4px; left: 10px; }
  .group-avatars.sm .mini.a3 { top: 11px; left: 20px; }

  /* Big variant (group info identity card) */
  .group-avatars.big { width: 86px; height: 72px; flex-shrink: 0; margin: 0 auto 12px; }
  .group-avatars.big .mini { width: 46px; height: 46px; font-size: 17px; border-width: 3px; }
  .group-avatars.big .mini.a1 { top: 0; left: 4px; }
  .group-avatars.big .mini.a2 { top: 10px; left: 22px; }
  .group-avatars.big .mini.a3 { top: 22px; left: 38px; }

  /* Chat info bar — privacy chips under header for groups */
  .chat-info-bar { padding: 8px 14px; background: var(--cream); display: flex; gap: 6px; overflow-x: auto; border-bottom: 1px solid rgba(0,0,0,.03); flex-shrink: 0; }
  .chat-info-bar::-webkit-scrollbar { display: none; }
  .info-chip { flex-shrink: 0; padding: 4px 10px; border-radius: 999px; background: var(--coral-bg); color: var(--coral-deep); font-size: 10.5px; font-weight: 700; letter-spacing: .1px; display: inline-flex; align-items: center; gap: 4px; }
  .info-chip svg { width: 10px; height: 10px; }

  /* Sender label above group bubbles */
  .sender { display: flex; align-items: center; gap: 6px; margin: 0 0 4px 10px; }
  .mine .sender { display: none; }
  .sender-dot { width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 9.5px; font-weight: 800; flex-shrink: 0; }
  .sender-name { font-size: 11.5px; font-weight: 700; color: var(--ink-soft); letter-spacing: .1px; }

  /* Group info view */
  .group-identity-card { text-align: center; padding: 22px 18px 18px; background: var(--cream); border-radius: 22px; box-shadow: var(--shadow-soft); margin-bottom: 14px; }
  .gi-name { font-size: 20px; font-weight: 800; color: var(--ink); letter-spacing: -.3px; }
  .gi-sub { font-size: 12.5px; color: var(--muted); margin-top: 4px; }

  .invite-code-card { background: var(--cream); border-radius: 20px; padding: 16px 18px; box-shadow: var(--shadow-soft); margin-bottom: 14px; }
  .invite-code-row { display: flex; align-items: center; gap: 10px; }
  .invite-code-row .code-text { flex: 1; text-align: left; font-size: 18px; font-weight: 800; color: var(--ink); letter-spacing: 1.5px; font-feature-settings: "tnum"; }
  .invite-code-hint { font-size: 11.5px; color: var(--muted); margin-top: 8px; line-height: 1.45; }

  .member-admin-pill { padding: 3px 8px; border-radius: 999px; background: var(--coral-bg); color: var(--coral-deep); font-size: 9.5px; font-weight: 800; letter-spacing: .3px; text-transform: uppercase; }
  .member-self-pill { padding: 3px 8px; border-radius: 999px; background: var(--sand); color: var(--ink-soft); font-size: 9.5px; font-weight: 800; letter-spacing: .3px; text-transform: uppercase; }

  .gi-invite-picker { background: var(--cream); border-radius: 20px; box-shadow: var(--shadow-soft); padding: 14px; margin-bottom: 14px; }
  .gi-invite-picker .picker-list { max-height: 240px; margin-bottom: 10px; }
  .gi-toast { padding: 10px 14px; border-radius: 14px; background: var(--coral); color: #fff; font-size: 12.5px; font-weight: 700; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(255,122,89,.3); animation: popIn 280ms cubic-bezier(.2,1.2,.4,1); }

  /* ============ PITCH / FORSIDE ============ */
  .view-pitch { background: linear-gradient(165deg, var(--cream) 0%, var(--coral-bg) 45%, var(--coral-soft) 100%); }
  .pitch-scroll { flex: 1; overflow-y: auto; padding: 0; }
  .pitch-scroll::-webkit-scrollbar { width: 4px; }
  .pitch-scroll::-webkit-scrollbar-thumb { background: var(--muted-soft); border-radius: 2px; }

  .pitch-hero { text-align: center; padding: 44px 24px 30px; }
  .pitch-logo { width: 68px; height: 68px; border-radius: 22px; background: linear-gradient(135deg, var(--coral), var(--coral-deep)); margin: 0 auto 18px; display: flex; align-items: center; justify-content: center; box-shadow: 0 18px 44px rgba(255,122,89,.38); animation: blink 2.6s ease-in-out infinite; position: relative; }
  .pitch-logo::after { content: ""; width: 20px; height: 20px; border-radius: 50%; background: #fff; }
  .pitch-brand { font-size: 12px; font-weight: 800; color: var(--coral-deep); letter-spacing: 2.4px; text-transform: uppercase; margin-bottom: 14px; }
  .pitch-hero h1 { font-size: 28px; font-weight: 800; color: var(--ink); letter-spacing: -.7px; line-height: 1.15; max-width: 290px; margin: 0 auto 10px; }
  .pitch-hero p { font-size: 13.5px; color: var(--ink-soft); line-height: 1.55; max-width: 300px; margin: 0 auto; }
  .pitch-tag { font-size: 10.5px; color: var(--muted); margin-top: 16px; font-weight: 800; letter-spacing: 1.6px; text-transform: uppercase; }

  .pitch-points { padding: 0 18px; margin-bottom: 24px; }
  .pitch-point { background: var(--cream); border-radius: 20px; padding: 16px 18px; box-shadow: var(--shadow-soft); margin-bottom: 10px; display: flex; align-items: flex-start; gap: 14px; }
  .pitch-point .ic { width: 42px; height: 42px; border-radius: 13px; background: var(--coral-bg); color: var(--coral-deep); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .pitch-point .ic svg { width: 19px; height: 19px; }
  .pitch-point .txt .ttl { font-size: 14.5px; font-weight: 800; color: var(--ink); margin-bottom: 3px; letter-spacing: -.1px; }
  .pitch-point .txt .sub { font-size: 12.5px; color: var(--ink-soft); line-height: 1.5; }

  .pitch-how { padding: 0 18px 24px; }
  .pitch-how .pitch-label { font-size: 10.5px; font-weight: 800; color: var(--muted); letter-spacing: .6px; text-transform: uppercase; padding: 0 4px 10px; }
  .pitch-steps { background: var(--cream); border-radius: 20px; padding: 4px 18px; box-shadow: var(--shadow-soft); }
  .pitch-step { display: flex; gap: 14px; padding: 12px 0; align-items: flex-start; border-bottom: 1px solid rgba(0,0,0,.04); }
  .pitch-step:last-child { border-bottom: none; }
  .pitch-step .step-num { width: 28px; height: 28px; border-radius: 50%; background: var(--coral); color: #fff; font-size: 12.5px; font-weight: 800; display: flex; align-items: center; justify-content: center; flex-shrink: 0; box-shadow: 0 4px 10px rgba(255,122,89,.3); }
  .pitch-step .step-text { font-size: 13px; color: var(--ink); line-height: 1.5; padding-top: 3px; font-weight: 500; }

  .pitch-ctas { padding: 12px 20px 20px; background: rgba(255,248,240,.94); backdrop-filter: blur(12px); border-top: 1px solid rgba(0,0,0,.04); flex-shrink: 0; }
  .pitch-ctas .btn-primary-big { margin-bottom: 10px; }

  /* ============ PARENT INTRO / LANDING ============ */
  .intro-scroll { flex: 1; overflow-y: auto; padding: 4px 18px 18px; }
  .intro-scroll::-webkit-scrollbar { width: 4px; }
  .intro-scroll::-webkit-scrollbar-thumb { background: var(--muted-soft); border-radius: 2px; }

  .intro-hero { text-align: center; padding: 26px 12px 22px; }
  .intro-hero .logo-large { width: 58px; height: 58px; border-radius: 18px; background: linear-gradient(135deg, var(--coral), var(--coral-deep)); margin: 0 auto 18px; display: flex; align-items: center; justify-content: center; box-shadow: 0 12px 32px rgba(255,122,89,.3); animation: blink 2.6s ease-in-out infinite; position: relative; }
  .intro-hero .logo-large::after { content: ""; width: 16px; height: 16px; border-radius: 50%; background: #fff; }
  .intro-hero h1 { font-size: 22px; font-weight: 800; color: var(--ink); letter-spacing: -.5px; line-height: 1.2; margin-bottom: 8px; }
  .intro-hero p { font-size: 13.5px; color: var(--ink-soft); line-height: 1.5; max-width: 300px; margin: 0 auto; }

  .intro-value-card { background: var(--cream); border-radius: 20px; padding: 15px 16px; box-shadow: var(--shadow-soft); display: flex; align-items: flex-start; gap: 14px; margin-bottom: 10px; }
  .intro-value-card .ic { width: 40px; height: 40px; border-radius: 12px; background: var(--coral-bg); color: var(--coral-deep); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .intro-value-card .ic svg { width: 18px; height: 18px; }
  .intro-value-card .txt .ttl { font-size: 14px; font-weight: 800; color: var(--ink); margin-bottom: 3px; letter-spacing: -.1px; }
  .intro-value-card .txt .sub { font-size: 12.5px; color: var(--ink-soft); line-height: 1.5; }

  .intro-safety { background: linear-gradient(135deg, var(--coral-bg), var(--coral-soft)); border-radius: 22px; padding: 18px 20px; margin: 16px 0 14px; }
  .intro-safety h4 { font-size: 12.5px; font-weight: 800; color: var(--coral-deep); margin-bottom: 12px; letter-spacing: .3px; text-transform: uppercase; }
  .intro-safety-list { list-style: none; padding: 0; margin: 0; }
  .intro-safety-list li { display: flex; align-items: flex-start; gap: 10px; padding: 6px 0; font-size: 13px; color: var(--ink); line-height: 1.5; font-weight: 500; }
  .intro-safety-list li svg { width: 16px; height: 16px; color: var(--coral-deep); flex-shrink: 0; margin-top: 3px; }

  .intro-how { background: var(--cream); border-radius: 20px; box-shadow: var(--shadow-soft); margin-bottom: 14px; overflow: hidden; max-height: 0; opacity: 0; padding: 0 18px; transition: max-height 360ms ease, opacity 220ms ease, padding 320ms ease; }
  .intro-how.open { max-height: 520px; opacity: 1; padding: 14px 18px 10px; }
  .intro-how .step { display: flex; gap: 12px; padding: 10px 0; align-items: flex-start; border-bottom: 1px solid rgba(0,0,0,.05); }
  .intro-how .step:last-child { border-bottom: none; }
  .intro-how .step-num { width: 26px; height: 26px; border-radius: 50%; background: var(--coral); color: #fff; font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; flex-shrink: 0; box-shadow: 0 3px 8px rgba(255,122,89,.28); }
  .intro-how .step-text { font-size: 13px; color: var(--ink); line-height: 1.5; padding-top: 3px; }

  .intro-cta-wrap { padding: 12px 18px 18px; background: var(--sand); border-top: 1px solid rgba(0,0,0,.04); flex-shrink: 0; }
  .intro-back-link { display: block; width: 100%; text-align: center; padding: 10px 0 0; color: var(--muted); font-size: 12.5px; font-weight: 600; background: transparent; border: none; cursor: pointer; font-family: inherit; transition: color 140ms ease; }
  .intro-back-link:hover { color: var(--ink-soft); }

  /* ============ PARENT DASHBOARD ============ */
  .parent-header { padding: 14px 16px; display: flex; align-items: center; gap: 10px; background: var(--cream); border-bottom: 1px solid rgba(0,0,0,.03); }
  .parent-header .mode-tag { font-size: 11px; color: var(--coral-deep); background: var(--coral-bg); padding: 4px 10px; border-radius: 999px; font-weight: 700; letter-spacing: .3px; text-transform: uppercase; }
  .parent-header .spacer { flex: 1; }
  .parent-header .close-btn { width: 32px; height: 32px; border-radius: 50%; background: var(--coral-bg); color: var(--coral-deep); border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 160ms ease; }
  .parent-header .close-btn:hover { background: var(--coral-soft); }
  .parent-header .close-btn svg { width: 13px; height: 13px; }

  .parent-body { flex: 1; overflow-y: auto; padding: 14px 14px 16px; }
  .parent-body::-webkit-scrollbar { width: 4px; }
  .parent-body::-webkit-scrollbar-thumb { background: var(--muted-soft); border-radius: 2px; }
  .parent-section { display: none; animation: rowIn 240ms cubic-bezier(.2,.8,.2,1); }
  .parent-section.active { display: block; }

  .section-label { font-size: 10.5px; font-weight: 700; color: var(--muted); letter-spacing: .6px; text-transform: uppercase; padding: 4px 4px 8px; margin-top: 4px; }

  .child-card { padding: 14px; background: var(--cream); border-radius: 20px; box-shadow: var(--shadow-soft); display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
  .child-card .avatar { width: 48px; height: 48px; font-size: 17px; }
  .child-card .avatar::after { display: none; }
  .child-card .who { flex: 1; min-width: 0; }
  .child-card .who .name { font-size: 15.5px; font-weight: 700; }
  .child-card .who .sub { font-size: 11.5px; color: var(--muted); margin-top: 2px; }
  .safety-pill { padding: 5px 10px; border-radius: 999px; background: var(--coral-bg); color: var(--coral-deep); font-size: 10.5px; font-weight: 800; letter-spacing: .3px; text-transform: uppercase; }

  .stat-row { display: flex; gap: 10px; margin-bottom: 12px; }
  .stat { flex: 1; background: var(--cream); border-radius: 18px; padding: 12px 14px; box-shadow: var(--shadow-soft); }
  .stat .num { font-size: 22px; font-weight: 800; color: var(--ink); line-height: 1.1; letter-spacing: -.5px; }
  .stat .lbl { font-size: 11px; color: var(--muted); margin-top: 3px; font-weight: 600; }

  .pending-summary { display: flex; align-items: center; gap: 12px; padding: 14px; background: linear-gradient(135deg, var(--coral-bg), var(--coral-soft)); border-radius: 20px; margin-bottom: 12px; cursor: pointer; transition: transform 160ms ease, box-shadow 180ms ease; border: none; width: 100%; text-align: left; font-family: inherit; }
  .pending-summary:hover { transform: translateY(-1px); box-shadow: var(--shadow-float); }
  .pending-summary .count { width: 38px; height: 38px; border-radius: 50%; background: var(--coral); color: #fff; font-weight: 800; font-size: 15px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; box-shadow: 0 3px 10px rgba(255,122,89,.3); }
  .pending-summary .txt { flex: 1; }
  .pending-summary .ttl { font-size: 13.5px; font-weight: 700; color: var(--ink); }
  .pending-summary .sub { font-size: 11.5px; color: var(--ink-soft); margin-top: 1px; }
  .pending-summary .arrow { color: var(--coral-deep); }
  .pending-summary .arrow svg { width: 14px; height: 14px; }

  .q-actions { display: flex; flex-direction: column; background: var(--cream); border-radius: 20px; overflow: hidden; box-shadow: var(--shadow-soft); margin-bottom: 12px; }
  .q-action { display: flex; align-items: center; gap: 12px; padding: 13px 14px; cursor: pointer; border: none; background: transparent; width: 100%; text-align: left; font-family: inherit; font-size: 13.5px; color: var(--ink); font-weight: 600; transition: background 140ms ease; border-bottom: 1px solid rgba(0,0,0,.04); }
  .q-action:last-child { border-bottom: none; }
  .q-action:hover { background: var(--coral-bg); }
  .q-action .ic { width: 32px; height: 32px; border-radius: 10px; background: var(--coral-bg); color: var(--coral-deep); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .q-action .ic svg { width: 15px; height: 15px; }
  .q-action .lbl { flex: 1; }
  .q-action .arr { color: var(--muted); display: flex; }
  .q-action .arr svg { width: 13px; height: 13px; }

  .list { background: var(--cream); border-radius: 20px; box-shadow: var(--shadow-soft); overflow: hidden; margin-bottom: 12px; }
  .list-item { display: flex; align-items: center; gap: 12px; padding: 11px 14px; border-bottom: 1px solid rgba(0,0,0,.04); }
  .list-item:last-child { border-bottom: none; }
  .list-item .avatar { width: 40px; height: 40px; font-size: 14.5px; }
  .list-item .avatar::after { display: none; }
  .list-item .who { flex: 1; min-width: 0; }
  .list-item .who .name { font-size: 14px; font-weight: 600; color: var(--ink); }
  .list-item .who .sub { font-size: 11px; color: var(--muted); margin-top: 2px; display: flex; align-items: center; gap: 4px; }
  .list-item .who .sub svg { width: 10px; height: 10px; }
  .list-item .actions { display: flex; gap: 6px; align-items: center; }

  .btn-sm { padding: 7px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; cursor: pointer; border: 1px solid transparent; font-family: inherit; transition: all 160ms ease; }
  .btn-approve { background: var(--coral); color: #fff; border-color: var(--coral); box-shadow: 0 3px 10px rgba(255,122,89,.28); }
  .btn-approve:hover { transform: translateY(-1px); box-shadow: 0 5px 14px rgba(255,122,89,.36); }
  .btn-decline { background: transparent; color: var(--ink-soft); border-color: var(--muted-soft); }
  .btn-decline:hover { background: var(--sand); border-color: var(--muted); }
  .btn-ghost { background: transparent; color: var(--muted); border: none; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 140ms ease; }
  .btn-ghost:hover { background: var(--coral-bg); color: var(--coral-deep); }
  .btn-ghost svg { width: 15px; height: 15px; }

  .empty { text-align: center; padding: 22px 14px; }
  .empty .circle { width: 44px; height: 44px; border-radius: 50%; background: var(--coral-bg); color: var(--coral-deep); display: flex; align-items: center; justify-content: center; margin: 0 auto 10px; }
  .empty .circle svg { width: 18px; height: 18px; }
  .empty .msg { font-size: 13px; font-weight: 600; color: var(--ink-soft); }
  .empty .sub { font-size: 11.5px; margin-top: 3px; color: var(--muted); }

  .toggle-row { display: flex; align-items: center; gap: 12px; padding: 13px 14px; border-bottom: 1px solid rgba(0,0,0,.04); cursor: pointer; background: transparent; border-left: none; border-right: none; border-top: none; width: 100%; text-align: left; font-family: inherit; }
  .toggle-row:last-child { border-bottom: none; }
  .toggle-row .txt { flex: 1; }
  .toggle-row .ttl { font-size: 13.5px; font-weight: 600; color: var(--ink); }
  .toggle-row .desc { font-size: 11.5px; color: var(--muted); margin-top: 2px; line-height: 1.4; }
  .toggle { width: 40px; height: 24px; border-radius: 999px; background: var(--muted-soft); position: relative; flex-shrink: 0; transition: background 200ms ease; }
  .toggle::after { content: ""; position: absolute; top: 2px; left: 2px; width: 20px; height: 20px; border-radius: 50%; background: #fff; box-shadow: 0 2px 6px rgba(0,0,0,.15); transition: transform 220ms cubic-bezier(.2,.8,.2,1); }
  .toggle.on { background: var(--coral); }
  .toggle.on::after { transform: translateX(16px); }

  .safety-info { background: linear-gradient(135deg, var(--coral-bg), var(--coral-soft)); border-radius: 20px; padding: 14px 16px; margin-bottom: 12px; }
  .safety-info h4 { font-size: 13px; font-weight: 800; color: var(--coral-deep); margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
  .safety-info h4 svg { width: 13px; height: 13px; }
  .safety-info ul { margin: 0; padding-left: 0; list-style: none; }
  .safety-info li { font-size: 12px; color: var(--ink-soft); line-height: 1.7; padding-left: 16px; position: relative; }
  .safety-info li::before { content: ""; position: absolute; left: 3px; top: 9px; width: 5px; height: 5px; border-radius: 50%; background: var(--coral-deep); }
  /* ============ ONBOARDING (Sprint 7B) ============ */
  .view-onboarding .add-header { position: relative; }
  .onb-step-pill { font-size: 11px; font-weight: 700; letter-spacing: .3px; color: var(--muted); background: var(--cream); padding: 4px 10px; border-radius: 999px; }

  .onb-section-label { font-size: 10.5px; font-weight: 700; color: var(--muted); letter-spacing: .5px; text-transform: uppercase; padding: 12px 2px 8px; }

  /* Preview card — calm, profile-like */
  .onb-preview-card { display: flex; flex-direction: column; align-items: center; padding: 18px 16px; margin-bottom: 18px; }
  .onb-preview-avatar { width: 88px; height: 88px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 34px; line-height: 1; letter-spacing: -0.5px; background: var(--coral-bg); color: var(--coral-deep); transition: background 180ms ease, color 180ms ease; box-shadow: 0 6px 18px rgba(0,0,0,.06); }
  .onb-preview-name { margin-top: 10px; font-size: 14px; color: var(--ink); font-weight: 600; letter-spacing: .1px; }

  /* Mark grid — more modern, less toy-like */
  .onb-avatar-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 8px; }
  .onb-avatar-btn { aspect-ratio: 1; border-radius: 14px; background: transparent; border: 1px solid var(--muted-soft); cursor: pointer; font-size: 19px; line-height: 1; display: flex; align-items: center; justify-content: center; color: var(--ink-soft); transition: all 140ms ease; padding: 0; font-family: inherit; font-weight: 500; }
  .onb-avatar-btn:hover { border-color: var(--ink-soft); color: var(--ink); }
  .onb-avatar-btn.picked { border: 1.5px solid var(--ink); color: var(--ink); background: var(--cream); }

  /* Color dots — small, elegant, evenly spaced */
  .onb-color-row { display: flex; gap: 10px; justify-content: flex-start; padding: 2px 4px; margin-bottom: 16px; }
  .onb-color-btn { width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid rgba(0,0,0,.06); cursor: pointer; padding: 0; transition: transform 140ms ease, box-shadow 140ms ease; flex-shrink: 0; }
  .onb-color-btn:hover { transform: scale(1.08); }
  .onb-color-btn.picked { box-shadow: 0 0 0 2px var(--surface-alt, #FFFAF3), 0 0 0 3.5px var(--ink); }

  .onb-consent { display: flex; align-items: flex-start; gap: 12px; padding: 14px 16px; background: var(--cream); border-radius: 18px; cursor: pointer; margin-bottom: 14px; box-shadow: var(--shadow-soft); }
  .onb-consent input[type=checkbox] { appearance: none; -webkit-appearance: none; width: 22px; height: 22px; border-radius: 6px; border: 2px solid var(--muted-soft); flex-shrink: 0; margin-top: 1px; cursor: pointer; display: grid; place-items: center; transition: all 140ms ease; }
  .onb-consent input[type=checkbox]:checked { background: var(--coral); border-color: var(--coral); }
  .onb-consent input[type=checkbox]:checked::after { content: "✓"; color: #fff; font-size: 14px; font-weight: 800; line-height: 1; }
  .onb-consent span { font-size: 13px; line-height: 1.5; color: var(--ink); }

  .onb-blink-code { font-size: 20px; font-weight: 800; letter-spacing: 2px; color: var(--coral-deep); background: var(--coral-bg); padding: 10px 14px; border-radius: 14px; text-align: center; margin-top: 8px; font-feature-settings: "tnum"; }

  /* Dev-only indicator that shows the OTP for local testing */
  .onb-dev-info { background: #FFF8DC; border: 1.5px dashed #C8A75B; border-radius: 16px; padding: 14px 16px; margin-bottom: 14px; }
  .onb-dev-label { font-size: 10px; font-weight: 800; letter-spacing: .5px; color: #7A5A20; margin-bottom: 6px; }
  .onb-dev-otp { font-size: 26px; font-weight: 800; letter-spacing: 4px; color: var(--ink); font-feature-settings: "tnum"; margin-bottom: 6px; }
  .onb-dev-hint { font-size: 11px; color: #7A5A20; line-height: 1.4; }

  /* Dev theme picker — discrete corner control */
  .blink-theme-picker { position: fixed; bottom: 14px; right: 14px; display: flex; gap: 6px; padding: 5px 7px; border-radius: 999px; background: rgba(255,255,255,.86); backdrop-filter: blur(10px); box-shadow: 0 4px 14px rgba(0,0,0,.08); z-index: 999; opacity: .45; transition: opacity 180ms ease; }
  .blink-theme-picker:hover { opacity: 1; }
  .blink-theme-picker button { width: 20px; height: 20px; border-radius: 50%; border: 2px solid rgba(0,0,0,.05); cursor: pointer; padding: 0; transition: transform 140ms ease, border-color 140ms ease; }
  .blink-theme-picker button:hover { transform: scale(1.15); }
  .blink-theme-picker button.active { border-color: var(--ink, #2B2B2B); transform: scale(1.1); }
</style>
<script src="/blink_api_client.js"></script>
</head>
<body>
  <div class="phone">
    <!-- ============ PITCH / FORSIDE ============ -->
    <div class="view view-pitch" id="viewPitch">
      <div class="pitch-scroll">
        <div class="pitch-hero">
          <div class="pitch-logo"></div>
          <div class="pitch-brand">Blink</div>
          <h1>Privat gruppechat for børn</h1>
          <p>Kun godkendte venner. Trygge rammer sat af en voksen.</p>
          <div class="pitch-tag">På iPhone og Android</div>
        </div>

        <div class="pitch-points">
          <div class="pitch-point">
            <div class="ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
            </div>
            <div class="txt">
              <div class="ttl">Ikke offentlig</div>
              <div class="sub">Blink kan ikke findes via søgning. Kun godkendte venner kan skrive med dit barn.</div>
            </div>
          </div>
          <div class="pitch-point">
            <div class="ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16v10H8l-4 4z"/><circle cx="9" cy="11" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="11" r="1.2" fill="currentColor" stroke="none"/><circle cx="15" cy="11" r="1.2" fill="currentColor" stroke="none"/></svg>
            </div>
            <div class="txt">
              <div class="ttl">Gruppechat med venner</div>
              <div class="sub">Privat gruppechat er kernen. Direkte beskeder findes også.</div>
            </div>
          </div>
          <div class="pitch-point">
            <div class="ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/><path d="M9 12l2 2 4-4"/></svg>
            </div>
            <div class="txt">
              <div class="ttl">Forældre styrer rammerne</div>
              <div class="sub">Du godkender nye venner og grupper og sætter tryghedsniveauet.</div>
            </div>
          </div>
        </div>

        <div class="pitch-how">
          <div class="pitch-label">Sådan virker det</div>
          <div class="pitch-steps">
            <div class="pitch-step">
              <div class="step-num">1</div>
              <div class="step-text">Barn får sin personlige Blink-kode og QR.</div>
            </div>
            <div class="pitch-step">
              <div class="step-num">2</div>
              <div class="step-text">Venner og grupper tilføjes kun via kode eller QR.</div>
            </div>
            <div class="pitch-step">
              <div class="step-num">3</div>
              <div class="step-text">Voksen godkender nye venner og grupper.</div>
            </div>
            <div class="pitch-step">
              <div class="step-num">4</div>
              <div class="step-text">Beskeder og billeder forsvinder igen.</div>
            </div>
          </div>
        </div>
      </div>

      <div class="pitch-ctas">
        <button class="btn-primary-big" id="pitchOnboard">Opret barnets Blink</button>
        <button class="btn-secondary-big" id="pitchChild">Prøv barnets oplevelse</button>
        <button class="btn-secondary-big" id="pitchParent" style="margin-top:8px">Se forælderens side</button>
      </div>
    </div>

    <!-- ============ ONBOARDING (Sprint 7B) ============ -->
    <div class="view view-onboarding hidden" id="viewOnboarding">
      <header class="add-header">
        <button class="chat-back-btn" id="onbBack" aria-label="Tilbage">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>
        </button>
        <div class="ttl" id="onbTitle">Opret Blink</div>
        <div class="onb-step-pill" id="onbStepPill">1/7</div>
      </header>
      <div class="add-body" id="onbBody">

        <!-- welcome -->
        <section class="add-step active" data-onb-step="welcome">
          <div class="add-intro">
            <h2>Velkommen til Blink</h2>
            <p>Først laver vi din profil. En voksen skal godkende før du er klar.</p>
          </div>
          <button class="btn-primary-big" data-onb-next="profile">Kom i gang</button>
        </section>

        <!-- profile: name + mark + color -->
        <section class="add-step" data-onb-step="profile">
          <div class="add-intro">
            <h2>Sådan ser du ud i Blink</h2>
          </div>

          <div class="onb-preview-card">
            <div class="onb-preview-avatar" id="onbPreviewAvatar">?</div>
            <div class="onb-preview-name" id="onbPreviewName">Dit navn</div>
          </div>

          <div class="code-entry">
            <label>Dit navn</label>
            <input type="text" id="onbName" class="group-name" maxlength="24" placeholder="Fx Sofie" autocomplete="off">
          </div>

          <div class="onb-section-label">Vælg dit mærke</div>
          <div class="onb-avatar-grid" id="onbAvatarGrid"></div>

          <div class="onb-section-label">Vælg farvetone</div>
          <div class="onb-color-row" id="onbColorRow"></div>

          <button class="btn-primary-big" id="onbSubmitProfile" disabled>Fortsæt</button>
          <button class="btn-secondary-big" data-onb-next="welcome">Tilbage</button>
        </section>

        <!-- findParent -->
        <section class="add-step" data-onb-step="findParent">
          <div class="add-intro">
            <h2>Find en voksen</h2>
            <p>Skriv din voksnes email eller telefonnummer. De får en besked fra Blink.</p>
          </div>
          <div class="code-entry">
            <label>Voksnes email eller telefon</label>
            <input type="text" id="onbContact" maxlength="200" placeholder="mor@example.dk" autocomplete="off">
          </div>
          <button class="btn-primary-big" id="onbSubmitInvite" disabled>Send til voksen</button>
        </section>

        <!-- waiting (child side) -->
        <section class="add-step" data-onb-step="waiting">
          <div class="add-intro">
            <h2>Din voksne skal godkende</h2>
            <p>Når de siger ja, er din Blink klar.</p>
          </div>
          <div class="onb-dev-info" id="onbDevInfo" style="display:none;">
            <div class="onb-dev-label">DEV-TILSTAND — kode til voksen</div>
            <div class="onb-dev-otp" id="onbDevOtp"></div>
            <div class="onb-dev-hint">Denne besked vises kun i dev-mode. I produktion sendes koden via email/SMS.</div>
          </div>
          <button class="btn-primary-big" id="onbAsParent">Jeg er den voksne (fortsæt)</button>
        </section>

        <!-- parent preview -->
        <section class="add-step" data-onb-step="parentPreview">
          <div class="add-intro">
            <h2>Godkend Blink for <span id="onbPrevName">dit barn</span></h2>
            <p>Blink er en privat gruppechat for børn med godkendte rammer.</p>
          </div>
          <div class="found-card">
            <div class="avatar" id="onbPrevAvatar" style="font-size:26px">?</div>
            <div class="name" id="onbPrevName2">...</div>
            <div class="meta"><span id="onbPrevContact"></span></div>
          </div>
          <button class="btn-primary-big" data-onb-next="parentOtp">Fortsæt</button>
          <button class="btn-secondary-big" id="onbDecline">Afvis</button>
        </section>

        <!-- parent OTP -->
        <section class="add-step" data-onb-step="parentOtp">
          <div class="add-intro">
            <h2>Indtast koden</h2>
            <p>Du har modtaget en 6-cifret kode. Indtast den her.</p>
          </div>
          <div class="code-entry">
            <label>Kode</label>
            <input type="text" id="onbOtp" maxlength="6" inputmode="numeric" placeholder="000000" autocomplete="one-time-code">
          </div>
          <button class="btn-primary-big" id="onbSubmitOtp" disabled>Bekræft kode</button>
        </section>

        <!-- parent consent + approve -->
        <section class="add-step" data-onb-step="parentApprove">
          <div class="add-intro">
            <h2>Sidste trin</h2>
            <p>Bekræft at du vil godkende Blink for dit barn.</p>
          </div>
          <div class="safety-info">
            <h4>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
              Hvad Blink er
            </h4>
            <ul>
              <li>Privat gruppechat for børn</li>
              <li>Kun godkendte venner kan skrive med dit barn</li>
              <li>Beskeder og billeder forsvinder igen</li>
              <li>Du styrer rammerne</li>
            </ul>
          </div>
          <label class="onb-consent">
            <input type="checkbox" id="onbConsent">
            <span>Jeg er barnets forælder/værge eller har tilladelse til at godkende Blink for barnet.</span>
          </label>
          <button class="btn-primary-big" id="onbSubmitApprove" disabled>Godkend Blink</button>
        </section>

        <!-- done -->
        <section class="add-step" data-onb-step="done">
          <div class="success-card">
            <div class="check">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
            </div>
            <h3>Din Blink er klar</h3>
            <p>Del din kode med en ven for at tilføje dem:</p>
            <div class="onb-blink-code" id="onbBlinkCode">BLINK-XXXXXX</div>
          </div>
          <button class="btn-primary-big" id="onbGoHome">Start Blink</button>
        </section>

      </div>
    </div>

    <!-- ============ CHILD HOME ============ -->
    <div class="view view-child-home hidden" id="viewChildHome">
      <header class="home-header">
        <div class="brand">
          <div class="brand-mark"></div>
          <h1>Blink</h1>
        </div>
        <span class="hi">Hej Sofie</span>
        <div class="spacer"></div>
        <button class="header-icon pill" id="openParent" title="Skift til forælder">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
          <span>Forælder</span>
        </button>
      </header>

      <div class="home-body" id="homeBody">
        <!-- Groups (primary landing) -->
        <section class="child-section active" data-section="c-groups">
          <div class="group-ctas">
            <button class="group-cta primary" data-open-group-step="create">
              <div class="ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
              </div>
              <div class="txt">
                <div class="ttl">Opret gruppe</div>
                <div class="sub">Med dine venner</div>
              </div>
            </button>
            <button class="group-cta" data-open-group-step="join">
              <div class="ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="12" rx="2"/><path d="M7 11h.01"/><path d="M11 11h.01"/><path d="M15 11h.01"/><path d="M7 15h10"/></svg>
              </div>
              <div class="txt">
                <div class="ttl">Join gruppe</div>
                <div class="sub">Med en gruppekode</div>
              </div>
            </button>
          </div>

          <div class="section-title-row">
            <div class="ttl">Dine grupper<span class="count" id="groupsCount"></span></div>
          </div>
          <div id="groupsList"></div>

          <div class="section-title-row spaced">
            <div class="ttl">Chats med venner</div>
            <button class="btn-add-friend ghost" data-open-add>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
              Tilføj ven
            </button>
          </div>
          <div id="chatsList"></div>
        </section>

        <!-- Friends -->
        <section class="child-section" data-section="c-friends">
          <div class="section-title-row">
            <div class="ttl">Mine venner</div>
            <button class="btn-add-friend" data-open-add>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
              Tilføj ven
            </button>
          </div>
          <div id="friendsArea"></div>
        </section>

        <!-- My code -->
        <section class="child-section" data-section="c-code">
          <div class="section-title-row">
            <div class="ttl">Min Blink-kode</div>
          </div>
          <div class="code-card">
            <div class="greet">Del med en ven</div>
            <div class="who-me">Sofie</div>
            <div class="qr-wrap">
              <svg class="qr-grid" id="qrGrid" viewBox="0 0 25 25" shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg"></svg>
              <div class="qr-logo"></div>
            </div>
            <div class="code-text" id="myCode">BLINK-4821</div>
            <div class="code-label">Min vennekode</div>
          </div>
          <div class="code-foot">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
            <span>Kun godkendte venner kan skrive med dig. Din voksne godkender nye.</span>
          </div>
        </section>
      </div>

      <nav class="bottom-nav" id="childNav">
        <button class="nav-btn active" data-child-tab="c-groups" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M3 19c.7-3 3.2-5 6-5s5.3 2 6 5"/><circle cx="17" cy="7" r="2.5"/><path d="M15 14c1.8 0 3.5 1 4.2 2.5"/></svg>
          <div class="lbl">Grupper</div>
        </button>
        <button class="nav-btn" data-child-tab="c-friends" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="9" r="4"/><path d="M4 21c0-4 3.5-7 8-7s8 3 8 7"/></svg>
          <div class="lbl">Venner</div>
        </button>
        <button class="nav-btn" data-child-tab="c-code" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3"/><path d="M20 14v7"/><path d="M14 20h3"/></svg>
          <div class="lbl">Min kode</div>
        </button>
      </nav>
    </div>

    <!-- ============ CHAT VIEW ============ -->
    <div class="view view-child hidden" id="viewChild">
      <header>
        <button class="chat-back-btn" id="chatBack" aria-label="Tilbage">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>
        </button>
        <div class="peer" id="peerTap">
          <div class="avatar" id="chatAvatar">E</div>
          <div class="group-avatars sm hidden" id="chatGroupAvatars" aria-hidden="true">
            <div class="mini a1" id="chatGA1">?</div>
            <div class="mini a2" id="chatGA2">?</div>
            <div class="mini a3" id="chatGA3">?</div>
          </div>
          <div class="peer-info">
            <div class="name" id="chatName">Emma</div>
            <div class="status" id="chatStatus">online nu</div>
          </div>
        </div>
        <button class="header-icon group-menu hidden" id="groupMenuBtn" title="Gruppeinfo" aria-label="Gruppeinfo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01"/><path d="M11 12h1v4h1"/></svg>
        </button>
      </header>

      <div class="chat-info-bar hidden" id="chatInfoBar">
        <div class="info-chip">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
          Privat gruppe
        </div>
        <div class="info-chip">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
          Godkendte medlemmer
        </div>
        <div class="info-chip">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><path d="M12 10v3l2 1.5"/></svg>
          Beskeder forsvinder
        </div>
      </div>

      <div id="messages"></div>

      <div class="input-area">
        <div class="lifetime-chips">
          <button class="chip" data-mode="10s" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><path d="M12 10v3l2 1.5"/><path d="M9 3h6"/></svg>
            10s
          </button>
          <button class="chip active" data-mode="1m" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><path d="M12 10v3l2 1.5"/><path d="M9 3h6"/></svg>
            1m
          </button>
          <button class="chip" data-mode="photo" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="14" rx="3"/><circle cx="12" cy="13" r="3.5"/><path d="M8 6l1.5-2h5L16 6"/></svg>
            Foto
          </button>
        </div>
        <form id="form">
          <input type="text" id="input" autocomplete="off" placeholder="Skriv...">
          <button class="send" type="submit" aria-label="Send">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M13 5l7 7-7 7"/></svg>
          </button>
        </form>
      </div>
    </div>

    <!-- ============ ADD FRIEND ============ -->
    <div class="view view-add-friend hidden" id="viewAddFriend">
      <header class="add-header">
        <button class="chat-back-btn" id="addBack" aria-label="Tilbage">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>
        </button>
        <div class="ttl" id="addTitle">Tilføj ven</div>
      </header>
      <div class="add-body">
        <section class="add-step active" data-step="choose">
          <div class="add-intro">
            <h2>Tilføj en ven</h2>
            <p>Tilføj kun nogen, du kender. Din voksne skal godkende nye venner.</p>
          </div>
          <button class="add-choice" data-go-step="scan">
            <div class="ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3"/><path d="M20 14v7"/><path d="M14 20h3"/></svg>
            </div>
            <div class="txt">
              <div class="ttl">Scan QR</div>
              <div class="sub">Hold telefonen op foran din vens QR-kode.</div>
            </div>
            <div class="arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
          </button>
          <button class="add-choice" data-go-step="code">
            <div class="ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="12" rx="2"/><path d="M7 11h.01"/><path d="M11 11h.01"/><path d="M15 11h.01"/><path d="M7 15h10"/></svg>
            </div>
            <div class="txt">
              <div class="ttl">Indtast vennekode</div>
              <div class="sub">Skriv din vens Blink-kode, fx BLINK-4821.</div>
            </div>
            <div class="arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
          </button>
        </section>

        <section class="add-step" data-step="scan">
          <div class="scanner">
            <div class="frame">
              <div class="corner tl"></div>
              <div class="corner tr"></div>
              <div class="corner bl"></div>
              <div class="corner br"></div>
            </div>
            <div class="laser"></div>
            <div class="scan-hint" id="scanHint">Søger...</div>
          </div>
          <button class="btn-secondary-big" data-go-step="choose">Annullér</button>
        </section>

        <section class="add-step" data-step="code">
          <div class="code-entry">
            <label>Indtast vennekode</label>
            <input type="text" id="codeInput" maxlength="10" placeholder="BLINK-0000" autocomplete="off">
            <div class="example">Fx BLINK-4821</div>
          </div>
          <button class="btn-primary-big" id="codeSubmit" disabled>Find ven</button>
          <button class="btn-secondary-big" data-go-step="choose">Tilbage</button>
        </section>

        <section class="add-step" data-step="found">
          <div class="add-intro">
            <h2>Ven fundet</h2>
            <p>Vil du sende en venneanmodning?</p>
          </div>
          <div class="found-card" id="foundCard">
            <div class="avatar" id="foundAvatar">L</div>
            <div class="name" id="foundName">Liam</div>
            <div class="meta">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
              <span>Verificeret Blink-ven</span>
            </div>
          </div>
          <button class="btn-primary-big" id="sendRequest">Send venneanmodning</button>
          <button class="btn-secondary-big" data-go-step="choose">Annullér</button>
        </section>

        <section class="add-step" data-step="success">
          <div class="success-card">
            <div class="check">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
            </div>
            <h3 id="successTitle">Anmodning sendt</h3>
            <p id="successSub">Din voksne skal godkende, før I kan skrive sammen.</p>
            <div class="parent-note">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
              <span>Du får besked, når din voksne har svaret.</span>
            </div>
          </div>
          <button class="btn-primary-big" id="successDone">Færdig</button>
        </section>
      </div>
    </div>

    <!-- ============ GROUP ACTION (create / join) ============ -->
    <div class="view view-group-action hidden" id="viewGroupAction">
      <header class="add-header">
        <button class="chat-back-btn" id="groupBack" aria-label="Tilbage">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>
        </button>
        <div class="ttl" id="groupActionTitle">Opret gruppe</div>
      </header>
      <div class="add-body">
        <section class="add-step" data-gstep="create">
          <div class="add-intro">
            <h2>Opret gruppe</h2>
            <p>Giv din gruppe et navn og vælg hvem der skal være med.</p>
          </div>
          <div class="code-entry">
            <label>Navn på gruppen</label>
            <input type="text" id="groupNameInput" class="group-name" placeholder="Fx Skatepark" autocomplete="off" maxlength="30">
          </div>
          <div class="section-title-row">
            <div class="ttl">Vælg venner</div>
            <div class="picked-hint" id="pickedHint"></div>
          </div>
          <div class="picker-list" id="friendPicker"></div>
          <button class="btn-primary-big" id="groupCreateBtn" disabled>Opret gruppe</button>
          <button class="btn-secondary-big" data-close-group>Annullér</button>
        </section>

        <section class="add-step" data-gstep="join">
          <div class="add-intro">
            <h2>Join gruppe</h2>
            <p>Skriv gruppekoden, du har fået af en ven.</p>
          </div>
          <div class="code-entry">
            <label>Gruppekode</label>
            <input type="text" id="groupCodeInput" maxlength="12" placeholder="GRUPPE-0000" autocomplete="off">
            <div class="example">Fx GRUPPE-4821</div>
          </div>
          <button class="btn-primary-big" id="groupJoinBtn" disabled>Find gruppe</button>
          <button class="btn-secondary-big" data-close-group>Annullér</button>
        </section>

        <section class="add-step" data-gstep="found">
          <div class="add-intro">
            <h2>Gruppe fundet</h2>
            <p>Vil du bede om at komme med?</p>
          </div>
          <div class="found-card">
            <div class="avatar group" id="groupFoundAvatar">G</div>
            <div class="name" id="groupFoundName">Skatepark</div>
            <div class="meta">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M3 19c.7-3 3.2-5 6-5s5.3 2 6 5"/><circle cx="17" cy="7" r="2.5"/><path d="M15 14c1.8 0 3.5 1 4.2 2.5"/></svg>
              <span id="groupFoundMeta">6 medlemmer</span>
            </div>
          </div>
          <button class="btn-primary-big" id="groupJoinRequestBtn">Send anmodning</button>
          <button class="btn-secondary-big" data-close-group>Annullér</button>
        </section>

        <section class="add-step" data-gstep="success">
          <div class="success-card">
            <div class="check">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
            </div>
            <h3 id="groupSuccessTitle">Gruppe oprettet</h3>
            <p id="groupSuccessSub">Nu kan I skrive sammen.</p>
            <div class="parent-note" id="groupSuccessNote" style="display:none;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
              <span>Du får besked, når din voksne har svaret.</span>
            </div>
          </div>
          <button class="btn-primary-big" id="groupSuccessDone">Færdig</button>
        </section>
      </div>
    </div>

    <!-- ============ GROUP INFO ============ -->
    <div class="view view-group-info hidden" id="viewGroupInfo">
      <header class="add-header">
        <button class="chat-back-btn" id="groupInfoBack" aria-label="Tilbage til gruppechat">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>
        </button>
        <div class="ttl">Gruppeinfo</div>
      </header>
      <div class="add-body" id="groupInfoBody">
        <div class="group-identity-card">
          <div class="group-avatars big" id="giAvatars">
            <div class="mini a1">?</div>
            <div class="mini a2">?</div>
            <div class="mini a3">?</div>
          </div>
          <div class="gi-name" id="giName">Gruppe</div>
          <div class="gi-sub" id="giSub">0 medlemmer</div>
        </div>

        <div class="safety-info">
          <h4>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
            Det her er en privat gruppe
          </h4>
          <ul>
            <li>Kun godkendte venner er med</li>
            <li>Beskeder og billeder forsvinder igen</li>
            <li>I kan invitere flere med en gruppekode</li>
          </ul>
        </div>

        <div class="section-label">Gruppekode</div>
        <div class="invite-code-card">
          <div class="invite-code-row">
            <div class="code-text" id="giCode">GRUPPE-0000</div>
            <button class="btn-sm btn-approve" id="giCopyBtn" type="button">Kopiér</button>
          </div>
          <div class="invite-code-hint">Del koden. Din ven bruger "Join gruppe" for at komme med.</div>
        </div>

        <div class="section-label">Invitér</div>
        <div class="q-actions">
          <button class="q-action" id="giInviteBtn" type="button">
            <div class="ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M3 19c.7-3 3.2-5 6-5s5.3 2 6 5"/><path d="M18 7v6"/><path d="M15 10h6"/></svg>
            </div>
            <div class="lbl">Invitér en ven</div>
            <div class="arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
          </button>
        </div>

        <div class="gi-invite-picker hidden" id="giInvitePicker">
          <div class="section-title-row"><div class="ttl">Vælg en ven</div><div class="picked-hint" id="giInviteHint"></div></div>
          <div class="picker-list" id="giInviteList"></div>
          <button class="btn-secondary-big" id="giInviteCancel" type="button">Annullér</button>
        </div>

        <div class="section-label">Medlemmer</div>
        <div class="list" id="giMembersList"></div>
      </div>
    </div>

    <!-- ============ PARENT INTRO ============ -->
    <div class="view view-parent-intro hidden" id="viewParentIntro">
      <header class="parent-header">
        <div class="brand">
          <div class="brand-mark"></div>
          <h1>Blink</h1>
        </div>
        <span class="mode-tag">Forælder</span>
      </header>

      <div class="intro-scroll">
        <div class="intro-hero">
          <div class="logo-large"></div>
          <h1>Privat gruppechat for børn</h1>
          <p>Kun godkendte venner. Trygge rammer, sat af dig.</p>
        </div>

        <div class="intro-value-card">
          <div class="ic">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
          </div>
          <div class="txt">
            <div class="ttl">Ikke offentlig</div>
            <div class="sub">Blink kan ikke findes via søgning. Dit barn bliver kun kontaktet af godkendte venner.</div>
          </div>
        </div>

        <div class="intro-value-card">
          <div class="ic">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M3 19c.7-3 3.2-5 6-5s5.3 2 6 5"/><circle cx="17" cy="7" r="2.5"/><path d="M15 14c1.8 0 3.5 1 4.2 2.5"/></svg>
          </div>
          <div class="txt">
            <div class="ttl">Du godkender</div>
            <div class="sub">Nye venner og grupper kræver din godkendelse, før dit barn kan skrive med dem.</div>
          </div>
        </div>

        <div class="intro-value-card">
          <div class="ic">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><path d="M12 10v3l2 1.5"/></svg>
          </div>
          <div class="txt">
            <div class="ttl">Beskeder forsvinder</div>
            <div class="sub">Beskeder og billeder forsvinder igen. Chatten er let og midlertidig, ikke et digitalt arkiv.</div>
          </div>
        </div>

        <div class="intro-safety">
          <h4>Sådan beskytter Blink dit barn</h4>
          <ul class="intro-safety-list">
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
              Ingen offentlig søgning eller profiler
            </li>
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
              Venner tilføjes kun via QR eller kode
            </li>
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
              Du styrer grupper, venner og rammer
            </li>
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
              Nem blokering og rapportering
            </li>
          </ul>
        </div>

        <div class="intro-how" id="introHow">
          <div class="step"><div class="step-num">1</div><div class="step-text">Dit barn får en personlig Blink-kode og deler den kun fysisk med venner.</div></div>
          <div class="step"><div class="step-num">2</div><div class="step-text">Venner tilføjes via QR eller kode — der er ingen søgning eller tilfældige kontakter.</div></div>
          <div class="step"><div class="step-num">3</div><div class="step-text">Du godkender nye venner og grupper, før de bliver aktive.</div></div>
          <div class="step"><div class="step-num">4</div><div class="step-text">Beskeder og billeder forsvinder igen. Du kan altid justere rammerne.</div></div>
        </div>
      </div>

      <div class="intro-cta-wrap">
        <button class="btn-primary-big" id="introAccept">Godkend Blink</button>
        <button class="btn-secondary-big" id="introHowToggle">Se hvordan det virker</button>
        <button class="intro-back-link" id="introBack">Tilbage</button>
      </div>
    </div>

    <!-- ============ PARENT VIEW ============ -->
    <div class="view view-parent hidden" id="viewParent">
      <header class="parent-header">
        <div class="brand">
          <div class="brand-mark"></div>
          <h1>Blink</h1>
        </div>
        <span class="mode-tag">Forælder</span>
        <div class="spacer"></div>
        <button class="close-btn" id="closeParent" aria-label="Tilbage til Blink">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12"/><path d="M18 6L6 18"/></svg>
        </button>
      </header>

      <div class="parent-body" id="parentBody">
        <section class="parent-section active" data-section="p-home">
          <div class="child-card">
            <div class="avatar">S</div>
            <div class="who">
              <div class="name">Sofie</div>
              <div class="sub">Konto aktiv</div>
            </div>
            <div class="safety-pill">Balanceret</div>
          </div>

          <div class="stat-row">
            <div class="stat"><div class="num" id="statFriends">0</div><div class="lbl">Venner</div></div>
            <div class="stat"><div class="num" id="statGroups">0</div><div class="lbl">Grupper</div></div>
          </div>

          <button class="pending-summary" id="pendingSummary">
            <div class="count" id="pendingCount">0</div>
            <div class="txt">
              <div class="ttl" id="pendingTtl">Nye anmodninger</div>
              <div class="sub" id="pendingSub">Godkend eller afvis</div>
            </div>
            <div class="arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
          </button>

          <div class="q-actions">
            <button class="q-action" data-goto="p-friends">
              <div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M3 19c.7-3 3.2-5 6-5s5.3 2 6 5"/><circle cx="17" cy="7" r="2.5"/><path d="M15 14c1.8 0 3.5 1 4.2 2.5"/></svg></div>
              <div class="lbl">Venner</div>
              <div class="arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
            </button>
            <button class="q-action" data-goto="p-settings">
              <div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg></div>
              <div class="lbl">Indstillinger</div>
              <div class="arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
            </button>
            <button class="q-action" data-goto="p-safety">
              <div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg></div>
              <div class="lbl">Sikkerhed</div>
              <div class="arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
            </button>
          </div>
        </section>

        <section class="parent-section" data-section="p-requests">
          <div id="friendReqSection">
            <div class="section-label">Venneanmodninger</div>
            <div class="list" id="requestsList"></div>
          </div>
          <div id="groupReqSection" style="display:none;">
            <div class="section-label">Gruppeanmodninger</div>
            <div class="list" id="groupRequestsList"></div>
          </div>
        </section>

        <section class="parent-section" data-section="p-friends">
          <div class="section-label">Sofies venner</div>
          <div class="list" id="parentFriendsList"></div>
        </section>

        <section class="parent-section" data-section="p-settings">
          <div class="section-label">Kontakt &amp; relationer</div>
          <div class="list" id="settingsList"></div>
          <div class="section-label">Grupper</div>
          <div class="list" id="groupSettingsList"></div>
          <div class="section-label">Maks gruppestørrelse</div>
          <div class="list" id="maxMembersList"></div>
          <div class="section-label">Pause</div>
          <div class="list" id="pauseList"></div>
        </section>

        <section class="parent-section" data-section="p-safety">
          <div class="safety-info">
            <h4><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg> Sådan beskytter Blink Sofie</h4>
            <ul>
              <li>Sofie kan ikke findes offentligt</li>
              <li>Kun godkendte venner kan skrive med hende</li>
              <li>Nye venner kræver din godkendelse</li>
              <li>Beskeder og billeder forsvinder igen</li>
            </ul>
          </div>
          <div class="section-label">Blokerede brugere</div>
          <div class="list" id="blockedList"></div>
          <div class="section-label">Rapporter</div>
          <div class="list" id="reportsList"></div>
          <div class="section-label">Hjælp</div>
          <div class="q-actions">
            <button class="q-action">
              <div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 0 1 5 0c0 1.5-2.5 2-2.5 3.5"/><path d="M12 17h.01"/></svg></div>
              <div class="lbl">Hjælpecenter</div>
              <div class="arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
            </button>
            <button class="q-action">
              <div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16v10H7l-3 3z"/></svg></div>
              <div class="lbl">Kontakt support</div>
              <div class="arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
            </button>
          </div>
        </section>
      </div>

      <nav class="bottom-nav" id="parentNav">
        <button class="nav-btn active" data-tab="p-home" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/></svg>
          <div class="lbl">Hjem</div>
        </button>
        <button class="nav-btn" data-tab="p-requests" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 11a4 4 0 1 0-4-4"/><path d="M2 20c0-3 2.5-5 6-5s6 2 6 5"/><path d="M19 8v6"/><path d="M16 11h6"/></svg>
          <div class="lbl">Anmod.</div>
          <span class="badge" id="navBadge">0</span>
        </button>
        <button class="nav-btn" data-tab="p-friends" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M3 19c.7-3 3.2-5 6-5s5.3 2 6 5"/><circle cx="17" cy="7" r="2.5"/><path d="M15 14c1.8 0 3.5 1 4.2 2.5"/></svg>
          <div class="lbl">Venner</div>
        </button>
        <button class="nav-btn" data-tab="p-settings" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>
          <div class="lbl">Indst.</div>
        </button>
        <button class="nav-btn" data-tab="p-safety" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/></svg>
          <div class="lbl">Sikker.</div>
        </button>
      </nav>
    </div>

    <div class="overlay" id="overlay">
      <div class="overlay-bar"><div class="overlay-bar-fill" id="overlayBarFill"></div></div>
      <button class="overlay-close" id="overlayClose" aria-label="Luk">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12"/><path d="M18 6L6 18"/></svg>
      </button>
      <div class="overlay-img"></div>
      <div class="overlay-meta">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><path d="M12 10v3l2 1.5"/></svg>
        <span id="overlayText">Forsvinder efter visning</span>
      </div>
    </div>
  </div>

<script>
/* ============ THEME FOUNDATION (Sprint 7A) ============
 * Central theme config. Flip the primary palette by calling applyTheme(name).
 * Existing CSS uses --coral / --coral-deep / --coral-soft / --coral-bg / --sand / --cream
 * as its tokens. applyTheme() overrides those variables at runtime so no
 * stylesheet rewrite is needed.
 */
// Canonical Blink palette is "Warm Signal" — keyed as 'coral' for backwards
// compatibility with anything that still reads localStorage['blink-theme'].
// The other themes remain available for dev-only experimentation via the
// gated picker (see DEV_THEME_PICKER below).
const BLINK_THEMES = {
  coral: {
    label: 'Warm Signal',
    primary: '#FF6B4A', primaryDark: '#D94D33',
    primarySoft: '#FFE1D8', primaryBg: '#FFF2EC',
    surface: '#EFE6DA', surfaceAlt: '#FFFDF8',
    pageBg: '#F7F1E8',
  },
  blue: {
    label: 'Blå (dev)',
    primary: '#4A8BF0', primaryDark: '#2E6DD4',
    primarySoft: '#D8E4F7', primaryBg: '#EEF1F7',
    surface: '#F3F2EF', surfaceAlt: '#FBF9F5',
    pageBg: '#E6E6E0',
  },
  green: {
    label: 'Grøn (dev)',
    primary: '#4CAD77', primaryDark: '#2E8A55',
    primarySoft: '#D4EFDE', primaryBg: '#EDF7F1',
    surface: '#F0F6F2', surfaceAlt: '#FAFCFB',
    pageBg: '#E4EDE7',
  },
  purple: {
    label: 'Lilla (dev)',
    primary: '#8C5CD4', primaryDark: '#6A3DBF',
    primarySoft: '#E1D4F5', primaryBg: '#F3ECFC',
    surface: '#F4F0FA', surfaceAlt: '#FCFAFF',
    pageBg: '#E8E1F1',
  },
};

function applyTheme(name) {
  const t = BLINK_THEMES[name];
  if (!t) return;
  const root = document.documentElement;
  // The existing CSS names its vars --coral*; we map theme tokens onto them
  // so nothing breaks visually when the palette changes.
  root.style.setProperty('--coral',      t.primary);
  root.style.setProperty('--coral-deep', t.primaryDark);
  root.style.setProperty('--coral-soft', t.primarySoft);
  root.style.setProperty('--coral-bg',   t.primaryBg);
  root.style.setProperty('--sand',       t.surface);
  root.style.setProperty('--cream',      t.surfaceAlt);
  // page background lives on body in CSS; set it directly.
  document.body.style.background = t.pageBg;
  try { localStorage.setItem('blink-theme', name); } catch (e) { /* private mode */ }
  // Sync the picker's visual active state.
  document.querySelectorAll('.blink-theme-picker button').forEach(b =>
    b.classList.toggle('active', b.dataset.theme === name)
  );
}

// Apply saved theme early so there's no flash of wrong color.
(function () {
  let saved = 'coral';
  try { saved = localStorage.getItem('blink-theme') || 'coral'; } catch (e) {}
  // Wait for body to exist (the script is below the DOM at the time of parse
  // but defensively rAF anyway).
  if (document.body) applyTheme(saved);
  else document.addEventListener('DOMContentLoaded', () => applyTheme(saved));
})();

/* ============ VIEW NAVIGATION ============ */
const VIEWS = ['viewPitch', 'viewOnboarding', 'viewChildHome', 'viewChild', 'viewAddFriend', 'viewGroupAction', 'viewGroupInfo', 'viewParentIntro', 'viewParent'];
function showView(id) {
  VIEWS.forEach(v => {
    const el = document.getElementById(v);
    if (!el) return;
    el.classList.toggle('hidden', v !== id);
  });
}

/* ============ CHAT (CHILD) LOGIC ============ */
const LIFE = { '10s': 10000, '1m': 60000 };
const PHOTO_VIEW_MS = 4000;
let lifetimeMode = '1m';
let nextId = 100;
let chatPeer = { name: 'Emma', initial: 'E', group: false };
let currentGroup = null;

// Sender avatar palettes — kept distinct so users can tell initials apart,
// but retuned to sit inside the Warm Signal palette (same lightness range,
// warm undertone, primary coral leads the cycle).
const SENDER_PALETTES = [
  { bg: '#FFE1D8', fg: '#D94D33' },  // coral (primary)
  { bg: '#DCE7FF', fg: '#2E5FD4' },  // accent blue
  { bg: '#DDEFE3', fg: '#3B8A5F' },  // mint
  { bg: '#FFE3E8', fg: '#C2496D' },  // rose
  { bg: '#E8DFF7', fg: '#6A3DBF' },  // lavender
  { bg: '#FFF0D1', fg: '#A6761B' },  // amber
];
function senderPaletteFor(name) {
  let h = 0;
  const s = name || '?';
  for (let i = 0; i < s.length; i++) h = ((h * 31) + s.charCodeAt(i)) | 0;
  return SENDER_PALETTES[Math.abs(h) % SENDER_PALETTES.length];
}

const messages = [];

const BOT_REPLIES = [
  'Lyder godt 💛',
  'Haha okay 😄',
  'Ses snart!',
  'Nice 🌟',
  'Helt enig',
  'Jeg glæder mig!',
  'Cool 😎',
  'Okay! 👍',
];

const messagesEl = document.getElementById('messages');
const form = document.getElementById('form');
const inputEl = document.getElementById('input');
const sendBtn = document.querySelector('button.send');
const chips = document.querySelectorAll('.chip');
const overlay = document.getElementById('overlay');
const overlayBarFill = document.getElementById('overlayBarFill');
const overlayClose = document.getElementById('overlayClose');

chips.forEach(chip => {
  chip.addEventListener('click', () => {
    const mode = chip.dataset.mode;
    if (mode === 'photo') { sendPhoto(); return; }
    lifetimeMode = mode;
    chips.forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
  });
});

function render() {
  messagesEl.innerHTML = '';
  messages.forEach(m => messagesEl.appendChild(renderMsg(m)));
  requestAnimationFrame(() => { messagesEl.scrollTop = messagesEl.scrollHeight; });
}

function renderMsg(m) {
  const row = document.createElement('div');
  row.className = 'row ' + m.who;
  row.dataset.id = m.id;

  const showSender = chatPeer.group && m.who === 'theirs' && m.sender;

  if (m.kind === 'photo') {
    if (m.state === 'opened') {
      const chip = document.createElement('div');
      chip.className = 'photo-opened';
      chip.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7h3l1.5-2h5L16 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z"/><circle cx="12" cy="13" r="3.5"/></svg><span>Åbnet</span>`;
      row.appendChild(chip);
      return row;
    }
    if (showSender) row.appendChild(senderLabel(m));
    row.appendChild(photoCard(m));
    if (m.who === 'mine') {
      const meta = document.createElement('div');
      meta.className = 'meta';
      meta.innerHTML = `<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12l5 5L20 6"/></svg><span>Sendt i gruppen</span>`;
      row.appendChild(meta);
    }
    return row;
  }

  if (showSender) row.appendChild(senderLabel(m));

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = m.text;
  row.appendChild(bubble);

  if (m.state === 'seen') {
    row.appendChild(progressBar(m));
  }

  row.appendChild(metaLine(m));
  return row;
}

function senderLabel(m) {
  const wrap = document.createElement('div');
  wrap.className = 'sender';
  const p = senderPaletteFor(m.sender);
  const init = (m.senderInitial || m.sender[0] || '?').toUpperCase();
  wrap.innerHTML = `<div class="sender-dot" style="background:${p.bg};color:${p.fg}">${init}</div><span class="sender-name">${m.sender}</span>`;
  return wrap;
}

function progressBar(m) {
  const bar = document.createElement('div');
  bar.className = 'progress';
  const fill = document.createElement('div');
  fill.className = 'progress-fill running';
  const elapsed = Date.now() - m.seenAt;
  fill.style.setProperty('--lifetime', m.lifetime + 'ms');
  fill.style.setProperty('--lifetime-delay', `-${elapsed}ms`);
  bar.appendChild(fill);
  return bar;
}

function metaLine(m) {
  const meta = document.createElement('div');
  meta.className = 'meta';
  if (m.state === 'sent') {
    meta.innerHTML = `<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12l5 5L20 6"/></svg><span>Sendt</span>`;
  } else if (m.state === 'seen') {
    meta.innerHTML = `<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l4 4L14 9"/><path d="M10 12l4 4L21 9"/></svg><span>Set</span>`;
  }
  return meta;
}

function photoCard(m) {
  const card = document.createElement('div');
  card.className = 'photo-card';
  const clickable = m.who === 'theirs' && m.state === 'unopened';
  if (clickable) card.classList.add('clickable');

  const thumb = document.createElement('div');
  thumb.className = 'photo-thumb ' + (clickable ? 'unopened' : 'preview');
  thumb.innerHTML = `
    <div class="photo-badge">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><path d="M12 10v3l2 1.5"/></svg>
      <span>Engang</span>
    </div>
    ${clickable ? '<div class="blink-ico"><div class="core"></div></div><div class="photo-cta">Tryk for at åbne</div>' : ''}
  `;
  card.appendChild(thumb);

  if (clickable) card.addEventListener('click', () => openPhoto(m));
  return card;
}

function markSeen(id) {
  const m = messages.find(x => x.id === id);
  if (!m || m.state !== 'sent') return;
  m.state = 'seen';
  m.seenAt = Date.now();
  render();
  setTimeout(() => markGone(id), m.lifetime);
}

function markGone(id) {
  const m = messages.find(x => x.id === id);
  if (!m) return;
  if (m.kind === 'photo' && m.state === 'unopened') {
    markOpened(id);
    return;
  }
  fadeAndRemove(id);
}

function markOpened(id) {
  const m = messages.find(x => x.id === id);
  if (!m || m.state === 'opened') return;
  m.state = 'opened';
  render();
  setTimeout(() => fadeAndRemove(id), 3500);
}

function fadeAndRemove(id) {
  const row = messagesEl.querySelector(`[data-id="${id}"]`);
  const finalize = () => {
    const i = messages.findIndex(x => x.id === id);
    if (i >= 0) messages.splice(i, 1);
    render();
  };
  if (row) {
    row.querySelectorAll('.bubble, .photo-card, .photo-opened, .progress, .meta')
      .forEach(el => el.classList.add('gone-anim'));
    setTimeout(finalize, 380);
  } else {
    finalize();
  }
}

function openPhoto(m) {
  overlay.classList.add('open');
  overlayBarFill.style.animation = 'none';
  void overlayBarFill.offsetWidth;
  overlayBarFill.style.animation = `drain ${PHOTO_VIEW_MS}ms linear forwards`;

  let closed = false;
  const finish = () => {
    if (closed) return; closed = true;
    overlay.classList.remove('open');
    markOpened(m.id);
  };
  const timer = setTimeout(finish, PHOTO_VIEW_MS);
  overlayClose.onclick = () => { clearTimeout(timer); finish(); };
}

function sendPhoto() {
  sendBtn.classList.remove('pulse'); void sendBtn.offsetWidth; sendBtn.classList.add('pulse');
  const m = { id: nextId++, who: 'mine', kind: 'photo', state: 'unopened' };
  messages.push(m);
  render();
  setTimeout(() => markOpened(m.id), 4200);
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = '';
  sendBtn.classList.remove('pulse'); void sendBtn.offsetWidth; sendBtn.classList.add('pulse');

  // --- Sprint 6B: backend path (group chats only) ---
  if (typeof USE_BACKEND !== 'undefined' && USE_BACKEND
      && chatPeer.group && currentGroup && currentGroup.id) {
    try {
      const res = await sendTextBackend(currentGroup.id, text);
      // Append the backend-confirmed message to local state.
      messages.push(mapBackendMessageToUi(res));
      render();
    } catch (err) {
      // Put the text back so the user can retry.
      inputEl.value = text;
      showBackendError('Send besked', err);
    }
    return;
  }

  const m = { id: nextId++, who: 'mine', kind: 'text', state: 'sent', text, lifetime: LIFE[lifetimeMode] };
  messages.push(m);
  render();
  setTimeout(() => markSeen(m.id), 1500);

  setTimeout(() => {
    const reply = { id: nextId++, who: 'theirs', kind: 'text', state: 'sent', text: BOT_REPLIES[Math.floor(Math.random()*BOT_REPLIES.length)], lifetime: LIFE[lifetimeMode] };
    if (chatPeer.group && currentGroup && currentGroup.memberList) {
      const others = currentGroup.memberList.filter(x => !x.self);
      if (others.length) {
        const pick = others[Math.floor(Math.random() * others.length)];
        reply.sender = pick.name;
        reply.senderInitial = pick.initial;
      }
    }
    messages.push(reply);
    render();
    setTimeout(() => markSeen(reply.id), 1200);
  }, 2400);
});

function openChatWith(name, initial, seed, opts) {
  opts = opts || {};
  const isGroup = !!opts.group;
  chatPeer = { name, initial, group: isGroup };
  currentGroup = isGroup && opts.groupData ? opts.groupData : null;

  document.getElementById('chatName').textContent = name;

  const singleAv = document.getElementById('chatAvatar');
  const compAv = document.getElementById('chatGroupAvatars');
  if (isGroup) {
    singleAv.classList.add('hidden');
    compAv.classList.remove('hidden');
    const mi = (currentGroup && currentGroup.memberInitials) || [];
    document.getElementById('chatGA1').textContent = mi[0] || '?';
    document.getElementById('chatGA2').textContent = mi[1] || '?';
    document.getElementById('chatGA3').textContent = mi[2] || '?';
  } else {
    singleAv.classList.remove('hidden');
    singleAv.textContent = initial;
    singleAv.classList.remove('group');
    compAv.classList.add('hidden');
  }

  document.getElementById('chatStatus').textContent = isGroup ? `${opts.members} medlemmer` : 'online nu';
  inputEl.placeholder = isGroup ? `Skriv i ${name}...` : `Skriv til ${name}...`;

  document.getElementById('chatInfoBar').classList.toggle('hidden', !isGroup);
  document.getElementById('groupMenuBtn').classList.toggle('hidden', !isGroup);
  document.getElementById('peerTap').classList.toggle('peer-tappable', isGroup);

  messages.length = 0;
  if (seed) {
    const seedText = (typeof seed === 'string') ? seed : seed.text;
    const sender = (typeof seed === 'object' && seed.sender) ? seed.sender : null;
    const senderInitial = (typeof seed === 'object' && seed.senderInitial) ? seed.senderInitial : null;
    if (seedText) {
      const m = { id: nextId++, who: 'theirs', kind: 'text', state: 'seen', text: seedText, lifetime: 60000, seenAt: Date.now() - 5000, sender, senderInitial };
      messages.push(m);
      setTimeout(() => markGone(m.id), 55000);
    }
  }
  render();
  showView('viewChild');

  // --- Sprint 6B: backend path. Load real messages for group chats.
  // Non-blocking — chat view is already visible with seed (if any).
  if (typeof USE_BACKEND !== 'undefined' && USE_BACKEND && isGroup && currentGroup && currentGroup.id) {
    loadMessagesIntoChat(currentGroup.id);
  }
}

document.getElementById('chatBack').addEventListener('click', () => {
  showView('viewChildHome');
  goChildTab('c-groups');
});

/* ============ GROUP INFO VIEW ============ */
function openGroupInfo() {
  if (!currentGroup) return;
  renderGroupInfo();
  showView('viewGroupInfo');
}

document.getElementById('peerTap').addEventListener('click', () => {
  if (chatPeer.group) openGroupInfo();
});
document.getElementById('groupMenuBtn').addEventListener('click', openGroupInfo);
document.getElementById('groupInfoBack').addEventListener('click', () => {
  hideInvitePicker();
  showView('viewChild');
});

function renderGroupInfo() {
  const g = currentGroup;
  if (!g) return;

  const mi = g.memberInitials || [];
  document.querySelector('#giAvatars .a1').textContent = mi[0] || '?';
  document.querySelector('#giAvatars .a2').textContent = mi[1] || '?';
  document.querySelector('#giAvatars .a3').textContent = mi[2] || '?';
  document.getElementById('giName').textContent = g.name;
  document.getElementById('giSub').textContent = `${g.members} medlemmer · Oprettet af ${g.createdBy || 'ukendt'}`;
  document.getElementById('giCode').textContent = g.code || 'GRUPPE-0000';

  const list = document.getElementById('giMembersList');
  list.innerHTML = '';
  const members = g.memberList || [];
  members.forEach(m => {
    const el = document.createElement('div');
    el.className = 'list-item';
    const pill = m.admin
      ? '<span class="member-admin-pill">Admin</span>'
      : (m.self ? '<span class="member-self-pill">Dig</span>' : '');
    const p = senderPaletteFor(m.name);
    el.innerHTML = `
      <div class="avatar" style="background:${p.bg};color:${p.fg}">${m.initial}</div>
      <div class="who">
        <div class="name">${m.name}${m.self ? ' (dig)' : ''}</div>
        ${m.admin ? '<div class="sub">Oprettede gruppen</div>' : '<div class="sub">Godkendt medlem</div>'}
      </div>
      <div class="actions">${pill}</div>`;
    list.appendChild(el);
  });

  hideInvitePicker();
  const toast = document.getElementById('giToast');
  if (toast) toast.remove();
}

document.getElementById('giCopyBtn').addEventListener('click', () => {
  const code = document.getElementById('giCode').textContent;
  if (navigator.clipboard) navigator.clipboard.writeText(code).catch(() => {});
  showGiToast('Kode kopieret — del den med din ven');
});

function showGiToast(text) {
  const body = document.getElementById('groupInfoBody');
  let toast = document.getElementById('giToast');
  if (toast) toast.remove();
  toast = document.createElement('div');
  toast.id = 'giToast';
  toast.className = 'gi-toast';
  toast.textContent = text;
  body.insertBefore(toast, body.firstChild);
  setTimeout(() => { if (toast) toast.remove(); }, 3000);
}

document.getElementById('giInviteBtn').addEventListener('click', () => {
  if (!currentGroup) return;
  renderInvitePicker();
  const picker = document.getElementById('giInvitePicker');
  picker.classList.remove('hidden');
  setTimeout(() => picker.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 60);
});
document.getElementById('giInviteCancel').addEventListener('click', hideInvitePicker);

function hideInvitePicker() {
  const p = document.getElementById('giInvitePicker');
  if (p) p.classList.add('hidden');
}

function renderInvitePicker() {
  const g = currentGroup;
  const list = document.getElementById('giInviteList');
  list.innerHTML = '';
  const inGroup = new Set((g.memberList || []).map(m => m.name));
  const eligible = friends.filter(f => !inGroup.has(f.name));
  if (eligible.length === 0) {
    list.innerHTML = `<div class="empty-compact"><div class="msg">Alle dine venner er allerede med</div><div class="sub">Del gruppekoden ovenfor for at invitere nye.</div></div>`;
    document.getElementById('giInviteHint').textContent = '';
    return;
  }
  document.getElementById('giInviteHint').textContent = `${eligible.length} kan inviteres`;
  eligible.forEach(f => {
    const row = document.createElement('button');
    row.className = 'picker-item';
    row.type = 'button';
    row.innerHTML = `
      <div class="avatar">${f.initial}</div>
      <div class="name">${f.name}</div>
      <div class="picker-check"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg></div>
    `;
    const check = row.querySelector('.picker-check svg');
    if (check) check.style.opacity = '1';
    row.addEventListener('click', () => inviteFriendToGroup(g, f));
    list.appendChild(row);
  });
}

function inviteFriendToGroup(group, friend) {
  if (group.memberList && group.memberList.some(m => m.name === friend.name)) return;

  if (groupSettingOn('require_invite_approval')) {
    pendingRequests.push({
      id: 'ginv-' + Date.now(),
      kind: 'group-invite',
      groupId: group.id,
      groupName: group.name,
      name: group.name,
      initial: group.initial,
      members: group.members,
      memberInitials: group.memberInitials,
      friendName: friend.name,
      friendInitial: friend.initial,
    });
    updateHomeStats();
    renderRequests();
    hideInvitePicker();
    showGiToast(`Invitation til ${friend.name} afventer godkendelse`);
  } else {
    addFriendToGroup(group, friend);
    renderGroups();
    renderGroupInfo();
    showGiToast(`${friend.name} er nu med i gruppen`);
  }
}

function addFriendToGroup(group, friend) {
  group.members = (group.members || 0) + 1;
  if (group.memberInitials) group.memberInitials.push(friend.initial);
  if (group.memberList) group.memberList.push({ name: friend.name, initial: friend.initial });
}

/* ============ CHILD HOME DATA ============ */
const chats = [
  { id: 'c1', peer: 'Emma',  initial: 'E', last: 'Skal vi i parken senere? 🌳', time: 'nu',     unread: 0, online: true, seed: 'Skal vi i parken senere? 🌳' },
  { id: 'c2', peer: 'Noah',  initial: 'N', last: 'Haha okay 😄',                time: '14 min', unread: 1, online: true, seed: 'Haha okay 😄' },
  { id: 'c4', peer: 'Ida',   initial: 'I', last: 'Et billede forsvandt',        time: '3 t',    unread: 0, blink: true,  seed: '' },
  { id: 'c5', peer: 'Oscar', initial: 'O', last: 'Blink!',                      time: 'i går',  unread: 0, blink: true,  seed: 'Blink!' },
];

const groups = [
  {
    id: 'g1', name: 'Gyngerne', initial: 'G', members: 5,
    memberInitials: ['E','M','N','I','O'],
    memberList: [
      { name: 'Sofie',    initial: 'S', self: true },
      { name: 'Mathilde', initial: 'M', admin: true },
      { name: 'Emma',     initial: 'E' },
      { name: 'Noah',     initial: 'N' },
      { name: 'Ida',      initial: 'I' },
    ],
    createdBy: 'Mathilde',
    code: 'GRUPPE-1247',
    last: 'Mathilde: ses i morgen!', time: '1 t', unread: 2,
    seed: { text: 'Ses i morgen! 🌟', sender: 'Mathilde', senderInitial: 'M' },
  },
  {
    id: 'g2', name: 'Fødselsdag', initial: '🎂', members: 6,
    memberInitials: ['E','N','A','M','F'],
    memberList: [
      { name: 'Sofie',    initial: 'S', self: true, admin: true },
      { name: 'Emma',     initial: 'E' },
      { name: 'Noah',     initial: 'N' },
      { name: 'Asta',     initial: 'A' },
      { name: 'Mathilde', initial: 'M' },
      { name: 'Frederik', initial: 'F' },
    ],
    createdBy: 'Sofie',
    code: 'GRUPPE-8832',
    last: 'Oscar: hvilken farve kage?', time: '3 t', unread: 1,
    seed: { text: 'Hvilken farve kage? 🎂', sender: 'Oscar', senderInitial: 'O' },
  },
  {
    id: 'g3', name: 'Klassen 4.B', initial: 'K', members: 12,
    memberInitials: ['I','N','A','M'],
    memberList: [
      { name: 'Sofie',    initial: 'S', self: true },
      { name: 'Ida',      initial: 'I', admin: true },
      { name: 'Noah',     initial: 'N' },
      { name: 'Asta',     initial: 'A' },
      { name: 'Mathilde', initial: 'M' },
    ],
    createdBy: 'Ida',
    code: 'GRUPPE-4491',
    last: 'Ida: husk idrætstøj!', time: 'i går', unread: 0,
    seed: { text: 'Husk idrætstøj!', sender: 'Ida', senderInitial: 'I' },
  },
];

const friends = [
  { name: 'Emma',     initial: 'E' },
  { name: 'Noah',     initial: 'N' },
  { name: 'Ida',      initial: 'I' },
  { name: 'Oscar',    initial: 'O' },
  { name: 'Mathilde', initial: 'M' },
  { name: 'Mikkel',   initial: 'M' },
  { name: 'Asta',     initial: 'A' },
  { name: 'Frederik', initial: 'F' },
];

/* ============ GROUPS RENDERING ============ */
function renderGroups() {
  const list = document.getElementById('groupsList');
  const countEl = document.getElementById('groupsCount');
  list.innerHTML = '';
  if (countEl) countEl.textContent = groups.length ? String(groups.length) : '';
  if (groups.length === 0) {
    list.innerHTML = `
      <div class="empty-warm">
        <div class="big-circle">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M3 19c.7-3 3.2-5 6-5s5.3 2 6 5"/><circle cx="17" cy="7" r="2.5"/><path d="M15 14c1.8 0 3.5 1 4.2 2.5"/></svg>
        </div>
        <h3>Ingen grupper endnu</h3>
        <p>Lav en gruppe med dine venner, eller join en med en gruppekode.</p>
        <button class="empty-cta" data-open-group-step="create">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
          Opret gruppe
        </button>
      </div>`;
    wireGroupCtas();
    return;
  }
  const wrap = document.createElement('div');
  wrap.className = 'group-list';
  const peopleIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3"/><path d="M3 18c.7-2.5 3-4 6-4s5.3 1.5 6 4"/><circle cx="17" cy="7" r="2.2"/></svg>`;
  // Split "Who: message" so we can warm up the sender's name.
  const formatLast = (raw) => {
    if (!raw) return '';
    const m = String(raw).match(/^([^:]{1,20}):\s*(.+)$/);
    if (!m) return raw;
    return `<span class="who">${m[1]}</span> ${m[2]}`;
  };
  groups.forEach(g => {
    const row = document.createElement('button');
    const isPending = g.status === 'pending';
    row.className = 'group-item' + (isPending ? ' pending' : '');
    row.type = 'button';
    const mi = g.memberInitials || [];
    const extra = Math.max(0, (g.members || mi.length) - 3);
    const moreChip = extra > 0 ? `<div class="more">+${extra}</div>` : '';
    const avatars = `
      <div class="group-avatars">
        <div class="mini a1">${mi[0] || '?'}</div>
        <div class="mini a2">${mi[1] || '?'}</div>
        <div class="mini a3">${mi[2] || '?'}</div>
        ${moreChip}
      </div>`;
    const hasActivity = !isPending && g.unread > 0;
    const liveDot = hasActivity ? '<span class="live-dot" aria-hidden="true"></span>' : '';
    const timeText = isPending ? '' : g.time;
    const timeHtml = timeText ? `<div class="time">${timeText}</div>` : '';
    const lastHtml = isPending
      ? `<div class="last"><span class="pending-pill">Venter på voksen</span></div>`
      : `<div class="last">${formatLast(g.last)}</div>`;
    row.innerHTML = `
      ${avatars}
      <div class="chat-meta">
        <div class="top">
          <div class="name">${g.name}</div>
          ${liveDot}
          <div class="group-badge">${peopleIcon}${g.members}</div>
          ${timeHtml}
        </div>
        ${lastHtml}
      </div>
      ${(!isPending && g.unread) ? `<div class="unread">${g.unread}</div>` : ''}
    `;
    row.addEventListener('click', () => {
      if (isPending) {
        alert('Gruppen venter på, at din voksne siger ja.');
        return;
      }
      g.unread = 0;
      renderGroups();
      openChatWith(g.name, g.initial, g.seed, { group: true, members: g.members, groupData: g });
    });
    wrap.appendChild(row);
  });
  list.appendChild(wrap);
}

/* ============ DIRECT CHATS RENDERING ============ */
function renderChats() {
  const list = document.getElementById('chatsList');
  list.innerHTML = '';
  if (chats.length === 0) {
    list.innerHTML = `
      <div class="empty-compact">
        <div class="msg">Ingen venner endnu</div>
        <div class="sub">Tilføj en ven for at starte en 1:1-chat.</div>
      </div>`;
    return;
  }
  const wrap = document.createElement('div');
  wrap.className = 'chat-list compact';
  chats.forEach(c => {
    const row = document.createElement('button');
    row.className = 'chat-item';
    row.type = 'button';
    const avClass = 'avatar' + (c.online ? ' online' : '');
    const lastClass = c.blink ? 'last blink-active' : 'last';
    const blinkIc = c.blink ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><path d="M12 10v3l2 1.5"/></svg>` : '';
    row.innerHTML = `
      <div class="${avClass}">${c.initial}</div>
      <div class="chat-meta">
        <div class="top">
          <div class="name">${c.peer}</div>
          <div class="time">${c.time}</div>
        </div>
        <div class="${lastClass}">${blinkIc}<span>${c.last}</span></div>
      </div>
      ${c.unread ? `<div class="unread">${c.unread}</div>` : ''}
    `;
    row.addEventListener('click', () => {
      c.unread = 0;
      renderChats();
      openChatWith(c.peer, c.initial, c.seed);
    });
    wrap.appendChild(row);
  });
  list.appendChild(wrap);
}

function renderFriendsGrid() {
  const area = document.getElementById('friendsArea');
  area.innerHTML = '';
  if (friends.length === 0) {
    area.innerHTML = `
      <div class="empty-warm">
        <div class="big-circle">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="9" r="4"/><path d="M4 21c0-4 3.5-7 8-7s8 3 8 7"/></svg>
        </div>
        <h3>Ingen venner endnu</h3>
        <p>Del din Blink-kode eller scan din vens QR for at blive venner.</p>
        <button class="empty-cta" data-open-add>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
          Tilføj ven
        </button>
      </div>`;
    wireAddButtons();
    return;
  }
  const grid = document.createElement('div');
  grid.className = 'friends-grid';
  friends.forEach(f => {
    const tile = document.createElement('button');
    tile.className = 'friend-tile';
    tile.type = 'button';
    tile.innerHTML = `<div class="avatar">${f.initial}</div><div class="name">${f.name}</div>`;
    tile.addEventListener('click', () => openChatWith(f.name, f.initial, ''));
    grid.appendChild(tile);
  });
  area.appendChild(grid);
}

/* ============ QR CODE (fake for mock) ============ */
function renderQR() {
  const svg = document.getElementById('qrGrid');
  if (!svg) return;
  svg.innerHTML = '';
  const size = 25;
  const on = (x, y) => {
    const finder = (fx, fy) => {
      if (fx < 0 || fy < 0 || fx > 6 || fy > 6) return null;
      const outer = (fx === 0 || fx === 6 || fy === 0 || fy === 6);
      const inner = (fx >= 2 && fx <= 4 && fy >= 2 && fy <= 4);
      return outer || inner;
    };
    let f = finder(x, y); if (f !== null) return f;
    f = finder(x - (size - 7), y); if (f !== null) return f;
    f = finder(x, y - (size - 7)); if (f !== null) return f;
    if (y === 6 && x >= 7 && x < size - 7) return x % 2 === 0;
    if (x === 6 && y >= 7 && y < size - 7) return y % 2 === 0;
    const cx = size / 2, cy = size / 2;
    if (Math.abs(x - cx) < 3 && Math.abs(y - cy) < 3) return false;
    return ((x * 17 + y * 31 + x * y + 7) % 3) === 0;
  };
  const parts = [];
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if (on(x, y)) parts.push(`<rect x="${x}" y="${y}" width="1" height="1"/>`);
    }
  }
  svg.innerHTML = parts.join('');
}

/* ============ CHILD NAV ============ */
function goChildTab(name) {
  document.querySelectorAll('.child-section').forEach(s => {
    s.classList.toggle('active', s.dataset.section === name);
  });
  document.querySelectorAll('#childNav .nav-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.childTab === name);
  });
  document.getElementById('homeBody').scrollTop = 0;
}
document.querySelectorAll('#childNav .nav-btn').forEach(b => {
  b.addEventListener('click', () => goChildTab(b.dataset.childTab));
});

/* ============ ADD FRIEND FLOW ============ */
let scanTimer = null;
function goAddStep(step) {
  document.querySelectorAll('#viewAddFriend .add-step').forEach(s => {
    s.classList.toggle('active', s.dataset.step === step);
  });
  const titles = { choose: 'Tilføj ven', scan: 'Scan QR', code: 'Indtast kode', found: 'Ven fundet', success: 'Sendt' };
  const t = titles[step]; if (t) document.getElementById('addTitle').textContent = t;
  const body = document.querySelector('#viewAddFriend .add-body'); if (body) body.scrollTop = 0;

  if (scanTimer) { clearTimeout(scanTimer); scanTimer = null; }
  if (step === 'scan') {
    const hint = document.getElementById('scanHint');
    let dots = 0;
    const base = 'Søger';
    const tick = () => { dots = (dots + 1) % 4; hint.textContent = base + '.'.repeat(dots); };
    const interval = setInterval(tick, 400);
    scanTimer = setTimeout(() => {
      clearInterval(interval);
      showFoundUser({ name: 'Sebastian', initial: 'S' });
    }, 2000);
  }
  if (step === 'code') {
    const input = document.getElementById('codeInput');
    input.value = '';
    updateCodeSubmit();
    setTimeout(() => input.focus(), 60);
  }
}

function wireAddButtons() {
  document.querySelectorAll('[data-open-add]').forEach(b => {
    if (b.__wiredAdd) return;
    b.__wiredAdd = true;
    b.addEventListener('click', () => {
      showView('viewAddFriend');
      goAddStep('choose');
    });
  });
}

document.querySelectorAll('#viewAddFriend [data-go-step]').forEach(b => {
  b.addEventListener('click', () => goAddStep(b.dataset.goStep));
});
document.getElementById('addBack').addEventListener('click', () => {
  if (scanTimer) { clearTimeout(scanTimer); scanTimer = null; }
  showView('viewChildHome');
});

const codeInput = document.getElementById('codeInput');
const codeSubmit = document.getElementById('codeSubmit');
function updateCodeSubmit() {
  const v = codeInput.value.replace(/\s/g, '');
  codeSubmit.disabled = !/^BLINK-?\d{4}$/i.test(v);
}
codeInput.addEventListener('input', () => {
  const raw = codeInput.value.toUpperCase();
  if (/^BLINK\d/.test(raw) && !raw.includes('-')) {
    codeInput.value = raw.slice(0, 5) + '-' + raw.slice(5, 9);
  } else {
    codeInput.value = raw;
  }
  updateCodeSubmit();
});
codeSubmit.addEventListener('click', () => {
  const v = codeInput.value.trim().toUpperCase();
  const lookup = { 'BLINK-4821': { name: 'Liam', initial: 'L' }, 'BLINK-7731': { name: 'Sebastian', initial: 'S' } };
  const hit = lookup[v] || { name: 'Alma', initial: 'A' };
  showFoundUser(hit);
});

function showFoundUser(user) {
  document.getElementById('foundName').textContent = user.name;
  document.getElementById('foundAvatar').textContent = user.initial;
  window.__pendingAdd = user;
  goAddStep('found');
}

document.getElementById('sendRequest').addEventListener('click', () => {
  const u = window.__pendingAdd;
  if (u) {
    pendingRequests.push({ id: 'req-' + Date.now(), name: u.name, initial: u.initial, method: 'QR' });
    updateHomeStats();
  }
  goAddStep('success');
});
document.getElementById('successDone').addEventListener('click', () => {
  showView('viewChildHome');
  goChildTab('c-groups');
});

/* ============ GROUP ACTION FLOW ============ */
const pickedFriends = new Set();
let currentGroupFound = null;

function goGroupStep(step) {
  document.querySelectorAll('#viewGroupAction .add-step').forEach(s => {
    s.classList.toggle('active', s.dataset.gstep === step);
  });
  const titles = { create: 'Opret gruppe', join: 'Join gruppe', found: 'Gruppe fundet', success: 'Færdig' };
  const t = titles[step]; if (t) document.getElementById('groupActionTitle').textContent = t;
  const body = document.querySelector('#viewGroupAction .add-body'); if (body) body.scrollTop = 0;

  if (step === 'create') {
    document.getElementById('groupNameInput').value = '';
    pickedFriends.clear();
    renderFriendPicker();
    updateGroupCreateBtn();
    setTimeout(() => document.getElementById('groupNameInput').focus(), 60);
  }
  if (step === 'join') {
    document.getElementById('groupCodeInput').value = '';
    updateGroupJoinBtn();
    setTimeout(() => document.getElementById('groupCodeInput').focus(), 60);
  }
}

function wireGroupCtas() {
  document.querySelectorAll('[data-open-group-step]').forEach(b => {
    if (b.__wiredGroup) return;
    b.__wiredGroup = true;
    b.addEventListener('click', () => {
      const step = b.dataset.openGroupStep;
      if (step === 'create' && !groupSettingOn('allow_create_groups')) {
        alert('Din voksne har slået "Må oprette grupper" fra.');
        return;
      }
      if (step === 'join' && !groupSettingOn('allow_join_groups')) {
        alert('Din voksne har slået "Må joine grupper" fra.');
        return;
      }
      showView('viewGroupAction');
      goGroupStep(step);
    });
  });
}

document.getElementById('groupBack').addEventListener('click', () => {
  showView('viewChildHome');
  goChildTab('c-groups');
});
document.querySelectorAll('[data-close-group]').forEach(b => {
  b.addEventListener('click', () => {
    showView('viewChildHome');
    goChildTab('c-groups');
  });
});

function renderFriendPicker() {
  const list = document.getElementById('friendPicker');
  list.innerHTML = '';
  if (friends.length === 0) {
    list.innerHTML = `<div class="empty-compact"><div class="msg">Ingen venner endnu</div><div class="sub">Tilføj venner for at oprette en gruppe.</div></div>`;
    return;
  }
  friends.forEach((f, i) => {
    const row = document.createElement('button');
    row.className = 'picker-item' + (pickedFriends.has(i) ? ' picked' : '');
    row.type = 'button';
    row.innerHTML = `
      <div class="avatar">${f.initial}</div>
      <div class="name">${f.name}</div>
      <div class="picker-check"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg></div>
    `;
    row.addEventListener('click', () => {
      if (pickedFriends.has(i)) pickedFriends.delete(i); else pickedFriends.add(i);
      row.classList.toggle('picked');
      updatePickedHint();
      updateGroupCreateBtn();
    });
    list.appendChild(row);
  });
  updatePickedHint();
}

function updatePickedHint() {
  const hint = document.getElementById('pickedHint');
  const n = pickedFriends.size;
  const count = n + 1;
  if (count > maxMembersState.value) {
    hint.textContent = `Maks ${maxMembersState.value}`;
    hint.style.color = 'var(--coral-deep)';
  } else if (n === 0) {
    hint.textContent = '';
    hint.style.color = '';
  } else {
    hint.textContent = (n === 1 ? '1 valgt' : `${n} valgt`);
    hint.style.color = '';
  }
}

function updateGroupCreateBtn() {
  const nameEl = document.getElementById('groupNameInput');
  if (!nameEl) return;
  const name = nameEl.value.trim();
  const count = pickedFriends.size + 1;
  const overMax = count > maxMembersState.value;
  document.getElementById('groupCreateBtn').disabled = !(name && pickedFriends.size >= 1 && !overMax);
}

document.getElementById('groupNameInput').addEventListener('input', updateGroupCreateBtn);

document.getElementById('groupCreateBtn').addEventListener('click', async () => {
  const name = document.getElementById('groupNameInput').value.trim();
  const picked = [...pickedFriends].map(i => friends[i]);
  const memberInitials = ['S', ...picked.map(f => f.initial)];
  const memberCount = picked.length + 1;

  // --- Sprint 6B: backend path ---
  if (typeof USE_BACKEND !== 'undefined' && USE_BACKEND) {
    try {
      const res = await createGroupBackend(name);
      const needsApproval = !!(res && res.pendingApproval);
      const title = document.getElementById('groupSuccessTitle');
      const sub = document.getElementById('groupSuccessSub');
      const note = document.getElementById('groupSuccessNote');
      if (needsApproval) {
        title.textContent = 'Afventer godkendelse';
        sub.textContent = `Din voksne skal godkende ${name}.`;
        note.style.display = 'flex';
      } else {
        title.textContent = 'Gruppen er klar';
        sub.textContent = `${name} er oprettet. Skriv løs!`;
        note.style.display = 'none';
      }
      goGroupStep('success');
    } catch (e) {
      showBackendError('Opret gruppe', e);
    }
    return;
  }

  if (memberCount > maxMembersState.value) {
    alert(`Din voksne har sat grænsen til maks ${maxMembersState.value} medlemmer.`);
    return;
  }

  const needsApproval = groupSettingOn('require_group_approval');
  const gid = 'g-' + Date.now();
  const memberList = [{ name: 'Sofie', initial: 'S', self: true, admin: true }];
  picked.forEach(f => memberList.push({ name: f.name, initial: f.initial }));
  const newGroup = {
    id: gid,
    name,
    initial: name[0].toUpperCase(),
    members: memberCount,
    memberInitials,
    memberList,
    createdBy: 'Sofie',
    code: 'GRUPPE-' + Math.floor(1000 + Math.random() * 9000),
    last: needsApproval ? 'Afventer godkendelse' : 'Du oprettede gruppen',
    time: needsApproval ? '—' : 'nu',
    unread: 0,
    seed: '',
    status: needsApproval ? 'pending' : 'active',
  };
  groups.unshift(newGroup);

  if (needsApproval) {
    pendingRequests.push({
      id: 'greq-' + Date.now(),
      kind: 'group-create',
      groupId: gid,
      groupName: name,
      name,
      initial: newGroup.initial,
      members: memberCount,
      memberInitials,
    });
  }

  renderGroups();
  updateHomeStats();
  renderRequests();

  const title = document.getElementById('groupSuccessTitle');
  const sub = document.getElementById('groupSuccessSub');
  const note = document.getElementById('groupSuccessNote');
  if (needsApproval) {
    title.textContent = 'Afventer godkendelse';
    sub.textContent = `Din voksne skal godkende ${name}.`;
    note.style.display = 'flex';
  } else {
    title.textContent = 'Gruppen er klar';
    sub.textContent = `${name} er oprettet. Skriv løs!`;
    note.style.display = 'none';
  }
  goGroupStep('success');
});

const groupCodeInput = document.getElementById('groupCodeInput');
const groupJoinBtn = document.getElementById('groupJoinBtn');
function updateGroupJoinBtn() {
  const v = groupCodeInput.value.replace(/\s/g, '');
  groupJoinBtn.disabled = !/^GRUPPE-?\d{4}$/i.test(v);
}
groupCodeInput.addEventListener('input', () => {
  const raw = groupCodeInput.value.toUpperCase();
  if (/^GRUPPE\d/.test(raw) && !raw.includes('-')) {
    groupCodeInput.value = raw.slice(0, 6) + '-' + raw.slice(6, 10);
  } else {
    groupCodeInput.value = raw;
  }
  updateGroupJoinBtn();
});
groupJoinBtn.addEventListener('click', () => {
  const v = groupCodeInput.value.trim().toUpperCase();
  const lookup = { 'GRUPPE-4821': { name: 'Skatepark', initial: 'S', members: 6 }, 'GRUPPE-1234': { name: 'Fodbold U10', initial: 'F', members: 9 } };
  currentGroupFound = lookup[v] || { name: 'Strandturen', initial: 'S', members: 7 };
  document.getElementById('groupFoundName').textContent = currentGroupFound.name;
  document.getElementById('groupFoundAvatar').textContent = currentGroupFound.initial;
  document.getElementById('groupFoundMeta').textContent = `${currentGroupFound.members} medlemmer`;
  goGroupStep('found');
});

document.getElementById('groupJoinRequestBtn').addEventListener('click', () => {
  if (!currentGroupFound) return;
  const needsApproval = groupSettingOn('require_invite_approval');

  if (needsApproval) {
    pendingRequests.push({
      id: 'greq-' + Date.now(),
      kind: 'group-join',
      groupName: currentGroupFound.name,
      name: currentGroupFound.name,
      initial: currentGroupFound.initial,
      members: currentGroupFound.members,
      memberInitials: ['?', '?', '?'],
    });
    updateHomeStats();
    renderRequests();
    document.getElementById('groupSuccessTitle').textContent = 'Anmodning sendt';
    document.getElementById('groupSuccessSub').textContent = 'Du får besked, når din voksne har svaret.';
    document.getElementById('groupSuccessNote').style.display = 'flex';
  } else {
    groups.unshift({
      id: 'g-' + Date.now(),
      name: currentGroupFound.name,
      initial: currentGroupFound.initial,
      members: currentGroupFound.members,
      memberInitials: ['S', '?', '?'],
      memberList: [{ name: 'Sofie', initial: 'S', self: true }],
      createdBy: 'ukendt',
      code: 'GRUPPE-' + Math.floor(1000 + Math.random() * 9000),
      last: 'Du kom med i gruppen',
      time: 'nu',
      unread: 0,
      seed: '',
      status: 'active',
    });
    renderGroups();
    updateHomeStats();
    document.getElementById('groupSuccessTitle').textContent = 'Velkommen!';
    document.getElementById('groupSuccessSub').textContent = `Du er nu med i ${currentGroupFound.name}.`;
    document.getElementById('groupSuccessNote').style.display = 'none';
  }
  goGroupStep('success');
});

document.getElementById('groupSuccessDone').addEventListener('click', () => {
  showView('viewChildHome');
  goChildTab('c-groups');
});

/* ============ PARENT/CHILD SWITCH ============ */
let parentHasAccepted = false;
let parentEntryFrom = 'viewChildHome';

function enterParentMode(from) {
  if (from) parentEntryFrom = from;
  if (parentHasAccepted) {
    showView('viewParent');
    goParentTab('p-home');
  } else {
    const how = document.getElementById('introHow');
    const toggle = document.getElementById('introHowToggle');
    if (how) how.classList.remove('open');
    if (toggle) toggle.textContent = 'Se hvordan det virker';
    const scroll = document.querySelector('#viewParentIntro .intro-scroll');
    if (scroll) scroll.scrollTop = 0;
    showView('viewParentIntro');
  }
}

document.getElementById('openParent').addEventListener('click', () => enterParentMode('viewChildHome'));

document.getElementById('pitchChild').addEventListener('click', () => {
  showView('viewChildHome');
  goChildTab('c-groups');
});
document.getElementById('pitchParent').addEventListener('click', () => enterParentMode('viewPitch'));

document.getElementById('closeParent').addEventListener('click', () => {
  showView(parentEntryFrom);
});

document.getElementById('introAccept').addEventListener('click', () => {
  parentHasAccepted = true;
  showView('viewParent');
  goParentTab('p-home');
});
document.getElementById('introBack').addEventListener('click', () => {
  showView(parentEntryFrom);
});
document.getElementById('introHowToggle').addEventListener('click', () => {
  const how = document.getElementById('introHow');
  const btn = document.getElementById('introHowToggle');
  const opening = !how.classList.contains('open');
  how.classList.toggle('open');
  btn.textContent = opening ? 'Skjul' : 'Se hvordan det virker';
  if (opening) {
    setTimeout(() => how.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 100);
  }
});

/* ============ PARENT DASHBOARD LOGIC ============ */
function goParentTab(name) {
  document.querySelectorAll('.parent-section').forEach(s => {
    s.classList.toggle('active', s.dataset.section === name);
  });
  document.querySelectorAll('#parentNav .nav-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === name);
  });
  const body = document.getElementById('parentBody');
  if (body) body.scrollTop = 0;
}
document.querySelectorAll('#parentNav .nav-btn').forEach(b => {
  b.addEventListener('click', () => goParentTab(b.dataset.tab));
});
document.querySelectorAll('[data-goto]').forEach(b => {
  b.addEventListener('click', () => goParentTab(b.dataset.goto));
});
document.getElementById('pendingSummary').addEventListener('click', () => goParentTab('p-requests'));

const pendingRequests = [
  { id: 'r1', kind: 'friend', name: 'Liam', initial: 'L', method: 'QR' },
  { id: 'r2', kind: 'friend', name: 'Alma', initial: 'A', method: 'code' },
];
const blocked = [
  { name: 'Ukendt profil', initial: '?', note: 'Blokeret 12. apr' },
];
const reports = [];
const settings = [
  { key: 'approve_friends',      ttl: 'Nye venner kræver godkendelse', desc: 'Du godkender, før Sofie kan skrive med nye venner.', on: true },
  { key: 'groups',               ttl: 'Gruppechat tilladt',            desc: 'Sofie kan være med i grupper med godkendte venner.', on: true },
  { key: 'photos',               ttl: 'Fotos tilladt',                 desc: 'Sofie kan sende og modtage billeder, der forsvinder.', on: true },
  { key: 'contact_only_friends', ttl: 'Kun venner kan kontakte',       desc: 'Fremmede kan ikke skrive til Sofie.', on: true },
];
const pauseSetting = { key: 'pause', ttl: 'Pause nye venner', desc: 'Sofie kan ikke tilføje nye venner, mens pause er slået til.', on: false };

const groupSettings = [
  { key: 'allow_create_groups',     ttl: 'Må oprette grupper',               desc: 'Sofie kan oprette grupper med sine venner.', on: true },
  { key: 'require_group_approval',  ttl: 'Nye grupper kræver godkendelse',   desc: 'Du godkender grupper, Sofie selv opretter.', on: true },
  { key: 'allow_join_groups',       ttl: 'Må joine grupper',                 desc: 'Sofie kan joine grupper med en gruppekode.', on: true },
  { key: 'require_invite_approval', ttl: 'Gruppeinvites kræver godkendelse', desc: 'Du godkender nye grupper, Sofie vil være med i.', on: true },
];
const maxMembersState = { value: 20 };

function groupSettingOn(key) {
  const s = groupSettings.find(x => x.key === key);
  return s ? s.on : true;
}

function iconQR() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3"/><path d="M20 14v7"/><path d="M14 20h3"/></svg>`;
}
function iconKey() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="15" r="4"/><path d="M11 13l9-9"/><path d="M17 7l3 3"/></svg>`;
}
function iconGroupSm() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M3 19c.7-3 3.2-5 6-5s5.3 2 6 5"/><circle cx="17" cy="7" r="2.5"/></svg>`;
}
function iconDot() { return `<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="12" cy="12" r="3"/></svg>`; }
function iconMore() { return `<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg>`; }
function iconLock() { return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>`; }
function iconShield() { return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z"/><path d="M9 12l2 2 4-4"/></svg>`; }

function renderRequests() {
  const friendList = document.getElementById('requestsList');
  const groupList = document.getElementById('groupRequestsList');
  const groupSection = document.getElementById('groupReqSection');

  const friendReqs = pendingRequests.filter(r => r.kind === 'friend' || (!r.kind && r.method !== 'group'));
  const groupReqs = pendingRequests.filter(r => r.kind === 'group-create' || r.kind === 'group-join' || r.kind === 'group-invite');

  friendList.innerHTML = '';
  if (friendReqs.length === 0) {
    friendList.innerHTML = `
      <div class="empty">
        <div class="circle">${iconShield()}</div>
        <div class="msg">Ingen ventende anmodninger</div>
        <div class="sub">Du får besked, når Sofie vil tilføje en ny ven.</div>
      </div>`;
  } else {
    friendReqs.forEach(r => {
      const el = document.createElement('div');
      el.className = 'list-item';
      const methodText = r.method === 'QR' ? 'Tilføjet via QR' : 'Tilføjet via vennekode';
      const methodIcon = r.method === 'QR' ? iconQR() : iconKey();
      el.innerHTML = `
        <div class="avatar">${r.initial}</div>
        <div class="who">
          <div class="name">${r.name}</div>
          <div class="sub">${methodIcon}<span>${methodText}</span></div>
        </div>
        <div class="actions">
          <button class="btn-sm btn-decline" data-id="${r.id}" data-action="decline">Afvis</button>
          <button class="btn-sm btn-approve" data-id="${r.id}" data-action="approve">Godkend</button>
        </div>`;
      friendList.appendChild(el);
    });
  }

  if (groupReqs.length === 0) {
    groupSection.style.display = 'none';
  } else {
    groupSection.style.display = 'block';
    groupList.innerHTML = '';
    groupReqs.forEach(r => {
      const el = document.createElement('div');
      el.className = 'list-item';
      let kindLabel, subText, titleText;
      if (r.kind === 'group-create') {
        kindLabel = 'Vil oprette gruppe';
        subText = `${kindLabel} · ${r.members || '?'} medlemmer`;
        titleText = r.groupName || r.name;
      } else if (r.kind === 'group-invite') {
        kindLabel = 'Vil invitere ny ven';
        subText = `${r.friendName} → ${r.groupName}`;
        titleText = r.friendName || 'Ny ven';
      } else {
        kindLabel = 'Vil joine gruppe';
        subText = `${kindLabel} · ${r.members || '?'} medlemmer`;
        titleText = r.groupName || r.name;
      }
      const mi = r.memberInitials || ['?', '?', '?'];
      el.innerHTML = `
        <div class="mini-stack">
          <div class="mini a1">${mi[0] || '?'}</div>
          <div class="mini a2">${mi[1] || '?'}</div>
          <div class="mini a3">${mi[2] || '?'}</div>
        </div>
        <div class="who">
          <div class="name">${titleText}</div>
          <div class="sub">${iconGroupSm()}<span>${subText}</span></div>
        </div>
        <div class="actions">
          <button class="btn-sm btn-decline" data-id="${r.id}" data-action="decline">Afvis</button>
          <button class="btn-sm btn-approve" data-id="${r.id}" data-action="approve">Godkend</button>
        </div>`;
      groupList.appendChild(el);
    });
  }

  document.querySelectorAll('#requestsList button[data-action], #groupRequestsList button[data-action]').forEach(b => {
    b.addEventListener('click', async () => {
      const id = b.dataset.id;
      const action = b.dataset.action;
      const idx = pendingRequests.findIndex(r => r.id === id);
      if (idx < 0) return;
      const req = pendingRequests[idx];

      // --- Sprint 6B: backend path ---
      if (typeof USE_BACKEND !== 'undefined' && USE_BACKEND) {
        try {
          const isFriend = req.kind === 'friend' || !req.kind;
          if (isFriend) {
            if (action === 'approve') await approveFriendRequestBackend(id);
            else await declineFriendRequestBackend(id);
          } else {
            if (action === 'approve') await approveGroupRequestBackend(id);
            else await declineGroupRequestBackend(id);
          }
          showBackendOk(action === 'approve' ? 'Godkendt' : 'Afvist');
        } catch (e) {
          showBackendError(action === 'approve' ? 'Godkend' : 'Afvis', e);
        }
        return;
      }

      pendingRequests.splice(idx, 1);

      if (action === 'approve') {
        if (req.kind === 'friend' || !req.kind) {
          friends.unshift({ name: req.name, initial: req.initial });
        } else if (req.kind === 'group-create') {
          const g = groups.find(x => x.id === req.groupId);
          if (g) { g.status = 'active'; g.time = 'nu'; g.last = 'Gruppen er godkendt'; }
        } else if (req.kind === 'group-join') {
          groups.unshift({
            id: 'g-' + Date.now(),
            name: req.groupName || req.name,
            initial: (req.groupName || req.name)[0].toUpperCase(),
            members: req.members || 1,
            memberInitials: req.memberInitials && req.memberInitials.length ? req.memberInitials : ['S', '?', '?'],
            memberList: [{ name: 'Sofie', initial: 'S', self: true }],
            createdBy: 'ukendt',
            code: 'GRUPPE-' + Math.floor(1000 + Math.random() * 9000),
            last: 'Du kom med i gruppen',
            time: 'nu',
            unread: 0,
            seed: '',
            status: 'active',
          });
        } else if (req.kind === 'group-invite') {
          const g = groups.find(x => x.id === req.groupId);
          if (g) addFriendToGroup(g, { name: req.friendName, initial: req.friendInitial });
        }
      } else if (action === 'decline') {
        if (req.kind === 'group-create') {
          const gi = groups.findIndex(x => x.id === req.groupId);
          if (gi >= 0) groups.splice(gi, 1);
        }
      }

      renderParent();
      renderChildHome();
    });
  });
}

function renderParentFriends() {
  const list = document.getElementById('parentFriendsList');
  list.innerHTML = '';
  if (friends.length === 0) {
    list.innerHTML = `
      <div class="empty">
        <div class="circle">${iconLock()}</div>
        <div class="msg">Ingen venner endnu</div>
        <div class="sub">Sofies konto er privat, indtil hun tilføjer nogen.</div>
      </div>`;
    return;
  }
  friends.forEach((f, i) => {
    const el = document.createElement('div');
    el.className = 'list-item';
    el.innerHTML = `
      <div class="avatar">${f.initial}</div>
      <div class="who">
        <div class="name">${f.name}</div>
        <div class="sub">${iconDot()}<span>Godkendt ven</span></div>
      </div>
      <div class="actions">
        <button class="btn-ghost" data-i="${i}" data-action="remove" title="Fjern ven">${iconMore()}</button>
      </div>`;
    list.appendChild(el);
  });
  list.querySelectorAll('button[data-action="remove"]').forEach(b => {
    b.addEventListener('click', () => {
      const i = parseInt(b.dataset.i, 10);
      if (!confirm(`Fjern ${friends[i].name} som ven?`)) return;
      friends.splice(i, 1);
      renderParent();
      renderChildHome();
    });
  });
}

function renderToggleList(containerId, arr) {
  const list = document.getElementById(containerId);
  if (!list) return;
  list.innerHTML = '';
  arr.forEach(s => {
    const row = document.createElement('button');
    row.className = 'toggle-row';
    row.type = 'button';
    row.innerHTML = `
      <div class="txt">
        <div class="ttl">${s.ttl}</div>
        <div class="desc">${s.desc}</div>
      </div>
      <div class="toggle ${s.on ? 'on' : ''}"></div>`;
    row.addEventListener('click', () => { s.on = !s.on; renderSettings(); });
    list.appendChild(row);
  });
}

function renderSettings() {
  renderToggleList('settingsList', settings);
  renderToggleList('groupSettingsList', groupSettings);

  const mList = document.getElementById('maxMembersList');
  if (mList) {
    mList.innerHTML = '';
    const row = document.createElement('div');
    row.className = 'toggle-row';
    row.style.cursor = 'default';
    row.innerHTML = `
      <div class="txt">
        <div class="ttl">Maks medlemmer</div>
        <div class="desc">Grænse for hvor mange der må være i en gruppe.</div>
      </div>
      <div class="stepper">
        <button class="step-btn" data-delta="-1" type="button">−</button>
        <span class="step-val" id="maxMembersVal">${maxMembersState.value}</span>
        <button class="step-btn" data-delta="1" type="button">+</button>
      </div>`;
    mList.appendChild(row);
    row.querySelectorAll('button[data-delta]').forEach(b => {
      b.addEventListener('click', (e) => {
        e.stopPropagation();
        const d = parseInt(b.dataset.delta, 10);
        maxMembersState.value = Math.max(3, Math.min(50, maxMembersState.value + d));
        document.getElementById('maxMembersVal').textContent = maxMembersState.value;
      });
    });
  }

  const pause = document.getElementById('pauseList');
  if (pause) {
    pause.innerHTML = '';
    const pr = document.createElement('button');
    pr.className = 'toggle-row';
    pr.type = 'button';
    pr.innerHTML = `
      <div class="txt">
        <div class="ttl">${pauseSetting.ttl}</div>
        <div class="desc">${pauseSetting.desc}</div>
      </div>
      <div class="toggle ${pauseSetting.on ? 'on' : ''}"></div>`;
    pr.addEventListener('click', () => { pauseSetting.on = !pauseSetting.on; renderSettings(); });
    pause.appendChild(pr);
  }
}

function renderBlocked() {
  const list = document.getElementById('blockedList');
  list.innerHTML = '';
  if (blocked.length === 0) {
    list.innerHTML = `
      <div class="empty">
        <div class="circle">${iconLock()}</div>
        <div class="msg">Ingen blokerede brugere</div>
      </div>`;
    return;
  }
  blocked.forEach((b, i) => {
    const el = document.createElement('div');
    el.className = 'list-item';
    el.innerHTML = `
      <div class="avatar">${b.initial}</div>
      <div class="who">
        <div class="name">${b.name}</div>
        <div class="sub">${iconDot()}<span>${b.note}</span></div>
      </div>
      <div class="actions">
        <button class="btn-sm btn-decline" data-i="${i}">Fjern</button>
      </div>`;
    list.appendChild(el);
  });
  list.querySelectorAll('button[data-i]').forEach(btn => {
    btn.addEventListener('click', () => {
      const i = parseInt(btn.dataset.i, 10);
      blocked.splice(i, 1);
      renderBlocked();
    });
  });
}

function renderReports() {
  const list = document.getElementById('reportsList');
  list.innerHTML = '';
  if (reports.length === 0) {
    list.innerHTML = `
      <div class="empty">
        <div class="circle">${iconShield()}</div>
        <div class="msg">Ingen rapporter</div>
        <div class="sub">Hvis Sofie rapporterer noget, vises det her.</div>
      </div>`;
  }
}

function updateHomeStats() {
  const fEl = document.getElementById('statFriends');
  if (fEl) fEl.textContent = friends.length;
  const gEl = document.getElementById('statGroups');
  if (gEl) gEl.textContent = groups.length;
  const n = pendingRequests.length;
  const badge = document.getElementById('navBadge');
  const count = document.getElementById('pendingCount');
  const sub = document.getElementById('pendingSub');
  const ttl = document.getElementById('pendingTtl');
  if (badge) {
    if (n === 0) { badge.style.display = 'none'; }
    else { badge.style.display = 'flex'; badge.textContent = n; }
  }
  if (count) count.textContent = n;
  if (n === 0) {
    if (ttl) ttl.textContent = 'Ingen nye anmodninger';
    if (sub) sub.textContent = 'Alt er roligt lige nu.';
  } else {
    if (ttl) ttl.textContent = n === 1 ? '1 ny anmodning' : `${n} nye anmodninger`;
    if (sub) sub.textContent = 'Godkend eller afvis.';
  }
}

function renderParent() {
  renderRequests();
  renderParentFriends();
  renderSettings();
  renderBlocked();
  renderReports();
  updateHomeStats();
}

function renderChildHome() {
  renderGroups();
  renderChats();
  renderFriendsGrid();
  wireAddButtons();
  wireGroupCtas();
}

/* ============================================================
 * BACKEND INTEGRATION (Sprint 6B)
 * Flip USE_BACKEND = true to route key flows through the real
 * Blink API. Mock state is kept as a fallback — when USE_BACKEND
 * is false, the prototype behaves exactly as before.
 *
 * Requires:
 *   - blink backend running (default http://localhost:8000)
 *   - BLINK_ENV=dev and BLINK_DEV_BYPASS_AUTH=true on the backend
 *   - BACKEND CORS_ORIGINS includes http://localhost:8765
 *   - Two seeded users in the DB — one child, one parent — whose
 *     UUIDs match DEV_CHILD_ID / DEV_PARENT_ID below.
 * See docs/FRONTEND_INTEGRATION.md for the full setup.
 * ============================================================ */

const USE_BACKEND = true;  // ← flip to true to use real backend
const BACKEND_URL = "http://localhost:8000";

// Seed these to match your local test users (see FRONTEND_INTEGRATION.md).
const DEV_CHILD_ID  = "11111111-1111-1111-1111-111111111111";
const DEV_PARENT_ID = "22222222-2222-2222-2222-222222222222";

let api = null;
if (typeof BlinkAPI !== "undefined") {
  api = new BlinkAPI({ baseUrl: BACKEND_URL, devUserId: DEV_CHILD_ID });
}

function useApiAsChild()  { if (api) api.devUserId = DEV_CHILD_ID; }
function useApiAsParent() { if (api) api.devUserId = DEV_PARENT_ID; }

function backendErrorMessage(e) {
  if (e && e.code) {
    const d = e.details || {};
    switch (e.code) {
      case "upgrade_required":
        return `Din voksne skal opgradere til "${d.requiredTier}" for at få plads til flere.`;
      case "hard_cap_exceeded":
        return `Gruppen kan ikke have mere end ${d.limit || 50} medlemmer.`;
      case "policy_blocked":
        return `Din voksne har slået "${d.policyKey}" fra.`;
      case "rate_limited":
        return `Prøv igen om ${d.retryAfterSeconds || "et øjeblik"} sek.`;
      case "unsupported":
        return `Ikke understøttet i v1: ${d.feature || e.message}`;
      case "authz_error":
        return "Du har ikke adgang.";
      case "not_found":
        return "Ikke fundet.";
      case "validation_error":
        return e.message || "Ugyldig anmodning.";
      default:
        return e.message || "Ukendt fejl";
    }
  }
  return (e && e.message) || "Netværksfejl";
}

function _showBackendToast(msg, kind) {
  // Lightweight toast — appended to body, disappears after 3.5s.
  const el = document.createElement("div");
  el.style.cssText =
    "position:fixed;left:50%;top:20px;transform:translateX(-50%);" +
    "background:" + (kind === "err" ? "var(--coral-deep,#F26A48)" : "var(--ink,#2B2B2B)") + ";" +
    "color:#fff;padding:10px 16px;border-radius:14px;" +
    "box-shadow:0 6px 20px rgba(0,0,0,.2);font-size:13px;font-weight:600;" +
    "z-index:9999;max-width:80%;";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 3500);
}

function showBackendError(where, e) {
  console.error(`[backend] ${where}:`, e);
  _showBackendToast(`${where}: ${backendErrorMessage(e)}`, "err");
}

function showBackendOk(msg) {
  _showBackendToast(msg, "ok");
}

/* ---- Shape mapping (backend → existing UI) ---- */

function _relativeTime(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const sec = Math.max(0, (Date.now() - then) / 1000);
  if (sec < 60)    return "nu";
  if (sec < 3600)  return `${Math.floor(sec / 60)} min`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} t`;
  return "i går";
}

function mapBackendGroupToUi(g) {
  const name = g.name || "Gruppe";
  const initial = (name[0] || "G").toUpperCase();
  const members = (g.activeMemberCount || 0) + (g.pendingMemberCount || 0);
  // For the list view we don't have full member details yet — seed with
  // the group initial so the stacked-avatars still render meaningfully.
  const mi = [initial, "?", "?"];
  return {
    id: g.id,
    name: name,
    initial: initial,
    members: members,
    memberInitials: mi,
    memberList: [{ name: "Sofie", initial: "S", self: true }],
    createdBy: "",
    code: g.inviteCode || "",
    last: g.lastMessagePreview ||
      (g.status === "pending_parent" ? "Afventer godkendelse" : "Ingen beskeder endnu"),
    time: _relativeTime(g.lastMessageAt),
    unread: 0,
    seed: "",
    status: g.status === "pending_parent" ? "pending" : "active",
  };
}

function mapBackendMessageToUi(m) {
  // Backend returns sender_display_name + sender_avatar_initial via JOIN.
  const senderName = m.senderDisplayName || "";
  const isMine = (m.senderId && api && m.senderId === api.devUserId);
  const base = {
    id: m.id,  // use backend id directly so retries are idempotent
    who: isMine ? "mine" : "theirs",
    state: m.status === "active" ? "seen" : "gone",
    lifetime: (m.ttlSeconds || 60) * 1000,
    seenAt: new Date(m.createdAt).getTime(),
  };
  if (m.type === "text") {
    return { ...base, kind: "text", text: m.text || "" };
  }
  // image path — rendered via photoCard which supports .kind='photo'
  return {
    ...base,
    kind: "photo",
    state: "unopened",
    mediaId: m.mediaId,
  };
}

function mapBackendFriendRequestToUi(fr) {
  return {
    id: fr.requestId,
    kind: "friend",
    name: fr.requesterDisplayName || "Ukendt",
    initial: ((fr.requesterDisplayName || "?")[0] || "?").toUpperCase(),
    method: fr.method || "code",
  };
}

function mapBackendGroupRequestToUi(gr) {
  const kind =
    gr.type === "create_group" ? "group-create" :
    gr.type === "join_group"   ? "group-join"   :
    "group-invite";
  const groupName = gr.groupName || gr.requestedName || "Gruppe";
  const actorName = gr.actorDisplayName || "";
  return {
    id: gr.requestId,
    kind: kind,
    groupId: gr.groupId,
    groupName: groupName,
    name: kind === "group-invite"
      ? (gr.targetDisplayName || "Ny ven")
      : actorName || groupName,
    initial: (((gr.actorDisplayName || groupName || "?")[0]) || "?").toUpperCase(),
    members: 0,
    memberInitials: [(groupName[0] || "G").toUpperCase(), "?", "?"],
    friendName: gr.targetDisplayName || null,
  };
}

/* ---- Backend-driven refresh calls ---- */

async function refreshGroupsFromBackend() {
  if (!api) return;
  useApiAsChild();
  try {
    const res = await api.groups.list();
    groups.length = 0;
    for (const g of (res.groups || [])) groups.push(mapBackendGroupToUi(g));
    renderGroups();
  } catch (e) {
    showBackendError("Henter grupper", e);
  }
}

async function refreshParentPendingFromBackend() {
  if (!api) return;
  useApiAsParent();
  try {
    const res = await api.parent.pending();
    pendingRequests.length = 0;
    for (const fr of (res.friendRequests || []))
      pendingRequests.push(mapBackendFriendRequestToUi(fr));
    for (const gr of (res.groupRequests || []))
      pendingRequests.push(mapBackendGroupRequestToUi(gr));
    renderRequests();
    updateHomeStats();
  } catch (e) {
    showBackendError("Henter anmodninger", e);
  }
}

async function createGroupBackend(name) {
  if (!api) throw new Error("api not loaded");
  useApiAsChild();
  // NOTE: backend requires UUID initial member ids. The mock friend picker
  // only has local names. For 6B we create with no initial members; the
  // parent can invite approved friends afterwards.
  const res = await api.groups.create({ name, initialMemberIds: [] });
  await refreshGroupsFromBackend();
  return res;
}

async function approveGroupRequestBackend(reqId) {
  if (!api) return;
  useApiAsParent();
  await api.parent.approveGroup(reqId);
  await refreshParentPendingFromBackend();
  await refreshGroupsFromBackend();
}

async function declineGroupRequestBackend(reqId) {
  if (!api) return;
  useApiAsParent();
  await api.parent.declineGroup(reqId);
  await refreshParentPendingFromBackend();
  await refreshGroupsFromBackend();
}

async function approveFriendRequestBackend(reqId) {
  if (!api) return;
  useApiAsParent();
  await api.parent.approveFriend(reqId);
  await refreshParentPendingFromBackend();
}

async function declineFriendRequestBackend(reqId) {
  if (!api) return;
  useApiAsParent();
  await api.parent.declineFriend(reqId);
  await refreshParentPendingFromBackend();
}

async function loadGroupMessagesBackend(groupId) {
  if (!api) return [];
  useApiAsChild();
  const res = await api.groups.listMessages(groupId, { limit: 50 });
  // Backend returns DESC (newest first). UI shows oldest first.
  return (res.messages || []).slice().reverse();
}

async function sendTextBackend(groupId, text) {
  if (!api) throw new Error("api not loaded");
  useApiAsChild();
  const clientMessageId = "msg-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
  const ttl = (typeof lifetimeMode !== "undefined" && lifetimeMode === "10s") ? 10 : 60;
  return await api.messages.createText({
    groupId,
    text,
    clientMessageId,
    ttlSeconds: ttl,
  });
}

// Used by openChatWith: fetch history and populate the local messages array.
async function loadMessagesIntoChat(groupId) {
  try {
    const list = await loadGroupMessagesBackend(groupId);
    messages.length = 0;
    for (const m of list) messages.push(mapBackendMessageToUi(m));
    render();
  } catch (e) {
    showBackendError("Henter beskeder", e);
  }
}

/* ============ INIT ============ */
// Always render the mock UI first so the app is usable immediately. When
// USE_BACKEND is true, we then overlay real data on top (brief flash is
// acceptable; replacing mock state cleanly is more important than avoiding
// the flash for a demo).
renderChildHome();
renderQR();
renderParent();

if (USE_BACKEND && api) {
  refreshGroupsFromBackend();
  refreshParentPendingFromBackend();
}

/* ============================================================
 * ONBOARDING FLOW (Sprint 7B)
 * Real onboarding when USE_BACKEND=true; mock fallback otherwise.
 * State lives in `onbState`; each step renders / validates / advances.
 * ============================================================ */

// Marks: first entry is "initial" (monogram derived from name); the rest
// are discrete symbols. Tween-friendly — no animals, no emoji.
const ONB_MARKS = [
  { type: 'initial', label: 'Initial' },   // value derived from name
  { type: 'icon', value: '✦', label: 'Gnist' },
  { type: 'icon', value: '●', label: 'Prik' },
  { type: 'icon', value: '▲', label: 'Trekant' },
  { type: 'icon', value: '◆', label: 'Diamant' },
  { type: 'icon', value: '#', label: 'Hash' },
  { type: 'icon', value: '✶', label: 'Stjerne' },
  { type: 'icon', value: '◐', label: 'Halv' },
  { type: 'icon', value: '○', label: 'Ring' },
  { type: 'icon', value: '✕', label: 'Kryds' },
];
// Avatar color choices for onboarding — aligned with Warm Signal. Coral
// leads (brand), blue and mint map to accent-blue / accent-mint, plus three
// muted neutrals that sit comfortably on the warm background.
const ONB_COLORS = [
  '#FF6B4A',  // primary coral
  '#3C7DFF',  // accent blue
  '#7BCFA6',  // accent mint
  '#9B8BBE',  // lavender
  '#BFA268',  // amber / sand
  '#A67986',  // rose / graphite-rose
];
const ONB_STEPS_TITLES = {
  welcome: 'Velkommen',
  profile: 'Din profil',
  findParent: 'Find voksen',
  waiting: 'Afventer voksen',
  parentPreview: 'Godkend Blink',
  parentOtp: 'Bekræft kode',
  parentApprove: 'Sidste trin',
  done: 'Klar!',
};
const ONB_STEP_ORDER = ['welcome','profile','findParent','waiting','parentPreview','parentOtp','parentApprove','done'];

const onbState = {
  step: 'welcome',
  displayName: '',
  markIndex: 0,                   // points into ONB_MARKS
  avatarType: 'initial',          // updated from selected mark
  avatarValue: '',                // for 'initial' this is derived from name
  avatarColor: ONB_COLORS[0],
  childUserId: null,
  blinkCode: null,
  inviteToken: null,
  devOtp: null,
  contact: '',
  consentAccepted: false,
};

// What's actually rendered in previews — for 'initial' we compute the
// first letter of the name live; for 'icon' it's the symbol itself.
function onbMarkGlyph(markIndex, name) {
  const m = ONB_MARKS[markIndex];
  if (!m) return '?';
  if (m.type === 'initial') {
    return (name && name[0] ? name[0] : '?').toUpperCase();
  }
  return m.value;
}

// Sync avatarType/avatarValue from the current markIndex + name.
// Keeps the outbound backend payload consistent with whatever was picked.
function syncAvatarFromMark() {
  const m = ONB_MARKS[onbState.markIndex];
  onbState.avatarType = m.type;
  if (m.type === 'initial') {
    onbState.avatarValue = (onbState.displayName[0] || '?').toUpperCase();
  } else {
    onbState.avatarValue = m.value;
  }
}

function onbGo(step) {
  onbState.step = step;
  document.querySelectorAll('#viewOnboarding .add-step').forEach(s => {
    s.classList.toggle('active', s.dataset.onbStep === step);
  });
  document.getElementById('onbTitle').textContent = ONB_STEPS_TITLES[step] || 'Opret Blink';
  const idx = ONB_STEP_ORDER.indexOf(step);
  const pill = document.getElementById('onbStepPill');
  if (idx >= 0) pill.textContent = `${idx + 1}/${ONB_STEP_ORDER.length}`;
  const body = document.getElementById('onbBody');
  if (body) body.scrollTop = 0;

  if (step === 'parentPreview') renderParentPreview();
  if (step === 'done') document.getElementById('onbBlinkCode').textContent = onbState.blinkCode || '—';
}

function onbStart() {
  // Reset picker defaults each time onboarding opens.
  onbState.step = 'welcome';
  onbState.displayName = '';
  onbState.markIndex = 0;
  onbState.avatarType = 'initial';
  onbState.avatarValue = '';
  onbState.avatarColor = ONB_COLORS[0];
  onbState.childUserId = null;
  onbState.blinkCode = null;
  onbState.inviteToken = null;
  onbState.devOtp = null;
  onbState.contact = '';
  onbState.consentAccepted = false;

  buildAvatarGrid();
  buildColorRow();
  buildPreview();
  document.getElementById('onbName').value = '';
  document.getElementById('onbContact').value = '';
  document.getElementById('onbOtp').value = '';
  document.getElementById('onbConsent').checked = false;
  document.getElementById('onbDevInfo').style.display = 'none';

  updateOnbSubmitProfile();
  updateOnbSubmitInvite();
  updateOnbSubmitOtp();
  updateOnbSubmitApprove();

  showView('viewOnboarding');
  onbGo('welcome');
}

function buildPreview() {
  const name = onbState.displayName || '';
  const glyph = onbMarkGlyph(onbState.markIndex, name);
  const av = document.getElementById('onbPreviewAvatar');
  if (av) {
    av.textContent = glyph;
    // Muted tint + solid-ink glyph — calm, not cartoon.
    av.style.background = onbState.avatarColor + '1F';   // ~12% opacity
    av.style.color = onbState.avatarColor;
  }
  const nm = document.getElementById('onbPreviewName');
  if (nm) nm.textContent = name || 'Dit navn';
}

function buildAvatarGrid() {
  const g = document.getElementById('onbAvatarGrid');
  if (!g) return;
  g.innerHTML = '';
  ONB_MARKS.forEach((mark, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    const isPicked = i === onbState.markIndex;
    b.className = 'onb-avatar-btn' + (isPicked ? ' picked' : '');
    b.textContent = onbMarkGlyph(i, onbState.displayName);
    b.title = mark.label;
    b.addEventListener('click', () => {
      onbState.markIndex = i;
      syncAvatarFromMark();
      buildAvatarGrid();
      buildPreview();
    });
    g.appendChild(b);
  });
}

function buildColorRow() {
  const r = document.getElementById('onbColorRow');
  if (!r) return;
  r.innerHTML = '';
  ONB_COLORS.forEach(color => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'onb-color-btn' + (color === onbState.avatarColor ? ' picked' : '');
    b.style.background = color;
    b.addEventListener('click', () => {
      onbState.avatarColor = color;
      buildColorRow();
      buildPreview();
    });
    r.appendChild(b);
  });
}

function updateOnbSubmitProfile() {
  const name = document.getElementById('onbName').value.trim();
  onbState.displayName = name;
  // Keep the live glyph + preview in sync when the name changes (matters
  // most for the "initial" mark).
  syncAvatarFromMark();
  buildAvatarGrid();
  buildPreview();
  document.getElementById('onbSubmitProfile').disabled = !(name.length >= 1 && name.length <= 24);
}

function updateOnbSubmitInvite() {
  const c = document.getElementById('onbContact').value.trim();
  onbState.contact = c;
  document.getElementById('onbSubmitInvite').disabled = !(c.length >= 3);
}

function updateOnbSubmitOtp() {
  const v = document.getElementById('onbOtp').value.trim();
  document.getElementById('onbSubmitOtp').disabled = !/^\d{4,6}$/.test(v);
}

function updateOnbSubmitApprove() {
  document.getElementById('onbSubmitApprove').disabled =
    !document.getElementById('onbConsent').checked;
}

document.getElementById('onbName').addEventListener('input', updateOnbSubmitProfile);
document.getElementById('onbContact').addEventListener('input', updateOnbSubmitInvite);
document.getElementById('onbOtp').addEventListener('input', updateOnbSubmitOtp);
document.getElementById('onbConsent').addEventListener('change', updateOnbSubmitApprove);

document.getElementById('onbBack').addEventListener('click', () => {
  // Back goes to pitch. Onboarding progress is thrown away.
  showView('viewPitch');
});

document.querySelectorAll('#viewOnboarding [data-onb-next]').forEach(b => {
  b.addEventListener('click', () => onbGo(b.dataset.onbNext));
});

// ---- Submit: child profile ----
document.getElementById('onbSubmitProfile').addEventListener('click', async () => {
  // Ensure derived values are current (e.g., if the user typed a name
  // after picking "initial" and went straight to submit).
  syncAvatarFromMark();
  const body = {
    displayName: onbState.displayName,
    avatarType: onbState.avatarType,   // 'initial' | 'icon' — backend accepts both
    avatarValue: onbState.avatarValue,
    avatarColor: onbState.avatarColor,
  };
  if (USE_BACKEND && api) {
    try {
      const res = await api.onboarding.createChildProfile(body);
      onbState.childUserId = res.userId;
      onbState.blinkCode = res.blinkCode;
      // Switch the api's devUserId so subsequent authenticated calls
      // (parent-approve flip → /me) talk as this new child.
      if (api.devUserId !== undefined) api.devUserId = res.userId;
      onbGo('findParent');
    } catch (e) {
      showBackendError('Opret profil', e);
    }
    return;
  }
  // Mock path — pretend the profile was created.
  onbState.childUserId = 'mock-child-' + Date.now();
  onbState.blinkCode = 'BLINK-MOCK42';
  onbGo('findParent');
});

// ---- Submit: parent invite ----
document.getElementById('onbSubmitInvite').addEventListener('click', async () => {
  if (USE_BACKEND && api) {
    try {
      const res = await api.onboarding.startParentInvite({
        childUserId: onbState.childUserId,
        contact: onbState.contact,
      });
      onbState.inviteToken = res.inviteToken || null;
      onbState.devOtp = res.otp || null;
      // Surface dev-only info so the single-device demo can complete the flow.
      if (onbState.devOtp) {
        document.getElementById('onbDevOtp').textContent = onbState.devOtp;
        document.getElementById('onbDevInfo').style.display = 'block';
      }
      onbGo('waiting');
    } catch (e) {
      showBackendError('Send til voksen', e);
    }
    return;
  }
  // Mock path
  onbState.inviteToken = 'mock-token-' + Date.now();
  onbState.devOtp = '000000';
  document.getElementById('onbDevOtp').textContent = onbState.devOtp;
  document.getElementById('onbDevInfo').style.display = 'block';
  onbGo('waiting');
});

// ---- "Jeg er voksen": child → parent perspective (same device) ----
document.getElementById('onbAsParent').addEventListener('click', () => {
  onbGo('parentPreview');
});

async function renderParentPreview() {
  document.getElementById('onbPrevName').textContent = onbState.displayName || 'dit barn';
  document.getElementById('onbPrevName2').textContent = onbState.displayName || 'Barnet';
  document.getElementById('onbPrevAvatar').textContent = onbState.avatarValue || '?';
  document.getElementById('onbPrevAvatar').style.background = (onbState.avatarColor || '#FFE3D8') + '33';
  document.getElementById('onbPrevAvatar').style.color = 'var(--ink)';
  document.getElementById('onbPrevContact').textContent = 'Sendt til: ' + (onbState.contact || '—');

  if (USE_BACKEND && api && onbState.inviteToken) {
    try {
      const res = await api.onboarding.previewInvite(onbState.inviteToken);
      document.getElementById('onbPrevContact').textContent = 'Sendt til: ' + (res.contactMasked || '—');
    } catch (e) {
      console.warn('[onboarding] preview failed:', e);
    }
  }
}

// ---- Submit: OTP verify ----
document.getElementById('onbSubmitOtp').addEventListener('click', async () => {
  const otp = document.getElementById('onbOtp').value.trim();
  if (USE_BACKEND && api) {
    try {
      await api.onboarding.verifyParent({ inviteToken: onbState.inviteToken, otp });
      onbGo('parentApprove');
    } catch (e) {
      showBackendError('Bekræft kode', e);
    }
    return;
  }
  // Mock path — accept any 4-6 digit code
  onbGo('parentApprove');
});

// ---- Submit: approve ----
document.getElementById('onbSubmitApprove').addEventListener('click', async () => {
  if (USE_BACKEND && api) {
    try {
      const res = await api.onboarding.approveChild({
        inviteToken: onbState.inviteToken,
        consentAccepted: true,
        consentVersion: '1.0',
      });
      if (res && res.blinkCode) onbState.blinkCode = res.blinkCode;
      onbGo('done');
    } catch (e) {
      showBackendError('Godkend', e);
    }
    return;
  }
  onbGo('done');
});

// ---- Decline (parent side) ----
document.getElementById('onbDecline').addEventListener('click', async () => {
  if (USE_BACKEND && api && onbState.inviteToken) {
    try {
      await api.onboarding.declineChild({ inviteToken: onbState.inviteToken });
    } catch (e) {
      console.warn('[onboarding] decline failed:', e);
    }
  }
  showView('viewPitch');
});

// ---- Finish: child lands in the real app ----
document.getElementById('onbGoHome').addEventListener('click', async () => {
  if (USE_BACKEND && api && onbState.childUserId) {
    // Make sure api identity is set to the newly activated child.
    if (api.devUserId !== undefined) api.devUserId = onbState.childUserId;
    // Best-effort sanity check that /me reports active.
    try { await api.me(); } catch (e) { console.warn('[onboarding] /me after activation:', e); }
    // Refresh groups etc. to reflect the real user.
    if (typeof refreshGroupsFromBackend === 'function') refreshGroupsFromBackend();
  }
  showView('viewChildHome');
  goChildTab('c-groups');
});

// ---- Pitch CTA ----
document.getElementById('pitchOnboard').addEventListener('click', onbStart);

/* ============ Theme picker UI (dev-only) ============
 * Blink ships a single canonical "Warm Signal" palette. The picker used to be
 * always-on, which made the app feel like a theme demo. It is now gated and
 * only mounted when explicitly enabled via:
 *   - window.DEV_THEME_PICKER = true (set before scripts run), OR
 *   - localStorage['blink-dev-theme-picker'] === '1', OR
 *   - ?devThemes=1 / ?devThemes in the URL.
 * The theme system itself stays intact for internal use.
 */
(function mountThemePicker() {
  let enabled = false;
  try {
    if (window.DEV_THEME_PICKER === true) enabled = true;
    else if (localStorage.getItem('blink-dev-theme-picker') === '1') enabled = true;
    else {
      const q = new URLSearchParams(window.location.search);
      if (q.has('devThemes')) enabled = true;
    }
  } catch (e) { /* private mode etc. */ }
  if (!enabled) return;

  const picker = document.createElement('div');
  picker.className = 'blink-theme-picker';
  picker.id = 'themePicker';
  picker.title = 'Blink theme (dev only)';
  Object.entries(BLINK_THEMES).forEach(([key, theme]) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.theme = key;
    b.style.background = theme.primary;
    b.title = theme.label;
    b.addEventListener('click', () => applyTheme(key));
    picker.appendChild(b);
  });
  document.body.appendChild(picker);
  let current = 'coral';
  try { current = localStorage.getItem('blink-theme') || 'coral'; } catch (e) {}
  picker.querySelectorAll('button').forEach(b =>
    b.classList.toggle('active', b.dataset.theme === current)
  );
})();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a, **kw):
        pass

    def do_GET(self):
        if self.path == "/blink_api_client.js":
            path = _find_api_client()
            if path is None:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"blink_api_client.js not found")
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Default: serve the HTML shell.
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))


if __name__ == "__main__":
    port = 8765
    print(f"Blink v4 (gruppe-først) kører på http://localhost:{port}")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
