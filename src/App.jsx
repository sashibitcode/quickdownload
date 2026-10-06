import { useState, useEffect, useRef } from "react";
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

// Shuriken SVG Icon
function ShurikenIcon({ className = "shuriken-icon" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" />
      <circle cx="12" cy="12" r="2.5" fill="#0f172a" />
    </svg>
  );
}

// 1-second Confetti & Shuriken Celebration
function ConfettiShuriken() {
  const particles = Array.from({ length: 20 });
  return (
    <div className="confetti-shuriken-overlay" aria-hidden="true">
      {particles.map((_, i) => (
        <span
          key={i}
          className={`shuriken-particle particle-${i % 5}`}
          style={{
            "--angle": `${(i * 360) / 20}deg`,
            "--distance": `${80 + (i % 4) * 35}px`,
            "--delay": `${(i % 3) * 0.05}s`,
          }}
        >
          {i % 2 === 0 ? "⚡" : "✦"}
        </span>
      ))}
    </div>
  );
}

// Trust Badges Component
function TrustBadges() {
  return (
    <div className="trust-badges-row" aria-label="Trust Badges">
      <div className="trust-badge-item">
        <span className="trust-icon">🛡️</span>
        <span className="trust-text">No Ads</span>
      </div>
      <div className="trust-badge-item">
        <span className="trust-icon">🎬</span>
        <span className="trust-text">HD Quality</span>
      </div>
      <div className="trust-badge-item">
        <span className="trust-icon">⚡</span>
        <span className="trust-text">100% Free</span>
      </div>
      <div className="trust-badge-item">
        <span className="trust-icon">🔒</span>
        <span className="trust-text">No Login</span>
      </div>
    </div>
  );
}

// Ninja Character with Dashing / Spinning Jutsu Animation
function NinjaCharacter({ isComplete = false }) {
  return (
    <div className={`anime-runner-wrapper ${isComplete ? "is-ready" : "is-dashing"}`}>
      <svg
        className="anime-runner-svg"
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* Pulsing Energy Aura */}
        <circle cx="50" cy="50" r="34" className="anime-aura-halo" />

        {/* Headband Flapping Ribbons */}
        <path
          d="M32 40 C20 37, 10 32, 2 35 C12 42, 24 44, 30 43"
          className="anime-ribbon-1"
          fill="#ff2647"
        />
        <path
          d="M32 43 C22 41, 12 38, 4 44 C15 47, 25 46, 31 45"
          className="anime-ribbon-2"
          fill="#f09433"
        />

        {/* Spiky Anime Hair */}
        <path
          d="M36 34 L28 19 L40 25 L46 13 L56 23 L69 16 L65 29 L77 27 L68 37 Z"
          fill="#fde047"
          className="anime-hair"
        />

        {/* Head */}
        <circle cx="50" cy="42" r="14" fill="#fed7aa" />

        {/* Ninja Headband */}
        <rect x="36" y="34" width="28" height="6.5" rx="2" fill="#0f172a" />
        <rect x="45" y="35.5" width="10" height="3.5" rx="1" fill="#cbd5e1" />

        {/* Focused Anime Eye & Flare */}
        <ellipse cx="54" cy="42" rx="3.5" ry="2" fill="#0f172a" />
        <circle cx="55" cy="41.5" r="1.2" fill="#ffffff" />
        <line x1="56" y1="42" x2="70" y2="42" stroke="#38bdf8" strokeWidth="2" strokeLinecap="round" className="eye-flare" />

        {/* Collar */}
        <path d="M40 52 C45 57, 55 57, 60 52 C58 59, 42 59, 40 52 Z" fill="#ff2647" />

        {/* Torso */}
        <path d="M43 52 L58 54 L54 68 L42 66 Z" fill="#ff2647" className="anime-torso" />

        {/* Aerodynamic Running Arms */}
        <g className="anime-arm-back">
          <path d="M44 54 L24 48 L10 39" stroke="#fed7aa" strokeWidth="4.5" strokeLinecap="round" />
        </g>
        <g className="anime-arm-front">
          <path d="M52 56 L34 52 L20 45" stroke="#fed7aa" strokeWidth="4.5" strokeLinecap="round" />
        </g>

        {/* Running Legs */}
        <g className="anime-leg-left">
          <path d="M46 66 L34 76 L20 84" stroke="#0f172a" strokeWidth="5" strokeLinecap="round" />
          <circle cx="18" cy="85" r="3.5" fill="#38bdf8" />
        </g>
        <g className="anime-leg-right">
          <path d="M52 66 L64 74 L78 72" stroke="#0f172a" strokeWidth="5" strokeLinecap="round" />
          <circle cx="80" cy="72" r="3.5" fill="#38bdf8" />
        </g>
      </svg>

      {/* Speed Dust Puffs */}
      <div className="anime-dust-cloud">
        <span className="dust dust-1" />
        <span className="dust dust-2" />
        <span className="dust dust-3" />
      </div>
    </div>
  );
}

// 4-Step Progress Card Component
const STEPS = [
  { id: 0, title: "Checking link...", sub: "Verifying video protocol & stream handshake..." },
  { id: 1, title: "Reading video info...", sub: "Extracting title, duration & available resolutions..." },
  { id: 2, title: "Generating download link...", sub: "Generating secure direct download link..." },
  { id: 3, title: "Ready!", sub: "Your video is ready to download" },
];

function ProgressCard({ currentStep, progressPercent }) {
  const currentStepData = STEPS[currentStep] || STEPS[0];

  return (
    <div className="anime-progress-card" role="status" aria-live="polite">
      {/* Speed Streaks Background */}
      <div className="anime-speed-grid" aria-hidden="true">
        <span className="speed-streak streak-1" />
        <span className="speed-streak streak-2" />
        <span className="speed-streak streak-3" />
      </div>

      <div className="progress-card-inner">
        {/* Animated Ninja Stage */}
        <div className="ninja-stage-column">
          <NinjaCharacter isComplete={currentStep === 3} />
        </div>

        {/* Progress Content Column */}
        <div className="progress-content-column">
          <div className="progress-headline-bar">
            <span className="progress-jutsu-badge">⚡ CHAKRA JUTSU</span>
            <span className="progress-percent-number">{Math.round(progressPercent)}%</span>
          </div>

          {/* Stepper Dots & Labels */}
          <div className="stepper-dots-row">
            {STEPS.map((step, idx) => {
              const isPast = idx < currentStep;
              const isCurrent = idx === currentStep;
              return (
                <div
                  key={step.id}
                  className={`step-item ${isPast ? "is-past" : ""} ${isCurrent ? "is-current" : ""}`}
                >
                  <div className="step-dot-wrap">
                    <span className="step-dot">{isPast ? "✓" : idx + 1}</span>
                    {idx < STEPS.length - 1 && <span className="step-connector" />}
                  </div>
                  <span className="step-label">{step.title}</span>
                </div>
              );
            })}
          </div>

          {/* Active Step Sub-Text */}
          <div className="step-subtext-area">
            <p className="step-active-subtext">{currentStepData.sub}</p>
          </div>

          {/* Progress Bar Track */}
          <div className="chakra-meter-track">
            <div
              className="chakra-meter-fill"
              style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
            >
              <span className="chakra-lightning-tip" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Result Card Component with Dynamic Quality Options & Download CTA
function ResultCard({
  result,
  selectedQuality,
  onSelectQuality,
  onDownload,
  onReset,
  isSwitchingQuality,
}) {
  const [copied, setCopied] = useState(false);

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

  const badgeText =
    result.media_badge ||
    (result.platform === "Instagram"
      ? "Instagram Video"
      : result.duration && result.duration <= 60
      ? "Shorts"
      : "YouTube Video");

  const qualities = result.qualities && result.qualities.length > 0
    ? result.qualities
    : [
        {
          id: "720p",
          label: "MP4 720p",
          badge: "HD",
          filesize: result.filesize,
        },
        {
          id: "mp3",
          label: "MP3 Audio",
          badge: "Audio",
          filesize: null,
        },
      ];

  const currentOption = qualities.find((q) => q.id === selectedQuality) || qualities[0];

  return (
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
            <span className="thumb-format-pill">{badgeText}</span>
          </div>
        )}

        {/* Video Info Details */}
        <div className="result-details">
          <div className="result-meta-tags">
            <span className={`meta-platform-tag tag-${result.platform.toLowerCase()}`}>
              {result.platform}
            </span>
            <span className="meta-badge-tag">{badgeText}</span>
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

          {/* Quality Options Selector */}
          <div className="quality-selector-wrap">
            <span className="quality-heading">Select Download Quality:</span>
            <div className="quality-chips-grid">
              {qualities.map((item) => {
                const isSelected = item.id === selectedQuality;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`quality-chip-btn ${isSelected ? "is-selected" : ""}`}
                    onClick={() => onSelectQuality(item.id)}
                  >
                    <span className="quality-chip-label">{item.label}</span>
                    {item.badge && <span className="quality-chip-badge">{item.badge}</span>}
                    {item.filesize && (
                      <span className="quality-chip-size">({formatBytes(item.filesize)})</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="result-action-row">
            <button
              type="button"
              className="cinematic-download-btn"
              onClick={onDownload}
              disabled={isSwitchingQuality}
            >
              {isSwitchingQuality ? (
                <>
                  <ShurikenIcon className="btn-shuriken-spinner" />
                  <span>Preparing {currentOption.label}...</span>
                </>
              ) : (
                <>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  <span>Download {currentOption.label}</span>
                </>
              )}
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

          {/* Reset link to download another video */}
          <div className="reset-action-row">
            <button
              type="button"
              className="reset-form-link"
              onClick={onReset}
            >
              ↺ Download another video
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Themed Jutsu Error Card
function ErrorCard({ error, onRetry, onDismiss }) {
  return (
    <div className="jutsu-error-card" role="alert">
      <div className="error-card-glow" />
      <div className="error-card-header">
        <div className="error-jutsu-badge">
          <span className="error-seal-icon">⚠️</span>
          <span>Jutsu failed! Please check the link and try again.</span>
        </div>
        <button
          type="button"
          className="error-card-close"
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          ✕
        </button>
      </div>

      <div className="error-card-body">
        <p className="error-card-message">{error}</p>
        <button
          type="button"
          className="error-retry-btn"
          onClick={onRetry}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M23 4v6h-6" />
            <path d="M1 20v-6h6" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          <span>Retry Jutsu</span>
        </button>
      </div>
    </div>
  );
}

// How It Works 3-Step Section
function HowItWorks() {
  return (
    <section className="how-it-works-section" aria-label="How it works">
      <div className="how-header-row">
        <span className="how-tag">EASY 3 STEPS</span>
        <h3 className="how-title">How It Works</h3>
      </div>
      <div className="how-steps-grid">
        <div className="how-step-card">
          <div className="step-num-pill">1</div>
          <div className="step-icon-wrap">📋</div>
          <h4>Paste Link</h4>
          <p>Copy any YouTube video or Instagram Reel link and paste it into the search box.</p>
        </div>

        <div className="how-step-connector">
          <span>➔</span>
        </div>

        <div className="how-step-card">
          <div className="step-num-pill">2</div>
          <div className="step-icon-wrap">⚡</div>
          <h4>Fetch Media</h4>
          <p>Click Fetch. Our high-speed engine extracts formats and generates direct streams.</p>
        </div>

        <div className="how-step-connector">
          <span>➔</span>
        </div>

        <div className="how-step-card">
          <div className="step-num-pill">3</div>
          <div className="step-icon-wrap">⬇️</div>
          <h4>Download in HD</h4>
          <p>Pick your preferred resolution (1080p, 720p, 360p or MP3) and download instantly.</p>
        </div>
      </div>
    </section>
  );
}

function App() {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [progressPercent, setProgressPercent] = useState(0);
  const [showCelebration, setShowCelebration] = useState(false);
  const [error, setError] = useState("");
  const [selectedQuality, setSelectedQuality] = useState("720p");
  const [qualityDownloads, setQualityDownloads] = useState({});
  const [isSwitchingQuality, setIsSwitchingQuality] = useState(false);

  const progressIntervalRef = useRef(null);

  const detectedPlatform = detectPlatform(url);
  const activeTheme = detectedPlatform
    ? `theme-${detectedPlatform}`
    : result?.platform
    ? `theme-${result.platform.toLowerCase()}`
    : "theme-auto";

  // Clean up progress intervals on unmount
  useEffect(() => {
    return () => {
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    };
  }, []);

  const startProgressAnimation = () => {
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    setProgressPercent(8);
    setCurrentStep(0);

    const startTime = Date.now();
    progressIntervalRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime;

      if (elapsed < 1400) {
        // Step 0: Checking link (8% to 28%)
        setCurrentStep(0);
        setProgressPercent((prev) => Math.min(28, prev + 2.2));
      } else if (elapsed < 3400) {
        // Step 1: Reading video info (28% to 62%)
        setCurrentStep(1);
        setProgressPercent((prev) => Math.min(62, prev + 1.8));
      } else if (elapsed < 6200) {
        // Step 2: Generating download link (62% to 88%)
        setCurrentStep(2);
        setProgressPercent((prev) => Math.min(88, prev + 1.2));
      } else {
        // Crawl slowly from 88% up to 94% waiting for server
        setCurrentStep(2);
        setProgressPercent((prev) => (prev < 94 ? prev + 0.15 : prev));
      }
    }, 120);
  };

  const handleGetVideo = async (overrideQuality = "720p") => {
    let cleanUrl = url.trim();
    if (cleanUrl && !/^https?:\/\//i.test(cleanUrl)) {
      cleanUrl = "https://" + cleanUrl;
    }

    setError("");
    setResult(null);
    setShowCelebration(false);

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
    startProgressAnimation();

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
          quality: overrideQuality,
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

      // Snap to Step 3 (Ready!) and 100%
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      setCurrentStep(3);
      setProgressPercent(100);
      setShowCelebration(true);

      const initialQuality = data.quality || overrideQuality || "720p";
      setSelectedQuality(initialQuality);
      setQualityDownloads({
        [initialQuality]: data.download_url,
      });

      // Show "Ready!" state with celebration for ~850ms before revealing Result Card
      setTimeout(() => {
        setLoading(false);
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
          media_badge: data.media_badge || (targetPlatform === "youtube" ? "YouTube Video" : "Instagram Reel"),
          qualities: data.qualities || [],
          message: data.message || "Video is ready for download.",
        });

        // Hide confetti after 1.2 seconds total
        setTimeout(() => setShowCelebration(false), 1200);
      }, 850);

    } catch (err) {
      clearTimeout(abortTimer);
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      setLoading(false);

      if (err.name === "AbortError") {
        setError("Request timed out. The server might be busy or waking up. Please try again.");
      } else if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
        setError("Backend server is unreachable. Please verify network connection or server status.");
      } else {
        setError(err.message || "Download could not be completed.");
      }
    }
  };

  const handleSelectQuality = async (qualityId) => {
    setSelectedQuality(qualityId);

    // If download URL is already cached for this quality, no need to re-fetch
    if (qualityDownloads[qualityId]) {
      return;
    }

    if (!result || !url) return;

    // Fetch this quality URL in background with lightweight feedback
    setIsSwitchingQuality(true);
    try {
      const endpoint = `${API_BASE_URL}/download`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify({
          platform: result.platform || "YouTube",
          url: url.trim(),
          quality: qualityId,
        }),
      });

      const data = await readApiResponse(response);
      if (response.ok && data.download_url) {
        setQualityDownloads((prev) => ({
          ...prev,
          [qualityId]: data.download_url,
        }));
        setResult((prev) => ({
          ...prev,
          downloadUrl: data.download_url,
          fileName: data.file_name || prev.fileName,
          filesize: data.filesize || prev.filesize,
        }));
      }
    } catch (e) {
      console.warn("Quality fetch fallback:", e);
    } finally {
      setIsSwitchingQuality(false);
    }
  };

  const handleDownloadFile = () => {
    try {
      if (!result) return;

      let fileUrl = qualityDownloads[selectedQuality] || result.downloadUrl;
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
      link.download = result.fileName || `saveall-${selectedQuality}.mp4`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      alert(err.message || "Download request failed.");
    }
  };

  const handleReset = () => {
    setUrl("");
    setResult(null);
    setError("");
    setProgressPercent(0);
    setCurrentStep(0);
    setShowCelebration(false);
    setQualityDownloads({});
  };

  const handlePaste = async () => {
    try {
      if (navigator?.clipboard?.readText) {
        const text = await navigator.clipboard.readText();
        if (text && text.trim()) {
          setUrl(text.trim());
          setError("");
          return;
        }
      }
      const promptText = window.prompt("Paste your video URL here:");
      if (promptText && promptText.trim()) {
        setUrl(promptText.trim());
        setError("");
      }
    } catch {
      const promptText = window.prompt("Clipboard permission not granted. Paste your link below:");
      if (promptText && promptText.trim()) {
        setUrl(promptText.trim());
        setError("");
      } else {
        setError("Clipboard access blocked. Please press Ctrl + V (or Cmd + V) in the input box.");
      }
    }
  };

  return (
    <div className={`app-wrapper ${activeTheme}`}>
      {/* 1-second Confetti Celebration Burst */}
      {showCelebration && <ConfettiShuriken />}

      {/* Atmospheric Ambient Glows */}
      <div className="ambient-glow ambient-glow-primary" aria-hidden="true" />
      <div className="ambient-glow ambient-glow-secondary" aria-hidden="true" />
      <div className="grid-overlay" aria-hidden="true" />

      {/* Header / Navbar */}
      <header className="cinematic-nav">
        <div className="nav-container">
          <div className="brand">
            <div className="brand-badge">
              <span className="brand-initial">Q</span>
            </div>
            <div className="brand-text">
              <span className="brand-title">Quick Download</span>
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
        {/* Requirement 1: Hero copy */}
        <h1 className="hero-headline">
          Save Your Favorite Videos in Seconds. <br />
          <span className="gradient-text">Without Any Ads.</span>
        </h1>

        <p className="hero-description">
          Paste any YouTube or Instagram link and download in HD. No pop-ups, no redirects, no sign-up.
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
                  : "Instagram & YouTube Downloader"}
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

            <label htmlFor="video-url-input" className="sr-only">
              Paste YouTube or Instagram Video URL
            </label>
            <input
              id="video-url-input"
              name="video-url"
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
              aria-label="Paste YouTube or Instagram link here"
              disabled={loading}
            />

            <div className="input-actions">
              {url && (
                <button
                  type="button"
                  className="action-icon-btn clear-btn"
                  onClick={handleReset}
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
                aria-label="Paste URL from clipboard"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
                  <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
                </svg>
                <span>Paste</span>
              </button>
            </div>
          </div>

          {/* Real-time detection feedback badge (Preserved green for detected states) */}
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

          {/* Requirement 2: Primary Action Fetch Button with contrast, white text on red/orange gradient, shuriken spinner */}
          <button
            type="button"
            className={`cinematic-cta-btn ${loading ? "is-loading" : ""} ${detectedPlatform ? `cta-${detectedPlatform}` : ""}`}
            onClick={() => handleGetVideo()}
            disabled={loading}
          >
            {loading ? (
              <div className="btn-loading-content">
                <ShurikenIcon className="btn-shuriken-spinner" />
                <span className="btn-loading-text">Fetching...</span>
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

          {/* Requirement 1: Small Trust Badges below Fetch button */}
          <TrustBadges />

          {/* Requirement 3: 4-Step Progress Card during loading */}
          {loading && (
            <ProgressCard
              currentStep={currentStep}
              progressPercent={progressPercent}
            />
          )}

          {/* Requirement 5: Themed Error Card */}
          {error && (
            <ErrorCard
              error={error}
              onRetry={() => handleGetVideo()}
              onDismiss={() => setError("")}
            />
          )}

          {/* Requirement 4: Result Card with dynamic quality options & download button */}
          {result && !loading && (
            <ResultCard
              result={result}
              selectedQuality={selectedQuality}
              onSelectQuality={handleSelectQuality}
              onDownload={handleDownloadFile}
              onReset={handleReset}
              isSwitchingQuality={isSwitchingQuality}
            />
          )}

          {/* Requirement 6: Footer Compliance Note */}
          <p className="compliance-note">
            <span className="lock-icon">🔒</span>
            <span>Use only content you own or have permission to download.</span>
          </p>
        </section>

        {/* Requirement 6: How It Works Section */}
        <HowItWorks />

        {/* Cinematic Feature Highlights Cards */}
        <div className="cinematic-features-grid">
          <div className="feature-card">
            <div className="feature-icon-bubble bubble-lightning">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </div>
            <h4>Blazing Acceleration</h4>
            <p>Multi-threaded stream extraction delivers high-definition files in seconds.</p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-bubble bubble-shield">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h4>Zero Ads & Pop-ups</h4>
            <p>Direct media streaming with no intrusive popups, adware, redirects or logins.</p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-bubble bubble-device">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
                <line x1="12" y1="18" x2="12.01" y2="18" />
              </svg>
            </div>
            <h4>Universal Responsive</h4>
            <p>Seamlessly responsive across iPhones, Android devices, tablets, and 4K desktops.</p>
          </div>
        </div>
      </main>

      {/* Cinematic Site Footer */}
      <footer className="cinematic-footer">
        <div className="footer-content">
          <div className="footer-brand-line">
            <div className="footer-logo">
              <span className="footer-logo-box">Q</span>
              <span className="footer-logo-title">Quick Download</span>
            </div>
            <p className="footer-tagline">
              Instagram & YouTube Downloader <span>•</span> Fast • Pure • Secure
            </p>
          </div>

          {/* Compliance notice in footer */}
          <p className="footer-compliance-text">
            ⚠️ Disclaimer: Use only content you own or have permission to download. We respect content creators and intellectual property rights.
          </p>

          <div className="footer-divider-glow" />

          {/* Creator Credit */}
          <div className="creator-block">
            <span className="credit-label">Engineered & Designed by</span>
            <h3 className="creator-title">{SITE_CONFIG.creatorName}</h3>
            <span className="brand-chip">{SITE_CONFIG.brandName}</span>
          </div>

          {/* Social Links */}
          <div className="social-links-deck">
            <a
              href={SITE_CONFIG.social.instagram}
              target="_blank"
              rel="noopener noreferrer"
              className="cinematic-social-btn"
              aria-label="Follow on Instagram"
              title="Instagram"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/>
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>
                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/>
              </svg>
              <span className="sr-only">Instagram</span>
              <span className="social-tooltip">Instagram</span>
            </a>

            <a
              href={SITE_CONFIG.social.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              className="cinematic-social-btn"
              aria-label="Connect on LinkedIn"
              title="LinkedIn"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
                <rect x="2" y="9" width="4" height="12" />
                <circle cx="4" cy="4" r="2" />
              </svg>
              <span className="sr-only">LinkedIn</span>
              <span className="social-tooltip">LinkedIn</span>
            </a>

            <a
              href={`mailto:${SITE_CONFIG.social.email}`}
              className="cinematic-social-btn"
              aria-label="Send Email"
              title="Email"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
              <span className="sr-only">Email</span>
              <span className="social-tooltip">Email</span>
            </a>

            <a
              href={SITE_CONFIG.social.github}
              target="_blank"
              rel="noopener noreferrer"
              className="cinematic-social-btn"
              aria-label="View GitHub Profile"
              title="GitHub"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
              </svg>
              <span className="sr-only">GitHub</span>
              <span className="social-tooltip">GitHub</span>
            </a>
          </div>

          <div className="footer-bottom-copy">
            <p>© 2026 Quick Download. All rights reserved.</p>
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