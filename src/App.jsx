import { useState, useEffect } from "react";
import "./App.css";
import { SITE_CONFIG } from "./config";

// Resolve API Base URL:
// 1. Check VITE_API_URL or VITE_API_BASE_URL
// 2. In production, default to canonical deployed Render backend: https://saveall-api.onrender.com
// 3. In local development, default to /api (proxied by Vite to http://127.0.0.1:8000)
const envApiUrl = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL)?.trim();
const API_BASE_URL = (
  envApiUrl ||
  (import.meta.env.PROD ? "https://saveall-api.onrender.com" : "/api")
).replace(/\/$/, "");

function getApiConfigurationError() {
  if (!import.meta.env.PROD) {
    return "";
  }

  try {
    const parsed = new URL(API_BASE_URL, window.location.origin);
    if (parsed.protocol === "http:" && window.location.protocol === "https:") {
      return "Production API must use HTTPS to prevent browser mixed content blocking.";
    }
    if (["localhost", "127.0.0.1"].includes(parsed.hostname)) {
      return "Production API cannot use localhost. Set VITE_API_URL to the deployed HTTPS Render backend URL.";
    }
  } catch {
    return "API URL configuration is invalid. Please verify VITE_API_URL.";
  }

  return "";
}

async function readApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  const text = await response.text();
  return text ? { detail: text.slice(0, 240), error: text.slice(0, 240) } : {};
}

function isValidYouTubeUrl(value) {
  if (!value) return false;
  let clean = value.trim();
  if (!/^https?:\/\//i.test(clean)) {
    clean = "https://" + clean;
  }
  try {
    const parsed = new URL(clean);
    const host = parsed.hostname.toLowerCase();
    const isYtHost =
      host === "youtu.be" ||
      host === "youtube.com" ||
      host.endsWith(".youtube.com");
    return (
      (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      isYtHost &&
      parsed.pathname !== "/" &&
      parsed.pathname.length > 1
    );
  } catch {
    return false;
  }
}

function isValidInstagramUrl(value) {
  if (!value) return false;
  let clean = value.trim();
  if (!/^https?:\/\//i.test(clean)) {
    clean = "https://" + clean;
  }
  try {
    const parsed = new URL(clean);
    const host = parsed.hostname.toLowerCase();
    const isIgHost =
      host === "instagram.com" ||
      host.endsWith(".instagram.com") ||
      host === "instagr.am" ||
      host.endsWith(".instagr.am") ||
      host === "ddinstagram.com";
    return (
      (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      isIgHost &&
      parsed.pathname.length > 2
    );
  } catch {
    return false;
  }
}

function detectPlatform(value) {
  if (!value) return null;
  const clean = value.trim();
  if (!clean) return null;
  if (isValidYouTubeUrl(clean)) return "youtube";
  if (isValidInstagramUrl(clean)) return "instagram";
  return null;
}

function formatDuration(sec) {
  if (!sec || isNaN(sec)) return null;
  const s = Math.floor(sec);
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatBytes(bytes) {
  if (!bytes || isNaN(bytes)) return null;
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let val = bytes;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(1)} ${units[i]}`;
}

const LOADING_STAGES = [
  "Connecting to high-speed stream servers...",
  "Extracting high-definition video & audio...",
  "Optimizing packaging for fast MP4 stream...",
  "Generating secure direct download link...",
];

function App() {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const detectedPlatform = detectPlatform(url);
  const activeTheme = detectedPlatform
    ? `theme-${detectedPlatform}`
    : result?.platform
    ? `theme-${result.platform.toLowerCase()}`
    : "theme-auto";

  // Rotate loading stage for engaging cinematic feedback
  useEffect(() => {
    if (!loading) return;
    const timer = setInterval(() => {
      setStageIndex((prev) => (prev < LOADING_STAGES.length - 1 ? prev + 1 : prev));
    }, 2200);
    return () => clearInterval(timer);
  }, [loading]);

  const handleGetVideo = async () => {
    let cleanUrl = url.trim();
    if (cleanUrl && !/^https?:\/\//i.test(cleanUrl)) {
      cleanUrl = "https://" + cleanUrl;
    }

    setError("");
    setResult(null);
    setStageIndex(0);

    if (!cleanUrl) {
      setError("Please paste a YouTube or Instagram video link.");
      return;
    }

    const targetPlatform = detectPlatform(cleanUrl);
    if (!targetPlatform) {
      setError("Please enter a valid YouTube video link (e.g. https://www.youtube.com/watch?v=...) or Instagram link (e.g. https://www.instagram.com/reel/...)");
      return;
    }

    setLoading(true);

    const controller = new AbortController();
    const abortTimer = setTimeout(() => {
      controller.abort();
    }, 85000);

    try {
      const configurationError = getApiConfigurationError();
      if (configurationError) {
        throw new Error(configurationError);
      }

      const endpoint = `${API_BASE_URL}/download`;

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify({
          platform: targetPlatform === "youtube" ? "YouTube" : "Instagram",
          url: cleanUrl,
        }),
        signal: controller.signal,
      });

      clearTimeout(abortTimer);

      const data = await readApiResponse(response);

      if (!response.ok) {
        let errorMsg =
          data.error ||
          data.detail ||
          (response.status === 400
            ? "Invalid URL or request format."
            : response.status === 404
            ? "API endpoint was not found on the server."
            : response.status === 502 || response.status === 503
            ? "Backend server is temporarily waking up. Please try again shortly."
            : "Server returned an error while processing the link.");

        throw new Error(errorMsg);
      }

      setResult({
        platform: data.platform || (targetPlatform === "youtube" ? "YouTube" : "Instagram"),
        url: cleanUrl,
        status: data.status || "ready",
        title: data.title || "Video ready",
        fileName: data.file_name || "",
        downloadUrl: data.download_url || "",
        thumbnail: data.thumbnail || null,
        duration: data.duration || null,
        uploader: data.uploader || null,
        filesize: data.filesize || null,
        message: data.message || "Video is ready for download.",
      });
    } catch (err) {
      clearTimeout(abortTimer);

      if (err.name === "AbortError") {
        setError("Request timed out. The server might be busy or waking up. Please try again.");
      } else if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
        setError("Backend server is unreachable. Please verify network connection or server status.");
      } else {
        setError(err.message || "Download could not be completed.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadFile = () => {
    try {
      if (!result) return;

      let fileUrl = result.downloadUrl;
      if (!fileUrl && result.fileName) {
        fileUrl = `${API_BASE_URL}/download-file?filename=${encodeURIComponent(result.fileName)}`;
      }

      if (!fileUrl) {
        throw new Error("No downloadable file was returned by the server.");
      }

      if (window.location.protocol === "https:" && fileUrl.startsWith("http://")) {
        fileUrl = fileUrl.replace(/^http:\/\//, "https://");
      }

      const link = document.createElement("a");
      link.href = fileUrl;
      link.download = result.fileName || "saveall-download.mp4";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      alert(err.message || "Download request failed.");
    }
  };

  const handleCopyLink = async () => {
    if (!result?.downloadUrl) return;
    try {
      await navigator.clipboard.writeText(result.downloadUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback
    }
  };

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrl(text);
        setError("");
      }
    } catch {
      setError("Clipboard access denied. Please paste using Ctrl + V.");
    }
  };

  return (
    <div className={`app-wrapper ${activeTheme}`}>
      {/* Cinematic Ambient Glows */}
      <div className="ambient-glow ambient-glow-primary" aria-hidden="true" />
      <div className="ambient-glow ambient-glow-secondary" aria-hidden="true" />
      <div className="grid-overlay" aria-hidden="true" />

      {/* Header / Navbar */}
      <header className="cinematic-nav">
        <div className="nav-container">
          <div className="brand">
            <div className="brand-badge">
              <span className="brand-initial">S</span>
            </div>
            <div className="brand-text">
              <span className="brand-title">SAVEALL</span>
              <span className="brand-tag">PRO</span>
            </div>
          </div>

          <div className="nav-actions">
            <div className="engine-status">
              <span className="status-dot pulsing"></span>
              <span className="status-label">Ultra Engine Active</span>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="cinematic-main">

        <h1 className="hero-headline">
          Save Any Video, <br />
          <span className="gradient-text">Anytime, Anywhere.</span>
        </h1>

        <p className="hero-description">
          Universal high-speed downloader for YouTube & Instagram with automatic link detection.
        </p>

        {/* Master Control Card */}
        <section className={`media-card-shell ${detectedPlatform ? `platform-${detectedPlatform}` : "platform-auto"}`}>
          {/* Universal Platform Bar & Auto-Detection Status */}
          <div className="unified-status-bar">
            <div className={`detection-pill ${detectedPlatform ? "pill-detected" : "pill-waiting"}`}>
              <span className={`status-radar ${detectedPlatform ? "radar-active" : ""}`} />
              <span className="detection-pill-text">
                {detectedPlatform === "youtube"
                  ? "YouTube Detected"
                  : detectedPlatform === "instagram"
                  ? "Instagram Detected"
                  : "Auto-Detect Ready"}
              </span>
            </div>

            <div className="supported-brands" aria-label="Supported Platforms">
              <span className={`brand-chip-item chip-yt ${detectedPlatform === "youtube" ? "is-active" : ""}`}>
                <svg className="chip-svg" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
                <span>YouTube</span>
              </span>
              <span className={`brand-chip-item chip-ig ${detectedPlatform === "instagram" ? "is-active" : ""}`}>
                <svg className="chip-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/>
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/>
                </svg>
                <span>Instagram</span>
              </span>
            </div>
          </div>

          {/* Universal Header Title */}
          <div className="card-header-info">
            <div className={`header-icon-wrap ${detectedPlatform || "auto"}`}>
              {detectedPlatform === "youtube" ? (
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M10 15l5.19-3L10 9v6m11.56-7.83c.13.47.22 1.1.28 1.9.07.8.1 1.49.1 2.09L22 12c0 2.19-.16 3.8-.44 4.83-.25.9-.83 1.48-1.73 1.73-.47.13-1.33.22-2.65.28-1.3.07-2.49.1-3.59.1L12 19c-4.19 0-6.8-.16-7.83-.44-.9-.25-1.48-.83-1.73-1.73-.13-.47-.22-1.1-.28-1.9-.07-.8-.1-1.49-.1-2.09L22 12c0-2.19.16-3.8.44-4.83.25-.9.83-1.48 1.73-1.73z"/>
                </svg>
              ) : detectedPlatform === "instagram" ? (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/>
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/>
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                </svg>
              )}
            </div>
            <div className="header-text-wrap">
              <h2>
                {detectedPlatform === "youtube"
                  ? "YouTube Video & Shorts"
                  : detectedPlatform === "instagram"
                  ? "Instagram Reels & Posts"
                  : "All-in-One Video Downloader"}
              </h2>
              <p>
                {detectedPlatform === "youtube"
                  ? "YouTube link detected • Ready to fetch high-definition video"
                  : detectedPlatform === "instagram"
                  ? "Instagram link detected • Ready to fetch Reel or Post"
                  : "Paste any YouTube or Instagram video link — auto-detected instantly"}
              </p>
            </div>
          </div>

          {/* Input Box Area */}
          <div className={`input-group-cinematic ${detectedPlatform ? `has-${detectedPlatform}` : ""}`}>
            <div className="input-prefix-icon">
              {detectedPlatform === "youtube" ? (
                <svg className="prefix-yt" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
              ) : detectedPlatform === "instagram" ? (
                <svg className="prefix-ig" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/>
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/>
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                </svg>
              )}
            </div>

            <input
              type="text"
              className="cinematic-input"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (error) setError("");
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !loading) {
                  handleGetVideo();
                }
              }}
              placeholder="Paste any YouTube or Instagram link here..."
              aria-label="Video URL"
              disabled={loading}
            />

            <div className="input-actions">
              {url && (
                <button
                  type="button"
                  className="action-icon-btn clear-btn"
                  onClick={() => {
                    setUrl("");
                    setError("");
                    setResult(null);
                  }}
                  title="Clear input"
                  aria-label="Clear input"
                >
                  ✕
                </button>
              )}
              <button
                type="button"
                className="action-paste-btn"
                onClick={handlePaste}
                title="Paste from clipboard"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
                  <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
                </svg>
                <span>Paste</span>
              </button>
            </div>
          </div>

          {/* Real-time detection feedback badge */}
          {url.trim() && (
            <div className={`cinematic-detect-feedback ${detectedPlatform ? "is-valid" : "is-invalid"}`}>
              {detectedPlatform === "youtube" && (
                <>
                  <span className="detect-icon yt">▶</span>
                  <span>YouTube video detected & ready</span>
                </>
              )}
              {detectedPlatform === "instagram" && (
                <>
                  <span className="detect-icon ig">📷</span>
                  <span>Instagram media detected & ready</span>
                </>
              )}
              {!detectedPlatform && (
                <>
                  <span className="detect-icon warn">⚠️</span>
                  <span>Please paste a valid YouTube (youtube.com, youtu.be) or Instagram (instagram.com) link</span>
                </>
              )}
            </div>
          )}

          {/* Primary Action Button */}
          <button
            type="button"
            className={`cinematic-cta-btn ${loading ? "is-loading" : ""} ${detectedPlatform ? `cta-${detectedPlatform}` : ""}`}
            onClick={handleGetVideo}
            disabled={loading}
          >
            {loading ? (
              <div className="btn-loading-content">
                <span className="spinner-ring" />
                <span>Processing Media Stream...</span>
              </div>
            ) : (
              <div className="btn-normal-content">
                <span>
                  {detectedPlatform === "youtube"
                    ? "Fetch YouTube Video"
                    : detectedPlatform === "instagram"
                    ? "Fetch Instagram Reel"
                    : "Fetch Video"}
                </span>
                <svg className="cta-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </div>
            )}
            <span className="btn-shine" />
          </button>

          {/* Cinematic Animated Progress Bar & Stage Indicator */}
          {loading && (
            <div className="cinematic-progress-wrap">
              <div className="progress-bar-track">
                <div className="progress-bar-fill" />
              </div>
              <div className="progress-status-row">
                <span className="pulse-beacon" />
                <span className="progress-message">{LOADING_STAGES[stageIndex]}</span>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="cinematic-error-banner" role="alert">
              <div className="error-icon-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <div className="error-text">{error}</div>
              <button
                type="button"
                className="error-dismiss"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                ✕
              </button>
            </div>
          )}

          {/* Result Card: Cinematic Video Stage */}
          {result && (
            <div className="cinematic-result-stage">
              <div className="result-backdrop" />
              
              <div className="result-inner-grid">
                {/* Thumbnail Display */}
                {result.thumbnail && (
                  <div className="result-thumb-wrapper">
                    <img
                      src={result.thumbnail}
                      alt={result.title}
                      className="result-thumb-img"
                      loading="lazy"
                    />
                    <div className="thumb-gradient-overlay" />
                    {result.duration && (
                      <span className="thumb-duration-pill">
                        {formatDuration(result.duration)}
                      </span>
                    )}
                    <span className="thumb-format-pill">MP4 • 720p HD</span>
                  </div>
                )}

                {/* Video Info Details */}
                <div className="result-details">
                  <div className="result-meta-tags">
                    <span className={`meta-platform-tag tag-${result.platform.toLowerCase()}`}>
                      {result.platform}
                    </span>
                    {result.filesize && (
                      <span className="meta-size-tag">
                        💾 {formatBytes(result.filesize)}
                      </span>
                    )}
                    <span className="meta-status-tag">
                      ✓ Ready for Instant Download
                    </span>
                  </div>

                  <h3 className="result-title" title={result.title}>
                    {result.title}
                  </h3>

                  {result.uploader && (
                    <p className="result-uploader">
                      <span>Creator:</span> {result.uploader}
                    </p>
                  )}

                  {/* Action Buttons */}
                  <div className="result-action-row">
                    <button
                      type="button"
                      className="cinematic-download-btn"
                      onClick={handleDownloadFile}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      <span>Download Video (MP4)</span>
                    </button>

                    {result.downloadUrl && (
                      <button
                        type="button"
                        className="cinematic-copy-btn"
                        onClick={handleCopyLink}
                        title="Copy direct file URL"
                      >
                        {copied ? (
                          <>
                            <svg viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                            <span>Copied!</span>
                          </>
                        ) : (
                          <>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                            </svg>
                            <span>Direct Link</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          <p className="compliance-note">
            <span className="lock-icon">🔒</span>
            <span>Fast, secure extraction. Use only content you own or have permission to download.</span>
          </p>
        </section>

        {/* Cinematic Feature Highlights Cards */}
        <div className="cinematic-features-grid">
          <div className="feature-card">
            <div className="feature-icon-bubble bubble-lightning">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </div>
            <h4>Blazing Acceleration</h4>
            <p>Multi-threaded fragment downloads deliver finished MP4s in seconds.</p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-bubble bubble-shield">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h4>Zero Ads & Tracking</h4>
            <p>Direct media streaming with no intrusive popups, adware, or redirects.</p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-bubble bubble-device">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
                <line x1="12" y1="18" x2="12.01" y2="18" />
              </svg>
            </div>
            <h4>Universal Responsive</h4>
            <p>Seamless experience precision-crafted for iPhones, Androids, and 4K screens.</p>
          </div>
        </div>
      </main>

      {/* Cinematic Site Footer */}
      <footer className="cinematic-footer">
        <div className="footer-content">
          <div className="footer-brand-line">
            <div className="footer-logo">
              <span className="footer-logo-box">S</span>
              <span className="footer-logo-title">SAVEALL</span>
            </div>
            <p className="footer-tagline">
              Premium All-in-One Downloader <span>•</span> Fast • Pure • Secure
            </p>
          </div>

          <div className="footer-divider-glow" />

          {/* Creator Credit */}
          <div className="creator-block">
            <span className="credit-label">Engineered & Designed by</span>
            <h3 className="creator-title">{SITE_CONFIG.creatorName}</h3>
            <span className="brand-chip">{SITE_CONFIG.brandName}</span>
          </div>

          {/* Social Links */}
          <div className="social-links-deck">
            {/* Instagram */}
            <a
              href={SITE_CONFIG.social.instagram}
              target="_blank"
              rel="noopener noreferrer"
              className="cinematic-social-btn"
              aria-label="Instagram"
              title="Instagram"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/>
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>
                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/>
              </svg>
              <span className="social-tooltip">Instagram</span>
            </a>

            {/* LinkedIn */}
            <a
              href={SITE_CONFIG.social.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              className="cinematic-social-btn"
              aria-label="LinkedIn"
              title="LinkedIn"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
                <rect x="2" y="9" width="4" height="12" />
                <circle cx="4" cy="4" r="2" />
              </svg>
              <span className="social-tooltip">LinkedIn</span>
            </a>

            {/* Email */}
            <a
              href={`mailto:${SITE_CONFIG.social.email}`}
              className="cinematic-social-btn"
              aria-label="Email"
              title="Email"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
              <span className="social-tooltip">Email</span>
            </a>

            {/* GitHub */}
            <a
              href={SITE_CONFIG.social.github}
              target="_blank"
              rel="noopener noreferrer"
              className="cinematic-social-btn"
              aria-label="GitHub"
              title="GitHub"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
              </svg>
              <span className="social-tooltip">GitHub</span>
            </a>
          </div>

          {/* Legal / Copyright */}
          <div className="footer-bottom-copy">
            <p>© 2026 SAVEALL. All rights reserved.</p>
            <p className="maker-line">
              Crafted with <span className="heart-pulse">♥</span> by{" "}
              <strong>{SITE_CONFIG.creatorName}</strong> ·{" "}
              <span className="brand-glow">{SITE_CONFIG.brandName}</span>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;