/**
 * VesselHero — a cinematic offshore oil & gas scene used behind the login.
 * Inline SVG (no external asset): dusk sky, warm sun glow near the horizon,
 * an offshore production platform with a flare stack, and a support vessel,
 * all rim-lit in the Vaalco orange. Layered gradients + vignette + grain give
 * it depth. Purely decorative.
 */
export default function VesselHero({ className = "" }: { className?: string }) {
  return (
    <div className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`} aria-hidden="true">
      <svg
        className="h-full w-full"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#050b12" />
            <stop offset="42%" stopColor="#0a2233" />
            <stop offset="70%" stopColor="#123246" />
            <stop offset="86%" stopColor="#1d3f4f" />
            <stop offset="100%" stopColor="#274c58" />
          </linearGradient>
          <radialGradient id="sun" cx="62%" cy="86%" r="46%">
            <stop offset="0%" stopColor="#e8563f" stopOpacity="0.55" />
            <stop offset="26%" stopColor="#d9773c" stopOpacity="0.28" />
            <stop offset="60%" stopColor="#d99a3c" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#d99a3c" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="ocean" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#173a48" />
            <stop offset="18%" stopColor="#0e2833" />
            <stop offset="100%" stopColor="#05131a" />
          </linearGradient>
          <linearGradient id="reflection" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#e8563f" stopOpacity="0.34" />
            <stop offset="100%" stopColor="#e8563f" stopOpacity="0" />
          </linearGradient>
          <radialGradient id="vignette" cx="50%" cy="46%" r="75%">
            <stop offset="55%" stopColor="#000000" stopOpacity="0" />
            <stop offset="100%" stopColor="#000000" stopOpacity="0.62" />
          </radialGradient>
          <filter id="soft"><feGaussianBlur stdDeviation="3" /></filter>
        </defs>

        {/* sky + sun glow */}
        <rect width="1440" height="620" fill="url(#sky)" />
        <rect width="1440" height="720" fill="url(#sun)" />

        {/* faint stars */}
        <g fill="#cdd6db" opacity="0.5">
          <circle cx="180" cy="90" r="1.1" /><circle cx="360" cy="150" r="0.9" />
          <circle cx="520" cy="70" r="1" /><circle cx="900" cy="110" r="0.9" />
          <circle cx="1120" cy="80" r="1.1" /><circle cx="1290" cy="150" r="0.9" />
          <circle cx="720" cy="60" r="0.8" /><circle cx="1010" cy="180" r="0.8" />
        </g>

        {/* ocean */}
        <rect y="560" width="1440" height="340" fill="url(#ocean)" />
        {/* sun reflection streak on the water */}
        <rect x="812" y="560" width="120" height="300" fill="url(#reflection)" filter="url(#soft)" />

        {/* --- Offshore production platform (right), rim-lit --- */}
        <g fill="#040a0e">
          {/* legs */}
          <rect x="1046" y="470" width="10" height="110" transform="skewX(-4)" />
          <rect x="1096" y="470" width="10" height="110" transform="skewX(-4)" />
          <rect x="1150" y="470" width="10" height="110" transform="skewX(-4)" />
          {/* deck */}
          <rect x="1020" y="430" width="176" height="44" rx="3" />
          {/* modules */}
          <rect x="1036" y="398" width="46" height="34" />
          <rect x="1092" y="386" width="40" height="46" />
          <rect x="1146" y="406" width="34" height="26" />
          {/* derrick */}
          <path d="M1104 386 L1112 320 L1122 320 L1130 386 Z" />
          {/* flare boom + flame */}
          <rect x="1188" y="424" width="86" height="6" transform="rotate(-10 1188 424)" />
        </g>
        {/* flare flame */}
        <path d="M1258 372 q10 -20 2 -34 q16 12 12 30 q10 -6 8 -20 q12 20 -4 40 q-14 10 -26 -2 q6 -6 8 -14 Z"
              fill="#e8563f" opacity="0.9" filter="url(#soft)" />
        {/* platform rim light (orange top edges) */}
        <g stroke="#e8563f" strokeOpacity="0.5" strokeWidth="1.4" fill="none">
          <path d="M1020 431 h176" /><path d="M1092 386 h40" />
        </g>

        {/* --- Support vessel (center-left), rim-lit --- */}
        <g fill="#050c11">
          {/* hull */}
          <path d="M470 556 q6 26 40 30 h300 q30 -2 44 -30 l-14 -2 H484 Z" />
          {/* raised bow deck */}
          <rect x="474" y="536" width="120" height="22" rx="2" />
          {/* superstructure / bridge */}
          <rect x="500" y="502" width="70" height="36" rx="2" />
          <rect x="512" y="486" width="30" height="18" />
          {/* mast */}
          <rect x="524" y="452" width="4" height="36" />
          {/* aft crane */}
          <path d="M700 540 v-52 h6 v52 Z" />
          <path d="M703 490 l70 26 l-2 6 l-70 -24 Z" />
          {/* containers on aft deck */}
          <rect x="620" y="524" width="30" height="16" /><rect x="654" y="524" width="30" height="16" />
          <rect x="620" y="540" width="64" height="14" />
        </g>
        {/* vessel rim light + deck lights */}
        <g stroke="#e8563f" strokeOpacity="0.45" strokeWidth="1.2" fill="none">
          <path d="M500 502 h70" /><path d="M474 536 h120" />
        </g>
        <g fill="#ffd9a0" opacity="0.9">
          <circle cx="536" cy="512" r="1.4" /><circle cx="556" cy="512" r="1.4" />
          <circle cx="524" cy="494" r="1.2" />
        </g>

        {/* horizon haze + gentle waves */}
        <rect y="556" width="1440" height="3" fill="#2a5563" opacity="0.5" filter="url(#soft)" />
        <g stroke="#2f5c6b" strokeOpacity="0.35" strokeWidth="1.5" fill="none">
          <path d="M120 640 q40 -8 80 0 t80 0" /><path d="M980 690 q50 -10 100 0 t100 0" />
          <path d="M300 760 q60 -10 120 0 t120 0" />
        </g>

        {/* vignette */}
        <rect width="1440" height="900" fill="url(#vignette)" />
      </svg>

      {/* film grain + ambient depth */}
      <div className="hero-grain absolute inset-0" />
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 80% at 50% 120%, rgba(5,11,18,0) 40%, rgba(3,7,12,0.9) 100%)"
        }}
      />
    </div>
  );
}
