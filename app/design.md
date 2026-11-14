# Design: Railway Reservation System

The locked system for the Flask app. Routes keep their existing content and behavior; the search, booking, account, and schedule screens share these tokens and surfaces.

## System
- Genre: editorial
- Shape of the first screen: app screen
- Theme: Editorial, keeping the forest green palette and existing type; translucent glass is the requested variation
- Axes: warm light paper / condensed display / forest green accent · restrained
- Image: `static/images/scenic-railway.webp` leads the search screen and supports account and run screens
- Signature: the journey search panel layered over the railway photograph

## Tokens
`static/tokens.css` is the source of truth. The role values:

```css
:root {
  --color-paper: oklch(98% 0.009 96);
  --color-paper-2: oklch(96% 0.012 112);
  --color-paper-3: oklch(93% 0.016 132);
  --color-ink: oklch(23% 0.035 155);
  --color-ink-2: oklch(34% 0.025 150);
  --color-muted: oklch(48% 0.018 142);
  --color-rule: oklch(86% 0.018 145);
  --color-accent: oklch(43% 0.115 151);
  --color-accent-ink: oklch(98% 0.008 96);
  --color-focus: oklch(44% 0.16 151);
  --font-display: "Bricolage Grotesque", ui-sans-serif, sans-serif;
  --font-body: "Source Serif 4", ui-serif, Georgia, serif;
  --radius-card: 22px;
  --radius-pill: 999px;
  --rule-hair: 1px;
  --shadow-float: 0 16px 28px -18px var(--color-shadow);
}
```

Spacing, type, timing, glass, image, and responsive tokens also live in `static/tokens.css`.

## Controls
- Primary: forest green fill · pill radius · 44px minimum height
- Secondary: paper surface with a green-aware outline · same height
- Inputs: 48px, labeled, with an instant focus ring
- Station pickers: custom accessible listboxes mirror the native selects; the original selects remain the no-script fallback and submitted values

## Motion
- Character: calm; feedback is limited to control state changes
- Reduced motion removes transitions and smooth scrolling

## Exports
`static/tokens.css` in this project.
