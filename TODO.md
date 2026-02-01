# Animation Optimization Plan

## Step 1: Optimize CSS Animations ✅
- Add hardware acceleration (will-change, transform: translateZ(0)) to key elements
- Reduce animation durations for smoother performance
- Simplify heavy effects like blur and complex transforms

## Step 2: Reduce Background Animations ✅
- Remove or simplify particleFloat animation on body::before
- Reduce sidebarBreath and chatBreath animations
- Keep essential animations like message slideIn and conversationFadeIn

## Step 3: Update JS for Smooth Scrolling ✅
- Replace basic scrollTop with requestAnimationFrame-based smooth scrolling
- Optimize message addition to avoid layout thrashing

## Step 4: Test and Verify
- Ensure animations are smooth without stuttering
- Check performance on different devices
