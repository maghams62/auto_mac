# UI/UX Fixes - Manual Test Cases

## Test Environment Setup
- Browser: Chrome/Safari/Firefox
- Frontend running: `npm run dev` in `frontend/` directory
- Backend running: `./start_ui.sh` or `python api_server.py`
- Screen resolution: Test at 1920x1080 and 1280x720

---

## Test Case 1: Voice Recorder Modal - Scroll Positioning

### Objective
Verify that the voice recorder modal stays centered in the viewport when the page is scrolled.

### Prerequisites
- Chat has multiple messages (scroll past viewport height)
- Voice recording permissions granted

### Test Steps
1. **Scroll to top of chat**
   - Click voice record button (microphone icon)
   - ✅ **Expected:** Modal appears centered in viewport
   - ✅ **Expected:** Backdrop covers entire visible area
   - ✅ **Expected:** Background scroll is disabled

2. **Scroll to middle of chat**
   - Scroll down halfway through conversation
   - Click voice record button
   - ✅ **Expected:** Modal appears centered in viewport (not at original scroll position)
   - ✅ **Expected:** Modal position doesn't jump or shift

3. **Scroll to bottom of chat**
   - Scroll to very bottom of chat
   - Click voice record button
   - ✅ **Expected:** Modal still centered in viewport
   - ✅ **Expected:** No white space or positioning issues

4. **Test backdrop click**
   - With modal open at any scroll position
   - Click outside modal on backdrop
   - ✅ **Expected:** Modal closes smoothly
   - ✅ **Expected:** Scroll position restored

5. **Test body scroll lock**
   - Open voice recorder modal
   - Try to scroll page with mouse wheel
   - ✅ **Expected:** Page does not scroll while modal is open
   - Close modal
   - ✅ **Expected:** Can scroll normally again

### Pass Criteria
- [ ] Modal is always centered regardless of scroll position
- [ ] No positioning jumps or shifts
- [ ] Backdrop covers entire viewport
- [ ] Body scroll is prevented during recording
- [ ] Modal animations are smooth (0.3s ease)

---

## Test Case 2: Voice Recorder Animation Performance

### Objective
Verify smooth, non-clunky animations for the voice recorder.

### Test Steps
1. **Test modal entry animation**
   - Click voice record button
   - ✅ **Expected:** Modal scales from 0.9 to 1.0 smoothly
   - ✅ **Expected:** Opacity fades in over 0.3s
   - ✅ **Expected:** No jank or stuttering

2. **Test pulse rings**
   - While recording is active
   - ✅ **Expected:** Two pulsing rings animate outward
   - ✅ **Expected:** Duration is 1.5s (not 2s - faster feel)
   - ✅ **Expected:** Smooth easing, no abrupt changes

3. **Test waveform animation**
   - While recording
   - ✅ **Expected:** 15 bars (not 20) animating in wave pattern
   - ✅ **Expected:** Each bar has independent rhythm
   - ✅ **Expected:** Smooth at 60fps, no dropped frames

4. **Test modal exit**
   - Click stop or backdrop
   - ✅ **Expected:** Modal scales down and fades out smoothly
   - ✅ **Expected:** Exit animation is 0.3s
   - ✅ **Expected:** Clean removal from DOM

### Pass Criteria
- [ ] All animations run at 60fps
- [ ] Pulse duration is 1.5s (optimized)
- [ ] Waveform has 15 bars (optimized from 20)
- [ ] No visual jank or stuttering
- [ ] Animations feel snappy, not sluggish

---

## Test Case 3: Spotify Player Collision Detection

### Objective
Verify Spotify player smoothly avoids ScrollToBottom button.

### Prerequisites
- Spotify authenticated
- Chat has enough messages to trigger scroll

### Test Steps
1. **Initial state - scroll at bottom**
   - Scroll to bottom of chat
   - ✅ **Expected:** Spotify player at `bottom-6` (24px from bottom)
   - ✅ **Expected:** ScrollToBottom button is hidden

2. **Scroll up to trigger button**
   - Scroll up by 200px
   - Wait 1 second for detection
   - ✅ **Expected:** ScrollToBottom button appears at `bottom-24` (96px)
   - ✅ **Expected:** Spotify player smoothly moves to `bottom-20` (80px)
   - ✅ **Expected:** Transition is smooth (300ms)
   - ✅ **Expected:** No overlap between elements

3. **Scroll back to bottom**
   - Scroll all the way to bottom
   - ✅ **Expected:** ScrollToBottom button fades out
   - ✅ **Expected:** Spotify player smoothly returns to `bottom-6`
   - ✅ **Expected:** Transition is smooth

4. **Rapid scroll testing**
   - Rapidly scroll up and down multiple times
   - ✅ **Expected:** Spotify player transitions are smooth, not jittery
   - ✅ **Expected:** No animation queue buildup

5. **Z-index verification**
   - Inspect elements with dev tools
   - ✅ **Expected:** ScrollToBottom has `z-40`
   - ✅ **Expected:** Spotify player has `z-50`
   - ✅ **Expected:** Both are above content but below modals

### Pass Criteria
- [ ] Spotify player detects ScrollToBottom visibility
- [ ] Position transitions are smooth (300ms)
- [ ] No visual overlap or collision
- [ ] Works in all three Spotify states (login, minimized, full player)
- [ ] MutationObserver updates correctly

---

## Test Case 4: General Animation Quality

### Objective
Verify all UI animations feel smooth and polished, not clunky.

### Test Steps
1. **Message list animations**
   - Send multiple messages quickly
   - ✅ **Expected:** Messages stagger in with 0.08s delay
   - ✅ **Expected:** Max stagger cap is 400ms (good UX)
   - ✅ **Expected:** Smooth fade + slide animation

2. **Input area focus**
   - Click on message input
   - ✅ **Expected:** Subtle scale to 1.01 on focus
   - ✅ **Expected:** Glow effect appears smoothly
   - ✅ **Expected:** No jarring transitions

3. **Button hover states**
   - Hover over various buttons (send, voice, etc.)
   - ✅ **Expected:** Scale to 1.06 smoothly
   - ✅ **Expected:** Color transitions are smooth
   - ✅ **Expected:** No lag or delay

4. **Slash command palette**
   - Type "/" to open command palette
   - ✅ **Expected:** Slides down smoothly from input
   - ✅ **Expected:** Items have hover states
   - ✅ **Expected:** Selection is clear and smooth

5. **Toast notifications**
   - Trigger various notifications
   - ✅ **Expected:** Slide in from bottom smoothly
   - ✅ **Expected:** Stack properly without overlap
   - ✅ **Expected:** Dismiss animations are clean

### Pass Criteria
- [ ] All animations run at stable 60fps
- [ ] No clunky or abrupt transitions
- [ ] Consistent timing (fast = 150-200ms, standard = 300ms)
- [ ] Proper use of easing curves
- [ ] Hardware-accelerated (transform/opacity)

---

## Test Case 5: Modal Stack Z-Index Hierarchy

### Objective
Verify proper z-index stacking for all overlays.

### Test Steps
1. **Open help overlay (⌘?)**
   - ✅ **Expected:** Help at `z-50`, above all content

2. **Open voice recorder**
   - ✅ **Expected:** Recorder at `z-40` backdrop, `z-50` modal
   - ✅ **Expected:** Appears above help if both somehow open

3. **Check header**
   - Scroll down
   - ✅ **Expected:** Header sticky at `z-50`
   - ✅ **Expected:** Header stays above content

4. **Multiple modals**
   - Try opening multiple modal scenarios
   - ✅ **Expected:** Proper dismissal order
   - ✅ **Expected:** No z-index fighting

### Pass Criteria
- [ ] Clear visual hierarchy
- [ ] No element overlap conflicts
- [ ] Modals always above content
- [ ] Sticky header works correctly

---

## Test Case 6: Responsive Behavior

### Objective
Verify UI works on different screen sizes.

### Test Steps
1. **Desktop (1920x1080)**
   - Test all above scenarios
   - ✅ **Expected:** Everything works as specified

2. **Laptop (1280x720)**
   - Resize browser window
   - ✅ **Expected:** Spotify player stays in corner
   - ✅ **Expected:** Modals stay centered
   - ✅ **Expected:** No horizontal scroll

3. **Mobile simulation**
   - Use Chrome DevTools mobile view
   - ✅ **Expected:** Voice recorder adapts to small screen
   - ✅ **Expected:** Spotify player doesn't overflow
   - ✅ **Expected:** Touch interactions work

### Pass Criteria
- [ ] All breakpoints work correctly
- [ ] No overflow or scroll issues
- [ ] Modals adapt to screen size
- [ ] Touch targets are adequate (44px minimum)

---

## Test Case 7: Edge Cases

### Objective
Test unusual scenarios and edge cases.

### Test Steps
1. **Very long chat**
   - Load 200+ messages
   - Open voice recorder at various scroll positions
   - ✅ **Expected:** No performance degradation
   - ✅ **Expected:** Modal still centers correctly

2. **Rapid modal toggling**
   - Open and close voice recorder rapidly (10 times)
   - ✅ **Expected:** No animation queue buildup
   - ✅ **Expected:** Clean state transitions

3. **Spotify player states**
   - Switch between login, minimized, full player rapidly
   - ✅ **Expected:** Smooth transitions
   - ✅ **Expected:** Position updates correctly

4. **Network interruption**
   - Disconnect network
   - Try voice recording
   - ✅ **Expected:** Error state displays correctly
   - ✅ **Expected:** Retry button works

### Pass Criteria
- [ ] No crashes or freezes
- [ ] Graceful error handling
- [ ] Performance remains smooth
- [ ] State management is correct

---

## Automated Performance Check

Run this in browser console while testing:

```javascript
// Monitor frame rate
let lastTime = performance.now();
let frames = 0;
let fps = 0;

function measureFPS() {
  frames++;
  const currentTime = performance.now();
  if (currentTime >= lastTime + 1000) {
    fps = Math.round((frames * 1000) / (currentTime - lastTime));
    frames = 0;
    lastTime = currentTime;
    console.log('FPS:', fps);
  }
  requestAnimationFrame(measureFPS);
}
measureFPS();
```

✅ **Expected:** FPS should stay at 60 during all animations

---

## Final Verification Checklist

### Critical Issues (Must Pass)
- [ ] Voice recorder modal centers correctly at all scroll positions
- [ ] No clunky animations detected
- [ ] Spotify player avoids button collision
- [ ] All z-index stacking is correct
- [ ] Body scroll lock works during modals

### Performance (Must Pass)
- [ ] All animations run at 60fps
- [ ] No jank or stuttering detected
- [ ] Optimized animation counts (15 bars, 1.5s duration)
- [ ] Smooth transitions throughout

### Polish (Should Pass)
- [ ] Backdrop blur works correctly
- [ ] Micro-interactions feel responsive
- [ ] Color transitions are smooth
- [ ] Loading states are present

---

## Bug Report Template

If issues are found, use this template:

```markdown
### Bug: [Short Description]

**Component:** [RecordingIndicator / SpotifyPlayer / etc.]
**Severity:** [Critical / High / Medium / Low]
**Browser:** [Chrome 120 / Safari 17 / etc.]

**Steps to Reproduce:**
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happens]

**Screenshots/Video:**
[If applicable]

**Console Errors:**
[Any errors in browser console]

**Suggested Fix:**
[If known]
```

---

## Test Results Summary

| Test Case | Status | Notes |
|-----------|--------|-------|
| TC1: Voice Recorder Scroll | ⏳ Pending | |
| TC2: Animation Performance | ⏳ Pending | |
| TC3: Spotify Collision | ⏳ Pending | |
| TC4: General Animations | ⏳ Pending | |
| TC5: Z-Index Hierarchy | ⏳ Pending | |
| TC6: Responsive Behavior | ⏳ Pending | |
| TC7: Edge Cases | ⏳ Pending | |

**Last Updated:** [Date]
**Tested By:** [Name]
**Build/Commit:** [Git commit hash]
