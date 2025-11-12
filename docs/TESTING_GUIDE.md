# UI Testing Guide - Glass OS Skin

## Overview

This guide provides a comprehensive testing checklist to verify all Glass OS skin features, animations, and interactions are working correctly.

## Pre-Testing Setup

1. **Start the development server**:
   ```bash
   cd frontend
   npm run dev
   ```

2. **Open the application** in your browser (typically `http://localhost:3000`)

3. **Enable browser DevTools** to inspect elements and check console for errors

## Visual Design Verification

### 1. Glass Effect Styling

#### Chat Interface
- [ ] Empty state shows glass card with backdrop blur
- [ ] Glass card has subtle inset border (soft white edge)
- [ ] Background is semi-transparent (`rgba(18, 18, 18, 0.82)`)
- [ ] Backdrop blur is visible (14px blur)

#### Message Bubbles
- [ ] Assistant messages have `rgba(255, 255, 255, 0.04)` background
- [ ] User messages have `rgba(255, 255, 255, 0.02)` background
- [ ] Both have backdrop blur and inset borders
- [ ] No thick borders visible (only subtle inset shadows)

#### Input Area
- [ ] Input container has glass styling
- [ ] Glass effect visible on focus (border glow)
- [ ] Slash command palette has glass styling
- [ ] Palette items have hover states with glass backgrounds

### 2. Typography

#### Font Stacks
- [ ] Assistant text uses Inter/SF Pro Display (font-medium, 500 weight)
- [ ] User commands use JetBrains Mono (monospace)
- [ ] Line height is 1.4 globally
- [ ] Timestamps are 12px, `rgba(255, 255, 255, 0.45)`

#### Text Rendering
- [ ] User messages render in monospace font
- [ ] Assistant messages have medium font weight
- [ ] Links are clickable and styled correctly
- [ ] Code blocks (if any) use monospace font

### 3. Shadows & Elevation

- [ ] Elevated cards use `shadow-elevated` (0 20px 60px rgba(0,0,0,0.35))
- [ ] Modals and overlays have elevated shadows
- [ ] Toast notifications have elevated shadows
- [ ] Inset borders visible on glass elements

## Animation Testing

### 4. Message Animations

#### Message Entrance
- [ ] New messages slide up 4px with fade-in
- [ ] Animation duration is ~100ms (fast, smooth)
- [ ] No jank or stuttering during animation
- [ ] Multiple messages animate smoothly in sequence

#### Timestamp Hover
- [ ] Timestamps are hidden by default (opacity 0)
- [ ] Timestamps appear on message hover (opacity 1)
- [ ] Transition is smooth (150ms duration)
- [ ] Works for both user and assistant messages

### 5. Status & Typing Indicators

#### StatusRow Component
- [ ] Status pills show shimmer effect (animated gradient)
- [ ] Three dots bounce with staggered timing
- [ ] Bounce animation uses soft easing curve
- [ ] Shimmer animation loops continuously

#### TypingIndicator
- [ ] Shows shimmer background effect
- [ ] Three dots animate with bounce effect
- [ ] Animation is smooth and continuous
- [ ] Uses glass styling (backdrop blur, inset border)

### 6. Toast Notifications

#### Toast Appearance
- [ ] Toasts slide in from bottom-right
- [ ] Animation duration is ~150ms
- [ ] Toasts have glass styling with backdrop blur
- [ ] Success toasts show green styling
- [ ] Error toasts show red styling
- [ ] Warning toasts show yellow styling
- [ ] Info toasts show default glass styling

#### Toast Behavior
- [ ] Toasts auto-dismiss after 3 seconds
- [ ] Multiple toasts stack vertically
- [ ] Dismiss button works correctly
- [ ] Toast exit animation is smooth

### 7. Modal & Overlay Animations

#### Help Overlay
- [ ] Backdrop fades in smoothly
- [ ] Modal slides down from top
- [ ] Animation duration is ~300ms
- [ ] Close button works (Esc key or click)
- [ ] Backdrop click closes overlay

#### Keyboard Shortcuts Overlay
- [ ] Same animation pattern as Help Overlay
- [ ] Opens with smooth entrance
- [ ] Closes with smooth exit

### 8. Scroll & Interaction Animations

#### Scroll to Bottom Button
- [ ] Button appears when scrolled up
- [ ] Button fades in smoothly
- [ ] Button fades out when at bottom
- [ ] Click scrolls smoothly to bottom
- [ ] Button has glass styling

#### Input Area Interactions
- [ ] Keyboard shortcut hint appears on hover
- [ ] Hint shows "⌘ Enter to send"
- [ ] Focus state shows accent border glow
- [ ] Slash command palette animates smoothly

## Component Functionality

### 9. Help System

#### Help Overlay (`⌘/` or `⌘?`)
- [ ] Opens with keyboard shortcut
- [ ] Opens with `/help` command
- [ ] Search functionality works
- [ ] Category filters work
- [ ] Keyboard navigation (↑↓) works
- [ ] Enter selects command
- [ ] Esc closes overlay
- [ ] Commands display with icons and descriptions

#### Keyboard Shortcuts Overlay (`?` key)
- [ ] Opens when `?` pressed (input not focused)
- [ ] Shows all keyboard shortcuts
- [ ] Grouped by category
- [ ] Esc closes overlay
- [ ] Click outside closes overlay

#### Slash Command Palette
- [ ] Appears when typing `/`
- [ ] Shows filtered commands as you type
- [ ] Arrow keys navigate selection
- [ ] Enter selects command
- [ ] Tab selects command
- [ ] Shows "Press ? for help" hint
- [ ] Has glass styling

### 10. Timeline & Plan Messages

#### TimelineStep Component
- [ ] Plan messages show as pill chips
- [ ] Steps separated by ▸ symbol
- [ ] Active step highlighted with accent color
- [ ] Active step has pulsing dot indicator
- [ ] Smooth transitions between states
- [ ] Goal displays at top if present

### 11. Toast Integration

#### Delivery Events
- [ ] Email sent triggers success toast
- [ ] File saved triggers success toast
- [ ] Message sent triggers success toast
- [ ] Draft saved triggers warning toast
- [ ] Toasts appear automatically
- [ ] Multiple toasts stack correctly

## Keyboard Shortcuts Testing

### 12. Global Shortcuts

- [ ] `⌘K` or `Ctrl+K` focuses input
- [ ] `⌘L` or `Ctrl+L` clears input
- [ ] `⌘Enter` or `Ctrl+Enter` sends message
- [ ] `Shift+Enter` creates new line
- [ ] `⌘/` or `⌘?` opens help overlay
- [ ] `?` (when input not focused) opens shortcuts
- [ ] `Esc` closes overlays/modals

### 13. Slash Command Palette Shortcuts

- [ ] `↑` navigates up in palette
- [ ] `↓` navigates down in palette
- [ ] `Enter` selects highlighted command
- [ ] `Tab` selects highlighted command
- [ ] Typing filters commands

## Performance Testing

### 14. Animation Performance

- [ ] All animations use GPU acceleration (check DevTools)
- [ ] No layout shifts during animations
- [ ] Smooth 60fps animations
- [ ] No jank when scrolling
- [ ] Multiple messages animate smoothly

### 15. Rendering Performance

- [ ] Large message lists render efficiently
- [ ] Glass effects don't cause performance issues
- [ ] Backdrop blur doesn't lag
- [ ] Toast stack doesn't slow down UI

## Browser Compatibility

### 16. Cross-Browser Testing

#### Chrome/Edge
- [ ] All features work correctly
- [ ] Backdrop blur works
- [ ] Animations are smooth

#### Firefox
- [ ] All features work correctly
- [ ] Backdrop blur works (may need fallback)
- [ ] Animations are smooth

#### Safari
- [ ] All features work correctly
- [ ] Backdrop blur works
- [ ] Animations are smooth
- [ ] WebKit prefixes work

## Accessibility Testing

### 17. Keyboard Navigation

- [ ] All interactive elements keyboard accessible
- [ ] Focus indicators visible
- [ ] Tab order is logical
- [ ] Esc closes modals/overlays

### 18. Screen Reader Support

- [ ] ARIA labels present on interactive elements
- [ ] Modal announcements work
- [ ] Toast announcements work
- [ ] Status messages announced

### 19. Reduced Motion

- [ ] Test with `prefers-reduced-motion: reduce`
- [ ] Animations respect user preference
- [ ] Essential functionality still works

## Edge Cases

### 20. Error Handling

- [ ] WebSocket disconnection shows error state
- [ ] Invalid commands show appropriate feedback
- [ ] Network errors handled gracefully
- [ ] Toast errors display correctly

### 21. Empty States

- [ ] Empty chat shows glass welcome card
- [ ] Empty search results show message
- [ ] Empty command palette shows message

### 22. Long Content

- [ ] Long messages wrap correctly
- [ ] Long command names truncate with ellipsis
- [ ] Scroll works with many messages
- [ ] Performance remains good

## Visual Regression

### 23. Layout Consistency

- [ ] Spacing is consistent (4px base unit)
- [ ] Border radius matches tokens (12px, 16px)
- [ ] Colors match token values
- [ ] Shadows match token values
- [ ] Typography matches specifications

### 24. Responsive Design

- [ ] Layout works on mobile (if applicable)
- [ ] Glass effects scale appropriately
- [ ] Modals/overlays work on small screens
- [ ] Touch interactions work (if applicable)

## Integration Testing

### 25. Component Integration

- [ ] ToastProvider wraps app correctly
- [ ] ToastStack renders in layout
- [ ] HelpOverlay integrates with ChatInterface
- [ ] ScrollToBottom integrates with messages container
- [ ] All components use motion utilities consistently

### 26. State Management

- [ ] Toast state persists correctly
- [ ] Help overlay state manages correctly
- [ ] Scroll position tracked correctly
- [ ] Message state updates correctly

## Quick Test Checklist

For a quick smoke test, verify these critical features:

1. ✅ Glass effect visible on messages and input
2. ✅ Messages animate in smoothly
3. ✅ Timestamps appear on hover
4. ✅ `⌘/` opens help overlay
5. ✅ `?` opens shortcuts overlay
6. ✅ Toasts appear for delivery events
7. ✅ Scroll to bottom button works
8. ✅ Typing indicator shows shimmer
9. ✅ Status messages show animated pills
10. ✅ Plan messages show timeline chips

## Reporting Issues

When reporting issues, include:

1. **Browser and version**
2. **Operating system**
3. **Steps to reproduce**
4. **Expected behavior**
5. **Actual behavior**
6. **Screenshots/videos** (if visual issue)
7. **Console errors** (if any)
8. **Performance metrics** (if performance issue)

## Known Issues & Limitations

- Backdrop blur may not work in older browsers (fallback: solid background)
- Some animations may be disabled if user has `prefers-reduced-motion` enabled
- Toast auto-dismiss may be delayed if browser tab is inactive

## Next Steps After Testing

1. Document any issues found
2. Verify fixes work across browsers
3. Test with real user workflows
4. Gather performance metrics
5. Update documentation if needed

