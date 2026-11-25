# CROWDPatrol 2.0 — Design System Specification

**Product:** CROWDPatrol  
**Design Philosophy:** "Linear Precision meets Awwwards Cinematic Surveillance"  
**Version:** 2.0.0-PROPOSED  
**Date:** November 23, 2026  

---

## 1. Design Token Architecture

The CROWDPatrol visual identity combines deep nocturnal surveillance backgrounds, high-contrast crisp typography, electric neon illumination, and disciplined glass surfaces.

### 1.1 Color Tokens

```css
:root {
  /* Surfaces & Backgrounds */
  --cp-bg-main:         #050816; /* Deep Midnight Navy */
  --cp-bg-secondary:    #080F20; /* Dark Obsidian Slate */
  --cp-surface-elevated:#101B30; /* Elevated Surface / Container */
  --cp-surface-glass:   rgba(16, 27, 48, 0.72);
  --cp-surface-overlay: rgba(5, 8, 22, 0.88);

  /* Primary Brand Accents */
  --cp-blue-primary:    #2563EB; /* Command Center Cobalt */
  --cp-blue-hover:      #1D4ED8;
  --cp-cyan-electric:   #00D9FF; /* Telemetry Electric Cyan */
  --cp-cyan-glow:       rgba(0, 217, 255, 0.28);
  --cp-violet-accent:   #8B5CF6; /* AI / Predictive Violet */
  --cp-violet-glow:     rgba(139, 92, 246, 0.25);

  /* Semantic Alert Indicators */
  --cp-status-low:      #10B981; /* Emerald Safe */
  --cp-status-medium:   #F59E0B; /* Amber Caution */
  --cp-status-high:     #EF4444; /* Crimson Danger */
  --cp-status-critical: #DC2626; /* Flashing Emergency Red */

  /* Typography Colors */
  --cp-text-primary:    #EAF4FF; /* Crisp Off-White */
  --cp-text-secondary:  #94A3B8; /* Muted Slate */
  --cp-text-tertiary:   #64748B; /* Subdued Meta */
  --cp-text-disabled:   #475569;

  /* Borders & Dividers */
  --cp-border-subtle:   rgba(59, 130, 246, 0.16);
  --cp-border-active:   rgba(0, 217, 255, 0.45);
  --cp-border-critical: rgba(239, 68, 68, 0.60);
}
```

---

## 2. Typography Scale

```css
/* Fonts */
--cp-font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--cp-font-mono: 'JetBrains Mono', 'Fira Code', monospace;

/* Type Scale */
--cp-text-xs:   0.75rem  /* 12px - Telemetry Badges, Footers */;
--cp-text-sm:   0.875rem /* 14px - Body Secondary, Table Data */;
--cp-text-base: 1.0rem   /* 16px - Default Body Text, Form Inputs */;
--cp-text-lg:   1.125rem /* 18px - Card Titles, Metric Headers */;
--cp-text-xl:   1.25rem  /* 20px - Section Subheadings */;
--cp-text-2xl:  1.5rem   /* 24px - Section Headings */;
--cp-text-3xl:  1.875rem /* 30px - Dashboard Overview Metrics */;
--cp-text-4xl:  2.25rem  /* 36px - Modal Headers, Feature Titles */;
--cp-text-6xl:  3.75rem  /* 60px - Cinematic Hero Headline */;
```

---

## 3. Spatial & Surface Hierarchy

Glassmorphism is applied **selectively to command headers, HUD overlays, and metric stat cards**. Heavy data tables and dense camera grids use solid elevated surfaces (`#101B30`) to guarantee contrast and 60 FPS scrolling.

```
┌────────────────────────────────────────────────────────┐
│ Glass Layer: backdrop-filter: blur(12px)               │
│ - Navbar, Active Camera HUD, Floating Alert Modals     │
├────────────────────────────────────────────────────────┤
│ Elevated Surface Layer: #101B30, border: 1px subtle    │
│ - Camera Grid Panels, Telemetry Data Cards, Forms      │
├────────────────────────────────────────────────────────┤
│ Secondary Base: #080F20                                │
│ - Section Enclosures, Sidebar Navigation Container     │
├────────────────────────────────────────────────────────┤
│ Foundation Base: #050816                               │
│ - Viewport Canvas, Canvas Backdrop                     │
└────────────────────────────────────────────────────────┘
```

---

## 4. Reusable Component Specifications

### 4.1 Buttons

```css
/* Primary Action Button (Electric Cyan Glow) */
.cp-btn-primary {
  background: linear-gradient(135deg, #2563EB 0%, #00D9FF 100%);
  color: #050816;
  font-weight: 700;
  border-radius: 8px;
  padding: 10px 20px;
  border: none;
  box-shadow: 0 0 16px rgba(0, 217, 255, 0.35);
  transition: all 0.2s ease-in-out;
}
.cp-btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 24px rgba(0, 217, 255, 0.55);
}

/* Secondary Button (Bordered Surface) */
.cp-btn-secondary {
  background: rgba(16, 27, 48, 0.8);
  color: #EAF4FF;
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
  padding: 10px 20px;
}

/* Danger / Emergency Button */
.cp-btn-danger {
  background: linear-gradient(135deg, #B91C1C 0%, #EF4444 100%);
  color: #FFFFFF;
  box-shadow: 0 0 16px rgba(239, 68, 68, 0.4);
}
```

### 4.2 Status & Alert Badges

| Badge Type | Background | Border | Text Color | Pulse Animation |
| :--- | :--- | :--- | :--- | :---: |
| **Normal / Safe** | `rgba(16, 185, 129, 0.12)` | `#10B981` | `#10B981` | No |
| **Medium Risk** | `rgba(245, 158, 11, 0.15)` | `#F59E0B` | `#F59E0B` | Subtle |
| **High Risk** | `rgba(239, 68, 68, 0.20)` | `#EF4444` | `#EF4444` | Active |
| **Critical / Emergency**| `rgba(220, 38, 38, 0.35)` | `#DC2626` | `#FF8888` | Rapid Glow Pulse |

### 4.3 Surveillance CCTV Grid Panel
- **Border:** `1px solid rgba(59, 130, 246, 0.25)`
- **Header HUD Overlay:** Floating top strip with Camera ID (`CAM-01`), Sector Name, live FPS, active person count, and risk dot.
- **Standby State:** Clean dark slate container with centered status icon, reconnection button, and source telemetry.

### 4.4 Organization Switcher Pill
- Positioned in dashboard header navigation.
- Shows current active organization name and badge (e.g. `🏢 AMC Engineering College`).
- Dropdown menu allows quick switching between authorized tenants for multi-org users.

---

## 5. Accessibility & Motion Rules

1. **Reduced Motion (`@media (prefers-reduced-motion: reduce)`):**
   - Disables hero floating particle drifts and parallax scroll offsets.
   - Transitions drop from ease curves to instant 0.05s cuts.
2. **Contrast Standard:**
   - Text ratio against `#050816` and `#101B30` exceeds WCAG AAA (7:1) for primary text (`#EAF4FF`) and WCAG AA (4.5:1) for secondary text (`#94A3B8`).
3. **Operational Clarity:**
   - Visual effects never obscure camera resolution, detection bounding boxes, tracking IDs, or alert timestamps.
