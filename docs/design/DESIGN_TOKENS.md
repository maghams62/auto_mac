# Design Tokens & Motion Guidelines

## Overview

This document outlines the design token system, motion rules, glass effect usage, and animation best practices for the Glass OS skin redesign.

## Design Token System

### Location
All design tokens are centralized in `frontend/lib/theme/tokens.ts`.

### Token Categories

#### Colors
- **Dark Mode**: Primary palette with glass effect values
- **Light Mode**: Parallel light mode tokens (ready for future theme toggle)
- **Semantic Colors**: Success, danger, warning variants with background and border values

#### Typography
- **Font Families**: 
  - Sans: Inter, SF Pro Display, system fallbacks
  - Mono: JetBrains Mono, SF Mono, system fallbacks
- **Font Sizes**: xs (12px) through 4xl (32px)
- **Font Weights**: normal (400), medium (500), semibold (600), bold (700)
- **Line Heights**: tight (1.2), normal (1.4), relaxed (1.6)

#### Spacing
- Base unit: 4px
- Scale: 0, 1 (4px), 2 (8px), 3 (12px), 4 (16px), 5 (20px), 6 (24px), 8 (32px), etc.

#### Radii
- sm: 8px
- md: 12px
- lg: 16px
- xl: 20px
- full: 9999px

#### Shadows
- **soft**: `0 4px 6px -1px rgba(0, 0, 0, 0.3)`
- **medium**: `0 10px 15px -3px rgba(0, 0, 0, 0.35)`
- **elevated**: `0 20px 60px rgba(0, 0, 0, 0.35)`
- **glow**: Primary and secondary glow effects
- **inset**: Top border and full border inset shadows

#### Glass Effects
- **Blur**: sm (14px), md (20px), lg (32px)
- **Opacity**: base (0.82), elevated (0.95)
- **Backgrounds**: 
  - `rgba(18, 18, 18, 0.82)` for base glass
  - `rgba(255, 255, 255, 0.04)` for assistant messages
  - `rgba(255, 255, 255, 0.02)` for user messages

### Usage

```typescript
import { useThemeTokens } from "@/lib/theme/tokens";

const tokens = useThemeTokens("dark");
// Access: tokens.colors, tokens.radii, tokens.spacing, etc.
```

## Motion System

### Location
Animation utilities are centralized in `frontend/lib/motion.ts`.

### Easing Curves

- **default**: `cubic-bezier(0.25, 0.1, 0.25, 1)` - Standard smooth easing
- **smooth**: `cubic-bezier(0.4, 0, 0.2, 1)` - Material Design easing
- **outExpo**: `cubic-bezier(0.19, 1, 0.22, 1)` - Exponential ease-out
- **bounceSoft**: `cubic-bezier(0.68, -0.55, 0.265, 1.55)` - Subtle bounce

### Duration Constants

All durations are in seconds:
- **fast**: 0.1s (100ms) - Micro-interactions
- **normal**: 0.15s (150ms) - Standard transitions
- **slow**: 0.2s (200ms) - Larger transitions
- **slower**: 0.3s (300ms) - Modal/overlay entrances

**Rule**: Micro-interactions MUST be ≤ 200ms for optimal UX.

### Animation Variants

Pre-built Framer Motion variants:
- `fadeIn` - Simple opacity fade
- `slideUp` - Slide up with fade (4px translate)
- `slideDown` - Slide down with fade (20px translate)
- `slideInFromRight` - Slide from right (20px translate)
- `slideInFromBottom` - Slide from bottom (20px translate)
- `scaleIn` - Scale from 0.95 to 1 with fade
- `messageEntrance` - Message bubble entrance (4px translate, 100ms)
- `toastSlideIn` - Toast notification entrance
- `overlayFade` - Modal backdrop fade
- `modalSlideDown` - Modal slide down entrance
- `staggerContainer` - Stagger children animations

### Usage

```typescript
import { messageEntrance, duration, easing } from "@/lib/motion";

<motion.div
  initial="hidden"
  animate="visible"
  variants={messageEntrance}
>
  Content
</motion.div>
```

## Glass Effect Usage

### Base Glass Class

```css
.glass {
  background: rgba(18, 18, 18, 0.82);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05);
}
```

### Tailwind Utilities

- `bg-glass` - Base glass background
- `bg-glass-assistant` - Assistant message background
- `bg-glass-user` - User message background
- `bg-glass-elevated` - Elevated glass background
- `backdrop-blur-glass` - 14px backdrop blur
- `backdrop-blur-glass-md` - 20px backdrop blur
- `backdrop-blur-glass-lg` - 32px backdrop blur
- `shadow-inset-border` - Inset border shadow

### Best Practices

1. **Always use backdrop-filter** with `-webkit-backdrop-filter` fallback
2. **Combine with inset borders** via `box-shadow` for soft edges
3. **Use elevated backgrounds** for modals and overlays (higher opacity)
4. **Apply shadows** for depth (`shadow-elevated` for cards)

## Animation Best Practices

### Performance

1. **Use transform and opacity only** - These properties are GPU-accelerated
2. **Avoid animating** `width`, `height`, `top`, `left` - Causes layout reflow
3. **Use `will-change` sparingly** - Only for elements actively animating

### Timing

1. **Micro-interactions**: 100-150ms
2. **Standard transitions**: 150-200ms
3. **Modal entrances**: 200-300ms
4. **Page transitions**: 300ms+

### Easing

1. **Default**: Use `easing.default` for most animations
2. **Entrances**: Use `easing.outExpo` for dramatic entrances
3. **Bounces**: Use `easing.bounceSoft` for playful interactions
4. **Avoid**: Linear easing (except for specific cases like shimmer)

### Accessibility

1. **Respect `prefers-reduced-motion`**:
```typescript
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
```

2. **Provide alternative feedback** for users who disable animations
3. **Keep animations subtle** - Don't distract from content

## Component Patterns

### Message Entrance

```typescript
import { messageEntrance } from "@/lib/motion";

<motion.div variants={messageEntrance}>
  Message content
</motion.div>
```

### Toast Notification

```typescript
import { toastSlideIn } from "@/lib/motion";

<motion.div
  initial="hidden"
  animate="visible"
  exit="exit"
  variants={toastSlideIn}
>
  Toast content
</motion.div>
```

### Modal Overlay

```typescript
import { overlayFade, modalSlideDown } from "@/lib/motion";

<motion.div variants={overlayFade}>
  <motion.div variants={modalSlideDown}>
    Modal content
  </motion.div>
</motion.div>
```

## Typography Guidelines

### Font Stacks

- **Sans**: `"Inter", "SF Pro Display", system-ui, -apple-system, sans-serif`
- **Mono**: `"JetBrains Mono", "SF Mono", Menlo, Monaco, monospace`

### Usage

- **Assistant messages**: `font-medium` (500 weight)
- **User commands**: `font-mono` with `text-sm`
- **Timestamps**: `text-xs` (12px), `rgba(255, 255, 255, 0.45)`
- **Line height**: `leading-[1.4]` globally

## Color Usage

### Text Colors

- **Primary**: `text-text-primary` - Main content
- **Muted**: `text-text-muted` - Secondary content
- **Subtle**: `text-text-subtle` - Tertiary content
- **Timestamp**: `rgba(255, 255, 255, 0.45)` - Timestamps

### Accent Colors

- **Primary**: `text-accent-primary` - Interactive elements
- **Success**: `text-accent-success` - Success states
- **Danger**: `text-accent-danger` - Error states
- **Warning**: `text-accent-warning` - Warning states

## Shadow Usage

### Elevation Levels

1. **Soft**: Cards, subtle elevation
2. **Medium**: Hover states, interactive elements
3. **Elevated**: Modals, overlays, floating elements
4. **Glow**: Focus states, active elements

### Inset Shadows

- **Top border**: `shadow-inset-top` - Subtle top highlight
- **Full border**: `shadow-inset-border` - Soft edge definition

## Future Considerations

### Theme Toggle

The token system is structured to support light mode:
- Light mode tokens are defined but not activated
- Theme context structure is ready for implementation
- Switching palettes will be trivial once activated

### Accessibility

- All tokens support high contrast modes
- Color contrast ratios meet WCAG AA standards
- Motion respects `prefers-reduced-motion`

## References

- **Design Inspiration**: shadcn/ui, Linear, Raycast
- **Animation Inspiration**: Linear, Framer Motion examples
- **Glass Effect**: Linear app, macOS Big Sur design language

